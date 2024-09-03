// This file is part of Scaffold
//
// Scaffold is free software: you can redistribute it and/or modify
// it under the terms of the GNU Lesser General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Lesser General Public License for more details.
//
// You should have received a copy of the GNU Lesser General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.
//
//
// Copyright 2024 Ledger SAS, written by Charles Christen

package Prescaler;

import Counter::*;

(* always_enabled *)
interface Prescaler#(numeric type n);
    method Bool rising;
    method Bool falling;
    method Bool pre_rising;
endinterface

module mkPrescaler (Prescaler#(prescale))
    provisos (
        Mul#(__a, 2, prescale),
        Add#(ctr_max, 1, prescale),
        Log#(ctr_max, __b),
        Add#(__b, 1, ctr_sz)
    );

    Counter#(ctr_sz) ctr <- mkCounter(fromInteger(valueof(ctr_max)));

    (* fire_when_enabled, no_implicit_conditions *)
    rule count_dow(ctr.value > 0);
        ctr.down();
    endrule

   (* fire_when_enabled, no_implicit_conditions *)
   rule reset_count(ctr.value == 0);
      ctr.setF(fromInteger(valueof(ctr_max)));
   endrule

    method rising = (ctr.value == 0);
    method pre_rising = (ctr.value == 1);
    method falling = (ctr.value == fromInteger(valueof(__a)));

endmodule

endpackage
