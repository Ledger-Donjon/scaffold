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
-- Copyright 2025 Ledger SAS, written by Olivier Hériveaux


library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;


entity iso14443_demod is
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Subcarrier input.
    rx: in std_logic;
    -- High to enable demodulator.
    enable: in std_logic;
    -- Demodulated output.
    result: out std_logic );
end;


architecture behavior of iso14443_demod is
    signal rx_z: std_logic;
    signal edge: std_logic;
    signal level: unsigned(1 downto 0);
    signal counter: unsigned(7 downto 0);
begin
    p_rx: process (clock, reset_n) is
    begin
        if reset_n = '0' then
            rx_z <= '0';
            edge <= '0';
        elsif rising_edge(clock) then
            rx_z <= rx and enable;
            edge <= rx xor rx_z;
        end if;
    end process;

    p_counter: process (clock, reset_n) is
    begin
        if reset_n = '0' then
            counter <= (others => '0');
        elsif rising_edge(clock) then
            if edge = '1' then
                -- 176 = 59 * 3 - 1
                -- With this value, for perfect modulated input we have a pulse
                -- of exactly half the duration of one bit.
                counter <= to_unsigned(176, counter'length);
            else
                if counter = 0 then
                    counter <= counter;
                else
                    counter <= counter - 1;
                end if;
            end if;
        end if;
    end process;

    p_level: process (clock, reset_n) is
    begin
        if reset_n = '0' then
            level <= (others => '0');
            result <= '0';
        elsif rising_edge(clock) then
            if (counter = 0) or (enable = '0') then
                level <= (others => '0');
            else
                if (edge = '1') and (level /= 3) then
                    level <= level + 1;
                else
                    level <= level;
                end if;
            end if;
            if (enable = '1') and (level = 3) then
                result <= '1';
            else
                result <= '0';
            end if;
        end if;
    end process;
end;
