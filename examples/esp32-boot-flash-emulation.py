#!/usr/bin/env python3
#
# This script emulates the flash memory behavior during boot of the ESP32. It
# does not emulate a full flash device, but only responds to the first received
# commands by sending predefined answers.
#
# Reference paper: Unlimited Results: Breaking Firmware Encryption of ESP32-V3
# from Karim M. Abdellatif, Olivier Heriveaux, and Adrian Thillard.
#
# The ESP32 communicates with the flash using SPI in mode 0.
#
# The MCU starts by sending the command ab000000h (Read Device ID) and receives a
# response 15h.
#
# The MCU then send the command 03001000h (Read Data Bytes) to read the content
# of the memory at address 0x1000. The response from the memory follows (32
# bytes).

from time import sleep
from scaffold import Scaffold, SPIMode, TimeoutError

s = Scaffold()
uart = s.uart0
uart.rx << s.d1
uart.tx >> s.d0
uart.baudrate = 115200
s.power.dut_trigger >> s.d5

sig_nrst = s.d2
sig_boot = s.d6

spi = s.spi0
spi.mode = SPIMode.SLAVE
spi.sck << s.d10
spi.ss << s.d11
spi.miso >> s.a0
spi.miso >> s.d9
spi.phase = 0
spi.polarity = 1

while True:
    print("Booting")
    s.power.dut = 0
    sig_nrst << 0
    sig_boot << 1
    sleep(0.1)
    spi.clear()
    spi.append(bytes.fromhex("0000000015"))
    spi.append(
        bytes.fromhex(
            "00000000bd56f3bff668db0480ae0e9006a45de91eab0f5b7628399ecf5d40ae"
            "b3bf96b5"
        )
    )
    spi.append(
        bytes.fromhex(
            "00000000bd56f3bff668db0480ae0e9006a45de91eab0f5b7628399ecf5d40ae"
            "b3bf96b5"
        )
    )
    s.power.dut = 1
    uart.flush()
    sleep(0.05)
    sig_nrst << 1

    sleep(0.05)
    s.timeout = 0.5
    data = None
    try:
        data = uart.receive(1000)
    except TimeoutError as e:
        data = e.data
    if data is not None:
        print(data.decode())
