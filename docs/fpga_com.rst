Communication protocol
======================

General architecture
--------------------

The FPGA has many embedded peripherals. Each peripheral has registers which can
be read/written to receive/send data and perform actions. Each register is
assigned a unique 16-bits address and is connected to the system data bus.

A bridge controller, inside the FPGA, controls the read and write operations on
the system data bus. This controller can be driven by a host computer using the
USB link, allowing the host computer to manipulate the registers connected to
the system data bus.

Protocol
--------

When connected to a host computer using a USB cable, the board is recognized as
a USB-to-Serial device from FTDI manufacturer. Baudrate is 2 Mbits/s, with one
stop bit and no parity check.

A very simple protocol is defined to perform read and write operations through
the serial device. To perform an operation, the following data must be sent to
Scaffold:

+----------------------+---------+----------------------+
| Command              | 1 byte  | Mandatory            |
+----------------------+---------+----------------------+
| Address              | 2 bytes | Mandatory            |
+----------------------+---------+----------------------+
| Polling address      | 2 bytes | When polling enabled |
+----------------------+---------+----------------------+
| Polling mask         | 1 byte  | When polling enabled |
+----------------------+---------+----------------------+
| Polling value        | 1 byte  | When polling enabled |
+----------------------+---------+----------------------+
| Size                 | 1 byte  | When size enabled    |
+----------------------+---------+----------------------+
| Data                 | N bytes | For write commands   |
+----------------------+---------+----------------------+

Bit 0 of command byte indicates if this is a read (0) or write (1) command.
Bit 1 indicates if size parameter is present (1 to enable size).
Bit 2 indicates if polling is requested for this command (1 to enable polling).
All other bits must be set to zero, otherwise the command is considered invalid
and Scaffold will enter error mode.

For write and read commands, a response is transmitted by the Scaffold board.
This response starts by the data bytes (for register read commands) and
terminates with a status byte. The status byte shall be equal to the size of the
processed data. If a command times out during polling, the returned status byte
will be lower than the size of the data.


Register polling
----------------

Read or write operations on registers can be conditioned to a given register
expected state. When polling is enabled, each read or write operation is
performed when the monitored register reaches a given value for some chosen
bits. Polling is enabled when bit 2 of command byte is 1. Read or write
operation is performed when ``(Register and Mask) = (Value and Mask)``.

Polling can be used for flow control when using a peripheral to process multiple
bytes. For instance, when using a SPI peripheral, polling can be used to wait
for incoming bytes.

The polled register can be different from the read or written register (two
different addresses can be passed in the command parameters: address and polling
address).


Polling timeout
---------------

Optionally, a timeout can be configured for polling operations. This is
particularly useful if receiving bytes from a peripheral is not guaranteed. When
the polling times out in a read operation, the remaining expected bytes are sent
by the board as zero. When the polling times out in a write operation, the
remaining bytes sent to the board are discarded by the bus bridge. The returned
acknowledge byte indicates the number of successfully processed bytes and will
be lower than the requested size in the command.

The timeout delay can be configured with a special command:

+----------------------+---------+----------------------+
| Command 0x08         | 1 byte  | Mandatory            |
+----------------------+---------+----------------------+
| Polling delay value  | 4 bytes | MSB first            |
+----------------------+---------+----------------------+

No response is expected after this command. The new delay value will be applied
for all the following commands. If the delay is set to zero, then the timeout is
disabled (which is the default).
