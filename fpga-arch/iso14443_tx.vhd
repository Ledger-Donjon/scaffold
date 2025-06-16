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


entity iso14443_tx is
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Polarity bit to negate the output if necessary, depending on the radio
    -- front-end.
    polarity: std_logic;
    -- High to resynchronize to external 13.56 MHz clock.
    use_sync: in std_logic;
    -- External 13.56 MHz clock.
    -- Use to synchronize transmission with the RF front-end clock if use_sync
    -- is enabled.
    clock_13_56: in std_logic;
    -- When low, forces modulation to cut power (valid only in OOK).
    power_enable: in std_logic;
    -- Maximum timeout value.
    timeout: in std_logic_vector(23 downto 0);
    -- Input pattern to be pushed.
    pattern: in std_logic_vector(1 downto 0);
    -- When high, push pattern in the FIFO.
    push: in std_logic;
    -- When high, start transmission.
    start: in std_logic;
    -- Number of bits stored in the FIFO.
    rx_fifo_usedw: out std_logic_vector(11 downto 0);
    -- High when reception FIFO is empty.
    rx_fifo_empty: out std_logic;
    -- RX FIFO output bit.
    rx_fifo_q: out std_logic;
    -- RX FIFO read request.
    rx_fifo_rdreq: in std_logic;
    -- High when transmission or reception is ongoing.
    busy: out std_logic;
    -- Output trigger asserted when transmission starts.
    trigger_tx_start: out std_logic;
    -- Output trigger asserted when transmission ends.
    trigger_tx_end: out std_logic;
    -- Output trigger asserted when the card starts to respond.
    trigger_rx_start: out std_logic; 
    -- Sub-carrier input.
    rx: in std_logic;
    -- Modulation output.
    tx: out std_logic );
end;


architecture behavior of iso14443_tx is
    -- FSM states
    type state_t is (
        st_idle,
        st_sync,
        st_trigger_start,
        st_tx_fetch,
        st_tx_copy,
        st_tx,
        st_trigger_tx_end,
        st_rx_wait,
        st_rx_a,
        st_rx_a_sample,
        st_rx_dummy,
        st_rx_b,
        st_rx_b_sample,
        st_rx_decode,
        st_end );
    -- Current FSM state
    signal state: state_t;
    -- Start signal from the 13.56 MHz clock synchronizer.
    signal clock_sync_go: std_logic;
    -- Symbol being transmitted.
    signal tx_buffer: std_logic_vector(3 downto 0);
    -- Counter used for the transmission, to generate 1/4 symbol period.
    -- One ETU is 128/fc, which is approximatively 1/944 clock cycles.
    -- One period is then 944 / 4 = 236, which corresponds the pause time of
    -- 2.5 µs.
    -- Maximum counter value will therefore be 235 for transmission.
    -- This counter is also used for reception, with a maximum value of 469
    -- (about half bit period).
    signal time_counter: unsigned(8 downto 0);
    -- Counts the number of moments during transmission of symbol.
    signal tx_symbol_counter: unsigned(1 downto 0);
    -- Transmission FIFO signals
    signal tx_fifo_q: std_logic_vector(1 downto 0);
    signal tx_fifo_empty: std_logic;
    signal tx_fifo_full: std_logic;
    signal tx_fifo_rdreq: std_logic;
    -- Samples come from the output of the demoulator.
    -- Two samples per bit are taken.
    signal samples: std_logic_vector(1 downto 0);
    -- High when samples is "01" or "10", corresponding to a valid Manchester
    -- symbol.
    signal samples_valid: std_logic;
    -- Reception FIFO signals
    signal rx_fifo_full: std_logic;
    signal rx_fifo_wreq: std_logic;
    -- Timeout counter.
    signal timeout_counter: unsigned(29 downto 0);
    -- Demodulator output.
    signal demod_result: std_logic;
    -- High to enable demodulator block. This help reducing power consumption
    -- and noise: we don't need to always have it running.
    signal demod_enable: std_logic;
begin
    p_state: process (clock, reset_n) is
    begin
        if reset_n = '0' then
            state <= st_idle;
        elsif rising_edge(clock) then
            case state is
                -- Nothing is happening.
                -- Wait for the order to start transmission.
                when st_idle =>
                    if start = '1' then
                        state <= st_sync;
                    else
                        state <= st_idle;
                    end if;

                -- Transmission has been requested, we are in clock
                -- synchronization state. Synchronization is bypassed if
                -- use_sync is disabled.
                when st_sync =>
                    if (clock_sync_go = '1') or (use_sync = '0') then
                        state <= st_trigger_start;
                    else
                        state <= st_sync;
                    end if;

                -- One clock cycle to generate trigger.
                when st_trigger_start =>
                    state <= st_tx_fetch;

                -- One clock cycle to request FIFO pop.
                when st_tx_fetch =>
                    state <= st_tx_copy;

                -- One clock cycle to load transmission buffer from FIFO output.
                when st_tx_copy =>
                    state <= st_tx;

                -- We are transmitting bits.
                when st_tx =>
                    if tx_symbol_counter = 0 then
                        -- We are transmitting the last moment of the current
                        -- symbol.
                        if (time_counter = 2) and (tx_fifo_empty = '0') then
                            -- We still have symbols to transmit, fetch it from
                            -- the FIFO.
                            state <= st_tx_fetch;
                        elsif time_counter = 0 then
                            -- Done transmitting all symbols.
                            state <= st_trigger_tx_end;
                        else
                            state <= st_tx;
                        end if;
                    else
                        state <= st_tx;
                    end if;

                -- One clock cycle used to generate end of transmission trigger.
                when st_trigger_tx_end =>
                    state <= st_rx_wait;

                -- Waiting for the beginning of the response.
                -- Goes to reception when modulation is detected, or end
                -- reception if timeout occurs.
                when st_rx_wait =>
                    if timeout_counter = 0 then
                        state <= st_end;
                    else
                        if demod_result = '1' then
                            state <= st_rx_a;
                        else
                            state <= st_rx_wait;
                        end if;
                    end if;

                -- Waiting to be at the middle of first bit half.
                when st_rx_a =>
                    if time_counter = 0 then
                        state <= st_rx_a_sample;
                    else
                        state <= st_rx_a;
                    end if;

                -- One clock cycle to sample first bit half.
                when st_rx_a_sample =>
                    state <= st_rx_dummy;

                -- One clock dummy cycle to have same timing as second bit half
                -- where there is a cycle for decoding. This way the time
                -- counter is reloaded to the same value for both bit halves.
                when st_rx_dummy =>
                    state <= st_rx_b;

                -- Waiting to be at the middle of second bit half.
                when st_rx_b =>
                    if time_counter = 0 then
                        state <= st_rx_b_sample;
                    else
                        state <= st_rx_b;
                    end if;

                -- One clock cycle to sample second bit half.
                when st_rx_b_sample =>
                    state <= st_rx_decode;

                -- We took two samples for the current bit, we now have one
                -- clock cycle to decode bit and push it in the RX FIFO. If bit
                -- has no valid encoding, end reception.
                when st_rx_decode =>
                    if samples_valid = '1' then
                        -- Bit has valid Manchester encoding, continue reception.
                        state <= st_rx_a;
                    else
                        -- Bit is not valid, end of transmission
                        state <= st_end;
                    end if;

                when st_end =>
                    state <= st_idle;

            end case;
        end if;
    end process;

    busy <= '1' when state /= st_idle else '0';

    -- Time counter to generate the correct baudrates for transmission and
    -- reception.
    p_time_counter: process (clock, reset_n) is
    begin
        if reset_n = '0' then
            time_counter <= (others => '0');
        elsif rising_edge(clock) then
            case state is
                -- Decrement the counter during all transmission, which includes
                -- st_tx_fetch.
                -- Exception: before starting transmission, when the first
                -- symbol is fetched from the FIFO the counter will be
                -- decremented once. This is not a problem, no need to add logic
                -- to avoid that.
                when st_tx | st_tx_fetch | st_tx_copy =>
                    if time_counter = 0 then
                        time_counter <= to_unsigned(235, time_counter'length);
                    else
                        time_counter <= time_counter - 1;
                    end if;
                when st_rx_wait =>
                    -- 235 = 944 / 4 - 1 - 2
                    -- Quarter bit duration, minus one because 0 is included,
                    -- minus 2 to take into account the dummy cycle and sampling
                    -- cycle.
                    time_counter <= to_unsigned(235, time_counter'length);
                when st_rx_a | st_rx_b =>
                    time_counter <= time_counter - 1;
                when st_rx_a_sample | st_rx_dummy | st_rx_b_sample | st_rx_decode =>
                    -- 469 = 944 / 2 - 1 - 2
                    -- Half bit duration, minus one because 0 is included,
                    -- minus 2 to take into account the sampling cycle and
                    -- decoding cycle.
                    time_counter <= to_unsigned(469, time_counter'length);
                when others =>
                    time_counter <= time_counter;
            end case;
        end if;
    end process;

    -- Symbol counting for transmission.
    -- Counts the number of moments to be transmitted. Loaded to value 3
    -- (4 moments) for each symbol to be transmitted.
    p_tx_symbol_counter: process (clock, reset_n) is
    begin
        if reset_n = '0' then
            tx_symbol_counter <= (others => '0');
        elsif rising_edge(clock) then
            case state is
                when st_tx =>
                    if time_counter = 0 then
                        tx_symbol_counter <= tx_symbol_counter - 1;
                    else
                        tx_symbol_counter <= tx_symbol_counter;
                    end if;
                when others =>
                    tx_symbol_counter <= to_unsigned(3, tx_symbol_counter'length);
            end case;
        end if;
    end process;

    -- Timout counter management.
    p_timeout_counter: process (clock, reset_n) is
    begin
        if reset_n = '0' then
            timeout_counter <= (others => '1');
        elsif rising_edge(clock) then
            case state is
                when st_idle =>
                    timeout_counter <= unsigned(timeout & "000000");
                when st_rx_wait =>
                    timeout_counter <= timeout_counter - 1;
                when others =>
                    timeout_counter <= timeout_counter;
            end case;
        end if;
    end process;

    -- Transmission buffer management.
    p_tx_buffer: process (clock, reset_n) is
    begin
        if reset_n = '0' then
            tx_buffer <= "1111";
        elsif rising_edge(clock) then
            case state is
                -- Load tx_buffer with the symbol to be transmitted right
                -- after. Symbol is stored on 2 bits in the FIFO, so there is
                -- some kind of decompression here.
                when st_tx_copy =>
                    case tx_fifo_q is
                        when "00" => tx_buffer <= "0000";
                        when "11" => tx_buffer <= "1111";
                        when "01" => tx_buffer <= "0111";
                        when "10" => tx_buffer <= "1101";
                        when others => tx_buffer <= "1111";
                    end case;
                when st_tx =>
                    if time_counter = 0 then
                        tx_buffer <= tx_buffer(2 downto 0) & "1";
                    else
                        tx_buffer <= tx_buffer;
                    end if;
                when others =>
                    tx_buffer <= tx_buffer;
            end case;
        end if;
    end process;
    
    -- Transmission patterns storage FIFO.
    e_tx_fifo: entity work.iso14443_tx_fifo
    port map (
        clock => clock,
        aclr => not reset_n,
        sclr => '0',
        data => pattern,
        wrreq => push,
        q => tx_fifo_q,
        full => tx_fifo_full,
        empty => tx_fifo_empty,
        rdreq => tx_fifo_rdreq );

    tx_fifo_rdreq <= '1' when state = st_tx_fetch else '0';

    -- 13.56 MHz clock synchronization block
    e_clock_sync: entity work.iso14443_clock_sync
    port map (
        clock => clock,
        reset_n => reset_n,
        clock_13_56 => clock_13_56,
        go => clock_sync_go );

    tx <= (tx_buffer(3) and power_enable) xor polarity;

    p_samples: process (clock, reset_n) is
    begin
        if reset_n = '0' then
            samples <= "00";
        elsif rising_edge(clock) then
            case state is
                when st_rx_a_sample | st_rx_b_sample =>
                    samples <= samples(0) & demod_result;
                when others =>
                    samples <= samples;
            end case;
        end if;
    end process;

    samples_valid <= samples(0) xor samples(1);

    e_demod: entity work.iso14443_demod
    port map (
        clock => clock,
        reset_n => reset_n,
        enable => demod_enable,
        rx => rx,
        result => demod_result );

    p_demo_enable: process (state) is
    begin
        case state is
            when st_rx_wait | st_rx_a | st_rx_a_sample | st_rx_dummy | st_rx_b
                | st_rx_b_sample | st_rx_decode =>
                demod_enable <= '1';
            when others =>
                demod_enable <= '0';
        end case;
    end process;

    -- Received bits are stored in the following FIFO.
    -- FIFO is automatically flushed when a new transmission is requested.
    e_rx_fifo: entity work.iso14443_rx_fifo
    port map (
        clock => clock,
        aclr => not reset_n,
        sclr => start,
        data => samples(1),
        wrreq => rx_fifo_wreq,
        q => rx_fifo_q,
        full => rx_fifo_full,
        empty => rx_fifo_empty,
        rdreq => rx_fifo_rdreq,
        usedw => rx_fifo_usedw );

    rx_fifo_wreq <= '1' when ((state = st_rx_decode) and (samples_valid = '1'))
        else '0';

    p_triggers: process (clock, reset_n) is
    begin
        if reset_n = '0' then
            trigger_tx_start <= '0';
            trigger_tx_end <= '0';
            trigger_rx_start <= '0';
        elsif rising_edge(clock) then
            if state = st_trigger_start then
                trigger_tx_start <= '1';
            else
                trigger_tx_start <= '0';
            end if;
            if state = st_trigger_tx_end then
                trigger_tx_end <= '1';
            else
                trigger_tx_end <= '0';
            end if;
            if (state = st_rx_wait) and (demod_result = '1') then
                trigger_rx_start <= '1';
            else
                trigger_rx_start <= '0';
            end if;
        end if;
    end process;
end;
