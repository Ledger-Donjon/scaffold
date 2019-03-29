Output module
=============

The available I/Os of the scaffold board can be internally connected to any
module output. The "right matrix" controls which module output signals are
connected to which I/Os. Each I/O has a register storing its multiplexer
selecting the source signal.


Multiplexers selection table
----------------------------

+-------+-------------------------+
| Index | Signal name             |
+=======+=========================+
| 0     | z                       |
+-------+-------------------------+
| 1     | 0                       |
+-------+-------------------------+
| 2     | 1                       |
+-------+-------------------------+
| 3     | /power/dut_trigger      |
+-------+-------------------------+
| 4     | /power/platform_trigger |
+-------+-------------------------+
| 5     | /uart0/tx               |
+-------+-------------------------+
| 6     | /uart0/trigger          |
+-------+-------------------------+
| 7     | /uart1/tx               |
+-------+-------------------------+
| 8     | /uart1/trigger          |
+-------+-------------------------+
| 9     | /iso7816/io_out         |
+-------+-------------------------+
| 10    | /iso7816/clk            |
+-------+-------------------------+
| 11    | /iso7816/trigger        |
+-------+-------------------------+
| 12    | /pgen0/out              |
+-------+-------------------------+
| 13    | /pgen1/out              |
+-------+-------------------------+
| 14    | /pgen2/out              |
+-------+-------------------------+
| 15    | /pgen3/out              |
+-------+-------------------------+
       
