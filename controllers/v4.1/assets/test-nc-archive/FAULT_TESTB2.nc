(TEST B2 - forced alarm via #3000 should fire error.nc)
#201 = 7778 (marker: THIS run started)
#202 = 0 (canary cleared)
#3000=1(MSG,TEST B2 forced alarm)
#202 = 5555 (canary - must stay 0 if alarm truly halts)
M30