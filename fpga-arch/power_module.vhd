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
-- Power supplies module.
--
entity power_module is
generic (
    -- Number of controller power supplies. Max is 4.
    n: positive );
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Bus signals
    bus_in: in bus_in_t;

    -- High when control register is selected on the bus.
    en_control: in std_logic;
    
    -- A rising edge on this signal will immediately turn off the power supply.
    -- This signal is asynchronous.
    teardown_async: in std_logic;

    -- When high, power supply is enabled.
    -- This signal is asynchronous: we don't want to wait for next clock cycle
    -- to teardown the device under test.
    power_async: out std_logic_vector(n-1 downto 0);
    -- Same as power_async but registered.
    power_sync: out std_logic_vector(n-1 downto 0);
    
    -- Control register value.
    reg_control: out byte_t );
end;


architecture behavior of power_module is
    -- High when a power-on request is written on the bus.
    signal power_on_rq: std_logic_vector(n-1 downto 0);
    -- High when a power-off request is written on the bus.
    signal power_off_rq: std_logic_vector(n-1 downto 0);
    -- Current power status, resynchronized.
    signal status: std_logic_vector(n-1 downto 0);
begin
    p0: process (clock, reset_n)
    begin
        if reset_n = '0' then
            power_on_rq <= (others => '0');
            power_off_rq <= (others => '0');
            status <= (others => '0');
        elsif rising_edge(clock) then
            status <= power_async;
            if (en_control = '1') and (bus_in.write = '1') then
                -- Control register is written.
                power_on_rq <= bus_in.write_data(n-1 downto 0);
                power_off_rq <= not bus_in.write_data(n-1 downto 0);
            else
                power_on_rq <= (others => '0');
                power_off_rq <= (others => '0');
            end if;
        end if;
    end process;
    power_sync <= status;

    p_reg_control: process (status)
    begin
        reg_control <= (others => '0');
        reg_control(n-1 downto 0) <= status;
    end process;

    -- Latch
    -- Disable power when:
    -- - reset is asserted,
    -- - a power-off request is made on the system bus
    -- - tearing input is high
    -- Enable power when:
    -- - a power-on request is made on the system bus
    p_latch: process (teardown_async, power_off_rq, power_on_rq, reset_n)
    begin
        for i in 0 to n-1 loop
            if (teardown_async or power_off_rq(i) or (not reset_n)) = '1' then
                power_async(i) <= '0';
            elsif power_on_rq(i) = '1' then
                power_async(i) <= '1';
            else
                power_async(i) <= power_async(i);
            end if;
        end loop;
    end process;
end;
