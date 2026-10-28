"""Pruebas de integración de la ventana con el motor real."""

import time
import tkinter as tk
import unittest

from main import EmulatorApp


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = EmulatorApp(self.root)
        self.root.update()

    def tearDown(self):
        self.app._pause(announce=False)
        if self.app.highlight_id:
            self.root.after_cancel(self.app.highlight_id)
        self.root.destroy()

    def finish_run(self):
        deadline = time.monotonic() + 8
        while self.app.running and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.005)
        self.assertFalse(self.app.running, "La interfaz no terminó la ejecución")

    def test_step_continue_and_register_display(self):
        self.app._step()
        self.assertEqual(self.app.cpu.steps, 1)
        self.assertEqual(self.app.cpu.registers["AX"], 10)
        self.app._run()
        self.finish_run()
        values = self.app.register_table.item("AX", "values")
        self.assertEqual(values, ("AX", "15", "15", "0x000F"))
        self.assertEqual(self.app.cpu.registers["DX"], 1)
        self.assertIn("Programa finalizado", self.app.status.cget("text"))
        self.assertEqual(self.app.editor.cget("state"), "normal")

    def test_reset_preserves_source(self):
        source = self.app._source()
        self.app._step()
        self.app._reset()
        self.assertEqual(self.app._source(), source)
        self.assertEqual(self.app.cpu.registers["AX"], 0)
        self.assertEqual(self.app.cpu.steps, 0)

    def test_edit_restarts_execution(self):
        self.app._step()
        self.app.editor.delete("1.0", "end")
        self.app.editor.insert("1.0", "MOV BX, 7\nHLT")
        self.root.update()
        self.app._step()
        self.assertEqual(self.app.cpu.steps, 1)
        self.assertEqual(self.app.cpu.registers["AX"], 0)
        self.assertEqual(self.app.cpu.registers["BX"], 7)

    def test_invalid_program_shows_line(self):
        self.app._set_source("MOV AX, 1\nJMP missing")
        self.app._run()
        self.assertFalse(self.app.running)
        self.assertIn("Línea 2", self.app.status.cget("text"))
        self.assertEqual(str(self.app.editor.tag_ranges("error")[0]), "2.0")
        self.assertEqual(self.app.cpu.steps, 0)

    def test_pause_and_infinite_loop_limit(self):
        self.app._set_source("again: INC AX\nJMP again")
        self.app._run()
        self.app._pause()
        self.assertFalse(self.app.running)
        self.assertIsNone(self.app.after_id)
        self.app._run()
        self.finish_run()
        self.assertEqual(self.app.cpu.steps, 10000)
        self.assertEqual(self.app.cpu.registers["AX"], 5000)
        self.assertIn("Pausa automática", self.app.status.cget("text"))
        self.app._step()
        self.assertEqual(self.app.cpu.registers["AX"], 5001)


if __name__ == "__main__":
    unittest.main()
