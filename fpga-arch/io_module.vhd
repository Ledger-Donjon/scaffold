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
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Bus signals
    bus_in: in bus_in_t;

    -- Registers selection signals, from address decoder.
    en_value: in std_logic;

    -- Output registers
    reg_value: out byte_t;

    -- FPGA I/O pin
    pin: inout std_logic;

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
begin
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

    -- Tristate output management
    p_pin: process (pin_out_en, pin_out)
    begin
        if pin_out_en = '0' then
            pin <= 'Z';
        else
            pin <= pin_out;
        end if;
    end process;
end;
