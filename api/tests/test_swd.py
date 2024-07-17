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
# Copyright 2024 Ledger SAS

# from scaffold import Scaffold, Pull


# def test_dut_connection_ok():
#     scaffold = Scaffold("/dev/ttyUSB3")
#     swd = scaffold.swd
#     swd.swclk >> scaffold.d0
#     swd.swd_out >> scaffold.d1
#     swd.swd_in << scaffold.d1
#     scaffold.d0.pull = Pull.UP
#     scaffold.d1.pull = Pull.UP
#
#     status = swd.reset()
#     print(f"status after: {status}")


# def test_read():
#     scaffold = Scaffold("/dev/ttyUSB3")
#     swd = scaffold.swd
#     swd.swclk >> scaffold.d0
#     swd.swd_out >> scaffold.d1
#     swd.swd_in << scaffold.d1
#     scaffold.d0.pull = Pull.UP
#     scaffold.d1.pull = Pull.UP
#
#     (status, rdata) = swd.read(0, 0)
#     print(f"status after: {status}")
#     print(f"rdata: {hex(rdata)}")


# def test_write():
#     scaffold = Scaffold("/dev/ttyUSB3")
#     swd = scaffold.swd
#     swd.swclk >> scaffold.d0
#     swd.swd_out >> scaffold.d1
#     swd.swd_in << scaffold.d1
#     scaffold.d0.pull = Pull.UP
#     scaffold.d1.pull = Pull.UP
#
#     status = swd.write(0, 0, 0b11010)
#     print(f"status after: {status}")
