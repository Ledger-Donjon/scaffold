-- This file is part of Scaffold
--
-- Scaffold is free software: you can redistribute it and/or modify
-- it under the terms of the GNU Lesser General Public License as published by
-- the Free Software Foundation, either version 3 of the License, or
-- (at your option) any later version.
--
-- This program is distributed in the hope that it will be useful,
-- but WITHOUT ANY WARRANTY; without even the implied warranty of
-- MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
-- GNU Lesser General Public License for more details.
--
-- You should have received a copy of the GNU Lesser General Public License
-- along with this program.  If not, see <https://www.gnu.org/licenses/>.
--
--
-- Copyright 2019 Ledger SAS, written by Olivier Hériveaux


library ieee;
use ieee.std_logic_1164.all;


package common_pkg is

    subtype byte_t is std_logic_vector(7 downto 0);
    subtype address_t is std_logic_vector(15 downto 0);
    type std_logic_vector_array_t is array (natural range <>) of
        std_logic_vector;

    -- Type for tristate signals.
    -- Bit 0 is the output enable signal.
    -- Bit 1 is the signal value.
    subtype tristate_t is std_logic_vector(1 downto 0);
    type tristate_array_t is array (natural range <>) of
        std_logic_vector(1 downto 0);

    -- Regroups the input signals of the system bus.
    type bus_in_t is record
        -- Bus address. Selects the register to be read or written.
        address: std_logic_vector(15 downto 0);
        -- Bus write control signal. When high, a write cycle is triggered and
        -- the value on bus_write_data written in the register at the address
        -- bus_address.
        write: std_logic;
        -- Data to be written.
        write_data: std_logic_vector(7 downto 0);
        -- Bus read control signal. When high, a read cycle is triggered.
        read: std_logic;
    end record;

    -- Output signals of the system bus.
    type bus_out_t is record
        -- Register read output value.
        read_data: std_logic_vector(7 downto 0);
    end record;

    -- Return the number of bits required to represent the given input value as
    -- an unsigned.
    -- If value is 0, result is 1.
    function req_bits(value: natural) return natural;

    -- Return the number groups of n size required for m elements.
    function req_n(m: natural; n: natural) return natural;

end;


package body common_pkg is

    function req_bits(value: natural) return natural is
        variable n: natural;
        variable x: natural;
    begin
        n := 1;
        x := 2;
        while value > (x-1) loop
            x := x * 2;
            n := n + 1;
        end loop;
        return n;
    end;

    function req_n(m: natural; n: natural) return natural is
        variable x: natural;
    begin
        x := 0;
        while (x * 8) < m loop
            x := x + 1;
        end loop;
        return x;
    end;

end;
