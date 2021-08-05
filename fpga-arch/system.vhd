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
-- Main architecture file.
--


library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.common_pkg.all;


entity system is
generic (
    -- Frequency of the system clock. Used for baudrate calculations.
    system_frequency: positive;
    -- Number of programmables IOs.
    io_count: positive;
    -- Number of UART modules.
    uart_count: positive := 2;
    -- Number of pulse generators.
    pulse_gen_count: positive := 4;
    -- Number of chain trigger module
    chain_count: positive := 2;
    -- Size of the chain trigger modules (number of event inputs)
    chain_size: positive := 3 );
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- UART communication to control the device
    rx: in std_logic;
    tx: out std_logic;
    -- TLC5927 LEDs driver control signals.
    leds_sin: out std_logic;
    leds_sclk: out std_logic;
    leds_lat: out std_logic;
    leds_blank: out std_logic;
    -- Programmable IO signals.
    io: inout std_logic_vector(io_count-1 downto 0);
    pull: out std_logic_vector(io_count-1 downto 0);
    -- Teardown input.
    -- Power-off the devices when high.
    -- This signal is asynchronous and can be connected directly to an input.
    teardown_async: in std_logic;
    -- Power control outputs
    power_dut: out std_logic;
    power_platform: out std_logic;
    -- Debug signals
    debug: out std_logic_vector(3 downto 0) );
end;


architecture behavior of system is
    --
    -- System architecture has three main blocks: the left matrix, the modules
    -- and the right matrix.
    --
    -- Board signals come from the 'left' and enter the left matrix. This matrix
    -- redirects the signals to the inputs of the modules. The outputs of the
    -- modules are then fed to the 'right' matrix. The right matrix redirects
    -- these signals to the board outputs.
    --
    -- Modules are all connected to a global system bus, exposing their
    -- registers to read and write operations. UART, SPI, pulse generators are
    -- some examples of the available modules.
    --
    --                                              +------+   +-----+
    --                         high impedance Z --->|      |-->|     |-----> io0
    --                                        0 --->|      |-->|     |-----> io1
    --                                        1 --->|      |-->|     |-----> io2
    --                                              |      |   |     |
    --         +----+   +------+    +----------+    |      |   |     |   .
    --   0 --->|    |-->|      |--->|          |--->|      |-->|     |   .
    --   1 --->|    |-->|      |--->| Module 1 |--->|      |-->|     |   .
    -- io0 --->|    |-->|      |    |          |--->|      |-->|     |   .
    -- io1 --->|    |-->|      |    +----------+    |      |   |     |   .
    -- io2 --->|    |-->|      |    +----------+    |      |   |     |   .
    --         |    |   |      |--->|          |--->|      |   |     |   .
    --      .  |    |   |      |    | Module 2 |--->|      |   |     |   .
    --      .  |    |   |      |    |          |    |      |   |     |
    --      .  | In |   | MTXL |    +----------+    | MTXR |-->| Out |-----> ion
    --         |    |   |      |                    |      |   |     |
    -- ion --->|    |-->|      |         .          |      |   |     |
    --         |    |   |      |         .          |      |   |     |
    --         |    |   |      |         .          |      |   |     |
    --         |    |   |      |                    |      |   |     |
    --         |    |   |      |    +----------+    |      |   |     |
    --         |    |   |      |--->|          |----|      |   |     |
    --         |    |   |      |--->| Module N |    |      |   |     |
    --         |    |   |      |    |          |    |      |   |     |
    --         +----+   +------+    +----------+    +------+   +-----+

    -- Function for easier address decoding.
    function addr_en (
        bus_in: bus_in_t;
        address: std_logic_vector(15 downto 0) )
    return std_logic is
    begin
        if address = bus_in.address then
            return '1';
        else
            return '0';
        end if;
    end;

    -- Function for multiple addresses decoding.
    function addr_en_loop (
        bus_in: bus_in_t;
        base_address: address_t;
        offset: address_t;
        n: positive )
    return std_logic_vector is
        variable result: std_logic_vector(n-1 downto 0);
        variable address: address_t;
    begin
        address := base_address;
        for i in 0 to n-1 loop
            result(i) := addr_en(bus_in, address);
            address := std_logic_vector(unsigned(address) + unsigned(offset));
        end loop;
        return result;
    end;

    -- Registered input signals
    signal in_reg: std_logic_vector(io_count-1 downto 0);

    -- Left matrix inputs.
    -- '0', '1' board I/Os and module feedback signals (mostly triggers).
    constant mtxl_in_count: positive := 2 + io_count
        + uart_count -- UART trigger
        + 1 -- ISO7816 trigger
        + 1 -- I2C trigger
        + 1 -- SPI trigger
        + pulse_gen_count -- Pulse generator outputs
        + chain_count; -- Chain trigger
    signal mtxl_in: std_logic_vector(mtxl_in_count-1 downto 0);

    -- Left matrix outputs. Inputs of modules.
    constant mtxl_out_count: positive := uart_count + pulse_gen_count
        + (chain_count * chain_size) -- Chain modules
        + 1 -- ISO7816 module
        + 2 -- I2C
        + 1 -- SPI
        + 2 -- SPI slave
        + 1; -- Clock
    signal mtxl_out: std_logic_vector(mtxl_out_count-1 downto 0);
    signal mtxl_out_uart_rx: std_logic_vector(uart_count-1 downto 0);
    signal mtxl_out_pulse_gen_start: std_logic_vector(pulse_gen_count-1 downto 0);
    signal mtxl_out_iso7816_io_in: std_logic;
    signal mtxl_out_i2c_sda_in: std_logic;
    signal mtxl_out_i2c_scl_in: std_logic;
    signal mtxl_out_spi_miso: std_logic;
    signal mtxl_out_spi_slave_sck: std_logic;
    signal mtxl_out_spi_slave_ss: std_logic;
    signal mtxl_out_clock_glitch_start: std_logic;
    signal mtxl_out_chain_events:
        std_logic_vector_array_t(chain_count-1 downto 0)(chain_size-1 downto 0);

    -- Right matrix inputs. Output of modules.
    -- Each output wire has two signals: a value and an output enable.
    constant mtxr_in_count: positive := 3 -- +3 for Z, 0 and 1 signals
        + (uart_count * 2) + pulse_gen_count + chain_count
        + 3 -- ISO7816 module
        + 2 -- Power signals
        + 3 -- I2C module
        + 4 -- SPI module
        + 1 -- SPI slave module
        + 1; -- Clock
    signal mtxr_in: tristate_array_t(mtxr_in_count-1 downto 0);
    signal mtxr_in_uart_tx: std_logic_vector(uart_count-1 downto 0);
    signal mtxr_in_uart_trigger: std_logic_vector(uart_count-1 downto 0);
    signal mtxr_in_pulse_gen_out: std_logic_vector(pulse_gen_count-1 downto 0);
    signal mtxr_in_iso7816_io_out: std_logic;
    signal mtxr_in_iso7816_io_oe: std_logic;
    signal mtxr_in_iso7816_clk: std_logic;
    signal mtxr_in_iso7816_trigger: std_logic;
    signal mtxr_in_i2c_sda: std_logic;
    signal mtxr_in_i2c_scl: std_logic;
    signal mtxr_in_i2c_scl_en: std_logic;
    signal mtxr_in_i2c_trigger: std_logic;
    signal mtxr_in_spi_sck: std_logic;
    signal mtxr_in_spi_mosi: std_logic;
    signal mtxr_in_spi_ss: std_logic;
    signal mtxr_in_spi_trigger: std_logic;
    signal mtxr_in_spi_slave_miso: std_logic;
    signal mtxr_in_clock_out: std_logic;
    signal mtxr_in_chain_out: std_logic_vector(chain_count-1 downto 0);

    -- Output signals of the output matrix
    constant mtxr_out_count: positive := io_count;
    signal mtxr_out: tristate_array_t(mtxr_out_count-1 downto 0);

    -- Bus signals
    signal bus_in: bus_in_t;
    signal bus_out: bus_out_t;
    signal bus_err: std_logic;

    -- Register addresses
    constant addr_version_data: address_t := x"0100";
    constant addr_leds_control: address_t := x"0200";
    constant addr_leds_brightness: address_t := x"0201";
    constant addr_leds_leds_0: address_t := x"0202";
    constant addr_leds_leds_1: address_t := x"0203";
    constant addr_leds_leds_2: address_t := x"0204";
    constant addr_leds_mode: address_t := x"0205";
    constant addr_pulse_gen_status: address_t := x"0300";
    constant addr_pulse_gen_control: address_t := x"0301";
    constant addr_pulse_gen_config: address_t := x"0302";
    constant addr_pulse_gen_delay: address_t := x"0303";
    constant addr_pulse_gen_interval: address_t := x"0304";
    constant addr_pulse_gen_width: address_t := x"0305";
    constant addr_pulse_gen_count: address_t := x"0306";
    constant addr_uart_status: address_t := x"0400";
    constant addr_uart_control: address_t := x"0401";
    constant addr_uart_config: address_t := x"0402";
    constant addr_uart_divisor: address_t := x"0403";
    constant addr_uart_data: address_t := x"0404";
    constant addr_iso7816_status: address_t := x"0500";
    constant addr_iso7816_control: address_t := x"0501";
    constant addr_iso7816_config: address_t := x"0502";
    constant addr_iso7816_divisor: address_t := x"0503";
    constant addr_iso7816_etu: address_t := x"0504";
    constant addr_iso7816_data: address_t := x"0505";
    constant addr_power_control: address_t := x"0600";
    constant addr_i2c_status: address_t := x"0700";
    constant addr_i2c_control: address_t := x"0701";
    constant addr_i2c_config: address_t := x"0702";
    constant addr_i2c_divisor: address_t := x"0703";
    constant addr_i2c_data: address_t := x"0704";
    constant addr_i2c_size_h: address_t := x"0705";
    constant addr_i2c_size_l: address_t := x"0706";
    constant addr_spi_status: address_t := x"0800";
    constant addr_spi_control: address_t := x"0801";
    constant addr_spi_config: address_t := x"0802";
    constant addr_spi_divisor: address_t := x"0803";
    constant addr_spi_data: address_t := x"0804";
    constant addr_chain_base: address_t := x"0900";
    constant addr_clock_config: address_t := x"0a00";
    constant addr_clock_divisor_a: address_t := x"0a01";
    constant addr_clock_divisor_b: address_t := x"0a02";
    constant addr_clock_count: address_t := x"0a03";
    constant addr_io_value_base: address_t := x"e000";
    constant addr_io_config_base: address_t := x"e001";
    constant addr_mtxl_base: address_t := x"f000";
    constant addr_mtxr_base: address_t := x"f100";

    -- Address decoding
    signal en_version_data: std_logic;
    signal en_leds_control: std_logic;
    signal en_leds_brightness: std_logic;
    signal en_leds_leds_0: std_logic;
    signal en_leds_leds_1: std_logic;
    signal en_leds_leds_2: std_logic;
    signal en_leds_mode: std_logic;
    signal en_pulse_gen_status: std_logic_vector(pulse_gen_count-1 downto 0);
    signal en_pulse_gen_control: std_logic_vector(pulse_gen_count-1 downto 0);
    signal en_pulse_gen_config: std_logic_vector(pulse_gen_count-1 downto 0);
    signal en_pulse_gen_delay: std_logic_vector(pulse_gen_count-1 downto 0);
    signal en_pulse_gen_interval: std_logic_vector(pulse_gen_count-1 downto 0);
    signal en_pulse_gen_width: std_logic_vector(pulse_gen_count-1 downto 0);
    signal en_pulse_gen_count: std_logic_vector(pulse_gen_count-1 downto 0);
    signal en_uart_status: std_logic_vector(uart_count-1 downto 0);
    signal en_uart_config: std_logic_vector(uart_count-1 downto 0);
    signal en_uart_control: std_logic_vector(uart_count-1 downto 0);
    signal en_uart_divisor: std_logic_vector(uart_count-1 downto 0);
    signal en_uart_data: std_logic_vector(uart_count-1 downto 0);
    signal en_iso7816_status: std_logic;
    signal en_iso7816_control: std_logic;
    signal en_iso7816_config: std_logic;
    signal en_iso7816_divisor: std_logic;
    signal en_iso7816_etu: std_logic;
    signal en_iso7816_data: std_logic;
    signal en_power_control: std_logic;
    signal en_i2c_status: std_logic;
    signal en_i2c_control: std_logic;
    signal en_i2c_config: std_logic;
    signal en_i2c_divisor: std_logic;
    signal en_i2c_data: std_logic;
    signal en_i2c_size_h: std_logic;
    signal en_i2c_size_l: std_logic;
    signal en_spi_status: std_logic;
    signal en_spi_control: std_logic;
    signal en_spi_config: std_logic;
    signal en_spi_divisor: std_logic;
    signal en_spi_data: std_logic;
    signal en_chain_control: std_logic_vector(chain_count-1 downto 0);
    signal en_clock_config: std_logic;
    signal en_clock_divisor_a: std_logic;
    signal en_clock_divisor_b: std_logic;
    signal en_clock_count: std_logic;
    signal en_io_value: std_logic_vector(io_count-1 downto 0);
    signal en_io_config: std_logic_vector(io_count-1 downto 0);
    signal en_mtxl_sel: std_logic_vector(mtxl_out_count-1 downto 0);
    signal en_mtxr_sel: std_logic_vector(mtxr_out_count-1 downto 0);

    -- Modules output registers
    -- These are the registers which are mapped to addresses and can be read by
    -- the host
    constant read_register_count: positive :=
        io_count -- I/Os
        + 1 -- Version
        + (2 * uart_count) -- UART
        + pulse_gen_count -- Pulse generators
        + 1 -- Power control
        + 2 -- ISO7816 status and data
        + 4 -- I2C
        + 2; -- SPI
    signal reg_io_value: std_logic_vector_array_t(io_count-1 downto 0)
        (7 downto 0);
    signal reg_version_data: byte_t;
    signal reg_uart_data, reg_uart_status:
        std_logic_vector_array_t(uart_count-1 downto 0)(7 downto 0);
    signal reg_pulse_gen_status:
        std_logic_vector_array_t(pulse_gen_count-1 downto 0)(7 downto 0);
    signal reg_iso7816_status, reg_iso7816_data: byte_t;
    signal reg_power_control: byte_t;
    signal reg_i2c_status, reg_i2c_data, reg_i2c_size_h, reg_i2c_size_l: byte_t;
    signal reg_spi_status, reg_spi_data: byte_t;

    -- State of the LEDs (when override is disabled in LEDs module).
    signal leds: std_logic_vector(23 downto 0);
    signal leds_blink_mask: std_logic_vector(23 downto 0);
    signal led_error: std_logic;
    signal led_power_dut_green: std_logic;
    signal led_power_dut_red: std_logic;
    signal led_power_platform_green: std_logic;
    signal led_power_platform_red: std_logic;
    signal leds_tabc: std_logic_vector(12 downto 0);
    signal led_tearing: std_logic;
    signal led_a0: std_logic;
    signal led_a1: std_logic;
    signal led_a2: std_logic;
    signal led_a3: std_logic;
    signal led_d0: std_logic;
    signal led_d1: std_logic;
    signal led_d2: std_logic;
    signal led_d3: std_logic;
    signal led_d4: std_logic;
    signal led_d5: std_logic;
    signal leds_debug: std_logic_vector(7 downto 0);

    -- Power signals
    signal power_async, power_sync: std_logic_vector(1 downto 0);

begin
    -- Bridge between the internal FPGA bus connecting all the peripherals, and
    -- the host computer.
    e_bus_bridge: entity work.bus_bridge
    generic map (
        system_frequency => system_frequency,
        baudrate => 2000000 )
    port map (
        clock => clock,
        reset_n => reset_n,
        uart_tx => tx,
        uart_rx => rx,
        bus_in => bus_in,
        bus_out => bus_out,
        err => bus_err );

    -- Address decoding
    en_version_data <= addr_en(bus_in, addr_version_data);
    en_leds_control <= addr_en(bus_in, addr_leds_control);
    en_leds_brightness <= addr_en(bus_in, addr_leds_brightness);
    en_leds_leds_0 <= addr_en(bus_in, addr_leds_leds_0);
    en_leds_leds_1 <= addr_en(bus_in, addr_leds_leds_1);
    en_leds_leds_2 <= addr_en(bus_in, addr_leds_leds_2);
    en_leds_mode <= addr_en(bus_in, addr_leds_mode);
    en_uart_status <=
        addr_en_loop(bus_in, addr_uart_status, x"0010", uart_count);
    en_uart_control <=
        addr_en_loop(bus_in, addr_uart_control, x"0010", uart_count);
    en_uart_config <=
        addr_en_loop(bus_in, addr_uart_config, x"0010", uart_count);
    en_uart_divisor <=
        addr_en_loop(bus_in, addr_uart_divisor, x"0010", uart_count);
    en_uart_data <=
        addr_en_loop(bus_in, addr_uart_data, x"0010", uart_count);
    en_pulse_gen_status <=
        addr_en_loop(bus_in, addr_pulse_gen_status, x"0010", pulse_gen_count);
    en_pulse_gen_control <=
        addr_en_loop(bus_in, addr_pulse_gen_control, x"0010", pulse_gen_count);
    en_pulse_gen_config <=
        addr_en_loop(bus_in, addr_pulse_gen_config, x"0010", pulse_gen_count);
    en_pulse_gen_delay <=
        addr_en_loop(bus_in, addr_pulse_gen_delay, x"0010", pulse_gen_count);
    en_pulse_gen_interval <=
        addr_en_loop(bus_in, addr_pulse_gen_interval, x"0010", pulse_gen_count);
    en_pulse_gen_width <= addr_en_loop(bus_in, addr_pulse_gen_width, x"0010",
        pulse_gen_count);
    en_pulse_gen_count <= addr_en_loop(bus_in, addr_pulse_gen_count, x"0010",
        pulse_gen_count);
    en_iso7816_status <= addr_en(bus_in, addr_iso7816_status);
    en_iso7816_control <= addr_en(bus_in, addr_iso7816_control);
    en_iso7816_config <= addr_en(bus_in, addr_iso7816_config);
    en_iso7816_divisor <= addr_en(bus_in, addr_iso7816_divisor);
    en_iso7816_etu <= addr_en(bus_in, addr_iso7816_etu);
    en_iso7816_data <= addr_en(bus_in, addr_iso7816_data);
    en_power_control <= addr_en(bus_in, addr_power_control);
    en_i2c_status <= addr_en(bus_in, addr_i2c_status);
    en_i2c_control <= addr_en(bus_in, addr_i2c_control);
    en_i2c_config <= addr_en(bus_in, addr_i2c_config);
    en_i2c_divisor <= addr_en(bus_in, addr_i2c_divisor);
    en_i2c_data <= addr_en(bus_in, addr_i2c_data);
    en_i2c_size_h <= addr_en(bus_in, addr_i2c_size_h);
    en_i2c_size_l <= addr_en(bus_in, addr_i2c_size_l);
    en_spi_status <= addr_en(bus_in, addr_spi_status);
    en_spi_control <= addr_en(bus_in, addr_spi_control);
    en_spi_config <= addr_en(bus_in, addr_spi_config);
    en_spi_divisor <= addr_en(bus_in, addr_spi_divisor);
    en_spi_data <= addr_en(bus_in, addr_spi_data);
    en_chain_control <=
        addr_en_loop(bus_in, addr_chain_base, x"0010", chain_count);
    en_clock_config <= addr_en(bus_in, addr_clock_config);
    en_clock_divisor_a <= addr_en(bus_in, addr_clock_divisor_a);
    en_clock_divisor_b <= addr_en(bus_in, addr_clock_divisor_b);
    en_clock_count <= addr_en(bus_in, addr_clock_count);
    en_io_value <= addr_en_loop(bus_in, addr_io_value_base, x"0010", io_count);
    en_io_config <=
        addr_en_loop(bus_in, addr_io_config_base, x"0010", io_count);
    en_mtxl_sel <=
        addr_en_loop(bus_in, addr_mtxl_base, x"0001", mtxl_out_count);
    en_mtxr_sel <=
        addr_en_loop(bus_in, addr_mtxr_base, x"0001", mtxr_out_count);

    -- Put on bus_out.read_data the correct register value depending on address
    -- selection signals. This is basically a big one-hot multiplexer.
    e_address_decoder: entity work.address_decoder
    generic map (n => read_register_count)
    port map (
        values =>
            reg_io_value &
            reg_pulse_gen_status &
            reg_uart_data &
            reg_uart_status &
            reg_version_data &
            reg_power_control &
            reg_i2c_status &
            reg_i2c_data &
            reg_i2c_size_h &
            reg_i2c_size_l &
            reg_iso7816_status &
            reg_iso7816_data &
            reg_spi_status &
            reg_spi_data,
        enables =>
            en_io_value &
            en_pulse_gen_status &
            en_uart_data &
            en_uart_status &
            en_version_data &
            en_power_control &
            en_i2c_status &
            en_i2c_data &
            en_i2c_size_h &
            en_i2c_size_l &
            en_iso7816_status &
            en_iso7816_data &
            en_spi_status &
            en_spi_data,
        value => bus_out.read_data );

    -- I/O modules
    -- A0 to A3
    -- Those first module are output only, so the initial value of the IO
    -- configuration register sets the mode to "Push-Pull always". This forces
    -- the outputs to be 0 when the board is powered-up or reset.
    g_io_module_a0_to_a3: for i in 0 to 3 generate
        e_io_module: entity work.io_module
        generic map (config_reset => x"03")
        port map (
            clock => clock,
            reset_n => reset_n,
            bus_in => bus_in,
            en_value => en_io_value(i),
            en_config => en_io_config(i),
            reg_value => reg_io_value(i),
            pin => io(i),
            pull_pin => pull(i),
            pin_out_en => mtxr_out(i)(1),
            pin_out => mtxr_out(i)(0),
            pin_in_reg => in_reg(i) );
    end generate;

    -- All other I/O modules
    g_io_module_others: for i in 4 to io_count-1 generate
        e_io_module: entity work.io_module
        port map (
            clock => clock,
            reset_n => reset_n,
            bus_in => bus_in,
            en_value => en_io_value(i),
            en_config => en_io_config(i),
            reg_value => reg_io_value(i),
            pin => io(i),
            pull_pin => pull(i),
            pin_out_en => mtxr_out(i)(1),
            pin_out => mtxr_out(i)(0),
            pin_in_reg => in_reg(i) );
    end generate;

    -- Version module
    e_version_module: entity work.version_module
    generic map (version => "scaffold-0.8")
    port map (
        clock => clock,
        reset_n => reset_n,
        bus_in => bus_in,
        en_data => en_version_data,
        reg_data => reg_version_data );

    -- LEDs driver module
    e_leds_module: entity work.leds_module
    port map (
        clock => clock,
        reset_n => reset_n,
        bus_in => bus_in,
        en_control => en_leds_control,
        en_brightness => en_leds_brightness,
        en_mode => en_leds_mode,
        en_leds_0 => en_leds_leds_0,
        en_leds_1 => en_leds_leds_1,
        en_leds_2 => en_leds_leds_2,
        leds => leds,
        blink_mask => leds_blink_mask,
        leds_sin => leds_sin,
        leds_sclk => leds_sclk,
        leds_lat => leds_lat,
        leds_blank => leds_blank );

    -- UART modules
    g_uart_module: for i in 0 to uart_count-1 generate
        e_uart_module: entity work.uart_module
        port map (
            clock => clock,
            reset_n => reset_n,
            bus_in => bus_in,
            en_status => en_uart_status(i),
            en_control => en_uart_control(i),
            en_config => en_uart_config(i),
            en_divisor => en_uart_divisor(i),
            en_data => en_uart_data(i),
            reg_data => reg_uart_data(i),
            reg_status => reg_uart_status(i),
            tx => mtxr_in_uart_tx(i),
            rx => mtxl_out_uart_rx(i),
            trigger => mtxr_in_uart_trigger(i) );
    end generate;

    -- ISO7816 module.
    e_iso7816_module: entity work.iso7816_module
    port map (
        clock => clock,
        reset_n => reset_n,
        bus_in => bus_in,
        en_status => en_iso7816_status,
        en_control => en_iso7816_control,
        en_config => en_iso7816_config,
        en_divisor => en_iso7816_divisor,
        en_etu => en_iso7816_etu,
        en_data => en_iso7816_data,
        reg_data => reg_iso7816_data,
        reg_status => reg_iso7816_status,
        io_in => mtxl_out_iso7816_io_in,
        io_out => mtxr_in_iso7816_io_out,
        io_oe => mtxr_in_iso7816_io_oe,
        clk => mtxr_in_iso7816_clk,
        trigger => mtxr_in_iso7816_trigger );

    -- SPI module.
    e_spi_module: entity work.spi_module
    port map (
        clock => clock,
        reset_n => reset_n,
        bus_in => bus_in,
        en_status => en_spi_status,
        en_control => en_spi_control,
        en_config => en_spi_config,
        en_divisor => en_spi_divisor,
        en_data => en_spi_data,
        reg_status => reg_spi_status,
        reg_data => reg_spi_data,
        miso_in => mtxl_out_spi_miso,
        sck_out => mtxr_in_spi_sck,
        mosi_out => mtxr_in_spi_mosi,
        ss_out => mtxr_in_spi_ss,
        trigger => mtxr_in_spi_trigger,
        sck_in => mtxl_out_spi_slave_sck,
        ss_in => mtxl_out_spi_slave_ss,
        miso_out => mtxr_in_spi_slave_miso);

    -- Pulse generators
    g_pulse_gen_module: for i in 0 to pulse_gen_count-1 generate
    begin
        e_pulse_gen: entity work.pulse_generator_module
        port map (
            clock => clock,
            reset_n => reset_n,
            bus_in => bus_in,
            en_config => en_pulse_gen_config(i),
            en_control => en_pulse_gen_control(i),
            en_delay => en_pulse_gen_delay(i),
            en_interval => en_pulse_gen_interval(i),
            en_width => en_pulse_gen_width(i),
            en_count => en_pulse_gen_count(i),
            reg_status => reg_pulse_gen_status(i),
            start => mtxl_out_pulse_gen_start(i),
            output => mtxr_in_pulse_gen_out(i) );
    end generate;

    -- Power controllers.
    e_power_module: entity work.power_module
    generic map (n => 2)
    port map (
        clock => clock,
        reset_n => reset_n,
        bus_in => bus_in,
        en_control => en_power_control,
        teardown_async => teardown_async,
        power_async => power_async,
        power_sync => power_sync,
        reg_control => reg_power_control );

    power_dut <= power_async(0);
    power_platform <= power_async(1);

    -- I2C module
    e_i2c: entity work.i2c_module
    port map (
        clock => clock,
        reset_n => reset_n,
        bus_in => bus_in,
        en_status => en_i2c_status,
        en_control => en_i2c_control,
        en_config => en_i2c_config,
        en_divisor => en_i2c_divisor,
        en_data => en_i2c_data,
        en_size_h => en_i2c_size_h,
        en_size_l => en_i2c_size_l,
        reg_status => reg_i2c_status,
        reg_data => reg_i2c_data,
        reg_size_h => reg_i2c_size_h,
        reg_size_l => reg_i2c_size_l,
        sda_in => mtxl_out_i2c_sda_in,
        scl_in => mtxl_out_i2c_scl_in,
        sda_out => mtxr_in_i2c_sda,
        scl_out => mtxr_in_i2c_scl,
        scl_out_en => mtxr_in_i2c_scl_en,
        trigger => mtxr_in_i2c_trigger );

    -- Chain trigger modules
    g_chain_module: for i in 0 to chain_count-1 generate
    begin
        e_chain: entity work.chain_module
        generic map (n => chain_size)
        port map (
            clock => clock,
            reset_n => reset_n,
            bus_in => bus_in,
            en_control => en_chain_control(i),
            events => mtxl_out_chain_events(i),
            chain_out => mtxr_in_chain_out(i) );
    end generate;

    -- Clock module
    e_clock: entity work.clock_module
    port map (
        clock => clock,
        reset_n => reset_n,
        bus_in => bus_in,
        en_config => en_clock_config,
        en_divisor_a => en_clock_divisor_a,
        en_divisor_b => en_clock_divisor_b,
        en_count => en_clock_count,
        output => mtxr_in_clock_out,
        glitch_start => mtxl_out_clock_glitch_start );

    -- Left matrix module
    e_left_matrix_module: entity work.left_matrix_module
    generic map (
        in_count => mtxl_in_count,
        out_count => mtxl_out_count )
    port map (
        clock => clock,
        reset_n => reset_n,
        bus_in => bus_in,
        en_sel => en_mtxl_sel,
        matrix_in => mtxl_in,
        matrix_out => mtxl_out );

    p_mtxl_out: process (mtxl_out)
        variable i: integer;
    begin
        i := 0;
        mtxl_out_uart_rx <= mtxl_out(i+uart_count-1 downto i);
        i := i + uart_count;
        mtxl_out_iso7816_io_in <= mtxl_out(i);
        i := i + 1;
        mtxl_out_pulse_gen_start <= mtxl_out(i+pulse_gen_count-1 downto i);
        i := i + pulse_gen_count;
        mtxl_out_i2c_sda_in <= mtxl_out(i);
        i := i + 1;
        mtxl_out_i2c_scl_in <= mtxl_out(i);
        i := i + 1;
        mtxl_out_spi_miso <= mtxl_out(i);
        i := i + 1;
        mtxl_out_spi_slave_sck <= mtxl_out(i);
        i := i + 1;
        mtxl_out_spi_slave_ss <= mtxl_out(i);
        i := i + 1;
        for j in 0 to chain_count-1 loop
            mtxl_out_chain_events(j) <= mtxl_out(i+chain_size-1 downto i);
            i := i + chain_size;
        end loop;
        mtxl_out_clock_glitch_start <= mtxl_out(i);
        i := i + 1;
        assert i = mtxl_out_count;
    end process;

    -- Left matrix input signals
    -- mtxr signals are feedback outputs of modules.
    -- Warning: signals order is inversed regarding Python API code.
    mtxl_in <=
        mtxr_in_chain_out &
        mtxr_in_pulse_gen_out &
        mtxr_in_spi_trigger &
        mtxr_in_i2c_trigger &
        mtxr_in_iso7816_trigger &
        mtxr_in_uart_trigger &
        in_reg & -- I/Os
        "10";

    -- Right matrix module
    e_right_matrix_module: entity work.right_matrix_module
    generic map (
        in_count => mtxr_in_count,
        out_count => io_count )
    port map (
        clock => clock,
        reset_n => reset_n,
        bus_in => bus_in,
        en_sel => en_mtxr_sel,
        matrix_in => mtxr_in,
        matrix_out => mtxr_out );

    p_mtxr_in: process (
        -- Keep this sensivity list up-to-date when adding new signals !
        -- This is for simulation.
        power_sync,
        mtxr_in_uart_tx,
        mtxr_in_uart_trigger,
        mtxr_in_iso7816_io_out,
        mtxr_in_iso7816_io_oe,
        mtxr_in_iso7816_clk,
        mtxr_in_iso7816_trigger,
        mtxr_in_pulse_gen_out,
        mtxr_in_i2c_sda,
        mtxr_in_i2c_scl_en,
        mtxr_in_i2c_scl,
        mtxr_in_i2c_trigger,
        mtxr_in_spi_sck,
        mtxr_in_spi_mosi,
        mtxr_in_spi_ss,
        mtxr_in_spi_trigger,
        mtxr_in_spi_slave_miso,
        mtxr_in_chain_out,
        mtxr_in_clock_out )
        variable i: integer;
    begin
        mtxr_in(0) <= "00"; -- Z
        mtxr_in(1) <= "10"; -- 0
        mtxr_in(2) <= "11"; -- 1
        mtxr_in(3) <= '1' & power_sync(0);
        mtxr_in(4) <= '1' & power_sync(1);
        i := 5;
        -- UART modules
        for j in 0 to uart_count-1 loop
            mtxr_in(i) <= "1" & mtxr_in_uart_tx(j);
            mtxr_in(i+1) <= "1" & mtxr_in_uart_trigger(j);
            i := i + 2;
        end loop;
        -- ISO7816 module
        mtxr_in(i) <= mtxr_in_iso7816_io_oe & mtxr_in_iso7816_io_out;
        mtxr_in(i+1) <= '1' & mtxr_in_iso7816_clk;
        mtxr_in(i+2) <= '1' & mtxr_in_iso7816_trigger;
        i := i + 3;
        -- Pulse generators
        for j in 0 to pulse_gen_count - 1 loop
            mtxr_in(i) <= "1" & mtxr_in_pulse_gen_out(j);
            i := i + 1;
        end loop;
        -- I2C module
        -- I2C lines have pull-up resistors, SDA and SCL in open-drain.
        mtxr_in(i) <= (not mtxr_in_i2c_sda) & mtxr_in_i2c_sda;
        mtxr_in(i+1) <= mtxr_in_i2c_scl_en & mtxr_in_i2c_scl;
        mtxr_in(i+2) <= '1' & mtxr_in_i2c_trigger;
        i := i + 3;
        -- SPI module
        mtxr_in(i) <= "1" & mtxr_in_spi_sck;
        mtxr_in(i+1) <= "1" & mtxr_in_spi_mosi;
        mtxr_in(i+2) <= "1" & mtxr_in_spi_ss;
        mtxr_in(i+3) <= "1" & mtxr_in_spi_trigger;
        i := i + 4;
        -- SPI slave module
        mtxr_in(i) <= "1" & mtxr_in_spi_slave_miso;
        i := i + 1;
        -- Chain triggers
        for j in 0 to chain_count-1 loop
            mtxr_in(i) <= "1" & mtxr_in_chain_out(j);
            i := i + 1;
        end loop;
        -- Clock module
        mtxr_in(i) <= "1" & mtxr_in_clock_out;
        i := i + 1;
        -- If you add other signals, please dont forget to update the sensivity
        -- list for simulation support.
        assert i = mtxr_in_count;
    end process;

    debug <= "000" & clock;

    led_error <= bus_err;
    led_power_platform_green <= power_sync(1);
    led_power_platform_red <= not power_sync(1);
    led_power_dut_green <= power_sync(0);
    led_power_dut_red <= not power_sync(0);

    led_a0 <= in_reg(0);
    led_a1 <= in_reg(1);
    led_a2 <= in_reg(2);
    led_a3 <= in_reg(3);
    led_d0 <= in_reg(4);
    led_d1 <= in_reg(5);
    led_d2 <= in_reg(6);
    led_d3 <= in_reg(7);
    led_d4 <= in_reg(8);
    led_d5 <= in_reg(9);

    leds <=
        led_power_platform_red &
        led_power_platform_green &
        led_tearing &
        led_error &
        led_power_dut_red &
        led_power_dut_green &
        led_d5 &
        led_d4 &
        led_d3 &
        led_d2 &
        led_d1 &
        led_d0 &
        led_a3 &
        led_a2 &
        led_a1 &
        led_a0 &
        leds_debug(0) &
        leds_debug(1) &
        leds_debug(2) &
        leds_debug(3) &
        leds_debug(4) &
        leds_debug(5) &
        leds_debug(6) &
        leds_debug(7);

    leds_blink_mask <= "000000111111111100000000";

end;
