Chain modules
=============

Chain modules are utility blocks which can be used to build chained-triggers.
Each chain module has 3 event inputs, and a trigger output. The trigger output
is asserted when the 3 inputs have been sequentially triggered.

.. warning::

    This module is still experimental and may be subject to changes.


Python API example
------------------

.. code-block:: python

    chain = scaffold.chain0
    chain.event0 << scaffold.d0
    chain.event1 << scaffold.d1
    chain.event2 << 1  # Don't use this one

For more API documentation, see :class:`scaffold.Chain`


Signals
-------

.. modbox::
    :inputs: event0, event1, event2
    :outputs: trigger


Internal registers
------------------

+--------+--------+
| chain0 | 0x0900 |
+--------+--------+
| chain1 | 0x0910 |
+--------+--------+

+---------------+---------+-----+
| base + 0x0000 | control | W   |
+---------------+---------+-----+

control register
^^^^^^^^^^^^^^^^

+---+---+---+---+---+---+---+-------+
| 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0     |
+---+---+---+---+---+---+---+-------+
| *reserved*                | rearm |
+---------------------------+-------+

rearm
  Write this bit to 1 to arm the chain trigger.

