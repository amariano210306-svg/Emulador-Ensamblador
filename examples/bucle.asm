; Suma 5 + 4 + 3 + 2 + 1: AX = 15 y CX = 0.
MOV AX, 0
MOV CX, 5

sumar:
    ADD AX, CX
    LOOP sumar

HLT
