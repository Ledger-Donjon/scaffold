ISO-7816 module
===============

The ISO-7816 module is a reader interface allowing communication with any
ISO-7816 device.

The ISO-7816 peripheral is a very low level interface. It is like an enhanced
UART with few features. Protocol management (ATR retrieval, byte convention and
APDU exchanges) is implemented in the :class:`scaffold.iso7816.Smartcard`.

.. warning::
    Current implementation has not been tested with a lot of cards. Don't
    hesitate to report issues!

Python API example
------------------

The following example shows how to reset a card, retrieve the ATR and send an
APDU command.

.. code-block:: python

    from scaffold import Scaffold
    from scaffold.iso7816 import Smartcard

    sc = Smartcard(Scaffold('/dev/ttyUSB0'))
    # Power-on the card
    sc.scaffold.power.dut = 1
    # Reset the card and retrieve ATR
    atr = sc.reset()
    # Send a SELECT command and get the response
    response = sc.apdu(b'\xa0\xa4\x00\x00\x02\x3f\x00')

    # For convenience, APDUs can be also be exchanged as strings
    response = sc.apdu_str('a0a40000023f00')


Signals
-------

.. modbox::
    :inputs: io_in
    :outputs: io_out, clk, trigger*

Internal registers
------------------

+--------+-----------+-----+
| 0x0500 | status    | R   |
+--------+-----------+-----+
| 0x0501 | control   | W   |
+--------+-----------+-----+
| 0x0502 | config    | W   |
+--------+-----------+-----+
| 0x0503 | divisor   | W   |
+--------+-----------+-----+
| 0x0504 | etu       | W   |
+--------+-----------+-----+
| 0x0505 | data      | R/W |
+--------+-----------+-----+

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
  1 when transceiver is ready to transmit a new byte.

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

+---+---+----+---+---------+--------------+------------+------------+
| 7 | 6 | 5  | 4 | 3       | 2            | 1          | 0          |
+---+---+----+---+---------+--------------+------------+------------+
| *reserved* | parity_mode | trigger_long | trigger_rx | trigger_tx |
+------------+-------------+--------------+------------+------------+

parity_mode
  - 0b00: Even parity (standard and default)
  - 0b01: Odd parity
  - 0b10: Parity bit always 0
  - 0b11: Parity bit always 1

trigger_tx
  When set to 1, trigger signal will be asserted at the end of bytes
  transmission, for one clock cycle long.

trigger_rx
  When set to 1, trigger signal will be asserted at the beginning of bytes
  reception, for one clock cycle long.

trigger_long
  When set to 1, trigger signal will be asserted at the end of bytes
  transmission, and cleared at the beginning of next byte reception or
  transmission.

divisor register
^^^^^^^^^^^^^^^^

The divisor register controls the ISO-7816 clock frequency.

Effective clock frequency is:

.. math::
    F = \frac{F_{sys}}{(D+1)*2}

Where :math:`F_{sys}` is the system frequency and :math:`D` the divisor value.
The value of :math:`D` for a target frequency :math:`F` is:

.. math::
    D = \frac{ F_{sys} }{ 2*F } - 1

etu register
^^^^^^^^^^^^

This register defines the ETU value for ISO-7816 communication. Add 1 to get
effective ETU value. This register has 11 bits. Write this register twice to
load the 11 bits, MSB first. Default value is 371, for the ETU 372.

data register
^^^^^^^^^^^^^

Reading the data register will return the received bytes. The received bytes are
stored in a FIFO memory.

Writing the data register will send a byte. The module has no memory for the
bytes to be sent. Writing to data register must be performed with polling over
status register to ensure the transceiver is ready to transmit each byte.
