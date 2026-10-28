; Suma y comparación: resultado AX = 15, BX = 5, DX = 1.
MOV AX, 10
MOV BX, 5
ADD AX, BX
CMP AX, 15
JGE mayor_o_igual
MOV DX, 0
JMP fin

mayor_o_igual:
    MOV DX, 1

fin:
    HLT
