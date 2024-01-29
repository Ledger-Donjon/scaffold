from enum import Enum
from typing import Optional, Union, List
import serial


class TimeoutError(Exception):
    """Thrown when a polling read or write command timed out."""

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
                return f"Read timeout: partially received {len(self.data)} bytes {h}."
            else:
                return "Read timeout: no data received."
        else:
            return f"Write timeout. Only {self.size}/{self.expected} bytes written."


class OperationKind(Enum):
    READ = 0
    WRITE = 1
    TIMEOUT = 2
    BUFFER_WAIT = 3
    DELAY = 4


class OperationStatus(Enum):
    PENDING = 0
    COMPLETED = 1
    TIMEOUT = 2


class Operation:
    """
    References a bus read or write operation requested to the Scaffold board.
    Used to fetch the operation result as late as possible to reduce communication
    latency and increase performances.
    """

    def __init__(
        self,
        bus,
        kind: OperationKind,
        size: Optional[int],
        fifo_size: int,
    ):
        self.__bus = bus
        self.__kind = kind
        self.__fifo_size = fifo_size
        self.__size = size
        self.__status = OperationStatus.PENDING
        self.__result: Optional[Union[bytes, int]] = None

    def __del__(self):
        assert self.__status == OperationStatus.COMPLETED

    def resolve(self, result: Optional[Union[bytes, int]] = None):
        """
        Mark the operation as completed and set the result details.

        :param result: Read bytes for a read operation, number of bytes written for a
            write operation.
        """
        assert self.__status == OperationStatus.PENDING
        if self.kind == OperationKind.READ:
            assert type(result) in (bytes, bytearray)
            size_completed = len(result)
        elif self.kind == OperationKind.WRITE:
            assert type(result) is int
            size_completed = result

        if self.kind in (OperationKind.READ, OperationKind.WRITE):
            if size_completed == self.__size:
                self.__status = OperationStatus.COMPLETED
            else:
                assert size_completed < self.__size
                self.__status = OperationStatus.TIMEOUT
                self.__size_completed = size_completed
        else:
            assert self.__size is None
            self.__status = OperationStatus.COMPLETED

        self.__result = result

    def sync(self):
        """Wait until this operation has been processed."""
        while self.__status == OperationStatus.PENDING:
            self.__bus.fetch_oldest_operation_result()

    @property
    def kind(self) -> OperationKind:
        """Operation kind"""
        return self.__kind

    @property
    def size(self) -> Optional[int]:
        """
        Number of bytes to be read or written, or None for delay and buffer wait
        operations.
        """
        return self.__size

    @property
    def fifo_size(self) -> int:
        """Size of the operation in the FIFO"""
        return self.__fifo_size

    @property
    def result(self) -> Optional[bytes]:
        """
        Read bytes if the operation is a read, None if the operation is a write.
        If the operation is still pending in the hardware, it will wait until the
        result is available (or the operation times out).

        :raises: :class:`TimeoutError` if operation timed out.
        """
        self.sync()
        status = self.__status
        if status == OperationStatus.COMPLETED:
            if self.__kind == OperationKind.READ:
                return self.__result
            else:
                return None
        elif status == OperationStatus.TIMEOUT:
            raise TimeoutError(size=self.__size_completed, expected=self.__size)
        else:
            raise RuntimeError("Invalid status of droped operation")


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
        self.timeout_unit = 3.0 / self.sys_freq
        self.ser = None
        # Timeout value. This value can't be read from the board, so we cache
        # it there once set.
        self.__cache_timeout = None
        # Timeout stack for push_timeout and pop_timeout methods.
        self.__timeout_stack = []
        self.__operations: List[Operation] = []
        self.__fifo_size = 0
        self.version = None

    def __del__(self):
        while len(self.__operations):
            self.fetch_oldest_operation_result()
        del self.__operations

    def connect(self, dev):
        """
        Connect to Scaffold board using the given serial port.
        :param dev: Serial port device path. For instance '/dev/ttyUSB0' on
            linux, 'COM0' on Windows.
        """
        self.ser = serial.Serial(dev, self.__baudrate)

    def prepare_datagram(self, rw, addr, size, poll, poll_mask, poll_value):
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
            raise ValueError("Invalid rw argument")
        if size not in range(1, self.MAX_CHUNK + 1):
            raise ValueError("Invalid size")
        if addr not in range(0x10000):
            raise ValueError("Invalid address")
        if isinstance(poll, Register):
            poll = poll.address
        if (poll is not None) and (poll not in range(0x10000)):
            raise ValueError("Invalid polling address")
        command = rw
        if size > 1:
            command |= 2
        if poll is not None:
            command |= 4
        datagram = bytearray()
        datagram.append(command)
        datagram.append(addr >> 8)
        datagram.append(addr & 0xFF)
        if poll is not None:
            datagram.append(poll >> 8)
            datagram.append(poll & 0xFF)
            datagram.append(poll_mask)
            datagram.append(poll_value)
        if size > 1:
            datagram.append(size)
        return datagram

    def fetch_oldest_operation_result(self):
        """
        Reads the response from the oldest :class:`Operation` in the pipe. This will
        block until it has been processed by the board.
        """
        op = self.__operations[0]
        if op.kind == OperationKind.WRITE:
            ack = self.ser.read(1)[0]
            op.resolve(ack)
        elif op.kind == OperationKind.READ:
            ack = self.ser.read(op.size + 1)
            data = ack[: ack[-1]]  # Last byte of ACK is size of read data
            op.resolve(data)
        elif op.kind in (OperationKind.BUFFER_WAIT, OperationKind.DELAY):
            ack = self.ser.read(1)[0]
            assert ack == 0
            op.resolve()
        elif op.kind == OperationKind.TIMEOUT:
            # Processing the TIMEOUT command takes a single clock cycle, it much faster
            # than receiving a byte so this can be considered non blocking. This is why
            # we don't wait for an aknowledge here.
            op.resolve()

        # Remove operation from the queue.
        # If operation has not been copied, this will trigger checks and raise
        # TimeoutError if the operation timed out.
        self.__fifo_size -= op.fifo_size
        del self.__operations[0]
        if len(self.__operations) == 0:
            assert self.__fifo_size == 0

    def __require_fifo_space(self, size: int):
        """
        Wait for pending operations to complete until there is `size` bytes
        available in the FIFO.
        """
        while self.FIFO_SIZE - self.__fifo_size < size:
            assert len(self.__operations) > 0
            self.fetch_oldest_operation_result()

    def operation_write(
        self,
        addr: int,
        data: bytes,
        poll: Optional[int] = None,
        poll_mask: int = 0xFF,
        poll_value: int = 0x00,
    ) -> Operation:
        """
        Write data to a register.

        :param addr: Register address.
        :param data: Data to be written.
        :param poll: Register instance or address, if polling is required.
        :param poll_mask: Register polling mask.
        :param poll_value: Register polling value.
        :return: Write pending operation.
        """
        if self.ser is None:
            raise RuntimeError("Not connected to board")

        assert len(data) <= self.MAX_CHUNK
        datagram = self.prepare_datagram(
            1, addr, len(data), poll, poll_mask, poll_value
        )
        datagram += data
        assert len(datagram) < self.FIFO_SIZE
        self.__require_fifo_space(len(datagram))
        self.ser.write(datagram)  # Send as early as possible
        op = Operation(self, OperationKind.WRITE, len(data), len(datagram))
        self.__operations.append(op)
        self.__fifo_size += len(datagram)
        return op

    def operation_read(
        self,
        addr: int,
        size: int = 1,
        poll: Optional[int] = None,
        poll_mask: int = 0xFF,
        poll_value: int = 0x00,
    ) -> Operation:
        """
        Read data from a register.

        :param addr: Register address.
        :param poll: Register instance or address, if polling is required.
        :param poll_mask: Register polling mask.
        :param poll_value: Register polling value.
        :return: Read pending operation.
        """
        if self.ser is None:
            raise RuntimeError("Not connected to board")
        assert size <= self.MAX_CHUNK
        datagram = self.prepare_datagram(0, addr, size, poll, poll_mask, poll_value)
        self.__require_fifo_space(len(datagram))
        self.ser.write(datagram)
        op = Operation(self, OperationKind.READ, size, len(datagram))
        self.__operations.append(op)
        self.__fifo_size += len(datagram)
        # If this operation can timeout, we want to block until having the result, to
        # eventually throw a TimeoutException.
        if (poll is not None) and (poll_mask != 0):
            op.sync()
        return op

    def operation_timeout(self, value: int):
        """
        Configure the polling timeout register.

        :param value: Timeout register value. If 0 the timeout is disabled. One
            unit corresponds to three FPGA system clock cycles.
        """
        if self.ser is None:
            raise RuntimeError("Not connected to board")
        if (value < 0) or (value > 0xFFFFFFFF):
            raise ValueError("Timeout value out of range")
        datagram = b"\x08" + value.to_bytes(4, "big")
        self.__require_fifo_space(len(datagram))
        self.ser.write(datagram)
        op = Operation(self, OperationKind.TIMEOUT, None, len(datagram))
        self.__operations.append(op)
        self.__fifo_size += len(datagram)

    def operation_delay(self, cycles: int):
        """
        Execute a delay operation.

        :param cycles: Number of clock cycles for the delay.
        """
        assert self.version is not None
        if self.version < "0.9":
            raise RuntimeError("Delays requires hardware >= 0.9")
        if self.ser is None:
            raise RuntimeError("Not connected to board")
        if cycles not in range(0x1000000):
            raise ValueError("Delay out of range")
        datagram = b"\x09" + cycles.to_bytes(3, "big")
        self.__require_fifo_space(len(datagram))
        self.ser.write(datagram)
        op = Operation(self, OperationKind.DELAY, None, len(datagram))
        self.__operations.append(op)
        self.__fifo_size += len(datagram)

    def operation_buffer_wait(self, size: int):
        """
        Execute a buffer wait operation.

        :param size: Requested buffer size for starting processing.
        """
        assert self.version is not None
        if self.version < "0.9":
            raise RuntimeError("Buffer wait requires hardware >= 0.9")
        if self.ser is None:
            raise RuntimeError("Not connected to board")
        if size not in range(512):
            raise RuntimeError("Buffer size out of range")
        datagram = b"\x0a" + size.to_bytes(2, "big")
        self.__require_fifo_space(len(datagram))
        self.ser.write(datagram)
        op = Operation(self, OperationKind.DELAY, None, len(datagram))
        self.__operations.append(op)
        self.__fifo_size += len(datagram)

    def write(self, addr, data, poll=None, poll_mask=0xFF, poll_value=0x00):
        """
        Write data to a register.
        :param addr: Register address.
        :param data: Data to be written. Can be a byte, bytes or bytearray.
        :param poll: Register instance or address. None if polling is not
            required.
        :param poll_mask: Register polling mask.
        :param poll_value: Register polling value.
        """
        # If data is an int, convert it to bytes.
        if type(data) is int:
            data = bytes([data])

        offset = 0
        remaining = len(data)
        while remaining:
            chunk_size = min(self.MAX_CHUNK, remaining)
            self.operation_write(
                addr, data[offset : offset + chunk_size], poll, poll_mask, poll_value
            )
            remaining -= chunk_size
            offset += chunk_size

    def read(self, addr, size=1, poll=None, poll_mask=0xFF, poll_value=0x00):
        """
        Read data from a register.
        :param addr: Register address.
        :param poll: Register instance or address. None if polling is not
            required.
        :param poll_mask: Register polling mask.
        :param poll_value: Register polling value.
        :return: bytearray
        """
        result = bytearray()
        remaining = size
        offset = 0
        while remaining:
            chunk_size = min(self.MAX_CHUNK, remaining)
            op = self.operation_read(addr, chunk_size, poll, poll_mask, poll_value)
            result += op.result
            remaining -= chunk_size
            offset += chunk_size
        return result

    @property
    def is_connected(self):
        return self.set is not None

    @property
    def timeout(self) -> Optional[float]:
        """
        Timeout in seconds for read and write commands. If set to None, timeout
        is disabled.
        """
        if self.__cache_timeout is None:
            return RuntimeError("Timeout not set yet")
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
            self.operation_timeout(n)  # May throw if n out of range.
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
            raise RuntimeError("Timeout setting stack is empty")
        self.timeout = self.__timeout_stack.pop()

    def timeout_section(self, timeout):
        """
        :return: :class:`ScaffoldBusTimeoutSection` to be used with the python
            'with' statement to start and close a timeout section.
        """
        return ScaffoldBusTimeoutSection(self, timeout)


class Register:
    """
    Manages accesses to a register of a module. Implements value cache
    mechanism whenever possible.
    """

    def __init__(
        self,
        parent,
        mode,
        address,
        wideness=1,
        min_value=None,
        max_value=None,
        reset=None,
    ):
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
            raise ValueError("Invalid register address")
        self.__address = address

        self.__w = "w" in mode
        self.__r = "r" in mode
        self.__volatile = "v" in mode

        if wideness < 1:
            raise ValueError("Invalid wideness")
        if (wideness > 1) and self.__r:
            raise ValueError("Wideness must be 1 if register can be read.")
        self.__wideness = wideness

        if min_value is None:
            # Set default minimum value to 0.
            self.__min_value = 0
        else:
            # Check maximum value.
            if min_value not in range(2 ** (wideness * 8)):
                raise ValueError("Invalid register minimum value")
            self.__min_value = min_value

        if max_value is None:
            # Set default maximum value based on register size.
            self.__max_value = 2 ** (wideness * 8) - 1
        else:
            # Check maximum value.
            if max_value not in range(2 ** (wideness * 8)):
                raise ValueError("Invalid register maximum value")
            self.__max_value = max_value

        if self.__min_value > self.__max_value:
            raise ValueError(
                "Register minimum value must be lower or equal to maximum value"
            )

        self.__reset = reset
        self.__cache = None

    def set(self, value, poll=None, poll_mask=0xFF, poll_value=0x00):
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
            raise ValueError("Value too low")
        if value > self.__max_value:
            raise ValueError("Value too high")
        if not self.__w:
            raise RuntimeError("Register cannot be written")
        # Handle wideness
        value_bytes = value.to_bytes(self.__wideness, "big", signed=False)
        self.__parent.bus.write(
            self.__address, value_bytes, poll, poll_mask, poll_value
        )
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
                raise RuntimeError("Register cannot be read")
            return self.__parent.bus.read(self.__address)[0]
        else:
            # Register is not volatile, so its data can be cached.
            if self.__cache is None:
                if self.__r:
                    value = self.__parent.bus.read(self.__address)[0]
                    self.__cache = value
                else:
                    raise RuntimeError("Register cannot be read")
            return self.__cache

    def or_set(self, value):
        """
        Sets some bits to 1 in the register.
        :param value: An int.
        """
        self.set(self.get() | value)

    def set_bit(self, index, value, poll=None, poll_mask=0xFF, poll_value=0x00):
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
            poll,
            poll_mask,
            poll_value,
        )

    def get_bit(self, index):
        """
        :return: Value of a given bit, 0 or 1.
        :param index: Bit index, in [0, 7].
        """
        return (self.get() >> index) & 1

    def set_mask(self, value, mask, poll=None, poll_mask=0xFF, poll_value=0x00):
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
        self.set((current & (~mask)) | (value & mask), poll, poll_mask, poll_value)

    def write(self, data, poll=None, poll_mask=0xFF, poll_value=0x00):
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
            raise RuntimeError("Register cannot be written")
        self.__parent.bus.write(self.__address, data, poll, poll_mask, poll_value)

    def read(self, size=1, poll=None, poll_mask=0xFF, poll_value=0x00):
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
            raise RuntimeError("Register cannot be read")
        return self.__parent.bus.read(self.__address, size, poll, poll_mask, poll_value)

    def reset(self):
        """
        Set the register value to its default value. If no default value has
        been defined, this method has no effect.
        """
        if self.__reset is not None:
            self.set(self.__reset)

    @property
    def address(self):
        """:return: Register address."""
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
