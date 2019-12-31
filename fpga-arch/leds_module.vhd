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
-- LEDs driver module.
--
entity leds_module is
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Bus signals
    bus_in: in bus_in_t;

    -- Registers selection signals, from address decoder.
    en_control: in std_logic;
    en_brightness: in std_logic;
    en_mode: in std_logic;
    en_leds_0: in std_logic;
    en_leds_1: in std_logic;
    en_leds_2: in std_logic;

    -- Inputs to be displayed with LEDs
    leds: in std_logic_vector(23 downto 0);
    -- For each signal indicate if blink management shall be generated (1) or
    -- not (0). Blink management requires extra logic, and we don't need each
    -- for all 24 LEDs.
    blink_mask: in std_logic_vector(23 downto 0);

    -- TLC5952 LEDs driver control signals.
    leds_sin: out std_logic;
    leds_sclk: out std_logic;
    leds_lat: out std_logic;
    leds_blank: out std_logic );
end;


architecture behavior of leds_module is
    -- control, brightness and leds_n registers
    signal control: std_logic_vector(7 downto 0);
    signal override_bit: std_logic;
    signal brightness: std_logic_vector(7 downto 0);
    signal leds_0: std_logic_vector(7 downto 0);
    signal leds_1: std_logic_vector(7 downto 0);
    signal leds_2: std_logic_vector(7 downto 0);
    -- Each bit choose between blink or static mode for each LED.
    -- If 0: blink mode (default)
    -- If 1: static mode
    signal mode: std_logic_vector(23 downto 0);
    -- State of the LEDs for override mode
    signal override_leds: std_logic_vector(23 downto 0);
    -- Output of the mode multiplexer.
    signal mode_mux_leds: std_logic_vector(23 downto 0);
    -- For each input signal, create a blink signal which is high for a fixed
    -- period of time when the input signal changes.
    signal blinks: std_logic_vector(23 downto 0);
    -- Final state of the LEDs. Output of a MUX from override_leds and leds,
    -- selected by override_bit.
    signal mux_leds: std_logic_vector(23 downto 0);
begin
    -- Generate blink signals
    g_blink: for i in 0 to 23 generate 
        e_led_blink: entity work.led_blink
        generic map (n => 5000000)
        port map (
            clock => clock,
            reset_n => reset_n,
            input => leds(i),
            light => blinks(i) );
    end generate;

    -- Blink mask and mode management.
    -- This is a MUX between blink and led signals.
    p_mask_mode: process (mode, leds, blinks, blink_mask)
    begin
        for i in 0 to 23 loop
            if blink_mask(i) = '0' then
                mode_mux_leds(i) <= leds(i);
            else
                if mode(i) = '0' then
                    mode_mux_leds(i) <= blinks(i);
                else
                    mode_mux_leds(i) <= leds(i);
                end if;
            end if;
        end loop;
    end process;

    override_leds <= leds_2 & leds_1 & leds_0;
    mux_leds <= override_leds when (override_bit = '1') else mode_mux_leds;

    e_control: entity work.module_reg
    generic map (reset => x"01")
    port map (
        clock => clock,
        reset_n => reset_n,
        en => en_control,
        bus_in => bus_in,
        value => control );

    override_bit <= control(1);

    e_mode: entity work.module_wide_reg
    generic map (wideness => 3, reset => x"000000")
    port map (
        clock => clock,
        reset_n => reset_n,
        en => en_mode,
        bus_in => bus_in,
        value => mode );

    e_brightness: entity work.module_reg
    generic map (reset => x"3f")
    port map (
        clock => clock,
        reset_n => reset_n,
        en => en_brightness,
        bus_in => bus_in,
        value => brightness );

    e_leds_0: entity work.module_reg
    generic map (reset => x"00")
    port map (
        clock => clock,
        reset_n => reset_n,
        en => en_leds_0,
        bus_in => bus_in,
        value => leds_0 );

    e_leds_1: entity work.module_reg
    generic map (reset => x"00")
    port map (
        clock => clock,
        reset_n => reset_n,
        en => en_leds_1,
        bus_in => bus_in,
        value => leds_1 );

    e_leds_2: entity work.module_reg
    generic map (reset => x"00")
    port map (
        clock => clock,
        reset_n => reset_n,
        en => en_leds_2,
        bus_in => bus_in,
        value => leds_2 );

    e_tlc5952_driver: entity work.tlc5952_driver
    generic map (divisor => 16)
    port map (
        clock => clock,
        reset_n => reset_n,
        leds => mux_leds,
        -- Same brightness for all three channels
        control => "000" & brightness(6 downto 0) & brightness(6 downto 0)
            & brightness(6 downto 0),
        sin => leds_sin,
        sclk => leds_sclk,
        lat => leds_lat,
        blank => leds_blank );
end;
