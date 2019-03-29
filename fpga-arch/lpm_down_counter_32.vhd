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
library lpm;
use lpm.all;


entity lpm_down_counter_32 is
port (
    aclr: in std_logic;
    clock: in std_logic;
    cnt_en: in std_logic;
    data: in std_logic_vector(31 downto 0);
    sload: in std_logic;
    q: out std_logic_vector(31 downto 0) );
end;


architecture behavior of lpm_down_counter_32 is
    component lpm_counter
    generic (
        lpm_type: string;
        lpm_direction: string;
        lpm_width: integer );
    port (
        aclr: in std_logic;
        clock: in std_logic;
        cnt_en: in std_logic;
        data: in std_logic_vector(31 downto 0);
        sload: in std_logic;
        q: out std_logic_vector(31 downto 0) );
    end component;
begin
    c_lpm_counter: lpm_counter
    generic map (
        lpm_type => "LPM_COUNTER",
        lpm_width => 32,
        lpm_direction => "DOWN" )
    port map (
        aclr => aclr,
        clock => clock,
        cnt_en => cnt_en,
        data => data,
        sload => sload,
        q => q );
end;
