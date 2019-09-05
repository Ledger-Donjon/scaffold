SPI module
==========

The SPI module enables SPI master communication with Scaffold. For the moment,
it is not able to act as a slave SPI peripheral.

This SPI peripheral is able to send or receive up to 32 bits per transaction.


Python API example
------------------

.. code-block:: python

    spi = scaffold.spi0
    spi.sck >> scaffold.d0
    spi.mosi >> scaffold.d1
    spi.miso << scaffold.d2
    spi.frequency = 10000
    resp = spi.transmit(0xaa)

For more API documentation, see :class:`scaffold.SPI`


Signals
-------

.. modbox::
    :inputs: miso
    :outputs: sck, mosi, ss, trigger


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

+---------+------------+---+---+---+---+---+---+
| 7       | 6          | 5 | 4 | 3 | 2 | 1 | 0 |
+---------+------------+---+---+---+---+---+---+
| trigger | *reserved* | size                  |
+---------+------------+-----------------------+

size
  Number of bits to be transmitted/received, minus 1. When written, transmission
  starts.
trigger
  Write 1 to enable trigger for next transmission.

config register
^^^^^^^^^^^^^^^

+---+---+---+---+---+---+-------+----------+
| 7 | 6 | 5 | 4 | 3 | 2 | 1     | 0        |
+---+---+---+---+---+---+-------+----------+
| *reserved*            | phase | polarity |
+-----------------------+-------+----------+

polarity
  Clock polarity configuration bit.
phase
  Clock phase during transmission.

divisor register
^^^^^^^^^^^^^^^^

This 16-bits register controls the baudrate of the SPI peripheral. Write twice
to set MSB and LSB.

data register
^^^^^^^^^^^^^

Write to set the data to be transmitted. Writting multiple times this register
will load the transmission buffer from the MSB.

Read this register to get the data which has been received. Reading multiple
times this register will read the reception buffer from the LSB.

