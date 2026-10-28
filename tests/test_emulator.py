import random
from pathlib import Path
import unittest

from emulator import AssemblyError, Emulator, ExecutionLimitError, assemble, signed


class EmulatorTests(unittest.TestCase):
    def execute(self, source):
        cpu = Emulator()
        cpu.load(source)
        cpu.run()
        return cpu

    def test_required_instructions(self):
        cpu = self.execute("""
            MOV AX, 65535
            ADD AX, 1
            JC carry
            MOV BX, 99
            carry: MOV BX, 5
            CMP BX, 3
            JGE greater
            MOV DX, 99
            greater: MOV DX, 1
            JMP end
            MOV DX, 99
            end: HLT
        """)
        self.assertEqual((cpu.registers["AX"], cpu.registers["BX"], cpu.registers["DX"]), (0, 5, 1))

    def test_numeric_formats_and_case(self):
        cpu = self.execute("mov ax, 0xFF\nmov bx, ffh\nmov cx, 0b11111111\nmov dx, 0255\nmov si, -1")
        self.assertEqual([cpu.registers[name] for name in ("AX", "BX", "CX", "DX")], [255] * 4)
        self.assertEqual(cpu.registers["SI"], 65535)

    def test_all_registers_and_register_source(self):
        cpu = self.execute("MOV AX, 42\nMOV BX, AX\nMOV CX, BX\nMOV DX, CX\nMOV SI, DX\nMOV DI, SI\nMOV BP, DI\nMOV SP, BP")
        self.assertEqual(set(cpu.registers.values()), {42})

    def test_arithmetic_boundary_and_random_values(self):
        rng = random.Random(1632)
        values = [0, 1, 32767, 32768, 65534, 65535]
        pairs = [(a, b) for a in values for b in values]
        pairs += [(rng.randrange(65536), rng.randrange(65536)) for _ in range(300)]
        for opcode in ("ADD", "SUB", "CMP"):
            for left, right in pairs:
                with self.subTest(opcode=opcode, left=left, right=right):
                    cpu = self.execute(f"MOV AX, {left}\n{opcode} AX, {right}")
                    full = left + right if opcode == "ADD" else left - right
                    signed_full = signed(left) + signed(right) if opcode == "ADD" else signed(left) - signed(right)
                    result = full % 65536
                    self.assertEqual(cpu.registers["AX"], left if opcode == "CMP" else result)
                    self.assertEqual(cpu.flags, {
                        "ZF": result == 0,
                        "CF": full < 0 or full > 65535,
                        "SF": result >= 32768,
                        "OF": not -32768 <= signed_full <= 32767,
                    })

    def test_signed_and_unsigned_jumps(self):
        pairs = [(0, 0), (2, 1), (1, 2), (65535, 1), (32767, 65535), (32768, 1), (0, 65535)]
        for left, right in pairs:
            a, b = signed(left), signed(right)
            conditions = {
                "JGE": a >= b, "JG": a > b, "JL": a < b, "JLE": a <= b,
                "JA": left > right, "JAE": left >= right, "JB": left < right,
                "JBE": left <= right, "JC": left < right, "JNC": left >= right,
                "JE": left == right, "JZ": left == right,
                "JNE": left != right, "JNZ": left != right, "JMP": True,
            }
            for opcode, expected in conditions.items():
                with self.subTest(opcode=opcode, left=left, right=right):
                    cpu = self.execute(f"MOV AX, {left}\nCMP AX, {right}\n{opcode} yes\nHLT\nyes: MOV BX, 1")
                    self.assertEqual(cpu.registers["BX"], int(expected))

    def test_overflow_and_sign_jumps(self):
        for value in (0, 1, 32767, 32768, 65535):
            result = (value + 1) % 65536
            for opcode, expected in {"JO": value == 32767, "JNO": value != 32767,
                                      "JS": result >= 32768, "JNS": result < 32768}.items():
                with self.subTest(opcode=opcode, value=value):
                    cpu = self.execute(f"MOV AX, {value}\nADD AX, 1\n{opcode} yes\nHLT\nyes: MOV BX, 1")
                    self.assertEqual(cpu.registers["BX"], int(expected))

    def test_increment_decrement_preserve_carry(self):
        cpu = self.execute("MOV AX, 65535\nADD AX, 1\nMOV BX, 32767\nINC BX")
        self.assertEqual(cpu.registers["BX"], 32768)
        self.assertTrue(cpu.flags["CF"])
        self.assertTrue(cpu.flags["OF"])
        cpu = self.execute("MOV BX, 32768\nDEC BX")
        self.assertEqual(cpu.registers["BX"], 32767)
        self.assertFalse(cpu.flags["CF"])
        self.assertTrue(cpu.flags["OF"])

    def test_negation(self):
        for value in (0, 1, 32767, 32768, 65535):
            with self.subTest(value=value):
                cpu = self.execute(f"MOV AX, {value}\nNEG AX")
                self.assertEqual(cpu.registers["AX"], (-value) % 65536)
                self.assertEqual(cpu.flags["CF"], value != 0)
                self.assertEqual(cpu.flags["OF"], value == 32768)

    def test_bitwise_operations(self):
        for opcode, expected in (("AND", 0x0030), ("OR", 0x03FF), ("XOR", 0x03CF), ("TEST", 0x00F0)):
            with self.subTest(opcode=opcode):
                cpu = self.execute(f"MOV BX, 65535\nADD BX, 1\nMOV AX, 0xF0\n{opcode} AX, 0x033F")
                self.assertEqual(cpu.registers["AX"], expected)
                self.assertFalse(cpu.flags["CF"])
                self.assertFalse(cpu.flags["OF"])
        cpu = self.execute("MOV AX, 42\nXOR AX, AX")
        self.assertEqual(cpu.registers["AX"], 0)
        self.assertTrue(cpu.flags["ZF"])

    def test_non_flag_instructions_preserve_flags(self):
        cpu = self.execute("MOV AX, 65535\nADD AX, 1\nMOV BX, 3\nNOT BX\nNOP\nJMP done\ndone: HLT")
        self.assertEqual(cpu.registers["BX"], 65532)
        self.assertEqual(cpu.flags, {"ZF": True, "CF": True, "SF": False, "OF": False})

    def test_loop_and_flag_preservation(self):
        cpu = self.execute("MOV CX, 3\nCMP AX, 1\nagain: MOV BX, CX\nLOOP again")
        self.assertEqual(cpu.registers["BX"], 1)
        self.assertEqual(cpu.registers["CX"], 0)
        self.assertEqual(cpu.flags, {"ZF": False, "CF": True, "SF": True, "OF": False})

    def test_labels_comments_and_end_label(self):
        cpu = self.execute("; comment\n\nfirst: alias: mov ax, 2 ; test\njmp DONE\nMOV AX, 99\ndone:")
        self.assertEqual(cpu.registers["AX"], 2)
        self.assertEqual(cpu.last_instruction.line, 4)
        self.assertTrue(cpu.halted)

    def test_parse_errors_have_line_number(self):
        invalid = ["BAD AX, 1", "MOV ZZ, 1", "MOV AX 1", "ADD AX,", "NOP AX", "JMP missing",
                   "MOV AX, 65536", "MOV AX, -32769", "MOV AX, abc", "MOV AX, [BX]", "JMP 2",
                   "AX: NOP", "JMP: NOP", "same: NOP\nsame: HLT"]
        for source in invalid:
            with self.subTest(source=source):
                with self.assertRaises(AssemblyError) as context:
                    assemble("; initial comment\n" + source)
                self.assertGreaterEqual(context.exception.line, 2)
        with self.assertRaises(AssemblyError):
            assemble("; empty program")

    def test_invalid_load_preserves_state(self):
        cpu = self.execute("MOV AX, 42")
        with self.assertRaises(AssemblyError):
            cpu.load("MOV AX, 7\nBAD")
        self.assertEqual(cpu.registers["AX"], 42)

    def test_step_reset_and_halt(self):
        cpu = Emulator()
        cpu.load("MOV AX, 2\nHLT\nMOV AX, 99")
        self.assertEqual(cpu.current_instruction.line, 1)
        cpu.step()
        self.assertEqual(cpu.registers["AX"], 2)
        self.assertFalse(cpu.halted)
        cpu.step()
        self.assertTrue(cpu.halted)
        self.assertIsNone(cpu.step())
        self.assertEqual(cpu.steps, 2)
        cpu.reset()
        self.assertEqual(cpu.steps, 0)
        self.assertEqual(cpu.registers["AX"], 0)
        cpu.run()
        self.assertEqual(cpu.registers["AX"], 2)

    def test_loop_limit_preserves_state_and_can_continue(self):
        cpu = Emulator()
        cpu.load("again: INC AX\nJMP again")
        with self.assertRaises(ExecutionLimitError):
            cpu.run(10)
        self.assertEqual(cpu.registers["AX"], 5)
        self.assertEqual(cpu.steps, 10)
        self.assertFalse(cpu.halted)
        cpu.step()
        self.assertEqual(cpu.registers["AX"], 6)
        with self.assertRaises(ValueError):
            cpu.run(0)

    def test_final_instruction_at_exact_limit(self):
        cpu = Emulator()
        cpu.load("NOP\nHLT")
        cpu.run(2)
        self.assertTrue(cpu.halted)

    def test_examples(self):
        folder = Path(__file__).resolve().parents[1] / "examples"
        for filename, expected in {
            "suma.asm": {"AX": 15, "BX": 5, "DX": 1},
            "acarreo.asm": {"AX": 0, "BX": 1},
            "bucle.asm": {"AX": 15, "CX": 0},
            "con_signo.asm": {"AX": 65534, "BX": 0},
        }.items():
            with self.subTest(example=filename):
                cpu = self.execute((folder / filename).read_text(encoding="utf-8"))
                for register, value in expected.items():
                    self.assertEqual(cpu.registers[register], value)


if __name__ == "__main__":
    unittest.main()
