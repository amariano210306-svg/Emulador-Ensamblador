"""Motor de un emulador educativo de ensamblador de 16 bits.

Solo utiliza la biblioteca estándar. El motor es independiente de la interfaz.
"""

from dataclasses import dataclass
import re


REGISTERS = ("AX", "BX", "CX", "DX", "SI", "DI", "BP", "SP")
MASK = 0xFFFF
SIGN_BIT = 0x8000

# Cada firma indica los operandos admitidos: registro, valor o etiqueta.
SIGNATURES = {
    **{name: ("register", "value") for name in
       ("MOV", "ADD", "SUB", "CMP", "AND", "OR", "XOR", "TEST")},
    **{name: ("register",) for name in ("INC", "DEC", "NEG", "NOT")},
    **{name: ("label",) for name in
       ("JMP", "JC", "JNC", "JZ", "JNZ", "JE", "JNE", "JG", "JGE", "JL",
        "JLE", "JA", "JAE", "JB", "JBE", "JO", "JNO", "JS", "JNS", "LOOP")},
    "NOP": (),
    "HLT": (),
}


class AssemblyError(ValueError):
    """Error de sintaxis con referencia a la línea original."""

    def __init__(self, message, line=None):
        self.line = line
        super().__init__(f"Línea {line}: {message}" if line else message)


class ExecutionLimitError(RuntimeError):
    """La ejecución se pausa para evitar un bucle infinito."""


@dataclass(frozen=True)
class Instruction:
    opcode: str
    operands: tuple
    line: int
    source: str


@dataclass(frozen=True)
class Program:
    instructions: tuple
    labels: dict


def signed(value):
    """Interpreta una palabra de 16 bits como entero con signo."""
    return value - 65536 if value & SIGN_BIT else value


def _parse_value(token, line):
    token = token.upper()
    if token in REGISTERS:
        return token
    try:
        if re.fullmatch(r"[+-]?\d+", token):
            value = int(token, 10)
        elif re.fullmatch(r"[+-]?0X[0-9A-F]+", token):
            value = int(token, 16)
        elif re.fullmatch(r"[+-]?0B[01]+", token):
            value = int(token, 2)
        elif re.fullmatch(r"[+-]?[0-9A-F]+H", token):
            value = int(token[:-1], 16)
        else:
            raise ValueError
    except ValueError:
        raise AssemblyError(
            f"'{token}' no es un registro ni un número válido.", line
        ) from None
    if not -32768 <= value <= 65535:
        raise AssemblyError("El número debe estar entre -32768 y 65535.", line)
    return value & MASK


def assemble(source):
    """Valida todo el programa y resuelve etiquetas antes de ejecutarlo."""
    labels = {}
    pending = []
    for line_number, raw in enumerate(source.splitlines(), start=1):
        code = raw.split(";", 1)[0].strip()
        if not code:
            continue
        while match := re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*", code):
            label = match.group(1).upper()
            if label in labels:
                raise AssemblyError(f"La etiqueta '{label}' está repetida.", line_number)
            if label in REGISTERS or label in SIGNATURES:
                raise AssemblyError(f"'{label}' es un nombre reservado.", line_number)
            labels[label] = len(pending)
            code = code[match.end():].strip()
        if not code:
            continue
        parts = code.split(None, 1)
        opcode = parts[0].upper()
        if opcode not in SIGNATURES:
            raise AssemblyError(f"Instrucción desconocida: '{opcode}'.", line_number)
        tokens = [piece.strip() for piece in parts[1].split(",")] if len(parts) > 1 else []
        signature = SIGNATURES[opcode]
        if len(tokens) != len(signature) or any(not token for token in tokens):
            detail = " Usa una coma para separar los operandos." if len(signature) == 2 else ""
            raise AssemblyError(
                f"{opcode} necesita {len(signature)} operando(s).{detail}", line_number
            )
        operands = []
        for token, kind in zip(tokens, signature):
            if kind == "register":
                register = token.upper()
                if register not in REGISTERS:
                    raise AssemblyError(
                        f"Se esperaba un registro ({', '.join(REGISTERS)}).", line_number
                    )
                operands.append(register)
            elif kind == "label":
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token):
                    raise AssemblyError("El salto necesita una etiqueta válida.", line_number)
                operands.append(token.upper())
            else:
                operands.append(_parse_value(token, line_number))
        pending.append(Instruction(opcode, tuple(operands), line_number, code))
    if not pending:
        raise AssemblyError("Escribe al menos una instrucción para ejecutar.")
    instructions = []
    for instruction in pending:
        if SIGNATURES[instruction.opcode] == ("label",):
            label = instruction.operands[0]
            if label not in labels:
                raise AssemblyError(f"La etiqueta '{label}' no existe.", instruction.line)
            instruction = Instruction(
                instruction.opcode, (labels[label],), instruction.line, instruction.source
            )
        instructions.append(instruction)
    return Program(tuple(instructions), labels)


class Emulator:
    """Registros y banderas compatibles con el subconjunto documentado."""

    def __init__(self):
        self.program = None
        self.reset()

    def reset(self):
        self.registers = dict.fromkeys(REGISTERS, 0)
        self.flags = dict.fromkeys(("ZF", "CF", "SF", "OF"), False)
        self.pc = 0
        self.steps = 0
        self.halted = False
        self.last_instruction = None

    def load(self, source):
        # Una entrada inválida no borra el estado de la ejecución anterior.
        program = assemble(source)
        self.program = program
        self.reset()

    @property
    def current_instruction(self):
        if self.program and not self.halted and self.pc < len(self.program.instructions):
            return self.program.instructions[self.pc]
        return None

    def _value(self, operand):
        return self.registers[operand] if isinstance(operand, str) else operand

    def _result_flags(self, result):
        self.flags["ZF"] = result == 0
        self.flags["SF"] = bool(result & SIGN_BIT)

    def _arithmetic(self, left, right, subtract=False):
        result = (left - right if subtract else left + right) & MASK
        self._result_flags(result)
        if subtract:
            self.flags["CF"] = left < right
            self.flags["OF"] = bool((left ^ right) & (left ^ result) & SIGN_BIT)
        else:
            self.flags["CF"] = left + right > MASK
            self.flags["OF"] = bool(~(left ^ right) & (left ^ result) & SIGN_BIT)
        return result

    def _jump_condition(self, opcode):
        z, c, s, o = (self.flags[name] for name in ("ZF", "CF", "SF", "OF"))
        return {
            "JMP": True, "JC": c, "JB": c, "JNC": not c, "JAE": not c,
            "JE": z, "JZ": z, "JNE": not z, "JNZ": not z,
            "JG": not z and s == o, "JGE": s == o, "JL": s != o,
            "JLE": z or s != o, "JA": not c and not z, "JBE": c or z,
            "JO": o, "JNO": not o, "JS": s, "JNS": not s,
        }[opcode]

    def step(self):
        if self.program is None:
            raise RuntimeError("Primero carga un programa.")
        instruction = self.current_instruction
        if instruction is None:
            return None
        opcode, operands = instruction.opcode, instruction.operands
        next_pc = self.pc + 1
        if opcode == "MOV":
            self.registers[operands[0]] = self._value(operands[1])
        elif opcode in ("ADD", "SUB", "CMP"):
            destination, right = operands
            result = self._arithmetic(
                self.registers[destination], self._value(right), opcode != "ADD"
            )
            if opcode != "CMP":
                self.registers[destination] = result
        elif opcode in ("INC", "DEC"):
            old_carry = self.flags["CF"]
            register = operands[0]
            self.registers[register] = self._arithmetic(
                self.registers[register], 1, opcode == "DEC"
            )
            self.flags["CF"] = old_carry
        elif opcode == "NEG":
            register = operands[0]
            self.registers[register] = self._arithmetic(0, self.registers[register], True)
        elif opcode == "NOT":
            self.registers[operands[0]] ^= MASK
        elif opcode in ("AND", "OR", "XOR", "TEST"):
            destination, right = operands
            left, right = self.registers[destination], self._value(right)
            result = (left | right) if opcode == "OR" else (
                (left ^ right) if opcode == "XOR" else (left & right)
            )
            self._result_flags(result)
            self.flags["CF"] = self.flags["OF"] = False
            if opcode != "TEST":
                self.registers[destination] = result
        elif opcode == "LOOP":
            self.registers["CX"] = (self.registers["CX"] - 1) & MASK
            if self.registers["CX"] != 0:
                next_pc = operands[0]
        elif opcode.startswith("J"):
            if self._jump_condition(opcode):
                next_pc = operands[0]
        elif opcode == "HLT":
            self.halted = True
        self.pc = next_pc
        self.steps += 1
        self.last_instruction = instruction
        if self.pc >= len(self.program.instructions):
            self.halted = True
        return instruction

    def run(self, max_steps=10000):
        """Continúa hasta HLT/fin o pausa al alcanzar el límite indicado."""
        if max_steps < 1:
            raise ValueError("El límite debe ser mayor que cero.")
        if self.program is None:
            raise RuntimeError("Primero carga un programa.")
        for _ in range(max_steps):
            if self.halted:
                break
            self.step()
        if not self.halted:
            raise ExecutionLimitError(
                f"Ejecución pausada tras {max_steps:,} instrucciones: "
                "revisa si hay un bucle infinito. El estado se conserva."
            )
        return dict(self.registers)
