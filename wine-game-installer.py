#!/usr/bin/env python3
"""
Wine Game Installer
A GUI tool to install Windows games on Steam Deck using Wine,
with automatic vcrun2022 setup and optional Steam shortcut creation.
"""

import os
import sys
import subprocess
import threading
import time
import json
import struct
import re
import shutil
import urllib.request
import tarfile
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ── Paths ────────────────────────────────────────────────────────────────────
HOME = Path.home()
GAMES_DIR = HOME / "Games"
WINE_RUNNER = (
    HOME / ".var/app/net.lutris.Lutris/data/lutris/runners/wine"
    / "wine-staging-11.2-x86_64/bin/wine"
)
WINETRICKS_BIN = (
    HOME / ".var/app/net.lutris.Lutris/data/lutris/runners/wine"
    / "wine-staging-11.2-x86_64/bin/winetricks"
)
STEAM_COMPAT_TOOLS = HOME / ".steam/root/compatibilitytools.d"
STEAM_USERDATA = HOME / ".steam/root/userdata"
STEAM_CONFIG = HOME / ".steam/root/config"

# ── Colors & Fonts ───────────────────────────────────────────────────────────
BG = "#0f0f14"
BG2 = "#16161e"
BG3 = "#1e1e2a"
ACCENT = "#7c6af7"
ACCENT2 = "#a89cf7"
GREEN = "#4ade80"
YELLOW = "#facc15"
RED = "#f87171"
TEXT = "#e2e8f0"
TEXT2 = "#94a3b8"
BORDER = "#2a2a3e"

FONT_TITLE = ("JetBrains Mono", 13, "bold")
FONT_LABEL = ("JetBrains Mono", 10)
FONT_SMALL = ("JetBrains Mono", 9)
FONT_LOG = ("JetBrains Mono", 9)
FONT_BTN = ("JetBrains Mono", 10, "bold")
FONT_MONO = ("JetBrains Mono", 10)


def find_wine():
    """Find wine binary from Lutris runners."""
    runners_dir = HOME / ".var/app/net.lutris.Lutris/data/lutris/runners/wine"
    if not runners_dir.exists():
        return None
    # Prefer wine-staging, then wine-ge
    for pattern in ["wine-staging-*", "wine-ge-*", "lutris-*"]:
        matches = sorted(runners_dir.glob(pattern), reverse=True)
        for m in matches:
            wine = m / "bin" / "wine"
            if wine.exists():
                return wine
    return None


def find_winetricks():
    """Find winetricks binary."""
    # Check flatpak lutris
    runners_dir = HOME / ".var/app/net.lutris.Lutris/data/lutris/runners/wine"
    if runners_dir.exists():
        for d in sorted(runners_dir.iterdir(), reverse=True):
            wt = d / "bin" / "winetricks"
            if wt.exists():
                return wt
    # Check system
    result = shutil.which("winetricks")
    if result:
        return Path(result)
    return None


class AnimatedDots:
    """Animates '....' suffix on a label."""
    def __init__(self, label, base_text):
        self.label = label
        self.base_text = base_text
        self.running = False
        self.step = 0

    def start(self):
        self.running = True
        self.step = 0
        self._tick()

    def stop(self):
        self.running = False
        self.label.config(text=self.base_text)

    def _tick(self):
        if not self.running:
            return
        dots = "." * self.step
        self.label.config(text=f"{self.base_text}{dots}")
        self.step = (self.step + 1) % 4
        self.label.after(500, self._tick)


class WineInstaller(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Wine Game Installer")
        self.geometry("780x680")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(700, 580)

        self.wine_path = find_wine()
        self.winetricks_path = find_winetricks()

        self.setup_exe = tk.StringVar()
        self.slug = tk.StringVar()
        self.game_exe = tk.StringVar()

        self._install_thread = None
        self._dots_anim = None

        self._build_ui()
        self._check_deps()

    # ── UI Construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=BG, pady=16)
        header.pack(fill="x", padx=24)

        tk.Label(header, text="⬡ WINE GAME INSTALLER",
                 font=("JetBrains Mono", 16, "bold"),
                 fg=ACCENT, bg=BG).pack(side="left")

        tk.Label(header, text="Steam Deck Edition",
                 font=FONT_SMALL, fg=TEXT2, bg=BG).pack(side="left", padx=12, pady=4)

        # Separator
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=24)

        # Main content
        content = tk.Frame(self, bg=BG, padx=24, pady=16)
        content.pack(fill="both", expand=True)

        # ── Step 1: Setup EXE ──
        self._section_label(content, "01", "INSTALLER")
        self._file_row(content, "Installer (.exe)", self.setup_exe,
                       self._browse_setup, "Select setup or installer .exe")

        # ── Step 2: Slug ──
        self._section_label(content, "02", "GAME FOLDER NAME  (slug)")
        slug_frame = tk.Frame(content, bg=BG)
        slug_frame.pack(fill="x", pady=(0, 4))

        slug_entry = tk.Entry(slug_frame, textvariable=self.slug,
                              bg=BG3, fg=TEXT, insertbackground=ACCENT,
                              font=FONT_MONO, bd=0, highlightthickness=1,
                              highlightbackground=BORDER,
                              highlightcolor=ACCENT, relief="flat")
        slug_entry.pack(fill="x", ipady=8, padx=2)
        self.slug.trace_add("write", self._on_slug_change)

        tk.Label(content, text="e.g.  clair-obscur-33  →  will install to ~/Games/clair-obscur-33/",
                 font=FONT_SMALL, fg=TEXT2, bg=BG).pack(anchor="w", pady=(0, 8))

        # ── Install path hint ──
        self._section_label(content, "03", "INSTALL PATH  (copy into the installer window)")
        hint_frame = tk.Frame(content, bg=BG3, pady=10, padx=12,
                              highlightthickness=1, highlightbackground=BORDER)
        hint_frame.pack(fill="x", pady=(0, 12))

        self.path_hint_var = tk.StringVar(value=r"C:\Program Files\<slug>")
        path_label = tk.Label(hint_frame, textvariable=self.path_hint_var,
                              font=("JetBrains Mono", 10), fg=YELLOW, bg=BG3)
        path_label.pack(side="left")

        copy_btn = tk.Button(hint_frame, text="⧉ Copy",
                             font=FONT_SMALL, fg=ACCENT, bg=BG3,
                             activeforeground=ACCENT2, activebackground=BG3,
                             bd=0, cursor="hand2",
                             command=self._copy_path)
        copy_btn.pack(side="left", padx=12)

        self.copy_confirm = tk.Label(hint_frame, text="", font=FONT_SMALL,
                                     fg=GREEN, bg=BG3)
        self.copy_confirm.pack(side="left")

        # ── Install button ──
        btn_frame = tk.Frame(content, bg=BG)
        btn_frame.pack(fill="x", pady=(4, 12))

        self.install_btn = tk.Button(
            btn_frame, text="▶  INSTALL",
            font=FONT_BTN, fg=BG, bg=ACCENT,
            activeforeground=BG, activebackground=ACCENT2,
            bd=0, padx=24, pady=10, cursor="hand2",
            command=self._start_install
        )
        self.install_btn.pack(side="left")

        self.status_label = tk.Label(btn_frame, text="", font=FONT_LABEL,
                                     fg=TEXT2, bg=BG)
        self.status_label.pack(side="left", padx=16)

        # ── Log ──
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=24)
        log_outer = tk.Frame(self, bg=BG, padx=24, pady=12)
        log_outer.pack(fill="both", expand=True)

        tk.Label(log_outer, text="LOG", font=FONT_SMALL, fg=TEXT2, bg=BG).pack(anchor="w")

        log_frame = tk.Frame(log_outer, bg=BG2,
                             highlightthickness=1, highlightbackground=BORDER)
        log_frame.pack(fill="both", expand=True, pady=(4, 0))

        self.log = tk.Text(log_frame, bg=BG2, fg=TEXT, font=FONT_LOG,
                           bd=0, relief="flat", state="disabled",
                           wrap="word", padx=10, pady=8,
                           insertbackground=ACCENT)
        self.log.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(log_frame, command=self.log.yview,
                                 bg=BG3, troughcolor=BG2,
                                 activebackground=ACCENT)
        scrollbar.pack(side="right", fill="y")
        self.log.config(yscrollcommand=scrollbar.set)

        # Color tags
        self.log.tag_config("ok", foreground=GREEN)
        self.log.tag_config("warn", foreground=YELLOW)
        self.log.tag_config("err", foreground=RED)
        self.log.tag_config("info", foreground=ACCENT2)
        self.log.tag_config("dim", foreground=TEXT2)

        # ── Steam shortcut section (hidden initially) ──
        self.steam_frame = tk.Frame(self, bg=BG, padx=24, pady=12)
        # Not packed yet — shown after install completes

        tk.Frame(self.steam_frame, bg=BORDER, height=1).pack(fill="x", pady=(0, 12))
        tk.Label(self.steam_frame,
                 text="04  ›  STEAM SHORTCUT",
                 font=FONT_TITLE, fg=ACCENT, bg=BG).pack(anchor="w", pady=(0, 8))

        self._file_row(self.steam_frame, "Game executable (.exe)",
                       self.game_exe, self._browse_game_exe,
                       "Select the game's main .exe")

        steam_btn_frame = tk.Frame(self.steam_frame, bg=BG)
        steam_btn_frame.pack(fill="x", pady=(8, 0))

        self.add_steam_btn = tk.Button(
            steam_btn_frame, text="⊕  Add to Steam",
            font=FONT_BTN, fg=BG, bg=GREEN,
            activeforeground=BG, activebackground="#86efac",
            bd=0, padx=20, pady=9, cursor="hand2",
            command=self._add_to_steam
        )
        self.add_steam_btn.pack(side="left")

        skip_btn = tk.Button(
            steam_btn_frame, text="Skip →",
            font=FONT_BTN, fg=TEXT2, bg=BG3,
            activeforeground=TEXT, activebackground=BORDER,
            bd=0, padx=16, pady=9, cursor="hand2",
            command=self._skip_steam
        )
        skip_btn.pack(side="left", padx=12)

    def _section_label(self, parent, num, title):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill="x", pady=(10, 4))
        tk.Label(f, text=num, font=("JetBrains Mono", 9, "bold"),
                 fg=ACCENT, bg=BG).pack(side="left")
        tk.Label(f, text=f"  ›  {title}",
                 font=("JetBrains Mono", 9, "bold"),
                 fg=TEXT2, bg=BG).pack(side="left")

    def _file_row(self, parent, label_text, var, cmd, placeholder):
        frame = tk.Frame(parent, bg=BG)
        frame.pack(fill="x", pady=(0, 6))

        entry = tk.Entry(frame, textvariable=var,
                         bg=BG3, fg=TEXT, insertbackground=ACCENT,
                         font=FONT_MONO, bd=0, highlightthickness=1,
                         highlightbackground=BORDER,
                         highlightcolor=ACCENT, relief="flat")
        entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(2, 8))

        btn = tk.Button(frame, text="Browse",
                        font=FONT_SMALL, fg=ACCENT, bg=BG3,
                        activeforeground=ACCENT2, activebackground=BORDER,
                        bd=0, padx=12, pady=8, cursor="hand2",
                        highlightthickness=1, highlightbackground=BORDER,
                        command=cmd)
        btn.pack(side="right")

    # ── Callbacks ────────────────────────────────────────────────────────────

    def _on_slug_change(self, *_):
        s = self.slug.get().strip()
        if s:
            self.path_hint_var.set(rf"C:\Program Files\{s}")
        else:
            self.path_hint_var.set(r"C:\Program Files\<slug>")

    def _copy_path(self):
        path = self.path_hint_var.get()
        self.clipboard_clear()
        self.clipboard_append(path)
        self.copy_confirm.config(text="✓ Copied!")
        self.after(2000, lambda: self.copy_confirm.config(text=""))

    def _browse_setup(self):
        path = filedialog.askopenfilename(
            title="Select installer .exe",
            filetypes=[("Executables", "*.exe"), ("All files", "*.*")],
            initialdir=str(HOME / "Downloads")
        )
        if path:
            self.setup_exe.set(path)

    def _browse_game_exe(self):
        slug = self.slug.get().strip()
        initial = str(GAMES_DIR / slug / "drive_c" / "Program Files") if slug else str(GAMES_DIR)
        path = filedialog.askopenfilename(
            title="Select game .exe",
            filetypes=[("Executables", "*.exe"), ("All files", "*.*")],
            initialdir=initial
        )
        if path:
            self.game_exe.set(path)

    # ── Dependency check ─────────────────────────────────────────────────────

    def _check_deps(self):
        if not self.wine_path:
            self._log("⚠  Wine not found in Lutris runners. Install Lutris + Wine runner first.", "warn")
        else:
            self._log(f"✓  Wine: {self.wine_path}", "ok")

        if not self.winetricks_path:
            self._log("⚠  Winetricks not found — vcrun2022 install will be skipped.", "warn")
        else:
            self._log(f"✓  Winetricks: {self.winetricks_path}", "ok")

    # ── Logging ──────────────────────────────────────────────────────────────

    def _log(self, msg, tag=None):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n", tag or "")
        self.log.see("end")
        self.log.config(state="disabled")

    def _set_status(self, text, color=TEXT2):
        self.status_label.config(text=text, fg=color)

    # ── Install flow ─────────────────────────────────────────────────────────

    def _start_install(self):
        setup = self.setup_exe.get().strip()
        slug = self.slug.get().strip()

        if not setup:
            messagebox.showerror("Missing field", "Please select an installer .exe")
            return
        if not slug:
            messagebox.showerror("Missing field", "Please enter a slug (folder name)")
            return
        if not Path(setup).exists():
            messagebox.showerror("File not found", f"Cannot find:\n{setup}")
            return
        if not self.wine_path:
            messagebox.showerror("Wine not found",
                                 "No Wine runner found.\nInstall Lutris and download a Wine runner.")
            return

        self.install_btn.config(state="disabled")
        self._install_thread = threading.Thread(target=self._run_install,
                                                args=(setup, slug), daemon=True)
        self._install_thread.start()

    def _run_install(self, setup, slug):
        prefix = GAMES_DIR / slug
        env = os.environ.copy()
        env["WINEPREFIX"] = str(prefix)
        env["WINEDLLOVERRIDES"] = "dxgi=b;d3d11=b;d3d10core=b;d3d9=b"
        wine = str(self.wine_path)

        # 1. Create prefix
        self._log(f"\n── Creating prefix: {prefix}", "info")
        GAMES_DIR.mkdir(parents=True, exist_ok=True)
        prefix.mkdir(parents=True, exist_ok=True)

        # 2. wineboot
        self._log("── Initializing Wine prefix (wineboot)...", "info")
        ret = subprocess.run([wine, "wineboot"], env=env,
                             capture_output=True, text=True)
        if ret.returncode != 0:
            self._log(f"wineboot stderr: {ret.stderr[:300]}", "dim")
        self._log("✓  Prefix initialized", "ok")

        # 3. vcrun2022
        if self.winetricks_path:
            self._log("── Installing vcrun2022...", "info")
            wt_env = env.copy()
            wt_env["WINEPREFIX"] = str(prefix)
            ret = subprocess.run(
                [str(self.winetricks_path), "-q", "vcrun2022"],
                env=wt_env, capture_output=True, text=True
            )
            if ret.returncode == 0:
                self._log("✓  vcrun2022 installed", "ok")
            else:
                self._log("⚠  vcrun2022 install may have failed (non-critical)", "warn")
                self._log(ret.stderr[:200], "dim")
        else:
            self._log("⚠  Skipping vcrun2022 (winetricks not found)", "warn")

        # 4. Launch installer & wait
        self._log(f"\n── Launching installer: {Path(setup).name}", "info")
        self._log(f"   Install path to use in installer window:", "dim")
        self._log(f"   C:\\Program Files\\{slug}", "warn")
        self._log("", "")

        # Start animated status
        self.after(0, self._start_waiting_anim)

        proc = subprocess.Popen([wine, setup], env=env)
        pid = proc.pid
        self._log(f"   Installer PID: {pid}", "dim")

        proc.wait()

        self.after(0, self._stop_waiting_anim)
        self._log("\n✓  Installer closed", "ok")

        # Done
        self.after(0, self._install_done, slug)

    def _start_waiting_anim(self):
        self._set_status("", TEXT2)
        self._dots_anim = AnimatedDots(self.status_label,
                                       "Waiting for installer to complete")
        self._dots_anim.start()

    def _stop_waiting_anim(self):
        if self._dots_anim:
            self._dots_anim.stop()
            self._dots_anim = None

    def _install_done(self, slug):
        self._set_status("✓  Installation complete", GREEN)
        self._log("── Base installation done.", "ok")
        self._log("── You can now add a Steam shortcut below.", "info")
        self.install_btn.config(state="normal")
        self.steam_frame.pack(fill="x", before=None)
        # Show steam section at bottom
        self.steam_frame.pack(fill="x", padx=0, pady=0)

    # ── Steam shortcut ───────────────────────────────────────────────────────

    def _add_to_steam(self):
        exe = self.game_exe.get().strip()
        slug = self.slug.get().strip()

        if not exe:
            messagebox.showerror("Missing field", "Please select the game .exe")
            return
        if not Path(exe).exists():
            messagebox.showerror("File not found", f"Cannot find:\n{exe}")
            return

        threading.Thread(target=self._run_add_steam,
                         args=(exe, slug), daemon=True).start()

    def _run_add_steam(self, exe, slug):
        self._log("\n── Steam shortcut setup...", "info")

        # Check / install GE-Proton
        ge_version = self._ensure_ge_proton()

        # Add shortcut
        self._write_steam_shortcut(exe, slug, ge_version)

    def _ensure_ge_proton(self):
        """Check latest GE-Proton, install if missing. Returns version string."""
        self._log("── Checking GE-Proton latest release...", "info")
        try:
            url = "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": "WineGameInstaller/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            tag = data["tag_name"]  # e.g. GE-Proton10-4
            self._log(f"   Latest: {tag}", "dim")
        except Exception as e:
            self._log(f"⚠  Could not fetch GE-Proton info: {e}", "warn")
            # Return whatever is installed
            return self._find_installed_ge_proton()

        install_dir = STEAM_COMPAT_TOOLS / tag
        if install_dir.exists():
            self._log(f"✓  {tag} already installed", "ok")
            return tag

        # Download
        self._log(f"── Downloading {tag}...", "info")
        try:
            assets = data.get("assets", [])
            tar_url = next(
                (a["browser_download_url"] for a in assets
                 if a["name"].endswith(".tar.gz")), None
            )
            if not tar_url:
                raise ValueError("No .tar.gz asset found")

            tmp = Path("/tmp") / f"{tag}.tar.gz"
            self._log(f"   URL: {tar_url}", "dim")

            def progress(count, block, total):
                if total > 0:
                    pct = min(100, count * block * 100 // total)
                    self.after(0, self._set_status,
                               f"Downloading GE-Proton... {pct}%", ACCENT2)

            urllib.request.urlretrieve(tar_url, tmp, reporthook=progress)

            self._log(f"── Extracting to {STEAM_COMPAT_TOOLS}...", "info")
            STEAM_COMPAT_TOOLS.mkdir(parents=True, exist_ok=True)
            with tarfile.open(tmp, "r:gz") as tf:
                tf.extractall(STEAM_COMPAT_TOOLS)
            tmp.unlink(missing_ok=True)
            self._log(f"✓  {tag} installed", "ok")
            return tag

        except Exception as e:
            self._log(f"⚠  GE-Proton download failed: {e}", "warn")
            return self._find_installed_ge_proton()

    def _find_installed_ge_proton(self):
        """Find newest installed GE-Proton version."""
        if not STEAM_COMPAT_TOOLS.exists():
            return None
        versions = sorted(
            [d.name for d in STEAM_COMPAT_TOOLS.iterdir()
             if d.is_dir() and "GE-Proton" in d.name],
            reverse=True
        )
        return versions[0] if versions else None

    def _write_steam_shortcut(self, exe, slug, ge_version):
        """Write entry to Steam shortcuts.vdf."""
        self._log("── Writing Steam shortcut...", "info")

        # Find shortcuts.vdf
        shortcuts_path = self._find_shortcuts_vdf()
        if not shortcuts_path:
            self._log("⚠  Could not find Steam shortcuts.vdf", "warn")
            self._log("   Start Steam at least once to generate user data.", "dim")
            self.after(0, self._steam_done, False)
            return

        try:
            # Read existing
            if shortcuts_path.exists():
                with open(shortcuts_path, "rb") as f:
                    data = f.read()
                shortcuts = self._parse_vdf_shortcuts(data)
            else:
                shortcuts = {}

            # New entry ID
            new_id = max((int(k) for k in shortcuts.keys()), default=-1) + 1

            # Launch options
            launch_opts = ""
            if ge_version:
                launch_opts = f"STEAM_COMPAT_TOOL_REQUESTS={ge_version} %command%"

            entry = {
                "appid": str(self._gen_appid(exe)),
                "AppName": slug.replace("-", " ").title(),
                "Exe": f'"{exe}"',
                "StartDir": f'"{str(Path(exe).parent)}"',
                "icon": "",
                "ShortcutPath": "",
                "LaunchOptions": launch_opts,
                "IsHidden": "0",
                "AllowDesktopConfig": "1",
                "AllowOverlay": "1",
                "OpenVR": "0",
                "Devkit": "0",
                "DevkitGameID": "",
                "LastPlayTime": "0",
                "tags": {},
            }

            shortcuts[str(new_id)] = entry

            # Write back
            shortcuts_path.parent.mkdir(parents=True, exist_ok=True)
            with open(shortcuts_path, "wb") as f:
                f.write(self._write_vdf_shortcuts(shortcuts))

            self._log(f"✓  Shortcut added: {entry['AppName']}", "ok")
            if ge_version:
                self._log(f"✓  GE-Proton set: {ge_version}", "ok")
            self._log("   Restart Steam to see the new shortcut.", "info")
            self.after(0, self._steam_done, True)

        except Exception as e:
            self._log(f"✗  Failed to write shortcut: {e}", "err")
            self.after(0, self._steam_done, False)

    def _find_shortcuts_vdf(self):
        """Find shortcuts.vdf in Steam userdata."""
        if STEAM_USERDATA.exists():
            for user_dir in STEAM_USERDATA.iterdir():
                if user_dir.is_dir():
                    path = user_dir / "config" / "shortcuts.vdf"
                    return path
        # Fallback
        alt = HOME / ".local/share/Steam/userdata"
        if alt.exists():
            for user_dir in alt.iterdir():
                if user_dir.is_dir():
                    return user_dir / "config" / "shortcuts.vdf"
        return None

    def _gen_appid(self, exe):
        """Generate a stable app ID from exe path."""
        import hashlib
        h = hashlib.md5(exe.encode()).hexdigest()
        return int(h[:8], 16) & 0x7FFFFFFF

    def _parse_vdf_shortcuts(self, data):
        """Minimal VDF binary parser for shortcuts."""
        # Returns dict of id -> dict of fields
        shortcuts = {}
        try:
            i = 0
            # Skip header "\x00shortcuts\x00"
            while i < len(data) and data[i:i+11] != b'\x00shortcuts':
                i += 1
            i += 11  # skip "\x00shortcuts"
            if i < len(data) and data[i] == 0:
                i += 1  # skip NUL after key

            while i < len(data):
                if data[i] == 0x08:  # end of map
                    break
                if data[i] != 0x00:  # sub-object
                    break
                i += 1  # skip type byte 0x00

                # Read key (entry index as string)
                key_end = data.index(b'\x00', i)
                key = data[i:key_end].decode('utf-8', errors='replace')
                i = key_end + 1

                entry = {}
                while i < len(data):
                    if data[i] == 0x08:  # end of sub-object
                        i += 1
                        break
                    vtype = data[i]
                    i += 1
                    name_end = data.index(b'\x00', i)
                    name = data[i:name_end].decode('utf-8', errors='replace')
                    i = name_end + 1

                    if vtype == 0x02:  # int32
                        val = struct.unpack_from('<I', data, i)[0]
                        entry[name] = str(val)
                        i += 4
                    elif vtype == 0x01:  # string
                        val_end = data.index(b'\x00', i)
                        entry[name] = data[i:val_end].decode('utf-8', errors='replace')
                        i = val_end + 1
                    elif vtype == 0x00:  # sub-object (tags)
                        entry[name] = {}
                        while i < len(data) and data[i] != 0x08:
                            i += 1
                        i += 1
                    else:
                        break

                shortcuts[key] = entry
        except Exception:
            pass
        return shortcuts

    def _write_vdf_shortcuts(self, shortcuts):
        """Write shortcuts dict back to VDF binary format."""
        out = bytearray()
        out += b'\x00shortcuts\x00'
        for idx, (key, entry) in enumerate(shortcuts.items()):
            out += b'\x00' + key.encode() + b'\x00'
            for field, val in entry.items():
                if isinstance(val, dict):
                    out += b'\x00' + field.encode() + b'\x00'
                    out += b'\x08'
                elif isinstance(val, str):
                    try:
                        int_val = int(val)
                        out += b'\x02' + field.encode() + b'\x00'
                        out += struct.pack('<I', int_val & 0xFFFFFFFF)
                    except ValueError:
                        out += b'\x01' + field.encode() + b'\x00'
                        out += val.encode('utf-8') + b'\x00'
            out += b'\x08'
        out += b'\x08\x08'
        return bytes(out)

    def _steam_done(self, success):
        if success:
            self._set_status("✓  Done! Restart Steam.", GREEN)
        else:
            self._set_status("⚠  Shortcut failed — see log", YELLOW)

    def _skip_steam(self):
        self._log("\n── Steam shortcut skipped.", "dim")
        self._set_status("✓  Done!", GREEN)
        self.steam_frame.pack_forget()


if __name__ == "__main__":
    app = WineInstaller()
    app.mainloop()
