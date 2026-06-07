( ===== dialect.js :: canonical phrasing each helper emits (default rules) ===== )

( goto(label) -> bare jump )
GOTO2

( ifGoto(lhs, op, rhs, label) -> conditional jump, default ifBracket=false )
IF #1920!=2 GOTO1
IF #1505==0 GOTO2

( ifGoto with rules.ifBracket=true -> bracketed condition form )
IF [#1920!=2] GOTO1

( g53(axis, value, comment) -> machine-coord move, default g53Rapid=false drops G0 )
G53 Z#57 ( comment )

( g53 with rules.g53Rapid=true -> FANUC form, documented to FAIL on M350 )
G53 G0 Z#57 ( comment )

( ===== wcsBase('active') block ===== )
( Read Active WCS )
#71=#578 ( Active WCS index: 1=G54 2=G55 etc )
#72=[#71-1] ( Zero-based index )
#70=[805+[#72*5]] ( Base WCS address )

( ===== wcsBase('G54') block (G54=805,G55=810,G56=815,G57=820,G58=825,G59=830) ===== )
( Target: G54 )
#70=805 ( Base WCS address )
