Pulse generator modules
=======================

Each pulse generator allows generating one or multiple pulse when an input
signal is asserted. Delay, width, interval and number of pulses are all
programmable using the registers of the module.

Below is an example of two generated pulses, to show what delays can be
configured. Delays are a multiple of the system clock period.

.. wavedrom::

    {"signal": [
      {"name": "start", "wave": "010............"},
      {"name": "out", "wave": "0.....1.0..1.0."},
      {"node": "..a...b.c..d"}
      ],
      "edge": ["a<->b D+1", "b<->c W+1", "c<->d I+1"]
    }


Python API example
------------------

.. code-block:: python

    pgen = scaffold.pgen0
    pgen.width = 100e-9  # 100 ns
    pgen.count = 1
    pgen.delay = 10e-6  # 10 µs
    pgen.start << scaffold.d0
    pgen.out >> scaffold.d1


Signals
-------

.. modbox::
    :inputs: start
    :outputs: out

Internal registers
------------------

+-------------------+--------+
| pulse_generator_0 | 0x0300 |
+-------------------+--------+

+---------------+-----------+-----+
| base + 0x0000 | status    | R   |
+---------------+-----------+-----+
| base + 0x0001 | control   | W   |
+---------------+-----------+-----+
| base + 0x0002 | config    | W   |
+---------------+-----------+-----+
| base + 0x0003 | delay     | W   |
+---------------+-----------+-----+
| base + 0x0004 | interval  | W   |
+---------------+-----------+-----+
| base + 0x0005 | width     | W   |
+---------------+-----------+-----+
| base + 0x0006 | count     | W   |
+---------------+-----------+-----+

status register
^^^^^^^^^^^^^^^

+---+---+---+---+---+---+---+-------+
| 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0     |
+---+---+---+---+---+---+---+-------+
| *reserved*                | ready |
+---------------------------+-------+

ready
  1 when the pulse generator is in idle mode, ready to fire. 0 during pulse
  generation.

control register
^^^^^^^^^^^^^^^^

+---+---+---+---+---+---+---+------+
| 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0    |
+---+---+---+---+---+---+---+------+
| *reserved*                | fire |
+---------------------------+------+

fire
  Write this bit to 1 to fire the pulse generation.


config register
^^^^^^^^^^^^^^^

+---+---+---+---+---+---+---+----------+
| 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0        |
+---+---+---+---+---+---+---+----------+
| *reserved*                | polarity |
+---------------------------+----------+

polarity
  Pulse polarity. When 1, pulse is negative.


delay register
^^^^^^^^^^^^^^

24 bits register storing the delay before the pulse. If the value of this
register is :math:`D`, the delay is :math:`1/F_{sys} * (D+1)`. Write 3 times
this register to load the 24 bits word, MSB first.

interval register
^^^^^^^^^^^^^^^^^

24 bits register storing the delay after the pulse and before the next one
(when using multiple pulses). If the value of this register is :math:`I`, the
interval is :math:`1/F_{sys} * (I+1)`. Write 3 times this register to load the
24 bits word, MSB first.

width register
^^^^^^^^^^^^^^

24 bits register storing the width of the pulses to be generated. If the value
of this register is :math:`W`, the pulse width is :math:`1/F_{sys} * (W+1)`.
Write 3 times this register to load the 24 bits word, MSB first.

count register
^^^^^^^^^^^^^^

16 bits register storing the number of pulses to be generated. If the value of
this register is :math:`N`, :math:`N+1` pulses are generated. 
