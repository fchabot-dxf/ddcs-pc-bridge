(TEST B - deliberate fault to fire error.nc)
#201 = 7777 (marker: program started)
G04 P0.1 (tiny dwell, no motion)
ZZZZ (garbage token -> parse fault -> should run error.nc)
M30