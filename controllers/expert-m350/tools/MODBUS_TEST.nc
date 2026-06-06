(MODBUS TEST - push known bytes to the PC Modbus slave)
(NO MOTION: only MSETDATA serial writes - safe on the real machine.)
(Per RU manual: each #var carries ONE byte 0-255; 2 vars pack into 1 Modbus register.)

(Distinctive byte values so we recognize the frame in the slave log)
#200 = 11
#201 = 22
#202 = 33
#203 = 44

(MSETDATA[X1,X2,X3,X4,X5,X6] - verified arg meanings from RU manual)
(  X1 = 200  start var #200)
(  X2 = 1    slave id      -> run slave as --slave 1)
(  X3 = 0    start register address)
(  X4 = 4    length in BYTES = #200..#203 -> 2 registers)
(  X5 = 16   Modbus function: write-multiple registers)
(  X6 = 300  exception-code returned into #300)
MSETDATA[200,1,0,4,16,300]

(Show the returned exception code on screen: 0 = OK)
#1510 = #300
#1505 = -5000(MSETDATA done - exception code #300 = %.0f)
M30
