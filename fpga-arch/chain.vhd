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
-- Copyright 2019 Ledger SAS, written by Karim Abdellatif and Olivier Hériveaux


library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;


entity chain is
generic (
    -- Number of events to the chain
    n: integer );
port (
    clock: in std_logic;
    reset_n: in std_logic;
    events: in std_logic_vector(n-1 downto 0);
    chain_out: out std_logic;
    rearm: in std_logic );
end chain;


architecture behavior of chain is
    type state_type is (s1, s2, s3, s4, st_end);
    signal cs, ns: state_type;
begin
    synch: process(clock, ns, reset_n)
    begin
        if(reset_n='0')then
            cs <= s1;
        else
            if(rising_edge(clock))then
                cs<=ns;
            end if;
        end if;
    end process;

    next_state: process(cs, events, rearm)
    begin
        case cs is
            when s1=> --ready
                chain_out<='0';
                if rearm = '1' then
                    ns <= s1;
                else
                    if (events(0)='1') then
                        ns<=s2;
                    else
                        ns<=s1;
                    end if;
                end if;

            when s2=>
                chain_out<='0';
                if rearm = '1' then
                    ns <= s1;
                else
                    if(events(1)='1')then
                        ns<=s3;
                    else
                        ns<=s2;
                    end if;
                end if;

            when s3=>
                if(n /=3)then
                    chain_out<='1';
                    ns<=s1;
                else
                    chain_out<='0';
                    if rearm = '1' then
                        ns <= s1;
                    else
                        if(events(2)='1')then
                            ns<=s4;
                        else
                            ns<=s3;
                        end if;
                    end if;
                end if;

            when s4=>
                chain_out <= '1';
                if rearm = '1' then
                    ns <= s1;
                else
                    ns <= st_end;
                end if;

            when st_end =>
                chain_out <= '0';
                if rearm = '1' then
                    ns <= s1;
                else
                    ns <= st_end;
                end if;

        end case;
    end process;
end;
