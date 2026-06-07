( ===== WCSWizard :: AUTO-DETECT path (sys="0"), X+Y+Z selected, sync slave A ===== )
( WCS | Direct #805+ writes )
( M350 Ready - G10 not used )

( Auto-detect active WCS from #578 )
#150=#578
#151=805+[#150-1]*5

( Zero selected axes )
#[#151+0]=#880
#[#151+1]=#881
#[#151+2]=#882

( Dual Gantry Sync - Slave A )
#152=[#151+3] ( Base WCS + Slave Offset )
#[#152]=#883

( ===== WCSWizard :: FIXED path (sys="55"), X+Y+Z selected, sync slave A ===== )
( WCS | Direct #805+ writes )
( M350 Ready - G10 not used )

( Fixed WCS: G55 - Base address #810 )
( Zero selected axes )
#810=#880
#811=#881
#812=#882

( Dual Gantry Sync - Slave A )
#813=#883
