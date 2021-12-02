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
-- Module managing a Scaffold I/O pin.
--
entity io_module is
generic (
    -- Reset value of the configuration register
    config_reset: std_logic_vector(7 downto 0) := x"00" );
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Bus signals
    bus_in: in bus_in_t;

    -- Registers selection signals, from address decoder.
    en_value: in std_logic;
    en_config: in std_logic;

    -- Output registers
    reg_value: out byte_t;

    -- FPGA I/O pin
    pin: inout std_logic;
    -- FPGA I/O pin for the pull resistor
    pull_pin: out std_logic;

    -- Output enable signal.
    pin_out_en: in std_logic;
    -- Output value (when pin_out_en is '1')
    pin_out: in std_logic;
    -- Input registered
    pin_in_reg: out std_logic );
end;


architecture behavior of io_module is
    -- Previous input value. Used for events detection.
    signal pin_in_z: std_logic;
    -- High when event clearing is requested.
    signal event_clear_rq: std_logic;
    -- Configuration register
    -- Bit 0 and 1 selects the I/O mode:
    -- - 0: auto
    -- - 1: open-collector
    -- - 2: push only
    -- - 3: reserved
    signal config: byte_t;
    signal mode: std_logic_vector(1 downto 0);
    -- Bit 2 and 3 selects the pull resistor mode
    -- - 0: no pull
    -- - 1: pull-down
    -- - 2: no pull
    -- - 3: pull-up
    -- Bit 2 can be seen as a pull-enable signal.
    -- Bit 3 can be seen as the pull direction signal.
    signal pull: std_logic_vector(1 downto 0);
    -- Output enable after mode application
    signal pin_out_en_mode: std_logic;
begin
    e_config: entity work.module_reg
    generic map (reset => config_reset)
    port map (
        clock => clock,
        reset_n => reset_n,
        en => en_config,
        bus_in => bus_in,
        value => config );
    mode <= config(1 downto 0);
    pull <= config(3 downto 2);

    -- Register inputs to have clean signals.
    p_pin_in_reg: process(clock, reset_n)
    begin
        if reset_n = '0' then
            pin_in_reg <= '0';
            pin_in_z <= '0';
        elsif rising_edge(clock) then
            pin_in_reg <= pin;
            pin_in_z <= pin_in_reg;
        end if;
    end process;

    -- value register is the following:
    -- - bit 0: current input value on the pin.
    -- - bit 1: toggle event detected
    reg_value(7 downto 2) <= "000000";
    reg_value(0) <= pin_in_reg;
    event_clear_rq <= en_value and bus_in.write and (not bus_in.write_data(1));
    p_reg_value: process(clock, reset_n)
    begin
        if reset_n = '0' then
            reg_value(1) <= '0';
        elsif rising_edge(clock) then
            -- Set bit on event, clear if requested.
            reg_value(1) <= ((pin_in_z xor pin_in_reg) or reg_value(1))
                and not event_clear_rq;
        end if;
    end process;

    -- Tristate depends on selected IO mode.
    p_pin_out_en_mode: process (pin_out_en, pin_out, mode)
    begin
        case mode is
            when "00" =>
                -- Auto
                pin_out_en_mode <= pin_out_en;
            when "01" =>
                -- Open-collector
                pin_out_en_mode <= not pin_out;
            when "10" =>
                -- Push only
                pin_out_en_mode <= pin_out;
            when "11" =>
                -- Push pull always
                pin_out_en_mode <= '1';
            when others =>
                -- Never used, but must be defined if using modelsim
                pin_out_en_mode <= pin_out_en;
        end case;
    end process;

    -- Output pin control with tristate.
    -- Signals are registered here to prevent glitches.
    p_pin: process (clock, reset_n)
    begin
        if reset_n = '0' then
            pin <= 'Z';
            pull_pin <= 'Z';
        elsif rising_edge(clock) then
            if pin_out_en_mode = '1' then
                pin <= pin_out;
            else
                pin <= 'Z';
            end if;
            case pull is
                when "00" => pull_pin <= 'Z';
                when "01" => pull_pin <= '0'; -- Pull-down
                when "10" => pull_pin <= 'Z';
                when "11" => pull_pin <= '1'; -- Pull-up
                -- Never used, but must be defined if using modelsim
                when others => pull_pin <= 'X';
            end case;
        end if;
    end process;
end;
