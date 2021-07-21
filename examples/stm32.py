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


from scaffold import Scaffold, TimeoutError
from scaffold.stm32 import STM32, NACKError
from binascii import hexlify
import sys
import argparse


# Arguments parsing
parser = argparse.ArgumentParser(
    description='This script uses Scaffold to communicate with STM32 devices. '
    'It allows loading and executing code.')
default_com = {'win32': 'COM0'}.get(sys.platform, '/dev/ttyUSB0')
parser.add_argument(
    '-d', '--dev', help='Scaffold serial device path. '
    f'If not specified, {default_com} is used on Linux by default.',
    default=default_com)
parser.add_argument('-l', '--load', help='Load binary into device.')
parser.add_argument('--ram', help='Load binary into RAM memory.')
parser.add_argument(
    '-r', '--run', help='Reset and run device from Flash memory.',
    action='store_true')
parser.add_argument('-j', '--jump', help='Jump to RAM memory.')
parser.add_argument('--erase', help='Erase Flash memory.', action='store_true')
args = parser.parse_args()

# Connect to Scaffold board
scaffold = Scaffold(args.dev)
stm = STM32(scaffold)

# Try to connect to ST bootloader by sending 0x7f byte on USART and expecting a
# response from the device bootloader. This may fail if the device is locked in
# RDP2 state.
try:
    stm.startup_bootloader()
except TimeoutError:
    print('Failed to communicate with bootloader!')
    sys.exit()
print('Communication initiated')

pid = stm.get_id()
print(f'Product ID: 0x{pid:04x}')
if stm.device is not None:
    print(f'Possible device match: {stm.device.name}')

get = stm.get()
print(f'Get: {hexlify(get).decode()}')

# Print bootloader version and protection status details
data = stm.get_version_and_read_protection_status()
version = f'{data[0]:02x}'
print(f'Bootloader version: {version[0]}.{version[1]}')

if stm.device is not None:
    try:
        data = stm.read_option_bytes()
        print(f'Option bytes: {hexlify(data).decode()}')
        rdp = data[stm.device.offset_rdp]
        if rdp == 0xaa:
            rdp_str = 'no protection'
        elif rdp == 0xcc:
            # If the chip is really protected, we should not be able to know it
            # by reading the option bytes... So this may be useless.
            rdp_str = 'chip protection'
        else:
            rdp_str = 'read protection'
        print(f'RDP: {rdp_str}')
    except NACKError:
        print('Failed to read protection bytes, device probably in RDP1.')

if args.erase or ((args.load is not None) and (args.ram is None)):
    # Erase Flash memory before writing it. This may be very long.
    print('Erasing Flash memory...')
    stm.extended_erase()

# Load binary file into Flash memory
if (args.load is not None) and (args.ram is None):
    data = bytearray(open(args.load, 'rb').read())
    # Pad the data (multiple of 4 bytes is required)
    while len(data) % 4:
        data.append(0xff)
    print('Programming...')
    stm.write_memory(0x08000000, data)
    print('Verifying...')
    assert data == stm.read_memory(0x08000000, len(data))
    print('Flash memory written successfully!')

if (args.load is not None) and (args.ram is not None):
    ram_addr = int(args.ram, 0)
    data = bytearray(open(args.load, 'rb').read())
    # Pad the data (multiple of 4 bytes is required)
    while len(data) % 4:
        data.append(0xff)
    print('Loading code in RAM...')
    stm.write_memory(ram_addr, data)

if args.run:
    print('Rebooting from Flash memory...')
    stm.startup_flash()

if args.jump is not None:
    ram_addr = int(args.jump, 0)
    print(f'Jumping to 0x{ram_addr:08x}...')
    stm.go(ram_addr)
