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
from scaffold.iso7816 import Smartcard
from binascii import hexlify
import sys


scaffold = Scaffold('/dev/ttyUSB0')
sc = Smartcard(scaffold)

if not sc.card_inserted:
    print('No card inserted')
    sys.exit(1)

scaffold.power.dut = 1
atr = sc.reset()
print('ATR: ' + hexlify(atr).decode())
info = sc.find_info()
if info:
    print('Card found in ATR list:')
    for line in info:
        print('  ' + line)
else:
    print('No info found on this card.')
