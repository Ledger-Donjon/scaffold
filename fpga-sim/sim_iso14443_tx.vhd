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
use work.common_pkg.all;


entity sim_iso14443_tx is end;


architecture behavior of sim_iso14443_tx is
    constant clock_frequency: integer := 100000000;
    constant clock_period: time := (1 sec) / clock_frequency;

    -- External clock
    signal clock: std_logic;
    -- Reset
    signal reset_n: std_logic;

    -- Input signals
    signal polarity: std_logic;
    signal push: std_logic;
    signal start: std_logic;
    signal pattern: std_logic_vector(1 downto 0);

    -- Output signals
    signal busy: std_logic;
    signal tx: std_logic;
    signal trigger_start: std_logic;
    signal trigger_end: std_logic;

begin

    e_iso14443: entity work.iso14443_tx
    port map (
        clock => clock,
        reset_n => reset_n,
        pattern => pattern,
        polarity => polarity,
        push => push,
        start => start,
        busy => busy,
        tx => tx,
        trigger_start => trigger_start,
        trigger_end => trigger_end );

    -- External clock generation
    p_clock: process
    begin
        clock <= '0';
        wait for clock_period / 2;
        clock <= '1';
        wait for clock_period / 2;
    end process;

    -- Reset signal
    p_reset: process
    begin
        reset_n <= '0';
        wait for clock_period * 4;
        reset_n <= '1';
        wait;
    end process;

    p_0: process is
    begin
        polarity <= '0';
        push <= '0';
        start <= '0';
        pattern <= "11";
        wait for clock_period * 100;

        pattern <= "01";
        push <= '1';
        wait for clock_period;
        push <= '0';
        pattern <= "01";
        push <= '1';
        wait for clock_period;
        push <= '0';
        pattern <= "01";
        push <= '1';
        wait for clock_period;
        push <= '0';

        wait for clock_period;
        start <= '1';
        wait for clock_period;
        start <= '0';

        wait;
    end process;

end;
