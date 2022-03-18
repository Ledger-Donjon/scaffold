#!/usr/bin/python3
#
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


from scaffold import Scaffold
from scaffold.iso7816 import Smartcard, T1RedundancyCode, ProtocolError
import sys


scaffold = Scaffold()
sc = Smartcard(scaffold)

if not sc.card_inserted:
    print('No card inserted')
    sys.exit(1)

scaffold.power.dut = 1
atr = sc.reset()
print('ATR: ' + atr.hex())
print('Protocols: ' + ', '.join(f"T={x}" for x in sc.protocols))
if 1 in sc.protocols:
    edc_dict = {
        T1RedundancyCode.LRC: 'LRC (1 byte)',
        T1RedundancyCode.CRC: 'CRC (2 bytes)'}
    print('T1 redundancy code:', edc_dict[sc.t1_redundancy_code])
info = sc.find_info(allow_web_download=True)
if info:
    print('Card found in ATR list:')
    for line in info:
        print('  ' + line)
else:
    print('No info found on this card.')

while True:
    try:
        apdu = bytes.fromhex(input('apdu$ '))
    except ValueError:
        print('Invalid input')
        continue
    try:
        response = sc.apdu(apdu, trigger='a')
        print(response.hex())
    except ProtocolError as e:
        print(e)
    except ValueError as e:
        print(e)
