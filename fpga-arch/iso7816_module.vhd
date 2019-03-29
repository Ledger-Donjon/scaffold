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
-- ISO7816 tranceiver module.
--
entity iso7816_module is
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
    en_etu: in std_logic;
    en_data: in std_logic;

    -- Output registers
    reg_data: out byte_t;
    reg_status: out byte_t;

    -- I/O signal as input.
    io_in: in std_logic;
    -- I/O signal as output.
    io_out: out std_logic;
    -- High when the tranceiver controls the I/O line.
    io_oe: out std_logic;
    -- Clock signal provided on the ISO7816 interface.
    clk: out std_logic;
    -- Transmission trigger signal.
    trigger: out std_logic );
end;


architecture behavior of iso7816_module is
    -- Status register
    signal status: byte_t;
    signal ready: std_logic;
    signal parity_error: std_logic;
    -- Configuration registers
    signal config: byte_t;
    signal trigger_tx_en: std_logic;
    signal trigger_rx_en: std_logic;
    signal trigger_long_en: std_logic;
    -- Divisor register
    signal divisor: byte_t;
    -- ETU register
    signal etu_16: std_logic_vector(15 downto 0);
    signal etu: std_logic_vector(10 downto 0);

    -- Transmission trigger
    signal start: std_logic;
    -- High when transceiver received a byte.
    signal has_data: std_logic;
    -- Received data byte.
    signal data_in: byte_t;
    -- Parity error flag from transceiver.
    signal parity_error_tmp: std_logic;
    -- FIFO output byte
    signal fifo_q: byte_t;
    -- High when FIFO is empty.
    signal fifo_empty: std_logic;
    -- FIFO read request input.
    signal fifo_rdreq: std_logic;
    -- High when FIFO must be flushed.
    signal fifo_flush: std_logic;
    -- High during one clock cycle, at the end of byte transmission.
    signal trigger_tx: std_logic;
    -- High during one clock cycle, at the beginning of byte reception.
    signal trigger_rx: std_logic;
    -- Long trigger signal.
    signal trigger_long: std_logic;
    -- Parity mode.
    signal parity_mode: std_logic_vector(1 downto 0);

begin

    -- FIFO to store received bytes
    e_fifo512: entity work.fifo512
    port map (
        aclr => not reset_n,
        sclr => fifo_flush,
        clock => clock,
        data => data_in,
        wrreq => has_data,
        q => fifo_q,
        empty => fifo_empty,
        rdreq => fifo_rdreq );

    fifo_rdreq <= en_data and bus_in.read;
    -- Flush the FIFO when bit 0 of control register is written to 1.
    fifo_flush <= en_control and bus_in.write and bus_in.write_data(0);

    start <= en_data and bus_in.write;

    e_iso7816: entity work.iso7816
    port map (
        clock => clock,
        reset_n => reset_n,
        divisor => divisor,
        etu => etu,
        parity_mode => parity_mode,
        data_out => bus_in.write_data,
        start => start,
        ready => ready,
        has_data => has_data,
        data_in => data_in,
        parity_error => parity_error_tmp,
        trigger_tx => trigger_tx,
        trigger_rx => trigger_rx,
        clk => clk,
        io_in => io_in,
        io_out => io_out,
        io_oe => io_oe );

    e_config: entity work.module_reg
    generic map (reset => x"00")
    port map (
        clock => clock,
        reset_n => reset_n,
        en => en_config,
        bus_in => bus_in,
        value => config );

    trigger_tx_en <= config(0);
    trigger_rx_en <= config(1);
    trigger_long_en <= config(2);
    parity_mode <= config(4 downto 3);

    e_divisor: entity work.module_reg
    generic map (reset => x"63") -- Divide by 100 for 1 MHz
    port map (
        clock => clock,
        reset_n => reset_n,
        en => en_divisor,
        bus_in => bus_in,
        value => divisor );

    e_etu: entity work.module_wide_reg
    generic map (wideness => 2, reset => x"0173") -- ETU 372
    port map (
        clock => clock,
        reset_n => reset_n,
        en => en_etu,
        bus_in => bus_in,
        value => etu_16 );

    etu <= etu_16(etu'high downto 0);

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

    -- Trigger management.
    p_trigger: process (clock, reset_n)
    begin
        if reset_n = '0' then
            trigger_long <= '0';
            trigger <= '0';
        elsif rising_edge(clock) then
            trigger_long <= (trigger_long or trigger_tx) and (not trigger_rx)
                and trigger_long_en;
            trigger <= trigger_long
                or (trigger_tx and trigger_tx_en)
                or (trigger_rx and trigger_rx_en);
        end if;
    end process;

    status(0) <= ready;
    status(1) <= parity_error;
    status(2) <= fifo_empty;
    status(7 downto 3) <= (others => '0');
    reg_status <= status;
    reg_data <= fifo_q;
end;
