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
-- Allows reading and writing to the registers mapped to the bus of the device
-- through a UART.
--
entity bus_bridge is
generic (
    -- System clock frequency, required for UART baudrate divisor calculation.
    system_frequency: positive;
    -- Serial baudrate
    baudrate: positive );
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- UART TX signal
    uart_tx: out std_logic;
    -- UART RX signal
    uart_rx: in std_logic;
    -- Bus signals controlled by the bridge.
    bus_in: out bus_in_t;
    -- Bus signals read by the bridge.
    bus_out: in bus_out_t;
    -- High while the bridge is working.
    busy: out std_logic;
    -- High when the bride is in error state.
    err: out std_logic );
end;


architecture behavior of bus_bridge is
    type state_t is (
        st_command,
        st_timeout_conf_1,
        st_timeout_conf_2,
        st_timeout_conf_3,
        st_timeout_conf_4,
        st_addr_high,
        st_addr_low,
        st_poll_addr_high,
        st_poll_addr_low,
        st_poll_mask,
        st_poll_value,
        st_size,
        st_loop,
        st_ack_wait,
        st_ack_send,
        st_poll_1,
        st_poll_2,
        st_poll_3,
        st_poll_4,
        st_timeout,
        st_timeout_fill_wait,
        st_timeout_fill_send,
        st_timeout_flush,
        st_value,
        st_write,
        st_read,
        st_read_load,
        st_read_wait,
        st_read_send,
        st_error );

    -- Data to be sent from the bridge to host.
    signal uart_data_tx: std_logic_vector(7 downto 0);
    -- High during one clock cycle when a byte must be sent from the bridge to
    -- the host.
    signal uart_start: std_logic;
    -- High when the UART is ready to send another byte.
    signal uart_ready: std_logic;
    -- High during one clock cycle when the UART receives a byte.
    signal uart_has_data: std_logic;
    -- The data the UART receives. Valid when uart_has_data is asserted, until
    -- the next received byte.
    signal uart_data_rx: std_logic_vector(7 downto 0);

    -- FIFO output data byte.
    signal fifo_q: std_logic_vector(7 downto 0);
    -- High when FIFO is empty
    signal fifo_empty: std_logic;
    -- FIFO read request. When high, the FIFO will drop a byte at next clock
    -- cycle.
    signal fifo_rdreq: std_logic;
    -- When high, the FSM is waiting from a byte to be available from the FIFO.
    -- This signal is used to perform read requests.
    signal need_byte: std_logic;
    -- When high, the output of the FIFO shows the next input byte. This signal
    -- will rise one clock cycle after fifo_rdreq is asserted.
    signal byte_available: std_logic;

    -- Current and next FSM states.
    signal current_state: state_t;
    signal next_state: state_t;

    -- High when UART data output is a valid bus command.
    signal valid_rw_command: std_logic;
    -- Command byte storage register.
    signal command: std_logic_vector(7 downto 0);
    -- Bit 0 of command byte. When 1, this is a write command. When 0, this is
    -- a read command.
    signal command_is_write: std_logic;
    -- Bit 1 of command byte. When 1, the size argument is expected.
    signal command_has_size: std_logic;
    -- Bit 2 of command byte. When 1, polling is enabled for the command.
    signal command_has_polling: std_logic;
    -- Address storage registers.
    signal addr_high: std_logic_vector(7 downto 0);
    signal addr_low: std_logic_vector(7 downto 0);
    signal addr: std_logic_vector(15 downto 0);
    -- Polling address storage registers.
    signal poll_addr_high: std_logic_vector(7 downto 0);
    signal poll_addr_low: std_logic_vector(7 downto 0);
    signal poll_addr: std_logic_vector(15 downto 0);
    -- Polling mask storage register.
    signal poll_mask: std_logic_vector(7 downto 0);
    -- Polling value storage register.
    signal poll_value: std_logic_vector(7 downto 0);
    -- Read/write size command storage register. This register stores the number
    -- of bytes to be read or written. This register has 9 bits because it can
    -- go up to 256.
    signal size: std_logic_vector(7 downto 0);
    -- Counts the number of successfully processed bytes during a read or write
    -- operation. This is usefull when doing a polled request to know if a
    -- timeout occured.
    signal size_done: std_logic_vector(7 downto 0);
    -- High when polling is finished.
    signal polling_ok: std_logic;
    -- Polling timeout counter current value.
    signal polling_counter: std_logic_vector(31 downto 0);
    signal polling_counter_is_zero: std_logic;
    -- Polling timeout counter initial value.
    signal polling_counter_max: std_logic_vector(31 downto 0);
    -- High when polling timeout is enabled.
    signal polling_timeout_enabled: std_logic;
    -- High when polling counter is counting.
    signal polling_counter_en: std_logic;
    -- High when loading initial value in the polling counter.
    signal polling_counter_load: std_logic;

    -- Register for pipelining the incoming data from the bus.
    signal bus_read_data_pipelined: byte_t;

begin

    e_light_uart: entity work.light_uart
    generic map (
        system_frequency => system_frequency,
        baudrate => baudrate )
    port map (
        clock => clock,
        reset_n => reset_n,
        data_tx => uart_data_tx,
        start => uart_start,
        ready => uart_ready,
        has_data => uart_has_data,
        data_rx => uart_data_rx,
        rx => uart_rx,
        tx => uart_tx );

    -- FIFO used to store the received bytes awaiting for processing. This is
    -- useful for polling-write operations.
    -- Reading a byte from the FIFO takes one clock cycle (no read-ahead).
    e_fifo512: entity work.fifo512
    port map (
        aclr => not reset_n,
        sclr => '0',
        clock => clock,
        data => uart_data_rx,
        wrreq => uart_has_data,
        q => fifo_q,
        empty => fifo_empty,
        rdreq => fifo_rdreq );

    -- Fetch FIFO byte when possible and requested.
    fifo_rdreq <= (not fifo_empty) and need_byte and not (byte_available);

    -- Tell FSM when a byte is available on the output of the FIFO.
    p_byte_available: process (clock, reset_n)
    begin
        if reset_n = '0' then
            byte_available <= '0';
        elsif rising_edge(clock) then
            byte_available <= fifo_rdreq;
        end if;
    end process;

    -- Registration of the data bus, to reduce design critical path. This is
    -- done at the cost of some FSM extra states to handle read delay.
    -- Read data is valid only the clock cycle after bus_in.read signal is
    -- asserted
    p_bus_read_data_pipelined: process (clock, reset_n)
    begin
        if reset_n = '0' then
            bus_read_data_pipelined <= (others => '0');
        elsif rising_edge(clock) then
            case current_state is
                when st_read_load | st_poll_2 =>
                    bus_read_data_pipelined <= bus_out.read_data;
                when others =>
                    bus_read_data_pipelined <= bus_read_data_pipelined;
            end case;
        end if;
    end process;

    -- Next state to current state registration
    p_current_state: process (clock, reset_n)
    begin
        if reset_n = '0' then
            current_state <= st_command;
        elsif rising_edge(clock) then
            current_state <= next_state;
        end if;
    end process;

    -- Next state calculation
    p_next_state: process (current_state, byte_available, valid_rw_command,
        command_has_polling, command_has_size, command_is_write, size,
        polling_ok, uart_ready, fifo_q, polling_counter_is_zero,
        polling_timeout_enabled)
    begin
        case current_state is
            -- Waiting for command byte from UART.
            when st_command =>
                if byte_available = '1' then
                    if valid_rw_command = '1' then
                        -- Register read or write command.
                        next_state <= st_addr_high;
                    elsif fifo_q = x"08" then
                        -- Timeout register configuration command.
                        next_state <= st_timeout_conf_1;
                    else
                        -- Unknown command. Enter error state.
                        next_state <= st_error;
                    end if;
                else
                    next_state <= st_command;
                end if;

            -- Waiting for first byte of timeout configuration register.
            when st_timeout_conf_1 =>
                if byte_available = '1' then
                    next_state <= st_timeout_conf_2;
                else
                    next_state <= st_timeout_conf_1;
                end if;

            -- Waiting for second byte of timeout configuration register.
            when st_timeout_conf_2 =>
                if byte_available = '1' then
                    next_state <= st_timeout_conf_3;
                else
                    next_state <= st_timeout_conf_2;
                end if;

            -- Waiting for third byte of timeout configuration register.
            when st_timeout_conf_3 =>
                if byte_available = '1' then
                    next_state <= st_timeout_conf_4;
                else
                    next_state <= st_timeout_conf_3;
                end if;

            -- Waiting for fourth (and last) byte of timeout configuration
            -- register.
            when st_timeout_conf_4 =>
                if byte_available = '1' then
                    next_state <= st_command;
                else
                    next_state <= st_timeout_conf_4;
                end if;

            -- Waiting for address high byte from UART.
            when st_addr_high =>
                if byte_available = '1' then
                    next_state <= st_addr_low;
                else
                    next_state <= st_addr_high;
                end if;

            -- Waiting for address low byte from UART.
            when st_addr_low =>
                if byte_available = '1' then
                    if command_has_polling = '1' then
                        next_state <= st_poll_addr_high;
                    else
                        next_state <= st_size;
                    end if;
                else
                    next_state <= st_addr_low;
                end if;

            -- Waiting for polling address high byte from UART.
            when st_poll_addr_high =>
                if byte_available = '1' then
                    next_state <= st_poll_addr_low;
                else
                    next_state <= st_poll_addr_high;
                end if;

            -- Waiting for polling address low byte from UART.
            when st_poll_addr_low =>
                if byte_available = '1' then
                    next_state <= st_poll_mask;
                else
                    next_state <= st_poll_addr_low;
                end if;

            -- Waiting for polling mask from UART.
            when st_poll_mask =>
                if byte_available = '1' then
                    next_state <= st_poll_value;
                else
                    next_state <= st_poll_mask;
                end if;

            -- Waiting for polling value from UART.
            when st_poll_value =>
                if byte_available = '1' then
                    next_state <= st_size;
                else
                    next_state <= st_poll_value;
                end if;

            -- Loading size byte: wait for byte from UART if the command
            -- requires a size argument (LSB of command is 1), otherwise load 0
            -- (for size = 1).
            when st_size =>
                if command_has_size = '1' then
                    if byte_available = '1' then
                        next_state <= st_loop;
                    else
                        next_state <= st_size;
                    end if;
                else
                    next_state <= st_loop;
                end if;

            -- Loop state. If all bytes have been read/written, send acknoledge
            -- and return to initial state. Otherwise, enter polling logic.
            when st_loop =>
                if unsigned(size) = 0 then
                    next_state <= st_ack_wait;
                else
                    next_state <= st_poll_1;
                end if;

            -- Wait for UART to be ready for transmitting acknoledge byte.
            when st_ack_wait =>
                if uart_ready = '1' then
                    next_state <= st_ack_send;
                else
                    next_state <= st_ack_wait;
                end if;

            -- Transmitting acknoledge byte.
            when st_ack_send =>
                next_state <= st_command;

            -- First polling state. This is a dummy state to perform initial
            -- polling read cycle on the bus. The value read on the bus will be
            -- tested two clock cycles later, in st_poll_3 state.
            when st_poll_1 =>
                next_state <= st_poll_2;

            -- One clock cycle delay required because bus_out.read_data is
            -- registered in bus_read_data_pipelined.
            when st_poll_2 =>
                next_state <= st_poll_3;

            -- Polling loop state.
            when st_poll_3 =>
                if polling_ok = '1' then
                    -- Polling unlocked
                    next_state <= st_poll_4;
                elsif (polling_counter_is_zero = '1') and
                    (polling_timeout_enabled = '1') then
                    -- Polling timeout. Leave polling loop and main transfert
                    -- loop.
                    next_state <= st_timeout;
                else
                    -- Stay in polling loop
                    next_state <= st_poll_1;
                end if;

            -- End of polling. This extra cycle is used for loading read or
            -- write address on the bus.
            -- This state has been added for pipelining purpose.
            when st_poll_4 =>
                if command_is_write = '1' then
                    -- Register write command.
                    next_state <= st_value;
                else
                    -- Register read command.
                    next_state <= st_read;
                end if;

            -- Waiting from UART for the value to be written in the register.
            when st_value =>
                if byte_available = '1' then
                    next_state <= st_write;
                else
                    next_state <= st_value;
                end if;

            -- Register write cycle.
            when st_write =>
                next_state <= st_loop;

            -- Register read cycle.
            when st_read =>
                next_state <= st_read_load;

            -- One clock cycle to fetch data from the bus
            when st_read_load =>
                next_state <= st_read_wait;

            -- Waiting for UART to be ready to transmit.
            when st_read_wait =>
                if uart_ready = '1' then
                    next_state <= st_read_send;
                else
                    next_state <= st_read_wait;
                end if;

            -- Transmitting the value read from a register.
            when st_read_send =>
                next_state <= st_loop;

            -- Timeout
            -- If we are executing a read operation, send zeros instead of the
            -- expected bytes, then go to ack byte transmission.
            -- If we are executing a write operation, go directly to the ack
            -- byte transmission.
            when st_timeout =>
                if unsigned(size) = 0 then
                    next_state <= st_ack_wait;
                else
                    if command_is_write = '1' then
                        -- Write command. We need to pop from the FIFO the bytes
                        -- which cannot be written.
                        next_state <= st_timeout_flush;
                    else
                        -- Read command. We need to send bytes before returning
                        -- aknowledge byte.
                        next_state <= st_timeout_fill_wait;
                    end if;
                end if;

            -- Timeout response dummy bytes loop.
            -- Wait for UART to be ready for transmission.
            when st_timeout_fill_wait =>
                -- Some bytes must be sent. Wait for UART to be ready.
                if uart_ready = '1' then
                    next_state <= st_timeout_fill_send;
                else
                    next_state <= st_timeout_fill_wait;
                end if;

            -- Timeout response dummy bytes loop.
            -- Send a '\0' byte over the UART. Leave the loop if all dummy
            -- bytes have been sent, or return to UART ready wait.
            when st_timeout_fill_send =>
                next_state <= st_timeout;

            -- Wait until a byte is available in the FIFO.
            -- When leaving this state, a byte is poped from the FIFO.
            when st_timeout_flush =>
                if byte_available = '1' then
                    next_state <= st_timeout;
                else
                    next_state <= st_timeout_flush;
                end if;

            -- Error state. Entered if an invalid command byte has been
            -- received.
            when st_error =>
                next_state <= st_error;

            when others =>
                next_state <= st_error;
        end case;
    end process;

    -- Compute when the FSM waits for an input byte to be available. This will
    -- control the FIFO.
    p_need_byte: process (current_state, command_has_size)
    begin
        case current_state is
            when st_command | st_addr_high | st_addr_low | st_poll_addr_high |
                st_poll_addr_low | st_poll_mask | st_poll_value | st_value |
                st_timeout_conf_1 | st_timeout_conf_2 | st_timeout_conf_3 |
                st_timeout_conf_4 | st_timeout_flush =>
                need_byte <= '1';
            when st_size =>
                need_byte <= command_has_size;
            when others => need_byte <= '0';
        end case;
    end process;

    -- Command value validator
    -- bit 0: read/write
    -- bit 1: size attribute
    -- bit 2: polling attribute
    -- Polling commands with size attribute are not allowed (for the moment).
    p_valid_rw_command: process (fifo_q)
    begin
        case fifo_q is
            when x"00" | x"01" | x"02" | x"03" | x"04" | x"05" | x"06" | x"07"
                 => valid_rw_command <= '1';
            when others => valid_rw_command <= '0';
        end case;
    end process;

    -- Fetch command byte when received.
    p_command: process (clock, reset_n)
    begin
        if reset_n = '0' then
            command <= (others => '0');
        elsif rising_edge(clock) then
            if (current_state = st_command) and (byte_available = '1') then
                command <= fifo_q;
            else
                command <= command;
            end if;
        end if;
    end process;

    command_is_write <= command(0);
    command_has_size <= command(1);
    command_has_polling <= command(2);

    -- Fetch address high byte when received.
    p_addr_high: process (clock, reset_n)
    begin
        if reset_n = '0' then
            addr_high <= (others => '0');
        elsif rising_edge(clock) then
            if (current_state = st_addr_high) and (byte_available = '1') then
                addr_high <= fifo_q;
            else
                addr_high <= addr_high;
            end if;
        end if;
    end process;

    -- Fetch address high byte when received.
    p_addr_low: process (clock, reset_n)
    begin
        if reset_n = '0' then
            addr_low <= (others => '0');
        elsif rising_edge(clock) then
            if (current_state = st_addr_low) and (byte_available = '1') then
                addr_low <= fifo_q;
            else
                addr_low <= addr_low;
            end if;
        end if;
    end process;

    addr <= addr_high & addr_low;

    -- Fetch polling address high byte when received.
    p_poll_addr_high: process (clock, reset_n)
    begin
        if reset_n = '0' then
            poll_addr_high <= (others => '0');
        elsif rising_edge(clock) then
            if (current_state = st_poll_addr_high) and (byte_available = '1') then
                poll_addr_high <= fifo_q;
            else
                poll_addr_high <= poll_addr_high;
            end if;
        end if;
    end process;

    -- Fetch polling address high byte when received.
    p_poll_addr_low: process (clock, reset_n)
    begin
        if reset_n = '0' then
            poll_addr_low <= (others => '0');
        elsif rising_edge(clock) then
            if (current_state = st_poll_addr_low) and (byte_available = '1') then
                poll_addr_low <= fifo_q;
            else
                poll_addr_low <= poll_addr_low;
            end if;
        end if;
    end process;

    poll_addr <= poll_addr_high & poll_addr_low;

    -- Fetch polling mask.
    p_poll_mask: process (clock, reset_n)
    begin
        if reset_n = '0' then
            poll_mask <= (others => '0');
        elsif rising_edge(clock) then
            if (current_state = st_poll_mask) and (byte_available = '1') then
                poll_mask <= fifo_q;
            else
                poll_mask <= poll_mask;
            end if;
        end if;
    end process;

    -- Fetch polling value.
    p_poll_value: process (clock, reset_n)
    begin
        if reset_n = '0' then
            poll_value <= (others => '0');
        elsif rising_edge(clock) then
            if (current_state = st_poll_value) and (byte_available = '1') then
                poll_value <= fifo_q;
            else
                poll_value <= poll_value;
            end if;
        end if;
    end process;

    -- Fetch size byte.
    -- Copy input data when expect_size is 1, otherwise, set to 0 (1 byte).
    p_size: process (clock, reset_n)
    begin
        if reset_n = '0' then
            size <= (others => '0');
        elsif rising_edge(clock) then
            case current_state is
                -- Size loading state. Copy UART value if command has size
                -- parameter, otherwise set to 1 by default.
                when st_size =>
                    if (command_has_size = '1') and (byte_available = '1') then
                        size <= fifo_q;
                    else
                        size <= "00000001";
                    end if;
                -- We don't want to decrement size if there is a polling
                -- timeout, so don't do it in loop state but once we are sure
                -- the bus cycle will occur.
                when st_poll_4 | st_timeout =>
                    -- Decrease size counter.
                    size <= std_logic_vector(unsigned(size) - 1);
                when others => size <= size;
            end case;
        end if;
    end process;

    -- Polling management
    -- TODO: we can save some logic if poll_value is precalculated by the host.
    polling_ok <= '1' when ((not (command_has_polling = '1')) or
        ((bus_read_data_pipelined and poll_mask) = (poll_value and poll_mask)))
        else '0';

    -- Polling timeout configuration register loading
    p_polling_counter_max: process (clock, reset_n)
    begin
        if reset_n = '0' then
            -- 0 means timeout is disabled.
            polling_counter_max <= (others => '0');
        elsif rising_edge(clock) then
            case current_state is
                when st_timeout_conf_1 | st_timeout_conf_2 | st_timeout_conf_3
                    | st_timeout_conf_4 =>
                    if byte_available = '1' then
                        -- Shift-load from the right
                        polling_counter_max <= polling_counter_max(23 downto 0)
                            & fifo_q;
                    else
                        polling_counter_max <= polling_counter_max;
                    end if;
                when others =>
                    polling_counter_max <= polling_counter_max;
            end case;
        end if;
    end process;

    -- Polling timeout counter.
    e_polling_counter: entity work.lpm_down_counter_32
    port map (
        aclr => not reset_n,
        clock => clock,
        cnt_en => polling_counter_en,
        sload => polling_counter_load,
        data => polling_counter_max,
        q => polling_counter );

    polling_timeout_enabled <= '0' when unsigned(polling_counter_max) = 0
        else '1';
    polling_counter_is_zero <= '1' when unsigned(polling_counter) = 0 else '0';
    polling_counter_en <= '1' when (current_state = st_poll_3) else '0';
    polling_counter_load <= '1' when (current_state = st_loop) else '0';

    -- size_done counts the number of processed bytes (read or written). At the
    -- end of a command, this number is returned as the acknoledgment byte. If a
    -- polling timeout occured, size_done will be smaller than the size field of
    -- the command, so it is possible to know how many bytes are valid in a
    -- response or how many byte have been effectively written.
    p_size_done: process (clock, reset_n)
    begin
        if reset_n = '0' then
            size_done <= (others => '0');
        elsif rising_edge(clock) then
            case current_state is
                when st_command =>
                    size_done <= (others => '0');
                when st_poll_4 =>
                    size_done <= std_logic_vector(unsigned(size_done) + 1);
                when others =>
                    size_done <= size_done;
            end case;
        end if;
    end process;

    -- Bus address control
    -- Use polling address during polling states, otherwise use the read/write
    -- address.
    -- We use a register here for pipelining, so the address must be preloaded
    -- before any read, write or polling operation.
    p_bus_address: process (clock, reset_n)
    begin
        if reset_n = '0' then
            bus_in.address <= (others => '0');
        elsif rising_edge(clock) then
            case current_state is
                when st_loop | st_poll_1 | st_poll_2 | st_poll_3 =>
                    bus_in.address <= poll_addr;
                when others =>
                    bus_in.address <= addr;
            end case;
        end if;
    end process;

    -- Bus read cycle control
    p_bus_read: process (current_state, command_has_polling)
    begin
        case current_state is
            when st_read =>
                bus_in.read <= '1';
            when st_poll_1 =>
                bus_in.read <= command_has_polling;
            when others =>
                bus_in.read <= '0';
        end case;
    end process;

    -- Bus write cycle control
    p_bus_write: process (current_state)
    begin
        case current_state is
            when st_write =>
                bus_in.write <= '1';
            when others =>
                bus_in.write <= '0';
        end case;
    end process;

    -- UART transmission control
    p_uart_start: process (current_state, bus_read_data_pipelined, size_done)
    begin
        case current_state is
            when st_read_send =>
                uart_start <= '1';
                uart_data_tx <= bus_read_data_pipelined;
            when st_timeout_fill_send =>
                -- Sending dummy zeros when a timeout cancelled a read loop
                -- operation.
                uart_start <= '1';
                uart_data_tx <= "00000000";
            when st_ack_send =>
                uart_start <= '1';
                uart_data_tx <= size_done;
            when others =>
                uart_start <= '0';
                uart_data_tx <= "00000000";
        end case;
    end process;

    busy <= '1' when (current_state /= st_command) else '0';
    err <= '1' when (current_state = st_error) else '0';

    -- Bus write data
    bus_in.write_data <= fifo_q;

end;
