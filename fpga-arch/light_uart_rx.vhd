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
-- Basic UART receiver.
-- Baudrate is fixed, no parity bit.
--
entity light_uart_rx is
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
    -- Input signal. This signal is registered by light_uart_rx entity, so it
    -- can be directly connected to an input pin.
    rx: in std_logic;
    -- High during one clock cycle when a data byte has been received.
    has_data: out std_logic;
    -- Received data. Valid when has_data is asserted, until the next received
    -- byte.
    data: out std_logic_vector(7 downto 0) );
end;


architecture behavior of light_uart_rx is
    -- Number of cyles per bit
    constant period: integer := system_frequency / baudrate;

    -- FSM states for reception
    type state_t is (st_idle, st_receiving, st_has_data);

    -- Registration of rx signal
    signal rx_reg: std_logic;

    -- Current and next FSM states
    signal current_state: state_t;
    signal next_state: state_t;

    -- Counter for baudrate generation
    signal baud_counter: integer range 0 to period-1;
    -- High when a bit can be sampled.
    signal tick_mid: std_logic;

    -- Bit counter when receiving data.
    signal bit_counter: integer range 0 to 9;

    -- Shift-register where the received data is stored.
    -- Start bit is included (stop bit is not).
    signal data_shift: std_logic_vector(8 downto 0);

    -- Output data register.
    signal data_reg: std_logic_vector(7 downto 0);
begin

    -- Register rx input signal to avoid troubles when it is directly connected
    -- to an asynchronous input pin.
    p_rx_reg: process (clock, reset_n)
    begin
        if reset_n = '0' then
            rx_reg <= '1';
        elsif rising_edge(clock) then
            rx_reg <= rx;
        end if;
    end process;

    -- Generate reception rate using a counter.
    -- This counter is only active when receiving (we must synchronize counter
    -- start to frame start bit).
    p_baud_counter: process (clock, reset_n)
    begin
        if reset_n = '0' then
            baud_counter <= 0;
        elsif rising_edge(clock) then
            case current_state is
                when st_receiving =>
                    if baud_counter = period-1 then
                        baud_counter <= 0;
                    else
                        baud_counter <= baud_counter + 1;
                    end if;
                when others =>
                    -- Valid for st_idle
                    baud_counter <= 0;
            end case;
        end if;
    end process;

    tick_mid <= '1' when baud_counter = (period / 2) else '0';

    -- Next state to current state registration
    p_current_state: process (clock, reset_n)
    begin
        if reset_n = '0' then
            current_state <= st_idle;
        elsif rising_edge(clock) then
            current_state <= next_state;
        end if;
    end process;

    -- Calculate next state of FSM
    p_next_state: process (current_state, rx_reg, tick_mid, bit_counter)
    begin
        case current_state is
            -- Waiting for start bit to go low.
            when st_idle =>
                if rx_reg = '0' then
                    next_state <= st_receiving;
                else
                    next_state <= st_idle;
                end if;

            -- Currently receiving the bits, including start.
            -- Stop when the last bit is received (right before the stop bit).
            -- We don't want to wait until the end of the stop bit: if the
            -- emitter is faster than the receiver, the receiver will
            -- resynchronize at the next start bit (and possibly during the
            -- previous stop bit).
            when st_receiving =>
                if (tick_mid = '1') and (bit_counter = 0) then
                    next_state <= st_has_data;
                else
                    next_state <= st_receiving;
                end if;

            when st_has_data =>
                next_state <= st_idle;

            when others =>
                next_state <= st_idle;
        end case;
    end process;

    -- Count the remaining bits to be received.
    p_bit_counter: process (clock, reset_n)
    begin
        if reset_n = '0' then
            bit_counter <= 0;
        elsif rising_edge(clock) then
            case current_state is
                when st_idle =>
                    bit_counter <= 9;
                when st_receiving =>
                    if (tick_mid = '1') and (bit_counter /= 0) then
                        bit_counter <= bit_counter - 1;
                    else
                        bit_counter <= bit_counter;
                    end if;
                when others =>
                    bit_counter <= bit_counter;
            end case;
        end if;
    end process;

    -- Data register shift management.
    p_data_shift: process (clock, reset_n)
    begin
        if reset_n = '0' then
            data_shift <= (others => '1'); -- 1 or 0, whatever
        elsif rising_edge(clock) then
            case current_state is
                when st_receiving =>
                    if tick_mid = '1' then
                        data_shift <= rx_reg &
                            data_shift(data_shift'high downto 1);
                    else
                        data_shift <= data_shift;
                    end if;
                when others =>
                    -- Valid for st_idle
                    data_shift <= data_shift;
            end case;
        end if;
    end process;

    -- Data availability signal management
    p_has_data: process (clock, reset_n)
    begin
        if reset_n = '0' then
            has_data <= '0';
        elsif rising_edge(clock) then
            case current_state is
                when st_has_data => has_data <= '1';
                when others => has_data <= '0';
            end case;
        end if;
    end process;

    -- Copy the shift register to the data reg when a byte is received.
    p_data_reg: process (clock, reset_n)
    begin
        if reset_n = '0' then
            data_reg <= (others => '0');
        elsif rising_edge(clock) then
            case current_state is
                -- data_shift(0) is the start bit; skip it.
                when st_has_data => data_reg <= data_shift(7 downto 0);
                when others => data_reg <= data_reg;
            end case;
        end if;
    end process;

    data <= data_reg;

end;
