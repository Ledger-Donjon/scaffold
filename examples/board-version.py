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
import serial.tools.list_ports


scaffold = Scaffold()
print("Scaffold arch version:", scaffold.version)

dev = scaffold.bus.ser.port
sn = next(
    (p.serial_number for p in serial.tools.list_ports.comports() if p.device == dev),
    None,
)
print("Serial number:", sn)
