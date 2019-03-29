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


--
-- Driver for Texas Instruments TLC5927 circuit.
--
-- Each TLC5927 driver can drive up to 16 LEDs. TLC5927 circuits can be
-- cascaded. Cascading is supported by the architecture.
--
entity tlc5927_driver is
generic (
    -- Number of cascaded TLC5927 drivers.
    count: positive := 1;
    -- System clock divisor for TLC5927 input clock.
    -- Minimum is 2.
    -- Output clock is (system clock / (divisor * 2))
    divisor: positive := 2 );
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- LEDs requested state. Each bit corresponds to a LED. When a bit is 1,
    -- the corresponding LED will be lit.
    leds: in std_logic_vector(count * 16 - 1 downto 0);
    -- TLC5927 Serial Data In.
    sdi: out std_logic;
    -- TLC5927 Serial clock.
    clk: out std_logic;
    -- TLC5927 Latch Enable.
    le: out std_logic;
    -- TLC5927 Output Enable (negated)
    oe_n: out std_logic );
end;


architecture behavior of tlc5927_driver is
    type state_t is (
        st_idle,
        st_start,
        st_transmit,
        st_strobe );
    
    -- FSM state.
    signal state: state_t;
    -- Current LEDs status.
    -- During transmission, this register is shifted count * 16 times. At the
    -- end of the transmission, its value is the same as at the beginning.
    signal current_leds: std_logic_vector(count * 16 - 1 downto 0);
    -- Transmission clock divisor counter
    signal counter: integer range 0 to divisor-1;
    -- Number of remaining bits to be transmitted (minus 1).
    signal bit_counter: integer range 0 to count*16-1;
    -- High when counter is zero.
    signal tick: std_logic;
begin
    assert divisor >= 2 report "Invalid divisor value!";

    -- Clock divisor counter.
    p_counter: process (clock, reset_n)
    begin
        if reset_n = '0' then
            counter <= divisor-1;
        elsif rising_edge(clock) then
            if counter = 0 then
                counter <= divisor-1;
            else
                counter <= counter-1;
            end if;
        end if;
    end process;

    tick <= '1' when counter = 0 else '0';

    -- FSM state management
    p_state: process (clock, reset_n)
    begin
        if reset_n = '0' then
            state <= st_idle;
        elsif rising_edge(clock) then
            case state is
                -- Idle mode. Not transmitting anything. TLC5927 drivers are
                -- up-to-date.
                when st_idle =>
                    if current_leds /= leds then
                        -- Change detected
                        state <= st_start;
                    else
                        state <= st_idle;
                    end if;

                -- Transmission required.
                -- Synchronizing to transmission clock.
                when st_start =>
                    if tick = '1' then
                        state <= st_transmit;
                    else
                        state <= st_start;
                    end if;

                -- Transmitting bits
                when st_transmit =>
                    if (tick = '1') and (bit_counter = 0) then
                        state <= st_strobe;
                    else
                        state <= st_transmit;
                    end if;

                -- Asserting strobe to latch the shift-register of the TLC5927
                -- driver.
                when st_strobe =>
                    if tick = '1' then
                        state <= st_idle;
                    else
                        state <= st_strobe;
                    end if;
                        
                when others =>
                    state <= st_idle;
            end case;
        end if;
    end process;

    -- Transmission bits counter
    p_bit_counter: process (clock, reset_n)
    begin
        if reset_n = '0' then
            bit_counter <= 0;
        elsif rising_edge(clock) then
            case state is
                when st_transmit =>
                    if tick = '1' then
                        if bit_counter = 0 then
                            bit_counter <= bit_counter;
                        else
                            bit_counter <= bit_counter - 1;
                        end if;
                    else
                        bit_counter <= bit_counter;
                    end if;
                when others =>
                    bit_counter <= count * 16 - 1;
            end case;
        end if;
    end process;

    -- LEDs status register management.
    p_current_leds: process (clock, reset_n)
    begin
        if reset_n = '0' then
            current_leds <= (others => '0');
        elsif rising_edge(clock) then
            case state is
                when st_start =>
                    current_leds <= leds;
                when st_transmit =>
                    if tick = '1' then
                        current_leds <= current_leds(0) &
                            current_leds(count * 16 - 1 downto 1);
                    else
                        current_leds <= current_leds;
                    end if;
                when others =>
                    current_leds <= current_leds;
            end case;
        end if;
    end process;

    oe_n <= '0';

    -- TLC5927 driver signals. All registered.
    p_signals: process (clock, reset_n)
    begin
        if reset_n = '0' then
            sdi <= '0';
            clk <= '0';
            le <= '0';
        elsif rising_edge(clock) then
            sdi <= current_leds(0);
           
            if state = st_transmit then
                if counter >= (divisor / 2) then
                    clk <= '0';
                else
                    clk <= '1';
                end if;
            else
                clk <= '0';
            end if;
            
            if state = st_strobe then
                le <= '1';
            else
                le <= '0';
            end if;
        end if;
    end process;
end;
