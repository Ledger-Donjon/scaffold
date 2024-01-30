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
-- UART transmitter with a buffer FIFO.
-- Baudrate is fixed, there is one stop bit and no parity bit.
--
entity buffered_uart_tx is
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


architecture behavior of buffered_uart_tx is
    -- The buffer FIFO has no read ahead and requires one clock cycle to output
    -- oldest byte on request. So we need a very small state machine to handle
    -- this.
    type state_t is (st_idle, st_transmit);
    -- Current FSM state
    signal current_state: state_t;
    -- Next FSM state
    signal next_state: state_t;

    -- Output of the buffer FIFO
    signal fifo_q: std_logic_vector(7 downto 0);
    -- High when the buffer FIFO cannot accept any more byte
    signal fifo_full: std_logic;
    -- High when the buffer FIFO has no data.
    signal fifo_empty: std_logic;
    -- High when a byte from the FIFO must be poped.
    signal fifo_rdreq: std_logic;

    -- High when the unbuffered UART is ready to send another byte.
    signal light_uart_ready: std_logic;
    -- High starts a new UART transmission.
    signal light_uart_start: std_logic;
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

    -- Next state calculation and control signals
    p_fsm: process (current_state, fifo_empty, light_uart_ready)
    begin
        case current_state is
            when st_idle =>
                if (not fifo_empty) and light_uart_ready then
                    next_state <= st_transmit;
                    fifo_rdreq <= '1';
                else
                    next_state <= st_idle;
                    fifo_rdreq <= '0';
                end if;
                light_uart_start <= '0';
            when st_transmit =>
                next_state <= st_idle;
                fifo_rdreq <= '0';
                light_uart_start <= '1';
        end case;
    end process;

    -- Reading the FIFO takes one clock cycle, there is no read ahead.
    e_fifo512: entity work.fifo512
    port map (
        clock => clock,
        aclr => not reset_n,
        sclr => '0',
        data => data,
        wrreq => start,
        q => fifo_q,
        full => fifo_full,
        empty => fifo_empty,
        rdreq => fifo_rdreq );

    ready <= not fifo_full;

    e_uart_tx: entity work.light_uart_tx
    generic map (
        system_frequency => system_frequency,
        baudrate => baudrate )
    port map (
        clock => clock,
        reset_n => reset_n,
        data => fifo_q,
        start => light_uart_start,
        ready => light_uart_ready,
        tx => tx );
end;
