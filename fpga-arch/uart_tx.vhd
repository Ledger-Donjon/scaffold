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
-- UART transmitter.
-- Parameters of the UART are reconfigurable.
-- This entity is also able to generate a trigger signal at the end of byte
-- transmission, at the cost of one extra clock cycle.
--
entity uart_tx is
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
    -- Next byte to be sent.
    data: in std_logic_vector(7 downto 0);
    -- When high, send the next byte.
    start: in std_logic;
    -- High when UART is ready to send a new byte.
    ready: out std_logic;
    -- Output of the UART.
    tx: out std_logic;
    -- High during one clock cycle at the end of byte transmission.
    -- This signal is registered.
    trigger: out std_logic );
end;


architecture behavior of uart_tx is
    -- FSM states
    type state_t is (st_idle, st_sync, st_start_bit, st_bit_7, st_bit_6,
        st_bit_5, st_bit_4, st_bit_3, st_bit_2, st_bit_1, st_bit_0,
        st_parity_bit, st_stop_bit_1, st_stop_bit_2, st_trigger);

    -- Counter for baudrate generation
    signal baud_counter: unsigned(15 downto 0);
    -- FSM state
    signal state: state_t;

    -- Shift-register where the data to be sent is stored.
    -- Start bit and parity bit are included.
    signal data_shift: std_logic_vector(9 downto 0);

    -- High when baud_counter is zero.
    signal tick: std_logic;

    -- UART output register.
    signal tx_reg: std_logic;
begin

    -- Generate transmission rate using a counter.
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

    -- FSM management
    p_state: process (clock, reset_n)
    begin
        if reset_n = '0' then
            state <= st_idle;
        elsif rising_edge(clock) then
            case state is
                -- Not transmitting. Enter sync mode when a byte has to be
                -- transmitted.
                when st_idle =>
                    if start = '1' then
                        state <= st_sync;
                    else
                        state <= st_idle;
                    end if;

                -- Synchronizing to baudrate counter.
                when st_sync =>
                    if tick = '1' then
                        state <= st_start_bit;
                    else
                        state <= st_sync;
                    end if;

                -- Sending start bit.
                when st_start_bit =>
                    if tick = '1' then
                        state <= st_bit_7;
                    else
                        state <= st_start_bit;
                    end if;

                -- Sending bit 7.
                when st_bit_7 =>
                    if tick = '1' then
                        state <= st_bit_6;
                    else
                        state <= st_bit_7;
                    end if;

                -- Sending bit 6.
                when st_bit_6 =>
                    if tick = '1' then
                        state <= st_bit_5;
                    else
                        state <= st_bit_6;
                    end if;

                -- Sending bit 5.
                when st_bit_5 =>
                    if tick = '1' then
                        state <= st_bit_4;
                    else
                        state <= st_bit_5;
                    end if;

                -- Sending bit 4.
                when st_bit_4 =>
                    if tick = '1' then
                        state <= st_bit_3;
                    else
                        state <= st_bit_4;
                    end if;

                -- Sending bit 3.
                when st_bit_3 =>
                    if tick = '1' then
                        state <= st_bit_2;
                    else
                        state <= st_bit_3;
                    end if;

                -- Sending bit 2.
                when st_bit_2 =>
                    if tick = '1' then
                        state <= st_bit_1;
                    else
                        state <= st_bit_2;
                    end if;

                -- Sending bit 1.
                when st_bit_1 =>
                    if tick = '1' then
                        state <= st_bit_0;
                    else
                        state <= st_bit_1;
                    end if;

                -- Sending bit 0.
                when st_bit_0 =>
                    if tick = '1' then
                        if parity_mode = "00" then
                            state <= st_stop_bit_1;
                        else
                            state <= st_parity_bit;
                        end if;
                    else
                        state <= st_bit_0;
                    end if;

                -- Sending parity bit
                when st_parity_bit =>
                    if tick = '1' then
                        state <= st_stop_bit_1;
                    else
                        state <= st_parity_bit;
                    end if;

                -- Sending first stop bit
                when st_stop_bit_1 =>
                    if tick = '1' then
                        if stop_bits = '1' then
                            state <= st_stop_bit_2;
                        else
                            state <= st_trigger;
                        end if;
                    else
                        state <= st_stop_bit_1;
                    end if;

                -- Sending second stop bit
                when st_stop_bit_2 =>
                    if tick = '1' then
                        state <= st_trigger;
                    else
                        state <= st_stop_bit_2;
                    end if;

                -- One clock cycle for trigger generation.
                when st_trigger =>
                    state <= st_idle;

                when others =>
                    state <= st_idle;
            end case;
        end if;
    end process;

    -- Data register load and shift management
    p_data_shift: process (clock, reset_n)
    variable x: std_logic;
    begin
        if reset_n = '0' then
            -- LSB must be 1 because it is the output of the UART and it shall
            -- be high when not transmitting.
            data_shift <= (others => '1');
        elsif rising_edge(clock) then
            case state is
                when st_idle =>
                    if start = '1' then
                        -- Load the shift-register now
                        if parity_mode = "00" then
                            x := '1';
                        else
                            x := parity_mode(0);
                            for i in 0 to 7 loop
                                x := x xor data(i);
                            end loop;
                        end if;
                        data_shift <= x & data & '0';
                    else
                        data_shift <= data_shift;
                    end if;

                when st_sync =>
                    data_shift <= data_shift;

                when others =>
                    if tick = '1' then
                        data_shift <= '1' & data_shift(9 downto 1);
                    else
                        data_shift <= data_shift;
                    end if;
            end case;
        end if;
    end process;

    -- UART output
    p_tx_reg: process (clock, reset_n)
    begin
        if reset_n = '0' then
            tx_reg <= '1';
        elsif rising_edge(clock) then
            case state is
                when st_idle | st_sync =>
                    tx_reg <= '1';
                when others =>
                    tx_reg <= data_shift(0);
            end case;
        end if;
    end process;

    tx <= tx_reg;
    ready <= '1' when state = st_idle else '0';

    -- Trigger generation.
    p_trigger: process (clock, reset_n)
    begin
        if reset_n = '0' then
            trigger <= '0';
        elsif rising_edge(clock) then
            if state = st_trigger then
                trigger <= '1';
            else
                trigger <= '0';
            end if;
        end if;
    end process;

end;
