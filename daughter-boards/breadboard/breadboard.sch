EESchema Schematic File Version 4
LIBS:breadboard-cache
EELAYER 26 0
EELAYER END
$Descr A4 11693 8268
encoding utf-8
Sheet 1 1
Title ""
Date ""
Rev ""
Comp ""
Comment1 ""
Comment2 ""
Comment3 ""
Comment4 ""
$EndDescr
$Comp
L power:GNDA #PWR0103
U 1 1 5BA2E8A1
P 1650 4600
F 0 "#PWR0103" H 1650 4350 50  0001 C CNN
F 1 "GNDA" V 1655 4473 50  0000 R CNN
F 2 "" H 1650 4600 50  0001 C CNN
F 3 "" H 1650 4600 50  0001 C CNN
	1    1650 4600
	1    0    0    -1  
$EndComp
Text Notes 700  4750 0    50   ~ 0
Virtual ground for DUT\ncurrent measurement
$Comp
L power:+3V3 #PWR0104
U 1 1 5BA2EFB7
P 3300 2100
F 0 "#PWR0104" H 3300 1950 50  0001 C CNN
F 1 "+3V3" V 3315 2228 50  0000 L CNN
F 2 "" H 3300 2100 50  0001 C CNN
F 3 "" H 3300 2100 50  0001 C CNN
	1    3300 2100
	1    0    0    -1  
$EndComp
Wire Wire Line
	2600 4000 3300 4000
Text Notes 2800 4200 0    50   ~ 0
DUT power\ncontrolled by the FPGA
$Comp
L mylib:SAMTEC-QSE-020-01-F-D-A P2
U 1 1 5BA30784
P 5300 2150
F 0 "P2" H 5500 2415 50  0000 C CNN
F 1 "SAMTEC-QSE-020-01-F-D-A" H 5500 2324 50  0000 C CNN
F 2 "mykicadlibs:SAMTEC-QSE-020-01-F-D-A" H 5700 650 50  0001 C CNN
F 3 "" H 5700 650 50  0001 C CNN
	1    5300 2150
	1    0    0    -1  
$EndComp
$Comp
L Connector:TestPoint TP1
U 1 1 5BA35025
P 2750 2200
F 0 "TP1" V 2750 2387 50  0000 L CNN
F 1 "TestPoint" H 2808 2229 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 2950 2200 50  0001 C CNN
F 3 "~" H 2950 2200 50  0001 C CNN
	1    2750 2200
	0    1    1    0   
$EndComp
Wire Wire Line
	2600 2200 2750 2200
$Comp
L Connector:TestPoint TP10
U 1 1 5BA35459
P 2750 2400
F 0 "TP10" V 2750 2587 50  0000 L CNN
F 1 "TestPoint" H 2808 2429 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 2950 2400 50  0001 C CNN
F 3 "~" H 2950 2400 50  0001 C CNN
	1    2750 2400
	0    1    1    0   
$EndComp
$Comp
L Connector:TestPoint TP11
U 1 1 5BA35475
P 2750 2600
F 0 "TP11" V 2750 2787 50  0000 L CNN
F 1 "TestPoint" H 2808 2629 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 2950 2600 50  0001 C CNN
F 3 "~" H 2950 2600 50  0001 C CNN
	1    2750 2600
	0    1    1    0   
$EndComp
$Comp
L Connector:TestPoint TP12
U 1 1 5BA35493
P 2750 2800
F 0 "TP12" V 2750 2987 50  0000 L CNN
F 1 "TestPoint" H 2808 2829 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 2950 2800 50  0001 C CNN
F 3 "~" H 2950 2800 50  0001 C CNN
	1    2750 2800
	0    1    1    0   
$EndComp
$Comp
L Connector:TestPoint TP13
U 1 1 5BA354B3
P 2750 3000
F 0 "TP13" V 2750 3187 50  0000 L CNN
F 1 "TestPoint" H 2808 3029 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 2950 3000 50  0001 C CNN
F 3 "~" H 2950 3000 50  0001 C CNN
	1    2750 3000
	0    1    1    0   
$EndComp
Wire Wire Line
	2750 2400 2600 2400
Wire Wire Line
	2750 2600 2600 2600
Wire Wire Line
	2600 2800 2750 2800
Wire Wire Line
	2750 3000 2600 3000
$Comp
L Connector:TestPoint TP14
U 1 1 5BA3560E
P 2750 3200
F 0 "TP14" V 2750 3387 50  0000 L CNN
F 1 "TestPoint" H 2808 3229 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 2950 3200 50  0001 C CNN
F 3 "~" H 2950 3200 50  0001 C CNN
	1    2750 3200
	0    1    1    0   
$EndComp
$Comp
L Connector:TestPoint TP15
U 1 1 5BA35636
P 2750 3400
F 0 "TP15" V 2750 3587 50  0000 L CNN
F 1 "TestPoint" H 2808 3429 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 2950 3400 50  0001 C CNN
F 3 "~" H 2950 3400 50  0001 C CNN
	1    2750 3400
	0    1    1    0   
$EndComp
$Comp
L Connector:TestPoint TP16
U 1 1 5BA35660
P 2750 3600
F 0 "TP16" V 2750 3787 50  0000 L CNN
F 1 "TestPoint" H 2808 3629 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 2950 3600 50  0001 C CNN
F 3 "~" H 2950 3600 50  0001 C CNN
	1    2750 3600
	0    1    1    0   
$EndComp
$Comp
L Connector:TestPoint TP17
U 1 1 5BA3569C
P 2750 3800
F 0 "TP17" V 2750 3987 50  0000 L CNN
F 1 "TestPoint" H 2808 3829 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 2950 3800 50  0001 C CNN
F 3 "~" H 2950 3800 50  0001 C CNN
	1    2750 3800
	0    1    1    0   
$EndComp
Wire Wire Line
	2750 3800 2600 3800
Wire Wire Line
	2600 3600 2750 3600
Wire Wire Line
	2750 3400 2600 3400
Wire Wire Line
	2600 3200 2750 3200
$Comp
L Connector:TestPoint TP2
U 1 1 5BA35D55
P 2050 2400
F 0 "TP2" V 2153 2474 50  0000 C CNN
F 1 "TestPoint" H 2108 2429 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 2250 2400 50  0001 C CNN
F 3 "~" H 2250 2400 50  0001 C CNN
	1    2050 2400
	0    -1   -1   0   
$EndComp
Wire Wire Line
	2050 2400 2200 2400
$Comp
L Connector:TestPoint TP3
U 1 1 5BA35F00
P 2050 2600
F 0 "TP3" V 2153 2674 50  0000 C CNN
F 1 "TestPoint" H 2108 2629 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 2250 2600 50  0001 C CNN
F 3 "~" H 2250 2600 50  0001 C CNN
	1    2050 2600
	0    -1   -1   0   
$EndComp
$Comp
L Connector:TestPoint TP4
U 1 1 5BA35F2E
P 2050 2800
F 0 "TP4" V 2153 2874 50  0000 C CNN
F 1 "TestPoint" H 2108 2829 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 2250 2800 50  0001 C CNN
F 3 "~" H 2250 2800 50  0001 C CNN
	1    2050 2800
	0    -1   -1   0   
$EndComp
$Comp
L Connector:TestPoint TP5
U 1 1 5BA35F5E
P 2050 3000
F 0 "TP5" V 2153 3074 50  0000 C CNN
F 1 "TestPoint" H 2108 3029 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 2250 3000 50  0001 C CNN
F 3 "~" H 2250 3000 50  0001 C CNN
	1    2050 3000
	0    -1   -1   0   
$EndComp
$Comp
L Connector:TestPoint TP6
U 1 1 5BA35F90
P 2050 3200
F 0 "TP6" V 2153 3274 50  0000 C CNN
F 1 "TestPoint" H 2108 3229 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 2250 3200 50  0001 C CNN
F 3 "~" H 2250 3200 50  0001 C CNN
	1    2050 3200
	0    -1   -1   0   
$EndComp
$Comp
L Connector:TestPoint TP7
U 1 1 5BA35FC4
P 2050 3400
F 0 "TP7" V 2153 3474 50  0000 C CNN
F 1 "TestPoint" H 2108 3429 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 2250 3400 50  0001 C CNN
F 3 "~" H 2250 3400 50  0001 C CNN
	1    2050 3400
	0    -1   -1   0   
$EndComp
$Comp
L Connector:TestPoint TP8
U 1 1 5BA35FFA
P 2050 3600
F 0 "TP8" V 2153 3674 50  0000 C CNN
F 1 "TestPoint" H 2108 3629 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 2250 3600 50  0001 C CNN
F 3 "~" H 2250 3600 50  0001 C CNN
	1    2050 3600
	0    -1   -1   0   
$EndComp
$Comp
L Connector:TestPoint TP9
U 1 1 5BA36032
P 2050 3800
F 0 "TP9" V 2153 3874 50  0000 C CNN
F 1 "TestPoint" H 2108 3829 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 2250 3800 50  0001 C CNN
F 3 "~" H 2250 3800 50  0001 C CNN
	1    2050 3800
	0    -1   -1   0   
$EndComp
Wire Wire Line
	2050 3800 2200 3800
Wire Wire Line
	2200 3600 2050 3600
Wire Wire Line
	2050 3400 2200 3400
Wire Wire Line
	2200 3200 2050 3200
Wire Wire Line
	2050 3000 2200 3000
Wire Wire Line
	2200 2800 2050 2800
Wire Wire Line
	2050 2600 2200 2600
Wire Wire Line
	1650 4600 1650 3600
Wire Wire Line
	1650 2200 2200 2200
Wire Wire Line
	2200 4200 2100 4200
$Comp
L Connector:TestPoint TP18
U 1 1 5BA3A935
P 1650 2200
F 0 "TP18" V 1753 2274 50  0000 C CNN
F 1 "TestPoint" H 1708 2229 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 1850 2200 50  0001 C CNN
F 3 "~" H 1850 2200 50  0001 C CNN
	1    1650 2200
	0    -1   -1   0   
$EndComp
Connection ~ 1650 2200
$Comp
L Connector:TestPoint TP19
U 1 1 5BA3A97F
P 1650 2400
F 0 "TP19" V 1753 2474 50  0000 C CNN
F 1 "TestPoint" H 1708 2429 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 1850 2400 50  0001 C CNN
F 3 "~" H 1850 2400 50  0001 C CNN
	1    1650 2400
	0    -1   -1   0   
$EndComp
Connection ~ 1650 2400
Wire Wire Line
	1650 2400 1650 2200
$Comp
L Connector:TestPoint TP20
U 1 1 5BA3A9C5
P 1650 2600
F 0 "TP20" V 1753 2674 50  0000 C CNN
F 1 "TestPoint" H 1708 2629 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 1850 2600 50  0001 C CNN
F 3 "~" H 1850 2600 50  0001 C CNN
	1    1650 2600
	0    -1   -1   0   
$EndComp
Connection ~ 1650 2600
Wire Wire Line
	1650 2600 1650 2400
$Comp
L Connector:TestPoint TP21
U 1 1 5BA3AA0F
P 1650 2800
F 0 "TP21" V 1753 2874 50  0000 C CNN
F 1 "TestPoint" H 1708 2829 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 1850 2800 50  0001 C CNN
F 3 "~" H 1850 2800 50  0001 C CNN
	1    1650 2800
	0    -1   -1   0   
$EndComp
Connection ~ 1650 2800
Wire Wire Line
	1650 2800 1650 2600
$Comp
L Connector:TestPoint TP22
U 1 1 5BA3AA53
P 1650 3000
F 0 "TP22" V 1753 3074 50  0000 C CNN
F 1 "TestPoint" H 1708 3029 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 1850 3000 50  0001 C CNN
F 3 "~" H 1850 3000 50  0001 C CNN
	1    1650 3000
	0    -1   -1   0   
$EndComp
Connection ~ 1650 3000
Wire Wire Line
	1650 3000 1650 2800
$Comp
L Connector:TestPoint TP23
U 1 1 5BA3AA9D
P 1650 3200
F 0 "TP23" V 1753 3274 50  0000 C CNN
F 1 "TestPoint" H 1708 3229 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 1850 3200 50  0001 C CNN
F 3 "~" H 1850 3200 50  0001 C CNN
	1    1650 3200
	0    -1   -1   0   
$EndComp
Connection ~ 1650 3200
Wire Wire Line
	1650 3200 1650 3000
$Comp
L Connector:TestPoint TP24
U 1 1 5BA3AAE9
P 1650 3400
F 0 "TP24" V 1753 3474 50  0000 C CNN
F 1 "TestPoint" H 1708 3429 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 1850 3400 50  0001 C CNN
F 3 "~" H 1850 3400 50  0001 C CNN
	1    1650 3400
	0    -1   -1   0   
$EndComp
Connection ~ 1650 3400
Wire Wire Line
	1650 3400 1650 3200
$Comp
L Connector:TestPoint TP25
U 1 1 5BA3AB33
P 1650 3600
F 0 "TP25" V 1753 3674 50  0000 C CNN
F 1 "TestPoint" H 1708 3629 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 1850 3600 50  0001 C CNN
F 3 "~" H 1850 3600 50  0001 C CNN
	1    1650 3600
	0    -1   -1   0   
$EndComp
Connection ~ 1650 3600
Wire Wire Line
	1650 3600 1650 3400
Wire Wire Line
	3300 2100 3300 2200
$Comp
L Connector:TestPoint TP26
U 1 1 5BA3BB4F
P 3300 2200
F 0 "TP26" V 3300 2388 50  0000 L CNN
F 1 "TestPoint" H 3358 2229 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 3500 2200 50  0001 C CNN
F 3 "~" H 3500 2200 50  0001 C CNN
	1    3300 2200
	0    1    1    0   
$EndComp
Connection ~ 3300 2200
Wire Wire Line
	3300 2200 3300 2400
$Comp
L Connector:TestPoint TP27
U 1 1 5BA3BCD9
P 3300 2400
F 0 "TP27" V 3300 2588 50  0000 L CNN
F 1 "TestPoint" H 3358 2429 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 3500 2400 50  0001 C CNN
F 3 "~" H 3500 2400 50  0001 C CNN
	1    3300 2400
	0    1    1    0   
$EndComp
Connection ~ 3300 2400
Wire Wire Line
	3300 2400 3300 2600
$Comp
L Connector:TestPoint TP28
U 1 1 5BA3BD2D
P 3300 2600
F 0 "TP28" V 3300 2788 50  0000 L CNN
F 1 "TestPoint" H 3358 2629 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 3500 2600 50  0001 C CNN
F 3 "~" H 3500 2600 50  0001 C CNN
	1    3300 2600
	0    1    1    0   
$EndComp
Connection ~ 3300 2600
Wire Wire Line
	3300 2600 3300 2800
$Comp
L Connector:TestPoint TP29
U 1 1 5BA3BD7F
P 3300 2800
F 0 "TP29" V 3300 2988 50  0000 L CNN
F 1 "TestPoint" H 3358 2829 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 3500 2800 50  0001 C CNN
F 3 "~" H 3500 2800 50  0001 C CNN
	1    3300 2800
	0    1    1    0   
$EndComp
Connection ~ 3300 2800
Wire Wire Line
	3300 2800 3300 3000
$Comp
L Connector:TestPoint TP30
U 1 1 5BA3BDD3
P 3300 3000
F 0 "TP30" V 3300 3188 50  0000 L CNN
F 1 "TestPoint" H 3358 3029 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 3500 3000 50  0001 C CNN
F 3 "~" H 3500 3000 50  0001 C CNN
	1    3300 3000
	0    1    1    0   
$EndComp
Connection ~ 3300 3000
Wire Wire Line
	3300 3000 3300 3200
$Comp
L Connector:TestPoint TP31
U 1 1 5BA3BE29
P 3300 3200
F 0 "TP31" V 3300 3388 50  0000 L CNN
F 1 "TestPoint" H 3358 3229 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 3500 3200 50  0001 C CNN
F 3 "~" H 3500 3200 50  0001 C CNN
	1    3300 3200
	0    1    1    0   
$EndComp
Connection ~ 3300 3200
Wire Wire Line
	3300 3200 3300 3400
$Comp
L Connector:TestPoint TP32
U 1 1 5BA3BE81
P 3300 3400
F 0 "TP32" V 3300 3588 50  0000 L CNN
F 1 "TestPoint" H 3358 3429 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 3500 3400 50  0001 C CNN
F 3 "~" H 3500 3400 50  0001 C CNN
	1    3300 3400
	0    1    1    0   
$EndComp
Connection ~ 3300 3400
Wire Wire Line
	3300 3400 3300 3600
$Comp
L Connector:TestPoint TP33
U 1 1 5BA3BEDB
P 3300 3600
F 0 "TP33" V 3300 3788 50  0000 L CNN
F 1 "TestPoint" H 3358 3629 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 3500 3600 50  0001 C CNN
F 3 "~" H 3500 3600 50  0001 C CNN
	1    3300 3600
	0    1    1    0   
$EndComp
Connection ~ 3300 3600
Wire Wire Line
	3300 3600 3300 4000
Text Notes 2000 5000 0    50   ~ 0
Scaffold GND,\ndon't connect to DUT
$Comp
L power:GND #PWR0102
U 1 1 5BA3C5AA
P 5200 4650
F 0 "#PWR0102" H 5200 4400 50  0001 C CNN
F 1 "GND" H 5205 4477 50  0000 C CNN
F 2 "" H 5200 4650 50  0001 C CNN
F 3 "" H 5200 4650 50  0001 C CNN
	1    5200 4650
	1    0    0    -1  
$EndComp
Wire Wire Line
	5300 4550 5200 4550
Wire Wire Line
	5200 4550 5200 4650
Wire Wire Line
	5300 4250 5200 4250
Wire Wire Line
	5200 4250 5200 4350
Connection ~ 5200 4550
Wire Wire Line
	5300 4450 5200 4450
Connection ~ 5200 4450
Wire Wire Line
	5200 4450 5200 4550
Wire Wire Line
	5200 4350 5300 4350
Connection ~ 5200 4350
Wire Wire Line
	5200 4350 5200 4450
Wire Wire Line
	2200 3900 2100 3900
Wire Wire Line
	2100 3900 2100 4000
Wire Wire Line
	2200 4000 2100 4000
Connection ~ 2100 4000
Wire Wire Line
	2100 4000 2100 4200
Wire Wire Line
	2200 3700 2100 3700
Wire Wire Line
	2100 3700 2100 3900
Connection ~ 2100 3900
Wire Wire Line
	2200 3500 2100 3500
Wire Wire Line
	2100 3500 2100 3700
Connection ~ 2100 3700
Wire Wire Line
	2200 3300 2100 3300
Wire Wire Line
	2100 3300 2100 3500
Connection ~ 2100 3500
Wire Wire Line
	2200 3100 2100 3100
Wire Wire Line
	2100 3100 2100 3300
Connection ~ 2100 3300
Wire Wire Line
	2200 2900 2100 2900
Wire Wire Line
	2100 2900 2100 3100
Connection ~ 2100 3100
Wire Wire Line
	2200 2700 2100 2700
Wire Wire Line
	2100 2700 2100 2900
Connection ~ 2100 2900
Wire Wire Line
	2200 2500 2100 2500
Wire Wire Line
	2100 2500 2100 2700
Connection ~ 2100 2700
Wire Wire Line
	2200 2300 2100 2300
Wire Wire Line
	2100 2300 2100 2500
Connection ~ 2100 2500
Wire Wire Line
	2200 2100 2100 2100
Wire Wire Line
	2100 2100 2100 2300
Connection ~ 2100 2300
$Comp
L mylib:SAMTEC-QSE-020-01-F-D-A P1
U 1 1 5BA30734
P 2200 2100
F 0 "P1" H 2400 2365 50  0000 C CNN
F 1 "SAMTEC-QSE-020-01-F-D-A" H 2400 2274 50  0000 C CNN
F 2 "mykicadlibs:SAMTEC-QSE-020-01-F-D-A" H 2600 600 50  0001 C CNN
F 3 "" H 2600 600 50  0001 C CNN
	1    2200 2100
	1    0    0    -1  
$EndComp
Wire Wire Line
	2600 3900 2700 3900
Wire Wire Line
	2700 3900 2700 4600
Wire Wire Line
	2600 3700 2700 3700
Wire Wire Line
	2700 3700 2700 3900
Connection ~ 2700 3900
Wire Wire Line
	2600 3500 2700 3500
Wire Wire Line
	2700 3500 2700 3700
Connection ~ 2700 3700
Wire Wire Line
	2600 3300 2700 3300
Wire Wire Line
	2700 3300 2700 3500
Connection ~ 2700 3500
Wire Wire Line
	2600 3100 2700 3100
Wire Wire Line
	2700 3100 2700 3300
Connection ~ 2700 3300
Wire Wire Line
	2600 2900 2700 2900
Wire Wire Line
	2700 2900 2700 3100
Connection ~ 2700 3100
Wire Wire Line
	2600 2700 2700 2700
Wire Wire Line
	2700 2700 2700 2900
Connection ~ 2700 2900
Wire Wire Line
	2600 2500 2700 2500
Wire Wire Line
	2700 2500 2700 2700
Connection ~ 2700 2700
Wire Wire Line
	2600 2300 2700 2300
Wire Wire Line
	2700 2300 2700 2500
Connection ~ 2700 2500
Wire Wire Line
	2600 2100 2700 2100
Wire Wire Line
	2700 2100 2700 2300
Connection ~ 2700 2300
Wire Wire Line
	5300 4050 5200 4050
Wire Wire Line
	5200 4050 5200 4250
Connection ~ 5200 4250
Wire Wire Line
	5300 3950 5200 3950
Wire Wire Line
	5200 3950 5200 4050
Connection ~ 5200 4050
Wire Wire Line
	5300 3750 5200 3750
Wire Wire Line
	5200 3750 5200 3950
Connection ~ 5200 3950
Wire Wire Line
	5300 3550 5200 3550
Wire Wire Line
	5200 3550 5200 3750
Connection ~ 5200 3750
Wire Wire Line
	5300 3350 5200 3350
Wire Wire Line
	5200 3350 5200 3550
Connection ~ 5200 3550
Wire Wire Line
	5200 3350 5200 3150
Wire Wire Line
	5200 2150 5300 2150
Connection ~ 5200 3350
Wire Wire Line
	5300 2350 5200 2350
Connection ~ 5200 2350
Wire Wire Line
	5200 2350 5200 2150
Wire Wire Line
	5300 2550 5200 2550
Connection ~ 5200 2550
Wire Wire Line
	5200 2550 5200 2350
Wire Wire Line
	5300 2750 5200 2750
Connection ~ 5200 2750
Wire Wire Line
	5200 2750 5200 2550
Wire Wire Line
	5300 2950 5200 2950
Connection ~ 5200 2950
Wire Wire Line
	5200 2950 5200 2750
Wire Wire Line
	5300 3150 5200 3150
Connection ~ 5200 3150
Wire Wire Line
	5200 3150 5200 2950
$Comp
L power:GND #PWR0106
U 1 1 5BA81648
P 5800 4650
F 0 "#PWR0106" H 5800 4400 50  0001 C CNN
F 1 "GND" H 5805 4477 50  0000 C CNN
F 2 "" H 5800 4650 50  0001 C CNN
F 3 "" H 5800 4650 50  0001 C CNN
	1    5800 4650
	1    0    0    -1  
$EndComp
Wire Wire Line
	5800 4650 5800 4050
Wire Wire Line
	5800 2150 5700 2150
Wire Wire Line
	5700 2350 5800 2350
Connection ~ 5800 2350
Wire Wire Line
	5800 2350 5800 2150
Wire Wire Line
	5700 2550 5800 2550
Connection ~ 5800 2550
Wire Wire Line
	5800 2550 5800 2350
Wire Wire Line
	5700 2750 5800 2750
Connection ~ 5800 2750
Wire Wire Line
	5800 2750 5800 2550
Wire Wire Line
	5700 2950 5800 2950
Connection ~ 5800 2950
Wire Wire Line
	5800 2950 5800 2750
Wire Wire Line
	5700 3150 5800 3150
Connection ~ 5800 3150
Wire Wire Line
	5800 3150 5800 2950
Wire Wire Line
	5700 3350 5800 3350
Connection ~ 5800 3350
Wire Wire Line
	5800 3350 5800 3150
Wire Wire Line
	5700 3550 5800 3550
Connection ~ 5800 3550
Wire Wire Line
	5800 3550 5800 3350
Wire Wire Line
	5700 3750 5800 3750
Connection ~ 5800 3750
Wire Wire Line
	5800 3750 5800 3550
Wire Wire Line
	5700 3950 5800 3950
Connection ~ 5800 3950
Wire Wire Line
	5800 3950 5800 3750
Wire Wire Line
	5800 4050 5700 4050
Connection ~ 5800 4050
Wire Wire Line
	5800 4050 5800 3950
$Comp
L Connector:TestPoint TP34
U 1 1 5BAAAF6B
P 5150 2250
F 0 "TP34" V 5253 2324 50  0000 C CNN
F 1 "TestPoint" H 5208 2279 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 5350 2250 50  0001 C CNN
F 3 "~" H 5350 2250 50  0001 C CNN
	1    5150 2250
	0    -1   -1   0   
$EndComp
$Comp
L Connector:TestPoint TP35
U 1 1 5BAAB011
P 5150 2450
F 0 "TP35" V 5253 2524 50  0000 C CNN
F 1 "TestPoint" H 5208 2479 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 5350 2450 50  0001 C CNN
F 3 "~" H 5350 2450 50  0001 C CNN
	1    5150 2450
	0    -1   -1   0   
$EndComp
$Comp
L Connector:TestPoint TP36
U 1 1 5BAAB06F
P 5150 2650
F 0 "TP36" V 5253 2724 50  0000 C CNN
F 1 "TestPoint" H 5208 2679 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 5350 2650 50  0001 C CNN
F 3 "~" H 5350 2650 50  0001 C CNN
	1    5150 2650
	0    -1   -1   0   
$EndComp
$Comp
L Connector:TestPoint TP37
U 1 1 5BAAB0CF
P 5150 2850
F 0 "TP37" V 5253 2924 50  0000 C CNN
F 1 "TestPoint" H 5208 2879 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 5350 2850 50  0001 C CNN
F 3 "~" H 5350 2850 50  0001 C CNN
	1    5150 2850
	0    -1   -1   0   
$EndComp
$Comp
L Connector:TestPoint TP38
U 1 1 5BAAB131
P 5150 3050
F 0 "TP38" V 5253 3124 50  0000 C CNN
F 1 "TestPoint" H 5208 3079 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 5350 3050 50  0001 C CNN
F 3 "~" H 5350 3050 50  0001 C CNN
	1    5150 3050
	0    -1   -1   0   
$EndComp
$Comp
L Connector:TestPoint TP39
U 1 1 5BAAB195
P 5150 3250
F 0 "TP39" V 5253 3324 50  0000 C CNN
F 1 "TestPoint" H 5208 3279 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 5350 3250 50  0001 C CNN
F 3 "~" H 5350 3250 50  0001 C CNN
	1    5150 3250
	0    -1   -1   0   
$EndComp
$Comp
L Connector:TestPoint TP40
U 1 1 5BAAB1FB
P 5150 3450
F 0 "TP40" V 5253 3524 50  0000 C CNN
F 1 "TestPoint" H 5208 3479 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 5350 3450 50  0001 C CNN
F 3 "~" H 5350 3450 50  0001 C CNN
	1    5150 3450
	0    -1   -1   0   
$EndComp
$Comp
L Connector:TestPoint TP41
U 1 1 5BAAB263
P 5150 3650
F 0 "TP41" V 5253 3724 50  0000 C CNN
F 1 "TestPoint" H 5208 3679 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 5350 3650 50  0001 C CNN
F 3 "~" H 5350 3650 50  0001 C CNN
	1    5150 3650
	0    -1   -1   0   
$EndComp
$Comp
L Connector:TestPoint TP42
U 1 1 5BAAB2CD
P 5150 3850
F 0 "TP42" V 5253 3924 50  0000 C CNN
F 1 "TestPoint" H 5208 3879 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 5350 3850 50  0001 C CNN
F 3 "~" H 5350 3850 50  0001 C CNN
	1    5150 3850
	0    -1   -1   0   
$EndComp
$Comp
L Connector:TestPoint TP43
U 1 1 5BAAB339
P 5850 2250
F 0 "TP43" V 5850 2438 50  0000 L CNN
F 1 "TestPoint" H 5908 2279 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 6050 2250 50  0001 C CNN
F 3 "~" H 6050 2250 50  0001 C CNN
	1    5850 2250
	0    1    1    0   
$EndComp
$Comp
L Connector:TestPoint TP44
U 1 1 5BAAB41F
P 5850 2450
F 0 "TP44" V 5850 2638 50  0000 L CNN
F 1 "TestPoint" H 5908 2479 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 6050 2450 50  0001 C CNN
F 3 "~" H 6050 2450 50  0001 C CNN
	1    5850 2450
	0    1    1    0   
$EndComp
$Comp
L Connector:TestPoint TP45
U 1 1 5BAAB48F
P 5850 2650
F 0 "TP45" V 5850 2838 50  0000 L CNN
F 1 "TestPoint" H 5908 2679 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 6050 2650 50  0001 C CNN
F 3 "~" H 6050 2650 50  0001 C CNN
	1    5850 2650
	0    1    1    0   
$EndComp
$Comp
L Connector:TestPoint TP46
U 1 1 5BAAB501
P 5850 2850
F 0 "TP46" V 5850 3038 50  0000 L CNN
F 1 "TestPoint" H 5908 2879 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 6050 2850 50  0001 C CNN
F 3 "~" H 6050 2850 50  0001 C CNN
	1    5850 2850
	0    1    1    0   
$EndComp
$Comp
L Connector:TestPoint TP47
U 1 1 5BAAB575
P 5850 3050
F 0 "TP47" V 5850 3238 50  0000 L CNN
F 1 "TestPoint" H 5908 3079 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 6050 3050 50  0001 C CNN
F 3 "~" H 6050 3050 50  0001 C CNN
	1    5850 3050
	0    1    1    0   
$EndComp
$Comp
L Connector:TestPoint TP48
U 1 1 5BAAB5EB
P 5850 3250
F 0 "TP48" V 5850 3438 50  0000 L CNN
F 1 "TestPoint" H 5908 3279 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 6050 3250 50  0001 C CNN
F 3 "~" H 6050 3250 50  0001 C CNN
	1    5850 3250
	0    1    1    0   
$EndComp
$Comp
L Connector:TestPoint TP49
U 1 1 5BAAB663
P 5850 3450
F 0 "TP49" V 5850 3638 50  0000 L CNN
F 1 "TestPoint" H 5908 3479 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 6050 3450 50  0001 C CNN
F 3 "~" H 6050 3450 50  0001 C CNN
	1    5850 3450
	0    1    1    0   
$EndComp
$Comp
L Connector:TestPoint TP50
U 1 1 5BAAB6DD
P 5850 3650
F 0 "TP50" V 5850 3838 50  0000 L CNN
F 1 "TestPoint" H 5908 3679 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 6050 3650 50  0001 C CNN
F 3 "~" H 6050 3650 50  0001 C CNN
	1    5850 3650
	0    1    1    0   
$EndComp
$Comp
L Connector:TestPoint TP51
U 1 1 5BAAB759
P 5850 3850
F 0 "TP51" V 5850 4038 50  0000 L CNN
F 1 "TestPoint" H 5908 3879 50  0001 L CNN
F 2 "TestPoint:TestPoint_Pad_D1.5mm" H 6050 3850 50  0001 C CNN
F 3 "~" H 6050 3850 50  0001 C CNN
	1    5850 3850
	0    1    1    0   
$EndComp
Wire Wire Line
	5850 3850 5700 3850
Wire Wire Line
	5700 3650 5850 3650
Wire Wire Line
	5850 3450 5700 3450
Wire Wire Line
	5700 3250 5850 3250
Wire Wire Line
	5850 3050 5700 3050
Wire Wire Line
	5700 2850 5850 2850
Wire Wire Line
	5850 2650 5700 2650
Wire Wire Line
	5700 2450 5850 2450
Wire Wire Line
	5850 2250 5700 2250
Wire Wire Line
	5300 2250 5150 2250
Wire Wire Line
	5150 2450 5300 2450
Wire Wire Line
	5300 2650 5150 2650
Wire Wire Line
	5150 2850 5300 2850
Wire Wire Line
	5300 3050 5150 3050
Wire Wire Line
	5150 3250 5300 3250
Wire Wire Line
	5300 3450 5150 3450
Wire Wire Line
	5150 3650 5300 3650
Wire Wire Line
	5300 3850 5150 3850
Wire Wire Line
	2200 4400 2100 4400
Connection ~ 2100 4200
Wire Wire Line
	2100 4200 2100 4300
Wire Wire Line
	2100 4300 2100 4400
Connection ~ 2100 4300
Wire Wire Line
	2200 4300 2100 4300
Connection ~ 2100 4400
Wire Wire Line
	2100 4400 2100 4500
Wire Wire Line
	2100 4500 2100 4600
Connection ~ 2100 4500
Wire Wire Line
	2200 4500 2100 4500
$Comp
L power:GND #PWR0101
U 1 1 5BA395D3
P 2100 4600
F 0 "#PWR0101" H 2100 4350 50  0001 C CNN
F 1 "GND" H 2105 4427 50  0000 C CNN
F 2 "" H 2100 4600 50  0001 C CNN
F 3 "" H 2100 4600 50  0001 C CNN
	1    2100 4600
	1    0    0    -1  
$EndComp
$Comp
L power:GND #PWR0105
U 1 1 5BA4AD0D
P 2700 4600
F 0 "#PWR0105" H 2700 4350 50  0001 C CNN
F 1 "GND" H 2705 4427 50  0000 C CNN
F 2 "" H 2700 4600 50  0001 C CNN
F 3 "" H 2700 4600 50  0001 C CNN
	1    2700 4600
	1    0    0    -1  
$EndComp
$EndSCHEMATC
