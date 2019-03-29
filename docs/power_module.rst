Power module
============

The power module controls two power supplies: the "platform" socket power
supply and the "dut" socket power supply. Each power supply can be turned
on and off. 

A positive input pulse on the "tearing" input of the board (SMA connector on
the left side) will automatically power-off both power supplies.


Python API example
------------------

.. code-block:: python

    # Turn DUT on
    scaffold.power.dut = 1 # True is also valid
    # Check current power supply status
    # (it may be off due to external tearing)
    if scaffold.power.dut: # Will return 0 or 1
        print('DUT is still ON')
    # Turn DUT off
    scaffold.power.dut = 0 # False is also valid

The following example controls both power supplies at the same time.

.. code-block:: python

    # Turn on all power supplies
    scaffold.power.all = 0b11 
    # Check current power status of both power supplies
    if (scaffold.power.all == 0b11):
        print('Both power supplies are ON')
    # Turn off all power supplies
    scaffold.power.all = 0b00

It is also possible to output the power enable signal to one of the IOs, for
triggering or monitoring:

.. code-block:: python

    scaffold.d0 << scaffold.power.dut_trigger

For more API documentation, see :class:`scaffold.Power`


Internal registers
------------------

+---------+--------+
| control | 0x0600 |
+---------+--------+


control register
^^^^^^^^^^^^^^^^

+---+---+---+---+---+---+----------+-----+
| 7 | 6 | 5 | 4 | 3 | 2 | 1        | 0   |
+---+---+---+---+---+---+----------+-----+
| *reserved*            | platform | dut |
+-----------------------+----------+-----+

dut
  Write 1 to enable the DUT socket power supply. Write 0 to disable. This bit
  is cleared when the tearing input is high.
platform
  Write 1 to enable the platform socket power supply. Write 0 to disable. This
  bit is cleared when the tearing input is high.
