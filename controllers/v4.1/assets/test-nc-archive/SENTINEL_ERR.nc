(SENTINEL test - detect syntax error via MISSING completion flag)
#203 = 0 (clear completion sentinel)
#201 = 7779 (start marker: this run began)
G04 P0.1 (no motion)
ZZZZ (syntax error - kills execution here)
#203 = 9999 (completion sentinel - must NOT run if error above)
M30