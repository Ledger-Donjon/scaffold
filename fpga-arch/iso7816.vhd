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
-- ISO7816 reader interface.
--
-- Character repetition is not supported.
--
entity iso7816 is
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- I/O signal as input.
    io_in: in std_logic;
    -- I/O signal as output.
    io_out: out std_logic;
    -- High when the tranceiver controls the I/O line.
    io_oe: out std_logic;
    -- Clock signal provided on the ISO7816 interface.
    clk: out std_logic;
    -- Clock divisor for ISO7816 clock generation.
    -- Output clock frequency is (system_frequency / (2*(divisor+1))).
    -- According to ISO7816-3 specification, minimum frequency is 1 Mhz, maximum
    -- frequency is 5 Mhz. A 8-bits divisor allows reaching both limits.
    divisor: in std_logic_vector(7 downto 0);
    -- ETU parameter (minus 1).
    -- Maximum ETU value is 2048 (for 20 MHz clk).
    etu: in std_logic_vector(10 downto 0);
    -- Parity mode:
    -- - 0b00: even parity (standard and default)
    -- - 0b01: odd parity
    -- - 0b10: parity bit always 0
    -- - 0b11: parity bit always 1
    parity_mode: in std_logic_vector(1 downto 0);
    -- When high, transmit byte.
    start: in std_logic;
    -- Byte to be transmitted when start is asserted.
    data_out: in byte_t;
    -- High during one clock cycle when a byte has been received.
    has_data: out std_logic;
    -- Last received data byte.
    data_in: out byte_t;
    -- High when parity is wrong on last received byte.
    parity_error: out std_logic;
    -- High when transceiver is ready to send another byte.
    ready: out std_logic;
    -- High during one clock cycle at the end of byte transmission.
    -- This signal is not registered.
    trigger_tx: out std_logic;
    -- High during one clock cycle at the beginning of new byte reception.
    trigger_rx: out std_logic );
end;


architecture behavior of iso7816 is
    -- FSM states.
    type state_t is (
        st_idle,
        st_tx_sync,
        st_tx_start_bit,
        st_tx_bit_7,
        st_tx_bit_6,
        st_tx_bit_5,
        st_tx_bit_4,
        st_tx_bit_3,
        st_tx_bit_2,
        st_tx_bit_1,
        st_tx_bit_0,
        st_tx_parity_bit,
        st_tx_pause,
        st_rx_start_bit,
        st_rx_bit_7,
        st_rx_bit_6,
        st_rx_bit_5,
        st_rx_bit_4,
        st_rx_bit_3,
        st_rx_bit_2,
        st_rx_bit_1,
        st_rx_bit_0,
        st_rx_parity_bit,
        st_rx_pause,
        st_has_data );

    -- Current FSM state.
    signal state: state_t;
    -- Counter for clk generation.
    signal clk_counter: std_logic_vector(7 downto 0);
    -- Register for clk signal generation.
    signal clk_reg: std_logic;
    -- High when clk goes from 0 to 1.
    signal clk_tick: std_logic;
    -- ETU counter.
    signal etu_counter: std_logic_vector(10 downto 0);
    -- High when ETU counter is zero.
    signal etu_tick: std_logic;
    -- High when incomming bit can be sampled.
    signal etu_tick_mid: std_logic;

    -- Sampled input IO signal.
    signal io_in_reg: std_logic;
    -- Transmission and reception buffer.
    signal shift_buf: std_logic_vector(9 downto 0);
begin

    -- IO input registration.
    p_io_in_reg: process (clock, reset_n)
    begin
        if reset_n = '0' then
            io_in_reg <= '1';
        elsif rising_edge(clock) then
            io_in_reg <= io_in;
        end if;
    end process;

    -- ISO7816 clock generation.
    -- Use a counter to toggle clk.
    -- Set clk_tick to high when clk goes from 0 to 1.
    p_clk_reg: process (clock, reset_n)
    begin
        if reset_n = '0' then
            clk_reg <= '0';
            clk_counter <= (others => '0');
            clk_tick <= '0';
        elsif rising_edge(clock) then
            if unsigned(clk_counter) = 0 then
                clk_counter <= divisor;
                clk_reg <= not clk_reg;
                clk_tick <= not clk_reg;
            else
                clk_counter <= std_logic_vector(unsigned(clk_counter) - 1);
                clk_reg <= clk_reg;
                clk_tick <= '0';
            end if;
        end if;
    end process;

    -- ETU counter
    etu_tick <= '1' when (unsigned(etu_counter) = 0) and (clk_tick = '1')
        else '0';
    etu_tick_mid <= '1' when (unsigned(etu_counter) = unsigned(etu) / 2)
        and (clk_tick = '1') else '0';

    p_etu_counter: process (clock, reset_n)
    begin
        if reset_n = '0' then
            etu_counter <= (others => '0');
        elsif rising_edge(clock) then
            case state is
                when st_idle =>
                    etu_counter <= etu;
                when others =>
                    if clk_tick = '1' then
                        if unsigned(etu_counter) = 0 then
                            etu_counter <= etu;
                        else
                            etu_counter <= std_logic_vector(unsigned(etu_counter) - 1);
                        end if;
                    else
                        etu_counter <= etu_counter;
                    end if;
            end case;
        end if;
    end process;

    -- FSM
    p_fsm: process (clock, reset_n)
    begin
        if reset_n = '0' then
            state <= st_idle;
        elsif rising_edge(clock) then
            case state is
                -- Waiting for byte reception or transmission.
                -- Start reception if IO is low (start bit).
                -- Start transmission if start is asserted.
                -- Reception has priority over transmission: if IO is low and
                -- start is asserted, the byte to be sent is dropped and FSM
                -- start receiving.
                when st_idle =>
                    if io_in_reg = '0' then
                        -- Start bit detected. Enter reception mode.
                        state <= st_rx_start_bit;
                    elsif start = '1' then
                        state <= st_tx_sync;
                    else
                        state <= st_idle;
                    end if;

                -- Synchronize transmission
                when st_tx_sync =>
                    if etu_tick = '1' then
                        state <= st_tx_start_bit;
                    else
                        state <= st_tx_sync;
                    end if;

                -- Transmitting start bit.
                when st_tx_start_bit =>
                    if etu_tick = '1' then
                        state <= st_tx_bit_7;
                    else
                        state <= st_tx_start_bit;
                    end if;

                -- Transmitting bit 7
                when st_tx_bit_7 =>
                    if etu_tick = '1' then
                        state <= st_tx_bit_6;
                    else
                        state <= st_tx_bit_7;
                    end if;

                -- Transmitting bit 6
                when st_tx_bit_6 =>
                    if etu_tick = '1' then
                        state <= st_tx_bit_5;
                    else
                        state <= st_tx_bit_6;
                    end if;

                -- Transmitting bit 5
                when st_tx_bit_5 =>
                    if etu_tick = '1' then
                        state <= st_tx_bit_4;
                    else
                        state <= st_tx_bit_5;
                    end if;

                -- Transmitting bit 4
                when st_tx_bit_4 =>
                    if etu_tick = '1' then
                        state <= st_tx_bit_3;
                    else
                        state <= st_tx_bit_4;
                    end if;

                -- Transmitting bit 3
                when st_tx_bit_3 =>
                    if etu_tick = '1' then
                        state <= st_tx_bit_2;
                    else
                        state <= st_tx_bit_3;
                    end if;

                -- Transmitting bit 2
                when st_tx_bit_2 =>
                    if etu_tick = '1' then
                        state <= st_tx_bit_1;
                    else
                        state <= st_tx_bit_2;
                    end if;

                -- Transmitting bit 1
                when st_tx_bit_1 =>
                    if etu_tick = '1' then
                        state <= st_tx_bit_0;
                    else
                        state <= st_tx_bit_1;
                    end if;

                -- Transmitting bit 0
                when st_tx_bit_0 =>
                    if etu_tick = '1' then
                        state <= st_tx_parity_bit;
                    else
                        state <= st_tx_bit_0;
                    end if;

                -- Transmitting parity bit
                when st_tx_parity_bit =>
                    if etu_tick = '1' then
                        state <= st_tx_pause;
                    else
                        state <= st_tx_parity_bit;
                    end if;

                -- Pause after byte transmission.
                when st_tx_pause =>
                    if etu_tick = '1' then
                        state <= st_idle;
                    else
                        state <= st_tx_pause;
                    end if;

                -- Receiving start bit
                when st_rx_start_bit =>
                    if etu_tick = '1' then
                        state <= st_rx_bit_7;
                    else
                        state <= st_rx_start_bit;
                    end if;

                -- Receiving bit 7
                when st_rx_bit_7 =>
                    if etu_tick = '1' then
                        state <= st_rx_bit_6;
                    else
                        state <= st_rx_bit_7;
                    end if;

                -- Receiving bit 6
                when st_rx_bit_6 =>
                    if etu_tick = '1' then
                        state <= st_rx_bit_5;
                    else
                        state <= st_rx_bit_6;
                    end if;

                -- Receiving bit 5
                when st_rx_bit_5 =>
                    if etu_tick = '1' then
                        state <= st_rx_bit_4;
                    else
                        state <= st_rx_bit_5;
                    end if;

                -- Receiving bit 4
                when st_rx_bit_4 =>
                    if etu_tick = '1' then
                        state <= st_rx_bit_3;
                    else
                        state <= st_rx_bit_4;
                    end if;

                -- Receiving bit 3
                when st_rx_bit_3 =>
                    if etu_tick = '1' then
                        state <= st_rx_bit_2;
                    else
                        state <= st_rx_bit_3;
                    end if;

                -- Receiving bit 2
                when st_rx_bit_2 =>
                    if etu_tick = '1' then
                        state <= st_rx_bit_1;
                    else
                        state <= st_rx_bit_2;
                    end if;

                -- Receiving bit 1
                when st_rx_bit_1 =>
                    if etu_tick = '1' then
                        state <= st_rx_bit_0;
                    else
                        state <= st_rx_bit_1;
                    end if;

                -- Receiving bit 0
                when st_rx_bit_0 =>
                    if etu_tick = '1' then
                        state <= st_rx_parity_bit;
                    else
                        state <= st_rx_bit_0;
                    end if;

                -- Receiving parity bit
                when st_rx_parity_bit =>
                    if etu_tick = '1' then
                        state <= st_rx_pause;
                    else
                        state <= st_rx_parity_bit;
                    end if;

                -- Pause after byte reception. This pause is shorter than a bit
                -- duration, to be ready to receive a new byte and resynchronize
                -- if the emitter is faster than the receiver.
                when st_rx_pause =>
                    if etu_tick_mid = '1' then
                        state <= st_has_data;
                    else
                        state <= st_rx_pause;
                    end if;

                -- One clock cycle long state to indicate a byte has been received.
                when st_has_data =>
                    state <= st_idle;

            end case;
        end if;
    end process;

    -- Shift buffer management.
    p_shift_buf: process (clock, reset_n)
        variable parity: std_logic;
    begin
        if reset_n = '0' then
            shift_buf <= (others => '0');
        elsif rising_edge(clock) then
            case state is
                when st_idle =>
                    if start = '1' then
                        -- Calculate parity bit.
                        parity := parity_mode(0);
                        if parity_mode(1) = '0' then
                            for i in 0 to 7 loop
                                parity := parity xor data_out(i);
                            end loop;
                        end if;
                        shift_buf <= parity & data_out & '0';
                    else
                        shift_buf <= shift_buf;
                    end if;

                when st_tx_start_bit | st_tx_bit_7 | st_tx_bit_6 | st_tx_bit_5 |
                    st_tx_bit_4 | st_tx_bit_3  | st_tx_bit_2 | st_tx_bit_1 |
                    st_tx_bit_0 | st_tx_parity_bit =>
                    if etu_tick = '1' then
                        -- Shift right, drop LSB.
                        shift_buf <= '1' & shift_buf(shift_buf'high downto 1);
                    else
                        shift_buf <= shift_buf;
                    end if;

                when st_rx_start_bit | st_rx_bit_7 | st_rx_bit_6 | st_rx_bit_5 |
                    st_rx_bit_4 | st_rx_bit_3 | st_rx_bit_2 | st_rx_bit_1 |
                    st_rx_bit_0 | st_rx_parity_bit =>
                    if etu_tick_mid = '1' then
                        -- Shift right, get MSB.
                        shift_buf <= io_in_reg & shift_buf(shift_buf'high downto 1);
                    else
                        shift_buf <= shift_buf;
                    end if;

                when others =>
                    shift_buf <= shift_buf;
            end case;
        end if;
    end process;

    -- has_data, data_in and parity_error signals.
    p_data_in: process (clock, reset_n)
        variable p: std_logic;
    begin
        if reset_n = '0' then
            has_data <= '0';
            data_in <= x"00";
            parity_error <= '0';
        elsif rising_edge(clock) then
            case state is
                when st_has_data =>
                    has_data <= '1';
                    data_in <= shift_buf(8 downto 1);
                    p := '0';
                    for i in 1 to 9 loop
                        p := p xor shift_buf(i);
                    end loop;
                    parity_error <= p;
                when others =>
                    has_data <= '0';
                    data_in <= data_in;
                    parity_error <= parity_error;
            end case;
        end if;
    end process;

    -- Ready signal
    ready <= '1' when state = st_idle else '0';

    p_out: process (clock, reset_n)
    begin
        if reset_n = '0' then
            io_out <= '1';
            io_oe <= '0';
        elsif rising_edge(clock) then
            case state is
                when st_tx_start_bit | st_tx_bit_7 | st_tx_bit_6 | st_tx_bit_5 |
                    st_tx_bit_4 | st_tx_bit_3 | st_tx_bit_2 | st_tx_bit_1 |
                    st_tx_bit_0 | st_tx_parity_bit =>
                    io_out <= shift_buf(0);
                    io_oe <= '1';
                when others =>
                    io_out <= '1';
                    io_oe <= '0';
            end case;
        end if;
    end process;

    -- Triggers
    trigger_tx <= '1' when (state = st_tx_parity_bit) and (etu_tick = '1') else '0';
    trigger_rx <= '1' when (state = st_idle) and (io_in_reg = '0') else '0';

    clk <= clk_reg;

end;
