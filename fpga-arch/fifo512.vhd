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


entity fifo512 is
port (
    clock: in std_logic;
    aclr: in std_logic;
    data: in std_logic_vector(7 downto 0);
    rdreq: in std_logic;
    sclr: in std_logic;
    wrreq: in std_logic;
    empty: out std_logic;
    full: out std_logic;
    q: out std_logic_vector(7 downto 0);
    usedw: out std_logic_vector(8 downto 0) );
end;


architecture behavior of fifo512 is
    component scfifo
    generic (
        lpm_type: string;
        intended_device_family: string;
        add_ram_output_register: string;
        lpm_numwords: integer;
        lpm_showahead: string;
        lpm_width: integer;
        lpm_widthu: integer;
        overflow_checking: string;
        underflow_checking: string;
        use_eab: string );
    port (
        clock: in std_logic;
        aclr: in std_logic;
        data: in std_logic_vector(7 downto 0);
        rdreq: in std_logic;
        sclr: in std_logic;
        wrreq: in std_logic;
        empty: out std_logic;
        full: out std_logic;
        q: out std_logic_vector(7 downto 0);
        usedw: out std_logic_vector(8 downto 0) );
    end component;
begin
    s_fifo: scfifo
    generic map (
        lpm_type => "scfifo",
        intended_device_family => "Cyclone IV E",
        add_ram_output_register => "ON",
        lpm_numwords => 512,
        -- Disable showahead for more performance
        lpm_showahead => "OFF",
        lpm_width => 8,
        lpm_widthu => 9,
        overflow_checking => "ON",
        underflow_checking => "ON",
        use_eab => "ON" )
    port map (
        clock => clock,
        aclr => aclr,
        data => data,
        rdreq => rdreq,
        sclr => sclr,
        wrreq => wrreq,
        empty => empty,
        full => full,
        q => q,
        usedw => usedw );
end;
