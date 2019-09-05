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
-- SPI master peripheral
--
entity spi_master is
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Input data to be sent.
    mosi_data: in std_logic_vector(31 downto 0);
    -- Received data register.
    miso_data: out std_logic_vector(31 downto 0);
    -- Transaction size -1.
    size_m1: in std_logic_vector(4 downto 0);
    -- When high, starts transmission.
    start: in std_logic;
    -- High during one clock cycle when transmission ends.
    eot: out std_logic;
    -- High while transmitting.
    busy: out std_logic;
    -- Phase and polarity configuration bits
    pha: in std_logic;
    pol: in std_logic;
    -- Baudrate divisor
    divisor: in std_logic_vector(15 downto 0);
    -- SPI bus signal
    sck: out std_logic;
    mosi: out std_logic;
    miso: in std_logic;
    ss: out std_logic );
end;


architecture behavior of spi_master is
    -- FSM states
    type state_t is (st_idle, st_sync_a, st_sync_b, st_transmit_a, st_transmit_b, st_eot);
    signal state: state_t;
    -- Counter for baudrate management
    signal baud_counter: unsigned(15 downto 0);
    -- High when baud_counter is zero.
    signal tick: std_logic;
    -- Number of bits remaining in transmission, minus one
    signal remaining_m1: std_logic_vector(4 downto 0);
    -- Transmission and reception buffers
    signal buf: std_logic_vector(31 downto 0);
    -- MISO value when sampled.
    signal sampled: std_logic;
begin
    -- Generate transmission rate using a counter
    p_baud_counter: process (clock, reset_n)
    begin
        if reset_n = '0' then
            baud_counter <= (others => '0');
        elsif rising_edge(clock) then
            if baud_counter = 0 then
                baud_counter <= unsigned(divisor);
            else
                baud_counter <= baud_counter - 1;
            end if;
        end if;
    end process;

    tick <= '1' when baud_counter = 0 else '0';

    -- FSM state management
    p_state: process (clock, reset_n)
    begin
        if reset_n = '0' then
            state <= st_idle;
        elsif rising_edge(clock) then
            case state is
                -- Not transmitting. Enter sync mode when transmission start is
                -- requested.
                when st_idle =>
                    if start = '1' then
                        state <= st_sync_a;
                    else
                        state <= st_idle;
                    end if;
                -- Synchronizing to baudrate counter.
                when st_sync_a =>
                    if tick = '1' then
                        state <= st_sync_b;
                    else
                        state <= st_sync_a;
                    end if;
                when st_sync_b =>
                    if tick = '1' then
                        state <= st_transmit_a;
                    else
                        state <= st_sync_b;
                    end if;
                -- Bit transmission, firt clock moment
                when st_transmit_a =>
                    if tick = '1' then
                        state <= st_transmit_b;
                    else
                        state <= st_transmit_a;
                    end if;
                -- Bit transmission, second clock moment
                when st_transmit_b =>
                    if tick = '1' then
                        if unsigned(remaining_m1) = 0 then
                            state <= st_eot;
                        else
                            state <= st_transmit_a;
                        end if;
                    else
                        state <= st_transmit_b;
                    end if;
                -- Asserts end-of-transmission flag
                when st_eot =>
                    state <= st_idle;
            end case;
        end if;
    end process;

    -- Buffer and remaining bit counter management
    p_buf: process (clock, reset_n)
    begin
        if reset_n = '0' then
            buf <= (others => '0');
            remaining_m1 <= (others => '0');
        elsif rising_edge(clock) then
            case state is
                when st_idle =>
                    if start = '1' then
                        remaining_m1 <= size_m1;
                        -- Fetch data to be transmitted
                        buf <= mosi_data;
                    else
                        remaining_m1 <= remaining_m1;
                        buf <= buf;
                    end if;
                when st_transmit_b =>
                    if tick = '1' then
                        -- Decrement bit counter.
                        -- We don't care about underflow, since the FSM shall
                        -- stop when it goes to zero and the counter is loaded
                        -- with size at the beginning of transaction.
                        remaining_m1 <=
                            std_logic_vector(unsigned(remaining_m1) - 1);
                        -- Shift-left and feed with sampled bit
                        buf <= buf(buf'high - 1 downto 0) & sampled;
                    else
                        remaining_m1 <= remaining_m1;
                        buf <= buf;
                    end if;
                when others =>
                    buf <= buf;
                    remaining_m1 <= remaining_m1;
            end case;
        end if;
    end process;

    -- End-of-Transmission flag
    p_eot: process (state)
    begin
        case state is
            when st_eot => eot <= '1';
            when others => eot <= '0';
        end case;
    end process;

    -- SCK and MOSI signals generation.
    -- Thoose signals are registered to remove glitches.
    p_sck_mosi: process (clock, reset_n)
    begin
        if reset_n = '0' then
            sck <= '1';
            mosi <= '1';
        elsif rising_edge(clock) then
            case state is
                when st_transmit_a =>
                    sck <= pha xor pol;
                    mosi <= buf(buf'high);
                when st_transmit_b =>
                    sck <= not (pha xor pol);
                    mosi <= buf(buf'high);
                when others =>
                   sck <= pol;
                   mosi <= '1';
            end case;
        end if;
    end process;

    -- Slave Select signal generation.
    p_ss: process (clock, reset_n)
    begin
        if reset_n = '0' then
            ss <= '1';
        elsif rising_edge(clock) then
            case state is
                when st_idle => ss <= '1';
                when others => ss <= '0';
            end case;
        end if;
    end process;
    
    -- MISO bit sampling
    p_sampled: process (clock, reset_n)
    begin
        if reset_n = '0' then
            sampled <= '0';
        elsif rising_edge(clock) then
            case state is
                when st_transmit_a =>
                    if tick = '1' then
                        sampled <= miso;
                    else
                        sampled <= sampled;
                    end if;
                when others =>
                    sampled <= sampled;
            end case;
        end if;
    end process;

    -- busy signal generation
    p_busy: process (state)
    begin
        case state is
            when st_idle => busy <= '0';
            when others => busy <= '1';
        end case;
    end process;
    
    miso_data <= buf;
end;
