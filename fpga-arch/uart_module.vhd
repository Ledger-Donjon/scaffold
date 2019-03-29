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
-- Configurable UART module.
--
entity uart_module is
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Bus signals
    bus_in: in bus_in_t;

    -- Registers selection signals, from address decoder.
    en_status: in std_logic;
    en_control: in std_logic;
    en_config: in std_logic;
    en_divisor: in std_logic;
    en_data: in std_logic;

    -- Output registers
    reg_data: out byte_t;
    reg_status: out byte_t;

    -- UART signals
    tx: out std_logic;
    rx: in std_logic;
    trigger: out std_logic );
end;


architecture behavior of uart_module is
    -- Status register
    signal status: byte_t;
    signal ready: std_logic;
    signal parity_error: std_logic;
    -- Configuration registers
    signal config: byte_t;
    signal divisor: std_logic_vector(15 downto 0);
    signal parity_mode: std_logic_vector(1 downto 0);
    signal stop_bits: std_logic;
    signal trigger_en: std_logic;

    -- UART transmission trigger
    signal start: std_logic;
    -- UART trigger output.
    signal uart_trigger: std_logic;
    -- High when UART received a byte.
    signal has_data: std_logic;
    -- Data received by UART
    signal data_rx: byte_t;
    -- Parity error flag from UART
    signal parity_error_tmp: std_logic;
    -- FIFO output byte
    signal fifo_q: byte_t;
    -- High when FIFO is empty.
    signal fifo_empty: std_logic;
    -- FIFO read request input.
    signal fifo_rdreq: std_logic;
    -- High when FIFO must be flushed.
    signal fifo_flush: std_logic;

begin

    -- FIFO to store received bytes
    e_fifo512: entity work.fifo512
    port map (
        aclr => not reset_n,
        sclr => fifo_flush,
        clock => clock,
        data => data_rx,
        wrreq => has_data,
        q => fifo_q,
        empty => fifo_empty,
        rdreq => fifo_rdreq );

    fifo_rdreq <= en_data and bus_in.read;
    -- Flush the FIFO when bit 0 of control register is written to 1.
    fifo_flush <= en_control and bus_in.write and bus_in.write_data(0);

    start <= en_data and bus_in.write;

    e_uart: entity work.uart
    port map (
        clock => clock,
        reset_n => reset_n,
        divisor => divisor,
        parity_mode => parity_mode,
        stop_bits => stop_bits,
        data_tx => bus_in.write_data,
        start => start,
        ready => ready,
        has_data => has_data,
        data_rx => data_rx,
        parity_error => parity_error_tmp,
        trigger => uart_trigger,
        rx => rx,
        tx => tx );

    -- UART transmission trigger
    -- Register the signal again for sake.
    p_trigger: process (clock, reset_n)
    begin
        if reset_n = '0' then
            trigger <= '0';
        elsif rising_edge(clock) then
            trigger <= uart_trigger and trigger_en;
        end if;
    end process;

    e_config: entity work.module_reg
    generic map (reset => x"00")
    port map (
        clock => clock,
        reset_n => reset_n,
        en => en_config,
        bus_in => bus_in,
        value => config );

    parity_mode <= config(1 downto 0);
    stop_bits <= config(2);
    trigger_en <= config(3);

    e_divisor: entity work.module_wide_reg
    generic map (wideness => 2, reset => x"28af")
    port map (
        clock => clock,
        reset_n => reset_n,
        en => en_divisor,
        bus_in => bus_in,
        value => divisor );

    -- Make parity errors persistent until cleared.
    p_parity_error: process (clock, reset_n)
    begin
        if reset_n = '0' then
            parity_error <= '0';
        elsif rising_edge(clock) then
            if parity_error_tmp = '1' then
                parity_error <= '1';
            else
                if (bus_in.write = '1') and (bus_in.write_data(1) = '0') then
                    parity_error <= '0';
                else
                    parity_error <= parity_error;
                end if;
            end if;
        end if;
    end process;

    status(0) <= ready;
    status(1) <= parity_error;
    status(2) <= fifo_empty;
    status(7 downto 3) <= (others => '0');
    reg_status <= status;
    reg_data <= fifo_q;
end;
