UART modules
============

The UART modules are configurable UARTs which can save and receive data.


Python API example
------------------

The following example shows how to send a message over UART from D0, and receive
it on D1 using a loop-back cable connecting D1 to D0.

.. code-block:: python

    uart = scaffold.uart0
    uart.baudrate = 9600

    scaffold.d0 << uart.tx
    uart.rx << scaffold.d1

    uart.flush() # Flush reception FIFO
    uart.write('Hello world!')
    print(uart.receive(12))

For more API documentation, see :class:`scaffold.UART`


Signals
-------

.. modbox::
    :inputs: rx
    :outputs: tx, trigger


Internal registers
------------------

+--------+--------+
| uart_0 | 0x0400 |
+--------+--------+

+---------------+-----------+-----+
| base + 0x0000 | status    | R   |
+---------------+-----------+-----+
| base + 0x0001 | control   | W   |
+---------------+-----------+-----+
| base + 0x0002 | config    | W   |
+---------------+-----------+-----+
| base + 0x0003 | divisor   | W   |
+---------------+-----------+-----+
| base + 0x0004 | data      | R/W |
+---------------+-----------+-----+

status register
^^^^^^^^^^^^^^^

+---+---+---+---+---+-------+--------------+-------+
| 7 | 6 | 5 | 4 | 3 | 2     | 1            | 0     |
+---+---+---+---+---+-------+--------------+-------+
| *reserved*        | empty | parity_error | ready |
+-------------------+-------+--------------+-------+

empty
  1 when reception FIFO is empty.
parity_error
  Set to 1 when a parity error occurred. Write this flag to 0 to clear it.
ready
  1 when UART is ready to transmit a new byte.

control register
^^^^^^^^^^^^^^^^

+---+---+---+---+---+---+---+-------+
| 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0     |
+---+---+---+---+---+---+---+-------+
| *reserved*                | flush |
+---------------------------+-------+

clear
  Write this bit to 1 to flush the reception FIFO memory.

config register
^^^^^^^^^^^^^^^

+---+---+---+---+---------+-----------+---+---------+
| 7 | 6 | 5 | 4 | 3       | 2         | 1 | 0       |
+---+---+---+---+---------+-----------+---+---------+
| *reserved*    | trigger | stop_bits | parity_mode |
+---------------+---------+-----------+-------------+

trigger
  When set to 1, trigger signal will be asserted at the end of the transmission
  of a byte. Default is 0.

stop_bits
  Number of stop bits. 0 for 1 stop bit, 1 for 2 stop bits.

parity_mode
  1 for odd parity bit, 2 for even parity bit, 0 to disable parity bit. Value 3
  is forbidden and has undefined behavior.

divisor register
^^^^^^^^^^^^^^^^

The divisor register is a 16 bits register. Write twice at the register address
to load the 16 bits value (MSB first). This register sets the baudrate of the
UART. The minimum allowed value is 0x0001. Setting value to 0x0000 has undefined
behavior. Changing this register during transmission will corrupt outgoing or
incoming bytes.

Effective baudrate is:

.. math::
    B = \frac{ F_{sys} }{ D + 1 }

Where :math:`F_{sys}` is the system frequency (100 MHz) and :math:`D` the
divisor value. The value of :math:`D` for a given baudrate :math:`B` is:

.. math::
    D = \frac{ F_{sys} }{ B } - 1

Below is a table showing the divisor for common baudrates:

.. include:: uart_baudrates.inc

data register
^^^^^^^^^^^^^

Reading the data register will return the received bytes. The received bytes are
stored in a FIFO memory.

Writing the data register will send a byte over the UART. The module has no
memory for the bytes to be sent. Writing to data register must be performed with
polling mode to ensure the UART is ready to transmit each byte.
