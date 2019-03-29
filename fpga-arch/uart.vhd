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
-- UART transmitter and receiver.
--
-- This entity just regroups uart_tx and uart_rx entities.
-- Configurable baudrate and parity mode are the same of the transmitter and the
-- receiver.
--
-- Changing parity mode or baudrate during a transmission will corrupt outgoing
-- or incomming data.
--
-- There is no memory to hold the received data or to stack the bytes to be
-- transmitted.
--
entity uart is
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
    -- High when using two stop bits.
    stop_bits: in std_logic;
    -- Next byte to be sent by the transmitter.
    data_tx: in std_logic_vector(7 downto 0);
    -- When high, send the next byte.
    start: in std_logic;
    -- High when UART is ready to send a new byte.
    ready: out std_logic;
    -- High during one clock cycle when a data byte has been received.
    has_data: out std_logic;
    -- Received byte. Valid when has_data is asserted, until next byte is
    -- received.
    data_rx: out std_logic_vector(7 downto 0);
    -- If 1, a parity error occured during transmission. If 0, parity is ok.
    -- Valid when has_data is asserted, until the next received byte.
    parity_error: out std_logic;
    -- UART receiver input. This signal is registered by the module, so it can
    -- be directly connected to an input pin.
    rx: in std_logic;
    -- Output of the UART.
    tx: out std_logic;
    -- High during one clock cycle at the end of byte transmission.
    trigger: out std_logic );
end;


architecture behavior of uart is
begin

    e_uart_tx: entity work.uart_tx
    port map (
        clock => clock,
        reset_n => reset_n,
        divisor => divisor,
        parity_mode => parity_mode,
        stop_bits => stop_bits,
        data => data_tx,
        start => start,
        ready => ready,
        tx => tx,
        trigger => trigger );

    e_uart_rx: entity work.uart_rx
    port map (
        clock => clock,
        reset_n => reset_n,
        divisor => divisor,
        parity_mode => parity_mode,
        rx => rx,
        has_data => has_data,
        data => data_rx,
        parity_error => parity_error);

end;
