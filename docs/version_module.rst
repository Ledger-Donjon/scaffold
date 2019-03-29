Version module
==============

This module helps the software identifying the board. When
:class:`scaffold.Scaffold` connects to the board, the version string is
automatically queried and cached in the version attribute.


Python API example
------------------

.. code-block:: python

    # Read cached version string
    # Shall return something like 'scaffold-1.0'
    print(scaffold.version)


Internal registers
------------------

+--------+------+---+
| 0x0100 | data | R |
+--------+------+---+


data register
^^^^^^^^^^^^^

Reading multiple times this register will return the version string of the
board. A null character indicates the beginning (and end) of the version
string. Latest version string is "scaffold-1.0".
