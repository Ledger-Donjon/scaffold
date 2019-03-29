I2C module
==========

The I2C module enables I2C master communication with Scaffold.


Python API example
------------------

.. code-block:: python

    sda = scaffold.d0
    scl = scaffold.d1
    i2c = scaffold.i2c0

    i2c.sda_in << sda
    i2c.sda_out >> sda
    i2c.scl_in << scl
    i2c.scl_out >> scl
    i2c.trigger >> scaffold.d5
    i2c.frequency = 100e3

    i2c.address = 0xc0
    i2c.write(b'1234')
    print(i2c.read(4))

For more API documentation, see :class:`scaffold.I2C`


Signals
-------

.. modbox::
    :inputs: sda_in, scl_in
    :outputs: sda_out, scl_out, trigger


Internal registers
------------------

+------+--------+
| i2c0 | 0x0700 |
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
| base + 0x0005 | size_h  | R/W |
+---------------+---------+-----+
| base + 0x0006 | size_l  | R/W |
+---------------+---------+-----+

status register
^^^^^^^^^^^^^^^

+---+---+---+---+---+------------+------+-------+
| 7 | 6 | 5 | 4 | 3 | 2          | 1    | 0     |
+---+---+---+---+---+------------+------+-------+
| *reserved*        | data_avail | nack | ready |
+-------------------+------------+------+-------+

ready
  1 when the I2C peripheral is ready to start a new transaction.
nack
  1 if the previous transaction received a NACK from the slave during a byte
  transmission.
data_avail
  1 while there is received data in the FIFO to be read.

control register
^^^^^^^^^^^^^^^^

+---+---+---+---+---+---+-------+-------+
| 7 | 6 | 5 | 4 | 3 | 2 | 1     | 0     |
+---+---+---+---+---+---+-------+-------+
| *reserved*            | flush | start |
+-----------------------+-------+-------+

start
  Write 1 to this bit to start a new transaction. All bytes which have been
  pushed in the FIFO are sent. The received bytes are then stored in the FIFO.
flush
  Write this bit to 1 to clear the FIFO.

config register
^^^^^^^^^^^^^^^

+---+---+---+---+---+------------+-------------+---------------+
| 7 | 6 | 5 | 4 | 3 | 2          | 1           | 0             |
+---+---+---+---+---+------------+-------------+---------------+
| *reserved*        | stretching | trigger_end | trigger_start |
+-------------------+------------+-------------+---------------+

trigger_start
  When enabled, assert trigger signal when the transaction starts.
trigger_end
  When enabled, assert trigger signal when the transaction ends.
stretching
  When set to 1 (default), clock stretching support is enabled and the I2C slave
  may maintain SCL low during a transaction and external pull-up resistor on SCL
  is mandatory. When this bit is set to 0, clock stretching is disabled and the
  SCL signal is fully driven in push-pull by the I2C master peripheral: the
  external pull-up resistor on SCL can be omitted.

divisor register
^^^^^^^^^^^^^^^^

This 16-bits register controls the baudrate of the I2C peripheral. Write twice
to set MSB and LSB.

Effective baudrate is:

.. math::
    B = \frac{ F_{sys} }{ 4 \times (D+1) }

Where :math:`F_{sys}` is the system frequency (100 MHz) and :math:`D` the
divisor value. The value of :math:`D` for a given baudrate :math:`B` is:

.. math::
    D = \frac{ F_{sys} }{ 4 \times B } - 1

data register
^^^^^^^^^^^^^

This is the peripheral FIFO access register. Writing to this register will push
the bytes to be transmitted during the next transaction.

Once the transaction has been performed, two cases are possibles:

- all the bytes to be transmitted been poped from the FIFO, and received bytes
  have been pushed into the FIFO. Reading the FIFO until it is empty will return
  only the received bytes.

- a NACK have been received from the slave during the transaction: the FIFO
  will have the remaining bytes which have not been transmitted. Reading the
  FIFO is useless because no received bytes have been pushed due to the abortion
  of the transaction.

size registers
^^^^^^^^^^^^^^

This 16-bit register is accessing through size_h and size_l registers. Reading
this register will return the untransmitted byte count, which may help
identifying where a transaction has been NACKed by the slave.

Writing this register will set the number of bytes to be read during the next
transaction.

Note: there is no register for the number of bytes to be transmitted: this is
determined by the size of the FIFO.

