Clock module
============

The clock module can generate a clock synthetized from the FPGA system clock,
using a 8-bits clock divisor. The frequency can be changed during a short
amount of time by switching to a secondary clock divisor in order to generate
clock glitches.

.. warning::

    This module is still experimental and may be subject to changes.


Python API example
------------------

.. code-block:: python

    clock = scaffold.clock0
    clock.frequency = 1e6
    clock.glitch_frequency = 4e6
    clock.glitch_count = 20  # Number of glitching clock edges
    clock.out >> scaffold.d0
    clock.glitch << scaffold.d1  # Glitch trigger

For more API documentation, see :class:`scaffold.Clock`


Signals
-------

.. modbox::
    :inputs: glitch
    :outputs: out


Internal registers
------------------

+--------+--------+
| clock0 | 0x0a00 |
+--------+--------+

+---------------+-----------+-----+
| base + 0x0000 | config    | W   |
+---------------+-----------+-----+
| base + 0x0001 | divisor_a | W   |
+---------------+-----------+-----+
| base + 0x0002 | divisor_b | W   |
+---------------+-----------+-----+
| base + 0x0003 | count     | W   |
+---------------+-----------+-----+

config register
^^^^^^^^^^^^^^^

+---+---+---+---+---+---+---+---+
| 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 |
+---+---+---+---+---+---+---+---+
| *reserved*                    |
+-------------------------------+

divisor_a register
^^^^^^^^^^^^^^^^^^

This 8-bits register can be configured to adjust the primary clock frequency.
Effective frequency is

Effective clock frequency is:

.. math::
    F = \frac{F_{sys}}{(D+1)*2}

Where :math:`F_{sys}` is the system frequency and :math:`D` the divisor value.
The value of :math:`D` for a target frequency :math:`F` is:

.. math::
    D = \frac{ F_{sys} }{ 2*F } - 1

The highest possible frequencies are 50 MHz, 25 MHz, 16.66 MHz, 12.5 MHz... The
lowest possible frequency is 196.08 kHz.

divisor_b register
^^^^^^^^^^^^^^^^^^

This 8-bits register can be configured to adjust the secondary clock frequency.
Frequency calculation is the same as `divisor_a` register.

count register
^^^^^^^^^^^^^^

This 8-bits register configures the number :math:`N` of glitched clock edges,
where :math:`N` is the register value plus one.
