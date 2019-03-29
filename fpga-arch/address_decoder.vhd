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
-- Address decoder.
--
-- The address decoding to place the correct data on the global system bus is
-- the critical path of the architecture. It is basically a big one-hot
-- multiplexer. The number of inputs of this multiplexer depends on the
-- integrated modules in the architecture, so the design here is generic. This
-- multiplexer has been put in this file so it can be easily enhanced or
-- rewritten if needed.
--
-- Writting a generic one-hot multiplexer is not easy and may lead to bad
-- process loop unroling producing a cascade of logic. Such cascade is avoided
-- in current implementation.
--


library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.common_pkg.all;


entity address_decoder is
generic (
    -- Number of values to be multiplexed
    n: positive );
port (
    -- Input values
    values: in std_logic_vector_array_t(n-1 downto 0)(7 downto 0);
    -- Selection signals.
    -- This vector is one-hot encoded (zero is allowed).
    enables: in std_logic_vector(n-1 downto 0);
    -- Multiplexer output value
    value: out byte_t );
end;


architecture behavior of address_decoder is
    -- Selection enable signals
begin
    p_value: process (values, enables)
        variable result: byte_t;
        variable x: byte_t;
    begin
        result := x"00";
        for i in 0 to n-1 loop
            x := (others => enables(i));
            result := result or (values(i) and x);
        end loop;
        value <= result;
    end process;
end;
