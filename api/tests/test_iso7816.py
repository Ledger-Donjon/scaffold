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


import pytest
import types

try:
    from scaffold.iso7816 import (
        load_atr_info_db,
        BasicByteReader,
        parse_atr,
        ProtocolError,
        Smartcard,
        T1RedundancyCode,
    )
except ImportError:
    from api.scaffold.iso7816 import (
        load_atr_info_db,
        BasicByteReader,
        parse_atr,
        ProtocolError,
        Smartcard,
        T1RedundancyCode,
    )


def test_parsing_ok():
    tab = load_atr_info_db(allow_web_download=True)

    # Some cards do not respect the norm correctly and have malformated ATR
    # Here are some list of invalid ATR in the database.

    # List with incomplete ATR
    badlist_incomplete = [
        "3b046089",
        "3b260011016d03",
        "3b2f008069af0307066800000a0e8306",
        "3b4f00536c653434322d34343da2131091",
        "3b6b00ff56434152445f4e5353",
        "3b6d0000",
        "3b6e00000031c071d66438d003008490",
        "3b6e00008066b1a30401110b83009000",
        "3b7f96000080318065b0850300ef120fff82",
        "3b8d0180fba000000397425446590401",
        "3b8f8001804f0ca0001a0000000078",
        "3b9596c0f01fc20f100a0a16",
        "3b9e95801fc78031e073fe211b66d00219151300",
        "3b9e96801fc78031e073fe211b66d00177970d00",
        "3b9f95801fc78031e073fe2113574a33052e323400",
        "3bba14008131865d0064057b020331809000",
        "3bba14008131865d0064057b0203319000ff",
        "3bba94004014",
        "3bbf96008131fe5d00640411000031c073f701d0009000",
        "3bbf96008131fe5d00640411030131c07301d000900000",
        "3bbf96008131fe5d00640411030131c073f701d0009000",
        "3bed000080318065b0840100c883009000",
        "3bed00008131fe450031c071c6644d35354d0f9000",
        "3bee00008131804380318066b1a11101a0f683009000",
        "3bee00008131804380318066b1a1110100f683009000",
        "3bef00ff813166456563202049424d20332e3120202020",
        "3bf57100fffe2400011e0f3339320103",
        "3bf81300008131fe454a4f5076323431b7",
        "3bfa1300008131fe454a434f50343156",
        "3bfb1300ffc0807553544f4c4c4d31504c5553bd",
        "3bfd9600008131204380318065b0831148c883009000",
        "3bfd9600008131484280318065b0840100c883009000",
        "3fff9500ff918171a04700444e4153503031312052657642",
        "3fff9500ff918171fe4700444e41535032343120447368",
        "3b6f00008031e06b082e0502b9555555",
        "3b781400000073c8400000",
        "3b9f978131fe458065544312210831c073f621808105",
        "3b6b00000031c164086032060f90",
        "3b6f00000031c173c8211064414d3347",
        "3b7f960080318065b084413df612004c829000",
        "3b8c8001502752318100000000007181",
        "3b8f80018031806549544a3442120fff829000",
        "3b9f95801fc78031a073b6a10067cf15ca9cd70920",
        "3b9f96801fc78031e073fe2113574a338101330017",
        "3bb89700813fe45ffff148230502300f",
        "3bd81800801f078031c1640806920f",
        "3bf01100ff01",
        "3bf99600008031fe455343453720474e335e",
        "3bfa1300008131fe454a434f50323156323331",
        "3bfa1300008131fe54a434f503233191",
        "3b6500002063cbbc",
    ]

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
        "3bfe9600008131fe45803180664090a5102e03830190006e9000",
    ]

    # List of ATR with invalid checksum
    badlist_checksum = [
        "3b86800106757781028f00",
        "3b888001000000007783950000",
        "3b888efe532a031e049280004132360111e4",
        "3b9711801f418031a073be2100a6",
        "3b9e95801fc78031e073fe211b66d0004900c0004a",
        "3b9f210e49524445544f204143532056312e32a0",
        "3b9f96801fc78031a073be2113674320071800000100",
        "3b9f96801fc78031a073be2113674320071800000100",
        "3b9f978131fe458065544312210831c073f62180810590",
        "3bdd97ff81b1fe451f0300640405080373969621d00090c8",
        "3bdf18008131fe58ac31b05202046405c903ac73b7b1d422",
        "3bdf18ff81f1fe43003f03834d4946506c75732053414d3b53414d3b",
        "3be6000080318066b1a30401110b83009000",
        "3bef00ff8131504565630000000000000000000000000000",
        "3bf99100ff918171fc40000a095161900058c290d2",
        "3bfe9100ff918171fe40004138002180818066b00701017707b7",
        "3bff0000ff8131fe458025a000000056575343363530000000",
        "3bff9500008031fe4380318067b0850201f3a3138301f83bff",
        "3be6000080318066b1a30401110b83",
        "3b801fc78031e073fe211163407163830790009a",
        "3b8580012063c8b880b4",
        "3b96004121920000622433339000",
        "3bde98ff8191fe1fc38031815448534d3173802140810792",
        "3bdf960090103f07008031e0677377696363000073fe2100dc",
        "3bfa00008131fe450031c173c840000090007a",
        "3bff1300918131fe4141434f532046696f6e6131204c6336f4",
    ]

    atrs = []
    for atr_pattern, _ in tab:
        if ("." not in atr_pattern) and ("[" not in atr_pattern):
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


def test_t1_lrc():
    dummy = types.SimpleNamespace()
    dummy.t1_redundancy_code = T1RedundancyCode.LRC
    vectors = [
        ("", 0x00),
        ("de0945b4298047029dd07a2b74975a86", 0xE9),
        ("7c5031c4ae356ce2cada16c6533eb9d9", 0x01),
        ("89973440f0af5e0e892137a3c15933de", 0x2C),
        ("181079e03db2992b423b61941a06a91c", 0x89),
    ]
    for data, lrc in vectors:
        expected = bytes([lrc])
        assert Smartcard.calculate_edc(dummy, bytes.fromhex(data)) == expected


def test_t1_crc():
    dummy = types.SimpleNamespace()
    dummy.t1_redundancy_code = T1RedundancyCode.CRC
    dummy.crc16 = None
    vectors = [
        ("dbc4fc2ad285292881f66af0f5c2a77d", "0aeb"),
        ("9da60b24b6b6b9b82c5edc5e53162063", "daf0"),
        ("5c24dea73cb5c4f4f0ca11d2a3ec9f89", "11cc"),
        ("c97124d4b54d8c427bfce6f3c6486518", "1f11"),
    ]
    for data, crc in vectors:
        expected = bytes.fromhex(crc)
        assert Smartcard.calculate_edc(dummy, bytes.fromhex(data)) == expected
