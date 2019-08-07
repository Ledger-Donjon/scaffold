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
from binascii import hexlify
from scaffold import Pull
import os.path


class ProtocolError(Exception):
    """
    Exception raised when a protocol error between the terminal and the
    smartcard occurs.
    """
    def __init__(self, message):
        super().__init__(message)


class Convention(Enum):
    """
    Possible ISO7816 communication convention. This is given by the first byte
    of the ATR returned by the card.
    """
    INVERSE = 0x3f
    DIRECT = 0x3b


class Smartcard:
    """
    Class for smartcard testing with Scaffold board and API. The
    following IOs are used:

    - D0: ISO7816 IO
    - D1: ISO7816 nRST
    - D2: ISO7816 CLK
    - D3: Socket card contactor sense

    :class:`scaffold.Scaffold` class has ISO7816 peripheral support, but it is
    very limited. This class adds full support to ISO7816 by managing ATR,
    convention convertion, etc.

    :var bytes atr: ATR received from card after reset.
    :var Convention convention: Communication convention between card
        and terminal. Updated when first byte TS of ATR is received.
    :var set protocols: Communication protocols found in ATR. This set contains
        integers, for instance 0 if T=0 is supported, 1 if T=1 is supported...
    """
    def __init__(self, scaffold):
        """
        Configure a Scaffold board for use with smartcards.
        :param scaffold: :class:`scaffold.Scaffold` instance.
        """
        self.iso7816 = scaffold.iso7816
        self.scaffold = scaffold
        self.sig_nrst = scaffold.d1
        self.sig_sense = scaffold.d3
        self.sig_nrst << 1
        # D0 is connected to a bidirectionnal bus. We enable the pull-up
        # resistor if hardware version is >= 1.1. For version 1.0, the pull-up
        # resistor must be soldered on the daughterboard.
        # 1.0 hardware version boards have <= 0.3 architecture version.
        if float(scaffold.version) >= 0.3:
            scaffold.d0.pull = Pull.UP
        scaffold.d0 << scaffold.iso7816.io_out
        scaffold.d0 >> scaffold.iso7816.io_in
        scaffold.d2 << scaffold.iso7816.clk
        self.atr = None
        self.convention = Convention.DIRECT

    def inverse_byte(self, byte):
        """
        Inverse order and polarity of bits in a byte. Used for ISO7816 inverse
        convention decoding.
        """
        byte ^= 0xff
        return int(f'{byte:08b}'[::-1], 2)

    def receive(self, n):
        """
        Use the ISO7816 peripheral to receive bytes from the smartcard, and
        apply direct or inverse convention depending on what has been read in
        the ATR.

        :param n: Number of bytes to be read.
        """
        data = self.iso7816.receive(n)
        if self.convention == Convention.INVERSE:
            for i in range(len(data)):
                data[i] = self.inverse_byte(data[i])
        return data

    def reset(self):
        """
        Reset the smartcard and retrieve the ATR.
        If the ATR is retrieved successfully, the attributes :attr:`atr`
        :attr:`convention` and :attr:`protocols` are updated.

        :return: ATR from the card.
        :raises ProtocolError: if the ATR is not valid.
        """
        self.sig_nrst << 0
        self.iso7816.flush()
        self.sig_nrst << 1
        # Receive and parse TS
        atr = bytearray(self.iso7816.receive(1))
        ts = atr[0]
        try:
            self.convention = Convention(ts)
        except ValueError as e:
            raise ProtocolError(f'Invalid TS byte in ATR: 0x{ts:02x}') \
                from e
        # Receive T0
        atr += self.receive(1)
        # Parse the rest of the ATR
        self.protocols = protocols = set()
        i = 1
        td = atr[i]
        while td is not None:
            has_t_abcd = list(bool(td & (1 << (j+4))) for j in range(4))
            count = has_t_abcd.count(True)
            atr += self.receive(count)
            # Test to skip T0 byte
            if i != 1:
                protocols.add(td & 0x0f)
            # Test TD presence
            if has_t_abcd[3]:
                td = atr[-1]
            else:
                td = None
        # If no protocol is specified, then T=0 is available by default
        if len(protocols) == 0:
            protocols.add(0)
        # Fetch historical bytes
        # Number of historical bytes is the low nibble of T0
        atr += self.receive(atr[1] & 0x0f)
        # Parse TCK (check byte)
        # This byte is absent is only T=0 is supported
        if protocols != {0}:
            # TCK expected
            atr += self.receive(1)
            tck = atr[-1]
            # Verify the checksum
            xored = 0x00
            for b in atr:
                xored ^= b
            if xored != 0x00:
                raise ProtocolError('ATR checksum error')
        # Verify that there is no more bytes
        if not self.iso7816.empty:
            raise ProtocolError('Unexpected bytes after ATR')
        self.atr = bytes(atr)
        return atr

    def apdu(self, the_apdu, trigger=''):
        """
        Send an APDU to the smartcard and retrieve the response.

        :param the_apdu: APDU to be sent. str hexadecimal strings are allowed,
            but user should consider using the :meth:`apdu_str` method instead.
        :type the_apdu: bytes or str
        :param trigger: If 'a' is in this string, trigger is raised after
            ISO-7816 header is sent, and cleared when the following response
            byte arrives. If 'b' is in this string, trigger is raised after
            data field has been transmitted, and cleared when the next
            response byte is received.
        :type trigger: str
        :raises ValueError: if APDU data is invalid.
        :return bytes: Response data, with status word.
        """
        if type(the_apdu) == str:
            the_apdu = bytes.fromhex(the_apdu)
        apdu_len = len(the_apdu)
        if apdu_len < 5:
            raise ValueError('APDU too short')
        out_data_len = apdu_len - 5
        if out_data_len > 256:
            raise ValueError('APDU too long')
        if out_data_len > 0:
            # This is an outgoing data transfer
            # Verify APDU P3 field correctness
            p3 = the_apdu[4]
            expected_p3 = out_data_len % 256
            if p3 != expected_p3:
                raise ValueError('Expected P3 (length) in APDU is '
                    f'0x{expected_p3:02x}, got 0x{p3:02x}')
            in_data_len = 0
        else:
            if the_apdu[4] > 0:
                in_data_len = the_apdu[4]
            else:
                in_data_len = 256
        # Transmit the header
        if 'a' in trigger:
            self.iso7816.transmit(the_apdu[:4])
            self.iso7816.trigger_long = 1
            self.iso7816.transmit(the_apdu[4:5])
        else:
            # Send all the header at once
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

    def find_info(self):
        """
        Parse the smartcard ATR list database available at
        http://ludovic.rousseau.free.fr/softwares/pcsc-tools/smartcard_list.txt
        and try to match the current ATR to retrieve more info about the card.
        
        The database file cannot be embedded in the library because it uses GPL
        and not LGPL license. On debian systems, this file is provided in the
        pcsc-tools package.

        :return: A list of str, where each item is an information line about
            the card. Return None if the ATR did not match any entry in the
            database.
        """
        tab = []
        text_file = open('/usr/share/pcsc/smartcard_list.txt', 'r')
        # We don't want to keep end lines such as LR or CR LF
        lines = text_file.read().splitlines()
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
        # Try to match ATR
        for item in tab:
            pattern = item[0]
            atr = hexlify(self.atr).decode()
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

    def apdu_str(self, the_apdu):
        """
        Same as :meth:`apdu` function, with str argument and return type for
        convenience.

        :param the_apdu: APDU to be sent, as an hexadecimal string.
        :type the_apdu: str
        :return str: Response from the card, as a lowercase hexadecimal string
            without spaces.
        """
        return hexlify(self.apdu(bytes.fromhex(the_apdu))).decode()

    @property
    def card_inserted(self):
        """
        True if a card is inserted, False otherwise. Card insertion is detected
        with a mecanical switch connected to D3 of Scaffold.
        """
        return self.sig_sense.value == 1
