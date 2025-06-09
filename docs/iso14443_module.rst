ISO-14443 module
================

The ISO-14443 module is a reader interface allowing communication with any
ISO-14443 contactless card.

This peripheral only handles frames transmission and decoding, and it must be
used with the dedicated NFC daughterboard which is responsible for the radio
modulation and demodulation. More precisely, this daughterboard embeds a
TRF7960A integrated circuit which acts as the RF front-end.

.. warning::
   Only ISO-14443 type A is supported at the moment.

Signals
-------

.. modbox::
   :inputs: rx, clock_13_56, tearing
   :outputs: tx, trigger*

Internal registers
------------------

+--------+----------------+-----+
| 0x0500 | status/control | R/W |
+--------+----------------+-----+
| 0x0501 | config         | W   |
+--------+----------------+-----+
| 0x0502 | data           | R/W |
+--------+----------------+-----+
| 0x0503 | timeout        | W   |
+--------+----------------+-----+

status and control register
^^^^^^^^^^^^^^^^^^^^^^^^^^^

+-------+---+---+---+---+---+-----------+----------+-------+
|       | 7 | 6 | 5 | 4 | 3 | 2         | 1        | 0     |
+-------+---+---+---+---+---+-----------+----------+-------+
| read  | *reserved*                               | busy  |
+-------+-------------------+-----------+----------+-------+
| write | *reserved*        | power_off | power_on | start |
+-------+-------------------+-----------+----------+-------+

busy
  Reading this bit returns 1 when a transmission is ongoing.
start
  Writing 1 to this bit will start the transmission of patterns pushed in the
  FIFO.
power_on
  Writing to 1 enables RF power.
power_off
  Writing to 1 disables RF power by constant modulation.
  Works only for ISO-14443 type A.

Note: Starting a transmission automatically flushes the reception FIFO.

config register
^^^^^^^^^^^^^^^
  
+----------+----------+---+--------+--------------+------------+----------------+------------------+
| 7        | 6        | 5 | 4      | 3            | 2          | 1              | 0                |
+----------+----------+------------+--------------+------------+----------------+------------------+
| polarity | use_sync | *reserved* | trigger_long | trigger_rx | trigger_tx_end | trigger_tx_start |
+----------+----------+------------+--------------+------------+----------------+------------------+

trigger_start
  When set to 1, trigger signal will be asserted at the beginning of
  transmission, for one clock cycle long. Can be combined with trigger_end and
  trigger_rx.
trigger_end
  When set to 1, trigger signal will be asserted at the end of transmission,
  for one clock cycle long. Can be combined with trigger_start and trigger_rx.
trigger_rx
  When set to 1, trigger signal will be asserted when the card starts to
  respond. Can be combined with trigger_start and trigger_end. Ignored if
  trigger_long is set.
trigger_long
  When set to 1, start or end signals will raise the trigger and keep it high
  until the card starts to respond, or the response timeout expires.
use_sync
  When set to 1, the transmitter will synchronize the transmission to the 13.56
  MHz clock issued from the daughterboard. This option reduces the jitter.
polarity
  Can be modified to set tx modulation signal polarity. Use value 1 for the
  reference Scaffold NFC daughterboard. May be changed if RF front-end is
  different.

data register
^^^^^^^^^^^^^

+-------+---+---+---+---+---+---+---+------------+
|       | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0          |
+-------+---+---+---+---+---+---+---+------+-----+
| read  | size_hint             | rx_empty | bit |
+-------+-----------------------+----------+-----+
| write | *reserved*            | pattern        |
+-------+-----------------------+----------------+

Writing to this register pushes in the FIFO a pattern to be transmitted. The
pattern field is encoded as this:

- 10: Miller sequence X (type A)
- 11: Miller sequence Y (type A) or NRZ bit 1 symbol (type B)
- 01: Miller sequence Z (type A)
- 00: NRZ bit 0 symbol (type B)

Up to 2048 patterns can be pushed in the FIFO. When all patterns have been
loaded, transmission can start by writting to the control register.

Reading this register pops the lastest bit stored in the reception FIFO and
returns the following information:

bit:
  Oldest received bit.
rx_empty:
  True if the FIFO is empty. False if it contains bits (before the actual
  read).
size_hint:
  Hints how many bits are stored in the FIFO. 0 means FIFO has from 0 to 63
  elements, 1 means FIFO has from 64 to 127 elements, etc. Maximum value is
  63, which means FIFO has from 4032 to 4095 elements.

The rx_empty and size_hint fields helps the software to read the correct amount
of received data with minimizing the number of requests to the board and
therefore reducing the response reading latency.

timeout register
^^^^^^^^^^^^^^^^

This 24-bit register defines how long the reader can awaits for a response from
the contactless card. After transmission and once the timeout expires, the
ISO-14443 peripheral returns to idle state.

Write three bytes, MSB first, to set the timeout. Each unit corresponds to
9.44 µs. The default setting is 2 seconds.
