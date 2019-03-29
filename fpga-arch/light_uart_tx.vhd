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
-- Lightweight UART transmitter.
-- Baudrate is fixed, there is one stop bit and no parity bit.
--
entity light_uart_tx is
generic (
    -- System clock frequency, required for baudrate divisor calculation.
    system_frequency: positive;
    -- Serial baudrate
    baudrate: positive );
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Next byte to be sent.
    data: in std_logic_vector(7 downto 0);
    -- When high, send the next byte.
    start: in std_logic;
    -- High when UART is ready to send a new byte.
    ready: out std_logic;
    -- Output of the UART.
    tx: out std_logic );
end;


architecture behavior of light_uart_tx is
    -- Number of cyles per bit
    constant period: integer := system_frequency / baudrate;

    -- FSM states for transmission
    type state_t is (st_idle, st_sending);

    -- Current and next FSM states
    signal current_state: state_t;
    signal next_state: state_t;

    -- Counter for baudrate generation
    signal baud_counter: integer range 0 to period-1;
    -- High when baud_counter is zero.
    signal tick: std_logic;

    -- Bit counter when transmitting data.
    signal bit_counter: integer range 0 to 9;

    -- Shift-register where the data to be sent is stored.
    -- Start bit is included, but not stop bits.
    signal data_shift: std_logic_vector(8 downto 0);
begin

    -- Next state to current state registration
    p_current_state: process (clock, reset_n)
    begin
        if reset_n = '0' then
            current_state <= st_idle;
        elsif rising_edge(clock) then
            current_state <= next_state;
        end if;
    end process;

    -- Generate transmission rate using a counter.
    p_baud_counter: process (clock, reset_n)
    begin
        if reset_n = '0' then
            baud_counter <= 0;
        elsif rising_edge(clock) then
            if current_state = st_idle then
                baud_counter <= period-1;
            else
                if baud_counter = 0 then
                    baud_counter <= period-1;
                else
                    baud_counter <= baud_counter - 1;
                end if;
            end if;
        end if;
    end process;

    tick <= '1' when baud_counter = 0 else '0';

    -- Calculate next state of FSM
    p_next_state: process (current_state, start, tick, bit_counter)
    begin
        case current_state is
            -- UART is ready to send a new byte. Wait for start input to be
            -- asserted.
            when st_idle =>
                if start = '1' then
                    next_state <= st_sending;
                else
                    next_state <= st_idle;
                end if;

            -- Currently sending the bits, including stop and start.
            when st_sending =>
                if (tick = '1') and (bit_counter = 0) then
                    next_state <= st_idle;
                else
                    next_state <= st_sending;
                end if;

            when others =>
                next_state <= st_idle;
        end case;
    end process;

    -- Count the remaining bits to be transmitted.
    p_bit_counter: process (clock, reset_n)
    begin
        if reset_n = '0' then
            bit_counter <= 0;
        elsif rising_edge(clock) then
            case current_state is
                when st_idle =>
                    bit_counter <= 9;
                when st_sending =>
                    if (tick = '1') and (bit_counter /= 0) then
                        bit_counter <= bit_counter - 1;
                    else
                        bit_counter <= bit_counter;
                    end if;
                when others =>
                    bit_counter <= bit_counter;
            end case;
        end if;
    end process;

    -- Data register load and shift management
    p_data_shift: process (clock, reset_n)
    begin
        if reset_n = '0' then
            -- LSB must be 1 because it is the output of the UART and it shall
            -- be high when not transmitting.
            data_shift <= (others => '1');
        elsif rising_edge(clock) then
            case current_state is
                when st_idle =>
                    -- UART ready to send a new byte. If start is asserted,
                    -- initialize the shift register to store start bit, input
                    -- data and stop bit.
                    if start = '1' then
                        data_shift <= data & '0';
                    else
                        data_shift <= data_shift;
                    end if;

                when st_sending =>
                    if tick = '1' then
                        data_shift <= '1' & data_shift(8 downto 1);
                    else
                        data_shift <= data_shift;
                    end if;

                when others =>
                    data_shift <= data_shift;
            end case;
        end if;
    end process;

    tx <= data_shift(0);
    ready <= '1' when current_state = st_idle else '0';

end;
