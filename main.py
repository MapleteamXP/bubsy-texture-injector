"""
main.py — Bubsy 3D Texture Injector GUI Entry Point.

A Windows .exe GUI application for injecting textures into PS1 Bubsy 3D ROMs.
Supports drag-and-drop ROM loading, selectable texture packs, preview,
dry-run mode, backup/restore, and progress tracking.

To build as .exe:
    pip install -r requirements.txt
    build.bat
"""

import os
import sys
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path

# Ensure our modules are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import BuildConfig, get_build_by_name, detect_build_from_iso
from rom_parser import open_ps1_image
from pack_manager import load_pack, list_available_packs, PackInfo
from injector import TextureInjector, InjectionResult
from color_mapper import ColorMapper, load_color_manifest


# ── Constants ──
APP_NAME = "Bubsy 3D Texture Injector"
APP_VERSION = "1.0.0"
PACKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "packs")


# ── GUI Application ──
class TextureInjectorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1000x750")
        self.root.minsize(900, 650)

        # State
        self.iso_path: str = ""
        self.selected_pack: PackInfo | None = None
        self.packs: list[PackInfo] = []
        self.detected_build = "Unknown"
        self.color_mapper: ColorMapper | None = None

        self._build_ui()
        self._scan_packs()

    # ── UI Construction ──
    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10, "italic"))
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"))

        # Main container with padding
        main = ttk.Frame(self.root, padding="10")
        main.pack(fill=tk.BOTH, expand=True)

        # === HEADER ===
        header = ttk.Frame(main)
        header.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header, text="🐱 Bubsy 3D Texture Injector", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(header, text="PS1 ROM Texture Enhancement Tool", style="Subtitle.TLabel").pack(side=tk.LEFT, padx=(10, 0))

        # === ROM SECTION ===
        rom_frame = ttk.LabelFrame(main, text="Step 1: Load Bubsy 3D ROM", padding="10")
        rom_frame.pack(fill=tk.X, pady=(0, 10))

        rom_row = ttk.Frame(rom_frame)
        rom_row.pack(fill=tk.X)

        self.rom_entry = ttk.Entry(rom_row, state="readonly")
        self.rom_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        ttk.Button(rom_row, text="📂 Browse…", command=self._browse_rom).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(rom_row, text="🔍 Analyze", command=self._analyze_rom).pack(side=tk.LEFT)

        # ROM info display
        self.rom_info = ttk.Label(rom_frame, text="No ROM loaded. Supported: .iso, .bin/.cue", foreground="gray")
        self.rom_info.pack(anchor=tk.W, pady=(5, 0))

        # === PACK SECTION ===
        pack_frame = ttk.LabelFrame(main, text="Step 2: Select Texture Pack", padding="10")
        pack_frame.pack(fill=tk.X, pady=(0, 10))

        pack_top = ttk.Frame(pack_frame)
        pack_top.pack(fill=tk.X)

        ttk.Label(pack_top, text="Available Packs:").pack(side=tk.LEFT)
        ttk.Button(pack_top, text="🔄 Refresh", command=self._scan_packs).pack(side=tk.RIGHT)

        # Pack list with scrollbar
        pack_list_frame = ttk.Frame(pack_frame)
        pack_list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        scrollbar = ttk.Scrollbar(pack_list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.pack_listbox = tk.Listbox(
            pack_list_frame,
            yscrollcommand=scrollbar.set,
            height=4,
            font=("Consolas", 10),
            selectmode=tk.SINGLE,
        )
        self.pack_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.pack_listbox.yview)
        self.pack_listbox.bind("<<ListboxSelect>>", self._on_pack_select)

        # Pack details
        self.pack_details = ttk.Label(pack_frame, text="Select a pack to view details", wraplength=900, foreground="gray")
        self.pack_details.pack(anchor=tk.W, pady=(5, 0))

        # === COLOR MAPPING SECTION ===
        color_frame = ttk.LabelFrame(main, text="Step 3: Color-to-Texture Mapping (Smart Injection)", padding="10")
        color_frame.pack(fill=tk.X, pady=(0, 10))

        self.color_status = ttk.Label(color_frame, text="Load a ROM and select a pack to enable smart color mapping", foreground="gray")
        self.color_status.pack(anchor=tk.W)

        color_btn_row = ttk.Frame(color_frame)
        color_btn_row.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(color_btn_row, text="🎨 Preview Color Map", command=self._preview_color_map).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(color_btn_row, text="⚙️ Configure Mapping", command=self._open_color_config).pack(side=tk.LEFT)

        # === OPTIONS SECTION ===
        opts_frame = ttk.LabelFrame(main, text="Options", padding="10")
        opts_frame.pack(fill=tk.X, pady=(0, 10))

        opts_grid = ttk.Frame(opts_frame)
        opts_grid.pack(fill=tk.X)

        # Dry run
        self.dry_run_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts_grid, text="Dry Run (preview only, no changes)", variable=self.dry_run_var).grid(row=0, column=0, sticky=tk.W, padx=(0, 20))

        # Backup
        self.backup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts_grid, text="Create .bak backup", variable=self.backup_var).grid(row=0, column=1, sticky=tk.W)

        # Texture size
        ttk.Label(opts_grid, text="Texture Size:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.texture_size = ttk.Combobox(opts_grid, values=[64, 128, 256], width=8, state="readonly")
        self.texture_size.set(128)
        self.texture_size.grid(row=1, column=1, sticky=tk.W, pady=(5, 0))

        # Color depth
        ttk.Label(opts_grid, text="Color Depth:").grid(row=2, column=0, sticky=tk.W, pady=(5, 0))
        self.color_depth = ttk.Combobox(opts_grid, values=["4bpp", "8bpp", "16bpp"], width=8, state="readonly")
        self.color_depth.set("16bpp")
        self.color_depth.grid(row=2, column=1, sticky=tk.W, pady=(5, 0))

        # === ACTION BUTTONS ===
        action_frame = ttk.Frame(main)
        action_frame.pack(fill=tk.X, pady=(0, 10))

        self.inject_btn = ttk.Button(
            action_frame,
            text="🚀 INJECT TEXTURES",
            command=self._run_injection,
            style="Action.TButton",
        )
        self.inject_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.inject_btn.state(["disabled"])

        ttk.Button(action_frame, text="💾 Save Color Map Config", command=self._save_color_config).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_frame, text="📋 Load Color Map Config", command=self._load_color_config).pack(side=tk.LEFT)

        # === PROGRESS ===
        prog_frame = ttk.LabelFrame(main, text="Progress", padding="10")
        prog_frame.pack(fill=tk.X, pady=(0, 10))

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(prog_frame, variable=self.progress_var, maximum=100, mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))

        self.status_label = ttk.Label(prog_frame, text="Ready")
        self.status_label.pack(anchor=tk.W)

        # === LOG CONSOLE ===
        log_frame = ttk.LabelFrame(main, text="Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            height=12,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.insert(tk.END, "Welcome to Bubsy 3D Texture Injector!\n")
        self.log_text.insert(tk.END, "Load a ROM, select a texture pack, and click INJECT!\n")
        self.log_text.config(state=tk.DISABLED)

    # ── Actions ──
    def _log(self, msg: str):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _set_status(self, msg: str):
        self.status_label.config(text=msg)
        self.root.update_idletasks()

    def _browse_rom(self):
        path = filedialog.askopenfilename(
            title="Select Bubsy 3D ROM",
            filetypes=[
                ("PS1 Disc Images", "*.iso *.bin *.cue"),
                ("ISO files", "*.iso"),
                ("BIN files", "*.bin"),
                ("CUE files", "*.cue"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.iso_path = path
            self.rom_entry.config(state="normal")
            self.rom_entry.delete(0, tk.END)
            self.rom_entry.insert(0, path)
            self.rom_entry.config(state="readonly")
            self.rom_info.config(text=f"Selected: {os.path.basename(path)}", foreground="green")
            self._log(f"ROM selected: {path}")
            self._analyze_rom()

    def _analyze_rom(self):
        if not self.iso_path or not os.path.exists(self.iso_path):
            messagebox.showwarning("No ROM", "Please select a ROM file first.")
            return

        try:
            self._set_status("Analyzing ROM...")
            parser = open_ps1_image(self.iso_path)
            file_count = len(parser.files)
            volume = parser.volume_label or "(no label)"

            # Detect build
            self.detected_build = detect_build_from_iso(parser)

            info_text = f"Volume: {volume} | Files: {file_count} | Detected: {self.detected_build}"
            self.rom_info.config(text=info_text, foreground="blue")
            self._log(f"ROM Analysis — Volume: {volume}, Files: {file_count}, Build: {self.detected_build}")

            # List some files for debugging
            tmd_files = [f for f in parser.list_files() if f.upper().endswith(".TMD")]
            tim_files = [f for f in parser.list_files() if f.upper().endswith(".TIM")]
            self._log(f"  Found {len(tmd_files)} TMD files, {len(tim_files)} TIM files")
            for f in tmd_files[:5]:
                self._log(f"    TMD: {f}")
            for f in tim_files[:5]:
                self._log(f"    TIM: {f}")

            self._update_inject_button()
            self._set_status("ROM analyzed. Select a texture pack.")

        except Exception as e:
            self._log(f"ERROR analyzing ROM: {e}")
            self.rom_info.config(text=f"Error: {e}", foreground="red")
            self._set_status("Analysis failed")

    def _scan_packs(self):
        self.pack_listbox.delete(0, tk.END)
        self.packs = list_available_packs(PACKS_DIR)
        for pack in self.packs:
            self.pack_listbox.insert(tk.END, f"{pack.name} v{pack.version} — {pack.author}")
        if not self.packs:
            self.pack_listbox.insert(tk.END, "(No packs found — add packs to the /packs folder)")
        self._log(f"Scanned {len(self.packs)} texture packs from {PACKS_DIR}")

    def _on_pack_select(self, event):
        selection = self.pack_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx >= len(self.packs):
            return
        self.selected_pack = self.packs[idx]
        pack = self.selected_pack
        details = (
            f"Name: {pack.name}\n"
            f"Version: {pack.version}\n"
            f"Author: {pack.author}\n"
            f"Target: {pack.target_game} ({', '.join(pack.target_builds)})\n"
            f"Description: {pack.description}\n"
            f"Path: {pack.base_dir}"
        )
        self.pack_details.config(text=details, foreground="black")
        self._log(f"Selected pack: {pack.name} v{pack.version}")

        # Initialize color mapper if we have a color manifest
        color_manifest_path = os.path.join(pack.base_dir, "color_manifest.json")
        if os.path.exists(color_manifest_path):
            try:
                self.color_mapper = ColorMapper(pack.base_dir, color_manifest_path)
                self.color_status.config(
                    text=f"✅ Color mapper loaded: {len(self.color_mapper.color_map)} surface types configured",
                    foreground="green"
                )
            except Exception as e:
                self.color_status.config(text=f"⚠️ Color manifest error: {e}", foreground="orange")
        else:
            self.color_status.config(text="ℹ️ No color manifest found — pack uses manual texture mapping only", foreground="gray")

        self._update_inject_button()

    def _update_inject_button(self):
        if self.iso_path and self.selected_pack:
            self.inject_btn.state(["!disabled"])
        else:
            self.inject_btn.state(["disabled"])

    def _preview_color_map(self):
        if not self.color_mapper:
            messagebox.showinfo("No Color Map", "Select a pack with a color manifest first.")
            return
        if not self.iso_path:
            messagebox.showinfo("No ROM", "Load a ROM first.")
            return

        # Open preview window
        preview = tk.Toplevel(self.root)
        preview.title("Color-to-Texture Mapping Preview")
        preview.geometry("700x500")

        ttk.Label(preview, text="Detected Polygon Colors → Texture Assignments", font=("Segoe UI", 12, "bold")).pack(pady=10)

        text = scrolledtext.ScrolledText(preview, wrap=tk.WORD, font=("Consolas", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        try:
            parser = open_ps1_image(self.iso_path)
            # Scan TMDs for colors
            tmd_files = [f for f in parser.list_files() if f.upper().endswith(".TMD")]
            report = self.color_mapper.preview_mapping(parser, tmd_files)
            text.insert(tk.END, report)
        except Exception as e:
            text.insert(tk.END, f"ERROR: {e}")

    def _open_color_config(self):
        if not self.color_mapper:
            messagebox.showinfo("No Color Map", "Select a pack with a color manifest first.")
            return

        cfg = tk.Toplevel(self.root)
        cfg.title("Color Mapping Configuration")
        cfg.geometry("600x500")

        ttk.Label(cfg, text="Adjust color ranges and texture assignments", font=("Segoe UI", 11, "bold")).pack(pady=10)

        canvas = tk.Canvas(cfg)
        scrollbar = ttk.Scrollbar(cfg, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for surface, mapping in self.color_mapper.color_map.items():
            frame = ttk.LabelFrame(scroll_frame, text=surface, padding=5)
            frame.pack(fill=tk.X, padx=10, pady=5)

            cr = mapping.get("color_range", {})
            ttk.Label(frame, text=f"R: {cr.get('r', '?')}  G: {cr.get('g', '?')}  B: {cr.get('b', '?')}").pack(anchor=tk.W)
            ttk.Label(frame, text=f"Textures: {', '.join(mapping.get('textures', []))}").pack(anchor=tk.W)

    def _save_color_config(self):
        if not self.color_mapper:
            messagebox.showinfo("No Color Map", "Nothing to save.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="color_config.json",
        )
        if path:
            with open(path, "w") as f:
                json.dump(self.color_mapper.color_map, f, indent=2)
            self._log(f"Color config saved: {path}")

    def _load_color_config(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            try:
                self.color_mapper = ColorMapper(os.path.dirname(path), path)
                self._log(f"Color config loaded: {path}")
            except Exception as e:
                self._log(f"ERROR loading config: {e}")

    def _run_injection(self):
        if not self.iso_path or not self.selected_pack:
            return

        # Disable UI during run
        self.inject_btn.state(["disabled"])
        self.progress_var.set(0)
        self._set_status("Starting injection...")
        self._log("=" * 50)
        self._log("INJECTION STARTED")
        self._log(f"ROM: {self.iso_path}")
        self._log(f"Pack: {self.selected_pack.name}")
        self._log(f"Dry Run: {self.dry_run_var.get()}")
        self._log("=" * 50)

        # Run in thread to keep UI responsive
        thread = threading.Thread(target=self._injection_worker, daemon=True)
        thread.start()

    def _injection_worker(self):
        try:
            build_cfg = get_build_by_name(self.detected_build)
            if not build_cfg:
                build_cfg = BuildConfig(name="unknown", preferred_tim_mode=2)

            # Override settings from UI
            bpp_map = {"4bpp": 0, "8bpp": 1, "16bpp": 2}
            build_cfg.preferred_tim_mode = bpp_map.get(self.color_depth.get(), 2)

            injector = TextureInjector(
                iso_path=self.iso_path,
                build_config=build_cfg,
                pack_dir=self.selected_pack.base_dir,
                manifest=self.selected_pack.manifest,
                dry_run=self.dry_run_var.get(),
                progress_callback=self._progress_callback,
            )

            # If we have a color mapper, attach it for smart injection
            if self.color_mapper:
                injector.color_mapper = self.color_mapper

            result = injector.run()

            # Update UI from main thread
            self.root.after(0, self._injection_done, result)

        except Exception as e:
            self.root.after(0, self._injection_error, str(e))

    def _progress_callback(self, current: int, total: int, msg: str):
        def update():
            if total > 0:
                pct = (current / total) * 100
                self.progress_var.set(pct)
            if msg:
                self._set_status(msg)
                self._log(msg)
        self.root.after(0, update)

    def _injection_done(self, result: InjectionResult):
        self.progress_var.set(100)
        self.inject_btn.state(["!disabled"])

        if result.success:
            self._set_status("Injection complete!")
            self._log("=" * 50)
            self._log("INJECTION COMPLETE ✅")
            self._log(f"Targets processed: {result.targets_processed}")
            self._log(f"Patched ISO: {result.patched_iso_path or '(dry run)'}")
            self._log(f"Backup: {result.backup_path or '(none)'}")

            if result.patched_iso_path:
                messagebox.showinfo(
                    "Success! 🎉",
                    f"Texture injection complete!\n\n"
                    f"Patched ROM saved to:\n{result.patched_iso_path}\n\n"
                    f"Backup at:\n{result.backup_path}",
                )
            else:
                messagebox.showinfo(
                    "Dry Run Complete",
                    "Dry run finished. Check the log for details.\n"
                    "Uncheck 'Dry Run' to apply changes for real.",
                )
        else:
            self._set_status("Injection failed!")
            self._log(f"FAILED: {result.message}")
            messagebox.showerror("Injection Failed", result.message)

    def _injection_error(self, msg: str):
        self.progress_var.set(0)
        self.inject_btn.state(["!disabled"])
        self._set_status("Error!")
        self._log(f"ERROR: {msg}")
        messagebox.showerror("Error", msg)


def main():
    root = tk.Tk()
    app = TextureInjectorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
