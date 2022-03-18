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


from enum import Enum
from scaffold import Pull
from typing import Tuple, List, Union, Optional
from . import Scaffold
import requests
import crcmod


class ProtocolError(Exception):
    """
    Exception raised when a protocol error between the terminal and the
    smartcard occurs.
    """
    def __init__(self, message):
        super().__init__(message)


class Convention(Enum):
    """
    Possible ISO-7816 communication convention. This is given by the first byte
    of the ATR returned by the card.
    """
    INVERSE = 0x3f
    DIRECT = 0x3b


class T1RedundancyCode(Enum):
    """
    Possible ISO78-16 possible error detection codes that can be used for T=1
    protocol. It is indicated in the first TC byte for T=1 of the ATR.
    """
    LRC = 0
    CRC = 1


class T1RedundancyCodeError(Exception):
    """ Thrown when the redundancy code of a received block is invalid. """
    pass


def inverse_byte(byte):
    """
    Inverse order and polarity of bits in a byte. Used for ISO-7816 inverse
    convention decoding.
    """
    byte ^= 0xff
    return int(f'{byte:08b}'[::-1], 2)


def apply_convention(data: bytes, convention: Convention) -> bytes:
    """
    :return: `data` if convention is `DIRECT`, `data` with all bytes inversed
        if convention is `INVERSE`.
    """
    if convention == Convention.DIRECT:
        return data
    elif convention == Convention.INVERSE:
        return bytes(inverse_byte(b) for b in data)
    else:
        raise ValueError("invalid convention")


class ATRInfo:
    def __init__(self):
        self.atr = bytearray()
        self.convention = None
        self.protocols = set()
        self.t_abcd_n = []


class ScaffoldISO7816ByteReader:
    """ Used for `parse_atr` function with a Scaffold device. """
    def __init__(self, iso7816):
        """ :param iso7816: Scaffold ISO7816 module. """
        self.iso7816 = iso7816
        self.convention = Convention.DIRECT

    def read(self, n: int) -> bytes:
        return apply_convention(self.iso7816.receive(n), self.convention)


class BasicByteReader:
    """ Used for `parse_atr` function with a test vector. """
    def __init__(self, data: bytes):
        self.data = data

    def read(self, n: int) -> bytes:
        if len(self.data) < n:
            raise EOFError()
        chunk = self.data[:n]
        self.data = self.data[n:]
        return chunk


def parse_atr(reader) -> ATRInfo:
    """
    ATR parsing function used by Smartcard class when reading a card ATR. The
    reader object passed in arguments allows unit testing with a list of ATR.

    :param reader: An object giving requested bytes for parsing ATR.
    :return: ATR info.
    """
    info = ATRInfo()
    atr = info.atr
    # Receive and parse TS
    atr.append(reader.read(1)[0])
    ts = atr[0]
    try:
        info.convention = Convention(ts)
    except ValueError as e:
        raise ProtocolError(f'Invalid TS byte in ATR: 0x{ts:02x}') from e
    reader.convention = info.convention
    # Receive T0
    atr += reader.read(1)
    # Parse the rest of the ATR
    i = 1
    td = atr[i]
    while td is not None:
        has_t_abcd = list(bool(td & (1 << (j+4))) for j in range(4))
        count = has_t_abcd.count(True)
        atr += reader.read(count)
        t_abcd = [None, None, None, None]
        offset = 0
        for j in range(4):
            if has_t_abcd[j]:
                t_abcd[j] = atr[-count + offset]
                offset += 1
        info.t_abcd_n.append(t_abcd)
        # Test to skip T0 byte
        if i != 1:
            info.protocols.add(td & 0x0f)
        # Test TD presence
        if has_t_abcd[3]:
            td = atr[-1]
        else:
            td = None
        i += 1
    # If no protocol is specified, then T=0 is available by default
    if len(info.protocols) == 0:
        info.protocols.add(0)
    # Fetch historical bytes
    # Number of historical bytes is the low nibble of T0
    atr += reader.read(atr[1] & 0x0f)
    # Parse TCK (check byte)
    # This byte is absent if only T=0 is supported
    if info.protocols != {0}:
        # TCK expected
        atr += reader.read(1)
        # tck = atr[-1]
        # Verify the checksum
        xored = 0x00
        for b in atr[1:]:
            xored ^= b
        if xored != 0x00:
            raise ProtocolError('ATR checksum error')
    return info


class NoATRDatabase(Exception):
    """
    Thrown during card information lookup if no ATR database could be loaded
    """
    pass


def load_atr_info_db(allow_web_download: bool = False) \
        -> List[Tuple[str, List[str]]]:
    """
    Parse the smartcard ATR list database from Ludovic Rousseau to get list of
    known ATR.

    The database file cannot be embedded in the library because it uses GPL
    and not LGPL license. On debian systems, this file is provided in the
    pcsc-tools package. If this file is missing and `allow_web_download` is
    enabled, this method will read the file with an HTTP GET request to:
    http://ludovic.rousseau.free.fr/softwares/pcsc-tools/smartcard_list.txt

    ATR values are returned with strings, and can have '.' wildcards for
    matching, or other special formatting characters. With each ATR is returned
    of list of description strings.

    :param allow_web_download: If enabled, allow the method to download the
        database from the web as a fallback when it is missing from the system.
    :raises NoATRDatabase: When database file is missing and download is not
        allowed, or when database file is missing and download failed.
    """
    tab = []
    try:
        text_file = open('/usr/share/pcsc/smartcard_list.txt', 'r')
        # We don't want to keep end lines such as LR or CR LF
        lines = text_file.read().splitlines()
        text_file.close()
    except FileNotFoundError:
        if allow_web_download:
            url = "http://ludovic.rousseau.free.fr/softwares/pcsc-tools/" \
                + "smartcard_list.txt"
            try:
                res = requests.get(url)
            except Exception:
                raise NoATRDatabase()
            if res.status_code != 200:
                raise NoATRDatabase()
            lines = res.content.decode().splitlines()
        else:
            raise NoATRDatabase()
    # Parse the file and build a table with ATR patterns and infos
    for line in lines:
        if (len(line) > 0) and (line[0] not in ('#', '\t')):
            # ATR line
            atr = line.replace(' ', '').lower()
            tab.append((atr, []))
        elif (len(line) > 0) and (line[0] == '\t'):
            # Info line
            # Remove first character \t
            tab[-1][1].append(line[1:])
    return tab


class Smartcard:
    """
    Class for smartcard testing with Scaffold board and API. The
    following IOs are used:

    - D0: ISO-7816 IO
    - D1: ISO-7816 nRST
    - D2: ISO-7816 CLK
    - D3: Socket card contactor sense

    :class:`scaffold.Scaffold` class has ISO-7816 peripheral support, but it is
    very limited. This class enables full support to ISO-7816 by managing ATR,
    convention convertion, T=0 or T=1 protocols, etc.

    :var bytes atr: ATR received from card after reset.
    :var Convention convention: Communication convention between card
        and terminal. Updated when first byte TS of ATR is received.
    :var set protocols: Communication protocols found in ATR. This set contains
        integers, for instance 0 if T=0 is supported, 1 if T=1 is supported...
    """
    def __init__(self, scaffold: Scaffold = None):
        """
        Configure a Scaffold board for use with smartcards.

        :param scaffold: Board instance which will be configured as a smartcard
            reader. :class:`scaffold.Scaffold` instance.
        """
        if scaffold is None:
            scaffold = Scaffold()
        self.iso7816 = scaffold.iso7816
        self.scaffold = scaffold
        self.sig_nrst = scaffold.d1
        self.sig_sense = scaffold.d3
        self.sig_nrst << 1
        # D0 is connected to a bidirectionnal bus. We enable the pull-up
        # resistor if hardware version is >= 1.1. For version 1.0, the pull-up
        # resistor must be soldered on the daughterboard.
        # 1.0 hardware version boards have <= 0.3 architecture version.
        if scaffold.version >= "0.3":
            scaffold.d0.pull = Pull.UP
        scaffold.d0 << scaffold.iso7816.io_out
        scaffold.d0 >> scaffold.iso7816.io_in
        scaffold.d2 << scaffold.iso7816.clk
        self.atr = None
        self.convention = Convention.DIRECT
        self.crc16 = None
        self.t1_ns_tx = 0  # Sequence number for I-block tranmission in T=1
        self.t1_ns_rx = 0  # Sequence number for I-block reception in T=1

    def receive(self, n: int) -> bytes:
        """
        Use the ISO-7816 peripheral to receive bytes from the smartcard, and
        apply direct or inverse convention depending on what has been read in
        the ATR.

        :param n: Number of bytes to be read.
        """
        return apply_convention(self.iso7816.receive(n), self.convention)

    def reset(self) -> bytes:
        """
        Reset the smartcard and retrieve the ATR.

        If the ATR is retrieved successfully, the attributes :attr:`atr`
        :attr:`convention` and :attr:`protocols` are updated.

        :attr:`protocols` indicates what protocols are supported. It will
            contain 0 if T=0 is supported, and 1 if T=1 is supported.

        If only T=1 is supported, exchanges using :meth:`apdu` will use I-block
        transmission automatically.

        :return: ATR from the card.
        :raises ProtocolError: if the ATR is not valid.
        """
        self.sig_nrst << 0
        self.iso7816.flush()
        self.sig_nrst << 1
        info = parse_atr(ScaffoldISO7816ByteReader(self.iso7816))
        self.atr = info.atr
        self.convention = info.convention
        self.protocols = info.protocols
        self.atr_info = info
        # If T=1 is supported, read in TC1 the correct redundancy code to be
        # used
        if 1 in self.protocols:
            tc1 = self.atr_info.t_abcd_n[0][2]
            self.t1_ns_tx = 0
            self.t1_ns_rx = 0
            if tc1 is not None:
                self.t1_redundancy_code = T1RedundancyCode(tc1 & 1)
            else:
                self.t1_redundancy_code = T1RedundancyCode.LRC
        else:
            self.t1_redundancy_code = None
        # Verify that there are no more bytes
        if not self.iso7816.empty:
            raise ProtocolError('Unexpected bytes after ATR')
        return info.atr

    def apdu(self, the_apdu: Union[bytes, str], trigger: str = '') -> bytes:
        """
        Send an APDU to the smartcard and retrieve the response.

        If only T=1 protocol is supported, this method use `transmit_block` and
        `receive_block` to send the APDU by sending information blocks.

        :param the_apdu: APDU to be sent. str hexadecimal strings are allowed,
            but user should consider using the :meth:`apdu_str` method instead.
        :param trigger: If 'a' is in this string, trigger is raised after
            ISO-7816 header is sent in T=0, and cleared when the following
            response byte arrives. If 'b' is in this string, trigger is raised
            after data field has been transmitted in T=0, and cleared when the
            next response byte is received. If T=1, both 'a' and 'b' will raise
            trigger after the I-block has been transmitted, and will be cleared
            when first byte of next block is received.
        :raises ValueError: if APDU data is invalid.
        :raises RuntimeError: if the received procedure byte is invalid in T=0,
            or if neither T=0 and T=1 protocols are supported by the card.
        :raises T1RedundancyCodeError: If LRC or CRC is wrong in T=1 protocol.
        :return: Response data, with status word.
        """
        if type(the_apdu) == str:
            the_apdu = bytes.fromhex(the_apdu)
        apdu_len = len(the_apdu)
        if apdu_len < 5:
            raise ValueError('APDU too short')
        if 0 in self.protocols:
            return self.__apdu_t0(the_apdu, trigger)
        elif 1 in self.protocols:
            return self.__apdu_t1(
                the_apdu, ('a' in trigger) or ('b' in trigger))
        else:
            raise RuntimeError("Neither T=0 or T=1 are supported by the card")

    def __apdu_t0(self, the_apdu: bytes, trigger: str = '') -> bytes:
        """
        Send an APDU to the smartcard and retrieve the response, using T=0
        protocol.

        :param the_apdu: APDU to be sent.
        :param trigger: If 'a' is in this string, trigger is raised after
            ISO-7816 header is sent, and cleared when the following response
            byte arrives. If 'b' is in this string, trigger is raised after
            data field has been transmitted, and cleared when the next
            response byte is received.
        :raises ValueError: if APDU data is invalid.
        :raises RuntimeError: if the received procedure byte is invalid.
        :return: Response data, with status word.
        """
        out_data_len = len(the_apdu) - 5
        if out_data_len > 256:
            raise ValueError('APDU too long')
        if out_data_len > 0:
            # This is an outgoing data transfer
            # Verify APDU P3 field correctness
            p3 = the_apdu[4]
            expected_p3 = out_data_len % 256
            if p3 != expected_p3:
                raise ValueError(
                    'Expected P3 (length) in APDU is '
                    f'0x{expected_p3:02x}, got 0x{p3:02x}')
            in_data_len = 0
        else:
            if the_apdu[4] > 0:
                in_data_len = the_apdu[4]
            else:
                in_data_len = 256
        # Transmit the header
        if 'a' in trigger:
            with self.scaffold.lazy_section():
                self.iso7816.transmit(the_apdu[:4])
                self.iso7816.trigger_long = 1
                self.iso7816.transmit(the_apdu[4:5])
        else:
            # Send all the header at once
            with self.scaffold.lazy_section():
                self.iso7816.trigger_long = 0
                self.iso7816.transmit(the_apdu[:5])
        # Receive procedure byte
        procedure_byte = self.iso7816.receive(1)[0]
        if 'a' in trigger:  # Disable only if enabled previously
            self.iso7816.trigger_long = 0
        while procedure_byte == 0x60:
            procedure_byte = self.iso7816.receive(1)[0]
        response = bytearray()
        ins = the_apdu[1]
        if (procedure_byte & 0xf0) in (0x60, 0x90):
            # Received SW1 byte.
            response.append(procedure_byte)
            # Received SW2
            response.append(self.iso7816.receive(1)[0])
            return response
        elif procedure_byte in (ins, ~ins):
            # Acknowledge byte.
            # Transfer the remaining data
            if out_data_len > 0:
                if 'b' in trigger:
                    # Enable trigger on last byte only
                    self.iso7816.transmit(the_apdu[5:-1])
                    self.iso7816.trigger_long = 1
                    self.iso7816.transmit(the_apdu[-1:])
                else:
                    # Send all remaining data at once
                    self.iso7816.transmit(the_apdu[5:])
            # Receive the response data and status word
            response += self.iso7816.receive(in_data_len + 2)
            if 'b' in trigger:  # Disable only if enabled previously
                self.iso7816.trigger_long = 0
            return response
        else:
            raise RuntimeError(
                f'Unexpected procedure byte 0x{procedure_byte:02x} received')

    def __apdu_t1(self, the_apdu: bytes, trigger: bool = False) -> bytes:
        """
        Send an APDU to the smartcard and retrieve the response, using T=1
        protocol. Transmission supports chaining for both command and response.

        :param the_apdu: APDU to be sent.
        :param trigger: If True, raise trigger on last byte of last I-block
            transmission.
        :return: Response data, with status word.
        :raises T1RedundancyCodeError: If LRC or CRC is wrong.
        :raises ProtocolError: If an unpexpected response is received.
        """
        edc_len_dict = {T1RedundancyCode.LRC: 1, T1RedundancyCode.CRC: 2}

        apdu_remaining = the_apdu
        while len(apdu_remaining):
            chunk = apdu_remaining[:254]
            apdu_remaining = apdu_remaining[254:]
            has_more = min(1, len(apdu_remaining))
            enable_trigger = trigger and not has_more
            # Send I-block
            self.transmit_block(
                0, (self.t1_ns_tx << 6) + (has_more << 5), chunk,
                enable_trigger)
            # Increment sequence number
            self.t1_ns_tx = (self.t1_ns_tx + 1) % 2
            if has_more:
                # We expect a R-block before sending the next info block
                block = self.receive_block()
                pcb = block[1]
                if pcb & (1 << 7) == 0:  # I-block
                    raise ProtocolError('Expected R-block, received I-block')
                elif pcb & (1 << 6) == 0:  # R-block
                    if pcb & 0x0f == 0:  # Error free acknowledgement
                        pass
                    elif pcb & 0x0f == 1:
                        raise ProtocolError(
                            'Redundancy code error reported by card')
                    else:
                        raise ProtocolError(
                            'Unspecified error reported by card')
                else:  # S-block
                    raise ProtocolError('Expected R-block, received I-block')

        response = bytearray()
        has_more = True
        while has_more:
            block = self.receive_block()
            if enable_trigger:
                self.iso7816.trigger_long = 0
            pcb = block[1]
            if pcb & (1 << 7) == 0:  # I-block
                # Check that the sequence number is correct
                if (pcb >> 6) & 1 != self.t1_ns_rx:
                    raise ProtocolError(
                        'Incorrect received sequence number in I-block '
                        + block.hex())
                has_more = bool((pcb >> 5) & 1)
                edc_len = edc_len_dict[self.t1_redundancy_code]
                response += block[3:-edc_len]  # Trim header and EDC
            elif pcb & (1 << 6) == 0:  # R-block
                raise ProtocolError('Expected I-block, received R-block')
            else:  # S-block
                raise ProtocolError('Expected I-block, received S-block')

            self.t1_ns_rx = (self.t1_ns_rx + 1) % 2
            if has_more:
                # Send R block
                self.transmit_block(0, 0b10000000 + (self.t1_ns_rx << 4), b'')

        return response

    def pps(self, pps1: int) -> int:
        """
        Send a PPS request to change the communication speed parameters Fi and
        Di (as specified in ISO-7816-3). PPS0 and PPS1 are sent. PPS2 is
        ignored. This method waits for the response of the card and then
        automatically changes the ETU from the Fi and Di values.
        Scaffold hardware does not support all possible parameters:
        ETU = Fi/Di must not have a fractional part.

        :param pps1: Value of the PPS1 byte.
        :return: New etu value.
        :raises ValueError: if Fi or Di parameters in PPS1 are reserved.
        :raises ValueError: if target ETU has a fractional part.
        :raises RuntimeError: if response to PPS request is invalid.
        """
        if pps1 not in range(0x100):
            raise ValueError('Invalid PPS1 value')
        fi = ([372, 372, 558, 744, 1116, 1488, 1860, None, None, 512, 768,
               1024, 1536, 2048, None, None][pps1 >> 4])
        if fi is None:
            raise ValueError('Fi parameter in PPS1 has a reserved value')
        di = ([None, 1, 2, 4, 8, 16, 32, 64, 12, 20, None, None, None, None,
               None, None][pps1 & 0x0f])
        if di is None:
            raise ValueError('Di parameter in PPS1 has a reserved value')
        # PPSS = 0xff
        # PPS0 = 0x10 to indicate presence of PPS1
        request = bytearray(b'\xff\x10')
        request.append(pps1)
        etu = round(fi / di)
        if etu != fi / di:
            raise ValueError(
                f'Cannot set ETU to {etu} because of the '
                'fractional part (hardware limitation)')
        # Checksum
        pck = 0
        for b in request:
            pck ^= b
        request.append(pck)
        # Send the request
        self.iso7816.transmit(request)
        # Get the response
        res = self.iso7816.receive(4, timeout=1)
        if res == request:
            # Negociation is successfull
            self.iso7816.etu = etu
            return etu
        else:
            raise RuntimeError('PPS request failed')

    def find_info(self, allow_web_download: bool = False) \
            -> Optional[List[str]]:
        """
        Parse the smartcard ATR list database available at
        http://ludovic.rousseau.free.fr/softwares/pcsc-tools/smartcard_list.txt
        and try to match the current ATR to retrieve more info about the card.

        The database file cannot be embedded in the library because it uses GPL
        and not LGPL license. On debian systems, this file is provided in the
        pcsc-tools package.

        :param allow_web_download: If enabled, allow the method to download the
            database from the web as a fallback when it is missing from the
            system.
        :return: A list of str, where each item is an information line about
            the card. Return None if the ATR did not match any entry in the
            database.
        :raises NoATRDatabase: When database file is missing and download is
            not allowed, or when database file is missing and download failed.
        """
        tab = load_atr_info_db(allow_web_download)
        # Try to match ATR
        for item in tab:
            pattern = item[0]
            atr = self.atr.hex()
            if len(pattern) != len(atr):
                continue
            match = True
            for i in range(len(pattern)):
                if pattern[i] != '.':
                    if pattern[i] != atr[i]:
                        match = False
                        break
            if match:
                return item[1]
                break

    def apdu_str(self, the_apdu: str) -> str:
        """
        Same as :meth:`apdu` function, with str argument and return type for
        convenience.

        :param the_apdu: APDU to be sent, as an hexadecimal string.
        :return: Response from the card, as a lowercase hexadecimal string
            without spaces.
        """
        return self.apdu(bytes.fromhex(the_apdu)).hex()

    def calculate_edc(self, data: bytes) -> bytes:
        """
        Calculate expected error detection code for a block. Depending on
        `self.t1_redundancy_code` LRC (1 bytes) or CRC (2 bytes) is calculated.

        :param data: Input data for the error detection code calculation.
            Includes all bytes of the block excepted the LRC or CRC bytes.
        :return: ECC bytes at the end of the block.
        """
        if self.t1_redundancy_code == T1RedundancyCode.LRC:
            result = 0
            for b in data:
                result = result ^ b
            return bytes([result])
        elif self.t1_redundancy_code == T1RedundancyCode.CRC:
            # CRC is CRC-16-CCITT, with initial value 0xffff
            # I cannot tell if this is correct as it does not seem very well
            # documented and I don't have any card to test this...
            if self.crc16 is None:
                self.crc16 = crcmod.mkCrcFun(0x11021, 0xffff, rev=False)
            return self.crc16(data).to_bytes(2, 'big')
        else:
            raise RuntimeError("invalid t1_redundancy_code value")

    def transmit_block(self, nad: int, pcb: int, info: bytes = b"",
                       trigger: bool = False):
        """
        Transmit a T=1 protocol block.
        Error detection code is calculated and appended automatically.

        :param nad: Node address byte.
        :param pcb: Protocol control byte.
        :param info: Information field.
        :param trigger: If True, raise trigger on last byte transmission.
        """
        if len(info) > 254:
            raise ValueError(
                f"info field is too long ({len(info)} > 254)")
        data = bytearray([nad, pcb, len(info)]) + info
        data += self.calculate_edc(data)
        with self.scaffold.lazy_section():
            if trigger:
                self.iso7816.transmit(data[:-1])
                self.iso7816.trigger_long = 1
                self.iso7816.transmit(data[-1:])
            else:
                self.iso7816.trigger_long = 0
                self.iso7816.transmit(data)

    def receive_block(self) -> bytes:
        """
        Receive a T=1 protocol block.

        :raises T1RedundancyCodeError: If LRC or CRC is wrong.
        """
        block = self.iso7816.receive(3)
        if self.t1_redundancy_code == T1RedundancyCode.LRC:
            edc_len = 1
        elif self.t1_redundancy_code == T1RedundancyCode.CRC:
            edc_len = 2
        block += self.iso7816.receive(block[2] + edc_len)
        # Verify LRC/CRC
        if self.calculate_edc(block[:-edc_len]) != block[-edc_len:]:
            raise T1RedundancyCodeError()
        return block

    @property
    def card_inserted(self):
        """
        True if a card is inserted, False otherwise. Card insertion is detected
        with a mecanical switch connected to D3 of Scaffold.
        """
        return self.sig_sense.value == 1
