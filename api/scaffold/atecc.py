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

from time import sleep
from enum import Enum
from binascii import hexlify
from ..scaffold import Pull, IOMode, Scaffold, I2CTrigger
from typing import Optional, Union, cast
import crcmod
from Crypto.Hash import SHA256


base_crc16 = crcmod.mkCrcFun(0x18005, 0, rev=True)


def crc16(data: bytes) -> int:
    x = base_crc16(data)
    rev = int(f"{x:016b}"[::-1], 2)
    result = ((rev & 0xFF) << 8) + (rev >> 8)
    return result


def crc16b(data: bytes) -> bytes:
    return int.to_bytes(crc16(data), 2, "big")


def swi_bits(byte: int) -> bytearray:
    result = bytearray()
    for i in range(8):
        result.append(0b11111101 + (((byte >> i) & 1) << 1))
    return result


class CRCError(Exception):
    def __init__(self, data, expected, received):
        self.data = data
        self.expected = expected
        self.received = received

    def __str__(self):
        return "CRCError"


class ProtocolError(Exception):
    def __init__(self, msg):
        super().__init__(msg)


class ATECCInterface(Enum):
    SWI = 1
    I2C = 2


class ATECCRevision(Enum):
    ATECC508A = 0x5000
    ATECC608A = 0x6002
    ATECC608B = 0x6003

    @property
    def is_ATECC608(self) -> bool:
        return self in [ATECCRevision.ATECC608A, ATECCRevision.ATECC608B]

    @property
    def is_ATECC508(self) -> bool:
        return self in [ATECCRevision.ATECC508A]


class ATECCErrorCode(int, Enum):
    SUCCESS = 0x00
    CHECKMAC_OR_VERIFY_MISCOMPARE = 0x01
    PARSE_ERROR = 0x03
    ECC_FAULT = 0x05
    SELF_TEST_ERROR = 0x07  # ATECC608A-TNGTLS
    HEALTH_TEST_ERROR = 0x08  # ATECC608A-TNGTLS
    EXECUTION_ERROR = 0x0F
    AFTER_WAKE = 0x11
    WATCHDOG_ABOUT_TO_EXPIRE = 0xEE  # ATECC608A-TNGTLS
    CRC_OR_OTHER_COMMUNICATION_ERROR = 0xFF  # ATECC608A-TNGTLS


class ATECCError(Exception):
    def __init__(self, code):
        super().__init__()
        self.code = code

    def __str__(self):
        try:
            return ATECCErrorCode(self.code).name
        except ValueError:
            return f"Unknown ATECC error 0x{self.code:02x}"


class ATECCOpCode(Enum):
    """ATECC508 command OpCodes"""

    CHECK_MAC = 0x28
    COUNTER = 0x24
    DERIVE_KEY = 0x1C
    ECDH = 0x43
    GEN_DIG = 0x15
    GEN_KEY = 0x40
    HMAC = 0x11
    INFO = 0x30
    LOCK = 0x17
    MAC = 0x08
    NONCE = 0x16
    PAUSE = 0x01
    PRIV_WRITE = 0x46
    RANDOM = 0x1B
    READ = 0x02
    SIGN = 0x41
    SHA = 0x47
    UPDATE_EXTRA = 0x20
    VERIFY = 0x45
    WRITE = 0x12
    AES = 0x51  # ATECC608A


class ATECCWordAddress(Enum):
    """Possible word-address for ATECC508 I2C writes."""

    RESET = 0x00
    SLEEP = 0x01
    IDLE = 0x02
    COMMAND = 0x03


class ATECCZone(Enum):
    """
    ATECC memory zones.

    Encoded values correspond to what must be transmitted in the READ commands.
    """

    CONFIG = 0
    OTP = 1
    DATA = 2


class SlotConfig:
    """ATECC data slot configuration."""

    def __init__(self):
        self.from_bytes(b"\x00\x00")

    def from_bytes(self, buf: bytes, offset=0) -> int:
        """
        Deserializes data from an input buffer.

        :param data: Input buffer.
        :type data: bytes
        :param offset: Offset of the data in the buffer.
        :type offset: int
        :return: Offset after the read data.
        :rtype: int
        """
        self.raw = buf[offset : offset + 2]
        x = int.from_bytes(self.raw, "little")
        self.write_config = (x >> 12) & 0x0F
        self.write_key = (x >> 8) & 0x0F
        self.is_secret = bool(x & (1 << 7))
        self.encrypt_read = bool(x & (1 << 6))
        self.limited_use = bool(x & (1 << 5))
        self.no_mac = bool(x & (1 << 4))
        self.read_key = x & 0x0F
        self.__check()
        return offset + 2

    def to_bytes(self) -> bytes:
        """
        :return: Data serialized to bytes.
        :rtype: bytes
        """
        self.__check()
        value = (
            (self.write_config << 12)
            + (self.write_key << 8)
            + (int(self.is_secret) << 7)
            + (int(self.encrypt_read) << 6)
            + (int(self.limited_use) << 5)
            + (int(self.no_mac) << 4)
            + self.read_key
        )
        return value.to_bytes(2, "little")

    def to_yaml(self) -> dict:
        """Generate dict object for yaml serialization"""
        self.__check()
        return {
            "write-config": self.write_config,
            "write-key": self.write_key,
            "is-secret": self.is_secret,
            "encrypt-read": self.encrypt_read,
            "limited-use": self.limited_use,
            "no-mac": self.no_mac,
            "read-key": self.read_key,
        }

    def from_yaml(self, data: dict):
        """Load attributes from yaml loaded dict"""
        self.write_config: int = data["write-config"]
        self.write_key: int = data["write-key"]
        self.is_secret: bool = data["is-secret"]
        self.encrypt_read: bool = data["encrypt-read"]
        self.limited_use: bool = data["limited-use"]
        self.no_mac: bool = data["no-mac"]
        self.read_key: int = data["read-key"]
        self.__check()

    def __check(self):
        """Check attributes types and values"""
        assert self.write_config in range(16)  # 4 bits
        assert self.write_key in range(16)  # 4 bits
        assert type(self.is_secret) is bool
        assert type(self.encrypt_read) is bool
        assert type(self.limited_use) is bool
        assert type(self.no_mac) is bool
        assert self.read_key in range(16)  # 4 bits


class ATECCInfoMode(Enum):
    REVISION = 0
    KEYVALID = 1
    STATE = 2
    GPIO = 3
    VOLATILE_KEY_PERMIT = 4


class Info:
    def __init__(self, mode, data: bytes, param):
        self.mode = mode
        self.revision: Optional[ATECCRevision] = None
        self.raw = data
        self.param = param
        if data is not None:
            self.from_bytes(data)

    def from_bytes(self, data: bytes, offset: int = 0):
        """
        Deserialize data from an input buffer.

        :param data: Input buffer.
        :param offset: Offset of the data in the buffer.
        :return: Offset after the read data.
        """
        self.raw = data
        buf = bytes(data[offset : offset + 4])
        if self.mode == ATECCInfoMode.REVISION:
            self.revision = ATECCRevision(int.from_bytes(buf, "big"))
        if self.mode == ATECCInfoMode.STATE:
            self.tempkey_id = buf[0] & 0xF
            self.tempkey_sourceflag = bool((buf[0] >> 4) & 0x1)
            self.tempkey_gendigdata = bool((buf[0] >> 5) & 0x1)
            self.tempkey_genkeydata = bool((buf[0] >> 6) & 0x1)
            self.tempkey_nomacflag = bool((buf[0] >> 7) & 0x1)

            self.authvalid = bool((buf[1] >> 2) & 0x1)
            self.authkey = (buf[1] >> 3) & 0b1111
            self.tempkey_valid = bool((buf[1] >> 7) & 0x1)

    def __str__(self) -> str:
        ret = f"Info mode: {self.mode} : {self.raw.hex()}\n"
        if self.mode == ATECCInfoMode.REVISION:
            ret += f" revision: {self.revision}"
        elif self.mode == ATECCInfoMode.KEYVALID:
            zeros = b"\0" * 4
            ret += f" Key {self.param} is valid? {self.raw != zeros}"
        elif self.mode == ATECCInfoMode.STATE:
            ret += f" tempkey_id: {self.tempkey_id}\n"
            ret += f" tempkey_sourceflag: {self.tempkey_sourceflag}\n"
            ret += f" tempkey_gendigdata: {self.tempkey_gendigdata}\n"
            ret += f" tempkey_genkeydata: {self.tempkey_genkeydata}\n"
            ret += f" tempkey_nomacflag: {self.tempkey_nomacflag}\n"
            ret += f" authvalid: {self.authvalid}\n"
            ret += f" authkey: {self.authkey}\n"
            ret += f" tempkey_valid: {self.tempkey_valid}"
        return ret


class KeyConfig:
    """ATECC key configuration"""

    def __init__(self, from_bytes: bytes = b"\x00\x00"):
        self.from_bytes(from_bytes)

    def from_bytes(self, buf: bytes, offset: int = 0) -> int:
        """
        Deserialize data from an input buffer.

        :param data: Input buffer.
        :param offset: Offset of the data in the buffer.
        :return: Offset after the read data.
        """
        self.raw = buf[offset : offset + 2]
        x = int.from_bytes(self.raw, "little")
        self.x509_id = x >> 14
        assert ((x >> 13) & 1) == 0  # RFU bit
        self.intrusion_disable = bool(x & (1 << 12))
        self.auth_key = (x >> 8) & 0x0F
        self.req_auth = bool(x & (1 << 7))
        self.req_random = bool(x & (1 << 6))
        self.lockable = bool(x & (1 << 5))
        self.key_type = (x >> 2) & 0b111
        self.pub_info = bool(x & (1 << 1))
        self.private = bool(x & 1)
        self.__check()
        return offset + 2

    def to_bytes(self) -> bytes:
        """
        :return: Data serialized to bytes.
        :rtype: bytes
        """
        self.__check()
        value: int = (
            (self.x509_id << 14)
            + (int(self.intrusion_disable) << 12)
            + (self.auth_key << 8)
            + (int(self.req_auth) << 7)
            + (int(self.req_random) << 6)
            + (int(self.lockable) << 5)
            + (self.key_type << 2)
            + (int(self.pub_info) << 1)
            + int(self.private)
        )
        return value.to_bytes(2, "little")

    def from_yaml(self, data: dict):
        """Load attributes from yaml loaded dict"""
        self.x509_id: int = data["x509-id"]
        self.intrusion_disable: bool = data["intrusion-disable"]
        self.auth_key: int = data["auth-key"]
        self.req_auth: bool = data["req-auth"]
        self.req_random: bool = data["req-random"]
        self.lockable: bool = data["lockable"]
        self.key_type: int = data["key-type"]
        self.pub_info: bool = data["pub-info"]
        self.private: bool = data["private"]
        self.__check()

    def to_yaml(self) -> dict:
        """Generate dict object for yaml serialization"""
        self.__check()
        return {
            "x509-id": self.x509_id,
            "intrusion-disable": self.intrusion_disable,
            "auth-key": self.auth_key,
            "req-auth": self.req_auth,
            "req-random": self.req_random,
            "lockable": self.lockable,
            "key-type": self.key_type,
            "pub-info": self.pub_info,
            "private": self.private,
        }

    def __check(self):
        """Check attributes types and values"""
        assert self.x509_id in range(4)  # 2 bits
        assert type(self.intrusion_disable) is bool
        assert self.auth_key in range(16)  # 4 bits
        assert type(self.req_auth) is bool
        assert type(self.req_random) is bool
        assert type(self.lockable) is bool
        assert self.key_type in range(8)  # 3 bits
        assert type(self.pub_info) is bool
        assert type(self.private) is bool


class Config:
    """
    Image of the configuration of the device (EEPROM configuration memory)
    """

    def __init__(self, from_bytes=None):
        self.serial = bytes()
        self.revision = bytes()
        self.atecc_revision = ATECCRevision.ATECC508A
        self.internal_13 = 0
        self.aes_enable = False
        self.internal_14 = 0
        self.i2c_enable = False
        self.internal_15 = 0
        self.i2c_address = 0
        self.internal_17 = False
        self.otp_mode = 0
        self.count_match_enable = False
        self.count_match_key = 0
        self.clock_divider = 0
        self.watchdog_duration = 0
        self.ttl_enable = False
        self.selector_mode = 0
        self.slot_config = list(SlotConfig() for _ in range(16))
        self.counters: tuple[bytes, bytes] = (b"", b"")
        self.last_key_use = bytes()
        self.user_extra = False
        self.selector = 0
        self.lock_value = 0
        self.lock_config = 0
        self.slot_locked = list(False for _ in range(16))
        self.chip_options = bytes()
        self.x509_format = bytes()
        self.key_config = list(KeyConfig() for _ in range(16))
        self.raw = bytes()
        if from_bytes is not None:
            self.from_bytes(from_bytes)

    def from_bytes(self, buf: bytes, offset: int = 0) -> int:
        """
        Deserialize data from an input buffer.

        :param buf: Input buffer.
        :param offset: Offset of the data in the buffer.
        :return: Offset after the read data.
        """
        buf = bytes(buf[offset : offset + 4 * 32])
        self.raw = buf
        self.serial = bytes(buf[0:4] + buf[8:13])
        self.revision = buf[4:8]
        revision = int.from_bytes(buf[4:8], "big")
        # For all versions of ATECC508A, 3rd byte will always be 0x50
        # For all versions of ATECC608A/B, 3rd byte will always be 0x60
        # For ATECC608A devices, 4th byte will be 0x02
        # For ATECC608B devices, 4th byte will be 0x03
        self.atecc_revision = ATECCRevision(revision)
        # Byte 13 'reserved' for ATECC508A, but AES enable for ATECC608A
        x = buf[13]
        if self.atecc_revision.is_ATECC608:
            self.internal_13 = x & 0xFE
            self.aes_enable = bool(x & 1)
        else:
            self.internal_13 = x
        # I2C enable
        x = buf[14]
        self.internal_14 = x & 0xFE
        self.i2c_enable = bool(x & 1)
        self.internal_15 = buf[15]
        self.i2c_address = buf[16]
        self.internal_17 = buf[17]
        assert self.internal_17 == 0
        # OTP mode (508A) or CountMatch (608A/B)
        x = buf[18]
        if self.atecc_revision.is_ATECC508:
            self.otp_mode = x
        elif self.atecc_revision.is_ATECC608:
            # CountMatch for ATECC608A
            self.count_match_enable = bool(x & 1)
            assert (x & 0b1110) == 0
            self.count_match_key = (x >> 4) & 0b1111
        # Chip mode
        x = buf[19]
        if self.atecc_revision.is_ATECC508:
            assert (x & 0b11111000) == 0
            self.selector_mode = x & 1
        elif self.atecc_revision.is_ATECC608:
            self.i2c_address_user_extra = bool(x & 1)
            self.clock_divider = (x >> 3) & 0b11111
        self.ttl_enable = bool((x >> 1) & 1)
        self.watchdog_duration = [1.3, 10][(x >> 2) & 1]
        # Slot config
        for i in range(16):
            self.slot_config[i].from_bytes(buf, 20 + i * 2)
        self.counters = (buf[52:60], buf[60:68])
        if self.atecc_revision.is_ATECC508:
            self.last_key_use = buf[68:84]
        elif self.atecc_revision.is_ATECC608:
            x = buf[68]
            self.use_lock_enable = (x & 0b1111) == 0x0A
            self.use_lock_key = (x >> 4) & 0b1111
            x = buf[69]
            self.volatile_key_permit_slot = x & 0b1111
            assert x & 0b1110000 == 0
            self.volatile_key_permit_enable = ((x >> 7) & 0b1) == 1
            self.secure_boot = buf[70:72]
            self.kdf_iv_loc = buf[72]
            self.kdf_iv_str = buf[73:75]
            assert buf[75:84] == bytes(84 - 75)
        self.user_extra = buf[84]
        self.selector = buf[85]
        # Lock value
        x = buf[86]
        # assert x in (0x55, 0x00)
        self.lock_value = x
        # Lock config
        x = buf[87]
        # assert x in (0x55, 0x00)
        self.lock_config = x
        # Slot locked
        x = int.from_bytes(buf[88:90], "little")
        for i in range(16):
            self.slot_locked[i] = (x & 1) == 0
            x >>= 1
        if self.atecc_revision.is_ATECC508:
            # For rev 508: Reserved, shall always be zero
            assert buf[90] == 0
            assert buf[91] == 0
        elif self.atecc_revision.is_ATECC608:
            self.chip_options = buf[90:92]
            # bits 3-7 must be zero
            assert (self.chip_options[0] & 0b11111000) == 0
        # X509 format
        self.x509_format = buf[92:96]
        # Key config
        for i in range(16):
            self.key_config[i].from_bytes(buf, 96 + i * 2)
        self.__check()
        return offset + 4 * 32

    def to_bytes(self):
        """
        :return: Data serialized to bytes.
        :rtype: bytes
        """
        self.__check()
        res = bytearray(self.serial[0:4] + self.revision + self.serial[4:9])
        if self.atecc_revision.is_ATECC608:
            res.append(int(self.aes_enable) + self.internal_13)
        else:
            res.append(self.internal_13)
        res.append(int(self.i2c_enable) + self.internal_14)
        res.append(self.internal_15)  # Reserved
        res.append(self.i2c_address)
        res.append(self.internal_17)  # Reserved
        if self.atecc_revision.is_ATECC508:
            res.append(self.otp_mode)
        elif self.atecc_revision.is_ATECC608:
            res.append(
                (1 if self.count_match_enable else 0) + (self.count_match_key << 4)
            )
        x = ((1 if self.ttl_enable else 0) << 1) + {1.3: 0, 10: 1 << 2}[
            self.watchdog_duration
        ]
        if self.atecc_revision.is_ATECC508:
            x += self.selector_mode
        elif self.atecc_revision.is_ATECC608:
            x += (1 if self.i2c_address_user_extra else 0) + (self.clock_divider << 3)
        res.append(x)
        for c in self.slot_config:
            res += c.to_bytes()
        res += self.counters[0]
        res += self.counters[1]
        if self.atecc_revision.is_ATECC508:
            res += self.last_key_use
        elif self.atecc_revision.is_ATECC608:
            res.append(0x0A if self.use_lock_enable else 0 + (self.use_lock_key << 4))
            res.append(
                self.volatile_key_permit_slot
                + ((1 if self.volatile_key_permit_enable else 0) << 7)
            )
            res += self.secure_boot
            res.append(self.kdf_iv_loc)
            res += self.kdf_iv_str
            res += bytes(9)
        res.append(self.user_extra)
        res.append(self.selector)
        res.append(self.lock_value)
        res.append(self.lock_config)
        x = 0
        for i in range(16):
            if not self.slot_locked[i]:
                x += 1 << i
        res += x.to_bytes(2, "big")
        if self.atecc_revision.is_ATECC508:
            res.append(0)
            res.append(0)
        elif self.atecc_revision.is_ATECC608:
            res += self.chip_options
        res += self.x509_format
        for c in self.key_config:
            res += c.to_bytes()
        return res

    def from_yaml(self, data: dict):
        """Load attributes from yaml loaded dict"""
        self.serial = bytes.fromhex(data["serial"])
        self.revision = bytes.fromhex(data["revision"])
        revision = int.from_bytes(self.revision[4:8], "big")
        self.atecc_revision = ATECCRevision(revision)
        if self.atecc_revision.is_ATECC608:
            raise RuntimeError(
                "Sorry, YAML import/export has not been updated for ATECC608"
            )
        self.internal_13 = data.get("internal-13", 0)
        self.aes_enable = data["aes-enable"]
        self.internal_14 = data.get("internal-14", 0)
        self.i2c_enable = data["i2c-enable"]
        self.i2c_address = data["i2c-address"]
        self.otp_mode = data["otp-mode"]
        self.watchdog_duration = data["watchdog-duration"]
        self.ttl_enable = data["ttl-enable"]
        self.selector_mode = data["selector-mode"]
        self.slot_config = []
        for i in range(16):
            c = SlotConfig()
            c.from_yaml(data["slot-config"][i])
            self.slot_config.append(c)
        _counters = data["counters"]
        assert len(_counters) == 2
        self.counters = tuple(_counters)
        self.last_key_use = bytes.fromhex(data["last-key-use"])
        self.user_extra = data["user-extra"]
        self.selector = data["selector"]
        self.lock_value = data["lock-value"]
        self.lock_config = data["lock-config"]
        self.slot_locked = data["slot-locked"]
        self.x509_format = bytes.fromhex(data["x509-format"])
        self.key_config = []
        for i in range(16):
            c = KeyConfig()
            c.from_yaml(data["key-config"][i])
            self.key_config.append(c)
        self.__check()

    def to_yaml(self) -> dict:
        if self.atecc_revision.is_ATECC608:
            raise RuntimeError(
                "Sorry, YAML import/export has not been updated for ATECC608"
            )
        """Generate dict object for yaml serialization"""
        self.__check()
        res = {
            "serial": self.serial.hex(),
            "revision": self.revision.hex(),
            "aes-enable": self.aes_enable,
            "i2c-enable": self.i2c_enable,
            "i2c-address": self.i2c_address,
            "otp-mode": self.otp_mode,
            "watchdog-duration": self.watchdog_duration,
            "ttl-enable": self.ttl_enable,
            "selector-mode": self.selector_mode,
            "slot-config": [c.to_yaml() for c in self.slot_config],
            "counters": [c.hex() for c in self.counters],
            "last-key-use": self.last_key_use.hex(),
            "user-extra": self.user_extra,
            "selector": self.selector,
            "lock-value": self.lock_value,
            "lock-config": self.lock_config,
            "slot-locked": self.slot_locked,
            "x509-format": self.x509_format.hex(),
            "key-config": [c.to_yaml() for c in self.key_config],
        }
        if self.internal_13 != 0:
            res["internal-13"] = self.internal_13
        if self.internal_14 != 0:
            res["internal-14"] = self.internal_14
        return res

    def __check(self):
        """Check attributes types and values"""
        assert type(self.serial) is bytes
        assert len(self.serial) == 9
        assert type(self.revision) is bytes
        assert len(self.revision) == 4
        if self.atecc_revision.is_ATECC608:
            assert type(self.aes_enable) is bool
        assert type(self.i2c_enable) is bool
        assert self.i2c_address in range(0, 0x100)
        if self.atecc_revision.is_ATECC508:
            assert self.otp_mode in (0xAA, 0x55)
        if self.atecc_revision.is_ATECC508:
            assert self.selector_mode in range(0, 2)
        elif self.atecc_revision.is_ATECC608:
            assert type(self.i2c_address_user_extra) is bool
        assert type(self.ttl_enable) is bool
        if self.atecc_revision.is_ATECC608:
            assert self.clock_divider in [0x00, 0x0D, 0x05]
        assert self.watchdog_duration in [1.3, 10]
        assert len(self.slot_config) == 16
        for c in self.slot_config:
            assert isinstance(c, SlotConfig)
        assert len(self.counters) == 2
        for c in self.counters:
            assert len(c) == 8
        if self.atecc_revision.is_ATECC508:
            assert len(self.last_key_use) == 16
        elif self.atecc_revision.is_ATECC608:
            assert self.secure_boot[0] & 0b11100100 == 0
        assert self.user_extra in range(0, 0x100)
        assert self.selector in range(0, 0x100)
        assert self.lock_value in (0, 0x55)
        assert self.lock_config in (0, 0x55)
        assert len(self.slot_locked) == 16
        for x in self.slot_locked:
            assert type(x) is bool
        assert type(self.x509_format) is bytes
        assert len(self.x509_format) == 4
        assert len(self.key_config) == 16
        for c in self.key_config:
            assert isinstance(c, KeyConfig)

    def print_config(self):
        def yes_no(x) -> str:
            return "yes" if x else "no"

        """ Print given configuration """
        if self.raw is not None:
            print("Raw:")
            for i in range(4):
                print("  " + hexlify(self.raw[i * 32 : (i + 1) * 32]).decode())

        print("Serial: 0x" + hexlify(self.serial).decode())
        print(
            "Revision: 0x" + hexlify(self.revision).decode(),
            f"({self.atecc_revision})",
        )
        if self.atecc_revision.is_ATECC608:
            print("AES enable: " + ["no", "yes"][int(self.aes_enable)])
        if self.internal_13 != 0:
            print(f"Internal 13: {self.internal_13}")
        print("I2C enable: " + ["no", "yes"][int(self.i2c_enable)])
        if self.internal_14 != 0:
            print(f"Internal 14: {self.internal_14}")
        print(f"I2C address: 0x{self.i2c_address:02x}")
        x = self.otp_mode
        s = {0xAA: "read-only", 0x55: "consumption"}.get(x, "unknown")
        if self.atecc_revision == ATECCRevision.ATECC508A:
            print(f"OTP mode: 0x{x:02x} ({s})")
        elif self.atecc_revision.is_ATECC608:
            print(f"CountMatch enabled: {self.count_match_enable}")
            print(f"CountMatch key: {self.count_match_key}")
        print(f"Watchdog duration: {self.watchdog_duration} s")
        print(
            "TTL enable: " + ["fixed reference", "vcc referenced"][int(self.ttl_enable)]
        )
        print(f"Selector mode: {self.selector_mode}")
        if self.atecc_revision.is_ATECC608:
            print(f"Clock divider: {self.clock_divider}")
        print("Slot config:")
        for i, sc in enumerate(self.slot_config):
            print(f"  Slot {i}:")
            print("    Raw: 0x" + hexlify(sc.raw).decode())
            x = sc.write_config
            print(f"    Write config: 0b{x:04b}")
            if x == 0:
                s = "always"
            elif x == 1:
                s = "pub invalid"
            elif (x & 0b1110) == 0b0010:
                s = "never"
            elif (x & 0b1100) == 0b1000:
                s = "never"
            elif (x & 0b0100) == 0b0100:
                s = "encrypt"
            else:
                s = "?"
            print(f"      write: {s}")
            print(f"    Write key: {sc.write_key}")
            print(f"    Read key: {sc.read_key}")
            print("    Is secret: " + ["no", "yes"][int(sc.is_secret)])
            print("    Encrypt read: " + ["no", "yes"][int(sc.encrypt_read)])
            print("    Limited use: " + ["no", "yes"][int(sc.limited_use)])
            print("    No MAC: " + ["no", "yes"][int(sc.no_mac)])
        print("Counters:")
        for i, c in enumerate(self.counters):
            print(f"  {i}: 0x" + hexlify(c).decode())
        if self.atecc_revision.is_ATECC508:
            print("Last key use: " + hexlify(self.last_key_use).decode())
        elif self.atecc_revision.is_ATECC608:
            print("Volatile Key Permit Enabled:", self.volatile_key_permit_enable)
            print("Volatile Key Permit Slot:", self.volatile_key_permit_slot)
            mode = self.secure_boot[0] & 0b11
            if mode == 0b00:
                print(f"Secure boot mode {mode:02b}: Disabled")
            elif mode == 0b01:
                print(f"Secure boot mode {mode:02b}: Full Secure boot (FullBoth)")
            elif mode == 0b10:
                print(f"Secure boot mode {mode:02b}: Stored Secure Boot (FullSig)")
            elif mode == 0b11:
                print(f"Secure boot mode {mode:02b}: Stored secure Boot (FullDig)")
            print("KDF IV location:", self.kdf_iv_loc)
            print(f"KDF IV string: 0x{self.kdf_iv_str.hex()}")
        print(f"User extra: 0x{self.user_extra:02x}")
        if self.atecc_revision.is_ATECC508:
            print(f"Selector: 0x{self.selector:02x}")
        elif self.atecc_revision.is_ATECC608:
            print(f"User extra i2c address: 0x{self.selector:02x}")
        x = self.lock_value
        s = {0x55: "unlocked", 0x00: "locked"}.get(x, "?")
        print(f"Lock value: 0x{x:02x} ({s})")
        x = self.lock_config
        s = {0x55: "unlocked", 0x00: "locked"}.get(x, "?")
        print(f"Lock config: 0x{x:02x} ({s})")
        print("Slot locked:")
        for i, sl in enumerate(self.slot_locked):
            print(f"  {i}: " + ["no", "yes"][int(sl)])
        if self.atecc_revision.is_ATECC608:
            co = self.chip_options
            print(f"Chip Options: 0x{co.hex()}")
            print(f"   Power on Self Test: {(co[0] & 0b1) != 0}")
            print(f"   IO Protection Key Enabled: {(co[0] & 0b10) != 0}")
            print(f"   KDF AES Enabled: {(co[0] & 0b100) != 0}")
            print(f"   ECDSH Protection bits: 0b{co[1] & 0b11:02b}")
            print(f"   KDF Protection bits: 0b{(co[1] >> 2) & 0b11:02b}")
            print(f"   IO Protection Key: {(co[1] >> 4) & 0b1111}")
        print(f"X509 format: 0x{self.x509_format.hex()}")
        print("Key config:")
        for i, kc in enumerate(self.key_config):
            print(f"  Key {i}:")
            if kc.raw is not None:
                print("    Raw: 0x" + hexlify(kc.raw).decode())
            print(f"    X509 ID: {kc.x509_id}")
            print("    Intrusion disable: " + yes_no(kc.intrusion_disable))
            print(f"    Auth key: {kc.auth_key}")
            print("    Req auth: " + yes_no(kc.req_auth))
            print("    Req random: " + yes_no(kc.req_random))
            print("    Lockable: " + yes_no(kc.lockable))
            if self.revision[2] > 0x05:
                d = {
                    4: "P256 NIST ECC key",
                    6: "AES key",
                    7: "SHA key or other data",
                }
            else:
                d = {4: "P256 NIST ECC key", 7: "Not an ECC key"}
            print("    Key type: " + d.get(kc.key_type, f"0x{kc.key_type}"))
            print("    Pub info: " + yes_no(kc.pub_info))
            print("    Private: " + yes_no(kc.private))


class ATECCIOFlag(Enum):
    COMMAND = 0x77
    TRANSMIT = 0x88
    IDLE = 0xBB
    SLEEP = 0xCC


class ATECC:
    """Factory default I2C address for ATECC508."""

    DEFAULT_ADDRESS = 0xC0
    SWI_TX_BAUDRATE = 1 / 4.34e-6

    def __init__(self, scaffold: Scaffold, interface=ATECCInterface.I2C):
        self.interface = interface
        self.scaffold = scaffold
        self.sda = scaffold.d0
        self.scl = scaffold.d1
        self.sda.pull = Pull.UP
        if interface == ATECCInterface.I2C:
            self.sda.mode = IOMode.AUTO
            self.i2c = scaffold.i2cs[0]
            # ATECC does not use clock stretchin.
            # Disabling it allows saving a pull-up resistor on SCL.
            self.i2c.clock_stretching = 0
            self.sda << self.i2c.sda_out
            self.scl << self.i2c.scl_out
            self.i2c.sda_in << self.sda
            self.i2c.scl_in << self.scl
            self.i2c.frequency = 500e3
            self.i2c.address = self.DEFAULT_ADDRESS
        elif interface == ATECCInterface.SWI:
            self.sda.mode = IOMode.OPEN_DRAIN
            self.uart = scaffold.uart0
            self.uart.baudrate = self.SWI_TX_BAUDRATE
            self.sda << self.uart.tx
            self.sda >> self.uart.rx
        self.serial = None  # Set when calling read_serial or read_config
        self.temp_key: Optional[bytes] = None  # Set when calling nonce

    @property
    def address(self):
        """I2C address of the device. Default is DEFAULT_ADDRESS."""
        if self.interface != ATECCInterface.I2C:
            raise RuntimeError("interface is not I2C")
        return self.i2c.address

    @address.setter
    def address(self, value):
        if self.interface != ATECCInterface.I2C:
            raise RuntimeError("interface is not I2C")
        self.i2c.address = value

    def power_cycle(self):
        self.scaffold.power.restart_dut(toff=0.05, ton=0.05)

    def wake_up(self):
        """
        Force a wake up by setting the SDA line to 0 and then to 1.
        """
        self.sda << 0
        sleep(2e-4)
        self.sda << 1
        sleep(2e-3)
        # Restore the SDA line
        if self.interface == ATECCInterface.I2C:
            self.sda << self.i2c.sda_out
        elif self.interface == ATECCInterface.SWI:
            self.sda << self.uart.tx

    def __swi_receive(self, n: int) -> bytes:
        """
        Receive n bytes using SWI.

        :param n: The number of bytes exepected to be received.
        :raises RuntimeError: Raises a transmission error when
            the received value is not 0xFF or 0xFB.
        :return: _description_
        """
        buf = self.uart.receive(n * 8)
        result = bytearray()
        for i in range(n):
            byte = 0
            for j in range(8):
                b = buf[i * 8 + j]
                if b == 0xFF:
                    byte += 1 << j
                elif b != 0xFB:
                    raise RuntimeError("Transmission error")
                result.append(byte)
        return bytes(result)

    def __read_output_group(self) -> bytes:
        response = b""
        if self.interface == ATECCInterface.I2C:
            response = bytes(self.i2c.read(1))
        elif self.interface == ATECCInterface.SWI:
            # We must drop first 8 bits
            self.uart.receive(8)
            response = self.__swi_receive(1)

        if response[0] < 4:
            raise ProtocolError(
                f"I/O group is too small ({response[0]} bytes)."
                " It should be at least 4 bytes."
            )
        if self.interface == ATECCInterface.I2C:
            response += bytes(self.i2c.read(response[0] - 1))
        elif self.interface == ATECCInterface.SWI:
            response += self.__swi_receive(response[0] - 1)
        # Check response checksum
        expected_crc = crc16b(response[:-2])
        received_crc = response[-2:]
        if crc16b(response[:-2]) != response[-2:]:
            raise CRCError(response, received_crc, expected_crc)
        # Return result without length and CRC
        return response[1:-2]

    def command(
        self,
        opcode: Union[int, ATECCOpCode],
        p1: int = 0,
        p2: int = 0,
        data: bytes = b"",
        trigger: Optional[Union[bool, int, I2CTrigger]] = None,
        wait: float = 0.0,
        skip_response: bool = False,
    ) -> Optional[bytes]:
        """
        Execute a command on the ATECC.

        :param opcode: Command code.
        :param p1: First command parameter. 8-bits.
        :param p2: Second command parameter. 16-bits.
        :param data: Command data.
        :param trigger: Enable or disable trigger signal for this command.
        :param wait: Wait time after sending the command.
        :param skip_response: If enabled, don't fetch the response,
            only send the command.
        :return: Command response.
        """
        if isinstance(opcode, ATECCOpCode):
            opcode = opcode.value
        buf = bytearray()
        if self.interface == ATECCInterface.I2C:
            buf.append(ATECCWordAddress.COMMAND.value)
        elif self.interface == ATECCInterface.SWI:
            buf.append(ATECCIOFlag.COMMAND.value)
        buf.append(7 + len(data))
        buf.append(opcode)
        buf.append(p1)
        buf += p2.to_bytes(2, "little")
        buf += data
        buf += crc16b(buf[1:])
        if self.interface == ATECCInterface.I2C:
            self.i2c.write(buf, trigger=trigger)
            if wait:
                sleep(wait)
            if skip_response:
                return
        elif self.interface == ATECCInterface.SWI:
            bits = bytearray()
            for b in buf:
                bits += swi_bits(b)
            self.uart.transmit(bits, trigger=trigger)
            # For SWI, we must send a TRANSMIT byte to ask the device to
            # respond. This can be done only after processing is done, otherwise
            # the TRANSMIT byte is ignored. Therefore, it is mandatory to wait.
            if wait:
                sleep(wait)
            else:
                # Default wait delay
                sleep(15e-3)
            if skip_response:
                return
            self.uart.flush()
            self.uart.transmit(swi_bits(ATECCIOFlag.TRANSMIT.value))
        g = self.__read_output_group()
        if len(g) == 1:
            # Just a status
            if g[0] != ATECCErrorCode.SUCCESS.value:
                # Command is not successfull
                raise ATECCError(g[0])
            return b""
        else:
            return g

    def reset(self):
        """Reset the address counter. Next I2C will start with the beginning of IO buffer."""
        if self.interface == ATECCInterface.I2C:
            self.i2c.write(bytes((ATECCWordAddress.RESET.value,)))
        elif self.interface == ATECCInterface.SWI:
            pass

    def idle(self):
        """Put the device into IDLE mode."""
        if self.interface == ATECCInterface.I2C:
            self.i2c.write(bytes((ATECCWordAddress.IDLE.value,)))
        elif self.interface == ATECCInterface.SWI:
            self.uart.transmit(swi_bits(ATECCIOFlag.IDLE.value))

    def info(
        self,
        mode: ATECCInfoMode = ATECCInfoMode.REVISION,
        param=0,
        trigger: Optional[Union[bool, int, I2CTrigger]] = None,
    ) -> Info:
        """
        Query info from device.

        :return: Device info bytes.
        """
        info = self.command(ATECCOpCode.INFO, mode.value, param, trigger=trigger)
        assert info is not None
        return Info(mode, info, param)

    def state(self, trigger: Optional[Union[bool, int, I2CTrigger]] = 0):
        return self.info(ATECCInfoMode.STATE, trigger=trigger)

    def read(
        self,
        zone=ATECCZone.DATA,
        size=32,
        block=0,
        slot=None,
        offset=0,
        trigger: Optional[Union[bool, int, I2CTrigger]] = None,
    ) -> bytes:
        """
        Read memory from the device.

        :param zone: Memory zone.
        :param slot: Slot index, for data memory only. None for other zones.
        :param block: Block index in the selected slot or zone.
        :param offset: Read/write offset
        :param size: 4 or 32.
        :return: Memory content.
        """
        if size not in (4, 32):
            raise ValueError("size must be 4 or 32.")
        data = self.command(
            ATECCOpCode.READ,
            ({4: 0, 32: 1}[size] << 7) | zone.value,
            self.__make_addr(zone, block, slot, offset),
            trigger=trigger,
        )
        assert data is not None
        return data

    def encrypted_read(
        self, slot, key_id, key, trigger: Optional[Union[bool, int, I2CTrigger]] = None
    ):
        self.nonce()
        self.gen_dig(key_id, key)
        encrypted_data = self.read(
            zone=ATECCZone.DATA, size=32, slot=slot, block=0, trigger=trigger
        )
        # Decrypt the data with temp key (XOR)
        assert self.temp_key is not None
        assert encrypted_data is not None
        return bytes([a ^ b for a, b in zip(self.temp_key, encrypted_data)])

    def encrypted_write(self, slot, key_id, key, data, trigger=0):
        self.nonce()
        self.gen_dig(key_id, key)
        assert self.temp_key is not None
        # Encrypt the data with temp key (XOR)
        encrypted_data = bytes([a ^ b for a, b in zip(self.temp_key, data)])
        # SHA-256(TempKey, Opcode, Param1, Param2, SN[8],
        # SN[0:1], <25 bytes of zeros>, PlainTextData)
        param1 = ({4: 0, 32: 1}[len(data)] << 7) | ATECCZone.DATA.value
        param2 = self.__make_addr(ATECCZone.DATA, 0, slot, 0).to_bytes(2, "little")
        sn = self.serial
        assert sn is not None
        sha = SHA256.new()
        sha.update(self.temp_key)
        sha.update(bytes([ATECCOpCode.WRITE.value, param1]))
        sha.update(param2)
        sha.update(sn[8:9] + sn[0:2] + b"\0" * 25 + data)
        mac = sha.digest()
        self.write(
            zone=ATECCZone.DATA,
            data=encrypted_data,
            mac=mac,
            slot=slot,
            block=0,
            trigger=trigger,
        )

    def __make_addr(
        self,
        zone: ATECCZone,
        block: int,
        slot: Optional[int] = None,
        offset: int = 0,
    ) -> int:
        """
        Generate address for use in write and read commands.

        :param zone: Memory zone.
        :param slot: Slot index, for data memory only. None for other zones.
        :param block: Block index in the selected slot or zone.
        :param offset: Read/write offset
        :return: Encoded address.
        """
        # Check the parameters
        if offset not in range(8):
            raise IndexError("Invalid offset")
        if (zone in (ATECCZone.CONFIG, ATECCZone.OTP)) and (slot is not None):
            raise UserWarning("Slot must be None for the selected zone")

        if zone == ATECCZone.DATA:
            if slot is None:
                raise ValueError("Please provide a slot number.")
            if slot not in range(16):
                raise IndexError(f"Invalid slot {slot}. Should be less than 16.")

            if slot < 8:
                block_range = 2
            elif slot == 8:
                block_range = 8
            else:
                block_range = 4
            if block not in range(block_range):
                raise IndexError("Invalid block")
        # Encode address depending on the memory zone
        if zone == ATECCZone.CONFIG:
            return (block << 3) + offset
        elif zone == ATECCZone.OTP:
            return (block << 3) + offset
        elif zone == ATECCZone.DATA:
            assert slot is not None
            return (block << 8) + (slot << 3) + offset

    def write(
        self,
        data: bytes,
        zone=ATECCZone.DATA,
        block=0,
        slot: Optional[int] = None,
        offset=0,
        trigger=0,
        mac=None,
    ):
        """
        Write memory to the device.

        :param zone: Memory zone.
        :type zone: ATECCZone
        :param data: Data to be written. Size must be 4 or 32.
        :param slot: Slot index, for data memory only. None for other zones.
        :param block: Block index in the selected slot or zone.
        :param offset: Read/write offset
        """
        size = len(data)
        if size not in (4, 32):
            raise ValueError("size must be 4 or 32.")
        result = self.command(
            ATECCOpCode.WRITE,
            ({4: 0, 32: 1}[size] << 7) | zone.value,
            self.__make_addr(zone, block, slot, offset),
            data + (mac if mac is not None else b""),
            wait=0.01,
            trigger=trigger,
        )
        if result is None:
            raise ProtocolError("Received no response after writing to the device.")
        if result != b"":
            raise ProtocolError(
                "Received unexpected response 0x" + hexlify(result).decode()
            )

    def read_serial(self) -> bytes:
        """
        Read and save in `self.serial` the device serial number.

        :return: Device serial number
        """
        self.wake_up()
        buf = self.read(ATECCZone.CONFIG, 32, 0)
        self.serial = buf[0:4] + buf[8:13]
        self.idle()
        return self.serial

    def read_config(self):
        """
        Read all the configuration memory.

        :return: Parsed configuration memory.
        """
        data = bytearray()
        for i in range(4):
            self.wake_up()
            data += self.read(ATECCZone.CONFIG, 32, i)
            self.idle()
        config = Config()
        config.from_bytes(data, 0)
        self.serial = config.serial
        return config

    def lock_config(self):
        """
        Lock config zone of the EEPROM memory.
        """
        # Bit 7 to ignore CRC content checking before lock.
        mode = 1 << 7
        self.command(ATECCOpCode.LOCK, mode, 0)

    def lock_data(self):
        """
        Lock data zone of the EEPROM memory.
        """
        # Bit 7 to ignore CRC content checking before lock.
        mode = (1 << 7) + 0b01
        self.command(ATECCOpCode.LOCK, mode, 0)

    def lock_slot(self, slot: int):
        """
        Lock individual data slot.

        :param slot: Slot number.
        """
        if slot not in range(0x10):
            raise ValueError(
                f"Incorrect value for slot number {slot}: should be less that {0x10}"
            )

        # Bit 7 to ignore CRC content checking before lock.
        mode = ((slot & 0b1111) << 2) + 0b10
        self.command(ATECCOpCode.LOCK, mode, 0)

    def gen_priv_key(
        self, slot: int, trigger: Optional[Union[bool, int, I2CTrigger]] = None
    ):
        """
        Call the GenKey command to generate a private key in a slot.

        :param slot: Slot number.
        :param trigger: permits to generate a trigger on the command.
        """
        # Command execution is long. We must wait before querying the response.
        self.command(ATECCOpCode.GEN_KEY, 1 << 2, slot, trigger=trigger, wait=0.2)

    def gen_pub_key(
        self,
        slot: int,
        trigger: Optional[Union[bool, int, I2CTrigger]] = None,
    ):
        """
        Call the GenKey command to generate a public key from a private key
        stored in a slot.

        :param slot: Slot number.
        """
        # Command execution is long. We must wait before querying the response.
        return self.command(ATECCOpCode.GEN_KEY, 0, slot, trigger=trigger, wait=0.2)

    def nonce(self, update_seed=False) -> bytes:
        """
        Call the Nonce command.
        Update `self.temp_key`.
        Warning: this implementation is vulnerable to replay attacks and must be
        used for testing only (num_in is fixed).
        """
        num_in = b"\x55" * 20
        self.wake_up()
        rand_out = self.command(
            ATECCOpCode.NONCE,
            0b01 if update_seed else 0b00,
            0,
            num_in,  # Don't update EEPROM seed
            wait=0.02,
        )
        self.idle()
        assert rand_out is not None
        sha = SHA256.new()
        sha.update(rand_out)
        sha.update(num_in)
        sha.update(
            b"\x16\x01\x00" if update_seed else b"\x16\x00\x00"
        )  # OpCode, mode and param
        # 2 LSB
        self.temp_key = cast(bytes, sha.digest())

        return rand_out

    def set_tempkey(self, k):
        """
        Set the TempKey value using the Nonce command in bypass mode.
        """
        return self.command(ATECCOpCode.NONCE, 0b11, 0, k)

    def mac(self, key_id: int):
        """

        :param key_id: Key data slot number.
        """
        return self.command(ATECCOpCode.MAC, (1 << 6), key_id)

    def check_mac(
        self,
        key_id: int,
        key: bytes,
        trigger: Optional[Union[bool, int, I2CTrigger]] = None,
        use_tempkey=True,
    ):
        """
        Calls CheckMac command to authenticate with a given key.
        The method `get_serial` and `nonce` must have been called prior to this
        command to get the device serial number and generate the temp key, both
        used in the MAC calculation.

        :param key_id: Key data slot number.
        :param key: Key value.
        """
        sn = self.serial
        assert sn is not None
        other = b"\x00" * 13  # Extra data used in MAC calculation
        sha = SHA256.new()

        mode = 1 if use_tempkey else 0

        # Mode:1 = 1: MAC hash Tempkey
        # Mode:1 = 0: MAC hash Key
        assert len(key) == 32
        sha.update(key)

        # Mode:0 = 1: MAC hash Tempkey
        # Mode:0 = 0: MAC hash Client Challenge
        client_challenge = b"01234567890123456789012345678901"
        assert len(client_challenge) == 32
        sha.update(self.temp_key if use_tempkey else client_challenge)
        last_block = (
            other[0:4]
            + b"\x00" * 8
            + other[4:7]
            + sn[8:9]
            + other[7:11]
            + sn[0:2]
            + other[11:13]
        )
        assert len(last_block) == 24
        sha.update(last_block)
        mac = sha.digest()
        data = client_challenge + mac + other
        assert len(data) == 32 + 32 + 13

        self.command(ATECCOpCode.CHECK_MAC, mode, key_id, data=data, trigger=trigger)

    def gen_dig(
        self,
        key_id: int,
        key: bytes,
        trigger: Optional[Union[bool, int, I2CTrigger]] = None,
    ):
        """
        Calls GenDig command to derive a key from a data slot.
        The method `get_serial` and `nonce` must have been called prior to this
        command to get the device serial number and generate the temp key, both
        used in the new temp key calculation.
        `self.temp_key` is updated.

        :param key_id: Key data slot number.
        :param key: Key value.
        """
        sn = self.serial
        assert sn is not None
        assert self.temp_key is not None
        self.command(ATECCOpCode.GEN_DIG, 2, key_id, trigger=trigger)
        data = (
            key
            + b"\x15"
            + bytes([2])
            + key_id.to_bytes(2, "little")
            + sn[8:9]
            + sn[0:2]
            + b"\x00" * 25
            + self.temp_key
        )
        sha = SHA256.new()
        sha.update(data)
        self.temp_key = cast(bytes, sha.digest())

    def aes(
        self,
        encrypt: bool,
        data_in: bytes,
        key_slot: Optional[int] = None,
        do_nonce=True,
        trigger: Optional[Union[bool, int, I2CTrigger]] = None,
    ) -> bytes:
        if key_slot is None:
            if do_nonce:
                self.nonce()
            # 0xFFFF is passed to indicate TempKey
            key_param = 0xFFFF
        else:
            key_param = key_slot
        mode = 0 if encrypt else 1
        result = self.command(
            ATECCOpCode.AES, mode, key_param, data_in, trigger=trigger
        )
        assert result is not None
        return result
