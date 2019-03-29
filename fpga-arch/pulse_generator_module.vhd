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
-- Programmable pulse generator module.
--
entity pulse_generator_module is
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Bus signals
    bus_in: in bus_in_t;

    -- Registers selection signals, from address decoder.
    en_config: in std_logic;
    en_control: in std_logic;
    en_delay: in std_logic;
    en_interval: in std_logic;
    en_width: in std_logic;
    en_count: in std_logic;

    -- Output registers.
    reg_status: out byte_t;

    -- Start input.
    start: in std_logic;
    -- Pulse output.
    output: out std_logic );
end;


architecture behavior of pulse_generator_module is
    -- Status register
    signal ready: std_logic;
    -- Configuration register
    signal config: byte_t;
    signal polarity: std_logic;
    -- Delay before pulse
    signal delay: std_logic_vector(23 downto 0);
    -- Delay after pulse
    signal interval: std_logic_vector(23 downto 0);
    -- Number of pulses to be generated.
    signal count: std_logic_vector(15 downto 0);
    -- Width of the pulses.
    signal width: std_logic_vector(23 downto 0);
    -- Pulse generation start signal.
    signal start_b: std_logic;
begin

    -- Start the pulse generation when the start input is asserted or the start
    -- bit in the control register is written.
    p_start_b: process (clock, reset_n)
    begin
        if reset_n = '0' then
            start_b <= '0';
        elsif rising_edge(clock) then
            if ((en_control = '1') and (bus_in.write = '1') and
                (bus_in.write_data(0) = '1')) or (start = '1') then
                start_b <= '1';
            else
                start_b <= '0';
            end if;
        end if;
    end process;
    
    e_config: entity work.module_reg
    port map (
        clock => clock,
        reset_n => reset_n,
        bus_in => bus_in,
        en => en_config,
        value => config );

    e_delay: entity work.module_wide_reg
    generic map (wideness => 3, reset => x"000000")
    port map (
        clock => clock,
        reset_n => reset_n,
        bus_in => bus_in,
        en => en_delay,
        value => delay );

    e_interval: entity work.module_wide_reg
    generic map (wideness => 3, reset => x"000000")
    port map (
        clock => clock,
        reset_n => reset_n,
        bus_in => bus_in,
        en => en_interval,
        value => interval );

    e_width: entity work.module_wide_reg
    generic map (wideness => 3, reset => x"000000")
    port map (
        clock => clock,
        reset_n => reset_n,
        bus_in => bus_in,
        en => en_width,
        value => width );

    e_count: entity work.module_wide_reg
    generic map (wideness => 2, reset => x"0000")
    port map (
        clock => clock,
        reset_n => reset_n,
        bus_in => bus_in,
        en => en_count,
        value => count );

    reg_status <= "0000000" & ready;
    polarity <= config(0);

    e_pulse_generator: entity work.pulse_generator
    port map (
        clock => clock,
        reset_n => reset_n,
        delay => delay,
        interval => interval,
        width => width,
        count => count,
        start => start_b,
        output => output,
        ready => ready,
        polarity => polarity );
 
end;
