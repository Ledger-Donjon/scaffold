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


-- Package to declare pattern codes for interfacing the pattern generator with
-- the I2C peripheral.
package i2c_pkg is
    type pattern_code_t is (op_idle, op_start, op_bit_0, op_bit_1, op_bit_rx,
        op_ack_from_slave, op_nack_from_master, op_ack_from_master, op_restart,
        op_stop);
end;


library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.i2c_pkg.all;


--
-- I2C pattern generator
--
-- This is a sub-element of the I2C peripheral. It generates the different
-- possible I2C patterns:
-- - start condition
-- - bit transmission
-- - bit reception
-- - stop condition
-- - restart
--
-- The pattern generator handles pauses requested by the I2C slaves.
--
-- The SCL output must be registered (registration not done here). The SCL
-- input must also be registered (not done here). That is, the observed SCL for
-- pause detection is delayed two clock cycles. Therefore the minimum possible
-- duration for a time slot is 2 clock cycles and the minimum possible divisor
-- is 1.
--
-- Each pattern is decomposed into four time slots. The baudrate setting allows
-- adjusting the duration of one time slot.
--
-- The pattern generator also performs bit sampling for ACK, NACK or bit
-- reception. Sampling if done for every transmitted or received bit and is not
-- always relevant.
--
entity i2cpg is
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Baudrate divisor.
    -- If set to N, the duration of one pattern is (N+1)*4.
    -- Minimum value is 1. If set to 0, the peripheral won't work.
    divisor: in std_logic_vector(15 downto 0);
    -- Next pattern to be generated.
    pattern: in pattern_code_t;
    -- High when the generator fetched the input pattern and will start to
    -- transmit it.
    fetched: out std_logic;
    -- SCL input signal. Used to detect pause requests on the bus.
    -- This must be a registered signal.
    scl_in: in std_logic;
    -- SDA input signal. Used to detect NACK from slave.
    sda_in: in std_logic;
    -- SCL and SDA output signals. Used for open-drain control of the bus.
    -- Those signals are not registered and will have glitches. They must be
    -- registered before being output.
    scl_out: out std_logic;
    sda_out: out std_logic;
    -- Sampled SDA signal. Used for ACK and bit reception.
    sampled_bit: out std_logic;
    -- High when a bit is sampled by the pattern generator at the current
    -- clock cycle.
    sampling: out std_logic );
end;


architecture behavior of i2cpg is
    type state_t is (t1, t2, t3, t4);

    -- Counter for baudrate generation
    signal baud_counter: unsigned(15 downto 0);
    -- Current FSM state
    signal state: state_t;
    -- Baudrate tick. When high, the FSM shall go to next state.
    signal tick: std_logic;

    -- Currently generated pattern.
    -- Copied from pattern input signal when entering t1 state.
    signal current_pattern: pattern_code_t;
    -- Waveform for SDA and SCL. Calculated from current_pattern.
    signal wfm_sda, wfm_scl: std_logic_vector(3 downto 0);
begin
    -- Baudrate counter
    -- We can register tick signal for best performance (at the cost of one
    -- register).
    p_baud_counter: process (clock, reset_n)
    begin
        if reset_n = '0' then
            baud_counter <= (others => '0');
            tick <= '0';
        elsif rising_edge(clock) then
            if baud_counter = 0 then
                baud_counter <= unsigned(divisor);
                tick <= '1';
            else
                baud_counter <= baud_counter - 1;
                tick <= '0';
            end if;
        end if;
    end process;

    p_state: process (clock, reset_n)
    begin
        if reset_n = '0' then
            state <= t1;
        elsif rising_edge(clock) then
            case state is
                when t1 =>
                    if tick = '1' then
                        state <= t2;
                    else
                        state <= t1;
                    end if;
                when t2 =>
                    if tick = '1' then
                        state <= t3;
                    else
                        state <= t2;
                    end if;
                when t3 =>
                    if tick = '1' then
                        case current_pattern is
                            when op_bit_0 | op_bit_1 | op_bit_rx |
                                op_ack_from_slave | op_nack_from_master |
                                op_ack_from_master | op_restart =>
                                -- This pattern may be paused by the slave.
                                -- Test input SCL signal to detect pause.
                                if scl_in = '1' then
                                    -- No pause detected.
                                    state <= t4;
                                else
                                    -- Pause asserted. Keep waiting.
                                    state <= t3;
                                end if;
                            when others =>
                                state <= t4;
                        end case;
                    else
                        state <= t3;
                    end if;
                when t4 =>
                    if tick = '1' then
                        state <= t1;
                    else
                        state <= t4;
                    end if;
            end case;
        end if;
    end process;

    -- Current pattern fetching
    -- fetched signal is registered for best performance.
    p_current_pattern: process (clock, reset_n)
    begin
        if reset_n = '0' then
            current_pattern <= op_idle;
            fetched <= '0';
        elsif rising_edge(clock) then
            if (state = t4) and (tick = '1') then
                current_pattern <= pattern;
                fetched <= '1';
            else
                current_pattern <= current_pattern;
                fetched <= '0';
            end if;
        end if;
    end process;

    -- Waveforms for SDA and SCL
    p_wfm: process (current_pattern)
    begin
        case current_pattern is
            when op_start =>
                wfm_sda <= "1000";
                wfm_scl <= "1110";
            when op_bit_0 =>
                wfm_sda <= "0000";
                wfm_scl <= "0110";
            when op_bit_1 =>
                wfm_sda <= "1111";
                wfm_scl <= "0110";
            when op_bit_rx =>
                wfm_sda <= "1111";
                wfm_scl <= "0110";
            when op_ack_from_slave | op_nack_from_master =>
                wfm_sda <= "1111";
                wfm_scl <= "0110";
            when op_ack_from_master =>
                wfm_sda <= "0000";
                wfm_scl <= "0110";
            when op_restart =>
                wfm_sda <= "1100";
                wfm_scl <= "0110";
            when op_stop =>
                wfm_sda <= "0011";
                wfm_scl <= "0111";
            -- Idle
            when others =>
                wfm_sda <= "1111";
                wfm_scl <= "1111";
        end case;
    end process;

    -- Waveform generation pick the correct bin in the patterns depending on the
    -- current time slot.
    p_scl_sda_out: process (wfm_sda, wfm_scl, state)
    begin
        case state is
            when t1 =>
                scl_out <= wfm_scl(3);
                sda_out <= wfm_sda(3);
            when t2 =>
                scl_out <= wfm_scl(2);
                sda_out <= wfm_sda(2);
            when t3 =>
                scl_out <= wfm_scl(1);
                sda_out <= wfm_sda(1);
            when t4 =>
                scl_out <= wfm_scl(0);
                sda_out <= wfm_sda(0);
        end case;
    end process;

    -- SDA sampling for ACK and bit reception
    p_sampled_bit: process (clock, reset_n)
    begin
        if reset_n = '0' then
            sampled_bit <= '1';
            sampling <= '0';
        elsif rising_edge(clock) then
            if (state = t3) and (tick = '1') then
                sampled_bit <= sda_in;
                sampling <= '1';
            else
                sampled_bit <= sampled_bit;
                sampling <= '0';
            end if;
        end if;
    end process;

end;


library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.i2c_pkg.all;


--
-- I2C master peripheral
--
entity i2c is
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Baudrate divisor.
    divisor: in std_logic_vector(15 downto 0);
    -- SCL input signal. Used to detect pause requests on the bus.
    -- This must be a registered signal.
    scl_in: in std_logic;
    -- SDA input signal. Used to detect NACK from slave.
    sda_in: in std_logic;
    -- SCL and SDA output signals. Used for open-drain control of the bus.
    -- Those signals are not registered and will have glitches. They must be
    -- registered before being output.
    scl_out: out std_logic;
    sda_out: out std_logic;
    -- Set high to start transaction.
    start_transaction: in std_logic;
    -- High during the transaction.
    busy: out std_logic;
    -- Keep high while there is still data to be sent.
    more_data_to_send: in std_logic;
    -- Keep high while there is still data to be received.
    more_data_to_receive: in std_logic;
    -- Data to be sent.
    data_in: in std_logic_vector(7 downto 0);
    -- High during one clock cycle when input data has been fetched.
    fetched: out std_logic;
    -- Received data.
    data_out: out std_logic_vector(7 downto 0);
    -- High during one clock cycle when a byte is available on data_out.
    data_avail: out std_logic;
    -- High if a NACK from slave is detected.
    nack: out std_logic;
    -- High during one clock cycle when the transaction starts.
    -- This signal is synchronized with the pattern generator to have no jitter.
    trigger_start: out std_logic;
    -- High during one clock cycle when the transaction ends.
    -- This signal is synchronized with the pattern generator to have no jitter.
    trigger_end: out std_logic );
end;


architecture behavior of i2c is
    type state_t is (
        st_idle,
        st_sync,
        st_start,
        st_tx_data,
        st_tx_ack,
        st_wait_ack,
        st_rx_data,
        st_rx_ack,
        st_stop );

    -- Current FSM state.
    signal state: state_t;
    -- Next pattern to be generated.
    signal pattern: pattern_code_t;
    -- High when the next pattern as been fetched by the pattern generator.
    signal pattern_fetched: std_logic;
    -- Shift-register holding the bits to be transmitted (address or command).
    signal shift_reg: std_logic_vector(7 downto 0);
    -- Shift-register used as a one-hot counter to count the transmitted bits.
    signal bit_counter: std_logic_vector(7 downto 0);
    -- High when we are about to transmit or receive the last bit.
    signal last_bit: std_logic;
    -- Bit sampled by the pattern generator.
    signal sampled_bit: std_logic;
    -- High when a bit is sampled by the pattern generator at the current
    -- clock cycle.
    signal sampling: std_logic;
begin

    -- Pattern generator which is fed with pattern codes and generates the I2C
    -- waveforms.
    e_pg: entity work.i2cpg
    port map (clock => clock, reset_n => reset_n, divisor => divisor,
        pattern => pattern, fetched => pattern_fetched, scl_in => scl_in,
        scl_out => scl_out, sda_in => sda_in, sda_out => sda_out,
        sampled_bit => sampled_bit, sampling => sampling);

    -- FSM management
    p_fsm: process (clock, reset_n)
    begin
        if reset_n = '0' then
            state <= st_idle;
        elsif rising_edge(clock) then
            case state is
                when st_idle =>
                    if start_transaction = '1' then
                        state <= st_sync;
                    else
                        state <= st_idle;
                    end if;
                -- Wait for dummy pattern to be fetched before starting
                -- transmitting things. We do this because the fetched signal
                -- from the pattern generated is delayed due to its
                -- registration.
                when st_sync =>
                    if pattern_fetched = '1' then
                        state <= st_start;
                    else
                        state <= st_sync;
                    end if;
                -- In this state the next pattern is set to the start
                -- condition. We wait it to be fetched by the pattern
                -- generator.
                when st_start =>
                    if pattern_fetched = '1' then
                        if more_data_to_send = '1' then
                            state <= st_tx_data;
                        elsif more_data_to_receive = '1' then
                            state <= st_rx_data;
                        else
                            state <= st_stop;
                        end if;
                    else
                        state <= st_start;
                    end if;
                -- Transmitting a byte. When all bits have been transmitted,
                -- wait for ACK from the slave.
                when st_tx_data =>
                    if (pattern_fetched = '1') and (last_bit = '1') then
                        state <= st_tx_ack;
                    else
                        state <= st_tx_data;
                    end if;
                -- Will run an ACK cycle after byte transmission
                when st_tx_ack =>
                    if pattern_fetched = '1' then
                        state <= st_wait_ack;
                    else
                        state <= st_tx_ack;
                    end if;
                -- ACK pattern fetched by the pattern generator. We are in a
                -- temporary state waiting for slave acknowledgement.
                when st_wait_ack =>
                    if sampling = '1' then
                        -- ACK/NACK bit has been sampled by the pattern
                        -- generator. We can now decide if the transmission
                        -- continues or not.
                        if sampled_bit = '0' then
                            -- ACK received
                            if more_data_to_send = '1' then
                                state <= st_tx_data;
                            elsif more_data_to_receive = '1' then
                                state <= st_rx_data;
                            else
                                state <= st_stop;
                            end if;
                        else
                            -- NACK received. Stop transaction.
                            state <= st_stop;
                        end if;
                    else
                        state <= st_wait_ack;
                    end if;
                -- Receiving a byte. When all bits have been received, send ACK.
                when st_rx_data =>
                    if (pattern_fetched = '1') and (last_bit = '1') then
                        state <= st_rx_ack;
                    else
                        state <= st_rx_data;
                    end if;
                -- Transmitting ACK (after byte reception)
                when st_rx_ack =>
                    if pattern_fetched = '1' then
                        if more_data_to_receive = '1' then
                            state <= st_rx_data;
                        else
                            state <= st_stop;
                        end if;
                    else
                        state <= st_rx_ack;
                    end if;
                -- Transmitting stop condition
                when st_stop =>
                    if pattern_fetched = '1' then
                        state <= st_idle;
                    else
                        state <= st_stop;
                    end if;
            end case;
        end if;
    end process;

    busy <= '0' when (state = st_idle) else '1';

    -- Transmission/reception shift-register
    p_shift_reg: process (clock, reset_n)
    begin
        if reset_n = '0' then
            shift_reg <= (others => '0');
            fetched <= '0';
        elsif rising_edge(clock) then
            case state is
                when st_start =>
                    if (pattern_fetched = '1') and (more_data_to_send = '1')
                    then
                        shift_reg <= data_in;
                        fetched <= '1';
                    else
                        shift_reg <= shift_reg;
                        fetched <= '0';
                    end if;
                when st_wait_ack =>
                    if (more_data_to_send = '1') and
                    -- Don't fetch if NACK is received
                    (sampled_bit = '0') and (sampling = '1') then
                        shift_reg <= data_in;
                        fetched <= '1';
                    else
                        shift_reg <= shift_reg;
                        fetched <= '0';
                    end if;
                when st_tx_data =>
                    fetched <= '0';
                    if pattern_fetched = '1' then
                        -- Push with sampled_bit only for having the same
                        -- expression as in st_rx_data state. We could as well
                        -- put '0' but this may generate more logic.
                        shift_reg <= shift_reg(6 downto 0) & sampled_bit;
                    else
                        shift_reg <= shift_reg;
                    end if;
                -- When we are in the state st_rx_ack, the pattern generator is
                -- generating the previous bit reception. This is why we must
                -- read SDA in st_rx_data and st_rx_ack. Also, first read of
                -- SDA during st_rx_data is not usefull because the pattern
                -- generator is generating the previous ACK cycle; this bit is
                -- discarded when last shift occurs (register is shifted 9
                -- times).
                when st_rx_data | st_rx_ack =>
                    fetched <= '0';
                    if sampling = '1' then
                        shift_reg <= shift_reg(6 downto 0) & sampled_bit;
                    else
                        shift_reg <= shift_reg;
                    end if;
                when others =>
                    shift_reg <= shift_reg;
                    fetched <= '0';
            end case;
        end if;
    end process;

    -- Calculate the pattern to be fed to the pattern generator depending on
    -- current state.
    p_pattern: process (state, shift_reg, more_data_to_receive)
    begin
        case state is
            when st_start =>
                pattern <= op_start;
            when st_stop =>
                pattern <= op_stop;
            when st_tx_data =>
                if shift_reg(shift_reg'high) = '1' then
                    pattern <= op_bit_1;
                else
                    pattern <= op_bit_0;
                end if;
            when st_tx_ack =>
                pattern <= op_ack_from_slave;
            when st_rx_data =>
                pattern <= op_bit_rx;
            when st_rx_ack =>
                if more_data_to_receive = '1' then
                    pattern <= op_ack_from_master;
                else
                    pattern <= op_nack_from_master;
                end if;
            when others =>
                pattern <= op_idle;
        end case;
    end process;

    -- Bit counter management
    p_bit_counter: process (clock, reset_n)
    begin
        if reset_n = '0' then
            bit_counter <= "10000000";
        elsif rising_edge(clock) then
            case state is
                when st_tx_data | st_rx_data =>
                    if pattern_fetched = '1' then
                        -- Shift right (decrements counter)
                        bit_counter <= '0' & bit_counter(7 downto 1);
                    else
                        bit_counter <= bit_counter;
                    end if;
                when others =>
                    bit_counter <= "10000000";
            end case;
        end if;
    end process;

    -- Received data output
    p_data_avail: process (clock, reset_n)
    begin
        if reset_n = '0' then
            data_avail <= '0';
        elsif rising_edge(clock) then
            case state is
                when st_rx_ack =>
                    -- Don't wait for the next pattern to be fetched. We need to
                    -- output early so the more_data_to_receive can be updated
                    -- in time, before next state.
                    if sampling = '1' then
                        data_avail <= '1';
                    else
                        data_avail <= '0';
                    end if;
                when others =>
                    data_avail <= '0';
            end case;
        end if;
    end process;
    data_out <= shift_reg;

    -- NACK alert
    -- Register it for performance.
    p_nack: process (clock, reset_n)
    begin
        if reset_n = '0' then
            nack <= '0';
        elsif rising_edge(clock) then
            case state is
                when st_wait_ack =>
                    if (sampling = '1') and (sampled_bit = '1') then
                        nack <= '1';
                    else
                        nack <= '0';
                    end if;
                when others =>
                    nack <= '0';
            end case;
        end if;
    end process;

    -- Trigger generation
    p_trigger: process (clock, reset_n)
    begin
        if reset_n = '0' then
            trigger_start <= '0';
        elsif rising_edge(clock) then
            if (state = st_sync) and (pattern_fetched = '1') then
                trigger_start <= '1';
            else
                trigger_start <= '0';
            end if;
            if (state = st_stop) and (pattern_fetched = '1') then
                trigger_end <= '1';
            else
                trigger_end <= '0';
            end if;
        end if;
    end process;

    last_bit <= bit_counter(0);

end;
