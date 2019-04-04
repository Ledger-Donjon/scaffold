I/Os
====

The Scaffold Python API allows controlling and reading the I/Os of the board.
This can be useful, for instance, to control the reset signal of a device under
test. The following example shows how easy this can be done.

.. code-block:: python

    # Toggle D0 every second.
    for i in range(10):
        scaffold.d0 << 0
        time.sleep(1)
        scaffold.d0 << 1
        time.sleep(1)

    # Put D0 in high impedance state
    scaffold.d0 << None
    time.sleep(1)

    # Connect the output to the internal UART peripheral TX signal, and send a
    # message !
    scaffold.d0 << scaffold.uart0.tx
    scaffold.uart0.send('Hello world!')

It is also possible to read the current electrical state of an input of the
board:

.. code-block:: python

    if scaffold.d0.value == 1:
        print('Input is high!')

Finally, you can watch for events on an input. The event will be asserted if a 1
is detected. This works for short pulses (> 10 ns).

.. code-block:: python

    # Reset event flag
    scaffold.d0.event = 0
    # Wait some time
    time.sleep(1)
    # Lookup event register to know if a pulse has been received
    if scaffold.d0.event == 1:
        print('Event detected!')
        scaffold.d0.clear_event()

.. warning::
    I/Os internals have been refactored in 0.3. Registers are not the same as in
    0.2. Current API supports both 0.2 and 0.3 versions.

Internal registers
------------------

+----+-------------------+
| a0 | 0xe000            |
+----+-------------------+
| a1 | 0xe010            |
+----+-------------------+
| b0 | 0xe020            |
+----+-------------------+
| b1 | 0xe030            |
+----+-------------------+
| c0 | 0xe040            |
+----+-------------------+
| c1 | 0xe050            |
+----+-------------------+
| dn | 0xe060 + 0x10 * n |
+----+-------------------+

+---------------+--------+-----+
| base + 0x0000 | value  | R/W |
+---------------+--------+-----+
| base + 0x0001 | config | W   |
+---------------+--------+-----+

value register
--------------

+---+---+---+---+---+---+-------+-------+
| 7 | 6 | 5 | 4 | 3 | 2 | 1     | 0     |
+---+---+---+---+---+---+-------+-------+
| *reserved*            | event | value |
+-----------------------+-------+-------+

value
  Reading this bit will return current logical state on the I/O.
  Setting this bit has no effect.
event
  This bit is set to 1 when the I/O logical state changes. It can be reset by
  writing 0 to it.

config register
---------------

+---+---+---+---+---+---+---+---+
| 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 |
+---+---+---+---+---+---+---+---+
| *reserved*            | mode  |
+-----------------------+-------+

This register allows customizing the output mode of an I/O.

+------+----------------------------------------------------------------------+
| mode | Description                                                          |
+------+----------------------------------------------------------------------+
| 0    | **Auto**                                                             |
|      |                                                                      |
|      | The pin is driven by the routed peripheral.                          |
+------+----------------------------------------------------------------------+
| 1    | **Open-drain**                                                       |
|      |                                                                      |
|      | The pin is driven by the routed peripheral, but always acts as an    |
|      | open-collector.                                                      |
+------+----------------------------------------------------------------------+
| 2    | **Push-only**                                                        |
|      |                                                                      |
|      | The pin is driven by the routed peripheral, but is active only when  |
|      | a one is outputed.                                                   |
+------+----------------------------------------------------------------------+
