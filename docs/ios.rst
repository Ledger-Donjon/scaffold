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
    scaff.uart0.send('Hello world!')

It is also possible to read the current electrical state of an input of the
board:

.. code-block:: python

    if scaff.d0.value == 1:
        print('Input is high!')

Finally, you can watch for events on an input. The event will be asserted if a 1
is detected. This works for short pulses (> 10 ns).

.. code-block:: python

    # Reset event flag
    scaff.d0.event = 0
    # Wait some time
    time.sleep(1)
    # Lookup event register to know if a pulse has been received
    if scaff.d0.event == 1:
        print('Event detected!')


Internal registers
------------------

+--------+---------+---+
| 0xe000 | value_a | R |
+--------+---------+---+
| 0xe001 | event_a | R |
+--------+---------+---+
| 0xe010 | value_b | R |
+--------+---------+---+
| 0xe011 | event_b | R |
+--------+---------+---+

value_a & event_a registers
^^^^^^^^^^^^^^^^^^^^^^^^^^^
+----+----+----+----+----+----+----+----+
|  7 |  6 |  5 |  4 |  3 |  2 |  1 |  0 |
+----+----+----+----+----+----+----+----+
| d1 | d0 | c1 | c0 | b1 | b0 | a1 | a0 |
+----+----+----+----+----+----+----+----+

value_b & event_b registers
^^^^^^^^^^^^^^^^^^^^^^^^^^^
+----+----+----+----+----+----+----+----+
|  7 |  6 |  5 |  4 |  3 |  2 |  1 |  0 |
+----+----+----+----+----+----+----+----+
| d9 | d8 | d7 | d6 | d5 | d4 | d3 | d2 |
+----+----+----+----+----+----+----+----+
