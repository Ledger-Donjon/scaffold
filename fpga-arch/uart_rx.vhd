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
-- UART receiver.
-- Baudrate and parity mode are reconfigurable.
--
entity uart_rx is
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Baudrate divisor.
    -- Minimum is 1.
    -- Effective baudrate is F / (divisor+1) where F is the clock frequency.
    divisor: in std_logic_vector(15 downto 0);
    -- Parity mode
    -- 00: no parity
    -- 01: odd parity
    -- 10: even parity
    parity_mode: in std_logic_vector(1 downto 0);
    -- Input signal. This signal is registered by uart_rx entity, so it can be
    -- directly connected to an input pin.
    rx: in std_logic;
    -- High during one clock cycle when a data byte has been received.
    has_data: out std_logic;
    -- Received data. Valid when has_data is asserted, until the next received
    -- byte.
    data: out std_logic_vector(7 downto 0);
    -- If 1, a parity error occured during transmission. If 0, parity is ok.
    -- Valid when has_data is asserted, until the next received byte.
    parity_error: out std_logic );
end;


architecture behavior of uart_rx is
    -- FSM states for reception
    type state_t is (st_idle, st_start_bit, st_bit_7, st_bit_6, st_bit_5,
        st_bit_4, st_bit_3, st_bit_2, st_bit_1, st_bit_0, st_parity_bit,
        st_stop_bit, st_wait_high, st_has_data);

    -- Registration of rx signal
    signal rx_reg: std_logic;

    -- FSM state
    signal state: state_t;

    -- Counter for baudrate generation
    signal baud_counter: unsigned(15 downto 0);
    -- High when baud_counter is 0.
    signal tick: std_logic;
    -- High when a bit can be sampled.
    signal tick_mid: std_logic;

    -- Shift-register where the received data is stored.
    -- Start bit, parity bit and stop bits are not included.
    signal data_shift: std_logic_vector(7 downto 0);
    -- Sampled parity bit.
    signal parity_bit: std_logic;
    -- Result of parity error calculation. This is not register.
    signal parity_error_tmp: std_logic;
    -- Registered parity error. Copies parity_error_tmp when has_data is
    -- asserted.
    signal parity_error_reg: std_logic;

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
            baud_counter <= (others => '0');
        elsif rising_edge(clock) then
            case state is
                when st_start_bit | st_bit_7 | st_bit_6 | st_bit_5 | st_bit_4 |
                    st_bit_3 | st_bit_2 | st_bit_1 | st_bit_0 | st_parity_bit |
                    st_stop_bit =>
                    if baud_counter = 0 then
                        baud_counter <= unsigned(divisor);
                    else
                        baud_counter <= baud_counter - 1;
                    end if;
                when others =>
                    -- Valid for st_idle
                    baud_counter <= unsigned(divisor);
            end case;
        end if;
    end process;

    tick <= '1' when baud_counter = 0 else '0';
    tick_mid <= '1' when baud_counter = (unsigned(divisor) / 2) else '0';

    p_state: process (clock, reset_n)
    begin
        if reset_n = '0' then
            state <= st_idle;
        elsif rising_edge(clock) then
            case state is
                -- Waiting for start bit.
                when st_idle =>
                    if rx_reg = '0' then
                        state <= st_start_bit;
                    else
                        state <= st_idle;
                    end if;

                -- Receiving start bit.
                when st_start_bit =>
                    if tick = '1' then
                        state <= st_bit_7;
                    else
                        state <= st_start_bit;
                    end if;

                -- Receiving bit 7.
                when st_bit_7 =>
                    if tick = '1' then
                        state <= st_bit_6;
                    else
                        state <= st_bit_7;
                    end if;

                -- Receiving bit 6.
                when st_bit_6 =>
                    if tick = '1' then
                        state <= st_bit_5;
                    else
                        state <= st_bit_6;
                    end if;

                -- Receiving bit 5.
                when st_bit_5 =>
                    if tick = '1' then
                        state <= st_bit_4;
                    else
                        state <= st_bit_5;
                    end if;

                -- Receiving bit 4.
                when st_bit_4 =>
                    if tick = '1' then
                        state <= st_bit_3;
                    else
                        state <= st_bit_4;
                    end if;

                -- Receiving bit 3.
                when st_bit_3 =>
                    if tick = '1' then
                        state <= st_bit_2;
                    else
                        state <= st_bit_3;
                    end if;

                -- Receiving bit 2.
                when st_bit_2 =>
                    if tick = '1' then
                        state <= st_bit_1;
                    else
                        state <= st_bit_2;
                    end if;

                -- Receiving bit 1.
                when st_bit_1 =>
                    if tick = '1' then
                        state <= st_bit_0;
                    else
                        state <= st_bit_1;
                    end if;

                -- Receiving bit 0.
                when st_bit_0 =>
                    if tick = '1' then
                        if parity_mode = "00" then
                            state <= st_stop_bit;
                        else
                            state <= st_parity_bit;
                        end if;
                    else
                        state <= st_bit_0;
                    end if;

                -- Receiving parity bit.
                when st_parity_bit =>
                    if tick = '1' then
                        state <= st_stop_bit;
                    else
                        state <= st_parity_bit;
                    end if;

                -- Receiving stop bit.
                when st_stop_bit =>
                    -- Exit earlier to allow resynchronization when next start
                    -- bit of next byte comes (we use tick_mid, not tick).
                    if tick_mid = '1' then
                        state <= st_has_data;
                    else
                        state <= st_stop_bit;
                    end if;

                -- State which is one cycle long, just to tell a byte has been
                -- received.
                when st_has_data =>
                    state <= st_wait_high;

                -- State in which we wait the transmission line to return to
                -- high logic state. This prevents receiving zeros in loop if
                -- the reception line is kept to low.
                when st_wait_high =>
                    if rx_reg = '1' then
                        state <= st_idle;
                    else
                        state <= st_wait_high;
                    end if;

                when others =>
                    state <= st_idle;
            end case;
        end if;
    end process;

    -- Data register shift management.
    p_data_shift: process (clock, reset_n)
    begin
        if reset_n = '0' then
            data_shift <= (others => '1'); -- 1 or 0, whatever
        elsif rising_edge(clock) then
            case state is
                when st_bit_7 | st_bit_6 | st_bit_5 | st_bit_4 | st_bit_3 |
                    st_bit_2 | st_bit_1 | st_bit_0 =>
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

    -- Parity bit sampling.
    p_parity_bit: process (clock, reset_n)
    begin
        if reset_n = '0' then
            parity_bit <= '1'; -- 1 or 0, whatever.
        elsif rising_edge(clock) then
            case state is
                when st_parity_bit =>
                    if tick_mid = '1' then
                        parity_bit <= rx_reg;
                    else
                        parity_bit <= parity_bit;
                    end if;
                when others =>
                    parity_bit <= parity_bit;
            end case;
        end if;
    end process;

    -- Parity error detection
    p_parity_error_tmp: process (data_shift, parity_mode, parity_bit)
    variable x: std_logic;
    begin
        if parity_mode = "00" then
            parity_error_tmp <= '0';
        else
            x := parity_mode(0);
            for i in 0 to 7 loop
                x := x xor data_shift(i);
            end loop;
            x := x xor parity_bit;
            parity_error_tmp <= x;
        end if;
    end process;

    -- Data output
    p_has_data: process (clock, reset_n)
    begin
        if reset_n = '0' then
            has_data <= '0';
            data_reg <= (others => '0');
            parity_error_reg <= '0';
        elsif rising_edge(clock) then
            case state is
                when st_has_data =>
                    has_data <= '1';
                    data_reg <= data_shift(7 downto 0);
                    parity_error_reg <= parity_error_tmp;
                when others =>
                    has_data <= '0';
                    data_reg <= data_reg;
                    parity_error_reg <= parity_error_reg;
            end case;
        end if;
    end process;

    data <= data_reg;
    parity_error <= parity_error_reg;

end;
