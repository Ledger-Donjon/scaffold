# FTDI EEPROM programming

Disconnect all USB-to-serial devices but the Scaffold board.

Install the package `ftdi_eeprom` and execute the `flash.sh` script as root to
program the EEPROM memory of the Scaffold FT232H device. This will configure
the vendor and description strings to respectively "Ledger" and "Scaffold".

Configuring the EEPROM is optional, but when programmed, the software is able
to recognize automatically which serial port corresponds to the Scaffold board.
