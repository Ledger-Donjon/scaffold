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
-- Programmable clock generator module.
--
entity clock_module is
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Bus signals
    bus_in: in bus_in_t;

    -- Registers selection signals, from address decoder.
    en_config: in std_logic;
    en_divisor_a: in std_logic;
    en_divisor_b: in std_logic;
    en_count: in std_logic;

    -- Glitch start input.
    glitch_start: in std_logic;
    -- Clock output.
    output: out std_logic );
end;


architecture behavior of clock_module is
    signal glitch_counter: unsigned(7 downto 0);
    signal config: byte_t;
    signal enable: std_logic;
    signal divisor_a: byte_t;
    signal divisor_b: byte_t;
    signal count: byte_t;
    signal clock_counter: unsigned(7 downto 0);
    signal tick: std_logic;
begin
    e_config: entity work.module_reg
    port map (clock => clock, reset_n => reset_n, bus_in => bus_in,
        en => en_config, value => config );
    enable <= config(0);

    e_divisor_a: entity work.module_reg
    generic map (reset => x"ff")
    port map (clock => clock, reset_n => reset_n, bus_in => bus_in,
        en => en_divisor_a, value => divisor_a );
    
    e_divisor_b: entity work.module_reg
    generic map (reset => x"ff")
    port map (clock => clock, reset_n => reset_n, bus_in => bus_in,
        en => en_divisor_b, value => divisor_b );
    
    e_count: entity work.module_reg
    port map (clock => clock, reset_n => reset_n, bus_in => bus_in,
        en => en_count, value => count );

    p_clock_counter: process (clock, reset_n)
    begin
        if reset_n = '0' then
            clock_counter <= (others => '0');
        elsif rising_edge(clock) then
            if clock_counter = 0 then
                if glitch_counter = 0 then
                    clock_counter <= unsigned(divisor_a);
                else
                    clock_counter <= unsigned(divisor_b);
                end if;
            else
                clock_counter <= clock_counter - 1;
            end if;
        end if;
    end process;

    p_glitch_counter: process (clock, reset_n)
    begin
        if reset_n = '0' then
            glitch_counter <= (others => '0');
        elsif rising_edge(clock) then
            if glitch_start = '1' then
                glitch_counter <= unsigned(count);
            else
                if (clock_counter = 0) and not (glitch_counter = 0) then
                    glitch_counter <= glitch_counter - 1;
                else
                    glitch_counter <= glitch_counter;
                end if;
            end if;
        end if;
    end process;

    p_output: process (clock, reset_n)
    begin
        if reset_n = '0' then
            output <= '0';
        elsif rising_edge(clock) then
            if clock_counter = 0 then
                output <= not output;
            else
                output <= output;
            end if;
        end if;
    end process;

end;
