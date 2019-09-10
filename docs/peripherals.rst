Scaffold peripherals
====================

The FPGA system has many modules wrapping communication peripherals or utility
hardware. Each module exposes registers which can be read or written. Each
register has a unique address.

Every module has input and output signals. Thoose signals are illustrated in
each peripheral documentation like the following example:

.. modbox::
    :inputs: input_a, input_b
    :outputs: output_a, output_b, output_c*

Input and output signals can be routed to Scaffold I/Os. Some special output
signals have a feedback path and can be routed to other peripheral inputs.
Thoose are usually trigger signals and are represented with an extra arrow like
the signal `output_c` in the example above.

.. toctree::
  :caption: Contents:

   I/Os <ios.rst>
   UART <uart_module.rst>
   Power <power_module.rst>
   LEDs <leds_module.rst>
   ISO7816 <iso7816_module.rst>
   I2C <i2c_module.rst>
   SPI <spi_module.rst>
   Pulse generator <pulse_generator_module.rst>
   Clock generator <clock_module.rst>
   Chain triggers <chain_module.rst>
   Version <version_module.rst>
