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
# Copyright 2025 Ledger SAS, written by Olivier Hériveaux


from scaffold import Scaffold, ISO14443Trigger
from scaffold.iso14443 import NFC

s = Scaffold()
nfc = NFC(s)
s.d5 << nfc.trigger
nfc.startup()
nfc.iso14443.trigger_mode = ISO14443Trigger.START
nfc.iso14443.timeout = 1
nfc.verbose = True

# REQA
atqa = nfc.reqa()
uid_size = ((atqa[0] >> 6) & 3) + 1
# Selection
for i in range(uid_size):
    nfc.sel(i + 1)
# Send Request Answer To Select
result = nfc.rats()
# Send APDU
response = nfc.apdu(bytes.fromhex("00a404000e315041592e5359532e4444463031"))
