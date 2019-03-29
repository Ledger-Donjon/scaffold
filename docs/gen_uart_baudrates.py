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
#
#
# Generate baudrate table to be included into the documentation. The output is
# the uart_baudrates.inc file in ReST format.

system_frequency = 100e6
baudrates = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 1000000,
    2000000]
table = [('Baudrate', 'Divisor', 'Effective baudrate', 'Error')]

for baudrate in baudrates:
    divisor = int(system_frequency / baudrate) - 1
    real_baudrate = system_frequency / (divisor + 1)
    error = abs(real_baudrate - baudrate) / baudrate
    print(error)
    table.append((
        str(baudrate),
        str(divisor),
        '{0:.3f}'.format(real_baudrate),
        '{0:.3f} %'.format(error * 100) ))

# Get the size of the table
row_count = len(table)
col_count = len(table[0])

# Calculate columns width
col_sizes = []
for i in range(col_count):
    size = 0
    for j in range(row_count):
        size = max(size, len(table[j][i]))
    col_sizes.append(size)

def gen_bar(sizes, c = '-'):
    result = '+'
    for size in sizes:
        result += c * (size + 2) + '+'
    return result

def gen_row(row, sizes):
    result = '|'
    for i, size in enumerate(sizes):
        result += ' ' + row[i].rjust(size) + ' |'
    return result

rest = gen_bar(col_sizes) + '\n'

for i in range(row_count):
    rest += gen_row(table[i], col_sizes) + '\n'
    if i == 0:
        bar = gen_bar(col_sizes, '=')
    else:
        bar = gen_bar(col_sizes, '-')
    rest += bar + '\n'

open('uart_baudrates.inc', 'w').write(rest)
