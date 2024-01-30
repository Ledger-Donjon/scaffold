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
-- Basic UART receiver with FIFO buffer.
-- Baudrate is fixed, no parity bit.
--
entity buffered_uart_rx is
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
    -- High when data is available in the buffer.
    has_data: out std_logic;
    -- When high, pops the next byte from the FIFO at the next clock cycle to
    -- the output.
    read_request: std_logic;
    -- Received data, poped from the FIFO. Valid one clock cycle after
    -- read_request has been asserted.
    data: out std_logic_vector(7 downto 0);
    -- Number of bytes in the FIFO.
    size: out std_logic_vector(8 downto 0) );
end;


architecture behavior of buffered_uart_rx is
    -- High when there is data in the FIFO
    signal fifo_empty: std_logic;
    -- Received data from the non-buffered UART.
    signal light_uart_data: std_logic_vector(7 downto 0);
    -- High when a byte has been received.
    signal light_uart_has_data: std_logic;
begin
    -- Reading a byte from the FIFO takes one clock cycle (no read-ahead).
    e_fifo512: entity work.fifo512
    port map (
        aclr => not reset_n,
        sclr => '0',
        clock => clock,
        data => light_uart_data,
        wrreq => light_uart_has_data,
        q => data,
        empty => fifo_empty,
        rdreq => read_request,
        usedw => size );

    has_data <= not fifo_empty;
    
    e_light_uart_rx: entity work.light_uart_rx
    generic map (
        system_frequency => system_frequency,
        baudrate => baudrate )
    port map (
        clock => clock,
        reset_n => reset_n,
        rx => rx,
        has_data => light_uart_has_data,
        data => light_uart_data );
end;
