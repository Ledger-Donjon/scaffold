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
-- Module which handles up to 8 board input signals.
-- Each input is registered and can be read using the system bus.
--
entity input_group_module is
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Bus signals
    bus_in: in bus_in_t;

    -- Registers selection signals, from address decoder.
    en_value: in std_logic;
    en_event: in std_logic;

    -- Output registers
    reg_value: out byte_t;
    reg_event: out byte_t;

    -- Input signals, connected to the pins of the FPGA.
    pin_in: in byte_t;
    -- Registered signals.
    pin_reg: out byte_t );
end;


architecture behavior of input_group_module is
    -- Registered input signals
    signal pin_in_reg: byte_t;
    -- When a bit is 0 the corresponding event bit is cleared.
    signal clear_mask: byte_t;
begin

    -- Register inputs to have clean signals.
    p_pin_in_reg: process(clock, reset_n)
    begin
        if reset_n = '0' then
            pin_in_reg <= x"00";
        elsif rising_edge(clock) then
            pin_in_reg <= pin_in;
        end if;
    end process;

    -- Event clear requests
    p_clear_mask: process(en_event, bus_in.write, bus_in.write_data)
    begin
        if (en_event = '1') and (bus_in.write = '1') then
            clear_mask <= bus_in.write_data;
        else
            clear_mask <= x"ff";
        end if;
    end process;

    -- Events detection.
    -- When an input is 1, set the event bit of this input to 1.
    -- Clear an event bit when it is written to 0. Writing a bit to 1 does not
    -- set the event bit.
    p_reg_event: process(clock, reset_n)
    begin
        if reset_n = '0' then
            reg_event <= x"00";
        elsif rising_edge(clock) then
            reg_event <= (reg_event and clear_mask) or pin_in_reg;
        end if;
    end process;

    pin_reg <= pin_in_reg;
    reg_value <= pin_in_reg;

end;
