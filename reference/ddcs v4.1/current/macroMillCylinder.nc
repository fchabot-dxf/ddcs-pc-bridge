O#1802(Main Program)
MarcoDialog "macroMillCylinder.rc"

M3S#1813

;#141 毛胚直径
;#142 圆柱体直径
;#143 工件长度
;#144 每层深度
;#145 刀具直径
;#146 刀尖间距
;#147 圆柱中心轴
;#139 下钻速度
;#140 铣圆柱速度

;每层深度 #1
;毛坯直径 #2
;刀具直径 #3
;圆柱体直径 #4
;刀尖间距 #5
;工件长度 #6
;圆柱中心轴 X轴 Y轴 #7
;下钻速度 #30
;铣圆柱速度 #31

#1=#144
#2=#141
#3=#145
#4=#142
#5=#146
#6=#143
#7=#147
#30=#139
#31=#140

#32=#1508
#11=1;X(Y)轴运动方向初始化

G0Z#2/2

IF#1>[#2-#4]/2GOTO10
#10=#2/2-#1
GOTO11
N10#10=#4/2
N11G1Z#10F#30

WHILE#10>=#4/2DO2

F#31
M98P#1802+1X#6-#3Y#5Z#11A#7

IF#10==#4/2GOTO3
#10=#10-#1
IF#10>#4/2GOTO4
#10=#4/2
N4G90Z#10F#30
GOTO5
N3#10=#10-1
N5

#11=-#11;X(Y)轴换向

END2

G90G0Z#32
M5
M99

O#1802+1(Subprograms)
;#1 X(Y)-axis movement distance
;#2 Interval distance
;#3 X(Y)-axis motion direction
;#4 X(Y)-axis selection
#11=0
#12=0
WHILE#11<#1DO1
IF#4==1GOTO11
G91G1X[#11-#12]*#3
GOTO12
N11G91G1Y[#11-#12]*#3
N12#12=#11
#11=#11+#2
G91G1A360
END1

IF#11>=#1GOTO1
GOTO2
N1IF#4==1GOTO13
G91G1X[#1-#12]*#3
GOTO14
N13G91G1Y[#1-#12]*#3
N14G91G1A360
N2
M99
