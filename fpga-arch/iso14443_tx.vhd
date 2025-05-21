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
-- Copyright 2025 Ledger SAS, written by Olivier Hériveaux


library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;


-- Manages transmission baudrate and divides a bit into 4 periods. Each period
-- represents a symbol which corresponds to ISO-14443A X, Y and Z sequences.
--
-- Transmission starts when start signal is asserted. This copies the symbol
-- input. On last transmission cycle, ready is asserted, allowing to chain
-- immediately a next transmission.
--
-- In following chronograms:
-- - X and Y are 4-bit input symbols
-- - counter is the tick counter whose max value is 3 for the example, 235 for
--   the real implementation.
-- - A, B, C and D are the sequence bit values from X and Y. They represent the
--   four transmission moments.
--
-- Single transmission example:
--
-- symbol:  *****X**********************
-- start:   000001***************0000000
-- counter: 3333333210321032103210333333
-- tick:    0000000001000100010001000000
-- ready:   1111110000000000000001111111
-- tx:      111111AAAABBBBCCCCDDDD111111
-- state:   [idle][m1][m2][m3][m4][idle]
--                [---sequence---]
--
-- Chained transmission example
--
-- symbol:  *****X***************Y**********************
-- start:   000001***************1**********************
-- counter: 33333332103210321032103210321032103210333333
-- tick:    00000000010001000100010001000100010001000000
-- ready:   11111100000000000000010000000000000001111111
-- tx:      111111aaaabbbbccccddddeeeeffffgggghhhh111111
-- state:   [idle][m1][m2][m3][m4][m1][m2][m3][m4][idle]
--                [---sequence---][---sequence---]
--
entity iso14443_sequencer is
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Next symbol to be sent.
    -- MSB is transmitted first.
    -- For ISO 14443 type A, symbols can be:
    -- - 1101 for sequence X
    -- - 1111 for sequence Y
    -- - 0111 for sequence Z
    symbol: in std_logic_vector(3 downto 0);
    -- When high, send the symbol.
    start: in std_logic;
    -- High when ready to accept next symbol.
    ready: out std_logic;
    -- Modulation output.
    tx: out std_logic );
end;

architecture behavior of iso14443_sequencer is
    -- FSM states
    type state_t is (st_idle, st_moment_1, st_moment_2, st_moment_3, st_moment_4);
    -- Current FSM state
    signal state: state_t;
    -- Counter for generating 4 ticks per ETU.
    signal tick_counter: unsigned(7 downto 0);
    -- High every ETU/4.
    -- One ETU is 128/fc, which is approximatively 1/944 clock cycles.
    -- One period is then 944 / 4 = 236, which corresponds the pause time of
    -- 2.5 µs.
    signal tick: std_logic;
    -- Fetched symbol to be generated.
    signal shift_reg: std_logic_vector(3 downto 0);
begin

    p_state: process (clock, reset_n)
    begin
        if reset_n = '0' then
            state <= st_idle;
        elsif rising_edge(clock) then
            case state is
                -- Waiting for start request.
                when st_idle =>
                    if start = '1' then
                        state <= st_moment_1;
                    else
                        state <= st_idle;
                    end if;

                when st_moment_1 =>
                    if tick = '1' then
                        state <= st_moment_2;
                    else
                        state <= st_moment_1;
                    end if;
                
                when st_moment_2 =>
                    if tick = '1' then
                        state <= st_moment_3;
                    else
                        state <= st_moment_2;
                    end if;
                
                when st_moment_3 =>
                    if tick = '1' then
                        state <= st_moment_4;
                    else
                        state <= st_moment_3;
                    end if;

                when st_moment_4 =>
                    if tick = '1' then
                        if start = '1' then
                            state <= st_moment_1;
                        else
                            state <= st_idle;
                        end if;
                    else
                        state <= st_moment_4;
                    end if;

                when others =>
                    state <= st_idle;
            end case;
        end if;
    end process;

    p_ticks: process (clock, reset_n)
    begin
        if reset_n = '0' then
            tick_counter <= to_unsigned(235, tick_counter'length);
        elsif rising_edge(clock) then
            case state is
                when st_idle =>
                    tick_counter <= to_unsigned(235, tick_counter'length);
                when st_moment_1 | st_moment_2 | st_moment_3 | st_moment_4 =>
                    if tick_counter = 0 then
                        tick_counter <= to_unsigned(235, tick_counter'length);
                    else
                        tick_counter <= tick_counter - 1;
                    end if;
            end case;
        end if;
    end process;

    -- tick must not be registered.
    tick <= '1' when tick_counter = 0 else '0';

    p_ready: process (state, tick)
    begin
        case state is
            when st_idle =>
                ready <= '1';
            when st_moment_4 =>
                ready <= tick;
            when others => 
                ready <= '0';
        end case;
    end process;

    p_shift_reg: process (clock, reset_n)
    begin
        if reset_n = '0' then
            shift_reg <= "1111";
        elsif rising_edge(clock) then
            case state is
                when st_idle =>
                    if start = '1' then
                        shift_reg <= symbol;
                    else
                        shift_reg <= shift_reg;
                    end if;
                when st_moment_1 | st_moment_2 | st_moment_3 =>
                    if tick = '1' then
                        -- Shift left, input '1' from the right.
                        shift_reg <= shift_reg(2 downto 0) & '1';
                    else
                        shift_reg <= shift_reg;
                    end if;
                when st_moment_4 =>
                    if tick = '1' then
                        shift_reg <= symbol;
                    else
                        shift_reg <= shift_reg;
                    end if;
            end case;
        end if;
    end process;

    tx <= shift_reg(3);
end;


library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;


-- ISO14443 transmitter.
-- Uses the iso14443_sequencer for sequences generation.
--
-- A transmission is prepared by pushing patterns in the FIFO. For ISO 14443
-- type A, each pattern corresponds to an "X", "Y" or "Z" sequence, which
-- encodes start bit, data bits, parity bits or stop condition.
--
-- Once all patterns of a frame to be transmitted have been pushed in the FIFO,
-- asserting start will trigger the transmission.
entity iso14443_tx is
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Input pattern to be pushed.
    pattern: in std_logic_vector(1 downto 0);
    -- Polarity bit to negate the output if necessary, depending on the radio
    -- front-end.
    polarity: std_logic;
    -- When high, push pattern in the FIFO.
    push: in std_logic;
    -- When high, start transmission.
    start: in std_logic;
    -- When high, transmission is ongoing.
    busy: out std_logic;
    -- Modulation output
    tx: out std_logic;
    -- Trigger when transmission starts.
    trigger_start: out std_logic;
    -- Trigger when transmission ends.
    trigger_end: out std_logic );
end;

architecture behavior of iso14443_tx is
    -- FSM states
    type state_t is (st_idle, st_fetch, st_wait, st_wait_last);
    -- Current FSM state.
    signal state: state_t;
    -- Next symbol to be transmitted by the sequencer.
    signal next_symbol: std_logic_vector(3 downto 0);
    -- When high, the sequencer will start transmission of next_symbol.
    signal seq_start: std_logic;
    -- When high, the sequencer is ready to start a new transmission.
    signal seq_ready: std_logic;
    -- Output of the sequencer.
    signal seq_tx: std_logic;
    signal seq_tx_reg: std_logic;
    -- FIFO signals
    signal fifo_q: std_logic_vector(1 downto 0);
    signal fifo_full: std_logic;
    signal fifo_empty: std_logic;
    signal fifo_rdreq: std_logic;
begin
    -- FSM management
    p_state: process (clock, reset_n)
    begin
        if reset_n = '0' then
            state <= st_idle;
        elsif rising_edge(clock) then
            case state is
                when st_idle =>
                    if (start = '1') and (fifo_empty = '0') then
                        state <= st_fetch;
                        busy <= '1';
                    else
                        state <= st_idle;
                        busy <= '0';
                    end if;

                -- Ask the FIFO to pop next pattern.
                when st_fetch =>
                    state <= st_wait;
                    busy <= '1';

                -- Sequencer is transmitting, waiting for it to end.
                -- A new byte is ready to be transmitted and already queried to
                -- the FIFO.
                when st_wait =>
                    if seq_ready = '1' then
                        if fifo_empty = '1' then
                            state <= st_wait_last;
                        else
                            state <= st_fetch;
                        end if;
                    else
                        state <= st_wait;
                    end if;
                    busy <= '1';

                -- We are waiting for the sequencer to finish, and this is the
                -- last symbol of the FIFO.
                when st_wait_last =>
                    if seq_ready = '1' then
                        state <= st_idle;
                        busy <= '0';
                    else
                        state <= st_wait_last;
                        busy <= '1';
                    end if;

            end case;
        end if;
    end process;

    fifo_rdreq <= '1' when (state = st_fetch) else '0';
    seq_start <= '1' when (state = st_wait) and (seq_ready = '1') else '0';
    
    -- Transmission patterns storage FIFO.
    e_fifo: entity work.iso14443_tx_fifo
    port map (
        clock => clock,
        aclr => not reset_n,
        sclr => '0',
        data => pattern,
        wrreq => push,
        q => fifo_q,
        full => fifo_full,
        empty => fifo_empty,
        rdreq => fifo_rdreq );

    p_next_symbol: process (state, fifo_q)
    begin
        if state = st_wait_last then
            next_symbol <= "1111";
        else
            case fifo_q is
                when "00" => next_symbol <= "0000";
                when "11" => next_symbol <= "1111";
                when "01" => next_symbol <= "0111";
                when "10" => next_symbol <= "1101";
                when others => next_symbol <= "1111";
            end case;
        end if;
    end process;
    
    e_sequencer: entity work.iso14443_sequencer
    port map (
        clock => clock,
        reset_n => reset_n,
        symbol => next_symbol,
        start => seq_start,
        ready => seq_ready,
        tx => seq_tx );

    -- Register the output
    p_seq_tx_reg: process (clock, reset_n)
    begin
        if reset_n = '0' then
            seq_tx_reg <= '1';
        elsif rising_edge(clock) then
            seq_tx_reg <= seq_tx xor polarity;
        end if;
    end process;

    -- Trigger generation
    p_triggers: process (clock, reset_n)
    begin
        if reset_n = '0' then
            trigger_start <= '0';
            trigger_end <= '0';
        elsif rising_edge(clock) then
            if (state = st_idle) and (start = '1') and (fifo_empty = '0') then
                trigger_start <= '1';
            else
                trigger_start <= '0';
            end if;

            if (state = st_wait_last) and (seq_ready = '1') then
                trigger_end <= '1';
            else
                trigger_end <= '0';
            end if;
        end if;
    end process;

    tx <= seq_tx_reg;
end;
