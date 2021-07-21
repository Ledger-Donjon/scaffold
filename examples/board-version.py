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
import sys
import argparse


# Arguments parsing
parser = argparse.ArgumentParser(
    description='Connects to a Scaffold board and prints FPGA architecture '
    'version.')
default_com = {'win32': 'COM0'}.get(sys.platform, '/dev/ttyUSB0')
parser.add_argument(
    '-d', '--dev', help='Scaffold serial device path. '
    f'If not specified, {default_com} is used.', default=default_com)
args = parser.parse_args()

# Connect to Scaffold board
scaffold = Scaffold(args.dev)
print('Scaffold arch version:', scaffold.version)
