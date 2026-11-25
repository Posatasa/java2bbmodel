#!/usr/bin/env python3
"""Tkinter window for java2bbmodel."""

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import java2bbmodel as core

LOG_FONT = ("Consolas", 9) if sys.platform == "win32" else ("DejaVu Sans Mono", 9)


def expand_paths(text):
    paths = []
    for part in text.replace("\n", ";").split(";"):
        part = part.strip().strip('"')
        if part:
            paths.append(Path(part))
    return paths


def collect(paths):
    files = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.rglob("*.java")))
        elif path.is_file() and path.suffix.lower() == ".java":
            files.append(path)
    return files


def convert(files, out_dir, y_origin, log, progress=None):
    out_dir.mkdir(parents=True, exist_ok=True)
    used = set()
    done = 0
    for index, path in enumerate(files, 1):
        stem = path.stem
        target = out_dir / (stem + ".bbmodel")
        suffix = 2
        while target.name.lower() in used:
            target = out_dir / ("%s_%d.bbmodel" % (stem, suffix))
            suffix += 1
        used.add(target.name.lower())
        try:
            data, model = core.convert_file(path, y_origin)
        except Exception as error:
            log("失败  %s：%s" % (path.name, error))
        else:
            target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            done += 1
            log("%s  ->  %s" % (path.name, target.name))
            if model.animated:
                log("      跳过动画旋转：%s" % ", ".join(sorted(model.animated)))
        if progress:
            progress(index, len(files))
    return done


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("java2bbmodel")
        self.geometry("780x580")
        self.minsize(660, 480)
        self.queue = queue.Queue()
        self.running = False
        self.output_dir = None
        self.build()
        self.after(80, self.drain)

    def build(self):
        root = ttk.Frame(self, padding=(10, 8))
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)

        ttk.Label(root, text="输入").grid(row=0, column=0, sticky="w")
        self.input_var = tk.StringVar()
        ttk.Entry(root, textvariable=self.input_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(root, text="文件…", width=8, command=self.pick_files).grid(row=0, column=2)
        ttk.Button(root, text="文件夹…", width=9, command=self.pick_folder).grid(row=0, column=3, padx=(4, 0))

        ttk.Label(root, text="输出").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.output_var = tk.StringVar()
        ttk.Entry(root, textvariable=self.output_var).grid(row=1, column=1, sticky="ew", padx=6, pady=(6, 0))
        ttk.Button(root, text="目录…", width=8, command=self.pick_output).grid(row=1, column=2, pady=(6, 0))
        self.open_button = ttk.Button(root, text="打开", width=9, command=self.open_output, state="disabled")
        self.open_button.grid(row=1, column=3, padx=(4, 0), pady=(6, 0))

        options = ttk.Frame(root)
        options.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(10, 4))
        ttk.Label(options, text="Y 基准").pack(side="left")
        self.y_var = tk.StringVar(value="24")
        ttk.Spinbox(options, from_=0, to=64, width=5, textvariable=self.y_var).pack(side="left", padx=(6, 8))
        ttk.Label(options, text="24 = 脚底落在 y=0，0 = 模型挂在 y<0", foreground="#666").pack(side="left")
        self.start_button = ttk.Button(options, text="开始转换", width=12, command=self.start)
        self.start_button.pack(side="right")

        self.log = tk.Text(root, height=18, wrap="none", font=LOG_FONT, state="disabled", background="#1e1e1e",
                           foreground="#dcdcdc", insertbackground="#dcdcdc", relief="flat")
        self.log.grid(row=3, column=0, columnspan=4, sticky="nsew", pady=(8, 0))
        root.rowconfigure(3, weight=1)
        scroll = ttk.Scrollbar(root, orient="vertical", command=self.log.yview)
        scroll.grid(row=3, column=4, sticky="ns", pady=(8, 0))
        self.log.configure(yscrollcommand=scroll.set)

        self.progress = ttk.Progressbar(root, mode="determinate")
        self.progress.grid(row=4, column=0, columnspan=5, sticky="ew", pady=(8, 0))
        self.status = tk.StringVar(value="选择 .java 文件或文件夹")
        ttk.Label(root, textvariable=self.status, foreground="#666").grid(row=5, column=0, columnspan=5,
                                                                          sticky="w", pady=(4, 0))

    def pick_files(self):
        paths = filedialog.askopenfilenames(title="选择模型类", filetypes=[("Java 模型", "*.java"), ("所有文件", "*.*")])
        if paths:
            self.input_var.set(";".join(paths))
            self.suggest_output(Path(paths[0]).parent / "output")
            self.status.set("已选择 %d 个文件" % len(paths))

    def pick_folder(self):
        path = filedialog.askdirectory(title="选择包含 .java 的文件夹")
        if path:
            self.input_var.set(path)
            self.suggest_output(Path(path) / "output")
            self.status.set(path)

    def pick_output(self):
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.output_var.set(path)

    def suggest_output(self, path):
        if not self.output_var.get().strip():
            self.output_var.set(str(path))

    def open_output(self):
        if not self.output_dir or not self.output_dir.exists():
            return
        if sys.platform == "win32":
            os.startfile(str(self.output_dir))
        else:
            subprocess.Popen(["xdg-open", str(self.output_dir)])

    def write(self, line):
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def start(self):
        if self.running:
            return
        paths = expand_paths(self.input_var.get())
        if not paths:
            messagebox.showwarning("java2bbmodel", "先选择 .java 文件或文件夹")
            return
        files = collect(paths)
        if not files:
            messagebox.showwarning("java2bbmodel", "这里没有 .java 文件")
            return
        text = self.output_var.get().strip()
        out_dir = Path(text) if text else paths[0].parent / "output"
        try:
            y_origin = float(self.y_var.get())
        except ValueError:
            messagebox.showwarning("java2bbmodel", "Y 基准要填数字")
            return
        self.output_var.set(str(out_dir))
        self.output_dir = out_dir
        self.clear()
        self.progress.configure(maximum=len(files), value=0)
        self.status.set("正在转换 %d 个文件…" % len(files))
        self.running = True
        self.start_button.configure(state="disabled")
        threading.Thread(target=self.work, args=(files, out_dir, y_origin), daemon=True).start()

    def work(self, files, out_dir, y_origin):
        def log(line):
            self.queue.put(("log", line))

        def progress(index, total):
            self.queue.put(("progress", index, total))

        ok = 0
        try:
            ok = convert(files, out_dir, y_origin, log, progress)
        except Exception as error:
            self.queue.put(("log", "中断：%s" % error))
        self.queue.put(("done", ok, len(files) - ok, str(out_dir)))

    def drain(self):
        try:
            while True:
                message = self.queue.get_nowait()
                if isinstance(message, str):
                    self.write(message)
                elif message[0] == "log":
                    self.write(message[1])
                elif message[0] == "progress":
                    self.progress.configure(value=message[1])
                elif message[0] == "done":
                    _, ok, failed, out_dir = message
                    self.running = False
                    self.start_button.configure(state="normal")
                    self.open_button.configure(state="normal")
                    self.status.set("完成 %d 个，失败 %d 个 -> %s" % (ok, failed, out_dir))
                    self.write("")
                    self.write("--- 完成 %d 个，失败 %d 个 ---" % (ok, failed))
        except queue.Empty:
            pass
        self.after(80, self.drain)


def main():
    try:
        app = App()
    except Exception as error:
        messagebox.showerror("java2bbmodel", "启动失败：%s" % error)
        raise
    app.mainloop()


if __name__ == "__main__":
    main()
