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
# Copyright 2023 Ledger SAS, written by Michael Mouchous
from api.scaffold.atecc import crc16, crc16b
from api.scaffold.atecc import ATECC, ATECCInterface, Scaffold


def test_crc16_with_various_inputs():
    assert crc16(b"") == 0x0000
    assert crc16(b"123456789") == 0xDDBC
    assert crc16(b"1234567890") == 0xA35E
    assert crc16(b"hello world") == 0x9C83
    assert crc16(b"test data") == 0xE50F


def test_crc16_with_edge_cases():
    assert crc16(b"") == 0x0000
    assert crc16(b"\x00") == 0x0000
    assert crc16(b"\xff") == 0x0202
    assert crc16(b"\x00\xff") == 0x0202
    assert crc16(b"\xff\x00") == 0x0F82
    assert crc16(b"\xff\xff") == 0x0D80


def test_crc16b_with_various_inputs():
    assert crc16b(b"") == b"\x00\x00"
    assert crc16b(b"123456789") == b"\xdd\xbc"
    assert crc16b(b"1234567890") == b"\xa3\x5e"
    assert crc16b(b"hello world") == b"\x9c\x83"
    assert crc16b(b"test data") == b"\xe5\x0f"


def test_crc16b_with_edge_cases():
    assert crc16b(b"") == b"\x00\x00"
    assert crc16b(b"\x00") == b"\x00\x00"
    assert crc16b(b"\xff") == b"\x02\x02"
    assert crc16b(b"\x00\xff") == b"\x02\x02"
    assert crc16b(b"\xff\x00") == b"\x0f\x82"
    assert crc16b(b"\xff\xff") == b"\x0d\x80"


def test_powerup_serial():
    scaffold = Scaffold()
    atecc = ATECC(scaffold, interface=ATECCInterface.I2C)
    atecc.power_cycle()
    atecc.read_serial()
    assert atecc.serial is not None


def test_powerup_read_config():
    scaffold = Scaffold()
    atecc = ATECC(scaffold, interface=ATECCInterface.I2C)
    atecc.power_cycle()
    atecc.read_config()
    assert atecc.serial is not None


def test_nonce():
    scaffold = Scaffold()
    atecc = ATECC(scaffold, interface=ATECCInterface.I2C)
    atecc.power_cycle()
    atecc.wake_up()
    atecc.read_serial()
    print("Nonce:", atecc.nonce().hex())
