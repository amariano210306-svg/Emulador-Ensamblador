; 65535 + 1 desborda los 16 bits: AX = 0 y CF = 1.
; JC detecta el acarreo y deja BX = 1.
MOV AX, 0xFFFF
ADD AX, 1
JC hay_acarreo
MOV BX, 0
JMP fin

hay_acarreo:
    MOV BX, 1

fin:
    HLT
