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
--
--
-- Testbench for whole system simulation.
-- Should work with modelsim.
-- Run this test-bench for 2 ms. Unexpected responses from the system are
-- logged as "Errors" in modelsim transcript.
--


library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.common_pkg.all;


entity scaffold_sim is end;


architecture behavior of scaffold_sim is
    -- Frequency of external clock (before PLL)
    -- 25 MHz
    constant clock_frequency: integer := 25000000;
    constant clock_period: time := (1 sec) / clock_frequency;
    -- Expected system frequency (after PLL).
    -- 100 MHz
    constant system_frequency: integer := 100000000;
    -- UART baudrate for the communication between the host and Scaffold.
    constant baudrate: integer := 2000000;
    constant bit_period: time := (1 sec) / baudrate;

    -- External clock
    signal clock: std_logic;
    -- Reset
    signal reset_n: std_logic;

    -- UART communication
    signal tx: std_logic;
    signal rx: std_logic;
    -- Scaffold generic I/Os
    signal io: std_logic_vector(35 downto 0);

    -- Transactions between host and system, as unsigned signals for better
    -- readability during debug.
    signal debug_tx: unsigned(7 downto 0);
    signal debug_rx: unsigned(7 downto 0);

    signal next_test: std_logic;
begin

    e_scaffold: entity work.scaffold port map (
        clock => clock,
        reset_n => reset_n,
        rx => rx,
        tx => tx,
        io => io,
        teardown => '0');

    -- External clock generation
    p_clock: process
    begin
        clock <= '0';
        wait for clock_period / 2;
        clock <= '1';
        wait for clock_period / 2;
    end process;

    -- Reset signal
    p_reset: process
    begin
        reset_n <= '0';
        wait for clock_period * 4;
        reset_n <= '1';
        wait;
    end process;

    -- Loopback of D0 to D1
    io(1) <= io(0);

    p_0: process is
        -- Emulate UART bit transmission
        procedure send_bit(value: in std_logic) is
        begin
            rx <= value;
            wait for bit_period;
        end;

        -- Emulate UART byte transmission
        procedure send_byte (value: in byte_t ) is
        begin
            send_bit('0');
            for i in 0 to 7 loop
                send_bit(value(i));
            end loop;
            send_bit('1');
        end;

        -- Send a single byte register write request
        procedure write_register (
            address: in address_t;
            value: in byte_t) is
        begin
            send_byte(x"01");
            send_byte(address(15 downto 8));
            send_byte(address(7 downto 0));
            send_byte(value);
        end;

        -- Send a register single byte write request, with polling mode.
        procedure write_register_poll (
            address: in address_t;
            poll_address: in address_t;
            poll_mask: in byte_t;
            poll_value: in byte_t;
            value: in byte_t ) is
        begin
            send_byte(x"05");
            send_byte(address(15 downto 8));
            send_byte(address(7 downto 0));
            send_byte(poll_address(15 downto 8));
            send_byte(poll_address(7 downto 0));
            send_byte(poll_mask);
            send_byte(poll_value);
            send_byte(value);
        end;

        -- Send register n bytes write request, with polling mode.
        -- The data bytes must be sent manually with send_byte.
        procedure write_n_register_poll (
            address: in address_t;
            poll_address: in address_t;
            poll_mask: in byte_t;
            poll_value: in byte_t;
            count: positive ) is
        begin
            send_byte(x"07");
            send_byte(address(15 downto 8));
            send_byte(address(7 downto 0));
            send_byte(poll_address(15 downto 8));
            send_byte(poll_address(7 downto 0));
            send_byte(poll_mask);
            send_byte(poll_value);
            send_byte(std_logic_vector(to_unsigned(count, 8)));
        end;

        -- Read n times a register
        procedure read_register (
            address: in address_t;
            count: positive ) is
        begin
            if count = 1 then
                send_byte(x"00");
            else
                send_byte(x"02");
            end if;
            send_byte(address(15 downto 8));
            send_byte(address(7 downto 0));
            if count > 1 then
                send_byte(std_logic_vector(to_unsigned(count, 8)));
            end if;
        end;

        -- Send a byte register read request, with polling mode.
        procedure read_register_poll (
            address: in address_t;
            poll_address: in address_t;
            poll_mask: in byte_t;
            poll_value: in byte_t;
            count: positive ) is
        begin
            if count = 1 then
                send_byte(x"04");
            else
                send_byte(x"06");
            end if;
            send_byte(address(15 downto 8));
            send_byte(address(7 downto 0));
            send_byte(poll_address(15 downto 8));
            send_byte(poll_address(7 downto 0));
            send_byte(poll_mask);
            send_byte(poll_value);
            if count > 1 then
                send_byte(std_logic_vector(to_unsigned(count, 8)));
            end if;
        end;
    begin
        rx <= '1';
        wait until reset_n = '1';
        wait for clock_period * 16;

        -- Read version string, twice
        read_register(x"0100", 27);

        -- Configure polling timeout
        wait for 200 us;
        send_byte(x"08");
        send_byte(x"00");
        send_byte(x"00");
        send_byte(x"20");
        send_byte(x"00");
        wait for 25 us;

        -- Test timeout
--        read_register_poll(x"0100", x"1234", x"ff", x"55", 5);
--        wait for 100 us;
--        write_n_register_poll(x"0100", x"1234", x"ff", x"55", 5);
--        send_byte(x"01");
--        send_byte(x"02");
--        send_byte(x"03");
--        send_byte(x"04");
--        send_byte(x"05");
--        wait for 100 us;
--
--        write_register(x"0201", x"aa");
--
--        wait;

        -- Configure UART divisor
        write_register(x"0403", x"01");
        write_register(x"0403", x"00");
        -- Connect UART0 TX to IO D0
        write_register(x"f100", x"05");
        -- Connect IO D1 to UART0 RX
        write_register(x"f000", x"03");
        -- Flush UART because it may have received a zero byte when it was
        -- unconnected.
        write_register(x"0401", x"01");
        wait for 25 us;

        -- Send 'Hello'
        write_n_register_poll(x"0404", x"0400", x"01", x"01", 5);
        send_byte(x"48");
        send_byte(x"65");
        send_byte(x"6c");
        send_byte(x"6c");
        send_byte(x"6f");

        wait for 100 us;

        -- Receive 'Hello' in loopback
        read_register_poll(x"0404", x"0400", x"04", x"00", 5);

        -- Test delay generator
--        io(3) <= '0';
--        write_register(x"f102", x"07");
--        write_register(x"f001", x"06");
--        write_register(x"0306", x"10");
--        write_register(x"0301", x"01");
--        wait for clock_period * 128;
--        io(3) <= '1';
--        wait for clock_period;
--        io(3) <= '0';

        wait until next_test = '1';

        -- Test I2C

        -- Connect I2C SDA to D2 and SCL to D3
        write_register(x"f102", x"10");
        write_register(x"f103", x"11");
        write_register(x"f007", x"04");
        write_register(x"f008", x"05");
        -- Set I2C divisor
        write_register(x"0703", x"01");
        write_register(x"0703", x"00");
        -- Prepare I2C transaction
        write_register(x"0704", x"aa");
        write_register(x"0705", x"00");
        write_register(x"0706", x"01");
        -- Start transaction
        write_register(x"0701", x"01");

        wait until next_test = '1';

        -- Test SPI
        io(12) <= '1';
        write_register(x"f109", x"14"); -- mosi >> d5
        write_register(x"f10a", x"13"); -- sck >> d6
        write_register(x"f10b", x"15"); -- ss >> d7
        write_register(x"f009", x"0e"); -- d8 >> miso
        write_register(x"0803", x"04"); -- Set divisor
        write_register(x"0804", x"aa"); -- Prepare data to be sent
        write_register(x"0801", x"07"); -- Start 8-bits transaction
        -- Read data register when transmission ended.
        read_register_poll(x"0804", x"0800", x"01", x"01", 1);

        wait;
    end process;

    -- Test the responses of the system on the UART line.
    p_test: process is
        -- Wait until next incomming byte or UART, and check the received data
        -- matches what's expected.
        procedure wait_byte(
            value: in std_logic_vector(7 downto 0) )
        is
            variable buf: std_logic_vector(7 downto 0);
        begin
            wait until tx = '0';
            wait for bit_period;
            for i in 0 to 7 loop
                wait for bit_period / 2;
                buf(i) := tx;
                wait for bit_period / 2;
            end loop;

            debug_tx <= (others => 'X');
            wait for bit_period / 2;
            debug_tx <= unsigned(buf);
            assert buf = value report "Unexpected response";
        end;
    begin
        wait until reset_n = '1';
        next_test <= '0';

        wait_byte(x"00");
        wait_byte(x"73"); -- s
        wait_byte(x"63"); -- c
        wait_byte(x"61"); -- a
        wait_byte(x"66"); -- f
        wait_byte(x"66"); -- f
        wait_byte(x"6f"); -- o
        wait_byte(x"6c"); -- l
        wait_byte(x"64"); -- d
        wait_byte(x"2d"); -- -
        wait_byte(x"30"); -- 0
        wait_byte(x"2e"); -- .
        wait_byte(x"37"); -- 7
        wait_byte(x"00");
        wait_byte(x"73"); -- s
        wait_byte(x"63"); -- c
        wait_byte(x"61"); -- a
        wait_byte(x"66"); -- f
        wait_byte(x"66"); -- f
        wait_byte(x"6f"); -- o
        wait_byte(x"6c"); -- l
        wait_byte(x"64"); -- d
        wait_byte(x"2d"); -- -
        wait_byte(x"30"); -- 0
        wait_byte(x"2e"); -- .
        wait_byte(x"37"); -- 7
        wait_byte(x"00");
        wait_byte(x"1b");

        -- UART testing
        wait_byte(x"01"); -- UART configuration
        wait_byte(x"01"); -- UART configuration
        wait_byte(x"01"); -- IO configuration
        wait_byte(x"01"); -- IO configuration
        wait_byte(x"01"); -- UART flush
        wait_byte(x"05"); -- Number of transmitted bytes
        wait_byte(x"48"); -- H
        wait_byte(x"65"); -- e
        wait_byte(x"6c"); -- l
        wait_byte(x"6c"); -- l
        wait_byte(x"6f"); -- o
        wait_byte(x"05"); -- Number of received bytes

        next_test <= '1';
        wait for clock_period;
        next_test <= '0';

        wait_byte(x"01"); -- IO configuration
        wait_byte(x"01"); -- IO configuration
        wait_byte(x"01"); -- IO configuration
        wait_byte(x"01"); -- IO configuration
        wait_byte(x"01"); -- I2C divisor configuration
        wait_byte(x"01"); -- I2C divisor configuration
        wait_byte(x"01"); -- I2C data write
        wait_byte(x"01"); -- I2C size configuration
        wait_byte(x"01"); -- I2C size configuration
        wait_byte(x"01"); -- I2C transaction start

        next_test <= '1';
        wait for clock_period;
        next_test <= '0';

        -- SPI
        wait_byte(x"01");
        wait_byte(x"01");
        wait_byte(x"01");
        wait_byte(x"01");
        wait_byte(x"01");
        wait_byte(x"01");
        wait_byte(x"01");
        wait_byte(x"ff");
        wait_byte(x"01");

        loop
            wait_byte("XXXXXXXX");
        end loop;

        wait;
    end process;

    -- I2C response process for ACK from slave
    p_i2c: process is
    begin
        io(2) <= 'H';
        for i in 0 to 8 loop
            wait for clock_period;
            wait until io(3) = '0';
        end loop;
        io(2) <= '0';
        wait;
    end process;

    -- Decode what is sent to the system over UART, for debug.
    p_2: process is
        variable buf: std_logic_vector(7 downto 0);
    begin
        wait for clock_period;
        wait until reset_n = '1';

        loop
            wait until rx = '0';
            wait for bit_period;
            for i in 0 to 7 loop
                wait for bit_period / 2;
                buf(i) := rx;
                wait for bit_period / 2;
            end loop;
            debug_rx <= (others => 'X');
            wait for bit_period / 2;
            debug_rx <= unsigned(buf);
        end loop;
    end process;

end;
