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
-- UART transmitter and receiver with FIFO buffer for the transmission.
-- Baudrate is fixed, there is one stop bit and no parity bit.
--
-- This entity just regroups light_uart_tx and light_uart_rx entities.
--
entity buffered_uart is
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
    -- Next byte to be sent by the transmitter.
    data_tx: in std_logic_vector(7 downto 0);
    -- When high, send the next byte.
    start: in std_logic;
    -- High when UART can accept a new byte in its transmission FIFO.
    ready: out std_logic;
    -- High during one clock cycle when a data byte has been received.
    has_data: out std_logic;
    -- Received byte. Valid when has_data is asserted, until next byte is
    -- received.
    data_rx: out std_logic_vector(7 downto 0);
    -- UART receiver input. This signal is registered by the module, so it can
    -- be directly connected to an input pin.
    rx: in std_logic;
    -- Output of the UART.
    tx: out std_logic );
end;


architecture behavior of buffered_uart is
begin
    e_buffered_uart_tx: entity work.buffered_uart_tx
    generic map (
        system_frequency => system_frequency,
        baudrate => baudrate )
    port map (
        clock => clock,
        reset_n => reset_n,
        data => data_tx,
        start => start,
        ready => ready,
        tx => tx );

    e_light_uart_rx: entity work.light_uart_rx
    generic map (
        system_frequency => system_frequency,
        baudrate => baudrate )
    port map (
        clock => clock,
        reset_n => reset_n,
        rx => rx,
        has_data => has_data,
        data => data_rx );
end;
