# This file is part of Scaffold
#
# Scaffold is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#
# Copyright 2025 Ledger SAS, written by Olivier Hériveaux


from . import Scaffold, Pull
from time import sleep
from enum import Enum
from typing import Optional
import crcmod
import colorama
import time


class CRCError(Exception):
    """Thrown when CRC of response is invalid"""

    def __init__(self, got: bytes, expected: bytes):
        self.got = got
        self.expected = expected

    def __str__(self):
        return f"Bad CRC: expected {self.expected.hex()}, got {self.got.hex()}."


class TRF7970ACommand(int, Enum):
    """TRF7970A command code, as defined in the datasheet."""

    IDLE = 0x00
    SOFTWARE_INIT = 0x03
    RF_COLLISION_AVOIDANCE = 0x04
    RESPONSE_RF_COLLISION_AVOIDANCE_1 = 0x05
    RESPONSE_RF_COLLISION_AVOIDANCE_2 = 0x06
    RESET_FIFO = 0x0F
    TRANSMISSION_WITHOUT_CRC = 0x10
    TRANSMISSION_WITH_CRC = 0x11
    DELAYED_TRANSMISSION_WITHOUT_CRC = 0x12
    DELAYED_TRANSMISSION_WITH_CRC = 0x13
    END_OF_FRAME_AND_TRANSMIT_NEXT_TIME_SLOT = 0x14
    BLOCK_RECEIVER = 0x16
    ENABLE_RECEIVER = 0x17
    TEST_INTERNAL_RF = 0x18
    TEST_EXTERNAL_RF = 0x19


class TRF7970ARegister(int, Enum):
    """TRF7970A register addresses, as defined in the datasheet."""

    CHIP_STATUS_CONTROL = 0x00
    ISO_CONTROL = 0x01
    ISO_IEC_14443B_TX_OPTIONS = 0x02
    ISO_IEC_14443A_HIGH_BIT_RATE_OPTIONS = 0x03
    TX_TIMER_CONTROL_HIGH = 0x04
    TX_TIMER_CONTROL_LOW = 0x05
    TX_PULSE_LENGTH_CONTROL = 0x06
    RX_NO_RESPONSE_WAIT_TIME = 0x07
    RX_WAIT_TIME = 0x08
    MODULATOR_AND_SYS_CLK_CONTROL = 0x09
    RX_SPECIAL_SETTING = 0x0A
    REGULATOR_AND_IO_CONTROL = 0x0B
    SPECIAL_FUNCTION_1 = 0x10
    SPECIAL_FUNCTION_2 = 0x11
    ADJUSTABLE_FIFO_IRQ_LEVELS = 0x14
    NFC_LOW_FIELD_LEVEL = 0x16
    NFCID1_NUMBER = 0x17
    NFC_TARGET_DETECTION_LEVEL = 0x18
    NFC_TARGET_PROTOCOL = 0x19
    IRQ_STATUS = 0x0C
    COLLISION_POSITION_AND_INTERRUPT_MASK = 0x0D
    COLLISION_POSITION = 0x0E
    RSSI_LEVELS_AND_OSCILLATOR_STATUS = 0x0F
    RAM_1 = 0x12
    RAM_2 = 0x13
    TEST_1 = 0x1A
    TEST_2 = 0x1B
    FIFO_STATUS = 0x1C
    TX_LENGTH_BYTE_1 = 0x1D
    TX_LENGTH_BUTE_2 = 0x1E
    FIFO_IO = 0x1F


class NFC:
    """
    NFC daughterboard driver to enable ISO 14443 communication with contactless
    cards.

    Uses a special scaffold daughterboard with the Texas Instruments TRF7970A
    RFID chip as a RF front-end. The chip is controlled via SPI using Scaffold
    SPI peripheral.

    The daughterboard has the following pinout:

    - D0: MOD modulation input
    - D1: SPI MISO
    - D2: Serial clock out
    - D6: IO0
    - D7: IO1
    - D8: IO2
    - D9: IO3
    - D10: SPI SS
    - D11: SPI MOSI
    - D12: SPI SCK
    - D13: ASK/OOK
    - D14: EN
    - D15: SYS_CLK
    """

    def __init__(self, scaffold: Scaffold):
        self.scaffold = scaffold
        scaffold.power.dut = 0
        self.pin_ss = scaffold.d10
        self.pin_en = scaffold.d14
        self.pin_io0 = scaffold.d6
        self.pin_io1 = scaffold.d7
        self.pin_io2 = scaffold.d8
        self.pin_clock_13_56 = scaffold.d15
        self.trigger = scaffold.iso14443.trigger
        self.spi = scaffold.spi0
        self.iso14443 = scaffold.iso14443
        scaffold.d0 << self.iso14443.tx
        scaffold.d1 >> self.iso14443.rx
        self.pin_clock_13_56 >> self.iso14443.clock_13_56

        self.pin_en << 0
        self.pin_ss << 0

        # According to the datasheet IO0, IO1 and IO2 must be tied to the
        # following values to select SPI communication with Slave Select.
        self.pin_io0 << 0
        self.pin_io1 << 1
        self.pin_io2 << 1

        self.spi.mosi >> scaffold.d11
        self.spi.miso << scaffold.d1
        self.spi.sck >> scaffold.d12
        self.spi.phase = 1
        self.spi.frequency = 1000000

        scaffold.d1.pull = Pull.UP
        self.crc_a = crcmod.mkCrcFun(0x11021, 0x6363, rev=True)

        # Used for I-block encapsulation
        self.block_number = 0

        self.verbose = False
        self.log_t_start = None

    def startup(self):
        """Power-on the NFC daughterboard and initialize the TRF7970A front-end."""
        self.scaffold.power.dut = 1
        sleep(2e-3)
        self.pin_ss << 1
        sleep(4e-3)
        self.pin_en << 1
        # Wait for the TRF7970A to be ready.
        # Below 2 ms sometimes it fails.
        sleep(4e-3)
        # Software reset
        self.command(TRF7970ACommand.SOFTWARE_INIT)
        self.command(TRF7970ACommand.IDLE)
        sleep(1e-3)
        # Read some registers and check their value after reset, as a sanity check.
        regs = (
            (TRF7970ARegister.CHIP_STATUS_CONTROL, 0x01),
            (TRF7970ARegister.ISO_CONTROL, 0x21),
            (TRF7970ARegister.ISO_IEC_14443B_TX_OPTIONS, 0x00),
            (TRF7970ARegister.ISO_IEC_14443A_HIGH_BIT_RATE_OPTIONS, 0x00),
            (TRF7970ARegister.TX_TIMER_CONTROL_HIGH, 0xC1),
            # We could read more, but this seems good enough to be confident.
        )
        for reg, value in regs:
            if self.register_read(reg) != value:
                print(f"DEBUG {reg} {value}")
                raise RuntimeError("TRF7970A not recognized")
        # Disable 27.12 MHz crystal, our crystal is 13.56 MHz.
        # Select OOK 100% modulation depth
        self.register_write(TRF7970ARegister.MODULATOR_AND_SYS_CLK_CONTROL, 0b00110001)
        self.register_write(TRF7970ARegister.ISO_CONTROL, 0b00001000)
        # Direct mode, RF ON, full output power
        # TODO bit 0 to 0
        self.register_write(TRF7970ARegister.CHIP_STATUS_CONTROL, 0b00100001)
        self.register_write(
            TRF7970ARegister.CHIP_STATUS_CONTROL, 0b01100001, keep_ss_low=True
        )
        self.spi.transmit(0)
        self.iso14443.power_on()

    def register_read(self, address: int) -> int:
        """
        Read a register of the TRF7970A front-end.

        :param address: 5-bit address.
        """
        assert address in range(32)
        self.pin_ss << 0
        self.spi.transmit(0b01000000 | address)
        result = self.spi.transmit(0)
        self.pin_ss << 1
        return result

    def register_write(self, address: int, value: int, keep_ss_low: bool = False):
        """
        Write a register of the TRF7970A front-end.

        :param address: 5-bit address.
        :param value: Byte to be written.
        """
        assert address in range(32)
        assert value in range(256)
        self.pin_ss << 0
        self.spi.transmit(address, read=False)
        self.spi.transmit(value, read=False)
        if not keep_ss_low:
            self.pin_ss << 1

    def command(self, value: TRF7970ACommand):
        """
        Sends a command to the TRF7970A front-end.

        :param value: 5-bit command index.
        """
        assert value in range(32)
        self.pin_ss << 0
        self.spi.transmit(0x80 | value, read=False)
        self.pin_ss << 1

    def reqa(self, read=True) -> bytes:
        """Sends REQA frame. Returns ATQA response bytes."""
        data = 0x26
        if self.verbose:
            self.log(True, "REQA", bytes((data,)))
        self.iso14443.transmit_short(data)
        result = self.iso14443.receive(bit_size_hint=19)
        if self.verbose:
            self.log(False, "ATQA", result)
        assert len(result) == 2
        return result

    def log(self, rw: bool, what: str, data: bytes):
        """
        Print log line in standard output.

        :param rw: True if data is sent to the card, card if data is read from the card.
        :param str: Frame type indication ("REQA", "ATQA", etc.).
        :param data: Data read/written from/to the card.
        """
        if rw:
            print(colorama.Fore.YELLOW, end="")
        else:
            print(colorama.Fore.CYAN, end="")
        sep = "│"
        rw_str = {False: "←", True: "→"}[rw]
        desc_lines = []
        while len(data) > 0:
            desc_lines.append(data[:32].hex())
            data = data[32:]
        if len(desc_lines) == 0:
            desc_lines.append("")
        t = time.time()
        if self.log_t_start is None:
            self.log_t_start = t
        dt = t - self.log_t_start
        print(
            f"{dt * 1000.0:>9.3f} ms {sep} Scaffold {rw_str} Card {sep} {what:<4} "
            f"{sep} {desc_lines[0]}"
        )
        for line in desc_lines[1:]:
            print(" " * 13 + sep + " " * 17 + sep + " " * 6 + sep + f" {line}")
        print(colorama.Fore.RESET, end="")

    def transmit(
        self,
        data: bytes,
        what_tx: str = "",
        what_rx: str = "",
        bit_size_hint: Optional[int] = None,
    ) -> bytes:
        """
        Transmits data to the card and reads the response. If card does not respond an
        empty byte string is returned.

        :param data: Bytes to be transmitted.
        :param what_tx: Transmitted frame type indication ("REQA" for instance).
            used when verbose is True.
        :param what_rx: Received frame type indication ("ATQA" for instance).
            used when verbose is True.
        :param bit_size_hint: If the number of expected bits in the response is known,
            it can be indicated as a hint to improve response readout performance. This
            number includes start and parity bits. If response has more bits than
            expected, it will still be read completely.
        """
        if self.verbose:
            self.log(True, what_tx, data)
        self.iso14443.transmit(data)
        response = self.iso14443.receive(bit_size_hint=bit_size_hint)
        if self.verbose:
            self.log(False, what_rx, response)
        return response

    def transmit_with_crc(
        self,
        data: bytes,
        what_tx: str = "",
        what_rx: str = "",
        bit_size_hint: int = None,
    ) -> bytes:
        """
        Transmits data, with CRC appended, reads the response and checks the received
        CRC validity.

        :param data: Bytes to be transmitted.
        :param what_tx: Transmitted frame type indication ("SEL" for instance).
            used when verbose is True.
        :param what_rx: Received frame type indication ("SAK" for instance).
            used when verbose is True.
        :param bit_size_hint: If the number of expected bits in the response is known,
            it can be indicated as a hint to improve response readout performance. This
            number includes start and parity bits. If response has more bits than
            expected, it will still be read completely.
        :raises CRCError: If received CRC is invalid.
        """
        frame = data + self.crc_a(data).to_bytes(2, "little")
        response = self.transmit(
            frame, what_tx=what_tx, what_rx=what_rx, bit_size_hint=bit_size_hint
        )
        assert len(response) >= 2
        got_crc = response[-2:]
        expected_crc = self.crc_a(response[:-2]).to_bytes(2, "little")
        if got_crc != expected_crc:
            raise CRCError(got_crc, expected_crc)
        return response[:-2]

    def sel(self, level: int) -> bytes:
        """
        Performs selection. This sends a SEL frame, reads the returned UID by the card
        and selects it with another SEL frame. Returns the UID returned during
        selection.
        Note: the returned UID can be partial, only the bytes corresponding to the
        selected cascade level are returned.

        :param level: Cascade level. Must be 1, 2 or 3.
        """
        sel = 0x93 + 2 * (level - 1)
        uid = self.transmit(
            bytes((sel, 0x20)), what_tx="SEL", what_rx="UID", bit_size_hint=46
        )
        self.transmit_with_crc(
            bytes((sel, 0x70)) + uid, what_tx="SEL", what_rx="SAK", bit_size_hint=28
        )
        return uid

    def rats(self) -> bytes:
        """
        Sends RATS (Request for Answer To Select) frame and returns PICC
        response.

        FSDI is set to 256 bytes. This value is the highest possible and is
        supported by Scaffold. CID is set to 0.
        """
        return self.transmit_with_crc(b"\xe0\x80", what_tx="RATS", what_rx="ATS")

    def apdu(self, apdu: bytes) -> bytes:
        """
        Sends an APDU and returns the response. Exchange is performed using I-blocks,
        and waiting time extension requests are handled transparently.

        :param apdu: APDU to be transmitted. Does not include I-block header or CRC.
        """
        iblock = bytes((0x02 + self.block_number,)) + apdu
        self.block_number = (self.block_number + 1) % 2
        response = self.transmit_with_crc(iblock)
        while response[0] & 0xC0 == 0xC0:
            # S-block with waiting time extension request
            response = self.transmit_with_crc(b"\xf2" + bytes((response[1],)))
        return response[1:]
