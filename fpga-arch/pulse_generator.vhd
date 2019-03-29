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


--
-- Programmable delay and pulse generator.
--
entity pulse_generator is
port (
    -- System clock.
    clock: in std_logic;
    -- System reset, active low.
    reset_n: in std_logic;
    -- Delay value before pulse.
    delay: in std_logic_vector(23 downto 0);
    -- Delay value after pulse, before next one.
    interval: in std_logic_vector(23 downto 0);
    -- Pulse width.
    width: in std_logic_vector(23 downto 0);
    -- Number of pulses.
    count: in std_logic_vector(15 downto 0);
    -- When high (and in idle state), start pulse generation.
    start: in std_logic;
    -- Pulse polarity. '1' for negative pulse.
    polarity: in std_logic;
    -- Output signal.
    output: out std_logic;
    -- High when pulse generator is in idle state.
    ready: out std_logic );
end;


architecture behavior of pulse_generator is
    -- FSM states
    type state_t is (st_idle, st_delay, st_pulse, st_interval);
    -- Previous value of start bit, for pulse detection.
    signal start_z: std_logic;
    -- High during one clock cycle when a rising edge has been detected.
    signal start_rising_edge: std_logic;
    -- Value of the delay, fetched when start is asserted.
    signal interval_fetch: std_logic_vector(23 downto 0);
    -- Value of pulse width, fetched when start is asserted.
    signal width_fetch: std_logic_vector(23 downto 0);
    -- Polarity, fetched when start is asserted.
    signal polarity_fetch: std_logic;
    -- Current FSM state
    signal state: state_t;
    -- Counter for delays
    signal delay_counter: std_logic_vector(23 downto 0);
    signal delay_counter_en: std_logic;
    signal delay_counter_data: std_logic_vector(23 downto 0);
    signal delay_counter_load: std_logic;
    signal delay_counter_zero: std_logic;
    -- Counter for pulses.
    signal pulse_counter: unsigned(15 downto 0);
begin

    p_start: process (clock, reset_n)
    begin
        if reset_n = '0' then
            start_z <= '1';
        elsif rising_edge(clock) then
            start_z <= start;
        end if;
    end process;

    start_rising_edge <= start and (not start_z);

    -- FSM
    p_state: process (clock, reset_n)
    begin
        if reset_n = '0' then
            state <= st_idle;
        elsif rising_edge(clock) then
            case state is
                -- Waiting for start.
                when st_idle =>
                    if start_rising_edge = '1' then
                        state <= st_delay;
                    else
                        state <= st_idle;
                    end if;

                -- Delay before pulse.
                when st_delay =>
                    if delay_counter_zero = '1' then
                        state <= st_pulse;
                    else
                        state <= st_delay;
                    end if;

                -- Pulse generation.
                when st_pulse =>
                    if delay_counter_zero = '1' then
                        if pulse_counter = 0 then
                            state <= st_idle;
                        else
                            state <= st_interval;
                        end if;
                    else
                        state <= st_pulse;
                    end if;

                -- Second delay before next pulse.
                when st_interval =>
                    if delay_counter_zero = '1' then
                        state <= st_pulse;
                    else
                        state <= st_interval;
                    end if;
            end case;
        end if;
    end process;

    -- Fetch interval value when start is asserted.
    p_fetch: process (clock, reset_n)
    begin
        if reset_n = '0' then
            interval_fetch <= (others => '0');
        elsif rising_edge(clock) then
            case state is
                when st_idle =>
                    interval_fetch <= interval;
                    width_fetch <= width;
                    polarity_fetch <= polarity;
                when others =>
                    interval_fetch <= interval_fetch;
                    width_fetch <= width_fetch;
                    polarity_fetch <= polarity_fetch;
            end case;
        end if;
    end process;

    -- Counters loading and counting
    e_counter: entity work.lpm_down_counter_24
    port map (
        aclr => not reset_n,
        clock => clock,
        cnt_en => delay_counter_en,
        data => delay_counter_data,
        sload => delay_counter_load,
        q => delay_counter );

    delay_counter_en <= '1';
    delay_counter_zero <= '1' when unsigned(delay_counter) = 0 else '0';

    p_delay_counter: process (state, delay, width_fetch, delay_counter_zero,
        interval_fetch)
    begin
        case state is
            when st_idle =>
                delay_counter_data <= delay;
                delay_counter_load <= '1';

            when st_delay =>
                delay_counter_data <= width_fetch;
                delay_counter_load <= delay_counter_zero;

            when st_pulse =>
                delay_counter_data <= interval_fetch;
                delay_counter_load <= delay_counter_zero;

            when st_interval =>
                delay_counter_data <= width_fetch;
                delay_counter_load <= delay_counter_zero;
        end case;
    end process;

    p_pulse_counter: process (clock, reset_n)
    begin
        if reset_n = '0' then
            pulse_counter <= (others => '0');
        elsif rising_edge(clock) then
            case state is
                when st_idle =>
                    pulse_counter <= unsigned(count);

                when st_delay =>
                    pulse_counter <= pulse_counter;

                when st_pulse =>
                    if delay_counter_zero = '1' then
                        pulse_counter <= pulse_counter - 1;
                    else
                        pulse_counter <= pulse_counter;
                    end if;

                when st_interval =>
                    pulse_counter <= pulse_counter;
            end case;
        end if;
    end process;

    -- Register the output to prevent any glitch, at the cost of one clock cycle
    -- delay.
    p_output: process (clock, reset_n)
    begin
        if reset_n = '0' then
            output <= '0';
        elsif rising_edge(clock) then
            case state is
                when st_pulse =>
                    output <= not polarity_fetch;
                when others =>
                    output <= polarity_fetch;
            end case;
        end if;
    end process;

    -- Ready signal. Not registered.
    ready <= '1' when state = st_idle else '0';

end;
