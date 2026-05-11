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
from pack_manager import load_pack, list_available_packs, PackInfo, create_sample_manifest
from injector import TextureInjector, InjectionResult
from color_mapper import ColorMapper, load_color_manifest
from tim_handler import validate_tim_for_ps1, _is_power_of_2
from extract_tim import extract_tims_from_file, generate_tim_report
from tmd_parser import read_tmd, find_flat_shaded_primitives
from PIL import Image, ImageTk


# ── Constants ──
APP_NAME = "Bubsy 3D Texture Injector"
APP_VERSION = "1.4.0"
PACKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "packs")

# ── Bubsy Orange Theme Colors ──
BUBSY_ORANGE = "#FF8C00"
BUBSY_DARK_ORANGE = "#E67E00"
BUBSY_LIGHT_ORANGE = "#FFB84D"
BUBSY_BLACK = "#1A1A1A"
BUBSY_DARK_BG = "#2D2D2D"
BUBSY_CARD_BG = "#FFF8F0"
BUBSY_SUCCESS = "#2ECC71"
BUBSY_WARNING = "#F39C12"
BUBSY_ERROR = "#E74C3C"


class ToolTip:
    """Create a tooltip for any widget."""
    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tipwindow = None
        self.id = None
        widget.bind("<Enter>", self.enter)
        widget.bind("<Leave>", self.leave)
    
    def enter(self, event=None):
        self.schedule()
    
    def leave(self, event=None):
        self.unschedule()
        self.hidetip()
    
    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.delay, self.showtip)
    
    def unschedule(self):
        id_ = self.id
        self.id = None
        if id_:
            self.widget.after_cancel(id_)
    
    def showtip(self):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                        background=BUBSY_BLACK, foreground="white",
                        font=("Segoe UI", 9), padx=8, pady=4,
                        relief=tk.SOLID, borderwidth=1)
        label.pack()
    
    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()


def setup_bubsy_theme(root):
    """Apply Bubsy orange theme to the application."""
    style = ttk.Style(root)
    
    # Configure theme colors
    style.configure(".",
        background=BUBSY_CARD_BG,
        foreground=BUBSY_BLACK,
        fieldbackground="white",
        font=("Segoe UI", 10),
    )
    
    # Frame styling
    style.configure("TFrame", background=BUBSY_CARD_BG)
    style.configure("TLabelframe", background=BUBSY_CARD_BG, borderwidth=2)
    style.configure("TLabelframe.Label",
        background=BUBSY_ORANGE,
        foreground="white",
        font=("Segoe UI", 10, "bold"),
        padding=(10, 2),
    )
    
    # Button styling - Orange with black text
    style.configure("TButton",
        background=BUBSY_ORANGE,
        foreground=BUBSY_BLACK,
        font=("Segoe UI", 10, "bold"),
        padding=(8, 4),
    )
    style.map("TButton",
        background=[("active", BUBSY_DARK_ORANGE), ("pressed", BUBSY_DARK_ORANGE)],
        foreground=[("active", BUBSY_BLACK), ("pressed", BUBSY_BLACK)],
    )
    
    # Action button - Bigger, more prominent
    style.configure("Action.TButton",
        background=BUBSY_ORANGE,
        foreground=BUBSY_BLACK,
        font=("Segoe UI", 12, "bold"),
        padding=(15, 8),
    )
    style.map("Action.TButton",
        background=[("active", BUBSY_DARK_ORANGE), ("pressed", "#CC7000")],
    )
    
    # Entry styling
    style.configure("TEntry",
        fieldbackground="white",
        foreground=BUBSY_BLACK,
        insertcolor=BUBSY_BLACK,
    )
    
    # Listbox styling (using tk not ttk, so configure directly)
    # Progress bar
    style.configure("Horizontal.TProgressbar",
        background=BUBSY_ORANGE,
        troughcolor="#FFE0B2",
        borderwidth=0,
    )
    
    # Combobox
    style.configure("TCombobox",
        fieldbackground="white",
        foreground=BUBSY_BLACK,
        background=BUBSY_ORANGE,
    )
    
    # Checkbutton
    style.configure("TCheckbutton",
        background=BUBSY_CARD_BG,
        foreground=BUBSY_BLACK,
    )
    
    # Label styling
    style.configure("Title.TLabel",
        background=BUBSY_CARD_BG,
        foreground=BUBSY_ORANGE,
        font=("Segoe UI", 16, "bold"),
    )
    style.configure("Subtitle.TLabel",
        background=BUBSY_CARD_BG,
        foreground="#666666",
        font=("Segoe UI", 10, "italic"),
    )
    style.configure("Status.TLabel",
        background=BUBSY_CARD_BG,
        foreground=BUBSY_BLACK,
        font=("Segoe UI", 10, "bold"),
    )
    
    # Treeview
    style.configure("Treeview",
        background="white",
        foreground=BUBSY_BLACK,
        fieldbackground="white",
        rowheight=25,
    )
    style.configure("Treeview.Heading",
        background=BUBSY_ORANGE,
        foreground=BUBSY_BLACK,
        font=("Segoe UI", 10, "bold"),
    )
    style.map("Treeview",
        background=[("selected", BUBSY_LIGHT_ORANGE)],
        foreground=[("selected", BUBSY_BLACK)],
    )
    
    # Notebook (tabs)
    style.configure("TNotebook",
        background=BUBSY_CARD_BG,
        tabmargins=(2, 5, 2, 0),
    )
    style.configure("TNotebook.Tab",
        background="#FFE0B2",
        foreground=BUBSY_BLACK,
        font=("Segoe UI", 10, "bold"),
        padding=(15, 5),
    )
    style.map("TNotebook.Tab",
        background=[("selected", BUBSY_ORANGE), ("active", BUBSY_LIGHT_ORANGE)],
        foreground=[("selected", BUBSY_BLACK)],
        expand=[("selected", (2, 5, 2, 0))],
    )
    
    # Scrollbar
    style.configure("TScrollbar",
        background=BUBSY_ORANGE,
        troughcolor="#FFE0B2",
    )
    
    # Root background
    root.configure(bg=BUBSY_CARD_BG)
    
    return style


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
        self.root.geometry("1000x900")
        self.root.minsize(900, 700)

        # State
        self.iso_path: str = ""
        self.selected_pack: PackInfo | None = None
        self.packs: list[PackInfo] = []
        self.detected_build = "Unknown"
        self.color_mapper: ColorMapper | None = None

        self._build_scrollable_ui()
        self._scan_packs()
        
        # Keyboard shortcuts for power users
        self._setup_keyboard_shortcuts()

    def _setup_keyboard_shortcuts(self):
        """Bind keyboard shortcuts for common actions."""
        self.root.bind("<Control-o>", lambda e: self._browse_rom())
        self.root.bind("<Control-O>", lambda e: self._browse_rom())
        self.root.bind("<Control-i>", lambda e: self._run_injection() if self.iso_path and self.selected_pack else None)
        self.root.bind("<Control-I>", lambda e: self._run_injection() if self.iso_path and self.selected_pack else None)
        self.root.bind("<Control-r>", lambda e: self._scan_packs())
        self.root.bind("<Control-R>", lambda e: self._scan_packs())
        self.root.bind("<F1>", lambda e: self._show_help())
        self.root.bind("<Control-h>", lambda e: self._show_help())
        self.root.bind("<Control-H>", lambda e: self._show_help())
        self._log("Keyboard shortcuts: Ctrl+O (Open ROM), Ctrl+I (Inject), Ctrl+R (Refresh), F1 (Help)")

    # ── UI Construction ──
    def _build_scrollable_ui(self):
        """Build the UI inside a scrollable canvas so all steps are reachable."""
        # Create a canvas with a VISIBLE, WIDE scrollbar
        self.scroll_canvas = tk.Canvas(self.root, bg=BUBSY_CARD_BG, highlightthickness=0)
        
        # Use tk.Scrollbar (not ttk) so we can control width and colors directly
        self.scrollbar = tk.Scrollbar(
            self.root,
            orient="vertical",
            command=self.scroll_canvas.yview,
            bg=BUBSY_ORANGE,
            troughcolor="#FFE0B2",
            activebackground=BUBSY_DARK_ORANGE,
            width=24,
            relief=tk.RAISED,
            bd=2,
        )
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)

        # Always show scrollbar so user KNOWS scrolling is available
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Inner frame that holds ALL content
        self.main_frame = tk.Frame(self.scroll_canvas, bg=BUBSY_CARD_BG)
        canvas_window = self.scroll_canvas.create_window(
            (0, 0), window=self.main_frame, anchor="nw", tags="main_frame"
        )

        # Update scrollregion whenever inner frame changes size
        def _on_frame_configure(event=None):
            self.scroll_canvas.update_idletasks()
            bbox = self.scroll_canvas.bbox("all")
            if bbox:
                _, _, w, h = bbox
                self.scroll_canvas.configure(scrollregion=(0, 0, w, h))

        self.main_frame.bind("<Configure>", _on_frame_configure)

        # Make inner frame width match canvas width
        def _on_canvas_configure(event):
            self.scroll_canvas.itemconfig(canvas_window, width=event.width)
        self.scroll_canvas.bind("<Configure>", _on_canvas_configure)

        # === GLOBAL MOUSEWHEEL - works from ANYWHERE in the window ===
        def _on_mousewheel(event):
            # Windows / macOS
            if hasattr(event, 'delta') and event.delta:
                self.scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                return "break"
            # Linux (X11) - Button-4 = up, Button-5 = down
            if hasattr(event, 'num'):
                if event.num == 4:
                    self.scroll_canvas.yview_scroll(-3, "units")
                    return "break"
                elif event.num == 5:
                    self.scroll_canvas.yview_scroll(3, "units")
                    return "break"

        # Bind to root so it works no matter which widget is under the mouse
        self.root.bind_all("<MouseWheel>", _on_mousewheel)
        self.root.bind_all("<Button-4>", _on_mousewheel)
        self.root.bind_all("<Button-5>", _on_mousewheel)

        # Keyboard scrolling - always works
        def _scroll_page_up(event):
            self.scroll_canvas.yview_scroll(-5, "units")
            return "break"
        def _scroll_page_down(event):
            self.scroll_canvas.yview_scroll(5, "units")
            return "break"
        def _scroll_home(event):
            self.scroll_canvas.yview_moveto(0)
            return "break"
        def _scroll_end(event):
            self.scroll_canvas.yview_moveto(1.0)
            return "break"

        self.root.bind_all("<Prior>", _scroll_page_up)    # Page Up
        self.root.bind_all("<Next>", _scroll_page_down)   # Page Down
        self.root.bind_all("<Home>", _scroll_home)
        self.root.bind_all("<End>", _scroll_end)

        # Build the actual UI inside the scrollable frame
        self._build_ui(self.main_frame)

        # Force initial scrollregion update after UI builds
        self.main_frame.update_idletasks()
        _on_frame_configure()

    def _build_ui(self, main: tk.Frame):
        # Apply Bubsy orange theme
        style = setup_bubsy_theme(self.root)

        # Main container with Bubsy background — DO NOT pack main since it's inside a canvas window
        main.configure(bg=BUBSY_CARD_BG)
        # NOTE: main is placed via canvas create_window, so we don't call main.pack() here

        # === HEADER ===
        header = tk.Frame(main, bg=BUBSY_ORANGE)
        header.pack(fill=tk.X, pady=(0, 15), ipady=8)
        
        title_label = tk.Label(header, text="🐱 Bubsy 3D Texture Injector",
                              bg=BUBSY_ORANGE, fg=BUBSY_BLACK,
                              font=("Segoe UI", 18, "bold"))
        title_label.pack(side=tk.LEFT, padx=15)
        
        subtitle = tk.Label(header, text=f"v{APP_VERSION} | PS1 Hardware Failproof",
                           bg=BUBSY_ORANGE, fg=BUBSY_BLACK,
                           font=("Segoe UI", 10))
        subtitle.pack(side=tk.LEFT, padx=(5, 0))
        
        # Help button
        help_btn = tk.Button(header, text="❓ Help", command=self._show_help,
                           bg=BUBSY_BLACK, fg="white",
                           font=("Segoe UI", 9, "bold"),
                           relief=tk.FLAT, padx=10, cursor="hand2")
        help_btn.pack(side=tk.RIGHT, padx=15)
        ToolTip(help_btn, "Click for step-by-step usage guide")

        # === QUICK START SECTION (Beginner-Friendly) ===
        quick_frame = tk.LabelFrame(main, text="🚀 Quick Start (3 Easy Steps)",
                                   bg=BUBSY_CARD_BG, fg=BUBSY_BLACK,
                                   font=("Segoe UI", 11, "bold"),
                                   padx=10, pady=10)
        quick_frame.pack(fill=tk.X, pady=(0, 15))

        quick_steps = tk.Frame(quick_frame, bg=BUBSY_CARD_BG)
        quick_steps.pack(fill=tk.X)

        # Step 1
        step1 = tk.Frame(quick_steps, bg=BUBSY_CARD_BG)
        step1.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Label(step1, text="1", bg=BUBSY_ORANGE, fg=BUBSY_BLACK,
                font=("Segoe UI", 14, "bold"), width=2).pack(side=tk.LEFT)
        tk.Label(step1, text="Load ROM", bg=BUBSY_CARD_BG, fg=BUBSY_BLACK,
                font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Label(step1, text="Select your Bubsy 3D ISO/BIN", bg=BUBSY_CARD_BG,
                fg="#666666", font=("Segoe UI", 9)).pack(side=tk.LEFT)

        # Arrow
        tk.Label(quick_steps, text="→", bg=BUBSY_CARD_BG, fg=BUBSY_ORANGE,
                font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT, padx=5)

        # Step 2
        step2 = tk.Frame(quick_steps, bg=BUBSY_CARD_BG)
        step2.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Label(step2, text="2", bg=BUBSY_ORANGE, fg=BUBSY_BLACK,
                font=("Segoe UI", 14, "bold"), width=2).pack(side=tk.LEFT)
        tk.Label(step2, text="Pick Pack", bg=BUBSY_CARD_BG, fg=BUBSY_BLACK,
                font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Label(step2, text="Choose a texture pack", bg=BUBSY_CARD_BG,
                fg="#666666", font=("Segoe UI", 9)).pack(side=tk.LEFT)

        # Arrow
        tk.Label(quick_steps, text="→", bg=BUBSY_CARD_BG, fg=BUBSY_ORANGE,
                font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT, padx=5)

        # Step 3
        step3 = tk.Frame(quick_steps, bg=BUBSY_CARD_BG)
        step3.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Label(step3, text="3", bg=BUBSY_ORANGE, fg=BUBSY_BLACK,
                font=("Segoe UI", 14, "bold"), width=2).pack(side=tk.LEFT)
        tk.Label(step3, text="INJECT!", bg=BUBSY_CARD_BG, fg=BUBSY_BLACK,
                font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Label(step3, text="Click the big orange button", bg=BUBSY_CARD_BG,
                fg="#666666", font=("Segoe UI", 9)).pack(side=tk.LEFT)

        # === SCROLL HINT ===
        scroll_hint = tk.Frame(quick_frame, bg=BUBSY_CARD_BG)
        scroll_hint.pack(fill=tk.X, pady=(8, 0))
        tk.Label(scroll_hint,
                text="↓  SCROLL DOWN or DRAG the orange scrollbar on the right to see the INJECT button  ↓",
                bg=BUBSY_ORANGE, fg=BUBSY_BLACK,
                font=("Segoe UI", 10, "bold"), padx=10, pady=4).pack(fill=tk.X)

        # === ROM SECTION ===
        rom_frame = tk.LabelFrame(main, text="Step 1: Load Bubsy 3D ROM",
                                 bg=BUBSY_CARD_BG, fg=BUBSY_BLACK,
                                 font=("Segoe UI", 11, "bold"), padx=10, pady=10)
        rom_frame.pack(fill=tk.X, pady=(0, 10))

        rom_row = tk.Frame(rom_frame, bg=BUBSY_CARD_BG)
        rom_row.pack(fill=tk.X)

        self.rom_entry = ttk.Entry(rom_row, state="readonly")
        self.rom_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        browse_btn = ttk.Button(rom_row, text="📂 Browse…", command=self._browse_rom)
        browse_btn.pack(side=tk.LEFT, padx=(0, 5))
        ToolTip(browse_btn, "Select your Bubsy 3D ROM file (.iso, .bin, .cue, .chd)")

        analyze_btn = ttk.Button(rom_row, text="🔍 Analyze", command=self._analyze_rom)
        analyze_btn.pack(side=tk.LEFT, padx=(0, 5))
        ToolTip(analyze_btn, "Scan the ROM to find TMD models and TIM textures")

        rip_btn = ttk.Button(rom_row, text="🎨 Rip Original TIMs", command=self._rip_original_tims)
        rip_btn.pack(side=tk.LEFT)
        ToolTip(rip_btn, "Extract original TIM textures from the ROM for reference")

        # ROM info display
        self.rom_info = tk.Label(rom_frame, text="No ROM loaded. Supported: .iso, .bin/.cue",
                                bg=BUBSY_CARD_BG, fg="#999999", font=("Segoe UI", 10))
        self.rom_info.pack(anchor=tk.W, pady=(8, 0))

        # Smart Tip Banner
        self.smart_tip = tk.Label(rom_frame, text="💡 TIP: Start by clicking 'Browse' to load your ROM!",
                                 bg=BUBSY_LIGHT_ORANGE, fg=BUBSY_BLACK,
                                 font=("Segoe UI", 9, "bold"), padx=10, pady=5)
        self.smart_tip.pack(fill=tk.X, pady=(8, 0))

        # === PACK SECTION ===
        pack_frame = tk.LabelFrame(main, text="Step 2: Select Texture Pack",
                                  bg=BUBSY_CARD_BG, fg=BUBSY_BLACK,
                                  font=("Segoe UI", 11, "bold"), padx=10, pady=10)
        pack_frame.pack(fill=tk.X, pady=(0, 10))

        pack_top = tk.Frame(pack_frame, bg=BUBSY_CARD_BG)
        pack_top.pack(fill=tk.X)

        tk.Label(pack_top, text="Available Packs:", bg=BUBSY_CARD_BG,
                fg=BUBSY_BLACK, font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        
        add_pack_btn = ttk.Button(pack_top, text="➕ Add Pack Folder…", command=self._add_pack_folder)
        add_pack_btn.pack(side=tk.LEFT, padx=(10, 0))
        ToolTip(add_pack_btn, "Copy a texture pack folder into the injector")
        
        add_files_btn = ttk.Button(pack_top, text="📁 Add Pack Files…", command=self._add_pack_files)
        add_files_btn.pack(side=tk.LEFT, padx=(5, 0))
        ToolTip(add_files_btn, "Add individual texture images to a pack")
        
        refresh_btn = ttk.Button(pack_top, text="🔄 Refresh", command=self._scan_packs)
        refresh_btn.pack(side=tk.RIGHT)
        ToolTip(refresh_btn, "Rescan the packs folder for new packs")

        # Pack list with scrollbar
        pack_list_frame = tk.Frame(pack_frame, bg=BUBSY_CARD_BG)
        pack_list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        scrollbar = ttk.Scrollbar(pack_list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.pack_listbox = tk.Listbox(
            pack_list_frame,
            yscrollcommand=scrollbar.set,
            height=4,
            font=("Consolas", 10),
            selectmode=tk.SINGLE,
            bg="white",
            fg=BUBSY_BLACK,
            selectbackground=BUBSY_LIGHT_ORANGE,
            selectforeground=BUBSY_BLACK,
        )
        self.pack_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.pack_listbox.yview)
        self.pack_listbox.bind("<<ListboxSelect>>", self._on_pack_select)

        # Pack details
        self.pack_details = tk.Label(pack_frame, text="Select a pack to view PS1 compliance details",
                                    bg=BUBSY_CARD_BG, fg="#999999",
                                    wraplength=900, font=("Segoe UI", 10))
        self.pack_details.pack(anchor=tk.W, pady=(8, 0))

        # === COLOR MAPPING SECTION ===
        color_frame = tk.LabelFrame(main, text="Step 3: Smart Color Mapping (Auto-Detect)",
                                   bg=BUBSY_CARD_BG, fg=BUBSY_BLACK,
                                   font=("Segoe UI", 11, "bold"), padx=10, pady=10)
        color_frame.pack(fill=tk.X, pady=(0, 10))

        self.color_status = tk.Label(color_frame,
                                    text="💡 Load a ROM and select a pack to enable smart color mapping",
                                    bg=BUBSY_CARD_BG, fg="#999999", font=("Segoe UI", 10))
        self.color_status.pack(anchor=tk.W)

        color_btn_row = tk.Frame(color_frame, bg=BUBSY_CARD_BG)
        color_btn_row.pack(fill=tk.X, pady=(8, 0))

        preview_btn = ttk.Button(color_btn_row, text="🎨 Preview Color Map", command=self._preview_color_map)
        preview_btn.pack(side=tk.LEFT, padx=(0, 5))
        ToolTip(preview_btn, "See how polygon colors map to textures before injecting")
        
        config_btn = ttk.Button(color_btn_row, text="⚙️ Configure Mapping", command=self._open_color_config)
        config_btn.pack(side=tk.LEFT)
        ToolTip(config_btn, "Adjust color ranges for surface type detection")

        # === OPTIONS SECTION ===
        opts_frame = tk.LabelFrame(main, text="Options",
                                  bg=BUBSY_CARD_BG, fg=BUBSY_BLACK,
                                  font=("Segoe UI", 11, "bold"), padx=10, pady=10)
        opts_frame.pack(fill=tk.X, pady=(0, 10))

        opts_grid = tk.Frame(opts_frame, bg=BUBSY_CARD_BG)
        opts_grid.pack(fill=tk.X)

        # Dry run
        self.dry_run_var = tk.BooleanVar(value=True)
        dry_cb = tk.Checkbutton(opts_grid, text="Dry Run (preview only, no changes)",
                               variable=self.dry_run_var,
                               bg=BUBSY_CARD_BG, fg=BUBSY_BLACK,
                               font=("Segoe UI", 10), selectcolor=BUBSY_CARD_BG)
        dry_cb.grid(row=0, column=0, sticky=tk.W, padx=(0, 20))
        ToolTip(dry_cb, "Test injection without modifying your ROM (safe mode)")

        # Backup
        self.backup_var = tk.BooleanVar(value=True)
        backup_cb = tk.Checkbutton(opts_grid, text="Create .bak backup",
                                  variable=self.backup_var,
                                  bg=BUBSY_CARD_BG, fg=BUBSY_BLACK,
                                  font=("Segoe UI", 10), selectcolor=BUBSY_CARD_BG)
        backup_cb.grid(row=0, column=1, sticky=tk.W)
        ToolTip(backup_cb, "Keep a backup of your original ROM before modifying")

        # Texture size
        tk.Label(opts_grid, text="Texture Size:", bg=BUBSY_CARD_BG,
                fg=BUBSY_BLACK, font=("Segoe UI", 10)).grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        self.texture_size = ttk.Combobox(opts_grid, values=[64, 128, 256], width=8, state="readonly")
        self.texture_size.set(128)
        self.texture_size.grid(row=1, column=1, sticky=tk.W, pady=(8, 0))
        ToolTip(self.texture_size, "PS1 texture size in pixels (must be power of 2)")

        # Color depth
        tk.Label(opts_grid, text="Color Depth:", bg=BUBSY_CARD_BG,
                fg=BUBSY_BLACK, font=("Segoe UI", 10)).grid(row=2, column=0, sticky=tk.W, pady=(8, 0))
        self.color_depth = ttk.Combobox(opts_grid, values=["4bpp", "8bpp", "16bpp"], width=8, state="readonly")
        self.color_depth.set("16bpp")
        self.color_depth.grid(row=2, column=1, sticky=tk.W, pady=(8, 0))
        ToolTip(self.color_depth, "PS1 color depth: 4bpp=saves VRAM, 16bpp=best quality")

        # === ACTION BUTTONS ===
        action_frame = tk.Frame(main, bg=BUBSY_CARD_BG)
        action_frame.pack(fill=tk.X, pady=(0, 10))

        self.inject_btn = tk.Button(
            action_frame,
            text="🚀 INJECT TEXTURES",
            command=self._run_injection,
            bg=BUBSY_ORANGE, fg=BUBSY_BLACK,
            font=("Segoe UI", 14, "bold"),
            padx=30, pady=12,
            relief=tk.RAISED,
            borderwidth=3,
            cursor="hand2",
            state=tk.DISABLED,
        )
        self.inject_btn.pack(side=tk.LEFT, padx=(0, 15))
        ToolTip(self.inject_btn, "Apply textures to your ROM! (Enable by loading ROM + selecting pack)")

        save_cfg_btn = ttk.Button(action_frame, text="💾 Save Color Map", command=self._save_color_config)
        save_cfg_btn.pack(side=tk.LEFT, padx=(0, 5))
        ToolTip(save_cfg_btn, "Save current color mapping configuration to JSON")
        
        load_cfg_btn = ttk.Button(action_frame, text="📋 Load Color Map", command=self._load_color_config)
        load_cfg_btn.pack(side=tk.LEFT)
        ToolTip(load_cfg_btn, "Load a previously saved color mapping configuration")

        # === PROGRESS ===
        prog_frame = tk.LabelFrame(main, text="Progress",
                                  bg=BUBSY_CARD_BG, fg=BUBSY_BLACK,
                                  font=("Segoe UI", 11, "bold"), padx=10, pady=10)
        prog_frame.pack(fill=tk.X, pady=(0, 10))

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(prog_frame, variable=self.progress_var, maximum=100, mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=(0, 8))

        self.status_label = tk.Label(prog_frame, text="Ready",
                                      bg=BUBSY_CARD_BG, fg=BUBSY_BLACK,
                                      font=("Segoe UI", 10, "bold"))
        self.status_label.pack(anchor=tk.W)

        # === LOG CONSOLE ===
        log_frame = tk.LabelFrame(main, text="Activity Log",
                                 bg=BUBSY_CARD_BG, fg=BUBSY_BLACK,
                                 font=("Segoe UI", 11, "bold"), padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            height=10,
            bg=BUBSY_BLACK,
            fg="#00FF00",  # Green terminal text
            insertbackground="white",
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.insert(tk.END, "🐱 Welcome to Bubsy 3D Texture Injector!\n")
        self.log_text.insert(tk.END, "Step 1: Load ROM  →  Step 2: Select Pack  →  Step 3: INJECT!\n")
        self.log_text.insert(tk.END, "-" * 50 + "\n")
        self.log_text.config(state=tk.DISABLED)

        # === MANUAL TEXTURE OVERRIDE SECTION ===
        manual_frame = tk.LabelFrame(main, text="🛡️ Manual Override (Fix Auto-Detect Mistakes)",
                                    bg=BUBSY_CARD_BG, fg=BUBSY_BLACK,
                                    font=("Segoe UI", 11, "bold"), padx=10, pady=10)
        manual_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(manual_frame,
                text="When auto-mapping is unsure, YOU decide what texture goes where!",
                bg=BUBSY_CARD_BG, fg=BUBSY_ORANGE,
                font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        tk.Label(manual_frame,
                text="⚠️ Use this for: checkerboard lava, blue mountains, orange ground — anything the auto-detect got wrong!",
                bg=BUBSY_CARD_BG, fg="#666666",
                font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(0, 8))

        self.manual_tree = ttk.Treeview(manual_frame, columns=("file", "surface", "texture"), show="headings", height=4)
        self.manual_tree.heading("file", text="TMD File")
        self.manual_tree.heading("surface", text="Detected Surface")
        self.manual_tree.heading("texture", text="Assigned Texture")
        self.manual_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        manual_btn_row = tk.Frame(manual_frame, bg=BUBSY_CARD_BG)
        manual_btn_row.pack(fill=tk.X)
        
        scan_btn = ttk.Button(manual_btn_row, text="🔍 Scan TMD Files", command=self._scan_tmd_manual)
        scan_btn.pack(side=tk.LEFT, padx=(0, 5))
        ToolTip(scan_btn, "Find all TMD models in the ROM and detect their surface colors")
        
        assign_btn = ttk.Button(manual_btn_row, text="📝 Assign Texture", command=self._manual_assign_texture)
        assign_btn.pack(side=tk.LEFT, padx=(0, 5))
        ToolTip(assign_btn, "Manually assign a texture file to a specific TMD")
        
        clear_btn = ttk.Button(manual_btn_row, text="❌ Clear Overrides", command=self._clear_manual)
        clear_btn.pack(side=tk.LEFT)
        ToolTip(clear_btn, "Remove all manual texture assignments")

        self.manual_overrides: dict[str, str] = {}  # iso_path -> texture_path

    # ── Manual Override Actions ──
    def _log(self, msg: str):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _set_status(self, msg: str):
        """Update status label with color coding."""
        self.status_label.config(text=msg)
        # Color code based on status content
        if any(word in msg.lower() for word in ["error", "fail", "invalid", "broken"]):
            self.status_label.config(fg=BUBSY_ERROR)
        elif any(word in msg.lower() for word in ["success", "done", "complete", "ready"]):
            self.status_label.config(fg=BUBSY_SUCCESS)
        elif any(word in msg.lower() for word in ["warning", "caution", "careful"]):
            self.status_label.config(fg=BUBSY_WARNING)
        else:
            self.status_label.config(fg=BUBSY_BLACK)
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
            
            # Auto-generate manifest if missing
            manifest_path = os.path.join(dest_path, "manifest.json")
            if not os.path.exists(manifest_path):
                self._log("No manifest.json found — auto-generating one from textures...")
                from pack_manager import auto_generate_manifest
                manifest = auto_generate_manifest(dest_path)
                if manifest:
                    self._log(f"✅ Auto-generated manifest with {len(manifest.get('color_map', {}))} categories")
                else:
                    self._log("⚠️ Could not auto-generate manifest (no textures/ folder found)")
            
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

    def _show_help(self):
        """Show a help dialog with step-by-step instructions."""
        help_text = """🐱 Bubsy 3D Texture Injector — Quick Guide

STEP 1: LOAD YOUR ROM
  • Click "Browse" and select your Bubsy 3D .iso, .bin, .cue, or .chd file
  • Click "Analyze" to scan the ROM for TMD models and TIM textures
  • (Optional) Click "Rip Original TIMs" to extract original textures for reference

STEP 2: SELECT A TEXTURE PACK
  • Choose from available packs in the list
  • Or click "Add Pack Folder" to import a new pack
  • PS1 compliance info shows automatically when you select a pack

STEP 3: CONFIGURE (Optional)
  • Use "Preview Color Map" to see auto-detected surface mappings
  • Use Manual Override if auto-detect gets colors wrong
  • Adjust Texture Size and Color Depth if needed
  • Keep "Dry Run" checked first time to test safely

STEP 4: INJECT!
  • Click the big orange "INJECT TEXTURES" button
  • The tool will backup your ROM, convert textures to TIM format,
    and patch them into the game
  • Test the patched ROM in DuckStation first, then real hardware!

TIPS:
  • Use 4bpp for simple textures (grass, dirt) to save VRAM
  • Use 16bpp for complex textures (metal, water) for best quality
  • Match original TIM dimensions for best compatibility
  • Keep total VRAM under 1.5MB for Bubsy 3D safety

Need more help? Check README.md or visit:
https://github.com/MapleteamXP/bubsy-texture-injector
"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Help & Quick Start Guide")
        dialog.geometry("650x550")
        dialog.configure(bg=BUBSY_CARD_BG)
        
        tk.Label(dialog, text="🐱 Bubsy 3D Texture Injector Help",
                bg=BUBSY_ORANGE, fg=BUBSY_BLACK,
                font=("Segoe UI", 14, "bold"), padx=15, pady=10).pack(fill=tk.X)
        
        text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD,
                                         font=("Segoe UI", 10),
                                         bg="white", fg=BUBSY_BLACK,
                                         padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        text.insert(tk.END, help_text)
        text.config(state=tk.DISABLED)
        
        ttk.Button(dialog, text="Got it!", command=dialog.destroy).pack(pady=10)

    def _update_smart_tip(self, message: str, color: str = BUBSY_LIGHT_ORANGE):
        """Update the smart tip banner with guidance."""
        self.smart_tip.config(text=f"💡 {message}", bg=color)

    def _update_inject_button(self):
        if self.iso_path and self.selected_pack:
            self.inject_btn.config(state=tk.NORMAL)
            self._update_smart_tip("Ready! Click the big orange button to inject textures!", "#90EE90")
        else:
            self.inject_btn.config(state=tk.DISABLED)
            if not self.iso_path:
                self._update_smart_tip("Start by loading a ROM file (Step 1)")
            elif not self.selected_pack:
                self._update_smart_tip("Now select a texture pack (Step 2)")

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
