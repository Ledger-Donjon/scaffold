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


entity chain_module is
generic (    
    -- Number of events.
    n: integer );
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Bus signals
    bus_in: in bus_in_t;
    -- Control register selection signal from address decoder
    en_control: in std_logic;
    -- Start input.
    events: in std_logic_vector(n-1 downto 0);
    -- Pulse output.
    chain_out: out std_logic );
end;

architecture behavior of chain_module is
    -- When high, the chain returns to initial state.
    -- This signal is high during one clock cycle when the control register bit
    -- 0 is written to 1.
    signal rearm: std_logic;
begin
    rearm <= bus_in.write and bus_in.write_data(0) and en_control;

    e_chain: entity work.chain
    generic map (n => n)
	port map (
        clock => clock,
        reset_n => reset_n,
        events => events,
        chain_out => chain_out,
        rearm => rearm );
end;
