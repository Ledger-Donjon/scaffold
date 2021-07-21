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
# Copyright 2019 Ledger SAS, written by Olivier Hériveaux


from time import sleep
from typing import List


class NACKError(Exception):
    """
    This error is thrown when a STM32 devices responds with NACK byte to a
    command.
    """
    def __init__(self, tag=None):
        super().__init__('Device returned NACK to a command')
        self.tag = tag


class MemorySection:
    """ Describes a memory section of a device. """
    def __init__(self, start, end):
        """
        :param start: First address of the section.
        :param end: End address of the section (excluded from section, address
            of next section).
        """
        if end < start:
            raise ValueError('Invalid section addresses')
        self.start = start
        self.end = end

    @property
    def size(self):
        """ Size in bytes of the section. """
        return self.end - self.start


class STM32Device:
    """ Possible name and product ID tuple. """
    def __init__(self, name, pid, memory_mapping, offset_rdp=0):
        self.name = name
        self.pid = pid
        self.memory_mapping = memory_mapping
        self.offset_rdp = offset_rdp


class STM32:
    """
    Class for instrumenting STM32 devices using Scaffold board and API. The
    following Scaffold IOs are used:

    - D0: STM32 UART MCU RX pin, Scaffold UART TX
    - D1: STM32 UART MCU TX pin, Scaffold UART RX
    - D2: STM32 NRST pin for reset
    - D6: STM32 BOOT0 pin
    - D7: STM32 BOOT1 pin

    The uart0 peripheral of Scaffold board is used for serial communication
    with the ST bootloader.

    This class can communicate with the ST bootloader via USART1. This allows
    programming the Flash memory and then execute the loaded code.
    """

    # Acknoledge byte returned by STM32 bootloader.
    ACK = 0x79
    # Error byte returned by STM32 bootloader.
    NACK = 0x1f

    # Memory layout for STM32F20xxx
    map_f20xxx = {
        'option_bytes': MemorySection(0x1fffc000, 0x1fffc008),
        'system': MemorySection(0x1fff0000, 0x1fff7a10),
        'flash': MemorySection(0x08000000, 0x08100000)}

    # Memory layout for STM32F4xxx
    map_f40xxx = map_f20xxx

    # Memory layout for STM32L431xx
    map_l431xx = {
        'option_bytes': MemorySection(0x1fff7800, 0x1fff7810),
        'otp': MemorySection(0x1fff7000, 0x1fff7400),
        'system': MemorySection(0x1fff0000, 0x1fff7000),
        'flash': MemorySection(0x08000000, 0x08040000)}

    # See AN2606 for PID values
    PIDS = [
        STM32Device('STM32F05xxx', 0x440, {}),
        STM32Device('STM32F030x8', 0x440, {}),
        STM32Device('STM32F03xx4/6', 0x444, {}),
        STM32Device('STM32F2xxxx', 0x411, map_f20xxx, offset_rdp=1),
        STM32Device('STM32F40xxx/41xxx', 0x413, map_f40xxx, offset_rdp=1),
        STM32Device('STM32F42xxx/43xxx', 0x419, map_f40xxx, offset_rdp=1),
        STM32Device('STM32L43xxx/44xxx', 0x435, map_l431xx),
        STM32Device('STM32L45xxx/46xxx', 0x462, {}),
        STM32Device('STM32L47xxx/48xxx', 0x415, {}),
        STM32Device('STM32L496xx/4A6xx', 0x461, {}),
        STM32Device('STM32L4Rxx/4Sxx', 0x470, {})]

    def __init__(self, scaffold):
        """
        :param scaffold: An instance of :class:`scaffold.Scaffold` which will
            be configured and used to communicate with STM32 daughter board.
        """
        self.scaffold = scaffold
        self.scaffold.timeout = 1
        self.nrst = scaffold.d2
        self.uart = uart = scaffold.uart0
        self.boot0 = scaffold.d6
        self.boot1 = scaffold.d7
        # Connect the UART peripheral to D0 and D1.
        uart.rx << scaffold.d1
        scaffold.d0 << uart.tx
        uart.baudrate = 115200
        # Instance of STM32Device, set when reading the device ID.
        self.device = None

    def checksum(self, data):
        """
        Calculate the checksum of some data, according to the STM32
        bootloader protocol.

        :param data: Input bytes.
        :return: Checksum byte. This is the XOR of all input bytes.
        """
        result = 0x00
        for b in data:
            result ^= b
        return result

    def startup_bootloader(self):
        """
        Power-cycle and reset target device in bootloader mode (boot on System
        Memory) and initiate serial communication. The byte 0x7f is sent and
        the response byte 0x79 (ACK) is expected. If the device does not
        respond, a Timeout exception is thrown by Scaffold. The device will not
        respond if it is locked in RDP2 state (Readout Protection level 2).
        """
        self.scaffold.power.dut = 0
        self.boot0 << 1
        self.boot1 << 0
        self.nrst << 0
        sleep(0.1)
        self.scaffold.power.dut = 1
        sleep(0.1)
        self.nrst << 1
        sleep(0.1)
        # Send 0x7f byte for initiating communication
        self.uart.flush()
        self.uart.transmit(b'\x7f')
        self.wait_ack()

    def startup_flash(self):
        """
        Power-cycle and reset target device and boot from user Flash memory.
        """
        self.scaffold.power.dut = 0
        self.boot0 << 0
        self.boot1 << 0
        self.nrst << 0
        sleep(0.1)
        self.scaffold.power.dut = 1
        sleep(0.1)
        self.nrst << 1
        sleep(0.1)

    def command(self, index):
        """
        Send a command and return the response.

        :param index: Command index.
        :return: Response bytes.
        """
        self.uart.transmit(bytes([index, 0xff ^ index]))
        res = self.uart.receive(2)
        assert res[0] == self.ACK
        data = self.uart.receive(res[1]+2)
        assert data[-1] == self.ACK
        return data[0:-1]

    def wait_ack(self, tag=None):
        """
        Wait for ACK byte.

        :param tag: Tag which is set when NACKError are thrown. Useful for
            error diagnostic.
        """
        b = self.uart.receive(1)[0]
        if b == self.NACK:
            raise NACKError(tag)
        if b != self.ACK:
            raise Exception(f'Received 0x{b:02x} byte instead of ACK or NACK.')

    def wait_ack_or_nack(self):
        """
        Wait for ACK or NACK byte.

        :return: True if ACK has been received, False if NACK has been
            received.
        """
        b = self.uart.receive(1)[0]
        assert b in (self.ACK, self.NACK)
        return b == self.ACK

    def get(self):
        """
        Execute the Get command of the bootloader, which returns the version
        and the supported commands.
        """
        response = self.command(0x00)
        return response

    def get_id(self):
        """
        Execute the Get ID command. The result is interpreted and the class
        will try to find information if the ID matches a known device.
        """
        self.device = None
        response = self.command(0x02)
        pid = int.from_bytes(response, 'big', signed=False)
        for dev in self.PIDS:
            if dev.pid == pid:
                self.device = dev
        return pid

    def get_version_and_read_protection_status(self):
        self.uart.transmit(b'\x01\xfe')
        response = self.uart.receive(5)
        assert response[0] == self.ACK
        assert response[-1] == self.ACK
        return response[1:-1]

    def read_memory(self, address, length, trigger=0):
        """
        Tries to read some memory from the device. If requested size is larger
        than 256 bytes, many Read Memory commands are sent.

        :param address: Memory address to be read.
        :param size: Number of bytes to be read.
        :param trigger: 1 to enable trigger on command transmission.
        """
        result = bytearray()
        remaining = length
        while remaining > 0:
            chunk_size = min(256, remaining)
            self.uart.transmit(b'\x11\xee', trigger=trigger)
            self.wait_ack()
            buf = bytearray(address.to_bytes(4, 'big', signed=False))
            buf.append(self.checksum(buf))
            self.uart.transmit(buf)
            self.wait_ack()
            buf = bytearray()
            buf.append(chunk_size-1)
            buf.append((chunk_size-1) ^ 0xff)
            self.uart.transmit(buf)
            self.wait_ack()
            result += self.uart.receive(chunk_size)
            remaining -= chunk_size
            address += chunk_size
        return result

    def write_memory(self, address, data, trigger=0):
        """
        Write data to device memory. If target address is Flash memory, this
        function DOES NOT erase Flash memory prior to writing. If data size is
        larger than 256 bytes, many Write Memory commands are sent.

        :param address: Address.
        :param data: Data to be written. bytes or bytearray.
        :param trigger: 1 to enable trigger on each command transmission.
        """
        remaining = len(data)
        offset = 0
        while remaining > 0:
            chunk_size = min(256, remaining)
            self.uart.transmit(b'\x31\xce', trigger=trigger)
            self.wait_ack(0)
            buf = bytearray(
                (address + offset).to_bytes(4, 'big', signed=False))
            buf.append(self.checksum(buf))
            self.uart.transmit(buf)
            self.wait_ack(1)
            buf = bytearray()
            buf.append(chunk_size - 1)
            buf += data[offset:offset + chunk_size]
            buf.append(self.checksum(buf))
            self.uart.transmit(buf)
            self.wait_ack(2)
            offset += chunk_size
            remaining -= chunk_size

    def assert_device(self):
        """ Raise a RuntimeError is device is unknown (None). """
        if self.device is None:
            raise RuntimeError(
                'Unknown device or not discovered yet. Call get_id or set the '
                'device attribute.')

    def read_option_bytes(self):
        """
        Read the option bytes of the device. The method get_id must have been
        called previously for device identification.

        :return: Memory content of 'option_bytes' section.
        """
        self.assert_device()  # We need the memory mapping
        section = self.device.memory_mapping['option_bytes']
        return self.read_memory(section.start, section.size)

    def readout_protect(self):
        """
        Execute the Readout Unprotect command.
        """
        self.uart.transmit(b'\x82\x7d', 1)
        self.wait_ack()
        self.wait_ack()

    def readout_unprotect(self):
        """
        Execute the Readout Unprotect command. If the device is locked, it will
        perform mass flash erase, which can be very very long.
        """
        self.uart.transmit(b'\x92\x6d', 1)
        self.wait_ack()
        # When the chip is in RDP1 it will perform mass flash erase. This can
        # take a lot of time, so we must change the timeout setting.
        previous_timeout = self.scaffold.timeout
        self.scaffold.timeout = 30
        try:
            self.wait_ack()
        finally:
            # Restore timeout setting, even if something bad happened!
            self.scaffold.timeout = previous_timeout

    def write_protect(self, sectors: List[int]):
        """
        Execute Write Protect command.

        :param sectors: List of sectors to be write protected.
        """
        if len(sectors) not in range(1, 0x100):
            raise ValueError("Invalid sector count")
        self.uart.transmit(b'\x63\x9c')
        self.wait_ack()
        buf = bytearray()
        buf.append(len(sectors)-1)
        buf += bytes(sectors)
        buf.append(self.checksum(buf))
        self.uart.transmit(buf)
        self.wait_ack()

    def write_unprotect(self):
        """
        Execute Write Unprotect command.
        """
        self.uart.transmit(b'\x73\x8c')
        self.wait_ack()
        self.wait_ack()

    def extended_erase(self):
        """
        Execute the Extended Erase command to erase all the Flash memory of the
        device.
        """
        self.uart.transmit(b'\x44\xbb')
        self.wait_ack()
        buf = bytearray(b'\xff\xff')
        buf.append(self.checksum(buf))
        self.uart.transmit(buf, 1)
        previous_timeout = self.scaffold.timeout
        self.scaffold.timeout = 30
        try:
            self.wait_ack()
        finally:
            self.scaffold.timeout = previous_timeout

    def go(self, address, trigger=0):
        """
        Execute the Go command.

        :param address: Jump address.
        :param trigger: 1 to enable trigger on command transmission.
        """
        self.uart.transmit(b'\x21\xde', trigger=trigger)
        self.wait_ack()
        buf = bytearray(address.to_bytes(4, 'big', signed=False))
        buf.append(self.checksum(buf))
        self.uart.transmit(buf)
        self.wait_ack()
