"""Core classes and methods for communicating with the Scaffold FPGA."""


from enum import Enum
from typing import Optional, List
from abc import ABC, abstractmethod
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
            return "Read timeout: no data received."
        return f"Write timeout. Only {self.size}/{self.expected} bytes written."


class OperationStatus(Enum):
    """Possible status of a Scaffold bus operation"""

    PENDING = 0
    SENT = 1
    COMPLETED = 2
    TIMEOUT = 3


class Operation(ABC):
    """
    Base for all Scaffold bus operations.
    Defines how operations are encoded for the board and how the responses are decoded.
    Each operation has an execution status to know wether the response has been
    received or not.
    """

    def __init__(self):
        self.bus = None
        self.status = OperationStatus.PENDING

    def __del__(self):
        assert self.status in (OperationStatus.COMPLETED, OperationStatus.TIMEOUT)

    def wait(self):
        """Wait until this operation has been processed."""
        if self.status == OperationStatus.PENDING:
            raise RuntimeError("Cannot wait a pending operation")
        while self.status == OperationStatus.SENT:
            self.bus.resolve_next_operation()

    @abstractmethod
    def supported(self, version: str) -> bool:
        """:return: True if the given hardware version supports this operation."""

    @abstractmethod
    def datagram(self) -> bytes:
        """:return: Datagram of the operation, to be sent to the board."""

    @abstractmethod
    def response_size(self) -> int:
        """:return: Expected board response size to this operation."""

    @abstractmethod
    def resolve(self, data: bytes):
        """Process board response."""


class ReadWriteOperation(Operation):
    """Base class for :class:`ReadOperation` and :class:`WriteOperation`."""

    def __init__(self, addr: int):
        super().__init__()
        if addr not in range(0x10000):
            raise ValueError("Invalid address")
        self.__addr = addr
        self.__poll: Optional[int] = None
        self.__poll_mask: int = 0xFF
        self.__poll_value: int = 0

    def set_polling(self, addr: int, mask: int, value: int):
        """
        Enable polling for this read or write operation: the operation will be executed
        only when the given register gets a particular value.

        :param addr: Polled register address.
        :param mask: Mask applied to the register value before comparison with `value`.
        :param value: Expected value for the masked register value.
        """
        if addr not in range(0x10000):
            raise ValueError("Invalid polling address")
        if mask not in range(0x100):
            raise ValueError("Invalid polling mask")
        if value not in range(0x100):
            raise ValueError("Invalid polling value")
        self.__poll = addr
        self.__poll_mask = mask
        self.__poll_value = value

    def supported(self, _version: str) -> bool:
        return True

    def datagram_head(self, rw: int, size: int) -> bytearray:
        """
        Generates part of the datagram for a read write operation.

        :param rw: 0 for read, 1 for write.
        :param size: Read or write size.
        """
        command = rw
        if size > 1:
            command |= 2
        if self.__poll is not None:
            command |= 4
        datagram = bytearray([command, self.__addr >> 8, self.__addr & 0xFF])
        if self.__poll is not None:
            datagram += bytes(
                [
                    self.__poll >> 8,
                    self.__poll & 0xFF,
                    self.__poll_mask,
                    self.__poll_value,
                ]
            )
        if size > 1:
            datagram.append(size)
        return datagram


class ReadOperation(ReadWriteOperation):
    """Scaffold register read operation"""

    def __init__(self, addr: int, size: int = 1):
        super().__init__(addr)
        self.__size = size
        self.__result = None

    def datagram(self) -> bytes:
        return bytes(self.datagram_head(0, self.__size))

    def response_size(self) -> int:
        return 1 + self.__size

    def resolve(self, data):
        size_completed = data[-1]
        self.__result = data[:size_completed]
        if size_completed == self.__size:
            self.status = OperationStatus.COMPLETED
        else:
            assert size_completed < self.__size
            self.status = OperationStatus.TIMEOUT

    @property
    def result(self):
        """
        Data returned by the board during the read operation.

        :raises TimeoutError: if the read operation timed out.
        """
        self.wait()
        if self.status == OperationStatus.COMPLETED:
            return self.__result
        if self.status == OperationStatus.TIMEOUT:
            raise TimeoutError(data=self.__result, expected=self.__size)
        raise RuntimeError("Invalid operation status")


class WriteOperation(ReadWriteOperation):
    """Scaffold register write operation"""

    def __init__(self, addr: int, data: bytes):
        super().__init__(addr)
        if len(data) == 0:
            raise ValueError("No data")
        if len(data) > 255:
            raise ValueError("Data too long")
        self.__data = data

    def datagram(self) -> bytes:
        return bytes(self.datagram_head(1, len(self.__data))) + self.__data

    def response_size(self) -> int:
        return 1

    def resolve(self, data: bytes):
        size_completed = data[0]
        if size_completed == len(self.__data):
            self.status = OperationStatus.COMPLETED
        else:
            assert size_completed < len(self.__data)
            self.status = OperationStatus.TIMEOUT


class TimeoutOperation(Operation):
    """Scaffold timeout configuration operation"""

    def __init__(self, value: int):
        super().__init__()
        if value not in range(0x100000000):
            raise ValueError("Timeout value out of range")
        self.__value = value

    def supported(self, _version: str) -> bool:
        return True

    def datagram(self) -> bytes:
        return b"\x08" + self.__value.to_bytes(4, "big")

    def response_size(self) -> int:
        return 0

    def resolve(self, data: bytes):
        self.status = OperationStatus.COMPLETED


class DelayOperation(Operation):
    """
    Scaffold delay operation.

    Supported only with hardware >= 0.9.
    """

    def __init__(self, cycles: int):
        super().__init__()
        if cycles not in range(0x1000000):
            raise ValueError("Delay out of range")
        self.__cycles = cycles

    def supported(self, version: str) -> bool:
        return version >= "0.9"

    def datagram(self) -> bytes:
        return b"\x09" + self.__cycles.to_bytes(3, "big")

    def response_size(self) -> int:
        return 1

    def resolve(self, data: bytes):
        assert data[0] == 0
        self.status = OperationStatus.COMPLETED


class BufferWaitOperation(Operation):
    """
    Scaffold buffer wait operation.

    Supported only with hardware >= 0.9.
    """

    def __init__(self, size: int):
        super().__init__()
        if size not in range(512):
            raise ValueError("Buffer size out of range")
        self.__size = size

    def supported(self, version: str) -> bool:
        return version >= "0.9"

    def datagram(self) -> bytes:
        return b"\x0a" + self.__size.to_bytes(2, "big")

    def response_size(self) -> int:
        return 1

    def resolve(self, data: bytes):
        assert data[0] == 0
        self.status = OperationStatus.COMPLETED


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

    def __exit__(self, exc_type, exc_value, traceback):
        self.bus.pop_timeout()


class BufferWaitSection:
    """Helper class to enter and leave buffer wait sections."""

    def __init__(self, bus):
        self.bus = bus

    def __enter__(self):
        self.bus.push_buffer_wait()

    def __exit__(self, exc_type, exc_value, traceback):
        self.bus.pop_buffer_wait()


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
        # List of operations that has been sent to the board, and whose response has
        # not been fetched yet.
        self.__operations: List[Operation] = []
        # List of operations that will be sent to the board, prepended with a buffer
        # wait operation to be sure that the board has all the data before starting to
        # execute the operations. This is used to execute different operations with
        # precise timing.
        self.__buffer_wait_operations: List[Operation] = []
        # Every time a buffer wait section is entered, this member is incremented.
        # Every time a buffer wait section is exited, this member is decremented.
        # When this value is greater than zero, operations are not sent to the board,
        # but pushed in the __buffer_wait_operations list. As soon as this value goes
        # back to zero, a buffer wait operation is sent to the board, followed by all
        # pending operations in the list.
        self.__buffer_wait_stack = 0
        self.__fifo_size = 0
        self.version = None

    def __del__(self):
        while len(self.__operations) > 0:
            self.resolve_next_operation()
        del self.__operations

    def connect(self, dev):
        """
        Connect to Scaffold board using the given serial port.
        :param dev: Serial port device path. For instance '/dev/ttyUSB0' on
            linux, 'COM0' on Windows.
        """
        self.ser = serial.Serial(dev, self.__baudrate)

    def resolve_next_operation(self):
        """
        Reads the response from the oldest :class:`Operation` in the pipe. This will
        block until it has been processed by the board.
        """
        op = self.__operations[0]
        op.resolve(self.ser.read(op.response_size()))
        # Remove operation from the queue.
        # If operation has not been copied, this will trigger checks and raise
        # TimeoutError if the operation timed out.
        self.__fifo_size -= len(op.datagram())
        del self.__operations[0]
        if len(self.__operations) == 0:
            assert self.__fifo_size == 0

    def __require_fifo_space(self, size: int):
        """
        Wait for pending operations to complete until there is `size` bytes
        available in the FIFO.
        """
        while self.FIFO_SIZE - self.__fifo_size < size:
            self.resolve_next_operation()

    def operation(self, op: Operation):
        """
        Register a bus operation to be performed.
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to board")
        assert self.version is not None
        if not op.supported(self.version):
            raise RuntimeError("Operation not supported by current hardware version")
        if self.__buffer_wait_stack == 0:
            datagram = op.datagram()
            op.bus = self
            assert len(datagram) < self.FIFO_SIZE
            self.__require_fifo_space(len(datagram))
            self.ser.write(datagram)
            op.status = OperationStatus.SENT
            self.__operations.append(op)
            self.__fifo_size += len(datagram)
        else:
            # A synchronized block is being prepared. Don't send the operation to the
            # board yet, keep it in a separate list.
            self.__buffer_wait_operations.append(op)
        return op

    def delay(self, cycles: int):
        """
        Execute a delay operation.

        :param cycles: Number of clock cycles for the delay.
        """
        self.operation(DelayOperation(cycles))

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
        if isinstance(data, int):
            data = bytes([data])

        offset = 0
        remaining = len(data)
        while remaining:
            chunk_size = min(self.MAX_CHUNK, remaining)
            op = WriteOperation(addr, data[offset : offset + chunk_size])
            if poll is not None:
                op.set_polling(poll, poll_mask, poll_value)
            self.operation(op)
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
            op = ReadOperation(addr, chunk_size)
            if poll is not None:
                op.set_polling(poll, poll_mask, poll_value)
            self.operation(op)
            result += op.result
            remaining -= chunk_size
            offset += chunk_size
        return result

    @property
    def is_connected(self):
        """:return: True if connection with a board is established."""
        return self.ser is not None

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
        return self.__cache_timeout * self.timeout_unit

    @timeout.setter
    def timeout(self, value: Optional[float]):
        if value is None:
            n = 0
        else:
            n = max(1, int(value / self.timeout_unit))
        if n != self.__cache_timeout:
            self.operation(TimeoutOperation(n))
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

    def push_buffer_wait(self):
        """
        Enter a buffer wait section. All next commands won't be sent to the board
        immediately, but will be sent and executed in a single shot when leaving
        the section.
        """
        self.__buffer_wait_stack += 1

    def pop_buffer_wait(self):
        """
        Leave a buffer wait section.
        """
        if self.__buffer_wait_stack == 0:
            raise RuntimeError("No buffer wait section has been started")
        self.__buffer_wait_stack -= 1
        if self.__buffer_wait_stack == 0:
            # Calculate the size of all pending operations
            fifo_size = 0
            for op in self.__buffer_wait_operations:
                fifo_size += len(op.datagram())
            required_fifo_space = fifo_size + 3  # Size of the buffer wait operation
            if required_fifo_space > self.FIFO_SIZE:
                raise RuntimeError("Buffer wait section is too large")
            self.__require_fifo_space(required_fifo_space)
            self.operation(BufferWaitOperation(fifo_size))
            for op in self.__buffer_wait_operations:
                self.operation(op)
            self.__buffer_wait_operations.clear()

    def buffer_wait_section(self):
        """
        :return: :class:`BufferWaitSection` to be used with the python 'with' statement
            to start and close a buffer wait section.
        """
        return BufferWaitSection(self)


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
