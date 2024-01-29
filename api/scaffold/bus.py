from enum import Enum
from typing import Optional, Union


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
