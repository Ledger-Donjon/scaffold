FPGA bus
========

The internal global bus connects all the peripherals together. This bus is
controlled by the serial bridge which is connected to the host computer with
the USB link. The bus can perform only two simple operations:

- Read a byte from a register,
- Write a byte to a register.

The bus works using many signals:

- 16-bits address: bus_address,
- Write assertion signal: bus_write
- 8-bits write data: bus_write_data,
- Read assertion signal: bus_read
- 8-bits read data: bus_read_data

Using different data wires for read and write operations makes conflicts
between modules impossible. Also, some FPGA devices may not allow internal
bidirectional wires.

All the signals of the bus are synchronized to the system clock, on rising
edges.


Register read cycle
-------------------

.. wavedrom::

    { "signal": [
        {"name": "clock", "wave": "P...."},
        {"name": "bus_address", "wave": "x=x..", "data": ["address"]},
        {"name": "bus_read", "wave": "010.."},
        {"name": "bus_read_data", "wave": "x.=x.", "data": ["data"]},
        {"name": "bus_write", "wave": "0...."},
        {"name": "bus_write_data", "wave": "x...."}
        ],
      "config": { "hscale": 1.5, "vscale": 1.5 }
    }

|

Peripherals connected to the bus must present valid data one clock cycle after
the `bus_read` signal is asserted. This allow using FIFO blocks with
*read-ahead* option disabled, which is more performant.

Register write cycle
--------------------
    
.. wavedrom::    
    
    { "signal": [
        {"name": "clock", "wave": "P...."},
        {"name": "bus_address", "wave": "x=x..", "data": ["address"]},
        {"name": "bus_read", "wave": "0...."},
        {"name": "bus_read_data", "wave": "x...."},
        {"name": "bus_write", "wave": "010.."},
        {"name": "bus_write_data", "wave": "x=x..", "data": ["data"]}
        ],
      "config": { "hscale": 1.5, "vscale": 1.5 }
    }

