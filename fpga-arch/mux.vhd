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
--
--
-- Generic multiplexers
--
-- This file uses VHDL-2008
--


library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.common_pkg.all;


--
-- N to 1 multiplexer of std_logic
--
entity mux_n_to_1 is
generic (
    -- Number of inputs
    n: positive );
port (
    -- Multiplexer input signals
    inputs: in std_logic_vector(n-1 downto 0);
    -- Selection
    sel: in std_logic_vector(req_bits(n-1)-1 downto 0);
    -- Multiplexer output
    output: out std_logic );
end;


architecture bahavior of mux_n_to_1 is
begin
    output <= inputs(to_integer(unsigned(sel)));
end;


library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.common_pkg.all;


--
-- N to 1 multiplexer of std_logic_vector
--
entity mux_n_to_1_w is
generic (
    -- Number of inputs
    n: positive;
    -- Width of signals
    w: positive );
port (
    -- Multiplexer input signals
    inputs: in std_logic_vector_array_t(n-1 downto 0)(w-1 downto 0);
    -- Selection
    sel: in std_logic_vector(req_bits(n-1)-1 downto 0);
    -- Multiplexer output
    output: out std_logic_vector(w-1 downto 0) );
end;


architecture bahavior of mux_n_to_1_w is
begin
    output <= inputs(to_integer(unsigned(sel)));
end;
