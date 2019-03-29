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
-- Keep a LED on for some period of time when a signal changes.
--
entity led_blink is
generic (
    -- How long a LED shall stay on once lit, in clock cycles.
    -- Max is 2^27-1.
    n: positive );
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Monitored input signal.
    input: in std_logic;
    -- High when the LED is lit.
    light: out std_logic );
end;


architecture behavior of led_blink is
    -- Counter output.
    signal counter: std_logic_vector(26 downto 0);
    -- High when counter is equal to zero.
    signal is_zero: std_logic;
    -- Current input signal state (registered).
    signal input_r: std_logic;
    -- Input signal previous state.
    signal input_z: std_logic;
    -- High when the input signal changed.
    signal act: std_logic;
begin
    is_zero <= '1' when unsigned(counter) = 0 else '0';
    act <= input_r xor input_z;

    e_counter: entity work.lpm_down_counter_27
    port map (
        aclr => not reset_n,
        clock => clock,
        sload => act,
        cnt_en => not is_zero,
        data => std_logic_vector(to_unsigned(integer(n), counter'length)),
        q => counter );

    -- Registering the input and output signals is not mandatory, but it seems
    -- cleaner to do it and it does not cost that much. There is no need for low
    -- latency on these signals.
    p0: process (clock, reset_n)
    begin
        if reset_n = '0' then
            light <= '0';
            input_r <= '0';
            input_z <= '0';
        elsif rising_edge(clock) then
            input_r <= input;
            input_z <= input_r;
            if is_zero = '1' then
                light <= '0';
            else
                light <= '1';
            end if;
        end if;
    end process;
end;

