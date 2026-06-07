( ===== SNIPPETS.safe_z ===== )
( Safe Z Retract - DDCS Compliant )
#99=0
G53 Z#99

( ===== SNIPPETS.probe ===== )
( Smart Probe - DDCS Compliant )
G91
G31 Z-10 F100 P3 L0 Q1
IF #1922!=2 GOTO1
#1505=-5000(Contact!)
GOTO2
N1
#1505=1(Miss!)
N2
G90
M30

( ===== SNIPPETS.wash ===== )
+0
