"""Interfaz gráfica y entrada de consola del emulador educativo."""

import argparse
from collections import deque
from pathlib import Path
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from emulator import AssemblyError, Emulator, ExecutionLimitError, REGISTERS, SIGNATURES, signed


BASE_DIR = Path(__file__).resolve().parent
EXAMPLES = {
    "Suma y comparación": "suma.asm",
    "Acarreo con JC": "acarreo.asm",
    "Bucle con LOOP": "bucle.asm",
    "Comparación con signo": "con_signo.asm",
}
BG = "#f2f4f8"
INK = "#1e293b"
MUTED = "#64748b"
ACCENT = "#4f46e5"
LIMIT = 10000


class EmulatorApp:
    def __init__(self, root, initial_path=None):
        self.root = root
        self.cpu = Emulator()
        self.running = False
        self.after_id = None
        self.highlight_id = None
        self.loaded_source = None
        self.file_path = None
        self.saved_source = ""
        self.history = deque(maxlen=250)
        self.run_steps = 0
        root.title("Ensamblador · Emulador de 16 bits")
        root.geometry("1120x820")
        root.minsize(960, 780)
        root.configure(bg=BG)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)
        root.protocol("WM_DELETE_WINDOW", self._close)
        self._styles()
        self._menu()
        self._build()
        self._set_source((BASE_DIR / "examples" / "suma.asm").read_text(encoding="utf-8"))
        if initial_path:
            self._open_path(initial_path)
        self._refresh()

    def _styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=INK, font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 8), background="white")
        style.map("TButton", background=[("active", "#e7e9f2")])
        style.configure("Primary.TButton", background=ACCENT, foreground="white", borderwidth=0)
        style.map("Primary.TButton", background=[("disabled", "#b4b1e8"), ("active", "#4338ca")],
                  foreground=[("disabled", "#f1f0ff")])
        style.configure("Treeview", font=("Consolas", 11), rowheight=27,
                        background="white", fieldbackground="white", foreground=INK, borderwidth=0)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"),
                        background="#eef0f6", foreground=MUTED, padding=(4, 8))
        style.map("Treeview", background=[("selected", "#e0e7ff")],
                  foreground=[("selected", INK)])
        style.configure("TCombobox", padding=7, font=("Segoe UI", 10))

    def _menu(self):
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Nuevo", accelerator="Ctrl+N", command=self._new)
        file_menu.add_command(label="Abrir…", accelerator="Ctrl+O", command=self._open)
        file_menu.add_command(label="Guardar", accelerator="Ctrl+S", command=self._save)
        file_menu.add_command(label="Guardar como…", command=lambda: self._save(save_as=True))
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self._close)
        menu.add_cascade(label="Archivo", menu=file_menu)
        menu.add_command(label="Guía de instrucciones", command=self._help)
        self.root.config(menu=menu)
        for key, action in (("<Control-n>", self._new), ("<Control-o>", self._open),
                            ("<Control-s>", self._save), ("<F5>", self._run),
                            ("<F10>", self._step), ("<Escape>", self._pause)):
            self.root.bind(key, lambda event, callback=action: self._shortcut(callback))

    @staticmethod
    def _shortcut(callback):
        callback()
        return "break"

    def _build(self):
        header = ttk.Frame(self.root, padding=(24, 20, 24, 15))
        header.grid(row=0, column=0, sticky="ew")
        tk.Label(header, text="ASM", font=("Consolas", 16, "bold"), bg=ACCENT,
                 fg="white", padx=12, pady=8).pack(side="left", padx=(0, 14))
        titles = ttk.Frame(header)
        titles.pack(side="left")
        tk.Label(titles, text="Emulador de ensamblador", font=("Segoe UI", 21, "bold"),
                 bg=BG, fg=INK).pack(anchor="w")
        tk.Label(titles, text="Escribe, ejecuta y observa cómo cambian los registros.",
                 font=("Segoe UI", 10), bg=BG, fg=MUTED).pack(anchor="w", pady=(3, 0))
        tk.Label(header, text="16 BITS  /  8 REGISTROS", font=("Consolas", 10),
                 bg=BG, fg=MUTED).pack(side="right", anchor="n", pady=10)

        toolbar = ttk.Frame(self.root, padding=(24, 0, 24, 16))
        toolbar.grid(row=1, column=0, sticky="ew")
        self.run_button = ttk.Button(toolbar, text="▶  Ejecutar  F5", command=self._run,
                                     style="Primary.TButton")
        self.run_button.pack(side="left", padx=(0, 8))
        self.step_button = ttk.Button(toolbar, text="Paso a paso  F10", command=self._step)
        self.step_button.pack(side="left", padx=(0, 8))
        self.pause_button = ttk.Button(toolbar, text="Pausar", command=self._pause, state="disabled")
        self.pause_button.pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Reiniciar", command=self._reset).pack(side="left")
        self.example_choice = ttk.Combobox(toolbar, values=list(EXAMPLES), state="readonly", width=23)
        self.example_choice.set("Cargar ejemplo…")
        self.example_choice.pack(side="right")
        self.example_choice.bind("<<ComboboxSelected>>", self._example)
        ttk.Button(toolbar, text="Guía", command=self._help).pack(side="right", padx=8)

        body = ttk.Frame(self.root, padding=(24, 0, 24, 0))
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2, minsize=400)
        body.rowconfigure(0, weight=1)
        editor_card = tk.Frame(body, bg="white", highlightbackground="#dce1ea", highlightthickness=1)
        editor_card.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        self.file_label = tk.Label(editor_card, text="CÓDIGO · sin guardar", anchor="w",
                                   font=("Segoe UI", 10, "bold"), bg="white", fg=INK, padx=15, pady=13)
        self.file_label.pack(fill="x")
        editor_frame = tk.Frame(editor_card, bg="white")
        editor_frame.pack(fill="both", expand=True)
        self.gutter = tk.Canvas(editor_frame, width=45, bg="#f8fafc", highlightthickness=0)
        self.gutter.pack(side="left", fill="y")
        scrollbar = ttk.Scrollbar(editor_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        self.editor = tk.Text(editor_frame, font=("Consolas", 12), bg="white", fg=INK,
                              insertbackground=ACCENT, selectbackground="#c7d2fe", undo=True,
                              wrap="none", borderwidth=0, padx=10, pady=10, width=48,
                              spacing1=2, spacing3=2, height=1)
        self.editor.pack(fill="both", expand=True)
        self.editor.configure(yscrollcommand=lambda first, last: self._editor_scroll(scrollbar, first, last))
        scrollbar.config(command=self.editor.yview)
        horizontal = ttk.Scrollbar(editor_card, orient="horizontal", command=self.editor.xview)
        horizontal.pack(fill="x")
        self.editor.configure(xscrollcommand=horizontal.set)
        tk.Label(editor_card, text="; comentario     etiqueta:     MOV AX, 10", anchor="w",
                 font=("Consolas", 9), bg="#f8fafc", fg=MUTED, padx=14, pady=10).pack(fill="x")
        for tag, color in (("opcode", ACCENT), ("register", "#0369a1"),
                           ("number", "#b45309"), ("label", "#0f766e"), ("comment", "#8491a5")):
            self.editor.tag_configure(tag, foreground=color)
        self.editor.tag_configure("current", background="#fef3c7")
        self.editor.tag_configure("executed", background="#e0e7ff")
        self.editor.tag_configure("error", background="#fee2e2")
        self.editor.bind("<<Modified>>", self._edited)
        self.editor.bind("<Configure>", lambda event: self._draw_lines())
        self.editor.bind("<Tab>", self._insert_spaces)

        state_card = tk.Frame(body, bg="white", highlightbackground="#dce1ea", highlightthickness=1)
        state_card.grid(row=0, column=1, sticky="nsew")
        tk.Label(state_card, text="ESTADO DE LA CPU", anchor="w", font=("Segoe UI", 10, "bold"),
                 bg="white", fg=INK, padx=15, pady=13).pack(fill="x")
        self.register_table = ttk.Treeview(state_card, columns=("name", "decimal", "signed", "hex"),
                                           show="headings", height=8, selectmode="none")
        for name, title, width in (("name", "Registro", 76), ("decimal", "Sin signo", 88),
                                   ("signed", "Con signo", 88), ("hex", "Hex", 86)):
            self.register_table.heading(name, text=title)
            self.register_table.column(name, width=width, minwidth=65, anchor="center")
        self.register_table.pack(fill="x", padx=14)
        self.register_table.tag_configure("changed", background="#e0e7ff", foreground="#3730a3")
        self.register_table.tag_configure("even", background="#f8fafc")
        for register in REGISTERS:
            self.register_table.insert("", "end", iid=register, values=(register, 0, 0, "0x0000"))
        tk.Label(state_card, text="BANDERAS", font=("Segoe UI", 9, "bold"), bg="white", fg=MUTED,
                 anchor="w").pack(fill="x", padx=16, pady=(12, 6))
        flags_frame = tk.Frame(state_card, bg="white")
        flags_frame.pack(fill="x", padx=14)
        self.flag_labels = {}
        for flag, caption in (("ZF", "Cero"), ("CF", "Acarreo"), ("SF", "Signo"), ("OF", "Desborde")):
            item = tk.Frame(flags_frame, bg="white")
            item.pack(side="left", fill="x", expand=True)
            label = tk.Label(item, text=f"{flag}  0", font=("Consolas", 13, "bold"),
                             bg="#f1f5f9", fg=MUTED, pady=6)
            label.pack(fill="x", padx=3)
            tk.Label(item, text=caption, font=("Segoe UI", 9), bg="white", fg=MUTED).pack(pady=4)
            self.flag_labels[flag] = label
        self.position_label = tk.Label(state_card, text="", justify="left", anchor="w",
                                       font=("Segoe UI", 10), bg="white", fg=MUTED, padx=16, pady=10)
        self.position_label.pack(fill="x", side="bottom")

        history_frame = ttk.Frame(self.root, padding=(24, 14, 24, 0))
        history_frame.grid(row=3, column=0, sticky="ew")
        ttk.Label(history_frame, text="HISTORIAL DE EJECUCIÓN", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 6))
        log_frame = tk.Frame(history_frame, bg="#172033")
        log_frame.pack(fill="x")
        log_scroll = ttk.Scrollbar(log_frame)
        log_scroll.pack(side="right", fill="y")
        self.log = tk.Text(log_frame, height=4, font=("Consolas", 10), bg="#172033", fg="#dce6f5",
                           borderwidth=0, padx=12, pady=10, wrap="word", state="disabled",
                           yscrollcommand=log_scroll.set)
        self.log.pack(fill="x")
        log_scroll.configure(command=self.log.yview)
        self.status = tk.Label(self.root, text="Listo para ejecutar.", anchor="w", font=("Segoe UI", 10),
                               bg=BG, fg=MUTED, padx=24, pady=13)
        self.status.grid(row=4, column=0, sticky="ew")

    def _editor_scroll(self, scrollbar, first, last):
        scrollbar.set(first, last)
        self._draw_lines()

    def _draw_lines(self):
        self.gutter.delete("all")
        index = self.editor.index("@0,0")
        while True:
            info = self.editor.dlineinfo(index)
            if info is None:
                break
            self.gutter.create_text(34, info[1], anchor="ne", text=index.split(".")[0],
                                    font=("Consolas", 12), fill="#94a3b8")
            index = self.editor.index(f"{index}+1line")

    def _insert_spaces(self, event):
        if not self.running:
            self.editor.insert("insert", "    ")
        return "break"

    def _source(self):
        return self.editor.get("1.0", "end-1c")

    def _edited(self, event=None):
        if not self.editor.edit_modified():
            return
        self.editor.edit_modified(False)
        if self.highlight_id:
            self.root.after_cancel(self.highlight_id)
        self.highlight_id = self.root.after(120, self._highlight)
        if self.loaded_source is not None and self._source() != self.loaded_source:
            self._status("Código modificado. La próxima ejecución empezará desde cero.")
            for tag in ("current", "executed", "error"):
                self.editor.tag_remove(tag, "1.0", "end")
        self._file_title()

    def _highlight(self):
        self.highlight_id = None
        source = self._source()
        for tag in ("opcode", "register", "number", "label", "comment"):
            self.editor.tag_remove(tag, "1.0", "end")
        patterns = {
            "opcode": r"\b(?:" + "|".join(SIGNATURES) + r")\b",
            "register": r"\b(?:" + "|".join(REGISTERS) + r")\b",
            "number": r"(?<!\w)[+-]?(?:0x[0-9a-f]+|0b[01]+|[0-9a-f]+h|\d+)\b",
            "label": r"\b[A-Za-z_]\w*(?=:)",
            "comment": r";[^\n]*",
        }
        for tag, pattern in patterns.items():
            for match in re.finditer(pattern, source, re.IGNORECASE):
                self.editor.tag_add(tag, f"1.0+{match.start()}c", f"1.0+{match.end()}c")
        self.editor.tag_raise("comment")
        self._draw_lines()

    def _status(self, text, error=False):
        self.status.config(text=text, fg="#b91c1c" if error else MUTED)

    def _file_title(self):
        name = self.file_path.name if self.file_path else "sin guardar"
        changed = " *" if self._source() != self.saved_source else ""
        self.file_label.config(text=f"CÓDIGO · {name}{changed}")

    def _set_source(self, source, path=None):
        self._pause(announce=False)
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", source)
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        self.file_path = path
        self.saved_source = source
        self._reset()
        self._highlight()
        self._file_title()

    def _prepare(self):
        source = self._source()
        if source == self.loaded_source:
            return True
        try:
            self.cpu.load(source)
        except AssemblyError as error:
            self.editor.tag_remove("error", "1.0", "end")
            if error.line:
                self.editor.tag_add("error", f"{error.line}.0", f"{error.line}.end+1c")
                self.editor.see(f"{error.line}.0")
            self._status(str(error), error=True)
            return False
        self.loaded_source = source
        self.history.clear()
        self._refresh()
        return True

    def _execute_one(self):
        before = dict(self.cpu.registers)
        instruction = self.cpu.step()
        if instruction:
            changes = ", ".join(f"{name}={value}" for name, value in self.cpu.registers.items()
                                if before[name] != value)
            flags = " ".join(f"{name}={int(value)}" for name, value in self.cpu.flags.items())
            self.history.append(f"{self.cpu.steps:04d} · L{instruction.line:02d}  "
                                f"{instruction.source}  →  {changes or 'sin cambios en registros'}  |  {flags}")

    def _step(self):
        if self.running or not self._prepare():
            return
        if self.cpu.halted:
            self._status("Programa finalizado. Pulsa Reiniciar para ejecutarlo de nuevo.")
            return
        self._execute_one()
        self._refresh()
        self._status("Programa finalizado." if self.cpu.halted else "Paso ejecutado. La siguiente instrucción está en amarillo.")

    def _run(self):
        if self.running or not self._prepare():
            return
        if self.cpu.halted:
            self._status("Programa finalizado. Pulsa Reiniciar para ejecutarlo de nuevo.")
            return
        self.running = True
        self.run_steps = 0
        self._controls()
        self._status("Ejecutando…")
        self.after_id = self.root.after(1, self._run_batch)

    def _run_batch(self):
        self.after_id = None
        if not self.running:
            return
        for _ in range(100):
            if self.cpu.halted or self.run_steps >= LIMIT:
                break
            self._execute_one()
            self.run_steps += 1
        self._refresh()
        if self.cpu.halted:
            self._pause(announce=False)
            self._status(f"Programa finalizado · {self.cpu.steps} instrucciones ejecutadas.")
        elif self.run_steps >= LIMIT:
            self._pause(announce=False)
            self._status("Pausa automática: 10 000 instrucciones. Revisa si hay un bucle infinito; el estado se conserva.", error=True)
        else:
            self.after_id = self.root.after(10, self._run_batch)

    def _controls(self):
        state = "disabled" if self.running else "normal"
        self.editor.config(state=state)
        self.run_button.config(state=state)
        self.step_button.config(state=state)
        self.example_choice.config(state="disabled" if self.running else "readonly")
        self.pause_button.config(state="normal" if self.running else "disabled")

    def _pause(self, announce=True):
        was_running = self.running
        self.running = False
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self._controls()
        if announce and was_running:
            self._status("Ejecución pausada. Puedes continuar con Ejecutar o Paso a paso.")

    def _reset(self):
        self._pause(announce=False)
        self.cpu = Emulator()
        self.loaded_source = None
        self.history.clear()
        self._refresh()
        self._status("Listo para ejecutar. Registros y banderas en cero.")

    def _refresh(self):
        for i, (name, value) in enumerate(self.cpu.registers.items()):
            previous = self.register_table.item(name, "values")
            changed = previous and int(previous[1]) != value
            self.register_table.item(name, values=(name, value, signed(value), f"0x{value:04X}"),
                                     tags=("changed" if changed else "even" if i % 2 == 0 else "",))
        for name, value in self.cpu.flags.items():
            self.flag_labels[name].config(text=f"{name}  {int(value)}",
                                          bg="#e0e7ff" if value else "#f1f5f9",
                                          fg=ACCENT if value else MUTED)
        instruction = self.cpu.current_instruction
        position = f"Siguiente: línea {instruction.line}" if instruction else (
            "Programa finalizado" if self.cpu.halted else "Sin programa cargado")
        self.position_label.config(text=f"{self.cpu.steps} instrucciones ejecutadas\n{position}")
        for tag in ("current", "executed", "error"):
            self.editor.tag_remove(tag, "1.0", "end")
        if self.cpu.last_instruction:
            line = self.cpu.last_instruction.line
            self.editor.tag_add("executed", f"{line}.0", f"{line}.end+1c")
        if instruction:
            self.editor.tag_add("current", f"{instruction.line}.0", f"{instruction.line}.end+1c")
            self.editor.tag_raise("current")
            self.editor.see(f"{instruction.line}.0")
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("1.0", "\n".join(self.history) if self.history else
                        "El historial aparecerá aquí. Se conservan las últimas 250 instrucciones.")
        self.log.see("end")
        self.log.config(state="disabled")

    def _confirm_discard(self):
        if self._source() == self.saved_source:
            return True
        answer = messagebox.askyesnocancel("Cambios sin guardar", "¿Quieres guardar los cambios del código?", parent=self.root)
        return self._save() if answer else answer is False

    def _new(self):
        self._pause()
        if self._confirm_discard():
            self._set_source("; Escribe tu programa aquí\nMOV AX, 0\nHLT\n")

    def _open(self):
        self._pause()
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(parent=self.root, title="Abrir programa",
                                          filetypes=[("Ensamblador", "*.asm"), ("Texto", "*.txt"), ("Todos los archivos", "*.*")])
        if path:
            self._open_path(Path(path))

    def _open_path(self, path):
        try:
            source = Path(path).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            messagebox.showerror("No se pudo abrir", str(error), parent=self.root)
            return
        self._set_source(source, Path(path))

    def _save(self, save_as=False):
        path = self.file_path if not save_as else None
        if path is None:
            selected = filedialog.asksaveasfilename(parent=self.root, title="Guardar programa", defaultextension=".asm",
                                                    filetypes=[("Ensamblador", "*.asm"), ("Texto", "*.txt")])
            if not selected:
                return False
            path = Path(selected)
        try:
            path.write_text(self._source(), encoding="utf-8")
        except OSError as error:
            messagebox.showerror("No se pudo guardar", str(error), parent=self.root)
            return False
        self.file_path = path
        self.saved_source = self._source()
        self._file_title()
        self._status(f"Guardado: {path.name}")
        return True

    def _example(self, event=None):
        filename = EXAMPLES.get(self.example_choice.get())
        if filename and self._confirm_discard():
            try:
                source = (BASE_DIR / "examples" / filename).read_text(encoding="utf-8")
            except (OSError, UnicodeError) as error:
                messagebox.showerror("No se pudo cargar el ejemplo", str(error), parent=self.root)
            else:
                self._set_source(source)
        self.example_choice.set("Cargar ejemplo…")

    def _help(self):
        window = tk.Toplevel(self.root)
        window.title("Guía de instrucciones")
        window.geometry("740x610")
        window.minsize(570, 400)
        window.configure(bg="white")
        text = tk.Text(window, wrap="word", font=("Segoe UI", 11), padx=24, pady=20, borderwidth=0,
                       bg="white", fg=INK)
        scroll = ttk.Scrollbar(window, command=text.yview)
        scroll.pack(side="right", fill="y")
        text.configure(yscrollcommand=scroll.set)
        text.pack(fill="both", expand=True)
        text.insert("1.0", HELP_TEXT)
        text.configure(state="disabled")

    def _close(self):
        self._pause()
        if self._confirm_discard():
            if self.highlight_id:
                self.root.after_cancel(self.highlight_id)
            self.root.destroy()


HELP_TEXT = """GUÍA DEL EMULADOR

Registros de 16 bits
AX, BX, CX, DX, SI, DI, BP y SP. Todos empiezan en 0. Cada valor se muestra sin signo (0 a 65535), con signo (-32768 a 32767) y en hexadecimal.

Sintaxis
MOV AX, 10      ; comentario
ADD AX, BX
CMP AX, 15
JGE destino
destino:
HLT

No se distinguen mayúsculas y minúsculas. Separa operandos con coma. Usa etiquetas para los saltos; pueden estar en la misma línea que una instrucción. Números: 15, -2, 0xFF, FFh o 0b1010.

Movimiento y aritmética
MOV destino, valor: copia un número o registro.
ADD / SUB destino, valor: suma o resta.
INC / DEC registro: suma o resta 1, conservando CF.
NEG registro: cambia el signo.
CMP registro, valor: compara como una resta, sin modificar registros.

Operaciones bit a bit
AND / OR / XOR registro, valor.
NOT registro: invierte los 16 bits, sin cambiar banderas.
TEST registro, valor: calcula AND solo para actualizar las banderas.

Saltos (usan las banderas de la última operación que las cambió)
JMP etiqueta: siempre salta.
JC / JB: CF=1. JNC / JAE: CF=0.
JE / JZ: ZF=1. JNE / JNZ: ZF=0.
Con signo: JG (>), JGE (≥), JL (<), JLE (≤).
Sin signo: JA (>), JAE (≥), JB (<), JBE (≤).
JO / JNO: OF=1 / OF=0. JS / JNS: SF=1 / SF=0.
LOOP etiqueta: resta 1 a CX y salta si CX no es 0; conserva las banderas.
NOP: no hace nada. HLT: termina el programa.

Banderas
ZF: el resultado es cero.
CF: acarreo en una suma o préstamo en una resta.
SF: el bit más alto del resultado es 1 (negativo con signo).
OF: el resultado aritmético no cabe en el intervalo con signo.
JGE comprueba SF=OF; JC comprueba CF=1.

Ejecución
F5 ejecuta; F10 avanza una instrucción; Escape pausa.
Amarillo: próxima instrucción. Violeta: última ejecutada o registro cambiado.
Reiniciar pone todo en cero y conserva el código. Tras editar, la siguiente ejecución empieza desde cero. Cada ejecución completa se pausa a las 10 000 instrucciones si no termina; puedes continuar o reiniciar.

Alcance
Es un subconjunto educativo inspirado en x86. No incluye memoria, pila, interrupciones, directivas, registros de 8/32/64 bits ni ejecutables nativos. BP y SP funcionan como registros generales. Los resultados se ajustan a 16 bits (65535 + 1 = 0). HLT es opcional: llegar al final también termina.
"""


def main():
    parser = argparse.ArgumentParser(description="Emulador educativo de ensamblador de 16 bits")
    parser.add_argument("archivo", nargs="?", type=Path, help="Programa .asm para abrir")
    parser.add_argument("--cli", action="store_true", help="Ejecutar en consola, sin ventana")
    parser.add_argument("--max-steps", type=int, default=LIMIT, help="Límite de instrucciones en consola")
    args = parser.parse_args()
    if args.cli:
        if not args.archivo:
            parser.error("--cli necesita un archivo .asm")
        if args.max_steps < 1:
            parser.error("--max-steps debe ser mayor que cero")
        cpu = Emulator()
        try:
            cpu.load(args.archivo.read_text(encoding="utf-8-sig"))
            cpu.run(args.max_steps)
        except (OSError, UnicodeError, AssemblyError, ExecutionLimitError) as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        print("REGISTRO  SIN SIGNO  CON SIGNO  HEXADECIMAL")
        for name, value in cpu.registers.items():
            print(f"{name:<8}  {value:>9}  {signed(value):>9}  0x{value:04X}")
        print("Banderas: " + "  ".join(f"{name}={int(value)}" for name, value in cpu.flags.items()))
        print(f"Instrucciones ejecutadas: {cpu.steps}")
        return 0
    root = tk.Tk()
    EmulatorApp(root, args.archivo)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
