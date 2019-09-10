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
-- Useful basic entity to help making module wide registers connected to the
-- system bus. Register width is a multiple of 8 bits.
-- Wide registers are loaded by consecutive writes. Most significant byte is
-- loaded first.
--
entity module_wide_reg is
generic (
    -- Number of bytes in the register.
    wideness: positive := 2;
    -- Value on reset.
    reset: std_logic_vector;
    -- Load direction option.
    -- "lsb" or "msb".
    dir: string := "lsb");
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- System bus.
    bus_in: in bus_in_t;
    -- Address decoding selection. High when the register is selected.
    en: in std_logic;
    -- Actual value of the register
    value: out std_logic_vector((wideness * 8) - 1 downto 0) );
end;


architecture behavior of module_wide_reg is
    -- Actual value of the register
    signal reg: std_logic_vector((wideness * 8) - 1 downto 0);
begin
    p: process (clock, reset_n)
    begin
        assert (dir = "lsb") or (dir = "msb");
        if reset_n = '0' then
            reg <= reset;
        elsif rising_edge(clock) then
            if (bus_in.write = '1') and (en = '1') then
                if dir = "lsb" then
                    reg <= reg(reg'high-8 downto 0) & bus_in.write_data;
                else
                    reg <= bus_in.write_data & reg(reg'high downto 8);
                end if;
            else
                reg <= reg;
            end if;
        end if;
    end process;

    value <= reg;
end;

