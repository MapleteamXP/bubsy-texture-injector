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
from PIL import Image, ImageTk


# ── Constants ──
APP_NAME = "Bubsy 3D Texture Injector"
APP_VERSION = "1.3.5"
PACKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "packs")


def _load_bubsy_bg(root):
    """Try to load a Bubsy background image."""
    bg_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "bubsy_bg.png"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "bubsy_bg.jpg"),
    ]
    for p in bg_paths:
        if os.path.exists(p):
            try:
                img = Image.open(p)
                # Resize to window size
                img = img.resize((1000, 750), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                label = tk.Label(root, image=photo)
                label.image = photo  # Keep reference
                label.place(x=0, y=0, relwidth=1, relheight=1)
                return label
            except Exception:
                pass
    return None


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
        ttk.Button(rom_row, text="🔍 Analyze", command=self._analyze_rom).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(rom_row, text="🎨 Rip Original TIMs", command=self._rip_original_tims).pack(side=tk.LEFT)

        # ROM info display
        self.rom_info = ttk.Label(rom_frame, text="No ROM loaded. Supported: .iso, .bin/.cue", foreground="gray")
        self.rom_info.pack(anchor=tk.W, pady=(5, 0))

        # === PACK SECTION ===
        pack_frame = ttk.LabelFrame(main, text="Step 2: Select Texture Pack", padding="10")
        pack_frame.pack(fill=tk.X, pady=(0, 10))

        pack_top = ttk.Frame(pack_frame)
        pack_top.pack(fill=tk.X)

        ttk.Label(pack_top, text="Available Packs:").pack(side=tk.LEFT)
        ttk.Button(pack_top, text="➕ Add Pack Folder…", command=self._add_pack_folder).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(pack_top, text="📁 Add Pack Files…", command=self._add_pack_files).pack(side=tk.LEFT, padx=(5, 0))
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

        # === MANUAL TEXTURE OVERRIDE SECTION ===
        manual_frame = ttk.LabelFrame(main, text="🛡️ MANUAL OVERRIDE (Failsafe Mode)", padding="10")
        manual_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(manual_frame, text="When auto-mapping is unsure, YOU decide what texture goes where!", 
                 foreground="#DC143C", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        ttk.Label(manual_frame, text="⚠️ Use this for: checkerboard lava, blue mountains, orange ground — anything the auto-detect got wrong!", 
                 foreground="gray").pack(anchor=tk.W, pady=(0, 5))

        self.manual_tree = ttk.Treeview(manual_frame, columns=("file", "surface", "texture"), show="headings", height=4)
        self.manual_tree.heading("file", text="TMD File")
        self.manual_tree.heading("surface", text="Detected Surface")
        self.manual_tree.heading("texture", text="Assigned Texture")
        self.manual_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        manual_btn_row = ttk.Frame(manual_frame)
        manual_btn_row.pack(fill=tk.X)
        ttk.Button(manual_btn_row, text="🔍 Scan TMD Files", command=self._scan_tmd_manual).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(manual_btn_row, text="📝 Assign Texture", command=self._manual_assign_texture).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(manual_btn_row, text="❌ Clear Overrides", command=self._clear_manual).pack(side=tk.LEFT)

        self.manual_overrides: dict[str, str] = {}  # iso_path -> texture_path

    # ── Manual Override Actions ──
    def _log(self, msg: str):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _set_status(self, msg: str):
        self.status_label.config(text=msg)
        self.root.update_idletasks()

    def _rip_original_tims(self):
        """Extract original TIM textures from the loaded ROM for analysis."""
        if not self.iso_path or not os.path.exists(self.iso_path):
            messagebox.showwarning("No ROM", "Please select a ROM file first.")
            return
        
        # Ask where to save
        output_dir = filedialog.askdirectory(
            title="Select folder to save extracted TIMs",
            initialdir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "extracted_tims")
        )
        if not output_dir:
            return
        
        self._set_status("Ripping original TIM textures...")
        self._log("=" * 50)
        self._log("RIPPING ORIGINAL TIM TEXTURES FROM ROM")
        self._log(f"ROM: {self.iso_path}")
        self._log(f"Output: {output_dir}")
        self._log("=" * 50)
        
        # Run in background thread
        thread = threading.Thread(target=self._rip_tims_worker, args=(output_dir,), daemon=True)
        thread.start()
    
    def _rip_tims_worker(self, output_dir: str):
        """Background worker for TIM extraction."""
        try:
            from extract_tim import extract_tims_from_file, generate_tim_report
            
            total, extracted = extract_tims_from_file(
                self.iso_path,
                output_dir,
                min_size=8,
                max_size=256,
                export_png=True,
                export_tim=True,
            )
            
            # Generate report
            report = generate_tim_report(output_dir)
            report_path = os.path.join(output_dir, "REPORT.txt")
            with open(report_path, "w") as f:
                f.write(report)
            
            # Update UI
            self.root.after(0, lambda: self._on_rip_done(total, extracted, output_dir, report_path))
            
        except Exception as e:
            self.root.after(0, lambda: self._on_rip_error(str(e)))
    
    def _on_rip_done(self, total: int, extracted: int, output_dir: str, report_path: str):
        self._set_status(f"Ripped {extracted} TIMs from ROM")
        self._log(f"✅ Extraction complete!")
        self._log(f"   Found: {total} candidates")
        self._log(f"   Valid TIMs: {extracted}")
        self._log(f"   Output: {output_dir}")
        self._log(f"   Report: {report_path}")
        
        msg = (
            f"Extracted {extracted} original TIM textures!\n\n"
            f"Location: {output_dir}\n"
            f"Report: {report_path}\n\n"
            f"Use these as reference for creating replacement textures:\n"
            f"• Match exact dimensions\n"
            f"• Use same BPP mode (4/8/16)\n"
            f"• Preserve CLUT for indexed textures\n"
            f"• Export as PNG from the .png previews to use as templates"
        )
        messagebox.showinfo("TIMs Ripped! 🎨", msg)
    
    def _on_rip_error(self, msg: str):
        self._set_status("TIM rip failed")
        self._log(f"❌ TIM extraction error: {msg}")
        messagebox.showerror("Extraction Failed", f"Failed to rip TIMs:\n{msg}")
    def _browse_rom(self):
        path = filedialog.askopenfilename(
            title="Select Bubsy 3D ROM",
            filetypes=[
                ("PS1 Disc Images", "*.iso *.bin *.cue *.chd"),
                ("ISO files", "*.iso"),
                ("BIN files", "*.bin"),
                ("CUE files", "*.cue"),
                ("CHD files", "*.chd"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.iso_path = path
            self.rom_entry.config(state="normal")
            self.rom_entry.delete(0, tk.END)
            self.rom_entry.insert(0, path)
            self.rom_entry.config(state="readonly")
            self.rom_info.config(text=f"Selected: {os.path.basename(path)} | Supported formats: .iso, .bin, .cue, .chd", foreground="green")
            self._log(f"ROM selected: {path}")
            self._analyze_rom()

    def _analyze_rom(self):
        if not self.iso_path or not os.path.exists(self.iso_path):
            messagebox.showwarning("No ROM", "Please select a ROM file first.")
            return

        try:
            self._set_status("Analyzing ROM...")
            self._log(f"Opening: {self.iso_path}")
            parser = open_ps1_image(self.iso_path)
            file_count = len(parser.files)
            volume = parser.volume_label or "(no label)"

            # Detect build
            self.detected_build = detect_build_from_iso(parser)

            info_text = f"Volume: {volume} | Files: {file_count} | Detected: {self.detected_build}"
            self.rom_info.config(text=info_text, foreground="blue")
            self._log(f"ROM Analysis — Volume: {volume}, Files: {file_count}, Build: {self.detected_build}")

            # Diagnose if 0 files found
            if file_count == 0:
                self._log("⚠️ WARNING: 0 files found in ISO tree!")
                self._log("  Possible causes:")
                self._log("    - Root directory LBA not found (offset mismatch)")
                self._log("    - Directory records unreadable")
                self._log("    - File is not a valid PS1 disc image")
                self._log("  Raw file info:")
                import os as _os
                size_mb = _os.path.getsize(self.iso_path) / (1024*1024)
                self._log(f"    File size: {size_mb:.1f} MB")
                self._log(f"    Sector size: {parser._sector_size}, Data offset: 0x{parser._data_offset:X}")
                
                # Try to show first few file paths if any raw listing works
                raw_files = list(parser.files.keys())
                if raw_files:
                    self._log(f"  (But {len(raw_files)} entries exist internally?)")

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
            import traceback as _tb
            err_detail = str(e)
            self._log(f"ERROR analyzing ROM: {err_detail}")
            self._log(_tb.format_exc())
            self.rom_info.config(text=f"Error: {err_detail}", foreground="red")
            self._set_status("Analysis failed")

    def _scan_packs(self):
        self.pack_listbox.delete(0, tk.END)
        self.packs = list_available_packs(PACKS_DIR)
        valid_count = 0
        invalid_count = 0
        for pack in self.packs:
            if pack.valid:
                valid_count += 1
                display = f"✅ {pack.pack_name} v{pack.version} — {pack.author} ({pack.texture_count} textures)"
            else:
                invalid_count += 1
                errors = " | ".join(pack.errors[:2])
                display = f"❌ {pack.pack_name or os.path.basename(pack.base_dir)} — {errors}"
            self.pack_listbox.insert(tk.END, display)
        
        if not self.packs:
            self.pack_listbox.insert(tk.END, "(No packs found — click 'Add Pack' to add one)")
        
        status = f"Found {len(self.packs)} packs: {valid_count} valid, {invalid_count} invalid"
        self._log(status)
        self._log(f"Pack directory: {PACKS_DIR}")

    def _add_pack_folder(self):
        """Browse and add a pack folder to the packs directory."""
        folder = filedialog.askdirectory(title="Select Texture Pack Folder")
        if not folder:
            return
        
        # Run copy in background thread to avoid freezing GUI
        self._set_status("Copying pack folder...")
        self._log(f"Copying pack from: {folder}")
        thread = threading.Thread(target=self._copy_pack_folder_worker, args=(folder,), daemon=True)
        thread.start()

    def _copy_pack_folder_worker(self, src_folder: str):
        """Background worker for copying pack folders."""
        import shutil
        try:
            # Prevent copying the packs directory into itself (infinite recursion)
            src_abs = os.path.abspath(src_folder)
            packs_abs = os.path.abspath(PACKS_DIR)
            if src_abs == packs_abs or src_abs.startswith(packs_abs + os.sep):
                self.root.after(0, lambda: self._on_pack_copy_error(
                    f"Cannot copy the packs directory into itself!\n"
                    f"Source: {src_abs}\n"
                    f"Packs dir: {packs_abs}"
                ))
                return
            
            dest_name = os.path.basename(src_folder)
            dest_path = os.path.join(PACKS_DIR, dest_name)
            
            # Handle name collision
            counter = 1
            original_dest = dest_path
            while os.path.exists(dest_path):
                dest_path = f"{original_dest}_{counter}"
                counter += 1
            
            # Use dirs_exist_ok=True and ignore dangling symlinks
            shutil.copytree(
                src_folder, dest_path,
                dirs_exist_ok=True,
                ignore_dangling_symlinks=True,
            )
            
            # Update UI from main thread
            self.root.after(0, lambda: self._on_pack_copy_done(
                f"Copied pack folder: {src_folder} → {dest_path}", dest_path
            ))
        except RecursionError:
            self.root.after(0, lambda: self._on_pack_copy_error(
                "Maximum recursion depth exceeded!\n"
                "The source folder may contain circular references (symlinks/junctions).\n"
                "Try copying the folder contents manually instead."
            ))
        except Exception as e:
            self.root.after(0, lambda: self._on_pack_copy_error(f"Failed to copy pack folder: {e}"))

    def _on_pack_copy_done(self, msg: str, dest_path: str):
        """Called on main thread when pack copy completes."""
        self._log(msg)
        self._scan_packs()
        self._set_status("Pack added successfully")
        messagebox.showinfo("Pack Added", f"Pack folder copied to:\n{dest_path}")

    def _on_pack_copy_error(self, msg: str):
        """Called on main thread when pack copy fails."""
        self._log(msg)
        self._set_status("Pack copy failed")
        messagebox.showerror("Error", msg)

    def _check_pack_ps1_compliance(self, pack: PackInfo) -> str:
        """Check all textures in a pack for PS1 hardware compliance.
        
        Returns a formatted string with compliance status.
        """
        try:
            from tim_handler import validate_tim_for_ps1
            from PIL import Image as PILImage
            
            texture_dir = os.path.join(pack.base_dir, "textures")
            if not os.path.exists(texture_dir):
                return "⚠️ PS1 Compliance: No textures folder found"
            
            total = 0
            compliant = 0
            issues_by_file = {}
            
            for filename in os.listdir(texture_dir):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                    total += 1
                    filepath = os.path.join(texture_dir, filename)
                    try:
                        img = PILImage.open(filepath)
                        w, h = img.size
                        
                        # Check power-of-2
                        from tim_handler import _is_power_of_2
                        if not _is_power_of_2(w) or not _is_power_of_2(h):
                            issues_by_file[filename] = f"Size {w}x{h} is not power-of-2 (must be 8,16,32,64,128,256)"
                            continue
                        
                        # Check max size
                        if w > 256 or h > 256:
                            issues_by_file[filename] = f"Size {w}x{h} exceeds PS1 max 256x256"
                            continue
                        
                        compliant += 1
                        
                    except Exception as e:
                        issues_by_file[filename] = f"Error checking: {e}"
            
            if total == 0:
                return "⚠️ PS1 Compliance: No image textures found in pack"
            
            pct = (compliant / total) * 100
            
            if pct == 100:
                status = f"✅ PS1 COMPLIANT: All {total} textures follow PS1 hardware rules"
            elif pct >= 75:
                status = f"⚠️ PS1 PARTIAL: {compliant}/{total} textures compliant ({pct:.0f}%)"
            else:
                status = f"❌ PS1 ISSUES: Only {compliant}/{total} textures compliant ({pct:.0f}%)"
            
            # Show first 3 issues
            if issues_by_file:
                issue_lines = ["  Issues found:"]
                for i, (fname, issue) in enumerate(issues_by_file.items()):
                    if i >= 3:
                        remaining = len(issues_by_file) - 3
                        issue_lines.append(f"    ... and {remaining} more issues")
                        break
                    issue_lines.append(f"    • {fname}: {issue}")
                status += "\n" + "\n".join(issue_lines)
            
            # Add VRAM estimate
            status += f"\n  Recommendation: Use 4bpp for simple textures, 16bpp for complex ones"
            
            return status
            
        except Exception as e:
            return f"⚠️ PS1 Compliance check failed: {e}"

    def _add_pack_files(self):
        """Browse and select individual texture files to add to a pack."""
        files = filedialog.askopenfilenames(
            title="Select Texture Files (PNG, JPEG, BMP)",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp"),
                ("PNG", "*.png"),
                ("JPEG", "*.jpg *.jpeg"),
                ("BMP", "*.bmp"),
                ("All files", "*.*"),
            ],
        )
        if not files:
            return
        
        # Ask which pack to add to (or create new)
        self._add_files_to_pack_dialog(files)

    def _add_files_to_pack_dialog(self, files):
        """Show dialog to choose which pack to add files to."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Textures to Pack")
        dialog.geometry("500x350")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text=f"Add {len(files)} texture file(s) to:", font=("Segoe UI", 10, "bold")).pack(pady=10)
        
        # List existing packs
        listbox = tk.Listbox(dialog, height=8, font=("Consolas", 10))
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        listbox.insert(tk.END, "[ CREATE NEW PACK ]")
        for pack in self.packs:
            status = "✅" if pack.valid else "❌"
            listbox.insert(tk.END, f"{status} {pack.pack_name} ({os.path.basename(pack.base_dir)})")
        
        def on_confirm():
            selection = listbox.curselection()
            if not selection:
                return
            idx = selection[0]
            dialog.destroy()
            
            # Run in background thread
            self._set_status("Adding textures...")
            thread = threading.Thread(target=self._add_files_worker, args=(files, idx), daemon=True)
            thread.start()
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Confirm", command=on_confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _add_files_worker(self, files, idx):
        """Background worker for adding texture files."""
        import shutil
        try:
            if idx == 0:
                # Create new pack — need to ask for name on main thread
                self.root.after(0, lambda: self._ask_new_pack_name(files))
                return
            else:
                # Add to existing pack
                pack = self.packs[idx - 1]  # -1 because of "CREATE NEW" at index 0
                for f in files:
                    shutil.copy2(f, os.path.join(pack.base_dir, "textures"))
                self.root.after(0, lambda: self._on_pack_copy_done(
                    f"Added {len(files)} textures to '{pack.pack_name}'", 
                    pack.base_dir
                ))
        except Exception as e:
            self.root.after(0, lambda: self._on_pack_copy_error(f"Failed to add textures: {e}"))

    def _ask_new_pack_name(self, files):
        """Ask user for new pack name (must run on main thread for dialog)."""
        name = filedialog.askstring("New Pack Name", "Enter a name for the new pack:")
        if not name:
            self._set_status("Pack creation cancelled")
            return
        # Run creation in background
        thread = threading.Thread(target=self._create_new_pack_worker, args=(name, files), daemon=True)
        thread.start()

    def _create_new_pack_worker(self, name: str, files):
        """Background worker for creating new pack with files."""
        import shutil
        try:
            pack_dir = os.path.join(PACKS_DIR, name.replace(" ", "_"))
            os.makedirs(os.path.join(pack_dir, "textures"), exist_ok=True)
            for f in files:
                shutil.copy2(f, os.path.join(pack_dir, "textures"))
            create_sample_manifest(pack_dir, pack_name=name)
            self.root.after(0, lambda: self._on_pack_copy_done(
                f"Created new pack '{name}' with {len(files)} textures",
                pack_dir
            ))
        except Exception as e:
            self.root.after(0, lambda: self._on_pack_copy_error(f"Failed to create pack: {e}"))

    def _on_pack_select(self, event):
        selection = self.pack_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx >= len(self.packs):
            return
        self.selected_pack = self.packs[idx]
        pack = self.selected_pack
        
        # Build details text
        if pack.valid:
            # Validate PS1 compliance of pack textures
            compliance_info = self._check_pack_ps1_compliance(pack)
            
            details = (
                f"Name: {pack.pack_name}\n"
                f"Version: {pack.version}\n"
                f"Author: {pack.author}\n"
                f"License: {pack.license}\n"
                f"Description: {pack.description}\n"
                f"Textures: {pack.texture_count} files\n"
                f"Color-mapped surfaces: {len(pack.color_map)}\n"
                f"Path: {pack.base_dir}\n"
                f"\n{compliance_info}"
            )
            self.pack_details.config(text=details, foreground="black")
            self._log(f"Selected pack: {pack.pack_name} v{pack.version}")
            
            # Initialize color mapper if we have a color manifest
            color_manifest_path = os.path.join(pack.base_dir, "color_manifest.json")
            manifest_path = os.path.join(pack.base_dir, "manifest.json")
            
            # Try manifest.json first (new format), then color_manifest.json (old format)
            cfg_path = manifest_path if os.path.exists(manifest_path) else color_manifest_path
            
            if os.path.exists(cfg_path):
                try:
                    self.color_mapper = ColorMapper(pack.base_dir, cfg_path)
                    self.color_status.config(
                        text=f"✅ Color mapper loaded: {len(self.color_mapper.color_map)} surface types configured",
                        foreground="green"
                    )
                except Exception as e:
                    self.color_status.config(text=f"⚠️ Color config error: {e}", foreground="orange")
            else:
                self.color_status.config(text="ℹ️ No color mapping config found — pack uses manual texture mapping only", foreground="gray")
                
        else:
            # Invalid pack — show errors
            errors = "\n".join(f"  • {err}" for err in pack.errors)
            details = (
                f"❌ INVALID PACK: {pack.pack_name or os.path.basename(pack.base_dir)}\n\n"
                f"Errors:\n{errors}\n\n"
                f"Path: {pack.base_dir}\n\n"
                f"Click 'Add Pack Folder' to browse to a valid pack, or\n"
                f"check that the folder contains a manifest.json file."
            )
            self.pack_details.config(text=details, foreground="red")
            self._log(f"Selected invalid pack: {pack.pack_name or pack.base_dir}")
            self._log(f"  Errors: {pack.errors}")
            self.selected_pack = None

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
            
            # Get failsafe recommendation
            mode, msg = self.color_mapper.get_failsafe_recommendation(parser, tmd_files)
            
            # Show colored banner based on safety
            if mode == "auto":
                banner = tk.Label(preview, text=f"✅ {msg}", 
                                 bg="#90EE90", fg="#006400", font=("Segoe UI", 10, "bold"),
                                 relief=tk.RIDGE, padx=10, pady=5)
                banner.pack(fill=tk.X, padx=10, pady=5)
            elif mode == "assisted":
                banner = tk.Label(preview, text=f"⚠️ {msg}", 
                                 bg="#FFD700", fg="#8B4513", font=("Segoe UI", 10, "bold"),
                                 relief=tk.RIDGE, padx=10, pady=5)
                banner.pack(fill=tk.X, padx=10, pady=5)
                manual_btn = tk.Button(preview, text="🔧 OPEN MANUAL OVERRIDE (Recommended!)", 
                                    bg="#FF6B6B", fg="white", font=("Segoe UI", 11, "bold"),
                                    command=lambda: [preview.destroy(), self._scan_tmd_manual()])
                manual_btn.pack(fill=tk.X, padx=10, pady=(0, 5))
            else:  # manual
                banner = tk.Label(preview, text=f"🛑 {msg}", 
                                 bg="#FF6B6B", fg="white", font=("Segoe UI", 10, "bold"),
                                 relief=tk.RIDGE, padx=10, pady=5)
                banner.pack(fill=tk.X, padx=10, pady=5)
                manual_btn = tk.Button(preview, text="🔧 MANUAL OVERRIDE REQUIRED", 
                                    bg="#DC143C", fg="white", font=("Segoe UI", 11, "bold"),
                                    command=lambda: [preview.destroy(), self._scan_tmd_manual()])
                manual_btn.pack(fill=tk.X, padx=10, pady=(0, 5))
                
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

    def _scan_tmd_manual(self):
        """Scan ROM for TMD files and populate manual override tree."""
        if not self.iso_path or not os.path.exists(self.iso_path):
            messagebox.showwarning("No ROM", "Load a ROM first.")
            return
        try:
            parser = open_ps1_image(self.iso_path)
            tmd_files = [f for f in parser.list_files() if f.upper().endswith(".TMD")]
            
            # Clear tree
            for item in self.manual_tree.get_children():
                self.manual_tree.delete(item)
            
            # Scan each TMD for colors
            for tmd_path in tmd_files:
                try:
                    data = parser.extract_file(tmd_path)
                    from tmd_parser import read_tmd, find_flat_shaded_primitives
                    model = read_tmd(data)
                    flat = find_flat_shaded_primitives(model)
                    
                    # Collect unique colors
                    colors = set()
                    for oi, pi, pkt in flat:
                        if pkt.color:
                            colors.add(pkt.color)
                    
                    # Classify colors with confidence
                    surface_entries = []
                    if self.color_mapper:
                        for c in colors:
                            result = self.color_mapper.classify_color(*c)
                            if result and result[0]:
                                surface, confidence, needs_confirm = result
                                conf_str = f"{confidence:.0%}"
                                warn = "⚠️" if needs_confirm else "✅"
                                surface_entries.append(f"{warn} {surface} [{conf_str}]")
                    
                    surface_str = ", ".join(sorted(set(surface_entries))) if surface_entries else "unknown"
                    tex = self.manual_overrides.get(tmd_path, "(auto)")
                    self.manual_tree.insert("", tk.END, values=(tmd_path, surface_str, tex))
                    
                except Exception as e:
                    self.manual_tree.insert("", tk.END, values=(tmd_path, f"error: {e}", "(none)"))
            
            self._log(f"Manual scan: found {len(tmd_files)} TMD files")
        except Exception as e:
            self._log(f"Manual scan error: {e}")

    def _manual_assign_texture(self):
        """Let user pick a texture file for selected TMD."""
        sel = self.manual_tree.selection()
        if not sel:
            messagebox.showinfo("Select First", "Select a TMD file in the list above.")
            return
        
        # Get selected TMD path
        item = sel[0]
        values = self.manual_tree.item(item, "values")
        tmd_path = values[0]
        
        # Ask for texture
        tex_path = filedialog.askopenfilename(
            title=f"Select texture for {os.path.basename(tmd_path)}",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")],
        )
        if tex_path:
            self.manual_overrides[tmd_path] = tex_path
            self.manual_tree.item(item, values=(values[0], values[1], tex_path))
            self._log(f"Manual override: {tmd_path} -> {tex_path}")

    def _clear_manual(self):
        """Clear all manual overrides."""
        self.manual_overrides.clear()
        for item in self.manual_tree.get_children():
            vals = self.manual_tree.item(item, "values")
            self.manual_tree.item(item, values=(vals[0], vals[1], "(auto)"))
        self._log("Manual overrides cleared")

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
        self._log(f"Pack: {self.selected_pack.pack_name}")
        self._log(f"Dry Run: {self.dry_run_var.get()}")
        if self.manual_overrides:
            self._log(f"Manual overrides: {len(self.manual_overrides)} files")
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

            # Prepare manifest — inject manual overrides
            manifest = dict(self.selected_pack.manifest)
            if self.manual_overrides:
                textures = manifest.get("textures", {})
                standalone = textures.get("standalone_tim", {})
                for tmd_path, tex_path in self.manual_overrides.items():
                    # Add as a TMD level entry for manual injection
                    tmd_levels = textures.get("tmd_levels", {})
                    level_name = os.path.basename(tmd_path).replace(".TMD", "").replace(".tmd", "")
                    tmd_levels[level_name] = {
                        "tmd_file": tmd_path,
                        "polygon_groups": {
                            "manual_override": {
                                "replacement": tex_path,
                                "uv_mode": "auto"
                            }
                        }
                    }
                    textures["tmd_levels"] = tmd_levels
                manifest["textures"] = textures

            injector = TextureInjector(
                iso_path=self.iso_path,
                build_config=build_cfg,
                pack_dir=self.selected_pack.base_dir,
                manifest=manifest,
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
    
    # Set window icon (bobcat!)
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "bubsy_icon.png")
    if os.path.exists(icon_path):
        try:
            img = tk.PhotoImage(file=icon_path)
            root.iconphoto(True, img)
        except Exception:
            pass
    
    # Try to load Bubsy background
    _load_bubsy_bg(root)
    
    app = TextureInjectorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
