SPI module
==========

The SPI module enables SPI master communication with Scaffold. For the moment,
it is not able to act as a slave SPI peripheral.

This SPI peripheral is able to send or receive up to 32 bits per transaction.


Python API example
------------------

The following example configures the SPI peripheral as master, transmits and
receives one byte:

.. code-block:: python

    spi = scaffold.spi0
    spi.sck >> scaffold.d0
    spi.ss >> scaffold.d1
    spi.mosi >> scaffold.d2
    spi.miso << scaffold.d3
    spi.frequency = 10000
    resp = spi.transmit(0xaa)

The following example configures the SPI peripheral as slave and prepares to
respond one byte when next transmission initiated by the master takes place:

.. code-block:: python

    spi = scaffold.spi0
    spi.mode = SPIMode.SLAVE
    spi.sck << scaffold.d0
    spi.ss << scaffold.d1
    spi.miso >> scaffold.d2
    spi.append(0xaa)

For more API documentation, see :class:`scaffold.SPI`


Signals
-------

.. modbox::
    :inputs: sck, ss, miso
    :outputs: sck, ss, miso, mosi, trigger*


Internal registers
------------------

+------+--------+
| spi0 | 0x0800 |
+------+--------+

+---------------+---------+-----+
| base + 0x0000 | status  | R   |
+---------------+---------+-----+
| base + 0x0001 | control | W   |
+---------------+---------+-----+
| base + 0x0002 | config  | W   |
+---------------+---------+-----+
| base + 0x0003 | divisor | W   |
+---------------+---------+-----+
| base + 0x0004 | data    | R/W |
+---------------+---------+-----+

status register
^^^^^^^^^^^^^^^

+---+---+---+---+---+---+---+-------+
| 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0     |
+---+---+---+---+---+---+---+-------+
| *reserved*                | ready |
+---------------------------+-------+

ready
  1 when the SPI peripheral is ready to start a new transaction.

control register
^^^^^^^^^^^^^^^^

+---------+-------+---+---+---+---+---+---+
| 7       | 6     | 5 | 4 | 3 | 2 | 1 | 0 |
+---------+-------+---+---+---+---+---+---+
| trigger | clear | size                  |
+---------+-------+-----------------------+

size
  Number of bits to be transmitted/received, minus 1. When written, transmission
  starts.
clear
  Write 1 to clear the slave FIFO
trigger
  Write 1 to enable trigger for next transmission.

config register
^^^^^^^^^^^^^^^

+---+---+---+---+---+------+-------+----------+
| 7 | 6 | 5 | 4 | 3 | 2    | 1     | 0        |
+---+---+---+---+---+------+-------+----------+
| *reserved*        | mode | phase | polarity |
+-------------------+------+-------+----------+

polarity
  Clock polarity configuration bit.
phase
  Clock phase during transmission.
mode
  SPI peripheral mode. 0 for master mode (default), 1 for slave mode.

divisor register
^^^^^^^^^^^^^^^^

This 16-bits register controls the baudrate of the SPI peripheral. Write twice
to set MSB and LSB.

data register
^^^^^^^^^^^^^

In master mode, write to set the data to be transmitted. Writting multiple
times this register will load the transmission buffer from the MSB.

In master mode, read this register to get the data which has been received.
Reading multiple times this register will read the reception buffer from the
LSB.

In slave mode, write to set the response bytes to be returned by the peripheral
as slave. Up to 512 bytes can be stored in the FIFO. Bytes are removed
one-by-one when they are transmitted.

In slave mode, reading this register has undefined behavior.
