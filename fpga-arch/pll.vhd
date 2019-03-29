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
library altera_mf;
use altera_mf.all;


entity pll is
port (
    areset: in std_logic;
    inclk0: in std_logic;
    c0: out std_logic;
    locked: out std_logic );
end;


architecture behavior of pll is
    signal clk_x: std_logic_vector(4 downto 0);

    component altpll
    generic (
        lpm_type: string;
        clk0_divide_by: integer;
        clk0_duty_cycle: integer;
        clk0_multiply_by: integer;
        inclk0_input_frequency: integer;
        operation_mode: string;
        intended_device_family: string;
        width_clock: integer;
        port_areset: string;
        port_inclk0: string;
        port_locked: string;
        port_clk0: string );
    port (
        areset: in std_logic;
        inclk: in std_logic_vector(1 downto 0);
        clk: out std_logic_vector(4 downto 0);
        locked: out std_logic );
    end component;

begin
    -- Name of this component (altpll_component) must match component name in
    -- the SDC constraint for timing analysis.
    altpll_component: altpll
    generic map (
        lpm_type => "altpll",
        clk0_divide_by => 1,
        clk0_duty_cycle => 50,
        clk0_multiply_by => 4,
        inclk0_input_frequency => 40000, -- period in ps
        operation_mode => "NORMAL",
        intended_device_family => "Cyclone IV E",
        width_clock => 5,
        port_areset => "PORT_USED",
        port_inclk0 => "PORT_USED",
        port_locked => "PORT_USED",
        port_clk0 => "PORT_USED" )
    port map (
        areset => areset,
        inclk => '0' & inclk0,
        clk => clk_x,
        locked => locked );

    c0 <= clk_x(0);
end;
