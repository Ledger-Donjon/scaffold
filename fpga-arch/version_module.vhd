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
use ieee.numeric_std.all;
use work.common_pkg.all;


--
-- Module which tells current FPGA bitstream version.
--
entity version_module is
generic (
    -- Version string.
    version: string );
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Bus signals
    bus_in: in bus_in_t;

    -- Registers selection signals, from address decoder.
    en_data: in std_logic;

    -- Output registers
    reg_data: out byte_t );
end;


architecture behavior of version_module is
    -- String length
    constant length: positive := version'length;
    -- Shift register holding the characters of the string.
    signal shift: std_logic_vector(8+length*8-1 downto 0);
begin

    p_shift: process(clock, reset_n)
    begin
        if reset_n = '0' then
            -- Null character at the beginning of the string. This character
            -- will help finding the beginning and end of the string when read.
            shift(7 downto 0) <= x"00";
            for i in 1 to length loop
                shift(i*8+7 downto i*8) <=
                    std_logic_vector(to_unsigned(character'pos(version(i)), 8));
            end loop;
        elsif rising_edge(clock) then
            if (en_data = '1') and (bus_in.read = '1') then
                -- Rotate right
                shift <= shift(7 downto 0) & shift(shift'high downto 8);
            else
                shift <= shift;
            end if;
        end if;
    end process;

    -- Map the data register to the last character in the shift register, so
    -- first access will return the null character after shifting.
    reg_data <= shift(shift'high downto shift'high-7);

end;
