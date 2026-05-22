"""
review-launcher — Desktop GUI launcher (tkinter, zero external deps).

Opens a native window to configure and launch the review tool.
After initial setup, the review server runs in background and config
can be changed via the web UI at /settings.

Usage:
    python review/launcher.py
"""

import argparse
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# When packaged with PyInstaller, PROJECT_ROOT points inside the bundle
IS_FROZEN = getattr(sys, "frozen", False)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9090)
    return parser.parse_known_args(argv[1:])[0]


ARGS = _parse_args(sys.argv)

if not ARGS.serve:
    try:
        import tkinter as tk
        from tkinter import ttk, scrolledtext
    except ImportError:
        print("错误: tkinter 不可用。请安装 python-tk 包。")
        print("  macOS: 已预装，无需额外操作")
        print("  Ubuntu/Debian: sudo apt install python3-tk")
        print("  Windows: 已预装")
        sys.exit(1)

CONFIG_FILE = Path.home() / ".review" / "config.json"
DEFAULT_CONFIG = {
    "api_key": "", "model": "deepseek-v4-flash",
    "host": "127.0.0.1", "port": 9090,
    "repo_path": ".", "commit_hash": "", "api_type": "deepseek",
    "log_dir": "",
}


def load_config() -> dict:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            return {**DEFAULT_CONFIG, **data}
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> dict:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    merged = {**DEFAULT_CONFIG, **cfg}
    CONFIG_FILE.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
    return merged


class LauncherApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Review 启动器")
        self.root.geometry("560x640")
        self.root.resizable(False, False)
        self.root.configure(bg="#f5f6fa")

        cfg = load_config()
        self._log_file: Path | None = None
        self._setup_log_file(cfg)
        self._build_ui(cfg)
        self._running = False

    def _setup_log_file(self, cfg: dict):
        d = cfg.get("log_dir") or str(Path.home() / ".review" / "logs")
        p = Path(d).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        self._log_file = p / "launcher.log"

    def _build_ui(self, cfg: dict):
        root = self.root
        pad = 16

        # Title
        title = tk.Label(root, text="⚡ Review 启动器", font=("Segoe UI", 18, "bold"),
                         bg="#f5f6fa", fg="#2c3e50")
        title.pack(pady=(pad, 4))

        subtitle = tk.Label(root, text="配置参数，一键启动服务", font=("Segoe UI", 11),
                            bg="#f5f6fa", fg="#7f8c8d")
        subtitle.pack(pady=(0, pad))

        # Main frame
        main = tk.Frame(root, bg="#fff", highlightbackground="#e0e0e0",
                        highlightthickness=1, padx=pad, pady=pad)
        main.pack(fill="x", padx=pad, pady=(0, pad // 2))

        def add_field(parent, label, row, col, colspan=1, is_password=False, is_select=False, options=None):
            lbl = tk.Label(parent, text=label, font=("Segoe UI", 10, "bold"),
                           bg="#fff", fg="#555", anchor="w")
            lbl.grid(row=row, column=col, sticky="w", pady=(8, 2), padx=(0, 8),
                     columnspan=colspan)

            if is_select:
                var = tk.StringVar()
                w = ttk.Combobox(parent, textvariable=var, values=options, state="readonly",
                                 font=("Segoe UI", 10))
                w.grid(row=row + 1, column=col, sticky="ew", padx=(0, 8 * (colspan - 1)),
                       columnspan=colspan, ipady=2)
                return var
            else:
                var = tk.StringVar()
                show = "*" if is_password else None
                w = tk.Entry(parent, textvariable=var, font=("Segoe UI", 10),
                             show=show, relief="solid", bd=1)
                w.grid(row=row + 1, column=col, sticky="ew", padx=(0, 8 * (colspan - 1)),
                       columnspan=colspan, ipady=2)
                return var

        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)
        main.grid_columnconfigure(2, weight=1)

        self.api_type_var = add_field(main, "API 类型", 0, 0, is_select=True, options=["deepseek", "anthropic"])
        self.api_key_var = add_field(main, "API Key", 0, 1, colspan=2, is_password=True)

        self.model_var = add_field(main, "模型", 2, 0)
        self.host_var = add_field(main, "Host", 2, 1)
        self.port_var = add_field(main, "端口", 2, 2)

        self.repo_var = add_field(main, "仓库路径", 4, 0, colspan=2)
        self.commit_var = add_field(main, "Commit Hash (可选)", 4, 2)

        self.log_dir_var = add_field(main, "日志目录 (留空默认 ~/.review/logs/)", 6, 0, colspan=3)

        # Set values from config
        self.api_type_var.set(cfg.get("api_type", "deepseek"))
        self.api_key_var.set(cfg.get("api_key", ""))
        self.model_var.set(cfg.get("model", "deepseek-v4-flash"))
        self.host_var.set(cfg.get("host", "127.0.0.1"))
        self.port_var.set(str(cfg.get("port", 9090)))
        self.repo_var.set(cfg.get("repo_path", "."))
        self.commit_var.set(cfg.get("commit_hash", ""))
        self.log_dir_var.set(cfg.get("log_dir", ""))

        # Buttons
        btn_frame = tk.Frame(root, bg="#f5f6fa")
        btn_frame.pack(fill="x", padx=pad, pady=(8, 4))

        self.launch_btn = tk.Button(btn_frame, text="⚡ 一键启动", font=("Segoe UI", 12, "bold"),
                                    bg="#27ae60", fg="white", relief="flat", padx=24, pady=6,
                                    cursor="hand2", activebackground="#219a52", activeforeground="white",
                                    command=self._do_launch)
        self.launch_btn.pack(side="left", padx=(0, 8))

        self.save_btn = tk.Button(btn_frame, text="保存配置", font=("Segoe UI", 10),
                                  bg="#3498db", fg="white", relief="flat", padx=16, pady=6,
                                  cursor="hand2", activebackground="#2980b9", activeforeground="white",
                                  command=self._do_save)
        self.save_btn.pack(side="left")

        tk.Button(btn_frame, text="关闭服务", font=("Segoe UI", 10),
                  bg="#e74c3c", fg="white", relief="flat", padx=14, pady=6,
                  cursor="hand2", activebackground="#c0392b", activeforeground="white",
                  command=self._do_shutdown
                  ).pack(side="right")

        # Log output
        log_frame = tk.Frame(root, bg="#f5f6fa")
        log_frame.pack(fill="both", expand=True, padx=pad, pady=(8, pad))

        log_label = tk.Label(log_frame, text="启动日志", font=("Segoe UI", 10, "bold"),
                             bg="#f5f6fa", fg="#555", anchor="w")
        log_label.pack(fill="x", pady=(0, 4))

        self.log_area = scrolledtext.ScrolledText(log_frame, font=("SF Mono", 10),
                                                   bg="#1e1e2e", fg="#cdd6f4",
                                                   relief="flat", bd=0, height=10,
                                                   wrap="word", state="disabled")
        self.log_area.pack(fill="both", expand=True)

        # Status bar at bottom
        self.status_var = tk.StringVar(value="就绪")
        status_bar = tk.Label(root, textvariable=self.status_var, font=("Segoe UI", 10),
                              bg="#f8f9fa", fg="#7f8c8d", anchor="w", padx=pad, pady=6,
                              relief="solid", bd=0, highlightbackground="#e8e8e8", highlightthickness=1)
        status_bar.pack(fill="x", side="bottom")

    def _log(self, msg: str, tag: str = ""):
        self.log_area.configure(state="normal")
        self.log_area.insert("end", msg + "\n", tag)
        self.log_area.see("end")
        self.log_area.configure(state="disabled")
        if self._log_file:
            try:
                with open(self._log_file, "a", encoding="utf-8") as f:
                    import datetime
                    f.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")
            except OSError:
                pass

    def _get_config(self) -> dict:
        return {
            "api_type": self.api_type_var.get(),
            "api_key": self.api_key_var.get(),
            "model": self.model_var.get(),
            "host": self.host_var.get(),
            "port": int(self.port_var.get() or 9090),
            "repo_path": self.repo_var.get() or ".",
            "commit_hash": self.commit_var.get(),
            "log_dir": self.log_dir_var.get(),
        }

    def _do_save(self):
        cfg = self._get_config()
        save_config(cfg)
        self.status_var.set("✓ 配置已保存")

    def _do_shutdown(self):
        import tkinter.messagebox as mb
        if not mb.askyesno("关闭服务", "确定要关闭 Review 服务吗？"):
            return
        cfg = self._get_config()
        host = cfg.get("host", "127.0.0.1")
        port = cfg.get("port", 9090)
        import urllib.request
        try:
            req = urllib.request.Request(f"http://{host}:{port}/api/shutdown", method="POST")
            urllib.request.urlopen(req, timeout=5)
            self._log("✓ 关闭请求已发送", "success")
            self.status_var.set("✓ 服务已关闭")
        except Exception as e:
            self._log(f"✗ 关闭失败: {e}", "error")
            self.status_var.set("✗ 关闭失败")

    def _do_launch(self):
        if self._running:
            return
        self._running = True
        self.launch_btn.configure(state="disabled", text="⏳ 启动中...")
        self.save_btn.configure(state="disabled")
        self.log_area.configure(state="normal")
        self.log_area.delete("1.0", "end")
        self.log_area.configure(state="disabled")
        self.status_var.set("⏳ 正在安装依赖...")

        cfg = self._get_config()
        save_config(cfg)
        self._setup_log_file(cfg)
        threading.Thread(target=self._run_pipeline, args=(cfg,), daemon=True).start()

    def _run_pipeline(self, cfg: dict):
        env = dict(os.environ)
        if cfg.get("api_key"):
            key_var = "DEEPSEEK_API_KEY" if cfg.get("api_type") != "anthropic" else "ANTHROPIC_API_KEY"
            env[key_var] = cfg["api_key"]
        env["REVIEW_LOG_DIR"] = cfg.get("log_dir", "")
        web_ui = PROJECT_ROOT / "web-ui"

        def run(cmd, cwd, timeout=120, label="") -> bool:
            self.root.after(0, lambda: self._log(f"→ {label}"))
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env)
                if r.returncode != 0:
                    err = r.stderr[-500:] if r.stderr.strip() else r.stdout[-500:]
                    self.root.after(0, lambda: self._log(f"✗ {label} 失败: {err}", "error"))
                    return False
                self.root.after(0, lambda: self._log(f"✓ {label} 完成", "success"))
                return True
            except subprocess.TimeoutExpired:
                self.root.after(0, lambda: self._log(f"✗ {label} 超时", "error"))
                return False
            except FileNotFoundError:
                self.root.after(0, lambda: self._log(f"✗ {label}: 找不到命令", "error"))
                return False

        if not IS_FROZEN:
            # Phase 1: pip install (only in development mode)
            if not run([sys.executable, "-m", "pip", "install", "-e", "."],
                       str(PROJECT_ROOT), label="pip install"):
                self.root.after(0, self._finish_fail, "pip install 失败")
                return

            # Phase 2: npm install + build (only in development mode)
            if web_ui.exists() and (web_ui / "package.json").exists():
                if not run(["npm", "install"], str(web_ui), label="npm install"):
                    self.root.after(0, self._finish_fail, "npm install 失败")
                    return
                if not run(["npm", "run", "build"], str(web_ui), label="npm run build"):
                    self.root.after(0, self._finish_fail, "前端构建失败")
                    return
        else:
            self.root.after(0, lambda: self._log("✓ 已打包模式，跳过依赖安装"))

        # Phase 3: start daemon
        host = cfg.get("host", "127.0.0.1")
        port = cfg.get("port", 9090)
        self.root.after(0, lambda: self._log(f"→ 启动 review server {host}:{port} ..."))

        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, port)) == 0:
                self.root.after(0, lambda: self._log(f"✗ 端口 {port} 已被占用", "error"))
                self.root.after(0, self._finish_fail, f"端口 {port} 已被占用")
                return

        if IS_FROZEN:
            launch_cmd = [sys.executable, "--serve", "--host", host, "--port", str(port)]
        else:
            launch_cmd = [sys.executable, "-m", "review.launcher", "--serve", "--host", host, "--port", str(port)]

        subprocess.Popen(
            launch_cmd,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True, env=env,
        )
        self.root.after(0, lambda: self._log(f"✓ review server 已启动", "success"))
        self.root.after(0, self._finish_success, host, port)

    def _finish_success(self, host: str, port: int):
        self._running = False
        self.launch_btn.configure(state="normal", text="⚡ 一键启动")
        self.save_btn.configure(state="normal")
        self.status_var.set(f"✓ 启动完成! http://{host}:{port}/timeline")

        import tkinter.messagebox as mb
        mb.showinfo("启动成功",
                    f"Review 服务已启动!\n\n"
                    f"  访问: http://{host}:{port}/timeline\n\n"
                    f"  后续配置在网页的「设置」中进行\n"
                    f"  终端可以关闭此窗口")

    def _finish_fail(self, reason: str):
        self._running = False
        self.launch_btn.configure(state="normal", text="⚡ 一键启动")
        self.save_btn.configure(state="normal")
        self.status_var.set(f"✗ 启动失败: {reason}")

        import tkinter.messagebox as mb
        mb.showerror("启动失败", f"启动失败:\n{reason}\n\n请检查后重试")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    if ARGS.serve:
        from review.web.server import start_server

        start_server(host=ARGS.host, port=ARGS.port)
    else:
        LauncherApp().run()
