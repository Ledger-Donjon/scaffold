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


-- Takes response sampled input and tries to decode the bit according to
-- ISO-14443 Manchester encoding.
--
-- At the end of one bit, for ISO-14443 type A, samples can look like this:
-- - "1010101000000000" for bit 1
-- - "0101010100000000" for bit 1
-- - "1010101011111111" for bit 1
-- - "0101010111111111" for bit 1
-- - "0000000010101010" for bit 0
-- - "0000000001010101" for bit 0
-- - "1111111110101010" for bit 0
-- - "1111111101010101" for bit 0
entity iso14443_rx_decoder is
port (
    -- Sampled response.
    samples: in std_logic_vector(15 downto 0);
    -- High when samples represent a valid 0 or 1 symbol.
    valid: out std_logic;
    -- Decoded bit value. Valid only if valid output is 1.
    value: out std_logic );
end;


architecture behavior of iso14443_rx_decoder is
    -- Left half of samples.
    signal samples_a: std_logic_vector(5 downto 0);
    -- Right half of samples.
    signal samples_b: std_logic_vector(5 downto 0);
    -- High when left half of samples are modulated with 0 degrees phase.
    signal a_mod_0: std_logic;
    -- High when left half of samples are modulated with 180 degrees phase.
    signal a_mod_180: std_logic;
    -- High when left half of samples have no modulation.
    signal a_nomod: std_logic;
    -- High when right half of samples are modulated with 0 degrees phase.
    signal b_mod_0: std_logic;
    -- High when right half of samples are modulated with 180 degrees phase.
    signal b_mod_180: std_logic;
    -- High when right half of samples have no modulation.
    signal b_nomod: std_logic;
    -- High when samples is decoded as logic 1 in Manchester encoding.
    signal manchester_0: std_logic;
    -- High when samples is decoded as logic 0 in Manchester encoding.
    signal manchester_1: std_logic;
begin
    -- The signal coming from the TRF7970A is not 100% precise/synchronized.
    -- To make reception more robust and tolerant, we strip left and right bits
    -- in 'a' and 'b' parts.
    samples_a <= samples(14 downto 9);
    samples_b <= samples(6 downto 1);

    a_mod_0 <= '1' when samples_a = "101010" else '0';
    a_mod_180 <= '1' when samples_a = "010101" else '0';
    a_nomod <= '1' when (samples_a = "000000") or (samples_a = "111111") else '0';
    b_mod_0 <= '1' when samples_b = "101010" else '0';
    b_mod_180 <= '1' when samples_b = "010101" else '0';
    b_nomod <= '1' when (samples_b = "000000") or (samples_b = "111111") else '0';

    manchester_0 <= a_nomod and (b_mod_0 or b_mod_180);
    manchester_1 <= b_nomod and (a_mod_0 or a_mod_180);

    valid <= manchester_0 or manchester_1;
    value <= manchester_1;
end;


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
        st_fdt_align,
        st_rx,
        st_rx_sample,
        st_rx_decode,
        st_end );
    -- Current FSM state
    signal state: state_t;
    -- Start signal from the 13.56 MHz clock synchronizer.
    signal clock_sync_go: std_logic;
    -- Symbol being transmitted.
    signal tx_buffer: std_logic_vector(3 downto 0);
    -- Counter for the transmission, to generate 1/4 symbol period.
    -- One ETU is 128/fc, which is approximatively 1/944 clock cycles.
    -- One period is then 944 / 4 = 236, which corresponds the pause time of
    -- 2.5 µs.
    -- Maximum counter value will therefore be 235.
    signal tx_time_counter: unsigned(8 downto 0);
    -- Counts the number of moments during transmission of symbol.
    signal tx_symbol_counter: unsigned(1 downto 0);
    -- Transmission FIFO signals
    signal tx_fifo_q: std_logic_vector(1 downto 0);
    signal tx_fifo_empty: std_logic;
    signal tx_fifo_full: std_logic;
    signal tx_fifo_rdreq: std_logic;
    -- All 16 collected samples.
    -- This string is initialized to zero with LSB at 1. It is shifted
    -- everytime a new sample is acquired. When the MSB becomes 1 it means the
    -- sample will be the last one. This way we have a counter for free.
    signal samples: std_logic_vector(15 downto 0);
    -- High when a valid encoding is detected in the sample string.
    signal decoder_valid: std_logic;
    -- Decoded bit value.
    signal decoder_value: std_logic;
    -- Reception FIFO signals
    --signal rx_fifo_q: std_logic;
    --signal rx_fifo_empty: std_logic;
    signal rx_fifo_full: std_logic;
    signal rx_fifo_wreq: std_logic;
    --signal rx_fifo_rdreq: std_logic;
    --signal rx_fifo_usedw: std_logic_vector(11 downto 0);
    -- Timeout counter.
    signal timeout_counter: unsigned(23 downto 0);
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
                        if (tx_time_counter = 2) and (tx_fifo_empty = '0') then
                            -- We still have symbols to transmit, fetch it from
                            -- the FIFO.
                            state <= st_tx_fetch;
                        elsif tx_time_counter = 0 then
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
                    state <= st_fdt_align;

                when st_fdt_align =>
                    if tx_time_counter = 0 then
                        state <= st_rx;
                    else
                        state <= st_fdt_align;
                    end if;

                when st_rx =>
                    if tx_time_counter = 0 then
                        state <= st_rx_sample;
                    else
                        state <= st_rx;
                    end if;

                when st_rx_sample =>
                    if samples(15) = '1' then
                        state <= st_rx_decode;
                    else
                        state <= st_rx;
                    end if;

                when st_rx_decode =>
                    if ((rx_fifo_empty = '0') and (decoder_valid = '0'))
                        or (timeout_counter = 0) then
                        state <= st_end;
                    else
                        state <= st_rx;
                    end if;

                when st_end =>
                    state <= st_idle;

            end case;
        end if;
    end process;

    busy <= '1' when state /= st_idle else '0';

    -- Time counter to generate the correct baudrate.
    p_tx_time_counter: process (clock, reset_n) is
    begin
        if reset_n = '0' then
            tx_time_counter <= (others => '0');
        elsif rising_edge(clock) then
            case state is
                -- Decrement the counter during all transmission, which includes
                -- st_tx_fetch.
                -- Exception: before starting transmission, when the first
                -- symbol is fetched from the FIFO the counter will be
                -- decremented once. This is not a problem, no need to add logic
                -- to avoid that.
                when st_tx | st_tx_fetch =>
                    if tx_time_counter = 0 then
                        tx_time_counter <= to_unsigned(235, tx_time_counter'length);
                    else
                        tx_time_counter <= tx_time_counter - 1;
                    end if;
                when st_trigger_tx_end =>
                    tx_time_counter <= to_unsigned(413, tx_time_counter'length);
                when st_fdt_align | st_rx | st_rx_decode | st_rx_sample =>
                    if tx_time_counter = 0 then
                        tx_time_counter <= to_unsigned(58, tx_time_counter'length);
                    else
                        tx_time_counter <= tx_time_counter - 1;
                    end if;
                when others =>
                    tx_time_counter <= to_unsigned(235, tx_time_counter'length);
            end case;
        end if;
    end process;

    -- Symbol counting.
    -- Counts the number of moments to be transmitted. Loaded to value 3
    -- (4 moments) for each symbol to be transmitted.
    p_tx_symbol_counter: process (clock, reset_n) is
    begin
        if reset_n = '0' then
            tx_symbol_counter <= (others => '0');
        elsif rising_edge(clock) then
            case state is
                when st_tx =>
                    if tx_time_counter = 0 then
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
                    timeout_counter <= unsigned(timeout);
                when st_rx_decode =>
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
                    if tx_time_counter = 0 then
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
            samples <= (others => '0');
        elsif rising_edge(clock) then
            case state is
                when st_rx_sample =>
                    samples <= samples(14 downto 0) & rx;
                when st_rx =>
                    samples <= samples;
                when others =>
                    samples <= "0000000000000001";
            end case;
        end if;
    end process;
   
    e_decoder: entity work.iso14443_rx_decoder
    port map (
        samples => samples,
        valid => decoder_valid,
        value => decoder_value );
    
    -- Received bits are stored in the following FIFO.
    -- FIFO is automatically flushed when a new transmission is requested.
    e_rx_fifo: entity work.iso14443_rx_fifo
    port map (
        clock => clock,
        aclr => not reset_n,
        sclr => start,
        data => decoder_value,
        wrreq => rx_fifo_wreq,
        q => rx_fifo_q,
        full => rx_fifo_full,
        empty => rx_fifo_empty,
        rdreq => rx_fifo_rdreq,
        usedw => rx_fifo_usedw );

    rx_fifo_wreq <= '1' when (state = st_rx_decode) and (decoder_valid = '1') else '0';

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
            if (state = st_rx_decode) and (rx_fifo_empty = '1') and (decoder_valid = '1') then
                trigger_rx_start <= '1';
            else
                trigger_rx_start <= '0';
            end if;
        end if;
    end process;
end;
