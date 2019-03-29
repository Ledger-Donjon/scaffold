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
-- Driver for Texas Instruments TLC5952 circuit.
--
-- Each TLC5952 driver can drive up to 24 LEDs.
--
-- The driver circuit configuration is updated when the leds or control inputs
-- change.
--
entity tlc5952_driver is
generic (
    -- System clock divisor for TLC5952 input clock.
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
    leds: in std_logic_vector(23 downto 0);
    -- Requested control register value.
    control: in std_logic_vector(23 downto 0);
    -- TLC5952 serial input. Registered.
    sin: out std_logic;
    -- TLC5952 serial clock. Registered.
    sclk: out std_logic;
    -- TLC5952 latch. Registered.
    lat: out std_logic;
    -- TLC5952 blank. When high, all constant-current outputs are forced off.
    blank: out std_logic );
end;


-- The architecture uses registers to store the actual state of the LEDs and
-- TLC5952 control register. When one of those registers changes, an update is
-- performed.
architecture behavior of tlc5952_driver is
    type state_t is (
        st_idle,
        st_start_leds,
        st_start_control,
        st_sync,
        st_transmit,
        st_latch );
    
    -- FSM state.
    signal state: state_t;
    -- Current LEDs status.
    signal current_leds: std_logic_vector(23 downto 0);
    -- Current control status.
    signal current_control: std_logic_vector(23 downto 0);
    -- Shift-register used for transmission.
    -- Includes the select bit.
    signal shift: std_logic_vector(24 downto 0);
    -- Transmission clock divisor counter
    signal counter: integer range 0 to divisor-1;
    -- Number of remaining bits to be transmitted (minus 1).
    -- Start bit (used to select between LEDs and controls registers) is
    -- included.
    signal bit_counter: integer range 0 to 25 - 1;
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
                -- Idle mode. Not transmitting anything. TLC5952 drivers are
                -- up-to-date.
                when st_idle =>
                    if current_control /= control then
                        state <= st_start_control;
                    elsif current_leds /= leds then
                        state <= st_start_leds;
                    else
                        state <= st_idle;
                    end if;

                -- Loading shift-register for LEDs state transmission, and
                -- saving LEDs state in the current_leds register.
                when st_start_leds =>
                    state <= st_sync;
                
                -- Loading shift-register for control register transmission, and
                -- saving control register in the current_control register.
                when st_start_control =>
                    state <= st_sync;

                -- Synchronizing to transmission clock.
                when st_sync =>
                    if tick = '1' then
                        state <= st_transmit;
                    else
                        state <= st_sync;
                    end if;

                -- Transmitting bits
                when st_transmit =>
                    if (tick = '1') and (bit_counter = 0) then
                        state <= st_latch;
                    else
                        state <= st_transmit;
                    end if;

                -- Latch the shift-register of the TLC5952 to apply update to
                -- the LEDs state register of control register.
                when st_latch =>
                    if tick = '1' then
                        state <= st_idle;
                    else
                        state <= st_latch;
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
                    bit_counter <= 24;
            end case;
        end if;
    end process;

    -- LEDs status and control registers management.
    p_current_registers: process (clock, reset_n)
    begin
        if reset_n = '0' then
            -- Set default value of current registers to '1', to force a
            -- configuration at startup when the default state must be '0'.
            current_leds <= (others => '1');
            current_control <= (others => '1');
        elsif rising_edge(clock) then
            case state is
                when st_start_leds =>
                    current_leds <= leds;
                    current_control <= current_control;
                when st_start_control =>
                    current_leds <= current_leds;
                    current_control <= control;
                when others =>
                    current_leds <= current_leds;
                    current_control <= current_control;
            end case;
        end if;
    end process;

    -- Transmission shift register management.
    p_shift: process (clock, reset_n)
    begin
        if reset_n = '0' then
            shift <= (others => '0');
        elsif rising_edge(clock) then
            case state is
                when st_start_leds =>
                    shift <= '0' & leds;
                when st_start_control =>
                    shift <= '1' & control;
                when st_transmit =>
                    if tick = '1' then
                        shift <= shift(shift'high-1 downto 0) & '1';
                    else
                        shift <= shift;
                    end if;
                when others =>
                    shift <= shift;
            end case;
        end if;
    end process;

    -- TLC5952 driver signals. All registered.
    p_signals: process (clock, reset_n)
    begin
        if reset_n = '0' then
            sin <= '0';
            sclk <= '0';
            lat <= '0';
        elsif rising_edge(clock) then
            sin <= shift(shift'high);
           
            if state = st_transmit then
                if counter >= (divisor / 2) then
                    sclk <= '0';
                else
                    sclk <= '1';
                end if;
            else
                sclk <= '0';
            end if;
            
            if state = st_latch then
                lat <= '1';
            else
                lat <= '0';
            end if;
        end if;
    end process;
    
    blank <= '0';

end;
