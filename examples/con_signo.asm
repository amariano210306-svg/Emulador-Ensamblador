; JGE compara con signo. -2 es menor que 1: BX = 0.
; AX se muestra como 65534 sin signo, -2 con signo y 0xFFFE.
MOV AX, -2
CMP AX, 1
JGE mayor_o_igual
MOV BX, 0
JMP fin

mayor_o_igual:
    MOV BX, 1

fin:
    HLT
