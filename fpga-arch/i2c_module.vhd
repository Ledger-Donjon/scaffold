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
-- Configurable I2C master module
--
entity i2c_module is
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
    en_size_h: in std_logic;
    en_size_l: in std_logic;

    -- Output registers
    reg_status: out byte_t;
    reg_data: out byte_t;
    reg_size_h: out byte_t;
    reg_size_l: out byte_t;

    -- I2C signals
    sda_in: in std_logic;
    sda_out: out std_logic;
    scl_in: in std_logic;
    scl_out: out std_logic;
    scl_out_en: out std_logic;
    trigger: out std_logic );
end;


architecture behavior of i2c_module is
    -- FSM
    type state_t is (st_ready, st_fetch, st_start, st_busy, st_stop);
    signal state: state_t;
    -- Status register
    signal ready: std_logic;
    signal nack: std_logic;
    -- Config register
    signal reg_config_trigger_start: std_logic;
    signal reg_config_trigger_end: std_logic;
    signal reg_config_clock_stretching: std_logic;
    signal reg_config: byte_t;
    -- FIFO control signals
    signal fifo_flush: std_logic;
    signal fifo_data: byte_t;
    signal fifo_wrreq: std_logic;
    signal fifo_q: byte_t;
    signal fifo_empty: std_logic;
    signal fifo_rdreq: std_logic;
    signal fifo_full: std_logic;
    signal fifo_usedw: std_logic_vector(8 downto 0);
    -- I2C control signals
    signal tx_size: std_logic_vector(9 downto 0);
    signal rx_size: std_logic_vector(15 downto 0);
    signal divisor: std_logic_vector(15 downto 0);
    signal divisor_locked: std_logic_vector(15 downto 0);
    signal i2c_start_transaction: std_logic;
    signal i2c_more_data_to_send: std_logic;
    signal i2c_more_data_to_receive: std_logic;
    signal i2c_data_out: byte_t;
    signal i2c_fetched: std_logic;
    signal i2c_nack: std_logic;
    signal i2c_busy: std_logic;
    signal i2c_data_avail: std_logic;
    signal i2c_trigger_start: std_logic;
    signal i2c_trigger_end: std_logic;
begin

    -- I2C peripheral
    e_i2c: entity work.i2c
    port map (
        clock => clock,
        reset_n => reset_n,
        divisor => divisor_locked,
        scl_in => scl_in,
        sda_in => sda_in,
        scl_out => scl_out,
        sda_out => sda_out,
        start_transaction => i2c_start_transaction,
        busy => i2c_busy,
        more_data_to_send => i2c_more_data_to_send,
        more_data_to_receive => i2c_more_data_to_receive,
        data_in => fifo_q,
        fetched => i2c_fetched,
        data_out => i2c_data_out,
        data_avail => i2c_data_avail,
        nack => i2c_nack,
        trigger_start => i2c_trigger_start,
        trigger_end => i2c_trigger_end );

    -- When clock stretching is disabled (bit set to 0), SCL is always driven.
    -- This allows not using an external pull-up resistor on SCL when using
    -- slave devices not doing clock stretching.
    scl_out_en <= (not scl_out) or (not reg_config_clock_stretching);

    -- Config register
    e_config: entity work.module_reg
    generic map (reset => x"01")
    port map (
        clock => clock,
        reset_n => reset_n,
        en => en_config,
        bus_in => bus_in,
        value => reg_config );
    reg_config_trigger_start <= reg_config(0);
    reg_config_trigger_end <= reg_config(1);
    reg_config_clock_stretching <= reg_config(2);

    -- Divisor configuration register.
    e_divisor: entity work.module_wide_reg
    generic map (wideness => 2, reset => x"0018")
    port map (
        clock => clock,
        reset_n => reset_n,
        en => en_divisor,
        bus_in => bus_in,
        value => divisor );

    -- Divisor value, locked during transactions.
    -- Updated only when a new transaction starts. This will prevent bad
    -- configurations due to shifts when updating the wide divisor register.
    p_divisor_locked: process (clock, reset_n)
    begin
        if reset_n = '0' then
            divisor_locked <= (others => '0');
        elsif rising_edge(clock) then
            if state = st_fetch then
                divisor_locked <= divisor;
            else
                divisor_locked <= divisor_locked;
            end if;
        end if;
    end process;

    -- FIFO reception size register
    p_rx_size: process (clock, reset_n)
    begin
        if reset_n = '0' then
            rx_size <= (others => '0');
        elsif rising_edge(clock) then
            case state is
                when st_ready =>
                    -- Write in this register is allowed.
                    if (bus_in.write = '1') and (en_size_h = '1') then
                        rx_size(15 downto 8) <= bus_in.write_data;
                    else
                        rx_size(15 downto 8) <= rx_size(15 downto 8);
                    end if;
                    if (bus_in.write = '1') and (en_size_l = '1') then
                        rx_size(7 downto 0) <= bus_in.write_data;
                    else
                        rx_size(7 downto 0) <= rx_size(7 downto 0);
                    end if;
                when st_busy =>
                    -- Decrement the counter if a byte is received
                    if i2c_data_avail = '1' then
                        rx_size <= std_logic_vector(unsigned(rx_size)-1);
                    else
                        rx_size <= rx_size;
                    end if;
                when others =>
                    rx_size <= rx_size;
            end case;
        end if;
    end process;

    -- FIFO data write control signals
    -- Signals are registered for performance.
    p_fifo_wrreq: process (clock, reset_n)
    begin
        if reset_n = '0' then
            fifo_data <= (others => '0');
            fifo_wrreq <= '0';
            fifo_flush <= '0';
        elsif rising_edge(clock) then
            case state is
                when st_ready =>
                    -- Write user to push bytes in the FIFO for transmission
                    fifo_data <= bus_in.write_data;
                    fifo_wrreq <= bus_in.write and en_data;
                    fifo_flush <= en_control and bus_in.write
                        and bus_in.write_data(1);
                when st_busy | st_stop | st_start | st_fetch =>
                    -- Push only received bytes
                    fifo_data <= i2c_data_out;
                    fifo_wrreq <= i2c_data_avail;
                    fifo_flush <= '0';
            end case;
        end if;
    end process;

    -- Transmission counter management.
    -- Used to count the number of remaining bytes to be sent. This helps
    -- managing the FIFO which has no read-ahead. The value of the counter can
    -- also be read by the host to know where a transaction has been cancelled
    -- when a NACK is received.
    p_tx_size: process (clock, reset_n)
    begin
        if reset_n = '0' then
            tx_size <= (others => '0');
        elsif rising_edge(clock) then
            case state is
                when st_fetch =>
                    tx_size <= fifo_full & fifo_usedw;
                when st_start | st_busy | st_stop =>
                    if (i2c_fetched = '1') and
                        (i2c_more_data_to_send = '1') then
                        tx_size <= std_logic_vector(unsigned(tx_size)-1);
                    else
                        tx_size <= tx_size;
                    end if;
                when st_ready =>
                    tx_size <= tx_size;
            end case;
        end if;
    end process;

    i2c_more_data_to_receive <= '0' when (unsigned(rx_size) = 0) else '1';
    i2c_more_data_to_send <= '0' when (unsigned(tx_size) = 0) else '1';

    -- FIFO to store bytes to be sent, and then the received bytes.
    -- This FIFO has no read-ahead, so q is available one clock cycle after
    -- rdreq is asserted.
    e_fifo512: entity work.fifo512
    port map (
        aclr => not reset_n,
        sclr => fifo_flush,
        clock => clock,
        data => fifo_data,
        wrreq => fifo_wrreq,
        q => fifo_q,
        empty => fifo_empty,
        rdreq => fifo_rdreq,
        usedw => fifo_usedw,
        full => fifo_full );

    -- FIFO pop
    p_fifo_pop: process(state, bus_in, en_data, i2c_fetched)
    begin
        case state is
            when st_ready =>
                fifo_rdreq <= bus_in.read and en_data;
            -- Assert rdreq before starting to emulate FIFO read-ahead.
            when st_fetch =>
                fifo_rdreq <= '1';
            when others =>
                fifo_rdreq <= i2c_fetched;
        end case;
    end process;

    -- FSM management
    p_fsm: process (clock, reset_n)
    begin
        if reset_n = '0' then
            state <= st_ready;
        elsif rising_edge(clock) then
            case state is
                when st_ready =>
                    if (bus_in.write = '1') and (en_control = '1')
                        and (bus_in.write_data(0) = '1') then
                        state <= st_fetch;
                    else
                        state <= st_ready;
                    end if;
                -- st_fetch is one clock cycle long to make FIFO output
                -- available after asserting rdreq (FIFO has no read-ahead).
                -- This state is also used to load the transmission counter to
                -- its initial value.
                when st_fetch =>
                    state <= st_start;
                -- st_start is one clock cycle long, just to assert I2C
                -- start_transaction signal.
                when st_start =>
                    state <= st_busy;
                when st_busy =>
                    if i2c_busy = '0' then
                        state <= st_stop;
                    else
                        state <= st_busy;
                    end if;
                when st_stop =>
                    state <= st_ready;
            end case;
        end if;
    end process;

    -- NACK flag in the status register
    -- Receiving NACK from the peripheral will raise the NACK flag.
    -- Starting a new transaction will clear it.
    p_nack: process (clock, reset_n)
    begin
        if reset_n = '0' then
            nack <= '0';
        elsif rising_edge(clock) then
            case state is
                -- Reset nack flag
                when st_start =>
                    nack <= '0';
                when others =>
                    nack <= nack or i2c_nack;
            end case;
        end if;
    end process;

    -- Trigger selection
    p_trigger: process (clock, reset_n)
    begin
        if reset_n = '0' then
            trigger <= '0';
        elsif rising_edge(clock) then
            trigger <= (reg_config_trigger_start and i2c_trigger_start)
                or (reg_config_trigger_end and i2c_trigger_end);
        end if;
    end process;

    i2c_start_transaction <= '1' when (state = st_start) else '0';

    ready <= '1' when (state = st_ready) else '0';
    reg_status <= "00000" & (not fifo_empty) & nack & ready;
    reg_size_h <= "000000" & tx_size(9 downto 8);
    reg_size_l <= tx_size(7 downto 0);
    reg_data <= fifo_q;

end;
