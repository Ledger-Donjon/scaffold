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


from enum import Enum
import serial
from time import sleep
import serial.tools.list_ports
from typing import Optional


class TimeoutError(Exception):
    """ Thrown when a polling read or write command timed out. """
    def __init__(self, data=None, size=None, expected=None):
        """
        :param data: The received data until timeout. None if timeout occured
        during a write operation.
        :param size: The number of successfully proceeded bytes.
        :param expected: The expected number of bytes to be proceeded.
        """
        self.data = data
        self.expected = expected
        if self.data is not None:
            assert size is None
            self.size = len(data)
        else:
            self.size = size

    def __str__(self):
        if self.data is not None:
            if len(self.data):
                h = self.data.hex()
                return (
                    f'Read timeout: partially received {len(self.data)} '
                    f'bytes {h}.')
            else:
                return 'Read timeout: no data received.'
        else:
            return (
                f'Write timeout. Only {self.size}/{self.expected} bytes '
                'written.')


class Signal:
    """
    Base class for all connectable signals in Scaffold. Every :class:`Signal`
    instance has a Scaffold board parent instance which is used to electrically
    configure the hardware board when two :class:`Signal` are connected
    together.
    """
    def __init__(self, parent, path):
        """
        :param parent: Scaffold instance which the signal belongs to.
        :param path: Signal path string. Uniquely identifies a Scaffold board
            internal signal. For instance '/dev/uart0/tx'.
        """
        self.__parent = parent
        self.__path = path

    @property
    def parent(self):
        """ Parent :class:`Scaffold` board instance. Read-only. """
        return self.__parent

    @property
    def path(self):
        """ Signal path. For instance '/dev/uart0/tx'. Read-only. """
        return self.__path

    @property
    def name(self):
        """
        Signal name (last element of the path). For instance 'tx'. Read-only.
        """
        return self.__path.split('/')[-1]

    def __str__(self):
        """ :return: Signal path. For instance '/dev/uart0/tx'. """
        return self.__path

    def __lshift__(self, other):
        """
        Feed the current signal with another signal.

        :param other: Another :class:`Signal` instance. The other signal must
            belong to the same :class:`Scaffold` instance.
        """
        self.__parent.sig_connect(self, other)

    def __rshift__(self, other):
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
    def __init__(self, parent, path=None):
        """
        :param parent: The Scaffold instance owning the object.
        :param path: Base path for the signals. For instance '/uart'.
        """
        self.__parent = parent
        self.__path = path
        self.__registers = []

    def add_signal(self, name):
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
            path = '/' + name
        else:
            path = self.__path + '/' + name
        sig = Signal(self.__parent, path)
        self.__dict__[name] = sig
        return sig

    def add_signals(self, *names):
        """
        Add many signals to the object and set them as new attributes of the
        instance.

        :param names: Name of the signals.
        :type names: Iterable(str)
        :return: List of created signals
        :rtype: List(Signal)
        """
        return list(self.add_signal(name) for name in names)

    def add_register(self, name, *args, **kwargs):
        """
        Create a new register.
        :param name: Register name.
        :param args: Arguments passed to Register.__init__.
        :param kwargs: Keyword arguments passed to Register.__init__.
        """
        attr_name = 'reg_' + name
        reg = Register(self.__parent, *args, **kwargs)
        self.__dict__[attr_name] = reg
        # Keep track of the register for reset_registers method
        self.__registers.append(reg)

    def __setattr__(self, key, value):
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
    def parent(self):
        """ Scaffold instance the module belongs to. Read-only. """
        return self.__parent


class Register:
    """
    Manages accesses to a register of a module. Implements value cache
    mechanism whenever possible.
    """
    def __init__(
            self, parent, mode, address, wideness=1, min_value=None,
            max_value=None, reset=None):
        """
        :param parent: The Scaffold instance owning the register.
        :param address: 16-bits address of the register.
        :param mode: Access mode string. Can have the following characters: 'r'
            for read, 'w' for write, 'v' to indicate the register is volatile.
            When the register is not volatile, a cache is used for read
            accesses.
        :param wideness: Number of bytes stored by the register. When this
            value is not 1, the register cannot be read.
        :parma min_value: Minimum allowed value. If None, minimum value will be
            0 by default.
        :param max_value: Maximum allowed value. If None, maximum value will be
            2^(wideness*8)-1 by default.
        :param reset: Value to be set to the register when :meth:`reset` is
            called. If None, :meth:`reset` has no effect.
        """
        self.__parent = parent

        if address not in range(0x10000):
            raise ValueError('Invalid register address')
        self.__address = address

        self.__w = 'w' in mode
        self.__r = 'r' in mode
        self.__volatile = 'v' in mode

        if wideness < 1:
            raise ValueError('Invalid wideness')
        if (wideness > 1) and self.__r:
            raise ValueError('Wideness must be 1 if register can be read.')
        self.__wideness = wideness

        if min_value is None:
            # Set default minimum value to 0.
            self.__min_value = 0
        else:
            # Check maximum value.
            if min_value not in range(2**(wideness*8)):
                raise ValueError('Invalid register minimum value')
            self.__min_value = min_value

        if max_value is None:
            # Set default maximum value based on register size.
            self.__max_value = 2**(wideness*8) - 1
        else:
            # Check maximum value.
            if max_value not in range(2**(wideness*8)):
                raise ValueError('Invalid register maximum value')
            self.__max_value = max_value

        if self.__min_value > self.__max_value:
            raise ValueError(
                'Register minimum value must be lower or equal to maximum '
                'value')

        self.__reset = reset
        self.__cache = None

    def set(self, value, poll=None, poll_mask=0xff, poll_value=0x00):
        """
        Set a new value to the register. This method will check bounds against
        the minimum and maximum allowed values of the register. If polling is
        enabled and the register is wide, polling is applied for each byte of
        the register.

        :param value: New value.
        :param poll: Register instance or address. None if polling is not
            required.
        :param poll_mask: Register polling mask.
        :param poll_value: Register polling value.
        """
        if value < self.__min_value:
            raise ValueError('Value too low')
        if value > self.__max_value:
            raise ValueError('Value too high')
        if not self.__w:
            raise RuntimeError('Register cannot be written')
        # Handle wideness
        value_bytes = value.to_bytes(self.__wideness, 'big', signed=False)
        self.__parent.bus.write(
            self.__address, value_bytes, poll, poll_mask, poll_value)
        # Save as int
        self.__cache = value

    def get(self):
        """
        :return: Current register value.
        If the register is not volatile and the value has been cached, no
        access to the board is performed and the cache is returned. If the
        register is not volatile but can't be read, the cached value is
        returned or an exception is raised if cache is not set.
        """
        if self.__volatile:
            if not self.__r:
                raise RuntimeError('Register cannot be read')
            return self.__parent.bus.read(self.__address)[0]
        else:
            # Register is not volatile, so its data can be cached.
            if self.__cache is None:
                if self.__r:
                    value = self.__parent.bus.read(self.__address)[0]
                    self.__cache = value
                else:
                    raise RuntimeError('Register cannot be read')
            return self.__cache

    def or_set(self, value):
        """
        Sets some bits to 1 in the register.
        :param value: An int.
        """
        self.set(self.get() | value)

    def set_bit(
            self, index, value, poll=None, poll_mask=0xff, poll_value=0x00):
        """
        Sets the value of a single bit of the register.
        :param index: Bit index, in [0, 7].
        :param value: True, False, 0 or 1.
        :param poll: Register instance or address. None if polling is not
            required.
        :param poll_mask: Register polling mask.
        :param poll_value: Register polling value.
        """
        self.set(
            (self.get() & ~(1 << index)) | (int(bool(value)) << index),
            poll, poll_mask, poll_value)

    def get_bit(self, index):
        """
        :return: Value of a given bit, 0 or 1.
        :param index: Bit index, in [0, 7].
        """
        return (self.get() >> index) & 1

    def set_mask(
            self, value, mask, poll=None, poll_mask=0xff, poll_value=0x00):
        """
        Set selected bits value.
        :param value: Bits value.
        :param mask: A mask indicating which bits must be sets.
        :param poll: Register instance or address. None if polling is not
            required.
        :param poll_mask: Register polling mask.
        :param poll_value: Register polling value.
        """
        # TODO: raise an exception is the register is declared as volatile ?
        current = self.get()
        self.set(
            (current & (~mask)) | (value & mask), poll, poll_mask, poll_value)

    def write(self, data, poll=None, poll_mask=0xff, poll_value=0x00):
        """
        Raw write in the register. This method raises a RuntimeError if the
        register cannot be written.
        :param data: Data to be written. Can be a byte, bytes or bytearray.
        :param poll: Register instance or address. None if polling is not
            required.
        :param poll_mask: Register polling mask.
        :param poll_value: Register polling value.
        """
        if not self.__w:
            raise RuntimeError('Register cannot be written')
        self.__parent.bus.write(
            self.__address, data, poll, poll_mask, poll_value)

    def read(self, size=1, poll=None, poll_mask=0xff, poll_value=0x00):
        """
        Raw read the register. This method raises a RuntimeError if the
        register cannot be read.
        :param poll: Register instance or address. None if polling is not
            required.
        :param poll_mask: Register polling mask.
        :param poll_value: Register polling value.
        :return: bytearray
        """
        if not self.__r:
            raise RuntimeError('Register cannot be read')
        return self.__parent.bus.read(
            self.__address, size, poll, poll_mask, poll_value)

    def reset(self):
        """
        Set the register value to its default value. If no default value has
        been defined, this method has no effect.
        """
        if self.__reset is not None:
            self.set(self.__reset)

    @property
    def address(self):
        """ :return: Register address. """
        return self.__address

    @property
    def max(self):
        """
        Maximum possible value for the register.
        :type: int
        """
        return self.__max_value

    @property
    def min(self):
        """
        Minimum possible value for the register.
        :type: int
        """
        return self.__min_value


class FreqRegisterHelper:
    """
    Helper to provide frequency attributes which compute clock divisor
    registers value based on asked target frequencies.
    """
    def __init__(self, sys_freq, reg):
        """
        :param sys_freq: System base frequency used to compute clock divisors.
        :type sys_freq: int
        :param reg: Register to be configured.
        :type reg: :class:`scaffold.Register`
        """
        self.__sys_freq = sys_freq
        self.__reg = reg
        self.__cache = None
        self.__max_err = 0.01

    def set(self, value):
        """
        Configure the register value depending on the target frequency.

        :param value: Target frequency, in Hertz.
        :type value: float
        """
        d = round((0.5 * self.__sys_freq / value) - 1)
        # Check that the divisor fits in the register
        if d > self.__reg.max:
            raise ValueError('Target clock frequency is too low.')
        if d < self.__reg.min:
            raise ValueError('Target clock frequency is too high.')
        # Calculate error between target and effective clock frequency
        real = self.__sys_freq / ((d + 1) * 2)
        err = abs(real - value) / value
        if err > self.__max_err:
            raise RuntimeError(
                f'Cannot reach target clock frequency within '
                f'{self.__max_err*100}% accuracy.')
        self.__reg.set(d)
        self.__cache = real

    def get(self):
        """
        :return: Actual clock frequency. None if frequency has not been set.
        """
        return self.__cache


class Version(Module):
    """ Version module of Scaffold. """
    def __init__(self, parent):
        """
        :param parent: The Scaffold instance owning the version module.
        """
        super().__init__(parent)
        self.add_register('data', 'r', 0x0100)

    def get_string(self):
        """
        Read the data register multiple times until the full version string has
        been retrieved.
        :return: Hardware version string.
        """
        # We consider the version string is not longer than 32 bytes. This
        # allows us reading the string with only one command to be faster.
        buf = self.reg_data.read(32 + 1 + 32 + 1)
        offset = 0
        result = ''
        # Find the first \0 character.
        while buf[offset] != 0:
            offset += 1
        offset += 1
        # Read characters until second \0 character.
        while buf[offset] != 0:
            result += chr(buf[offset])
            offset += 1
        return result


class LEDMode(Enum):
    EVENT = 0
    VALUE = 1


class LED:
    """
    Represents a LED of the board.
    Each instance of this class is an attribute of a :class:`LEDs` instance.
    """
    def __init__(self, parent, index):
        """
        :param parent: Parent LEDs module instance.
        :param index: Bit index of the LED.
        """
        self.__parent = parent
        self.__index = index

    @property
    def mode(self):
        """
        LED lighting mode. When mode is EVENT, the led is lit for a short
        period of time when an edge is detected on the monitored signal. When
        the mode is VALUE, the LED is lit when the monitored signal is high.
        Default mode is EVENT.

        :type: LEDMode.
        """
        return LEDMode((self.__parent.reg_mode.get() >> self.__index) & 1)

    @mode.setter
    def mode(self, value):
        self.__parent.reg_mode.set_mask(
            LEDMode(value).value << self.__index, 1 << self.__index)


class LEDs(Module):
    """ LEDs module of Scaffold. """
    def __init__(self, parent):
        """
        :param parent: The Scaffold instance owning the version module.
        """
        super().__init__(parent)
        self.add_register('control', 'w', 0x0200)
        self.add_register('brightness', 'w', 0x0201)
        self.add_register('leds_0', 'w', 0x0202)
        self.add_register('leds_1', 'w', 0x0203)
        self.add_register('leds_2', 'w', 0x0204)
        self.add_register('mode', 'w', 0x0205, wideness=3)
        if self.parent.version <= '0.3':
            # Scaffold hardware v1 only
            leds = [
                'a0', 'a1', 'b0', 'b1', 'c0', 'c1', 'd0', 'd1', 'd2', 'd3',
                'd4', 'd5']
            offset = 6
        else:
            # Scaffold hardware v1.1
            leds = [
                'a0', 'a1', 'a2', 'a3', 'd0', 'd1', 'd2', 'd3', 'd4', 'd5']
            offset = 8
        for i, name in enumerate(leds):
            self.__setattr__(name, LED(self, i + offset))

    def reset(self):
        """ Set module registers to default values. """
        self.reg_control = 0
        self.reg_brightness.set(20)
        self.reg_mode.set(0)

    @property
    def brightness(self):
        """
        LEDs brightness. 0 is the minimum. 1 is the maximum.

        :type: float
        """
        return self.reg_brightness.get() / 127.0

    @brightness.setter
    def brightness(self, value):
        if (value < 0) or (value > 1):
            raise ValueError('Invalid brightness value')
        self.reg_brightness.set(int(value * 127))

    @property
    def disabled(self):
        """ If set to True, LEDs driver outputs are all disabled. """
        return bool(self.reg_control.get() & 1)

    @disabled.setter
    def disabled(self, value):
        value = int(bool(value))
        self.reg_control.set_mask(value, 1)

    @property
    def override(self):
        """
        If set to True, LEDs state is the value of the leds_n registers.
        """
        return bool(self.reg_control.get() & 2)

    @override.setter
    def override(self, value):
        value = int(bool(value))
        self.reg_control.set_mask(value << 1, 2)


class UARTParity(Enum):
    """ Possible parity modes for UART peripherals. """
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

    def __init__(self, parent, index):
        """
        :param parent: The Scaffold instance owning the UART module.
        :param index: UART module index.
        """
        super().__init__(parent, f'/uart{index}')
        self.__index = index
        # Declare the signals
        self.add_signals('rx', 'tx', 'trigger')
        # Declare the registers
        self.__addr_base = base = 0x0400 + 0x0010 * index
        self.add_register('status', 'rv', base)
        self.add_register('control', 'w', base + 1)
        self.add_register('config', 'w', base + 2)
        self.add_register('divisor', 'w', base + 3, wideness=2, min_value=1)
        self.add_register('data', 'rwv', base + 4)
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
    def baudrate(self):
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
    def baudrate(self, value):
        """
        Set target baudrate. If baudrate is too low or too high, a ValueError
        is thrown. If baudrate cannot be reached within 1% accuracy, a
        RuntimeError is thrown.
        :param value: New target baudrate.
        """
        d = round((self.parent.sys_freq / value) - 1)
        # Check that the divisor can be stored on 16 bits.
        if d > 0xffff:
            raise ValueError('Target baudrate is too low.')
        if d < 1:
            raise ValueError('Target baudrate is too high.')
        # Calculate error between target and effective baudrates
        real = self.parent.sys_freq / (d + 1)
        err = abs(real - value) / value
        max_err = self.max_err
        if err > max_err:
            raise RuntimeError(
                f'Cannot reach target baudrate within {max_err*100}% '
                'accuracy.')
        self.reg_divisor.set(d)
        self.__cache_baudrate = real

    def transmit(self, data: bytes, trigger: bool = False):
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
        with self.parent.lazy_section():
            self.reg_data.write(
                buf, poll=self.reg_status, poll_mask=0x01, poll_value=0x01)
            if trigger:
                config = self.reg_config.get()
                # Enable trigger as soon as previous transmission ends
                self.reg_config.write(
                    config | (1 << self.__REG_CONFIG_BIT_TRIGGER),
                    poll=self.reg_status, poll_mask=0x01, poll_value=0x01)
                # Send the last byte. No need for polling here, because it has
                # already been done when enabling trigger.
                self.reg_data.write(data[-1])
                # Disable trigger
                self.reg_config.write(
                    config, poll=self.reg_status, poll_mask=0x01,
                    poll_value=0x01)

    def receive(self, n=1):
        """
        Receive n bytes from the UART. This function blocks until all bytes
        have been received or the timeout expires and a TimeoutError is thrown.
        """
        return self.reg_data.read(
            n, poll=self.reg_status, poll_mask=0x04, poll_value=0x00)

    def flush(self):
        """ Discard all the received bytes in the FIFO. """
        self.reg_control.set_bit(self.__REG_CONTROL_BIT_FLUSH, 1)

    @property
    def parity(self):
        """
        Parity mode. Disabled by default.

        :type: UARTParity
        """
        return UARTParity(
            (self.reg_config.get() >> self.__REG_CONFIG_BIT_PARITY) & 0b11)

    @parity.setter
    def parity(self, value):
        self.reg_config.set_mask(
            (value.value & 0b11) << self.__REG_CONFIG_BIT_PARITY,
            0b11 << self.__REG_CONFIG_BIT_PARITY)


class PulseGenerator(Module):
    """
    Pulse generator module of Scaffold.
    Usually abreviated as pgen.
    """
    def __init__(self, parent, path, base):
        """
        :param parent: The :class:`Scaffold` instance owning the UART module.
        :param path: Module path.
        :type path: str
        :param base: Base address for all registers.
        :type base: int
        """
        super().__init__(parent, path)
        # Create the signals
        self.add_signals('start', 'out')
        # Create the registers
        self.add_register('status', 'rv', base)
        self.add_register('control', 'wv', base + 1)
        self.add_register('config', 'w', base + 2, reset=0)
        self.add_register('delay', 'w', base + 3, wideness=3, reset=0)
        self.add_register('interval', 'w', base + 4, wideness=3, reset=0)
        self.add_register('width', 'w', base + 5, wideness=3, reset=0)
        self.add_register('count', 'w', base + 6, wideness=2, reset=0)

    def fire(self):
        """ Manually trigger the pulse generation. """
        self.reg_control.set(1)

    def __duration_to_clock_cycles(self, t):
        """
        Calculate the number of clock cycles corresponding to a given time.

        :param t: Time in seconds.
        :type t: float.
        """
        if t < 0:
            raise ValueError('Duration cannot be negative')
        cc = round(t * self.parent.sys_freq)
        return cc

    def __clock_cycles_to_duration(self, cc):
        """
        Calculate the time elapsed during a given number of clock cycles.

        :param cc: Number of clock cycles.
        :type cc: int
        """
        return cc / self.parent.sys_freq

    @property
    def delay(self):
        """
        Delay before pulse, in seconds.

        :type: float
        """
        return self.__clock_cycles_to_duration(self.reg_delay.get() + 1)

    @delay.setter
    def delay(self, value):
        n = self.__duration_to_clock_cycles(value)-1
        self.reg_delay.set(n)

    @property
    def delay_min(self):
        """ :return: Minimum possible delay. """
        return self.__clock_cycles_to_duration(1)

    @property
    def delay_max(self):
        """ :return: Maximum possible delay. """
        return self.__clock_cycles_to_duration(self.reg_delay.max + 1)

    @property
    def interval(self):
        """
        Delay between pulses, in seconds.

        :type: float
        """
        return self.__clock_cycles_to_duration(self.reg_interval.get() + 1)

    @interval.setter
    def interval(self, value):
        n = self.__duration_to_clock_cycles(value)-1
        self.reg_interval.set(n)

    @property
    def interval_min(self):
        """ :return: Minimum possible interval. """
        return self.__clock_cycles_to_duration(1)

    @property
    def interval_max(self):
        """ :return: Maximum possible interval. """
        return self.__clock_cycles_to_duration(self.reg_interval.max + 1)

    @property
    def width(self):
        """
        Pulse width, in seconds.

        :type: float
        """
        return self.__clock_cycles_to_duration(self.reg_width.get() + 1)

    @width.setter
    def width(self, value):
        n = self.__duration_to_clock_cycles(value)-1
        self.reg_width.set(n)

    @property
    def width_min(self):
        """ :return: Minimum possible pulse width. """
        return self.__clock_cycles_to_duration(1)

    @property
    def width_max(self):
        """ :return: Maximum possible pulse width. """
        return self.__clock_cycles_to_duration(self.reg_width.max + 1)

    @property
    def count(self):
        """
        Number of pulses to be generated. Minimum value is 1. Maximum value is
        2^16.

        :type: int
        """
        return self.reg_count.get() + 1

    @count.setter
    def count(self, value):
        if value not in range(1, 2**16+1):
            raise ValueError('Invalid pulse count')
        self.reg_count.set(value-1)

    @property
    def count_min(self):
        """ :return: Minimum possible pulse count. """
        return 1

    @property
    def count_max(self):
        """ :return: Maximum possible pulse count. """
        return self.reg_count.max + 1

    @property
    def polarity(self):
        """
        Pulse polarity. If 0, output is low when idle, and high during pulses.
        When 1, output is high when idle, and low during pulses.

        :type: int
        """
        return self.reg_config.get() & 1

    @polarity.setter
    def polarity(self, value):
        if value not in range(2):
            raise ValueError('Invalid polarity value: must be 0 or 1')
        self.reg_config.set_bit(0, value)


class Power(Module):
    """ Controls the platform and DUT sockets power supplies. """
    __ADDR_CONTROL = 0x0600

    def __init__(self, parent):
        """ :param parent: The Scaffold instance owning the power module. """
        super().__init__(parent, '/power')
        self.add_register('control', 'rwv', self.__ADDR_CONTROL)
        self.add_signals('dut_trigger', 'platform_trigger')

    @property
    def all(self):
        """
        All power-supplies state. int. Bit 0 corresponds to the DUT power
        supply. Bit 1 corresponds to the platform power-supply. When a bit is
        set to 1, the corresponding power supply is enabled. This attribute can
        be used to control both power supplies simultaneously.
        """
        return self.reg_control.get()

    @all.setter
    def all(self, value):
        assert (value & ~0b11) == 0
        self.reg_control.set(value)

    @property
    def platform(self):
        """ Platform power-supply state. int. """
        return self.reg_control.get_bit(1)

    @platform.setter
    def platform(self, value):
        self.reg_control.set_bit(1, value)

    @property
    def dut(self):
        """ DUT power-supply state. int. """
        return self.reg_control.get_bit(0)

    @dut.setter
    def dut(self, value):
        self.reg_control.set_bit(0, value)

    def restart_dut(self, toff=0.05, ton=0):
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

    def restart_platform(self, toff=0.05, ton=0):
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

    def restart_all(self, toff=0.05, ton=0):
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


class ISO7816ParityMode(Enum):
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

    def __init__(self, parent):
        """
        :param parent: The Scaffold instance owning the UART module.
        """
        super().__init__(parent, '/iso7816')
        self.add_signals('io_in', 'io_out', 'clk', 'trigger')
        self.__addr_base = base = 0x0500
        self.add_register('status', 'rv', base)
        self.add_register('control', 'w', base + 1)
        self.add_register('config', 'w', base + 2)
        self.add_register('divisor', 'w', base + 3)
        self.add_register('etu', 'w', base + 4, wideness=2)
        self.add_register('data', 'rwv', base + 5)
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
    def clock_frequency(self, value):
        d = round((0.5 * self.parent.sys_freq / value) - 1)
        # Check that the divisor fits one unsigned byte.
        if d > 0xff:
            raise ValueError('Target clock frequency is too low.')
        if d < 0:
            raise ValueError('Target clock frequency is too high.')
        # Calculate error between target and effective clock frequency
        real = self.parent.sys_freq / ((d + 1) * 2)
        err = abs(real - value) / value
        max_err = self.max_err = 0.01
        if err > max_err:
            raise RuntimeError(
                f'Cannot reach target clock frequency within {max_err*100}% '
                'accuracy.')
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
    def etu(self, value):
        if value not in range(1, 2**11):
            raise ValueError('Invalid ETU parameter')
        self.reg_etu.set(value - 1)

    def flush(self):
        """ Discard all the received bytes in the FIFO. """
        self.reg_control.write(1 << self.__REG_CONTROL_BIT_FLUSH)

    def receive(self, n=1, timeout=None):
        """
        Receive bytes. This function blocks until all bytes have been
        received or the timeout expires and a TimeoutError is thrown.

        :param n: Number of bytes to be read.
        """
        with self.parent.timeout_section(timeout):
            return self.reg_data.read(
                n, poll=self.reg_status,
                poll_mask=(1 << self.__REG_STATUS_BIT_EMPTY), poll_value=0x00)

    def transmit(self, data, trigger=False):
        """
        Transmit data.

        :param data: Data to be transmitted.
        :param trigger: Enable trigger on the last transmitted byte.
        :type data: bytes
        """
        # Polling on status.ready bit before sending each character
        if not trigger:
            self.reg_data.write(
                data, poll=self.reg_status,
                poll_mask=(1 << self.__REG_STATUS_BIT_READY),
                poll_value=(1 << self.__REG_STATUS_BIT_READY))
        else:
            # We want to trig on the last sent character
            with self.parent.lazy_section():
                self.reg_config.set_bit(
                    self.__REG_CONFIG_TRIGGER_TX, 0, poll=self.reg_status,
                    poll_mask=(1 << self.__REG_STATUS_BIT_READY),
                    poll_value=(1 << self.__REG_STATUS_BIT_READY))
                self.reg_data.write(
                    data[:-1], poll=self.reg_status,
                    poll_mask=(1 << self.__REG_STATUS_BIT_READY),
                    poll_value=(1 << self.__REG_STATUS_BIT_READY))
                self.reg_config.set_bit(
                    self.__REG_CONFIG_TRIGGER_TX, 1, poll=self.reg_status,
                    poll_mask=(1 << self.__REG_STATUS_BIT_READY),
                    poll_value=(1 << self.__REG_STATUS_BIT_READY))
                self.reg_data.write(data[-1])
                self.reg_config.set_bit(
                    self.__REG_CONFIG_TRIGGER_TX, 0, poll=self.reg_status,
                    poll_mask=(1 << self.__REG_STATUS_BIT_READY),
                    poll_value=(1 << self.__REG_STATUS_BIT_READY))

    @property
    def empty(self):
        """ True if reception FIFO is empty. """
        return bool(self.reg_status.get() & (1 << self.__REG_STATUS_BIT_EMPTY))

    @property
    def parity_mode(self):
        """
        Parity mode. Standard is Even parity, but it can be changed to odd or
        forced to a fixed value for testing purposes.
        :type: ISO7816ParityMode
        """
        return ISO7816ParityMode(
            (self.reg_config.get() >> self.__REG_CONFIG_PARITY_MODE) & 0b11)

    @parity_mode.setter
    def parity_mode(self, value):
        self.reg_config.set_mask(
            (value.value & 0b11) << self.__REG_CONFIG_PARITY_MODE,
            0b11 << self.__REG_CONFIG_PARITY_MODE)

    @property
    def trigger_tx(self):
        """
        Enable or disable trigger upon transmission.
        :type: bool
        """
        return bool(self.reg_config.get_bit(self.__REG_CONFIG_TRIGGER_TX))

    @trigger_tx.setter
    def trigger_tx(self, value):
        self.reg_config.set_bit(self.__REG_CONFIG_TRIGGER_TX, value)

    @property
    def trigger_rx(self):
        """
        Enable or disable trigger upon reception.
        :type: bool
        """
        return bool(self.reg_config.get_bit(self.__REG_CONFIG_TRIGGER_RX))

    @trigger_rx.setter
    def trigger_rx(self, value):
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
    def trigger_long(self, value):
        # We want until transmission is ready to avoid triggering on a pending
        # one.
        self.reg_config.set_bit(
            self.__REG_CONFIG_TRIGGER_LONG,
            value,
            poll=self.reg_status,
            poll_mask=1 << self.__REG_STATUS_BIT_READY,
            poll_value=1 << self.__REG_STATUS_BIT_READY)


class I2CNackError(Exception):
    """
    This exception is thrown by I2C peripheral when a transaction received a
    NACK from the I2C slave.
    """
    def __init__(self, index):
        """
        :param index: NACKed byte index. If N, then the N-th byte has not been
            acked.
        :type index: int
        """
        super().__init__()
        self.index = index

    def __str__(self):
        """ :return: Error details on the NACKed I2C transaction. """
        return f"Byte of index {self.index} NACKed during I2C transaction."


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

    def __init__(self, parent, index):
        """
        :param parent: The Scaffold instance owning the I2C module.
        :param index: I2C module index.
        """
        super().__init__(parent, f'/i2c{index}')
        self.__index = index
        # Declare the signals
        self.add_signals('sda_in', 'sda_out', 'scl_in', 'scl_out', 'trigger')
        # Declare the registers
        self.__addr_base = base = 0x0700 + 0x0010 * index
        self.add_register('status', 'rv', base)
        self.add_register('control', 'w', base + 1)
        self.add_register('config', 'w', base + 2)
        self.add_register('divisor', 'w', base + 3, wideness=2, min_value=1)
        self.add_register('data', 'rwv', base + 4)
        self.add_register('size_h', 'rwv', base + 5)
        self.add_register('size_l', 'rwv', base + 6)
        self.address = None
        # Current I2C clock frequency
        self.__cache_frequency = None

    def reset_config(self):
        """
        Reset the I2C peripheral to a default configuration.
        """
        self.reg_divisor = 1
        self.reg_size_h = 0
        self.reg_size_l = 0
        self.reg_config = (
            (1 << self.__REG_CONFIG_BIT_CLOCK_STRETCHING) |
            (1 << self.__REG_CONFIG_BIT_TRIGGER_START))

    def flush(self):
        """ Discards all bytes in the transmission/reception FIFO. """
        self.reg_control.write(1 << self.__REG_CONTROL_BIT_FLUSH)

    def raw_transaction(self, data, read_size, trigger=None):
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
        :type trigger: int or str.
        :raises I2CNackError: If a NACK is received during the transaction.
        """
        # Verify trigger parameter before doing anything
        t_start = False
        t_end = False
        if type(trigger) is int:
            if trigger not in range(2):
                raise ValueError('Invalid trigger parameter')
            t_start = (trigger == 1)
        elif type(trigger) is str:
            t_start = ('a' in trigger)
            t_end = ('b' in trigger)
        else:
            if trigger is not None:
                raise ValueError('Invalid trigger parameter')
        # We are going to update many registers. We start a lazy section to
        # make the update faster: all the acknoledgements of bus write
        # operations are checked at the end.
        with self.parent.lazy_section():
            self.flush()
            self.reg_size_h = read_size >> 8
            self.reg_size_l = read_size & 0xff
            # Preload the FIFO
            self.reg_data.write(data)
            # Configure trigger for this transaction
            config_value = 0
            if t_start:
                config_value |= (1 << self.__REG_CONFIG_BIT_TRIGGER_START)
            if t_end:
                config_value |= (1 << self.__REG_CONFIG_BIT_TRIGGER_END)
            # Write config with mask to avoid overwritting clock_stretching
            # option bit
            self.reg_config.set_mask(
                config_value,
                (1 << self.__REG_CONFIG_BIT_TRIGGER_START) |
                (1 << self.__REG_CONFIG_BIT_TRIGGER_END))
            # Start the transaction
            self.reg_control.write(1 << self.__REG_CONTROL_BIT_START)
            # End of lazy section. Leaving the scope will automatically check
            # the responses of the Scaffold write operations.
        # Wait until end of transaction and read NACK flag
        st = self.reg_status.read(
            poll=self.reg_status,
            poll_mask=(1 << self.__REG_STATUS_BIT_READY),
            poll_value=(1 << self.__REG_STATUS_BIT_READY))[0]
        nacked = (st & (1 << self.__REG_STATUS_BIT_NACK)) != 0
        # Fetch all the bytes which are stored in the FIFO.
        if nacked:
            # Get the number of bytes remaining.
            remaining = (
                (self.reg_size_h.get() << 8) + self.reg_size_l.get())
            raise I2CNackError(len(data) - remaining - 1)
        else:
            fifo = self.reg_data.read(
                read_size,
                poll=self.reg_status,
                poll_mask=(1 << self.__REG_STATUS_BIT_DATA_AVAIL),
                poll_value=(1 << self.__REG_STATUS_BIT_DATA_AVAIL))
            # FIFO emptyness verification can be enabled below for debug
            # purpose. This shall always be the case, unless there is an
            # implementation bug. This check is not enabled by default because
            # it will slow down I2C communication.
            # if self.reg_status.get_bit(self.__REG_STATUS_BIT_DATA_AVAIL) \
            #     == 1:
            #     raise RuntimeError('FIFO should be empty')
            return fifo

    def __make_header(self, address, rw):
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
            raise ValueError('I2C transaction address is not defined')
        # Check address
        if address < 0:
            raise ValueError('I2C address cannot be negative')
        if address >= 2**11:  # R/W bit counted in address, so 11 bits max
            raise ValueError('I2C address is too big')
        if address > 2**8:
            # 10 bits addressing mode
            # R/W bit is bit 8.
            if address & 0x10:
                raise ValueError('I2C address bit 8 (R/W) must be 0')
            result.append(0xf0 + (address >> 8) + rw)
            result.append(address & 0x0f)
        else:
            # 7 bits addressing mode
            # R/W bit is bit 0.
            if address & 1:
                raise ValueError('I2C address LSB (R/W) must be 0')
            result.append(address + rw)
        return result

    def read(self, size, address=None, trigger=None):
        """
        Perform an I2C read transaction.

        :param address: Slave device address. If None, self.address is used by
            default. If defined and addressing mode is 7 bits, LSB must be 0
            (this is the R/W bit). If defined and addressing mode is 10 bits,
            bit 8 must be 0.
        :type address: int or None
        :return: Bytes from the slave.
        :raises I2CNackError: If a NACK is received during the transaction.
        """
        data = self.__make_header(address, 1)
        return self.raw_transaction(data, size, trigger)

    def write(self, data, address=None, trigger=None):
        """
        Perform an I2C write transaction.

        :param address: Slave device address. If None, self.address is used by
            default. If defined and addressing mode is 7 bits, LSB must be 0
            (this is the R/W bit). If defined and addressing mode is 10 bits,
            bit 8 must be 0.
        :type address: int or None
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
    def clock_stretching(self, value):
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
    def frequency(self, value):
        d = round((self.parent.sys_freq / (4 * value)) - 1)
        # Check that the divisor can be stored on 16 bits.
        if d > 0xffff:
            raise ValueError('Target frequency is too low.')
        if d < 1:
            raise ValueError('Target frequency is too high.')
        real = self.parent.sys_freq / (d + 1)
        self.reg_divisor.set(d)
        self.__cache_frequency = real


class SPI(Module):
    """
    SPI peripheral of Scaffold.
    """
    __REG_STATUS_BIT_READY = 0
    __REG_CONTROL_BIT_TRIGGER = 7
    __REG_CONFIG_BIT_POLARITY = 0
    __REG_CONFIG_BIT_PHASE = 1

    def __init__(self, parent, index):
        """
        :param parent: The Scaffold instance owning the SPI module.
        :param index: SPI module index.
        """
        super().__init__(parent, f'/spi{index}')
        self.__index = index
        # Declare the signals
        self.add_signals('miso', 'sck', 'mosi', 'ss', 'trigger')
        # Declare the registers
        self.__addr_base = base = 0x0800 + 0x0010 * index
        self.add_register('status', 'rv', base)
        self.add_register('control', 'w', base + 1)
        self.add_register('config', 'w', base + 2, reset=0x00)
        self.add_register(
            'divisor', 'w', base + 3, wideness=2, min_value=1, reset=0x1000)
        self.add_register('data', 'rwv', base + 4)
        # Current SPI clock frequency
        self.__cache_frequency = None

    @property
    def polarity(self):
        """
        Clock polarity. 0 or 1.
        :type: int
        """
        return self.reg_config.get_bit(self.__REG_CONFIG_BIT_POLARITY)

    @polarity.setter
    def polarity(self, value):
        self.reg_config.set_bit(self.__REG_CONFIG_BIT_POLARITY, value)

    @property
    def phase(self):
        """
        Clock phase. 0 or 1.
        :type: int
        """
        return self.reg_config.get_bit(self.__REG_CONFIG_BIT_PHASE)

    @phase.setter
    def phase(self, value):
        self.reg_config.set_bit(self.__REG_CONFIG_BIT_PHASE, value)

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
    def frequency(self, value):
        d = round((self.parent.sys_freq / (4 * value)) - 1)
        # Check that the divisor can be stored on 16 bits.
        if d > 0xffff:
            raise ValueError('Target frequency is too low.')
        if d < 1:
            raise ValueError('Target frequency is too high.')
        real = self.parent.sys_freq / (d + 1)
        self.reg_divisor.set(d)
        self.__cache_frequency = real

    def transmit(self, value: int, size: int = 8, trigger=False, read=True):
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
            raise ValueError('Invalid size for SPI transaction')
        if value < 0:
            raise ValueError('value cannot be negative')
        if value >= (2**size):
            raise ValueError('value is too high')
        # The value to be transmitted must be loaded in the transmission
        # shift-register, less significant bit first. The buffer will transmit
        # its size most significant bits.
        pad = size
        while pad % 8 != 0:
            value <<= 1
            pad += 1
        remaining = size
        while remaining > 0:
            self.reg_data.write(value & 0xff)
            value >>= 8
            remaining -= 8
        # Start transmission
        if trigger:
            trigger = 1
        self.reg_control.write(
            (trigger << self.__REG_CONTROL_BIT_TRIGGER) + (size - 1),
            poll=self.reg_status,
            poll_mask=(1 << self.__REG_STATUS_BIT_READY),
            poll_value=(1 << self.__REG_STATUS_BIT_READY))
        if read:
            res = self.read_data_buffer((size-1)//8 + 1)
            # Mask to discard garbage bits from previous operations
            res &= 2**size - 1
            return res

    def read_data_buffer(self, n):
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
            poll=self.reg_status,
            poll_mask=(1 << self.__REG_STATUS_BIT_READY),
            poll_value=(1 << self.__REG_STATUS_BIT_READY))
        return int.from_bytes(res, 'little')


class Chain(Module):
    """ Chain trigger module. """
    __ADDR_CONTROL = 0x0900

    def __init__(self, parent, index, size):
        """
        :param parent: Scaffold instance owning the chain module.
        :type parent: Scaffold
        :param index: Module index.
        :type index: int
        :param size: Number of events in the chain.
        :type size: int
        """
        super().__init__(parent, f'/chain{index}')
        self.add_register('control', 'wv', self.__ADDR_CONTROL + index * 0x10)
        for i in range(size):
            self.add_signal(f'event{i}')
        self.add_signal('trigger')

    def rearm(self):
        """ Reset the chain trigger to initial state. """
        self.reg_control.set(1)


class Clock(Module):
    """
    Clock generator module. This peripheral allows generating a clock derived
    from the FPGA system clock using a clock divisor. A second clock can be
    generated and enabled during a short period of time to override the first
    clock, generating clock glitches.
    """
    __ADDR_CONFIG = 0x0a00
    __ADDR_DIVISOR_A = 0x0a01
    __ADDR_DIVISOR_B = 0x0a02
    __ADDR_COUNT = 0x0a03

    def __init__(self, parent, index):
        """
        :param parent: Scaffold instance owning the clock module.
        :type parent: Scaffold
        :param index: Module index.
        :type index: int
        """
        super().__init__(parent, f'/clock{index}')
        self.add_register('config', 'w', self.__ADDR_CONFIG + index * 0x10)
        self.add_register(
            'divisor_a', 'w', self.__ADDR_DIVISOR_A + index * 0x10)
        self.add_register(
            'divisor_b', 'w', self.__ADDR_DIVISOR_B + index * 0x10)
        self.add_register('count', 'w', self.__ADDR_COUNT + index * 0x10)
        self.add_signals('glitch', 'out')

        self.__freq_helper_a = FreqRegisterHelper(
            self.parent.sys_freq, self.reg_divisor_a)
        self.__freq_helper_b = FreqRegisterHelper(
            self.parent.sys_freq, self.reg_divisor_b)

    @property
    def frequency(self):
        """
        Base clock frequency, in Hertz. Only divisors of the system frequency
        can be set: 50 MHz, 25 MHz, 16.66 MHz, 12.5 MHz...

        :type: float
        """
        return self.__freq_helper_a.get()

    @frequency.setter
    def frequency(self, value):
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
    def glitch_frequency(self, value):
        self.__freq_helper_b.set(value)

    @property
    def div_a(self):
        return self.reg_divisor_a.get()

    @div_a.setter
    def div_a(self, value):
        self.reg_divisor_a.set(value)

    @property
    def div_b(self):
        return self.reg_divisor_b.get()

    @div_b.setter
    def div_b(self, value):
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
    def glitch_count(self, value):
        self.reg_count.set(value)


class IOMode(Enum):
    AUTO = 0
    OPEN_DRAIN = 1
    PUSH_ONLY = 2


class Pull(Enum):
    NONE = 0b00
    UP = 0b11
    DOWN = 0b01


class IO(Signal, Module):
    """
    Board I/O.
    """
    def __init__(self, parent, path, index, pullable=False):
        """
        :param parent: Scaffold instance which the signal belongs to.
        :param path: Signal path string.
        :param index: I/O index.
        :param pullable: True if this I/O supports pull resistor.
        """
        Signal.__init__(self, parent, path)
        Module.__init__(self, parent)
        self.index = index
        self.__pullable = pullable
        if parent.version == '0.2':
            # 0.2 only
            # Since I/O will have more options, it is not very convenient to
            # group them anymore.
            self.__group = index // 8
            self.__group_index = index % 8
            base = 0xe000 + 0x10 * self.__group
            self.add_register('value', 'rv', base + 0x00)
            self.add_register('event', 'rwv', base + 0x01, reset=0)
        else:
            # 0.3
            base = 0xe000 + 0x10 * self.index
            self.add_register('value', 'rwv', base + 0x00, reset=0)
            self.add_register('config', 'rw', base + 0x01, reset=0)
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
        if self.parent.version == '0.2':
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
        if self.parent.version == '0.2':
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
        if self.parent.version == '0.2':
            self.reg_event.set(0xff ^ (1 << self.__group_index))
        else:
            # 0.3
            self.reg_value.set(0)

    @property
    def mode(self):
        """
        I/O mode. Default is AUTO, but this can be overriden for special
        applications.

        :type: IOMode
        """
        assert self.parent.version >= '0.3'
        return IOMode(self.reg_config.get() & 0b11)

    @mode.setter
    def mode(self, value):
        assert self.parent.version >= '0.3'
        if not isinstance(value, IOMode):
            raise ValueError('mode must be an instance of IOMode enumeration')
        self.reg_config.set_mask(value.value, 0b11)

    @property
    def pull(self):
        """
        Pull resistor mode. Can only be written if the I/O supports this
        feature.

        :type: Pull
        """
        assert self.parent.version >= '0.3'
        if not self.__pullable:
            return Pull.NONE
        return Pull((self.reg_config.get() >> 2) & 0b11)

    @pull.setter
    def pull(self, value):
        assert self.parent.version >= '0.3'
        # Accept None as value
        if value is None:
            value = Pull.NONE
        if (not self.__pullable) and (value != Pull.NONE):
            raise RuntimeError('This I/O does not support pull resistor')
        self.reg_config.set_mask(value.value << 2, 0b1100)


class ScaffoldBusLazySection:
    """
    Helper class to be sure the opened lazy sections are closed at some time.
    """
    def __init__(self, bus):
        self.bus = bus

    def __enter__(self):
        self.bus.lazy_start()

    def __exit__(self, type, value, traceback):
        self.bus.lazy_end()


class ScaffoldBusTimeoutSection:
    """
    Helper class to be sure a pushed timeout configuration is poped at some
    time. This is to be used with the python 'with' statement.
    """
    def __init__(self, bus, timeout):
        """
        :param bus: Scaffold bus manager.
        :type bus: ScaffoldBus
        :param timeout: Section timeout value, in seconds.
        :type timeout: int, float
        """
        self.bus = bus
        self.timeout = timeout

    def __enter__(self):
        self.bus.push_timeout(self.timeout)

    def __exit__(self, type, value, traceback):
        self.bus.pop_timeout()


class ScaffoldBus:
    """
    Low level methods to drive the Scaffold device.
    """
    MAX_CHUNK = 255
    FIFO_SIZE = 512

    def __init__(self, sys_freq, baudrate):
        """
        :param baudrate: UART baudrate
        :type baudrate: int
        """
        self.__baudrate = baudrate
        self.sys_freq = sys_freq
        # How long in seconds one timeout unit is.
        self.timeout_unit = (3.0/self.sys_freq)
        self.ser = None
        self.__lazy_writes = []
        self.__lazy_fifo_total_size = 0
        self.__lazy_fifo_sizes = []
        self.__lazy_stack = 0
        # Timeout value. This value can't be read from the board, so we cache
        # it there once set.
        self.__cache_timeout = None
        # Timeout stack for push_timeout and pop_timeout methods.
        self.__timeout_stack = []

    def connect(self, dev):
        """
        Connect to Scaffold board using the given serial port.
        :param dev: Serial port device path. For instance '/dev/ttyUSB0' on
            linux, 'COM0' on Windows.
        """
        self.ser = serial.Serial(dev, self.__baudrate)

    def prepare_datagram(
            self, rw, addr, size, poll, poll_mask, poll_value):
        """
        Helper function to build the datagrams to be sent to the Scaffold
        device. Also performs basic check on arguments.
        :rw: 1 for a write command, 0 for a read command.
        :addr: Register address.
        :size: Size of the data to be sent or received. Maximum size is 255.
        :param poll: Register instance or address. None if polling is not
            required.
        :poll_mask: Register polling mask.
        :poll_value: Register polling value.
        :return: A bytearray.
        """
        if rw not in range(2):
            raise ValueError('Invalid rw argument')
        if size not in range(1, self.MAX_CHUNK+1):
            raise ValueError('Invalid size')
        if addr not in range(0x10000):
            raise ValueError('Invalid address')
        if isinstance(poll, Register):
            poll = poll.address
        if (poll is not None) and (poll not in range(0x10000)):
            raise ValueError('Invalid polling address')
        command = rw
        if size > 1:
            command |= 2
        if poll is not None:
            command |= 4
        datagram = bytearray()
        datagram.append(command)
        datagram.append(addr >> 8)
        datagram.append(addr & 0xff)
        if poll is not None:
            datagram.append(poll >> 8)
            datagram.append(poll & 0xff)
            datagram.append(poll_mask)
            datagram.append(poll_value)
        if size > 1:
            datagram.append(size)
        return datagram

    def write(
            self, addr, data, poll=None, poll_mask=0xff, poll_value=0x00):
        """
        Write data to a register.
        :param addr: Register address.
        :param data: Data to be written. Can be a byte, bytes or bytearray.
        :param poll: Register instance or address. None if polling is not
            required.
        :param poll_mask: Register polling mask.
        :param poll_value: Register polling value.
        """
        if self.ser is None:
            raise RuntimeError('Not connected to board')

        # If data is an int, convert it to bytes.
        if type(data) is int:
            data = bytes([data])

        offset = 0
        remaining = len(data)
        while remaining:
            chunk_size = min(self.MAX_CHUNK, remaining)
            datagram = self.prepare_datagram(
                1, addr, chunk_size, poll, poll_mask, poll_value)
            datagram += data[offset:offset + chunk_size]
            assert len(datagram) < self.FIFO_SIZE
            if self.__lazy_stack == 0:
                self.ser.write(datagram)
                # Check immediately the result of the write operation.
                ack = self.ser.read(1)[0]
                if ack != chunk_size:
                    assert poll is not None
                    # Timeout error !
                    raise TimeoutError(
                        size=offset+ack, expected=offset+chunk_size)
            else:
                # Lazy-update section. The write result will be checked later,
                # when all lazy-sections are closed.
                dg_len = len(datagram)
                # We don't know how many write datagram have been processed
                # until we don't fetch the responses. It is possible to
                # overflow the hardware FIFO if a polling operation is
                # blocking. We have to check for those potential troubles.
                while self.__lazy_fifo_total_size + dg_len > self.FIFO_SIZE:
                    # FIFO might be full. We must process some responses to get
                    # some guaranteed FIFO space
                    expected_size = self.__lazy_writes[0]
                    # Following read will block if first operation in the FIFO
                    # is still pending.
                    ack = self.ser.read(1)[0]
                    del self.__lazy_writes[0]
                    self.__lazy_fifo_total_size -= self.__lazy_fifo_sizes[0]
                    del self.__lazy_fifo_sizes[0]
                    if ack != expected_size:
                        # Timeout error !
                        raise TimeoutError(size=ack, expected=expected_size)
                self.__lazy_fifo_total_size += dg_len
                self.__lazy_fifo_sizes.append(dg_len)
                self.ser.write(datagram)
                self.__lazy_writes.append(chunk_size)
            remaining -= chunk_size
            offset += chunk_size

    def read(
            self, addr, size=1, poll=None, poll_mask=0xff,
            poll_value=0x00):
        """
        Read data from a register.
        :param addr: Register address.
        :param poll: Register instance or address. None if polling is not
            required.
        :param poll_mask: Register polling mask.
        :param poll_value: Register polling value.
        :return: bytearray
        """
        if self.ser is None:
            raise RuntimeError('Not connected to board')
        # Read operation not permitted during lazy-update sections
        if self.__lazy_stack > 0:
            raise RuntimeError(
                'Read operations not allowed during lazy-update section.')
        result = bytearray()
        remaining = size
        offset = 0
        while remaining:
            chunk_size = min(self.MAX_CHUNK, remaining)
            datagram = self.prepare_datagram(
                0, addr, chunk_size, poll, poll_mask, poll_value)
            self.ser.write(datagram)
            res = self.ser.read(chunk_size+1)
            ack = res[-1]
            if ack != chunk_size:
                assert poll is not None
                result += res[:ack]
                raise TimeoutError(data=result, expected=chunk_size+offset)
            result += res[:-1]
            remaining -= chunk_size
            offset += chunk_size
        return result

    def __set_timeout_raw(self, value):
        """
        Configure the polling timeout register.

        :param value: Timeout register value. If 0 the timeout is disabled. One
            unit corresponds to three FPGA system clock cycles.
        """
        if (value < 0) or (value > 0xffffffff):
            raise ValueError('Timeout value out of range')
        datagram = bytearray()
        datagram.append(0x08)
        datagram += value.to_bytes(4, 'big', signed=False)
        self.ser.write(datagram)
        # No response expected from the board

    @property
    def is_connected(self):
        return self.set is not None

    def lazy_start(self):
        """
        Enters lazy-check update block, or add a block level if already in
        lazy-check mode. When lazy-check is enabled, the result of write
        operations on Scaffold bus are not checked immediately, but only when
        leaving all blocks. This allows updating many different registers
        without the serial latency because all the responses will be checked at
        once.
        """
        self.__lazy_stack += 1

    def lazy_end(self):
        """
        Close current lazy-update block. If this was the last lazy section,
        fetch all responses from Scaffold and check that all write operations
        went good. If any write-operation timed-out, the last TimeoutError is
        thrown.
        """
        if self.__lazy_stack == 0:
            raise RuntimeError('No lazy section started')
        self.__lazy_stack -= 1
        last_error = None
        if self.__lazy_stack == 0:
            # We closes all update blocks, we must now check all responses of
            # write requests.
            for expected_size in self.__lazy_writes:
                ack = self.ser.read(1)[0]
                if ack != expected_size:
                    # Timeout error !
                    last_error = TimeoutError(size=ack, expected=expected_size)
            self.__lazy_writes.clear()
            # All writes have been processed, we know the FIFO buffer is empty.
            self.__lazy_fifo_total_size = 0
            self.__lazy_fifo_sizes.clear()
            if last_error is not None:
                raise last_error

    @property
    def timeout(self) -> Optional[float]:
        """
        Timeout in seconds for read and write commands. If set to None, timeout
        is disabled.
        """
        if self.__cache_timeout is None:
            return RuntimeError('Timeout not set yet')
        if self.__cache_timeout == 0:
            return None
        else:
            return self.__cache_timeout * self.timeout_unit

    @timeout.setter
    def timeout(self, value: Optional[float]):
        if value is None:
            n = 0
        else:
            n = max(1, int(value / self.timeout_unit))
        if n != self.__cache_timeout:
            self.__set_timeout_raw(n)  # May throw is n out of range.
            self.__cache_timeout = n  # Must be after set_timeout

    def push_timeout(self, value):
        """
        Save previous timeout setting in a stack, and set a new timeout value.
        Call to `pop_timeout` will restore previous timeout value.
        The new effective timeout will be lower or equal to the current
        timeout. That is, the timeout cannot be increased, previous defined
        timeout have higher priority.

        :param value: New timeout value, in seconds.
        """
        if value is None:
            value = self.timeout
        else:
            if self.timeout is not None:
                value = min(self.timeout, value)
        self.__timeout_stack.append(self.timeout)
        self.timeout = value

    def pop_timeout(self):
        """
        Restore timeout setting from stack.

        :raises RuntimeError: if timeout stack is already empty.
        """
        if len(self.__timeout_stack) == 0:
            raise RuntimeError('Timeout setting stack is empty')
        self.timeout = self.__timeout_stack.pop()

    def lazy_section(self):
        """
        :return: ScaffoldBusLazySection to be used with the python 'with'
            tatement to start and close a lazy update section.
        """
        return ScaffoldBusLazySection(self)

    def timeout_section(self, timeout):
        """
        :return: :class:`ScaffoldBusTimeoutSection` to be used with the python
            'with' statement to start and close a timeout section.
        """
        return ScaffoldBusTimeoutSection(self, timeout)


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
    __ADDR_MTXR_BASE = 0xf100
    __ADDR_MTXL_BASE = 0xf000

    def __init__(self, sys_freq, board_name, supported_versions,
                 baudrate=2000000):
        """
        Defines basic parameters of the board.

        :param sys_freq: Architecture system frequency, in Hertz.
        :type sys_freq: int
        :param board_name: Expected board name during version string readout.
        :type board_name: str
        :param supported_versions: A list of supported version strings. For
            instance `[1.0, 2.0]`.
        :type supported_versions: list or tuple of string.
        :param baudrate: UART baudrate. Default to 2 Mbps. Other hardware
            boards may have different speed.
        :type baudrate: int
        """
        self.sys_freq = sys_freq
        self.__expected_board_name = board_name
        self.__supported_versions = supported_versions

        # Hardware version module. Defined here because it is an architecture
        # requirement. There is no need to expose this module.
        self.__version_module = Version(self)

        # Cache the version string once read
        self.__version_string = None
        self.__version = None
        self.__board_name = None

        # Low-level management
        # Set as an attribute to avoid having all low level routines visible in
        # the higher API Scaffold class.
        self.bus = ScaffoldBus(self.sys_freq, baudrate)

        # Mux matrices signals
        self.mtxl_in = []
        self.mtxl_out = []
        self.mtxr_in = []
        self.mtxr_out = []

    def add_mtxl_in(self, name):
        """
        Declares an input for the left interconnect matrix.

        :param name: Input signal name.
        :type name: str.
        """
        self.mtxl_in.append(name)

    def add_mtxl_out(self, name):
        """
        Declares an output of the left interconnect matrix.

        :param name: Output signal name.
        :type name: str.
        """
        self.mtxl_out.append(name)

    def add_mtxr_in(self, name):
        """
        Declares an input for the right interconnect matrix.

        :param name: Input signal name.
        :type name: str.
        """
        self.mtxr_in.append(name)

    def add_mtxr_out(self, name):
        """
        Declares an output of the right interconnect matrix.

        :param name: Input signal name.
        :type name: str.
        """
        self.mtxr_out.append(name)

    @property
    def version(self):
        """
        :return: Hardware version string. This string is queried and checked
            when connecting to the board. It is then cached and can be accessed
            using this property. If the instance is not connected to a board,
            None is returned.
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
            possible_ports = []
            for port in serial.tools.list_ports.comports():
                # USB description string can be 'Scaffold', with uppercase 'S'.
                if ((port.product is not None)
                        and (port.product.lower() ==
                             self.__expected_board_name)
                        and ((sn is None) or (port.serial_number == sn))):
                    possible_ports.append(port)
            if len(possible_ports) > 1:
                raise RuntimeError(
                    'Multiple ' + self.__expected_board_name +
                    ' devices found! I don\'t know which one to use.')
            elif len(possible_ports) == 1:
                dev = possible_ports[0].device
            else:
                raise RuntimeError(
                    'No ' + self.__expected_board_name + ' device found')
        else:
            if sn is not None:
                raise ValueError("dev and sn cannot be set together")

        self.bus.connect(dev)
        # Check hardware responds and has the correct version.
        self.__version_string = self.__version_module.get_string()
        # Split board name and version string
        tokens = self.__version_string.split('-')
        if len(tokens) != 2:
            raise RuntimeError(
                'Failed to parse board version string \''
                + self.__version_string + '\'')
        self.__board_name = tokens[0]
        self.__version = tokens[1]
        if self.__board_name != self.__expected_board_name:
            raise RuntimeError('Invalid board name during version check')
        if self.__version not in self.__supported_versions:
            raise RuntimeError(
                'Hardware version ' + self.__version + ' not supported')

    def __signal_to_path(self, signal):
        """
        Convert a signal, 0, 1 or None to a path. Verify the signal belongs to
        the current Scaffold instance.
        :param signal: Signal, 0, 1 or None.
        :return: Path string.
        """
        if isinstance(signal, Signal):
            if signal.parent != self:
                raise ValueError('Signal belongs to another Scaffold instance')
            return signal.path
        elif type(signal) == int:
            if signal not in (0, 1):
                raise ValueError('Invalid signal value')
            return str(signal)
        elif type(signal) == int:
            return str(signal)
        elif signal is None:
            return 'z'  # High impedance
        else:
            raise ValueError('Invalid signal type')

    def sig_connect(self, a, b):
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

        dest_in_mtxr_out = (dest_path in self.mtxr_out)
        dest_in_mtxl_out = (dest_path in self.mtxl_out)
        if not (dest_in_mtxr_out or dest_in_mtxl_out):
            # Shall never happen unless there is a bug
            raise RuntimeError(f'Invalid destination path \'{dest_path}\'')
        src_in_mtxl_in = (src_path in self.mtxl_in)
        src_in_mtxr_in = (src_path in self.mtxr_in)
        # Beware: we can have a dest signal with the same name in mtxr and
        # mtxl.
        if dest_in_mtxr_out and src_in_mtxr_in:
            if dest_in_mtxl_out and src_in_mtxl_in:
                # Shall never happen unless a module output has the same name
                # as one of its input.
                raise RuntimeError(
                    f'Connection ambiguity \'{dest_path}\' << '
                    + f'\'{src_path}\'.')
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
                f'Failed to connect \'{dest_path}\' << ' + f'\'{src_path}\'.')

    def sig_disconnect_all(self):
        """
        Disconnects all input and output signals. This is called during
        initialization to reset the board in a known state.
        """
        with self.lazy_section():
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
    def timeout(self, value):
        self.bus.timeout = value

    def push_timeout(self, value):
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

    def lazy_section(self):
        """
        :return: ScaffoldBusLazySection to be used with the python 'with'
            statement to start and close a lazy update section.
        """
        return self.bus.lazy_section()

    def timeout_section(self, timeout):
        """
        :return: :class:`ScaffoldBusTimeoutSection` instance to be used with
            the python 'with' statement to push and pop timeout configuration.
        """
        return self.bus.timeout_section(timeout)


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
    # Number of UART peripherals
    __UART_COUNT = 2
    # Number of pulse generator peripherals
    __PULSE_GENERATOR_COUNT = 4
    # Number of I2C modules
    __I2C_COUNT = 1

    def __init__(self, dev: Optional[str] = None, init_ios: bool = False,
                 sn: Optional[str] = None):
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
            100e6,  # System frequency: 100 MHz
            'scaffold',  # board name
            # Supported FPGA bitstream versions
            ('0.2', '0.3', '0.4', '0.5', '0.6', '0.7', '0.7.1', '0.7.2'))
        self.connect(dev, init_ios, sn)

    def connect(self, dev: Optional[str] = None, init_ios: bool = False,
                sn: Optional[str] = None):
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

        # Power module
        self.power = Power(self)
        # Leds module
        self.leds = LEDs(self)

        # Create the IO signals
        # Scaffold hardware v1 has FPGA arch version <= 0.3
        # Scaffold hardware v1.1 has FPGA arch version >= 0.4
        # The I/Os have changed between both versions.
        self.a0 = IO(self, '/io/a0', 0)
        self.a1 = IO(self, '/io/a1', 1)
        if self.version <= '0.3':
            self.b0 = IO(self, '/io/b0', 2)
            self.b1 = IO(self, '/io/b1', 3)
            self.c0 = IO(self, '/io/c0', 4)
            self.c1 = IO(self, '/io/c1', 5)
            for i in range(self.__IO_D_COUNT):
                self.__setattr__(f'd{i}', IO(self, f'/io/d{i}', i+6))
        else:
            self.a2 = IO(self, '/io/a2', 1)
            self.a3 = IO(self, '/io/a3', 1)
            for i in range(self.__IO_D_COUNT):
                # Only D0, D1 and D2 can be pulled in Scaffold hardware v1.1.
                self.__setattr__(
                    f'd{i}', IO(self, f'/io/d{i}', i + 4, pullable=(i < 3)))
            if self.version >= '0.6':
                for i in range(self.__IO_P_COUNT):
                    self.__setattr__(
                        f'p{i}',
                        IO(self, f'/io/p{i}', i + 4 + self.__IO_D_COUNT))

        # Create the UART modules
        self.uarts = []
        for i in range(self.__UART_COUNT):
            uart = UART(self, i)
            self.uarts.append(uart)
            self.__setattr__(f'uart{i}', uart)

        # Create the pulse generator modules
        self.pgens = []
        for i in range(self.__PULSE_GENERATOR_COUNT):
            pgen = PulseGenerator(self, f'/pgen{i}', 0x0300 + 0x10*i)
            self.pgens.append(pgen)
            self.__setattr__(f'pgen{i}', pgen)

        # Declare the I2C peripherals
        self.i2cs = []
        for i in range(self.__I2C_COUNT):
            i2c = I2C(self, i)
            self.i2cs.append(i2c)
            self.__setattr__(f'i2c{i}', i2c)

        # Declare the SPI peripherals
        self.spis = []
        if self.version >= '0.7':
            for i in range(1):
                spi = SPI(self, i)
                self.spis.append(spi)
                self.__setattr__(f'spi{i}', spi)

        # Declare the trigger chain modules
        self.chains = []
        if self.version >= '0.7':
            for i in range(2):
                chain = Chain(self, i, 3)
                self.chains.append(chain)
                self.__setattr__(f'chain{i}', chain)

        # Declare clock generation module
        self.clocks = []
        if self.version >= '0.7':
            for i in range(1):
                clock = Clock(self, i)
                self.clocks.append(clock)
                self.__setattr__(f'clock{i}', clock)

        # Create the ISO7816 module
        self.iso7816 = ISO7816(self)

        # FPGA left matrix input signals
        self.add_mtxl_in('0')
        self.add_mtxl_in('1')
        self.add_mtxl_in('/io/a0')
        self.add_mtxl_in('/io/a1')
        if self.version <= '0.3':
            # Scaffold hardware v1 only
            self.add_mtxl_in('/io/b0')
            self.add_mtxl_in('/io/b1')
            self.add_mtxl_in('/io/c0')
            self.add_mtxl_in('/io/c1')
        else:
            # Scaffold hardware v1.1
            self.add_mtxl_in('/io/a2')
            self.add_mtxl_in('/io/a3')
        for i in range(self.__IO_D_COUNT):
            self.add_mtxl_in(f'/io/d{i}')
        if self.version >= '0.6':
            for i in range(self.__IO_P_COUNT):
                self.add_mtxl_in(f'/io/p{i}')
        if self.version >= '0.7':
            # Feeback signals from module outputs (mostly triggers)
            for i in range(len(self.uarts)):
                self.add_mtxl_in(f'/uart{i}/trigger')
            self.add_mtxl_in('/iso7816/trigger')
            for i in range(len(self.i2cs)):
                self.add_mtxl_in(f'/i2c{i}/trigger')
            for i in range(len(self.spis)):
                self.add_mtxl_in(f'/spi{i}/trigger')
            for i in range(len(self.pgens)):
                self.add_mtxl_in(f'/pgen{i}/out')
            for i in range(len(self.chains)):
                self.add_mtxl_in(f'/chain{i}/trigger')

        # FPGA left matrix output signals
        # Update this section when adding new modules with inputs
        for i in range(self.__UART_COUNT):
            self.add_mtxl_out(f'/uart{i}/rx')
        self.add_mtxl_out('/iso7816/io_in')
        for i in range(self.__PULSE_GENERATOR_COUNT):
            self.add_mtxl_out(f'/pgen{i}/start')
        for i in range(self.__I2C_COUNT):
            self.add_mtxl_out(f'/i2c{i}/sda_in')
            self.add_mtxl_out(f'/i2c{i}/scl_in')
        for i in range(len(self.spis)):
            self.add_mtxl_out(f'/spi{i}/miso')
        for i in range(len(self.chains)):
            for j in range(3):  # 3 is the number of chain events
                self.add_mtxl_out(f'/chain{i}/event{j}')
        for i in range(len(self.clocks)):
            self.add_mtxl_out(f'/clock{i}/glitch')

        # FPGA right matrix input signals
        # Update this section when adding new modules with outpus
        self.add_mtxr_in('z')
        self.add_mtxr_in('0')
        self.add_mtxr_in('1')
        self.add_mtxr_in('/power/dut_trigger')
        self.add_mtxr_in('/power/platform_trigger')
        for i in range(self.__UART_COUNT):
            self.add_mtxr_in(f'/uart{i}/tx')
            self.add_mtxr_in(f'/uart{i}/trigger')
        self.add_mtxr_in('/iso7816/io_out')
        self.add_mtxr_in('/iso7816/clk')
        self.add_mtxr_in('/iso7816/trigger')
        for i in range(self.__PULSE_GENERATOR_COUNT):
            self.add_mtxr_in(f'/pgen{i}/out')
        for i in range(self.__I2C_COUNT):
            self.add_mtxr_in(f'/i2c{i}/sda_out')
            self.add_mtxr_in(f'/i2c{i}/scl_out')
            self.add_mtxr_in(f'/i2c{i}/trigger')
        for i in range(len(self.spis)):
            self.add_mtxr_in(f'/spi{i}/sck')
            self.add_mtxr_in(f'/spi{i}/mosi')
            self.add_mtxr_in(f'/spi{i}/ss')
            self.add_mtxr_in(f'/spi{i}/trigger')
        for i in range(len(self.chains)):
            self.add_mtxr_in(f'/chain{i}/trigger')
        for i in range(len(self.clocks)):
            self.add_mtxr_in(f'/clock{i}/out')

        # FPGA right matrix output signals
        self.add_mtxr_out('/io/a0')
        self.add_mtxr_out('/io/a1')
        if self.version <= '0.3':
            # Scaffold hardware v1 only
            self.add_mtxr_out('/io/b0')
            self.add_mtxr_out('/io/b1')
            self.add_mtxr_out('/io/c0')
            self.add_mtxr_out('/io/c1')
        else:
            # Scaffold hardware v1.1
            self.add_mtxr_out('/io/a2')
            self.add_mtxr_out('/io/a3')
        for i in range(self.__IO_D_COUNT):
            self.add_mtxr_out(f'/io/d{i}')
        if self.version >= '0.6':
            for i in range(self.__IO_P_COUNT):
                self.add_mtxr_out(f'/io/p{i}')

        self.reset_config(init_ios=init_ios)

    def reset_config(self, init_ios=False):
        """
        Reset the board to a default state.
        :param init_ios: True to enable I/Os peripherals initialization. Doing
            so will set all I/Os to a default state, but it may generate pulses
            on the I/Os. When set to False, I/Os connections are unchanged
            during initialization and keep the configuration set by previous
            sessions.
        """
        # Reset to a default configuration
        # This will perform many writes to registers, so we start a lazy
        # section for maximum speed! (about 7 times faster)
        with self.lazy_section():
            self.timeout = None
            # Sometime we don't want the I/Os to be changed, since it may
            # generate pulses and triggering stuff... Reseting the I/Os is an
            # option.
            if init_ios:
                self.sig_disconnect_all()
                self.a0.reset_registers()
                self.a1.reset_registers()
                if self.version <= '0.3':
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
                    self.__getattribute__(f'd{i}').reset_registers()
                if self.version >= '0.6':
                    for i in range(self.__IO_P_COUNT):
                        self.__getattribute__(f'p{i}').reset_registers()
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
