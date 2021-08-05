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
-- Copyright 2021 Ledger SAS, written by Olivier Hériveaux


library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;


--
-- SPI slave peripheral to replay SPI slave frames.
--
entity spi_slave is
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Data to be transmitted to the master.
    miso_data: in std_logic_vector(7 downto 0);
    -- High when shift-register is empty, meaning it can be reloaded.
    empty: out std_logic;
    -- High to load miso_data into the slave shift-register.
    load: in std_logic;
    -- Phase and polarity configuration bits
    pha: in std_logic;
    pol: in std_logic;
    -- SPI bus signal
    sck: in std_logic;
    miso: out std_logic;
    ss: in std_logic );
end;


architecture behavior of spi_slave is
    -- Number of bits loaded in the shift-register. Value stored as a one-hot
    -- register.
    -- 100000000: 8 bits stored
    -- 000000010: 1 bit stored
    -- 000000001: 0 bits stored
    signal bit_counter: std_logic_vector(8 downto 0);
    -- Shift register
    -- We have one extra bit for handling the SPI phase correctly.
    signal shiftreg: std_logic_vector(8 downto 0);
    -- Previous state of the clock, used to detect edges
    signal sck_z: std_logic;
    -- High on clock first edge (rising edge if pol=0, falling edge if pol=1)
    signal sck_e1: std_logic;
    -- High on clock second edge (falling edge if pol=0, rising edge if pol=1)
    signal sck_e2: std_logic;
    -- High when shift register must be shifted
    signal shift: std_logic;
begin
    p_sck: process(clock, reset_n) is
    begin
        if reset_n = '0' then
            sck_z <= '0';
        elsif rising_edge(clock) then
            sck_z <= sck;
        end if;
    end process;

    -- Detect clock edges
    sck_e1 <= (not (sck_z xor pol)) and (sck xor pol);
    sck_e2 <= (sck_z xor pol) and (not (sck xor pol));

    -- Shift on first or second sck edge depending on SPI phase
    -- Don't shift when chip select is high
    shift <= (not ss) and ((sck_e1 and pha) or (sck_e2 and (not pha)));

    p_0: process(clock, reset_n) is
    begin
        if reset_n = '0' then
            shiftreg <= (others => '0');
            bit_counter <= "000000001";
        elsif rising_edge(clock) then
            if load = '1' then
                if pha = '0' then
                    shiftreg <= miso_data & '0';
                else
                    shiftreg <= shiftreg(shiftreg'high) & miso_data;
                end if;
                bit_counter <= "100000000";
            else
                if shift = '1' then
                    shiftreg <= shiftreg(7 downto 0) & '0';
                    if bit_counter(0) = '0' then
                        bit_counter <= '0' & bit_counter(8 downto 1);
                    else
                        bit_counter <= bit_counter;
                    end if;
                else
                    shiftreg <= shiftreg;
                    bit_counter <= bit_counter;
                end if;
            end if;
        end if;
    end process;

    miso <= shiftreg(shiftreg'high);  -- Transmission is MSB first
    empty <= bit_counter(0);
end;
