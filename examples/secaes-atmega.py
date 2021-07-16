#!/usr/bin/python3
#
# This file is part of Scaffold
#
# Scaffold is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#
# Copyright 2019 Ledger SAS, written by Manuel San Pedro


"""
Example script to communicate with a ATmega8515 running the code from
https://github.com/ANSSI-FR/secAES-ATmega8515
"""


from scaffold import Scaffold
from scaffold.iso7816 import Smartcard
from binascii import hexlify

class SecAesAtMega(Smartcard):

    def set_key(self, key=[0]*16):        
        assert len(key)==16
        answer = self.apdu( bytes([0x80,0x10,0x00,0x00,0x10]+list(key)))
        return answer == bytearray(b'\x90\x00')

    def get_key(self):
        answer = self.apdu( bytes([0x80,0x12,0x00,0x00,0x10]))
        assert answer[-2:] == bytearray(b'\x90\x00')
        assert len(answer) == 16 + 2
        return list(answer[:16])

    def set_input(self, input=[0]*16):
        
        assert len(input)==16
        answer = self.apdu( bytes([0x80,0x20,0x00,0x00,0x10]+list(input)))
        return answer == bytearray(b'\x90\x00')

    def get_input(self):
        answer = self.apdu( bytes([0x80,0x22,0x00,0x00,0x10]))
        assert answer[-2:] == bytearray(b'\x90\x00')
        assert len(answer) == 16 + 2
        return list(answer[:16])
    
    def set_mask(self, mask=[0]*18):        
        assert len(mask)==18
        answer = self.apdu( bytes([0x80,0x30,0x00,0x00,0x12]+list(mask)))
        return answer == bytearray(b'\x90\x00')

    def get_mask(self):
        answer = self.apdu( bytes([0x80,0x32,0x00,0x00,0x12]))
        assert answer[-2:] == bytearray(b'\x90\x00')
        assert len(answer) == 18 + 2
        return list(answer[:18])


    def get_output(self):
        answer = self.apdu( bytes([0x80,0x42,0x00,0x00,0x10]))
        assert answer[-2:] == bytearray(b'\x90\x00')
        assert len(answer) == 16 + 2
        return list(answer[:16])
        
    def launch_aes(self):
        return self.apdu( bytes([0x80,0x52,0x00,0x00,0x00]), trigger='a') == bytearray(b'\x90\x00')
    
    def test(self, n=5):
        import numpy as np
        from Crypto.Cipher import AES
        import time

        for i in range(n):
            start = time.time()
            key = np.random.randint(0,256,16,np.uint8)
            input = np.random.randint(0,256,16,np.uint8)
            mask = np.random.randint(0,256,18,np.uint8)

            self.set_key(key)
            self.set_input(input)
            self.set_mask(mask)
            
            assert all(key == self.get_key())
            assert all(input == self.get_input())
            assert all(mask == self.get_mask())

            self.launch_aes()
            output = self.get_output()

            assert AES.new(bytes(key), AES.MODE_ECB).encrypt(bytes(input)) == bytes(output)
            print("Test %d/%d OK, %fs"% (i+1,n,time.time()-start))


scaffold = Scaffold()
sc = SecAesAtMega(scaffold)

# Output trigger on D5
scaffold.d5 << scaffold.iso7816.trigger

# ISO-7816 clock drives MCU clock frequency directly.
# We can overclock it to run the card faster!
# It also works up to 25 MHz.
scaffold.iso7816.clock_frequency = 10e6

scaffold.power.dut = 1
atr = sc.reset()
print('ATR: ' + hexlify(atr).decode())
info = sc.find_info(allow_web_download=True)

sc.test()

