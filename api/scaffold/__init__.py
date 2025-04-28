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


from enum import Enum, Flag, auto
from time import sleep
from typing import Any, Literal, Optional, Union
import serial.tools.list_ports
import serial.tools.list_ports_common
from packaging.version import parse as parse_version, Version as PackagingVersion
from .bus import ScaffoldBus, Register, TimeoutError

# Version of the Scaffold API
__version__ = "0.9.4"

# Prevent flake8 from complaining about unused import. This class is actually
# re-exported. This should be improved in the future.
__all__ = ["TimeoutError"]


class Signal:
    """
    Base class for all connectable signals in Scaffold. Every :class:`Signal`
    instance has a Scaffold board parent instance which is used to electrically
    configure the hardware board when two :class:`Signal` are connected
    together.
    """

    def __init__(self, parent: "Scaffold", path: str):
        """
        :param parent: The :class:`Scaffold` instance which the signal belongs to.
        :param path: Signal path string. Uniquely identifies a Scaffold board
            internal signal. For instance '/dev/uart0/tx'.
        """
        self.__parent = parent
        self.__path = path

    @property
    def parent(self):
        """Parent :class:`Scaffold` board instance. Read-only."""
        return self.__parent

    @property
    def path(self):
        """Signal path. For instance '/dev/uart0/tx'. Read-only."""
        return self.__path

    @property
    def name(self) -> str:
        """
        Signal name (last element of the path). For instance 'tx'. Read-only.
        """
        return self.__path.split("/")[-1]

    def __str__(self) -> str:
        """:return: Signal path. For instance '/dev/uart0/tx'."""
        return self.__path

    def __lshift__(self, other: Union["Signal", Literal[0, 1]]):
        """
        Feed the current signal with another signal.

        :param other: Another :class:`Signal` instance. The other signal must
            belong to the same :class:`Scaffold` instance.
        """
        self.__parent.sig_connect(self, other)

    def __rshift__(self, other: "Signal"):
        """
        Feed another signal with current signal.

        :param other: Another :class:`Signal` instance. The other signal must
            belong to the same :class:`Scaffold` instance.
        """
        self.__parent.sig_connect(other, self)


class Module:
    """
    Class to facilitate signals and registers declaration.
    """

    def __init__(self, parent: "Scaffold", path: Optional[str] = None):
        """
        :param parent: The :class:`Scaffold` instance owning the module.
        :param path: Base path for the signals. For instance '/uart'.
        """
        self.__parent = parent
        self.__path = path
        self.__registers: list[Register] = []

    def add_signal(self, name: str) -> Signal:
        """
        Add a new signal to the object and set it as a new attribute of the
        instance.

        :name: Signal name.
        :type name: str
        :return: Created signal object
        :rtype: Signal
        """
        assert not hasattr(self, name)
        if self.__path is None:
            path = "/" + name
        else:
            path = self.__path + "/" + name
        sig = Signal(self.__parent, path)
        return sig

    def add_signals(self, *names: str) -> list[Signal]:
        """
        Add many signals to the object and set them as new attributes of the
        instance.

        :param names: Name of the signals.
        :type names: Iterable(str)
        :return: List of created signals
        :rtype: List(Signal)
        """
        return list(self.add_signal(name) for name in names)

    def add_register(self, *args: Any, **kwargs: Any) -> Register:
        """
        Create a new register.
        :param args: Arguments passed to Register.__init__.
        :param kwargs: Keyword arguments passed to Register.__init__.
        """
        reg = Register(self.__parent, *args, **kwargs)
        self.__registers.append(reg)
        return reg

    def __setattr__(self, key: str, value: Any):
        if key in self.__dict__:
            item = self.__dict__[key]
            if isinstance(item, Register):
                item.set(value)
                return
            else:
                super().__setattr__(key, value)
                return
        super().__setattr__(key, value)

    def reset_registers(self):
        """
        Call :meth:`Register.reset` on each defined register.
        """
        for reg in self.__registers:
            reg.reset()

    @property
    def parent(self) -> "Scaffold":
        """:class:`Scaffold` instance the module belongs to. Read-only."""
        return self.__parent


class FreqRegisterHelper:
    """
    Helper to provide frequency attributes which compute clock divisor
    registers value based on asked target frequencies.
    """

    def __init__(self, sys_freq: int, reg: Register):
        """
        :param sys_freq: System base frequency used to compute clock divisors.
        :type sys_freq: int
        :param reg: Register to be configured.
        :type reg: :class:`scaffold.Register`
        """
        self.__sys_freq = sys_freq
        self.__reg = reg
        self.__cache: Optional[float] = None
        self.__max_err = 0.01

    def set(self, value: float):
        """
        Configure the register value depending on the target frequency.

        :param value: Target frequency, in Hertz.
        :type value: float
        """
        d = round((0.5 * self.__sys_freq / value) - 1)
        # Check that the divisor fits in the register
        if d > self.__reg.max:
            raise ValueError("Target clock frequency is too low.")
        if d < self.__reg.min:
            raise ValueError("Target clock frequency is too high.")
        # Calculate error between target and effective clock frequency
        real = self.__sys_freq / ((d + 1) * 2)
        err = abs(real - value) / value
        if err > self.__max_err:
            raise RuntimeError(
                f"Cannot reach target clock frequency within "
                f"{self.__max_err * 100}% accuracy."
            )
        self.__reg.set(d)
        self.__cache = real

    def get(self) -> Optional[float]:
        """
        :return: Actual clock frequency. None if frequency has not been set.
        """
        return self.__cache


class Version(Module):
    """Version module of Scaffold."""

    def __init__(self, parent: "Scaffold"):
        """
        :param parent: The :class:`Scaffold` instance owning the version module.
        """
        super().__init__(parent)
        self.reg_data = self.add_register("r", 0x0100)

    def get_string(self) -> str:
        """
        Read the data register multiple times until the full version string has
        been retrieved.
        :return: Hardware version string.
        """
        # We consider the version string is not longer than 32 bytes. This
        # allows us reading the string with only one command to be faster.
        buf = self.reg_data.read(32 + 1 + 32 + 1)
        offset = 0
        result = ""
        # Find the first \0 character.
        while buf[offset] != 0:
            offset += 1
        offset += 1
        # Read characters until second \0 character.
        while buf[offset] != 0:
            result += chr(buf[offset])
            offset += 1
        return result


class LEDMode(int, Enum):
    EVENT = 0
    VALUE = 1


class LED:
    """
    Represents a LED of the board.
    Each instance of this class is an attribute of a :class:`LEDs` instance.
    """

    def __init__(self, parent: "LEDs", index: int):
        """
        :param parent: Parent LEDs module instance.
        :param index: Bit index of the LED.
        """
        self.__parent = parent
        self.__index = index

    @property
    def mode(self) -> LEDMode:
        """
        LED lighting mode. When mode is EVENT, the led is lit for a short
        period of time when an edge is detected on the monitored signal. When
        the mode is VALUE, the LED is lit when the monitored signal is high.
        Default mode is EVENT.

        :type: LEDMode.
        """
        return LEDMode((self.__parent.reg_mode.get() >> self.__index) & 1)

    @mode.setter
    def mode(self, value: LEDMode):
        self.__parent.reg_mode.set_mask(
            LEDMode(value) << self.__index, 1 << self.__index
        )


class LEDs(Module):
    """LEDs module of Scaffold."""

    def __init__(self, parent: "Scaffold"):
        """
        :param parent: The :class:`Scaffold` instance owning the LED modules.
        """
        super().__init__(parent)
        self.reg_control = self.add_register("w", 0x0200)
        self.reg_brightness = self.add_register("w", 0x0201)
        self.reg_leds_0 = self.add_register("w", 0x0202)
        self.reg_leds_1 = self.add_register("w", 0x0203)
        self.reg_leds_2 = self.add_register("w", 0x0204)
        self.reg_mode = self.add_register("w", 0x0205, wideness=3)
        assert self.parent.version is not None
        if self.parent.version <= parse_version("0.3"):
            # Scaffold hardware v1 only
            offset = 6
            self.a0 = LED(self, 0 + offset)
            self.a1 = LED(self, 1 + offset)
            self.b0 = LED(self, 2 + offset)
            self.b1 = LED(self, 3 + offset)
            self.c0 = LED(self, 4 + offset)
            self.c1 = LED(self, 5 + offset)
            self.d0 = LED(self, 6 + offset)
            self.d1 = LED(self, 7 + offset)
            self.d2 = LED(self, 8 + offset)
            self.d3 = LED(self, 9 + offset)
            self.d4 = LED(self, 10 + offset)
            self.d5 = LED(self, 11 + offset)
        else:
            # Scaffold hardware v1.1
            offset = 8
            self.a0 = LED(self, 0 + offset)
            self.a1 = LED(self, 1 + offset)
            self.a2 = LED(self, 2 + offset)
            self.a3 = LED(self, 3 + offset)
            self.d0 = LED(self, 4 + offset)
            self.d1 = LED(self, 5 + offset)
            self.d2 = LED(self, 6 + offset)
            self.d3 = LED(self, 7 + offset)
            self.d4 = LED(self, 8 + offset)
            self.d5 = LED(self, 9 + offset)

    def reset(self):
        """Set module registers to default values."""
        self.reg_control.set(0)
        self.reg_brightness.set(20)
        self.reg_mode.set(0)

    @property
    def brightness(self) -> float:
        """
        LEDs brightness. 0 is the minimum. 1 is the maximum.

        :type: float
        """
        return self.reg_brightness.get() / 127.0

    @brightness.setter
    def brightness(self, value: float):
        if (value < 0) or (value > 1):
            raise ValueError("Invalid brightness value")
        self.reg_brightness.set(int(value * 127))

    @property
    def disabled(self) -> bool:
        """If set to True, LEDs driver outputs are all disabled."""
        return bool(self.reg_control.get() & 1)

    @disabled.setter
    def disabled(self, value: bool):
        self.reg_control.set_mask(int(bool(value)), 1)

    @property
    def override(self) -> bool:
        """
        If set to True, LEDs state is the value of the leds_n registers.
        """
        return bool(self.reg_control.get() & 2)

    @override.setter
    def override(self, value: bool):
        self.reg_control.set_mask(int(bool(value)) << 1, 2)


class UARTParity(int, Enum):
    """Possible parity modes for UART peripherals."""

    NONE = 0
    ODD = 1
    EVEN = 2


class UART(Module):
    """
    UART module of Scaffold.
    """

    __REG_CONTROL_BIT_FLUSH = 0
    __REG_CONFIG_BIT_TRIGGER = 3
    __REG_CONFIG_BIT_PARITY = 0

    def __init__(self, parent: "Scaffold", index: int):
        """
        :param parent: The :class:`Scaffold` instance owning the UART module.
        :param index: UART module index.
        """
        super().__init__(parent, f"/uart{index}")
        self.__index = index
        # Declare the signals
        self.rx, self.tx, self.trigger = self.add_signals("rx", "tx", "trigger")
        # Declare the registers
        self.__addr_base = base = 0x0400 + 0x0010 * index
        self.reg_status = self.add_register("rv", base)
        self.reg_control = self.add_register("w", base + 1)
        self.reg_config = self.add_register("w", base + 2)
        self.reg_divisor = self.add_register("w", base + 3, wideness=2, min_value=1)
        self.reg_data = self.add_register("rwv", base + 4)
        # Current board target baudrate (this is not the effective baudrate)
        self.__cache_baudrate = None
        # Accuracy parameter
        self.max_err = 0.01

    def reset(self):
        """
        Reset the UART to a default configuration: 9600 bps, no parity, one
        stop bit, trigger disabled.
        """
        self.reg_config.set(0)
        self.reg_control.set(0)
        self.baudrate = 9600

    @property
    def baudrate(self) -> Optional[float]:
        """
        Target UART baudrate.

        :getter: Returns current baudrate, or None if no baudrate has
            been previously set during current session.
        :setter: Set target baudrate. If baudrate cannot be reached within 1%
            accuracy, a RuntimeError is thrown. Reading the baudrate attribute
            after setting it will return the real effective baudrate.
        """
        return self.__cache_baudrate

    @baudrate.setter
    def baudrate(self, value: int):
        """
        Set target baudrate. If baudrate is too low or too high, a ValueError
        is thrown. If baudrate cannot be reached within 1% accuracy, a
        RuntimeError is thrown.
        :param value: New target baudrate.
        """
        d = round((self.parent.sys_freq / value) - 1)
        # Check that the divisor can be stored on 16 bits.
        if d > 0xFFFF:
            raise ValueError("Target baudrate is too low.")
        if d < 1:
            raise ValueError("Target baudrate is too high.")
        # Calculate error between target and effective baudrates
        real = self.parent.sys_freq / (d + 1)
        err = abs(real - value) / value
        max_err = self.max_err
        if err > max_err:
            raise RuntimeError(
                f"Cannot reach target baudrate within {max_err * 100}% accuracy."
            )
        self.reg_divisor.set(d)
        self.__cache_baudrate = real

    def transmit(self, data: bytes, trigger: Union[bool, int] = False):
        """
        Transmit data using the UART.

        :param data: Data to be transmitted.
        :param trigger: True or 1 to enable trigger on last byte, False or 0 to
            disable trigger.
        """
        if trigger:
            buf = data[:-1]
        else:
            buf = data
        # Polling on status.ready bit before sending each character.
        self.reg_data.write(buf, self.reg_status.poll(mask=0x01, value=0x01))
        if trigger:
            config = self.reg_config.get()
            # Enable trigger as soon as previous transmission ends
            self.reg_config.write(
                config | (1 << self.__REG_CONFIG_BIT_TRIGGER),
                self.reg_status.poll(mask=0x01, value=0x01),
            )
            # Send the last byte. No need for polling here, because it has
            # already been done when enabling trigger.
            self.reg_data.write(data[-1])
            # Disable trigger
            self.reg_config.write(config, self.reg_status.poll(mask=0x01, value=0x01))

    def receive(self, n: int = 1):
        """
        Receive n bytes from the UART. This function blocks until all bytes
        have been received or the timeout expires and a TimeoutError is thrown.
        """
        return self.reg_data.read(n, self.reg_status.poll(mask=0x04, value=0x00))

    def flush(self):
        """Discard all the received bytes in the FIFO."""
        self.reg_control.set_bit(self.__REG_CONTROL_BIT_FLUSH, 1)

    @property
    def parity(self) -> UARTParity:
        """
        Parity mode. Disabled by default.

        :type: UARTParity
        """
        return UARTParity(
            (self.reg_config.get() >> self.__REG_CONFIG_BIT_PARITY) & 0b11
        )

    @parity.setter
    def parity(self, value: UARTParity):
        self.reg_config.set_mask(
            (value & 0b11) << self.__REG_CONFIG_BIT_PARITY,
            0b11 << self.__REG_CONFIG_BIT_PARITY,
        )


class Polarity(int, Enum):
    HIGH_ON_PULSES = 0
    LOW_ON_PULSES = 1


class PulseGenerator(Module):
    """
    Pulse generator module of Scaffold.
    Usually abreviated as pgen.
    """

    def __init__(self, parent: "Scaffold", index: int, base: int):
        """
        :param parent: The :class:`Scaffold` instance owning the pulse generator module.
        :param path: Module path.
        :param base: Base address for all registers.
        """
        super().__init__(parent, f"/pgen{index}")
        # Create the signals
        self.start, self.out = self.add_signals("start", "out")
        # Create the registers
        self.reg_status = self.add_register("rv", base)
        self.reg_control = self.add_register("wv", base + 1)
        self.reg_config = self.add_register("w", base + 2, reset=0)
        self.reg_delay = self.add_register("w", base + 3, wideness=3, reset=0)
        self.reg_interval = self.add_register("w", base + 4, wideness=3, reset=0)
        self.reg_width = self.add_register("w", base + 5, wideness=3, reset=0)
        self.reg_count = self.add_register("w", base + 6, wideness=2, reset=0)

    def fire(self):
        """Manually trigger the pulse generation."""
        self.reg_control.set(1)

    def wait_ready(self):
        """
        Wait while the pulse generator is busy.

        This uses the polling mechanism on the ready bit in the status
        register. It can be used to block next commands and synchronize their
        execution to the end of the pulse.
        """
        # Dummy write to the address 0 which is not mapped.
        self.parent.bus.write(0, 0, self.reg_status.poll(mask=1, value=1))

    def __duration_to_clock_cycles(self, t: float) -> int:
        """
        Calculate the number of clock cycles corresponding to a given time.

        :param t: Time in seconds.
        :type t: float.
        """
        if t < 0:
            raise ValueError("Duration cannot be negative")
        cc = round(t * self.parent.sys_freq)
        return cc

    def __clock_cycles_to_duration(self, cc: int) -> float:
        """
        Calculate the time elapsed during a given number of clock cycles.

        :param cc: Number of clock cycles.
        :type cc: int
        """
        return cc / self.parent.sys_freq

    @property
    def delay(self) -> float:
        """
        Delay before pulse, in seconds.

        :type: float
        """
        return self.__clock_cycles_to_duration(self.reg_delay.get() + 1)

    @delay.setter
    def delay(self, value: float):
        n = self.__duration_to_clock_cycles(value) - 1
        self.reg_delay.set(n)

    @property
    def delay_min(self) -> float:
        """:return: Minimum possible delay."""
        return self.__clock_cycles_to_duration(1)

    @property
    def delay_max(self) -> float:
        """:return: Maximum possible delay."""
        return self.__clock_cycles_to_duration(self.reg_delay.max + 1)

    @property
    def interval(self) -> float:
        """
        Delay between pulses, in seconds.

        :type: float
        """
        return self.__clock_cycles_to_duration(self.reg_interval.get() + 1)

    @interval.setter
    def interval(self, value: float):
        n = self.__duration_to_clock_cycles(value) - 1
        self.reg_interval.set(n)

    @property
    def interval_min(self) -> float:
        """:return: Minimum possible interval."""
        return self.__clock_cycles_to_duration(1)

    @property
    def interval_max(self) -> float:
        """:return: Maximum possible interval."""
        return self.__clock_cycles_to_duration(self.reg_interval.max + 1)

    @property
    def width(self) -> float:
        """
        Pulse width, in seconds.

        :type: float
        """
        return self.__clock_cycles_to_duration(self.reg_width.get() + 1)

    @width.setter
    def width(self, value: float):
        n = self.__duration_to_clock_cycles(value) - 1
        self.reg_width.set(n)

    @property
    def width_min(self) -> float:
        """:return: Minimum possible pulse width."""
        return self.__clock_cycles_to_duration(1)

    @property
    def width_max(self) -> float:
        """:return: Maximum possible pulse width."""
        return self.__clock_cycles_to_duration(self.reg_width.max + 1)

    @property
    def count(self) -> int:
        """
        Number of pulses to be generated. Minimum value is 1. Maximum value is
        2^16.

        :type: int
        """
        return self.reg_count.get() + 1

    @count.setter
    def count(self, value: int):
        if value not in range(1, 2**16 + 1):
            raise ValueError("Invalid pulse count")
        self.reg_count.set(value - 1)

    @property
    def count_min(self) -> int:
        """:return: Minimum possible pulse count."""
        return 1

    @property
    def count_max(self) -> int:
        """:return: Maximum possible pulse count."""
        return self.reg_count.max + 1

    @property
    def polarity(self) -> Polarity:
        """
        Pulse polarity. If 0, output is low when idle, and high during pulses.
        When 1, output is high when idle, and low during pulses.
        """
        return Polarity(self.reg_config.get() & 1)

    @polarity.setter
    def polarity(self, value: Polarity):
        if value not in [Polarity.HIGH_ON_PULSES, Polarity.LOW_ON_PULSES]:
            raise ValueError("Invalid polarity value: must be 0 or 1")
        self.reg_config.set_bit(0, value)


class Power(Module):
    """Controls the platform and DUT sockets power supplies."""

    __ADDR_CONTROL = 0x0600

    def __init__(self, parent: "Scaffold"):
        """:param parent: The :class:`Scaffold` instance owning the power module."""
        super().__init__(parent, "/power")
        self.reg_control = self.add_register("rwv", self.__ADDR_CONTROL)
        self.dut_trigger, self.platform_trigger = self.add_signals(
            "dut_trigger", "platform_trigger"
        )

    @property
    def all(self) -> int:
        """
        All power-supplies state. int. Bit 0 corresponds to the DUT power
        supply. Bit 1 corresponds to the platform power-supply. When a bit is
        set to 1, the corresponding power supply is enabled. This attribute can
        be used to control both power supplies simultaneously.
        """
        return self.reg_control.get()

    @all.setter
    def all(self, value: int):
        assert (value & ~0b11) == 0
        self.reg_control.set(value)

    @property
    def platform(self):
        """Platform power-supply state. int."""
        return self.reg_control.get_bit(1)

    @platform.setter
    def platform(self, value: int):
        self.reg_control.set_bit(1, value)

    @property
    def dut(self):
        """DUT power-supply state. int."""
        return self.reg_control.get_bit(0)

    @dut.setter
    def dut(self, value: int):
        self.reg_control.set_bit(0, value)

    def restart_dut(self, toff: float = 0.05, ton: float = 0):
        """
        Power-cycle the DUT socket.

        :param toff: Time to wait in seconds between power-off and power-on.
        :type toff: float
        :param ton: Time to wait in seconds after power-on.
        :type ton: float
        """
        self.dut = 0
        if toff > 0:
            sleep(toff)
        self.dut = 1
        if ton > 0:
            sleep(ton)

    def restart_platform(self, toff: float = 0.05, ton: float = 0):
        """
        Power-cycle the platform socket.

        :param toff: Time to wait in seconds between power-off and power-on.
        :type toff: float
        :param ton: Time to wait in seconds after power-on.
        :type ton: float
        """
        self.platform = 0
        if toff > 0:
            sleep(toff)
        self.platform = 1
        if ton > 0:
            sleep(ton)

    def restart_all(self, toff: float = 0.05, ton: float = 0):
        """
        Power-cycle both DUT and platform sockets.

        :param toff: Time to wait in seconds between power-off and power-on.
        :type toff: float
        :param ton: Time to wait in seconds after power-on.
        :type ton: float
        """
        self.all = 0b00
        if toff > 0:
            sleep(toff)
        self.all = 0b11
        if ton > 0:
            sleep(ton)


class ISO7816ParityMode(int, Enum):
    EVEN = 0b00  # Even parity (standard and default)
    ODD = 0b01  # Odd parity
    FORCE_0 = 0b10  # Parity bit always 0
    FORCE_1 = 0b11  # Parity bit always 1


class ISO7816(Module):
    """
    ISO7816 peripheral of Scaffold. Does not provide convention or protocol
    management. See :class:`scaffold.iso7816.Smartcard` for more features.
    """

    __REG_STATUS_BIT_READY = 0
    __REG_STATUS_BIT_PARITY_ERROR = 1
    __REG_STATUS_BIT_EMPTY = 2
    __REG_CONTROL_BIT_FLUSH = 0
    __REG_CONFIG_TRIGGER_TX = 0
    __REG_CONFIG_TRIGGER_RX = 1
    __REG_CONFIG_TRIGGER_LONG = 2
    __REG_CONFIG_PARITY_MODE = 3

    def __init__(self, parent: "Scaffold"):
        """
        :param parent: The :class:`Scaffold` instance owning the ISO7816 module.
        """
        super().__init__(parent, "/iso7816")
        self.io_in, self.io_out, self.clk, self.trigger = self.add_signals(
            "io_in", "io_out", "clk", "trigger"
        )
        self.__addr_base = base = 0x0500
        self.reg_status = self.add_register("rv", base)
        self.reg_control = self.add_register("w", base + 1)
        self.reg_config = self.add_register("w", base + 2)
        self.reg_divisor = self.add_register("w", base + 3)
        self.reg_etu = self.add_register("w", base + 4, wideness=2)
        self.reg_data = self.add_register("rwv", base + 5)
        # Accuracy parameter
        self.max_err = 0.01

    def reset_config(self):
        """
        Reset ISO7816 peripheral to its default configuration.
        """
        self.reg_config.set(0)
        self.etu = 372
        self.clock_frequency = 1e6  # 1 MHz

    @property
    def clock_frequency(self):
        """
        Target ISO7816 clock frequency. According to ISO7816-3 specification,
        minimum frequency is 1 Mhz and maximum frequency is 5 MHz. Scaffold
        hardware allows going up to 50 Mhz and down to 195312.5 Hz (although
        this may not work with the smartcard).

        :getter: Returns current clock frequency, or None if it has not been
            set previously.
        :setter: Set clock frequency. If requested frequency cannot be reached
            within 1% accuracy, a RuntimeError is thrown. Reading this
            attribute after setting it will return the real effective clock
            frequency.
        """
        return self.__cache_clock_frequency

    @clock_frequency.setter
    def clock_frequency(self, value: float):
        d = round((0.5 * self.parent.sys_freq / value) - 1)
        # Check that the divisor fits one unsigned byte.
        if d > 0xFF:
            raise ValueError("Target clock frequency is too low.")
        if d < 0:
            raise ValueError("Target clock frequency is too high.")
        # Calculate error between target and effective clock frequency
        real = self.parent.sys_freq / ((d + 1) * 2)
        err = abs(real - value) / value
        max_err = self.max_err = 0.01
        if err > max_err:
            raise RuntimeError(
                f"Cannot reach target clock frequency within {max_err * 100}% accuracy."
            )
        self.reg_divisor.set(d)
        self.__cache_clock_frequency = real

    @property
    def etu(self):
        """
        ISO7816 ETU parameter. Value must be in range [1, 2^11-1]. Default ETU
        is 372.
        """
        return self.reg_etu.get() + 1

    @etu.setter
    def etu(self, value: int):
        if value not in range(1, 2**11):
            raise ValueError("Invalid ETU parameter")
        self.reg_etu.set(value - 1)

    def flush(self):
        """Discard all the received bytes in the FIFO."""
        self.reg_control.write(1 << self.__REG_CONTROL_BIT_FLUSH)

    def receive(self, n: int = 1, timeout: Optional[float] = None):
        """
        Receive bytes. This function blocks until all bytes have been
        received or the timeout expires and a TimeoutError is thrown.

        :param n: Number of bytes to be read.
        """
        with self.parent.timeout_section(timeout):
            return self.reg_data.read(
                n,
                self.reg_status.poll(
                    mask=(1 << self.__REG_STATUS_BIT_EMPTY), value=0x00
                ),
            )

    def transmit(self, data: bytes, trigger: bool = False):
        """
        Transmit data.

        :param data: Data to be transmitted.
        :param trigger: Enable trigger on the last transmitted byte.
        """
        # Polling on status.ready bit before sending each character
        if not trigger:
            self.reg_data.write(
                data,
                self.reg_status.poll(
                    mask=(1 << self.__REG_STATUS_BIT_READY),
                    value=(1 << self.__REG_STATUS_BIT_READY),
                ),
            )
        else:
            # We want to trig on the last sent character
            self.reg_config.set_bit(
                self.__REG_CONFIG_TRIGGER_TX,
                0,
                self.reg_status.poll(
                    mask=(1 << self.__REG_STATUS_BIT_READY),
                    value=(1 << self.__REG_STATUS_BIT_READY),
                ),
            )
            self.reg_data.write(
                data[:-1],
                self.reg_status.poll(
                    mask=(1 << self.__REG_STATUS_BIT_READY),
                    value=(1 << self.__REG_STATUS_BIT_READY),
                ),
            )
            self.reg_config.set_bit(
                self.__REG_CONFIG_TRIGGER_TX,
                1,
                self.reg_status.poll(
                    mask=(1 << self.__REG_STATUS_BIT_READY),
                    value=(1 << self.__REG_STATUS_BIT_READY),
                ),
            )
            self.reg_data.write(data[-1])
            self.reg_config.set_bit(
                self.__REG_CONFIG_TRIGGER_TX,
                0,
                self.reg_status.poll(
                    mask=(1 << self.__REG_STATUS_BIT_READY),
                    value=(1 << self.__REG_STATUS_BIT_READY),
                ),
            )

    @property
    def empty(self):
        """True if reception FIFO is empty."""
        return bool(self.reg_status.get() & (1 << self.__REG_STATUS_BIT_EMPTY))

    @property
    def parity_mode(self):
        """
        Parity mode. Standard is Even parity, but it can be changed to odd or
        forced to a fixed value for testing purposes.
        :type: ISO7816ParityMode
        """
        return ISO7816ParityMode(
            (self.reg_config.get() >> self.__REG_CONFIG_PARITY_MODE) & 0b11
        )

    @parity_mode.setter
    def parity_mode(self, value: ISO7816ParityMode):
        self.reg_config.set_mask(
            (value & 0b11) << self.__REG_CONFIG_PARITY_MODE,
            0b11 << self.__REG_CONFIG_PARITY_MODE,
        )

    @property
    def trigger_tx(self):
        """
        Enable or disable trigger upon transmission.
        :type: bool
        """
        return bool(self.reg_config.get_bit(self.__REG_CONFIG_TRIGGER_TX))

    @trigger_tx.setter
    def trigger_tx(self, value: bool):
        self.reg_config.set_bit(self.__REG_CONFIG_TRIGGER_TX, value)

    @property
    def trigger_rx(self):
        """
        Enable or disable trigger upon reception.
        :type: bool
        """
        return bool(self.reg_config.get_bit(self.__REG_CONFIG_TRIGGER_RX))

    @trigger_rx.setter
    def trigger_rx(self, value: bool):
        self.reg_config.set_bit(self.__REG_CONFIG_TRIGGER_RX, value)

    @property
    def trigger_long(self):
        """
        Enable or disable long trigger (set on transmission, cleared on
        reception). When changing this value, wait until transmission buffer is
        empty.

        :type: bool
        """
        return bool(self.reg_config.get_bit(self.__REG_CONFIG_TRIGGER_LONG))

    @trigger_long.setter
    def trigger_long(self, value: bool):
        # We want until transmission is ready to avoid triggering on a pending
        # one.
        self.reg_config.set_bit(
            self.__REG_CONFIG_TRIGGER_LONG,
            value,
            self.reg_status.poll(
                mask=1 << self.__REG_STATUS_BIT_READY,
                value=1 << self.__REG_STATUS_BIT_READY,
            ),
        )


class I2CNackError(Exception):
    """
    This exception is thrown by I2C peripheral when a transaction received a
    NACK from the I2C slave.
    """

    def __init__(self, index: int):
        """
        :param index: NACKed byte index. If N, then the N-th byte has not been
            acked.
        :type index: int
        """
        super().__init__()
        self.index = index

    def __str__(self):
        """:return: Error details on the NACKed I2C transaction."""
        return f"Byte of index {self.index} NACKed during I2C transaction."


class I2CTrigger(Flag):
    START = auto()
    END = auto()


class I2C(Module):
    """
    I2C module of Scaffold.
    """

    __REG_STATUS_BIT_READY = 0
    __REG_STATUS_BIT_NACK = 1
    __REG_STATUS_BIT_DATA_AVAIL = 2
    __REG_CONTROL_BIT_START = 0
    __REG_CONTROL_BIT_FLUSH = 1
    __REG_CONFIG_BIT_TRIGGER_START = 0
    __REG_CONFIG_BIT_TRIGGER_END = 1
    __REG_CONFIG_BIT_CLOCK_STRETCHING = 2

    def __init__(self, parent: "Scaffold", index: int):
        """
        :param parent: The :class:`Scaffold` instance owning the I2C module.
        :param index: I2C module index.
        """
        super().__init__(parent, f"/i2c{index}")
        self.__index = index
        # Declare the signals
        self.sda_in, self.sda_out, self.scl_in, self.scl_out, self.trigger = (
            self.add_signals("sda_in", "sda_out", "scl_in", "scl_out", "trigger")
        )
        # Declare the registers
        self.__addr_base = base = 0x0700 + 0x0010 * index
        self.reg_status = self.add_register("rv", base)
        self.reg_control = self.add_register("w", base + 1)
        self.reg_config = self.add_register("w", base + 2)
        self.reg_divisor = self.add_register("w", base + 3, wideness=2, min_value=1)
        self.reg_data = self.add_register("rwv", base + 4)
        self.reg_size_h = self.add_register("rwv", base + 5)
        self.reg_size_l = self.add_register("rwv", base + 6)
        self.address = None
        # Current I2C clock frequency
        self.__cache_frequency = None

    def reset_config(self):
        """
        Reset the I2C peripheral to a default configuration.
        """
        self.reg_divisor.set(1)
        self.reg_size_h.set(0)
        self.reg_size_l.set(0)
        self.reg_config.set(
            (1 << self.__REG_CONFIG_BIT_CLOCK_STRETCHING)
            | (1 << self.__REG_CONFIG_BIT_TRIGGER_START)
        )

    def flush(self):
        """Discards all bytes in the transmission/reception FIFO."""
        self.reg_control.write(1 << self.__REG_CONTROL_BIT_FLUSH)

    def raw_transaction(
        self,
        data: bytes,
        read_size: int,
        trigger: Optional[Union[int, str, I2CTrigger]] = None,
    ):
        """
        Executes an I2C transaction. This is a low-level function which does
        not manage I2C addressing nor read/write mode (those shall already be
        defined in data parameter).

        :param data: Transmitted bytes. First byte is usually the address of
            the slave and the R/W bit. If the R/W bit is 0 (write), this
            parameter shall then contain the bytes to be transmitted, and
            read_size shall be zero.
        :type data: bytes
        :param read_size: Number of bytes to be expected from the slave. 0 in
            case of a write transaction.
        :type read_size: int
        :param trigger: Trigger configuration. If int and value is 1, trigger
            is asserted when the transaction starts. If str, it may contain the
            letter 'a' and/or 'b', where 'a' asserts trigger on transaction
            start and 'b' on transaction end.
        :type trigger: int, str or `I2CTrigger`.
        :raises I2CNackError: If a NACK is received during the transaction.
        """
        # Verify trigger parameter before doing anything
        t_start = False
        t_end = False
        if isinstance(trigger, int):
            if trigger not in range(2):
                raise ValueError(
                    "Invalid trigger parameter. "
                    "It should be 0 or 1, a string containing 'a' or 'b', "
                    "or a flag of type I2CTrigger"
                )
            t_start = trigger == 1
        elif isinstance(trigger, str):
            t_start = "a" in trigger
            t_end = "b" in trigger
        elif isinstance(trigger, I2CTrigger):
            t_start = I2CTrigger.START in trigger
            t_end = I2CTrigger.END in trigger
        else:
            if trigger is not None:
                raise ValueError("Invalid trigger parameter")
        self.flush()
        self.reg_size_h.set(read_size >> 8)
        self.reg_size_l.set(read_size & 0xFF)
        # Preload the FIFO
        self.reg_data.write(data)
        # Configure trigger for this transaction
        config_value = 0
        if t_start:
            config_value |= 1 << self.__REG_CONFIG_BIT_TRIGGER_START
        if t_end:
            config_value |= 1 << self.__REG_CONFIG_BIT_TRIGGER_END
        # Write config with mask to avoid overwritting clock_stretching
        # option bit
        self.reg_config.set_mask(
            config_value,
            (1 << self.__REG_CONFIG_BIT_TRIGGER_START)
            | (1 << self.__REG_CONFIG_BIT_TRIGGER_END),
        )
        # Start the transaction
        self.reg_control.write(1 << self.__REG_CONTROL_BIT_START)
        # Wait until end of transaction and read NACK flag
        st = self.reg_status.read(
            poll=self.reg_status.poll(
                mask=(1 << self.__REG_STATUS_BIT_READY),
                value=(1 << self.__REG_STATUS_BIT_READY),
            )
        )[0]
        nacked = (st & (1 << self.__REG_STATUS_BIT_NACK)) != 0
        # Fetch all the bytes which are stored in the FIFO.
        if nacked:
            # Get the number of bytes remaining.
            remaining = (self.reg_size_h.get() << 8) + self.reg_size_l.get()
            raise I2CNackError(len(data) - remaining - 1)
        else:
            fifo = self.reg_data.read(
                read_size,
                self.reg_status.poll(
                    mask=(1 << self.__REG_STATUS_BIT_DATA_AVAIL),
                    value=(1 << self.__REG_STATUS_BIT_DATA_AVAIL),
                ),
            )
            # FIFO emptyness verification can be enabled below for debug
            # purpose. This shall always be the case, unless there is an
            # implementation bug. This check is not enabled by default because
            # it will slow down I2C communication.
            # if self.reg_status.get_bit(self.__REG_STATUS_BIT_DATA_AVAIL) \
            #     == 1:
            #     raise RuntimeError('FIFO should be empty')
            return fifo

    def __make_header(self, address: Optional[int], rw: int) -> bytes:
        """
        Internal method to build the transaction header bytes.

        :param address: Slave device address. If None, self.address is used by
            default. If defined, LSB must be 0 (this is the R/W bit).
        :type address: int or None
        :param rw: R/W bit value, 0 or 1.
        :type rw: int
        :return: Header bytearray.
        """
        result = bytearray()
        assert rw in (0, 1)
        # Check that the address is defined in parameters or in self.address.
        if address is None:
            address = self.address
        if address is None:
            raise ValueError("I2C transaction address is not defined")
        # Check address
        if address < 0:
            raise ValueError("I2C address cannot be negative")
        if address >= 2**11:  # R/W bit counted in address, so 11 bits max
            raise ValueError("I2C address is too big")
        if address > 2**8:
            # 10 bits addressing mode
            # R/W bit is bit 8.
            if address & 0x10:
                raise ValueError("I2C address bit 8 (R/W) must be 0")
            result.append(0xF0 + (address >> 8) + rw)
            result.append(address & 0x0F)
        else:
            # 7 bits addressing mode
            # R/W bit is bit 0.
            if address & 1:
                raise ValueError("I2C address LSB (R/W) must be 0")
            result.append(address + rw)
        return result

    def read(
        self,
        size: int,
        address: Optional[int] = None,
        trigger: Optional[Union[bool, int, I2CTrigger]] = None,
    ):
        """
        Perform an I2C read transaction.

        :param address: Slave device address. If None, self.address is used by
            default. If defined and addressing mode is 7 bits, LSB must be 0
            (this is the R/W bit). If defined and addressing mode is 10 bits,
            bit 8 must be 0.
        :type address: int or None
        :param trigger: Trigger configuration. If int and value is 1, trigger
            is asserted when the transaction starts. If str, it may contain the
            letter 'a' and/or 'b', where 'a' asserts trigger on transaction
            start and 'b' on transaction end.
        :type trigger: int, str or `I2CTrigger`.
        :return: Bytes from the slave.
        :raises I2CNackError: If a NACK is received during the transaction.
        """
        data = self.__make_header(address, 1)
        return self.raw_transaction(data, size, trigger)

    def write(
        self,
        data: bytes,
        address: Optional[int] = None,
        trigger: Optional[Union[bool, int, I2CTrigger]] = None,
    ):
        """
        Perform an I2C write transaction.

        :param address: Slave device address. If None, self.address is used by
            default. If defined and addressing mode is 7 bits, LSB must be 0
            (this is the R/W bit). If defined and addressing mode is 10 bits,
            bit 8 must be 0.
        :type address: int or None
        :param trigger: Trigger configuration. If int and value is 1, trigger
            is asserted when the transaction starts. If str, it may contain the
            letter 'a' and/or 'b', where 'a' asserts trigger on transaction
            start and 'b' on transaction end.
        :type trigger: int, str or `I2CTrigger`.
        :raises I2CNackError: If a NACK is received during the transaction.
        """
        data = self.__make_header(address, 0) + data
        self.raw_transaction(data, 0, trigger)

    @property
    def clock_stretching(self):
        """
        Enable or disable clock stretching support. When clock stretching is
        enabled, the I2C slave may hold SCL low during a transaction. In this
        mode, an external pull-up resistor on SCL is required. When clock
        stretching is disabled, SCL is always controlled by the master and the
        pull-up resistor is not required.

        :type: bool or int.
        """
        return self.reg_config.get_bit(self.__REG_CONFIG_BIT_CLOCK_STRETCHING)

    @clock_stretching.setter
    def clock_stretching(self, value: int):
        self.reg_config.set_bit(self.__REG_CONFIG_BIT_CLOCK_STRETCHING, value)

    @property
    def frequency(self):
        """
        Target I2C clock frequency.

        :getter: Returns current frequency.
        :setter: Set target frequency. Effective frequency may be different if
            target cannot be reached accurately.
        """
        return self.__cache_frequency

    @frequency.setter
    def frequency(self, value: float):
        d = round((self.parent.sys_freq / (4 * value)) - 1)
        # Check that the divisor can be stored on 16 bits.
        if d > 0xFFFF:
            raise ValueError("Target frequency is too low.")
        if d < 1:
            raise ValueError("Target frequency is too high.")
        real = self.parent.sys_freq / (d + 1)
        self.reg_divisor.set(d)
        self.__cache_frequency = real


class SPIMode(int, Enum):
    MASTER = 0
    SLAVE = 1


class SPI(Module):
    """
    SPI peripheral of Scaffold.
    """

    __REG_STATUS_BIT_READY = 0
    __REG_CONTROL_BIT_CLEAR = 6
    __REG_CONTROL_BIT_TRIGGER = 7
    __REG_CONFIG_BIT_POLARITY = 0
    __REG_CONFIG_BIT_PHASE = 1
    __REG_CONFIG_BIT_MODE = 2

    def __init__(self, parent: "Scaffold", index: int):
        """
        :param parent: The :class:`Scaffold` instance owning the SPI module.
        :param index: SPI module index.
        """
        super().__init__(parent, f"/spi{index}")
        self.__index = index
        # Declare the signals
        self.miso, self.sck, self.mosi, self.ss, self.trigger = self.add_signals(
            "miso", "sck", "mosi", "ss", "trigger"
        )
        # Declare the registers
        self.__addr_base = base = 0x0800 + 0x0010 * index
        self.reg_status = self.add_register("rv", base)
        self.reg_control = self.add_register("w", base + 1)
        self.reg_config = self.add_register("w", base + 2, reset=0x00)
        self.reg_divisor = self.add_register(
            "w", base + 3, wideness=2, min_value=1, reset=0x1000
        )
        self.reg_data = self.add_register("rwv", base + 4)
        # Current SPI clock frequency
        self.__cache_frequency = None

    @property
    def polarity(self):
        """
        Clock polarity. 0 or 1.
        """
        return self.reg_config.get_bit(self.__REG_CONFIG_BIT_POLARITY)

    @polarity.setter
    def polarity(self, value: int):
        self.reg_config.set_bit(self.__REG_CONFIG_BIT_POLARITY, value)

    @property
    def phase(self):
        """
        Clock phase. 0 or 1.
        """
        return self.reg_config.get_bit(self.__REG_CONFIG_BIT_PHASE)

    @phase.setter
    def phase(self, value: int):
        self.reg_config.set_bit(self.__REG_CONFIG_BIT_PHASE, value)

    @property
    def mode(self) -> SPIMode:
        """SPI mode"""
        assert self.parent.version is not None
        if self.parent.version < parse_version("0.8"):
            return SPIMode.MASTER
        else:
            return SPIMode(self.reg_config.get_bit(self.__REG_CONFIG_BIT_MODE))

    @mode.setter
    def mode(self, value: SPIMode):
        assert self.parent.version is not None
        if self.parent.version < parse_version("0.8"):
            if value != SPIMode.MASTER:
                raise RuntimeError(
                    "Current FPGA confware only supports master mode. "
                    "Slave mode requires confware >= 0.8."
                )
        else:
            self.reg_config.set_bit(self.__REG_CONFIG_BIT_MODE, value)

    @property
    def frequency(self):
        """
        Target SPI clock frequency.

        :getter: Returns current frequency.
        :setter: Set target frequency. Effective frequency may be different if
            target cannot be reached accurately.
        :type: float
        """
        return self.__cache_frequency

    @frequency.setter
    def frequency(self, value: float):
        d = round((self.parent.sys_freq / (4 * value)) - 1)
        # Check that the divisor can be stored on 16 bits.
        if d > 0xFFFF:
            raise ValueError("Target frequency is too low.")
        if d < 1:
            raise ValueError("Target frequency is too high.")
        real = self.parent.sys_freq / (d + 1)
        self.reg_divisor.set(d)
        self.__cache_frequency = real

    def transmit(
        self,
        value: int,
        size: int = 8,
        trigger: Union[int, bool] = False,
        read: bool = True,
    ):
        """
        Performs a SPI transaction to transmit a value and receive data. If a
        transmission is still pending, this methods waits for the SPI
        peripheral to be ready.

        :param value: Value to be transmitted. Less significant bit is
            transmitted last.
        :param size: Number of bits to be transmitted. Minimum is 1, maximum is
            32.
        :param trigger: 1 or True to enable trigger upon SPI transmission.
        :type trigger: bool or int.
        :param read: Set 0 or False to disable received value readout (the
            method will return None). Default is True, but disabling it will
            make this command faster if the returned value can be discarded.
        :return: Received value.
        :rtype: int
        """
        if size not in range(1, 33):
            raise ValueError("Invalid size for SPI transaction")
        if value < 0:
            raise ValueError("value cannot be negative")
        if value >= (2**size):
            raise ValueError("value is too high")
        # The value to be transmitted must be loaded in the transmission
        # shift-register, less significant bit first. The buffer will transmit
        # its size most significant bits.
        pad = size
        while pad % 8 != 0:
            value <<= 1
            pad += 1
        remaining = size
        while remaining > 0:
            self.reg_data.write(value & 0xFF)
            value >>= 8
            remaining -= 8
        # Start transmission
        if trigger:
            trigger = 1
        self.reg_control.write(
            (trigger << self.__REG_CONTROL_BIT_TRIGGER) + (size - 1),
            self.reg_status.poll(
                mask=(1 << self.__REG_STATUS_BIT_READY),
                value=(1 << self.__REG_STATUS_BIT_READY),
            ),
        )
        if read:
            res = self.read_data_buffer((size - 1) // 8 + 1)
            # Mask to discard garbage bits from previous operations
            res &= 2**size - 1
            return res

    def read_data_buffer(self, n: int):
        """
        Read n bytes from the internal data buffer.

        :param n: In [1, 4]
        :type n: int
        :return: int
        """
        # The result bits are pushed from the right into the reception
        # buffer. The reception buffer is read by bytes starting at the
        # less significant byte.
        res = self.reg_data.read(
            n,
            self.reg_status.poll(
                mask=(1 << self.__REG_STATUS_BIT_READY),
                value=(1 << self.__REG_STATUS_BIT_READY),
            ),
        )
        return int.from_bytes(res, "little")

    def append(self, data: Union[int, bytes]):
        """
        Append data to be returned by the peripheral when configured as a
        slave.

        .. warning:: Appended data is stored in an internal FIFO memory of the
            SPI peripheral. Size is limited to 512 bytes, any write beyond that
            limit is discarded without any warning.

        :param data: Byte or bytes to be appended.
        """
        assert self.parent.version is not None
        if self.parent.version < parse_version("0.8"):
            raise RuntimeError("SPI slave support requires FPGA confware >= 0.8")
        if self.mode != SPIMode.SLAVE:
            raise RuntimeError("Select slave mode first to append response data.")
        self.reg_data.write(data)

    def clear(self):
        """
        Clear the FIFO memory of the data to be returned by the peripheral when
        configured as a slave.
        """
        assert self.parent.version is not None
        if self.parent.version < parse_version("0.8"):
            raise RuntimeError("SPI slave support requires FPGA confware >= 0.8")
        self.reg_control.write(1 << self.__REG_CONTROL_BIT_CLEAR)


class Chain(Module):
    """Chain trigger module."""

    __ADDR_CONTROL = 0x0900

    def __init__(self, parent: "Scaffold", index: int, size: int):
        """
        :param parent: The :class:`Scaffold` instance owning the chain module.
        :param index: Chain module index.
        :param size: Number of events in the chain.
        """
        super().__init__(parent, f"/chain{index}")
        self.reg_control = self.add_register("wv", self.__ADDR_CONTROL + index * 0x10)
        self.events = self.add_signals(*[f"event{i}" for i in range(size)])
        # For backward compatibility with scripts accessing
        # events with scaffold.chainX.eventX
        for i, event in enumerate(self.events):
            self.__dict__[f"event{i}"] = event

        self.trigger = self.add_signal("trigger")

    def rearm(self):
        """Reset the chain trigger to initial state."""
        self.reg_control.set(1)


class Clock(Module):
    """
    Clock generator module. This peripheral allows generating a clock derived
    from the FPGA system clock using a clock divisor. A second clock can be
    generated and enabled during a short period of time to override the first
    clock, generating clock glitches.
    """

    __ADDR_CONFIG = 0x0A00
    __ADDR_DIVISOR_A = 0x0A01
    __ADDR_DIVISOR_B = 0x0A02
    __ADDR_COUNT = 0x0A03

    def __init__(self, parent: "Scaffold", index: int):
        """
        :param parent: The :class:`Scaffold` instance owning the clock module.
        :param index: Clock module index.
        """
        super().__init__(parent, f"/clock{index}")
        self.reg_config = self.add_register("w", self.__ADDR_CONFIG + index * 0x10)
        self.reg_divisor_a = self.add_register(
            "w", self.__ADDR_DIVISOR_A + index * 0x10
        )
        self.reg_divisor_b = self.add_register(
            "w", self.__ADDR_DIVISOR_B + index * 0x10
        )
        self.reg_count = self.add_register("w", self.__ADDR_COUNT + index * 0x10)
        self.glitch, self.out = self.add_signals("glitch", "out")

        self.__freq_helper_a = FreqRegisterHelper(
            self.parent.sys_freq, self.reg_divisor_a
        )
        self.__freq_helper_b = FreqRegisterHelper(
            self.parent.sys_freq, self.reg_divisor_b
        )

    @property
    def frequency(self) -> Optional[float]:
        """
        Base clock frequency, in Hertz. Only divisors of the system frequency
        can be set: 50 MHz, 25 MHz, 16.66 MHz, 12.5 MHz...
        If the frequency has not been set previously, this attribute will return
        None.

        :type: float
        """
        return self.__freq_helper_a.get()

    @frequency.setter
    def frequency(self, value: float):
        self.__freq_helper_a.set(value)

    @property
    def glitch_frequency(self):
        """
        Glitch clock frequency, in Hertz. Only divisors of the system frequency
        can be set: 50 MHz, 25 MHz, 16.66 MHz, 12.5 MHz...

        :type: float
        """
        return self.__freq_helper_b.get()

    @glitch_frequency.setter
    def glitch_frequency(self, value: float):
        self.__freq_helper_b.set(value)

    @property
    def div_a(self):
        return self.reg_divisor_a.get()

    @div_a.setter
    def div_a(self, value: int):
        self.reg_divisor_a.set(value)

    @property
    def div_b(self):
        return self.reg_divisor_b.get()

    @div_b.setter
    def div_b(self, value: int):
        self.reg_divisor_b.set(value)

    @property
    def glitch_count(self):
        """
        Number of fast clock edges to be injected when glitching.
        Maximum value is 255.

        :type: int.
        """
        return self.reg_count.get()

    @glitch_count.setter
    def glitch_count(self, value: int):
        self.reg_count.set(value)


class IOMode(int, Enum):
    AUTO = 0
    OPEN_DRAIN = 1
    PUSH_ONLY = 2


class Pull(int, Enum):
    NONE = 0b00
    UP = 0b11
    DOWN = 0b01


class IO(Signal, Module):
    """
    Board I/O.
    """

    def __init__(
        self, parent: "Scaffold", path: str, index: int, pullable: bool = False
    ):
        """
        :param parent: The :class:`Scaffold` instance owning the I/O module.
        :param path: I/O module path.
        :param index: I/O module index.
        :param pullable: True if this I/O supports pull resistor.
        """
        Signal.__init__(self, parent, path)
        Module.__init__(self, parent)
        self.index = index
        self.__pullable = pullable
        if parent.version == parse_version("0.2"):
            # 0.2 only
            # Since I/O will have more options, it is not very convenient to
            # group them anymore.
            self.__group = index // 8
            self.__group_index = index % 8
            base = 0xE000 + 0x10 * self.__group
            self.reg_value = self.add_register("rv", base + 0x00)
            self.reg_event = self.add_register("rwv", base + 0x01, reset=0)
        else:
            # 0.3
            base = 0xE000 + 0x10 * self.index
            self.reg_value = self.add_register("rwv", base + 0x00, reset=0)
            self.reg_config = self.add_register("rw", base + 0x01, reset=0)
            # No more event register in 0.3. Events are in the value register

    @property
    def value(self):
        """
        Current IO logical state.

        :getter: Senses the input pin of the board and return either 0 or 1.
        :setter: Sets the output to 0, 1 or high-impedance state (None). This
            will disconnect the I/O from any already connected internal
            peripheral. Same effect can be achieved using << operator.
        """
        if self.parent.version == parse_version("0.2"):
            return (self.reg_value.get() >> self.__group_index) & 1
        else:
            # 0.3
            return self.reg_value.get_bit(0)

    @property
    def event(self):
        """
        I/O event register.

        :getter: Returns 1 if an event has been detected on this input, 0
            otherwise.
        :setter: Writing 0 to clears the event flag. Writing 1 has no effect.
        """
        if self.parent.version == parse_version("0.2"):
            return (self.reg_event.get() >> self.__group_index) & 1
        else:
            # 0.3
            return self.reg_value.get_bit(1)

    def clear_event(self):
        """
        Clear event register.

        :warning: If an event is received during this call, it may be cleared
            without being took into account.
        """
        if self.parent.version == parse_version("0.2"):
            self.reg_event.set(0xFF ^ (1 << self.__group_index))
        else:
            # 0.3
            self.reg_value.set(0)

    @property
    def mode(self) -> IOMode:
        """
        I/O mode. Default is AUTO, but this can be overriden for special
        applications.

        :type: IOMode
        """
        assert self.parent.version is not None and self.parent.version >= parse_version(
            "0.3"
        )
        return IOMode(self.reg_config.get() & 0b11)

    @mode.setter
    def mode(self, value: IOMode):
        assert self.parent.version is not None and self.parent.version >= parse_version(
            "0.3"
        )
        if not isinstance(value, IOMode):
            raise ValueError("mode must be an instance of IOMode enumeration")
        self.reg_config.set_mask(value, 0b11)

    @property
    def pull(self) -> Pull:
        """
        Pull resistor mode. Can only be written if the I/O supports this
        feature.

        :type: Pull
        """
        assert self.parent.version is not None and self.parent.version >= parse_version(
            "0.3"
        )
        if not self.__pullable:
            return Pull.NONE
        return Pull((self.reg_config.get() >> 2) & 0b11)

    @pull.setter
    def pull(self, value: Optional[Pull]):
        assert self.parent.version is not None and self.parent.version >= parse_version(
            "0.3"
        )
        # Accept None as value
        if value is None:
            value = Pull.NONE
        if (not self.__pullable) and (value != Pull.NONE):
            raise RuntimeError("This I/O does not support pull resistor")
        self.reg_config.set_mask(value << 2, 0b1100)


class IODir(Enum):
    """
    I/O direction mode.
    """

    INPUT = 0
    OUTPUT = 1


class ArchBase:
    """
    Base class for Scaffold API.
    The :class:`Scaffold` class inherits from this class and defines which
    modules and signals are defined on the board. This class can be inherited
    to create other boards than Scaffold sharing the same architecture
    principle.
    """

    __ADDR_MTXR_BASE = 0xF100
    __ADDR_MTXL_BASE = 0xF000

    def __init__(
        self,
        sys_freq: int,
        board_name: str,
        supported_versions: list[PackagingVersion],
        baudrate: int = 2000000,
    ):
        """
        Defines basic parameters of the board.

        :param sys_freq: Architecture system frequency, in Hertz.
        :type sys_freq: int
        :param board_name: Expected board name during version string readout.
        :type board_name: str
        :param supported_versions: A list of supported version.
        :param baudrate: UART baudrate. Default to 2 Mbps. Other hardware
            boards may have different speed.
        :type baudrate: int
        """
        self.sys_freq = sys_freq
        self.__expected_board_name = board_name
        self.__supported_versions = supported_versions

        # Hardware version module. Defined here because it is an architecture
        # requirement. There is no need to expose this module.
        self.__version_module = Version(self)  # type: ignore

        # Cache the version string once read
        self.__version_string: Optional[str] = None
        self.__version: Optional[PackagingVersion] = None
        self.__board_name: Optional[str] = None

        # Low-level management
        # Set as an attribute to avoid having all low level routines visible in
        # the higher API Scaffold class.
        self.bus = ScaffoldBus(self.sys_freq, baudrate)

        # Mux matrices signals
        self.mtxl_in: list[str] = []
        self.mtxl_out: list[str] = []
        self.mtxr_in: list[str] = []
        self.mtxr_out: list[str] = []

    def add_mtxl_in(self, name: str):
        """
        Declares an input for the left interconnect matrix.

        :param name: Input signal name.
        :type name: str.
        """
        self.mtxl_in.append(name)

    def add_mtxl_out(self, name: str):
        """
        Declares an output of the left interconnect matrix.

        :param name: Output signal name.
        :type name: str.
        """
        self.mtxl_out.append(name)

    def add_mtxr_in(self, name: str):
        """
        Declares an input for the right interconnect matrix.

        :param name: Input signal name.
        :type name: str.
        """
        self.mtxr_in.append(name)

    def add_mtxr_out(self, name: str):
        """
        Declares an output of the right interconnect matrix.

        :param name: Input signal name.
        :type name: str.
        """
        self.mtxr_out.append(name)

    @property
    def version(
        self,
    ) -> Optional[PackagingVersion]:
        """
        :return: Hardware version.
        """
        return self.__version

    def connect(self, dev: Optional[str] = None, sn: Optional[str] = None):
        """
        Connect to Scaffold board using the given serial port.

        :param dev: Serial port device path. For instance '/dev/ttyUSB0' on
            linux, 'COM0' on Windows. If None, tries to automatically find the
            board by scanning USB description strings.
        :param sn: If `dev` is not specified, automatic detection must find a
            board with the given serial number. This is an interesting feature
            when multiple Scaffold boards are connected to the same computer.
            Must be `None` when `dev` is set.
        """
        if dev is None:
            # Try to find automatically the device
            possible_ports: list[serial.tools.list_ports_common.ListPortInfo] = []
            for port in serial.tools.list_ports.comports():
                # USB description string can be 'Scaffold', with uppercase 'S'.
                if (
                    (port.product is not None)
                    and (port.product.lower() == self.__expected_board_name)
                    and ((sn is None) or (port.serial_number == sn))
                ):
                    possible_ports.append(port)
            if len(possible_ports) > 1:
                raise RuntimeError(
                    "Multiple "
                    + self.__expected_board_name
                    + " devices found! I don't know which one to use."
                )
            elif len(possible_ports) == 1:
                dev = possible_ports[0].device
            else:
                raise RuntimeError("No " + self.__expected_board_name + " device found")
        else:
            if sn is not None:
                raise ValueError("dev and sn cannot be set together")

        self.bus.connect(dev)
        # Check hardware responds and has the correct version.
        self.__version_string = self.__version_module.get_string()
        # Split board name and version string
        tokens = self.__version_string.split("-")
        if len(tokens) != 2:
            raise RuntimeError(
                "Failed to parse board version string '" + self.__version_string + "'"
            )
        self.__board_name = tokens[0]
        version = parse_version(tokens[1])
        if self.__board_name != self.__expected_board_name:
            raise RuntimeError("Invalid board name during version check")
        if version not in self.__supported_versions:
            raise RuntimeError("Hardware version " + str(version) + " not supported")
        self.__version = version

        # Tell ScaffoldBus the current version. If version is >= 0.9, delays and buffer
        # wait operations will be enabled.
        self.bus.version = self.__version

    def __signal_to_path(self, signal: Optional[Union[int, Signal]]) -> str:
        """
        Convert a signal, 0, 1 or None to a path. Verify the signal belongs to
        the current Scaffold instance.
        :param signal: Signal, 0, 1 or None.
        :return: Path string.
        """
        if isinstance(signal, Signal):
            if signal.parent != self:
                raise ValueError("Signal belongs to another Scaffold instance")
            return signal.path
        elif isinstance(signal, int):
            if signal not in (0, 1):
                raise ValueError("Invalid signal value")
            return str(signal)
        elif signal is None:
            return "z"  # High impedance
        else:
            raise ValueError("Invalid signal type")

    def sig_connect(self, a: Signal, b: Union[int, Signal]):
        """
        Configure interconnect matrices to feed the signal a with the signal b.

        :param a: Destination signal.
        :type a: Signal
        :param b: Source signal.
        :type b: Signal
        """
        # Check both signals belongs to the current board instance
        # Convert signals to path names
        dest_path = self.__signal_to_path(a)
        src_path = self.__signal_to_path(b)

        dest_in_mtxr_out = dest_path in self.mtxr_out
        dest_in_mtxl_out = dest_path in self.mtxl_out
        if not (dest_in_mtxr_out or dest_in_mtxl_out):
            # Shall never happen unless there is a bug
            raise RuntimeError(f"Invalid destination path '{dest_path}'")
        src_in_mtxl_in = src_path in self.mtxl_in
        src_in_mtxr_in = src_path in self.mtxr_in
        # Beware: we can have a dest signal with the same name in mtxr and
        # mtxl.
        if dest_in_mtxr_out and src_in_mtxr_in:
            if dest_in_mtxl_out and src_in_mtxl_in:
                # Shall never happen unless a module output has the same name
                # as one of its input.
                raise RuntimeError(
                    f"Connection ambiguity '{dest_path}' << " + f"'{src_path}'."
                )
            # Connect a module output to an IO output
            src_index = self.mtxr_in.index(src_path)
            dst_index = self.mtxr_out.index(dest_path)
            self.bus.write(self.__ADDR_MTXR_BASE + dst_index, src_index)
        elif dest_in_mtxl_out and src_in_mtxl_in:
            # Connect a module input to an IO input (or 0 or 1).
            src_index = self.mtxl_in.index(src_path)
            dst_index = self.mtxl_out.index(dest_path)
            self.bus.write(self.__ADDR_MTXL_BASE + dst_index, src_index)
        else:
            # Shall never happen unless there is a bug
            raise RuntimeError(
                f"Failed to connect '{dest_path}' << " + f"'{src_path}'."
            )

    def sig_disconnect_all(self):
        """
        Disconnects all input and output signals. This is called during
        initialization to reset the board in a known state.
        """
        for i in range(len(self.mtxl_out)):
            self.bus.write(self.__ADDR_MTXL_BASE + i, 0)
        for i in range(len(self.mtxr_out)):
            self.bus.write(self.__ADDR_MTXR_BASE + i, 0)

    @property
    def timeout(self):
        """
        Timeout in seconds for read and write commands. If set to 0, timeout is
        disabled.
        """
        return self.bus.timeout

    @timeout.setter
    def timeout(self, value: Optional[float]):
        self.bus.timeout = value

    def push_timeout(self, value: float):
        """
        Save previous timeout setting in a stack, and set a new timeout value.
        Call to `pop_timeout` will restore previous timeout value.

        :param value: New timeout value, in seconds.
        """
        self.bus.push_timeout(value)

    def pop_timeout(self):
        """
        Restore timeout setting from stack.

        :raises RuntimeError: if timeout stack is already empty.
        """
        self.bus.pop_timeout()

    def timeout_section(self, timeout: Optional[float]):
        """
        :return: :class:`ScaffoldBusTimeoutSection` instance to be used with
            the python 'with' statement to push and pop timeout configuration.
        """
        return self.bus.timeout_section(timeout)

    def buffer_wait_section(self):
        return self.bus.buffer_wait_section()

    def delay(self, duration: float):
        """
        Performs a delay operation.

        :param cycles: Delay duration in seconds.
        """
        cycles = round(duration * self.sys_freq)
        self.bus.delay(cycles)

    def wait(self):
        """Wait for all pending operations to be completed."""
        self.bus.wait()


class Scaffold(ArchBase):
    """
    This class connects to a Scaffold board and provides access to all the
    device parameters and peripherals.

    :ivar uarts: list of :class:`scaffold.UART` instance managing UART
        peripherals.
    :ivar i2cs: list of :class:`scaffold.I2C` instance managing I2C
        peripherals.
    :ivar iso7816: :class:`scaffold.ISO7816` instance managing the ISO7816
        peripheral.
    :ivar pgens: list of four :class:`scaffold.PulseGenerator` instance
        managing the FPGA pulse generators.
    :ivar power: :class:`scaffold.Power` instance, enabling control of the
        power supplies of DUT and platform sockets.
    :ivar leds: :class:`scaffold.LEDs` instance, managing LEDs brightness and
        lighting mode.
    :ivar [a0,a1,a2,a3,b0,b1,c0,c1,d0,d1,d2,d3,d4,d5]: :class:`scaffold.Signal`
        instances for connecting and controlling the corresponding I/Os of the
        board.
    """

    # Number of I/Os
    __IO_D_COUNT = 16
    __IO_P_COUNT = 16

    def __init__(
        self,
        dev: Optional[str] = None,
        init_ios: bool = False,
        sn: Optional[str] = None,
    ):
        """
        Create Scaffold API instance.

        :param dev: If specified, connect to the hardware Scaffold board using
            the given serial device. If None, tries to find automatically the
            device by scanning USB description strings.
        :param init_ios: True to enable I/Os peripherals initialization. Doing
            so will set all I/Os to a default state, but it may generate pulses
            on the I/Os. When set to False, I/Os connections are unchanged
            during initialization and keep the configuration set by previous
            sessions.
        :param sn: If `dev` is not specified, automatic detection must find a
            board with the given serial number. This is an interesting feature
            when multiple Scaffold boards are connected to the same computer.
        """
        super().__init__(
            int(100e6),  # System frequency: 100 MHz
            "scaffold",  # board name
            # Supported FPGA bitstream versions
            [
                PackagingVersion(v)
                for v in (
                    "0.2",
                    "0.3",
                    "0.4",
                    "0.5",
                    "0.6",
                    "0.7",
                    "0.7.1",
                    "0.7.2",
                    "0.8",
                    "0.9",
                )
            ],
        )
        self.connect(dev, sn, init_ios)

    def connect(
        self,
        dev: Optional[str] = None,
        sn: Optional[str] = None,
        init_ios: bool = False,
    ):
        """
        Connect to Scaffold board using the given serial port.

        :param dev: Serial port device path. For instance '/dev/ttyUSB0' on
            linux, 'COM0' on Windows.
        :param init_ios: True to enable I/Os peripherals initialization. Doing
            so will set all I/Os to a default state, but it may generate pulses
            on the I/Os. When set to False, I/Os connections are unchanged
            during initialization and keep the configuration set by previous
            sessions.
        :param sn: If `dev` is not specified, automatic detection must find a
            board with the given serial number. This is an interesting feature
            when multiple Scaffold boards are connected to the same computer.
        """
        super().connect(dev, sn=sn)

        # After a successful connection, the version should not be None
        assert self.version is not None

        # Power module
        self.power = Power(self)
        # Leds module
        self.leds = LEDs(self)

        # Create the IO signals
        # Scaffold hardware v1 has FPGA arch version <= 0.3
        # Scaffold hardware v1.1 has FPGA arch version >= 0.4
        # The I/Os have changed between both versions.
        self.a0 = IO(self, "/io/a0", 0)
        self.a1 = IO(self, "/io/a1", 1)
        if self.version <= parse_version("0.3"):
            self.b0 = IO(self, "/io/b0", 2)
            self.b1 = IO(self, "/io/b1", 3)
            self.c0 = IO(self, "/io/c0", 4)
            self.c1 = IO(self, "/io/c1", 5)
            offset = 6
            self.d0 = IO(self, "/io/d0", 0 + offset)
            self.d1 = IO(self, "/io/d1", 1 + offset)
            self.d2 = IO(self, "/io/d2", 2 + offset)
            self.d3 = IO(self, "/io/d3", 3 + offset)
            self.d4 = IO(self, "/io/d4", 4 + offset)
            self.d5 = IO(self, "/io/d5", 5 + offset)
            self.d6 = IO(self, "/io/d6", 6 + offset)
            self.d7 = IO(self, "/io/d7", 7 + offset)
            self.d8 = IO(self, "/io/d8", 8 + offset)
            self.d9 = IO(self, "/io/d9", 9 + offset)
            self.d10 = IO(self, "/io/d10", 10 + offset)
            self.d11 = IO(self, "/io/d11", 11 + offset)
            self.d12 = IO(self, "/io/d12", 12 + offset)
            self.d13 = IO(self, "/io/d13", 13 + offset)
            self.d14 = IO(self, "/io/d14", 14 + offset)
            self.d15 = IO(self, "/io/d15", 15 + offset)
            self.d16 = IO(self, "/io/d16", 16 + offset)
        else:
            self.a2 = IO(self, "/io/a2", 2)
            self.a3 = IO(self, "/io/a3", 3)
            offset = 4
            # Only D0, D1 and D2 can be pulled in Scaffold hardware v1.1.
            self.d0 = IO(self, "/io/d0", 0 + offset, pullable=True)
            self.d1 = IO(self, "/io/d1", 1 + offset, pullable=True)
            self.d2 = IO(self, "/io/d2", 2 + offset, pullable=True)
            self.d3 = IO(self, "/io/d3", 3 + offset)
            self.d4 = IO(self, "/io/d4", 4 + offset)
            self.d5 = IO(self, "/io/d5", 5 + offset)
            self.d6 = IO(self, "/io/d6", 6 + offset)
            self.d7 = IO(self, "/io/d7", 7 + offset)
            self.d8 = IO(self, "/io/d8", 8 + offset)
            self.d9 = IO(self, "/io/d9", 9 + offset)
            self.d10 = IO(self, "/io/d10", 10 + offset)
            self.d11 = IO(self, "/io/d11", 11 + offset)
            self.d12 = IO(self, "/io/d12", 12 + offset)
            self.d13 = IO(self, "/io/d13", 13 + offset)
            self.d14 = IO(self, "/io/d14", 14 + offset)
            self.d15 = IO(self, "/io/d15", 15 + offset)
            self.d16 = IO(self, "/io/d16", 16 + offset)
            if self.version >= parse_version("0.6"):
                offset = 4 + self.__IO_D_COUNT
                self.p0 = IO(self, "/io/p0", 0 + offset)
                self.p1 = IO(self, "/io/p1", 1 + offset)
                self.p2 = IO(self, "/io/p2", 2 + offset)
                self.p3 = IO(self, "/io/p3", 3 + offset)
                self.p4 = IO(self, "/io/p4", 4 + offset)
                self.p5 = IO(self, "/io/p5", 5 + offset)
                self.p6 = IO(self, "/io/p6", 6 + offset)
                self.p7 = IO(self, "/io/p7", 7 + offset)
                self.p8 = IO(self, "/io/p8", 8 + offset)
                self.p9 = IO(self, "/io/p9", 9 + offset)
                self.p10 = IO(self, "/io/p10", 10 + offset)
                self.p11 = IO(self, "/io/p11", 11 + offset)
                self.p12 = IO(self, "/io/p12", 12 + offset)
                self.p13 = IO(self, "/io/p13", 13 + offset)
                self.p14 = IO(self, "/io/p14", 14 + offset)
                self.p15 = IO(self, "/io/p15", 15 + offset)
                self.p16 = IO(self, "/io/p16", 16 + offset)

        # Create the UART modules
        self.uart0 = UART(self, 0)
        self.uart1 = UART(self, 1)
        self.uarts = [self.uart0, self.uart1]

        # Create the pulse generator modules
        self.pgen0 = PulseGenerator(self, 0, 0x0300 + 0x10 * 0)
        self.pgen1 = PulseGenerator(self, 1, 0x0300 + 0x10 * 1)
        self.pgen2 = PulseGenerator(self, 2, 0x0300 + 0x10 * 2)
        self.pgen3 = PulseGenerator(self, 3, 0x0300 + 0x10 * 3)
        self.pgens = [self.pgen0, self.pgen1, self.pgen2, self.pgen3]

        # Declare the I2C peripherals
        self.i2c0 = I2C(self, 0)
        self.i2cs = [self.i2c0]

        # Declare the SPI peripherals
        self.spis: list[SPI] = []
        if self.version >= parse_version("0.7"):
            self.spi0 = SPI(self, 0)
            self.spis = [self.spi0]

        # Declare the trigger chain modules
        self.chains: list[Chain] = []
        if self.version >= parse_version("0.7"):
            self.chain0 = Chain(self, 0, 3)
            self.chain1 = Chain(self, 1, 3)
            self.chains = [self.chain0, self.chain1]

        # Declare clock generation module
        self.clocks: list[Clock] = []
        if self.version >= parse_version("0.7"):
            self.clock0 = Clock(self, 0)
            self.clocks = [self.clock0]

        # Create the ISO7816 module
        self.iso7816 = ISO7816(self)

        # FPGA left matrix input signals
        self.add_mtxl_in("0")
        self.add_mtxl_in("1")
        self.add_mtxl_in("/io/a0")
        self.add_mtxl_in("/io/a1")
        if self.version <= parse_version("0.3"):
            # Scaffold hardware v1 only
            self.add_mtxl_in("/io/b0")
            self.add_mtxl_in("/io/b1")
            self.add_mtxl_in("/io/c0")
            self.add_mtxl_in("/io/c1")
        else:
            # Scaffold hardware v1.1
            self.add_mtxl_in("/io/a2")
            self.add_mtxl_in("/io/a3")
        for i in range(self.__IO_D_COUNT):
            self.add_mtxl_in(f"/io/d{i}")
        if self.version >= parse_version("0.6"):
            for i in range(self.__IO_P_COUNT):
                self.add_mtxl_in(f"/io/p{i}")
        if self.version >= parse_version("0.7"):
            # Feeback signals from module outputs (mostly triggers)
            for i in range(len(self.uarts)):
                self.add_mtxl_in(f"/uart{i}/trigger")
            self.add_mtxl_in("/iso7816/trigger")
            for i in range(len(self.i2cs)):
                self.add_mtxl_in(f"/i2c{i}/trigger")
            for i in range(len(self.spis)):
                self.add_mtxl_in(f"/spi{i}/trigger")
            for i in range(len(self.pgens)):
                self.add_mtxl_in(f"/pgen{i}/out")
            for i in range(len(self.chains)):
                self.add_mtxl_in(f"/chain{i}/trigger")

        # FPGA left matrix output signals
        # Update this section when adding new modules with inputs
        for i in range(len(self.uarts)):
            self.add_mtxl_out(f"/uart{i}/rx")
        self.add_mtxl_out("/iso7816/io_in")
        for i in range(len(self.pgens)):
            self.add_mtxl_out(f"/pgen{i}/start")
        for i in range(len(self.i2cs)):
            self.add_mtxl_out(f"/i2c{i}/sda_in")
            self.add_mtxl_out(f"/i2c{i}/scl_in")
        for i in range(len(self.spis)):
            self.add_mtxl_out(f"/spi{i}/miso")
        for i in range(len(self.spis)):
            self.add_mtxl_out(f"/spi{i}/sck")
            self.add_mtxl_out(f"/spi{i}/ss")
        for i in range(len(self.chains)):
            for j in range(3):  # 3 is the number of chain events
                self.add_mtxl_out(f"/chain{i}/event{j}")
        for i in range(len(self.clocks)):
            self.add_mtxl_out(f"/clock{i}/glitch")

        # FPGA right matrix input signals
        # Update this section when adding new modules with outpus
        self.add_mtxr_in("z")
        self.add_mtxr_in("0")
        self.add_mtxr_in("1")
        self.add_mtxr_in("/power/dut_trigger")
        self.add_mtxr_in("/power/platform_trigger")
        for i in range(len(self.uarts)):
            self.add_mtxr_in(f"/uart{i}/tx")
            self.add_mtxr_in(f"/uart{i}/trigger")
        self.add_mtxr_in("/iso7816/io_out")
        self.add_mtxr_in("/iso7816/clk")
        self.add_mtxr_in("/iso7816/trigger")
        for i in range(len(self.pgens)):
            self.add_mtxr_in(f"/pgen{i}/out")
        for i in range(len(self.i2cs)):
            self.add_mtxr_in(f"/i2c{i}/sda_out")
            self.add_mtxr_in(f"/i2c{i}/scl_out")
            self.add_mtxr_in(f"/i2c{i}/trigger")
        for i in range(len(self.spis)):
            self.add_mtxr_in(f"/spi{i}/sck")
            self.add_mtxr_in(f"/spi{i}/mosi")
            self.add_mtxr_in(f"/spi{i}/ss")
            self.add_mtxr_in(f"/spi{i}/trigger")
        for i in range(len(self.spis)):
            self.add_mtxr_in(f"/spi{i}/miso")
        for i in range(len(self.chains)):
            self.add_mtxr_in(f"/chain{i}/trigger")
        for i in range(len(self.clocks)):
            self.add_mtxr_in(f"/clock{i}/out")

        # FPGA right matrix output signals
        self.add_mtxr_out("/io/a0")
        self.add_mtxr_out("/io/a1")
        if self.version <= parse_version("0.3"):
            # Scaffold hardware v1 only
            self.add_mtxr_out("/io/b0")
            self.add_mtxr_out("/io/b1")
            self.add_mtxr_out("/io/c0")
            self.add_mtxr_out("/io/c1")
        else:
            # Scaffold hardware v1.1
            self.add_mtxr_out("/io/a2")
            self.add_mtxr_out("/io/a3")
        for i in range(self.__IO_D_COUNT):
            self.add_mtxr_out(f"/io/d{i}")
        if self.version >= parse_version("0.6"):
            for i in range(self.__IO_P_COUNT):
                self.add_mtxr_out(f"/io/p{i}")

        self.reset_config(init_ios=init_ios)

    def reset_config(self, init_ios: bool = False):
        """
        Reset the board to a default state.
        :param init_ios: True to enable I/Os peripherals initialization. Doing
            so will set all I/Os to a default state, but it may generate pulses
            on the I/Os. When set to False, I/Os connections are unchanged
            during initialization and keep the configuration set by previous
            sessions.
        """
        assert self.version is not None

        # Reset to a default configuration
        self.timeout = None
        # Sometime we don't want the I/Os to be changed, since it may
        # generate pulses and triggering stuff... Reseting the I/Os is an
        # option.
        if init_ios:
            self.sig_disconnect_all()
            self.a0.reset_registers()
            self.a1.reset_registers()
            if self.version <= parse_version("0.3"):
                # Scaffold hardware v1 only
                self.b0.reset_registers()
                self.b1.reset_registers()
                self.c0.reset_registers()
                self.c1.reset_registers()
            else:
                # Scaffold hardware v1.1
                self.a2.reset_registers()
                self.a3.reset_registers()
            for i in range(self.__IO_D_COUNT):
                self.__getattribute__(f"d{i}").reset_registers()
            if self.version >= parse_version("0.6"):
                for i in range(self.__IO_P_COUNT):
                    self.__getattribute__(f"p{i}").reset_registers()
        for uart in self.uarts:
            uart.reset()
        for pgen in self.pgens:
            pgen.reset_registers()
        self.leds.reset()
        self.iso7816.reset_config()
        for i2c in self.i2cs:
            i2c.reset_config()
        for spi in self.spis:
            spi.reset_registers()
