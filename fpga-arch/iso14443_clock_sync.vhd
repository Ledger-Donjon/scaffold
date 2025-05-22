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
-- Copyright 2025 Ledger SAS, written by Olivier Hériveaux


library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;


entity iso14443_clock_sync is
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- 13.56 MHz clock input
    clock_13_56: in std_logic;
    -- Resynchronization result
    go: out std_logic );
end;


architecture behavior of iso14443_clock_sync is
    -- Synchronization register chain
    signal sync_chain: std_logic_vector(3 downto 0);
    -- Sampled clock used for detection.
    signal samples: std_logic_vector(3 downto 0);
begin
    -- This chain helps preventing metastability issues.
    -- See Altera White Paper WP-01082-1.2
    -- https://cdrdv2-public.intel.com/650346/wp-01082-quartus-ii-metastability.pdf
    p_sync_chain: process (clock, reset_n) is
    begin
        if reset_n = '0' then
            sync_chain <= (others => '0');
        elsif rising_edge(clock) then
            sync_chain <= sync_chain(sync_chain'high - 1 downto 0) & clock_13_56;
        end if;
    end process;

    p_samples: process (clock, reset_n) is
    begin
        if reset_n = '0' then
            samples <= (others => '0');
            go <= '0';
        elsif rising_edge(clock) then
            samples <= samples(samples'high - 1 downto 0) & sync_chain(sync_chain'high);
            if samples = "0111" then
                go <= '1';
            else
                go <= '0';
            end if;
        end if;
    end process;
end;
