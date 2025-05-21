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


-- This block samples the response modulated signal. It synchronizes to the
-- edges of the response enveloppe (issued from the TRF7970A).
--
-- Modulation period is 118 clock cycles, that makes one transition every 59
-- clock cycles.
--
-- Here is an example of input, after 13.56 MHz demodulation:
-- (here with a period of 6 clock cycles instead of 118).
--
-- rx:           1111111000111000111000111000111111111111111111111111111000111
--                      [---------Bit 1 in Manchester encoding---------]
-- sample:       ********0**1**0**1**0**1**0**1**1**1**1**1**1**1**1**1**0**1*
-- sample_valid: 000000001001001001001001001001001001001001001001001001001001*
entity iso14443_rx_sampler is
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Input signal
    rx: in std_logic;
    -- High to enable the sampler.
    enable: in std_logic;
    -- High when a sample has been taken.
    sample_valid: out std_logic;
    -- Taken sample.
    sample: out std_logic;
    -- High when reception starts.
    trigger_start: out std_logic );
end;

architecture behavior of iso14443_rx_sampler is
    type state_t is (st_idle, st_waiting, st_delay, st_before_edge, st_after_edge);
    -- Current FSM state.
    signal state: state_t;
    -- rx delayed one clock cycle.
    signal rx_z: std_logic;
    -- rx delayed two clock cycles.
    signal rx_zz: std_logic;
    -- High when a transition on rx is detected.
    signal rx_edge: std_logic;
    -- Counts periods of the modulated signal.
    -- There is about 59 clock cycles each modulation half-period.
    signal counter: unsigned(6 downto 0);
begin
    p_rx_edge: process (clock, reset_n) is
    begin
        if reset_n = '0' then
            rx_z <= '0';
            rx_zz <= '0';
            rx_edge <= '0';
        elsif rising_edge(clock) then
            rx_z <= rx;
            rx_zz <= rx_z;
            rx_edge <= rx_z xor rx_zz;
        end if;
    end process;

    p_state: process (clock, reset_n)
    begin
        if reset_n = '0' then
            state <= st_idle;
            counter <= to_unsigned(0, counter'length);
        elsif rising_edge(clock) then
            case state is
                -- Receiver is sleeping, not trying to decode anything.
                when st_idle =>
                    if enable = '1' then
                        state <= st_waiting;
                    else
                        state <= st_idle;
                    end if;
                    counter <= to_unsigned(0, counter'length);

                -- Waiting for first edge.
                when st_waiting =>
                    if enable = '1' then
                        if rx_edge = '1' then
                            state <= st_delay;
                        else
                            state <= st_waiting;
                        end if;
                    else
                        state <= st_idle;
                    end if;
                    counter <= (others => '0');

                -- We are waiting for the duration of modulation
                -- half-period. We are not expecting any edge here. If an
                -- edge happens, we tolerate it.
                -- Sample will be sampled during this state.
                when st_delay =>
                    if enable = '1' then
                        if counter = 58 - 4 then
                            state <= st_before_edge;
                        else
                            state <= st_delay;
                        end if;
                        counter <= counter + 1;
                    else
                        state <= st_idle;
                        counter <= (others => '0');
                    end if;

                -- We are close to the edge, and in case it comes a bit
                -- earlier we are ready to resynchronize.
                when st_before_edge =>
                    if enable = '0' then
                        state <= st_idle;
                        counter <= (others => '0');
                    elsif rx_edge = '1' then
                        state <= st_delay;
                        counter <= (others => '0');
                    else
                        if counter = 58 then
                            -- Edge still not here. This can be normal
                            -- depending on what bit is being transmitted,
                            -- or maybe the edge will be a little bit late.
                            state <= st_after_edge;
                            counter <= to_unsigned(0, counter'length);
                        else
                            state <= st_before_edge;
                            counter <= counter + 1;
                        end if;
                    end if;

                when st_after_edge =>
                    if enable = '0' then
                        state <= st_idle;
                        counter <= (others => '0');
                    elsif rx_edge = '1' then
                        state <= st_delay;
                        counter <= to_unsigned(0, counter'length);
                    else
                        if counter = 3 then
                            -- Edge was not received, move on...
                            state <= st_delay;
                        else
                            state <= st_after_edge;
                        end if;
                        counter <= counter + 1;
                    end if;
            end case;
        end if;
    end process;

    p_trigger_start: process (clock, reset_n)
    begin
        if reset_n = '0' then
            trigger_start <= '0';
        elsif rising_edge(clock) then
            if (state = st_waiting) and (enable = '1') and (rx_edge = '1') then
                trigger_start <= '1';
            else
                trigger_start <= '0';
            end if;
        end if;
    end process;

    sample_valid <= '1' when counter = 29 else '0';
    sample <= rx_z;
end;


library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;


entity iso14443_rx is
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Input signal
    rx: in std_logic;
    -- High to start reception.
    start: in std_logic;
    -- High when a bit has been received.
    bit_valid: out std_logic;
    -- Received bit valud. Valid when bit_valid is high.
    bit_out: out std_logic;
    -- High during one clock cycle when reception starts.
    trigger_start: out std_logic;
    -- High during one clock cycle when reception ends.
    trigger_end: out std_logic );
end;


architecture behavior of iso14443_rx is
    type state_t is (st_idle, st_receiving, st_decode, st_end);
    -- Current FSM state.
    signal state: state_t;
    -- Enables the sampler.
    signal sampler_enable: std_logic;
    -- Sample value issued by the sampler.
    signal sample: std_logic;
    -- High when sample is valid.
    signal sample_valid: std_logic;
    -- All 16 collected samples, +1 for counting bits.
    -- This string is initialized to zero with LSB at 1. It is shifted
    -- everytime a new sample is acquired. When the MSB becomes 1 it means all
    -- 16 samples have been captured. This way we have a counter for the cost
    -- of a single bit register!
    signal samples: std_logic_vector(16 downto 0);
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
    -- High when a valid encoding is detected in the sample string.
    signal valid_encoding: std_logic;
begin
    e_sampler: entity work.iso14443_rx_sampler
    port map (
        clock => clock,
        reset_n => reset_n,
        rx => rx,
        enable => sampler_enable,
        sample => sample,
        sample_valid => sample_valid,
        trigger_start => trigger_start );

    p_state: process (clock, reset_n) is
    begin
        if reset_n = '0' then
            state <= st_idle;
            samples <= "00000000000000001";
            bit_valid <= '0';
            bit_out <= '0';
        elsif rising_edge(clock) then
            case state is
                when st_idle =>
                    if start = '1' then
                        state <= st_receiving;
                    else
                        state <= st_idle;
                    end if;
                    samples <= "00000000000000001";
                    bit_valid <= '0';
                    bit_out <= '0';

                when st_receiving =>
                    if samples(samples'high) = '1' then
                        state <= st_decode;
                    else
                        state <= st_receiving;
                    end if;
                    if sample_valid = '1' then
                        samples <= samples(15 downto 0) & sample;
                    else
                        samples <= samples;
                    end if;
                    bit_valid <= '0';
                    bit_out <= '0';

                when st_decode =>
                    if valid_encoding = '1' then
                        state <= st_receiving;
                    else
                        state <= st_end;
                    end if;
                    samples <= "00000000000000001";
                    bit_valid <= valid_encoding;
                    bit_out <= manchester_1;

                when st_end =>
                    state <= st_idle;
                    samples <= samples;
                    bit_valid <= '0';
                    bit_out <= '0';
            end case;
        end if;
    end process;

    sampler_enable <= '1' when state /= st_idle else '0';
    trigger_end <= '1' when state = st_end else '0';
    
    -- At the end of one bit, for ISO-14443 type A, samples can look like this:
    -- (without MSB used for counting):
    -- - "1010101000000000" for bit 1
    -- - "0101010100000000" for bit 1
    -- - "1010101011111111" for bit 1
    -- - "0101010111111111" for bit 1
    -- - "0000000010101010" for bit 0
    -- - "0000000001010101" for bit 0
    -- - "1111111110101010" for bit 0
    -- - "1111111101010101" for bit 0

    -- The signal coming from the TRF7970A is not 100% precise/synchronized,
    -- detecting the beginning of the reception is not that easy.
    -- To make reception more robust and tolerant, we strip left and right bits
    -- in 'a' and 'b' parts.
    -- Note: we could use Frame Guard Time grid alignment to help reception
    -- synchronization, but this is not trivial and we don't do this here.
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
    valid_encoding <= manchester_0 or manchester_1;
end;
