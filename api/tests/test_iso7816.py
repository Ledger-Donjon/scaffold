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
# Copyright 2021 Ledger SAS, written by Olivier Hériveaux


from scaffold import Pull
import pytest
from scaffold import Scaffold
from scaffold.iso7816 import load_atr_info_db, BasicByteReader, parse_atr, \
    ProtocolError


def test_parsing_ok():
    tab = load_atr_info_db()

    # Some cards do not respect the norm correctly and have malformated ATR
    # Here are some list of invalid ATR in the database.

    # List with incomplete ATR
    badlist_incomplete = [
        "3b260011016d03",
        "3b2f008069af0307066800000a0e8306",
        "3b6b00ff56434152445f4e5353",
        "3b9e96801fc78031e073fe211b66d00177970d00",
        "3b9f95801fc78031e073fe2113574a33052e323400",
        "3bba94004014",
        "3bbf96008131fe5d00640411030131c07301d000900000",
        "3bbf96008131fe5d00640411030131c073f701d0009000",
        "3bee00008131804380318066b1a11101a0f683009000",
        "3bef00ff813166456563202049424d20332e3120202020",
        "3bfa1300008131fe454a434f50343156",
        "3bfd9600008131204380318065b0831148c883009000",
        "3fff9500ff918171a04700444e4153503031312052657642",
        "3fff9500ff918171fe4700444e41535032343120447368"]

    # List of invalid ATR with too much bytes
    badlist_extra = [
        "3b02145011",
        "3b101450",
        "3b16964173747269643b021450",
        "3b230000364181",
        "3b6500002063cb680026",
        "3b66000090d1020110b13b021450",
        "3b6700ffc50000ffffffff5d",
        "3b781800000073c840000000009000",
        "3b84800101112003369000",
        "3b961880018051006110309f006110309e",
        "3b9f11406049524445544f204143532056352e3800",
        "3b9f96801fc78031e073fe211b6407595100829000ce00000000000000000000",
        "3bba96008131865d00640560020331809000667001040530c9",
        "3bec00004032424c554520445241474f4e20430001",
        "3bf711000140965430040e6cb6d69000",
        "3bf711000140967070070e6cb6d69000",
        "3bf7110001409670700a0e6cb6d69000",
        "3bfe9600008131fe45803180664090a5102e03830190006e9000"]

    # List of ATR with invalid checksum
    badlist_checksum = [
        "3b888001000000007783950000",
        "3b9e95801fc78031e073fe211b66d0004900c0004a",
        "3bdd97ff81b1fe451f0300640405080373969621d00090c8",
        "3bef00ff8131504565630000000000000000000000000000",
        "3bfe9100ff918171fe40004138002180818066b00701017707b7",
        "3bff0000ff8131fe458025a000000056575343363530000000"]

    atrs = []
    for atr_pattern, _ in tab:
        if ('.' not in atr_pattern) and ('[' not in atr_pattern):
            atrs.append(atr_pattern)
    for atr in atrs:
        reader = BasicByteReader(bytes.fromhex(atr))
        if atr in badlist_extra:
            parse_atr(reader)
            assert len(reader.data) > 0
        elif atr in badlist_incomplete:
            with pytest.raises(EOFError):
                parse_atr(reader)
        elif atr in badlist_checksum:
            with pytest.raises(ProtocolError):
                parse_atr(reader)
        else:
            parse_atr(reader)
