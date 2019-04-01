#!/usr/bin/python3
#
# This file is part of Scaffold
#
# Scaffold is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#
# Copyright 2019 Ledger SAS, written by Olivier Hériveaux

set_time_format -unit ns
create_clock -name {clock} -period 40 -waveform {0 20} [get_ports {clock}]
create_generated_clock -name {pll_output_clock} -source [get_pins {e_pll|altpll_component|auto_generated|pll1|inclk[0]}] -duty_cycle 50 -multiply_by 4 -master_clock {clock} [get_pins {e_pll|altpll_component|auto_generated|pll1|clk[0]}]
