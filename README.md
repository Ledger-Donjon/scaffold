[![Documentation Status](https://readthedocs.org/projects/donjonscaffold/badge/?version=latest)](https://donjonscaffold.readthedocs.io/en/latest/?badge=latest)

# Board status

Scaffold v1 board is currently a prototype and have a few issues we are
currently fixing. The new v1.1 version has been released and will soon be
tested.

- Reworked the adjustable regulators to fix stability issues and bad
  potentiometer routing.
- Replaced daughter-boards connectors with standard HE10 connectors and updated
  the pinout.
- Fixed glitching protection resistors value from 10 kOhm to 1 kOhm.
- Changed SMA connectors for better test points accessibility.
- Removed C0 and C1 outputs and renamed A0, A1, B0, and B1 to A0, A1, A2 and A3.
  Each Ax output has now its own voltage level translator.
- Removed CLOCK SMA connector.
- Added programmable pull-up or pull-down resistors for D0, D1 and D2.
- Added jumper to short the current measurement resistor.
- Added 50 Ohm resistor to the analog amplifier output.
- Improved tearing reactivity.
- Reworked power and error LEDs.
- Improved schematics readability and translated comments to English.
- Improved silkscreen.
- Board size has been slightly reduced.

# Scaffold

Scaffold is an electronic motherboard designed for security evaluation of
integrated circuits and embedded platforms. The board can be controlled through
USB using the Python3 API, enabling easy automation of tests.

![Scaffold board pictures](docs/pictures/board-anim.gif)

The FPGA architecture runs at 100 MHz and embeds many peripherals:

- UART,
- I2C (master),
- ISO7816 (master),
- Power supply controllers for each evaluation socket,
- Delay and pulse generators with 10 ns resolution
- And more to come in the future!

The board also integrates an 11X analog amplifier with 200 MHz bandwidth for
power measurement. The on-board shunt resistor can be tuned from 0 to
100 Ohms.

Scaffold is able to operate from 1.5V to 3.3V devices: power supplies and I/O
bank voltage can be tuned thanks to adjustable voltage regulators. Scaffold can
be powered from USB or external power supplies.

Six special I/Os can generate 5V pulses, which are compatible with
*ALPhANOV PDM* laser sources (50 Ohm TTL).

## Documentation

API documentation is available on [Read the Docs](https://donjonscaffold.readthedocs.io).

## Licensing

Scaffold is released under GNU Lesser General Public Licence version 3 (LGPLv3).
See COPYING and COPYING.LESSER for license details.

