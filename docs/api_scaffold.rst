Main Scaffold API
=================

This page documents the main classes and methods of the Scaffold Python API.

Manipulating the attributes of the different modules of a :class:`Scaffold`
instance will read or write in the FPGA registers. Some registers may be cached
by the Python API, so reading them does not require any communication with the
board and thus can be fast.

.. automodule:: scaffold

.. autoclass:: Scaffold
    :members: __init__

.. autoclass:: Signal
    :special-members: __init__, __str__, __lshift__
    :members:

.. autoclass:: IO
    :members:

.. autoclass:: IOMode
    :members:
    :undoc-members:

.. autoclass:: Pull
    :members:
    :undoc-members:

.. autoclass:: UARTParity
    :members:
    :undoc-members:

.. autoclass:: UART
    :members:

.. autoclass:: ISO7816
    :members:

.. autoclass:: I2C
    :members:

.. autoclass:: SPI
    :members:

.. autoclass:: PulseGenerator
    :members:

.. autoclass:: Chain
    :members:

.. autoclass:: LEDs
    :members:

.. autoclass:: Power
    :members:
