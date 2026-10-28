# Emulador de ensamblador en Python

Aplicación educativa con una interfaz sencilla en español. Escribe instrucciones, ejecútalas y consulta el valor de los registros y las banderas. Usa **Python 3.10 o posterior con Tkinter**; no necesita paquetes de `pip`. La instalación oficial de Python para Windows incluye Tkinter por defecto.

## Iniciar

En Windows, haz doble clic en **`iniciar.bat`**, o abre una terminal en esta carpeta y ejecuta:

```powershell
python main.py
```

La ventana abre un ejemplo listo para ejecutar:

- **Ejecutar / F5:** ejecuta desde la posición actual hasta `HLT` o el final.
- **Paso a paso / F10:** ejecuta una instrucción y muestra sus efectos.
- **Pausar / Escape:** conserva el estado para continuar después.
- **Reiniciar:** pone registros y banderas en cero y conserva el código.
- **Cargar ejemplo:** selecciona suma, acarreo, bucle o comparación con signo.
- **Archivo:** crea, abre y guarda programas `.asm` o `.txt` en UTF-8.
- **Guía:** consulta la sintaxis y las instrucciones sin salir de la aplicación.

Los registros se muestran en decimal sin signo, decimal con signo y hexadecimal. El amarillo señala la siguiente instrucción; el violeta, la última ejecutada y los registros que cambiaron en el último paso o bloque de ejecución. El historial conserva las últimas 250 instrucciones ejecutadas.

Si editas el código, la siguiente ejecución empieza desde cero. Después de finalizar, pulsa **Reiniciar** para volver a ejecutar. La ejecución completa se pausa automáticamente tras 10 000 instrucciones para evitar que un bucle infinito bloquee la ventana; conserva el estado y permite continuar.

## Ejemplo

```asm
MOV AX, 10
MOV BX, 5
ADD AX, BX
CMP AX, 15
JGE correcto
MOV DX, 0
JMP fin

correcto:
    MOV DX, 1

fin:
    HLT
```

Resultado: **AX = 15, BX = 5, DX = 1**. Los demás registros permanecen en cero. `CMP` compara sin modificar el registro; en este caso activa `ZF` porque ambos valores son iguales.

## Modelo y sintaxis

- Ocho registros de **16 bits**: `AX`, `BX`, `CX`, `DX`, `SI`, `DI`, `BP`, `SP`.
- Todos los registros y las banderas empiezan en cero.
- No distingue mayúsculas y minúsculas.
- Los operandos se separan con coma. El destino debe ser un registro.
- Acepta números entre `-32768` y `65535`: decimal (`10`, `-2`), hexadecimal (`0xFF`, `FFh`) y binario (`0b1010`).
- Las etiquetas terminan con `:` y pueden compartir línea con una instrucción. Los saltos reciben nombres de etiquetas, no números de línea.
- Las etiquetas usan letras, dígitos y `_`, y no comienzan con un dígito. No pueden repetirse ni usar nombres de registros o instrucciones.
- Los comentarios comienzan con `;`.
- La aritmética se ajusta a 16 bits: `65535 + 1 = 0`, con `CF = 1`. Un valor como `0xFFFF` representa `65535` sin signo o `-1` con signo.
- El programa completo se valida antes de ejecutar. Los errores indican la línea correspondiente.
- `HLT` es opcional: llegar al final del código también termina el programa.

Es un subconjunto educativo inspirado en x86. No interpreta programas completos de MASM/NASM: no incluye memoria, pila, interrupciones, directivas, segmentos, registros de 8/32/64 bits ni ejecutables nativos. `BP` y `SP` se usan como registros generales.

## Instrucciones

`valor` puede ser un número o cualquiera de los ocho registros.

| Instrucción | Operación |
| --- | --- |
| `MOV registro, valor` | Copia el valor; conserva las banderas. |
| `ADD registro, valor` | Suma y actualiza ZF, CF, SF, OF. |
| `SUB registro, valor` | Resta y actualiza ZF, CF, SF, OF. |
| `CMP registro, valor` | Actualiza banderas como una resta, sin guardar el resultado. |
| `INC registro`, `DEC registro` | Suma/resta 1; conserva CF y actualiza ZF, SF, OF. |
| `NEG registro` | Negación aritmética; actualiza las cuatro banderas. |
| `AND`, `OR`, `XOR registro, valor` | Operaciones bit a bit; actualizan ZF/SF y ponen CF/OF en cero. |
| `TEST registro, valor` | Actualiza banderas como AND, sin modificar el registro. |
| `NOT registro` | Invierte los 16 bits; conserva las banderas. |
| `JMP etiqueta` | Salto incondicional. |
| `JC`, `JB etiqueta` | Salta si CF = 1. |
| `JNC`, `JAE etiqueta` | Salta si CF = 0. |
| `JE`, `JZ etiqueta` | Salta si ZF = 1. |
| `JNE`, `JNZ etiqueta` | Salta si ZF = 0. |
| `JG etiqueta` | Mayor con signo: ZF = 0 y SF = OF. |
| `JGE etiqueta` | Mayor o igual con signo: SF = OF. |
| `JL etiqueta` | Menor con signo: SF ≠ OF. |
| `JLE etiqueta` | Menor o igual con signo: ZF = 1 o SF ≠ OF. |
| `JA etiqueta` | Mayor sin signo: CF = 0 y ZF = 0. |
| `JBE etiqueta` | Menor o igual sin signo: CF = 1 o ZF = 1. |
| `JO`, `JNO etiqueta` | Salta si OF = 1 / OF = 0. |
| `JS`, `JNS etiqueta` | Salta si SF = 1 / SF = 0. |
| `LOOP etiqueta` | Decrementa CX y salta si no es cero; conserva banderas. |
| `NOP` | No realiza cambios. |
| `HLT` | Finaliza la ejecución. |

Los saltos consultan las banderas actuales, normalmente establecidas por `CMP` o por una operación aritmética. `JGE` interpreta la comparación **con signo**; `JAE` la interpreta **sin signo**. Si `CX` vale cero antes de `LOOP`, pasa a `65535` y el salto se realiza.

| Bandera | Significado |
| --- | --- |
| ZF | El resultado es cero. |
| CF | Acarreo en suma o préstamo en resta. |
| SF | El bit 15 es 1; el resultado se interpreta como negativo con signo. |
| OF | Desbordamiento del intervalo con signo de -32768 a 32767. |

## Usar desde consola

```powershell
python main.py --cli examples/suma.asm
python main.py --cli examples/acarreo.asm --max-steps 1000
```

Muestra los registros finales, las banderas y el número de instrucciones. Devuelve código de salida `1` si encuentra un error o alcanza el límite de ejecución.

También puedes abrir un archivo directamente en la ventana:

```powershell
python main.py examples/bucle.asm
```

## Usar el motor desde Python

```python
from emulator import Emulator

cpu = Emulator()
cpu.load("MOV AX, 10\nADD AX, 5\nHLT")
registros = cpu.run()
print(registros["AX"])  # 15
print(cpu.flags)
```

`step()` ejecuta una instrucción, `run()` continúa desde el estado actual y `reset()` reinicia el programa cargado. Un programa inválido produce `AssemblyError`. Al alcanzar el límite, `run()` produce `ExecutionLimitError` y conserva el estado para inspeccionarlo o continuarlo.

## Comprobar el programa

```powershell
python -m unittest discover -s tests -v
```

Las pruebas cubren instrucciones, saltos con y sin signo, límites de 16 bits, banderas, errores, bucles, ejemplos e integración entre la ventana y el motor. Las pruebas de interfaz necesitan Tkinter y una sesión gráfica.

## Archivos

- `main.py`: interfaz Tkinter y ejecución por consola.
- `emulator.py`: análisis del código, registros, banderas y ejecución.
- `examples/`: cuatro programas de ejemplo.
- `tests/`: pruebas con `unittest` de la biblioteca estándar.
- `iniciar.bat`: acceso de inicio en Windows.
