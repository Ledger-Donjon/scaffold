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


entity right_matrix_module is
generic (
    -- Number of signals
    in_count: positive;
    -- Number of outputs
    out_count: positive );
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Bus signals
    bus_in: in bus_in_t;

    -- Input signals (and their output enable)
    matrix_in: in tristate_array_t(in_count-1 downto 0);
    -- Selection registers bus enable signals
    en_sel: in std_logic_vector(out_count-1 downto 0);
    -- Matrix output signals
    matrix_out: out tristate_array_t(out_count-1 downto 0) );
end;


architecture behavior of right_matrix_module is
    -- Selection configuration registers
    signal sel: std_logic_vector_array_t(out_count-1 downto 0)(7 downto 0);
    -- Some intermediate signal for converting from tristate_array_t to
    -- std_logic_vector_array_t.
    signal matrix_in_tmp: std_logic_vector_array_t(in_count-1 downto 0)
        (1 downto 0);
begin

    -- Some compilers are not smart enough to convert tristate_array_t to
    -- std_logic_vector_array_t, let help them a little bit...
    g_0: for i in 0 to in_count-1 generate
        matrix_in_tmp(i) <= matrix_in(i);
    end generate;

    g_sel: for i in 0 to out_count-1 generate

        -- Selection register
        e_sel: entity work.module_reg
        port map (
            clock => clock,
            reset_n => reset_n,
            bus_in => bus_in,
            en => en_sel(i),
            value => sel(i) );

        -- N to 1 multiplexer
        e_mux: entity work.mux_n_to_1_w
        generic map (n => in_count, w => 2)
        port map (
            inputs => matrix_in_tmp,
            sel => sel(i)(req_bits(in_count-1)-1 downto 0),
            output => matrix_out(i));

    end generate;

end;
