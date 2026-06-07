(CHECKPOINT_TEST - prove run-progress readback the SAFE way)
(Only sets ordinary user vars then MSETDATA. NO system-var reads, NO motion.)
(Slave logs 3 frames with #250 = 1 then 2 then 3 = how far the job got.)
(Note: each MSETDATA pauses ~16s, so the whole run takes ~45s. That is normal, not a freeze.)

(checkpoint 1 - started)
#250 = 1
#251 = 111
MSETDATA[250,1,0,2,16,300]

(checkpoint 2 - middle)
#250 = 2
MSETDATA[250,1,0,2,16,300]

(checkpoint 3 - before end)
#250 = 3
MSETDATA[250,1,0,2,16,300]

#1510 = #300
#1505 = -5000(checkpoints sent - last exception #300 = %.0f)
M30
