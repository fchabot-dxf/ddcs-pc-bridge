( ===== generatePopup :: mode 1 (OK/Cancel), with slots ===== )
#1510=1
#1511=2
#1512=3
#1513=4
( Popup - OK/Cancel )
#1505=1(Continue with operation?)
IF #1505==0 GOTO9  ( ESC = cancel )
( --- action if OK --- )
N9 ( end )

( ===== generatePopup :: mode 3 (Binary Choice), with slots ===== )
#1510=1
( Popup - Binary Choice )
#1505=3(Pick a branch)
IF #1505==0 GOTO8  ( ESC branch )
( --- ENTER action --- )
GOTO9
N8 ( --- ESC action --- )
N9 ( end )

( ===== generatePopup :: toast (-5000, display only) ===== )
( Popup - Toast )
#1505=-5000(Job complete)

( ===== generateStatus :: standard mode, with color + dwell ===== )
#1510=1
( Status Bar Update )
#2039=255  ( Status bar color - BGR )
#1503=1(Probing in progress)
#2039=-1  ( Restore default color )
G4 P1000  ( Dwell - keep message visible )

( ===== generateStatus :: persistent mode (-3000), no color ===== )
( Persistent Status Bar )
#1503=-3000(Machine homed)

( ===== generateInput :: id in 50-499 range, with dest copy ===== )
( Numeric Input - DDCS Safe )
#2070=100(Enter feed rate)
#805=#100  ( Copy to persistent )

( ===== generateInput :: id out of range -> falls back to temp #100 ===== )
( Numeric Input - DDCS Safe )
#2070=100(Enter value)
#805=#100  ( Copy to persistent )

( ===== generateBeep :: pulsed (cycle>0) ===== )
( System Beep - 5 pulses of 50ms )
#2043=50  ( Pulse width ms )
#2042=500  ( Total duration ms )

( ===== generateBeep :: continuous ===== )
( System Beep )
#2042=500  ( Beep duration ms )

( ===== generateDwell ===== )
( Dwell )
G4 P1000

( ===== default :: unknown communication type ===== )
( Unknown communication type: foo )
