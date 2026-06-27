"""CouncilCast Studio — a polished desktop UI for AI-powered podcast script generation."""

import os
import subprocess
import threading
import tempfile
from pathlib import Path
from typing import List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from councilcast.audio import text_to_speech
from councilcast.config import get_llm_provider, get_tts_provider, has_real_llm
from councilcast.council import generate_council_discussion
from councilcast.export import export_run
from councilcast.ingestion import (
    SUPPORTED_EXTENSIONS,
    combine_documents,
    format_file_list,
    read_documents,
)
from councilcast.models import CouncilDiscussion, PodcastScript, SourceBrief, SourceDocument
from councilcast.script_writer import generate_script
from councilcast.source_brief import generate_source_brief


class CouncilCastApp:
    """Main application window for CouncilCast Studio."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("CouncilCast Studio")
        self.root.geometry("1100x780")
        self.root.minsize(800, 600)

        # ── State ──────────────────────────────────────────────────────
        self.selected_files: List[str] = []
        self.documents: List[SourceDocument] = []
        self.brief: Optional[SourceBrief] = None
        self.discussion: Optional[CouncilDiscussion] = None
        self.script: Optional[PodcastScript] = None
        self.audio_path: Optional[str] = None
        self.audio_generated: bool = False
        self.audio_skipped: bool = False
        self.audio_error: Optional[str] = None
        self.export_path: Optional[Path] = None
        self.llm_provider = get_llm_provider()
        self.demo_mode_var = tk.BooleanVar(value=not has_real_llm())

        self._build_ui()

        # Show provider info in status on startup
        if self.demo_mode_var.get():
            self.status_var.set("Ready. Add source documents to begin.")
        else:
            self.status_var.set("Ready (real LLM configured). Add source documents to begin.")

    # ── Dark Theme ──────────────────────────────────────────────────────

    def _apply_dark_theme(self) -> None:
        """Apply a dark podcast-studio color scheme via ttk styles."""
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass  # clam may not be available on all platforms; fall back gracefully

        BG = "#1a1a2e"          # deep navy background
        BG_SURFACE = "#16213e"  # card/surface background
        BG_INPUT = "#0f3460"    # input/selected background
        FG = "#e0e0e0"          # primary text
        FG_DIM = "#8b8b9e"      # secondary text
        ACCENT = "#e94560"      # accent (coral-red for primary actions)
        ACCENT_HOVER = "#ff6b81"
        ACCENT_DISABLED = "#555566"

        self.root.configure(bg=BG)

        # Frame
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=BG_SURFACE, relief="flat")

        # Label
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("Card.TLabel", background=BG_SURFACE, foreground=FG)
        style.configure(
            "Header.TLabel", background=BG, foreground=FG,
            font=("Segoe UI", 18, "bold"),
        )
        style.configure(
            "Subtitle.TLabel", background=BG, foreground=FG_DIM,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Dim.TLabel", background=BG, foreground=FG_DIM,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Accent.TLabel", background=BG_SURFACE, foreground=ACCENT,
            font=("Segoe UI", 9, "bold"),
        )

        # Button
        style.configure(
            "TButton", background=BG_INPUT, foreground=FG, borderwidth=0,
            padding=(14, 6), font=("Segoe UI", 10),
        )
        style.map("TButton", background=[("active", "#1a4a8a")])
        style.configure(
            "Secondary.TButton", background=BG_SURFACE, foreground=FG_DIM,
            borderwidth=0, padding=(10, 5), font=("Segoe UI", 9),
        )
        style.map("Secondary.TButton", background=[("active", BG_INPUT)])
        style.configure(
            "Primary.TButton", background=ACCENT, foreground="#ffffff",
            font=("Segoe UI", 12, "bold"), padding=(28, 12), borderwidth=0,
        )
        style.map(
            "Primary.TButton",
            background=[("active", ACCENT_HOVER), ("disabled", ACCENT_DISABLED)],
            foreground=[("disabled", "#999999")],
        )

        # LabelFrame
        style.configure(
            "TLabelframe", background=BG, foreground=FG,
            borderwidth=1, relief="solid",
        )
        style.configure(
            "TLabelframe.Label", background=BG, foreground=FG,
            font=("Segoe UI", 10, "bold"),
        )

        # Notebook
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure(
            "TNotebook.Tab", background=BG_SURFACE, foreground=FG_DIM,
            padding=(16, 8), font=("Segoe UI", 10),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", BG_INPUT)],
            foreground=[("selected", FG)],
        )

        # Combobox
        style.configure(
            "TCombobox", fieldbackground=BG_INPUT, background=BG_SURFACE,
            foreground=FG, arrowcolor=FG, selectbackground=BG_INPUT,
        )
        style.map(
            "TCombobox", fieldbackground=[("readonly", BG_INPUT)],
            foreground=[("readonly", FG)], background=[("readonly", BG_INPUT)],
        )

        # Checkbutton
        style.configure(
            "TCheckbutton", background=BG, foreground=FG_DIM,
            font=("Segoe UI", 9),
        )
        style.map("TCheckbutton", background=[("active", BG)])

        # Status bar
        style.configure(
            "Status.TLabel", background=BG_SURFACE, foreground=FG_DIM,
            font=("Segoe UI", 9), padding=(8, 4),
        )

    # ── UI Construction ────────────────────────────────────────────────

    def _set_tab_placeholders(self) -> None:
        """Set empty-state placeholder text in each tab."""
        self._update_text_widget(
            self.brief_tab, "Your source brief will appear here.",
        )
        self._update_text_widget(
            self.discussion_tab, "The AI council discussion will appear here.",
        )
        self._update_text_widget(
            self.script_tab, "Your podcast script will appear here.",
        )

    def _build_ui(self) -> None:
        self._apply_dark_theme()

        # ── Hero Header ───────────────────────────────────────────────
        hero = ttk.Frame(self.root)
        hero.pack(fill=tk.X, padx=20, pady=(14, 6))

        # Left side: name + subtitle
        hero_left = ttk.Frame(hero)
        hero_left.pack(side=tk.LEFT)

        ttk.Label(
            hero_left, text="CouncilCast Studio", style="Header.TLabel",
        ).pack(anchor=tk.W)

        ttk.Label(
            hero_left,
            text="Turn source documents into AI podcast episodes.",
            style="Subtitle.TLabel",
        ).pack(anchor=tk.W, pady=(2, 0))

        # Right side: status pill + API Keys
        hero_right = ttk.Frame(hero)
        hero_right.pack(side=tk.RIGHT)

        # Status pill using a Label with background color
        is_real = has_real_llm()
        pill_text = "◉  Real Mode" if is_real else "◉  Demo Mode"
        pill_bg = "#1b5e20" if is_real else "#4a4a5e"
        self.status_pill = tk.Label(
            hero_right,
            text=pill_text,
            bg=pill_bg, fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            padx=10, pady=3,
            relief="flat", borderwidth=0,
        )
        self.status_pill.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            hero_right, text="API Keys", style="Secondary.TButton",
            command=self._configure_api_keys,
        ).pack(side=tk.LEFT)

        # ── Workflow Strip ────────────────────────────────────────────
        strip = tk.Frame(self.root, bg="#16213e", height=32)
        strip.pack(fill=tk.X, padx=0, pady=0)
        strip.pack_propagate(False)
        tk.Label(
            strip,
            text="Add Sources  →  Choose Style  →  Create Episode  →  Export",
            bg="#16213e", fg="#8b8b9e",
            font=("Segoe UI", 9),
        ).pack(expand=True)

        # ── Master Content ────────────────────────────────────────────
        main_pw = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pw.pack(fill=tk.BOTH, expand=True, padx=20, pady=(8, 8))

        # ── Left Sidebar: Source Documents ────────────────────────────
        left_frame = ttk.LabelFrame(main_pw, text="Source Documents", width=260)
        left_frame.pack_propagate(False)
        main_pw.add(left_frame, weight=0)

        # Buttons inside sidebar
        sidebar_btns = ttk.Frame(left_frame)
        sidebar_btns.pack(fill=tk.X, padx=8, pady=(8, 4))

        self.add_btn = ttk.Button(
            sidebar_btns, text="Add Source Documents",
            command=self._add_files,
        )
        self.add_btn.pack(fill=tk.X, pady=(0, 4))

        self.remove_btn = ttk.Button(
            sidebar_btns, text="Remove Selected",
            command=self._remove_selected, style="Secondary.TButton",
        )
        self.remove_btn.pack(fill=tk.X)

        # Separator
        ttk.Separator(left_frame, orient=tk.HORIZONTAL).pack(
            fill=tk.X, padx=8, pady=4,
        )

        # File listbox
        listbox_frame = ttk.Frame(left_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL)
        self.files_listbox = tk.Listbox(
            listbox_frame,
            selectmode=tk.EXTENDED,
            yscrollcommand=scrollbar.set,
            font=("Segoe UI", 10),
            bg="#0f3460",
            fg="#e0e0e0",
            selectbackground="#e94560",
            selectforeground="#ffffff",
            activestyle="none",
            borderwidth=0,
            highlightthickness=0,
        )
        scrollbar.config(command=self.files_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.files_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Empty state for file list
        self.no_sources_label = ttk.Label(
            left_frame,
            text="No sources yet. Add a document to begin.",
            style="Dim.TLabel",
            anchor=tk.CENTER,
        )
        self.no_sources_label.pack(fill=tk.X, padx=8, pady=(0, 12))

        # ── Right Panel ───────────────────────────────────────────────
        right_panel = ttk.Frame(main_pw)
        main_pw.add(right_panel, weight=1)

        # ── Style Selector Card ───────────────────────────────────────
        style_card = ttk.Frame(right_panel, style="Card.TFrame")
        style_card.pack(fill=tk.X, padx=8, pady=(4, 6))

        style_top = ttk.Frame(style_card, style="Card.TFrame")
        style_top.pack(fill=tk.X, padx=12, pady=(10, 4))

        ttk.Label(
            style_top, text="Episode Style:", style="Card.TLabel",
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.preset_var = tk.StringVar(value="Deep Dive")
        self.preset_combo = ttk.Combobox(
            style_top,
            textvariable=self.preset_var,
            values=[
                "Deep Dive",
                "Skeptical Review",
                "Beginner Friendly",
                "Founder Pitch Breakdown",
                "Research Roundtable",
            ],
            state="readonly",
            width=24,
        )
        self.preset_combo.pack(side=tk.LEFT)

        self.demo_mode_check = ttk.Checkbutton(
            style_top,
            text="Demo Mode",
            variable=self.demo_mode_var,
        )
        self.demo_mode_check.pack(side=tk.RIGHT)

        # Style description
        descriptions = {
            "Deep Dive": "Nuanced, detailed, and exploratory.",
            "Skeptical Review": "Challenges assumptions and weak claims.",
            "Beginner Friendly": "Plain-language explanation with jargon reduced.",
            "Founder Pitch Breakdown": "Product, market, risks, and opportunity.",
            "Research Roundtable": "Balanced academic-style discussion.",
        }
        self.preset_desc_var = tk.StringVar(value=descriptions["Deep Dive"])
        ttk.Label(
            style_card, textvariable=self.preset_desc_var,
            style="Dim.TLabel",
        ).pack(anchor=tk.W, padx=12, pady=(0, 10))

        def on_style_change(*args: object) -> None:
            self.preset_desc_var.set(descriptions.get(self.preset_var.get(), ""))

        self.preset_var.trace_add("write", on_style_change)

        # ── Primary Action Card ───────────────────────────────────────
        action_card = ttk.Frame(right_panel, style="Card.TFrame")
        action_card.pack(fill=tk.X, padx=8, pady=(0, 6))

        action_inner = ttk.Frame(action_card, style="Card.TFrame")
        action_inner.pack(fill=tk.X, padx=16, pady=16)

        self.generate_btn = ttk.Button(
            action_inner,
            text="Create Podcast From Sources",
            command=self._generate_episode,
            state=tk.DISABLED,
            style="Primary.TButton",
        )
        self.generate_btn.pack(fill=tk.X)

        self.generate_hint = ttk.Label(
            action_inner,
            text="Add at least one source document to create an episode.",
            style="Dim.TLabel",
            anchor=tk.CENTER,
        )
        self.generate_hint.pack(pady=(6, 0))

        self.file_count_label = ttk.Label(action_inner, text="", style="Dim.TLabel")

        # ── Progress Area ─────────────────────────────────────────────
        self.progress_var = tk.StringVar(value="")
        self.progress_label = ttk.Label(
            right_panel,
            textvariable=self.progress_var,
            style="Dim.TLabel",
            anchor=tk.CENTER,
        )
        self.progress_label.pack(fill=tk.X, padx=8, pady=(0, 4))

        # ── Output Tabs ───────────────────────────────────────────────
        self.notebook = ttk.Notebook(right_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        self.brief_tab = self._make_text_tab("Brief")
        self.discussion_tab = self._make_text_tab("Council")
        self.script_tab = self._make_text_tab("Script")
        self.audio_frame = self._make_audio_tab()
        self._set_tab_placeholders()

        # ── Export Button ─────────────────────────────────────────────
        export_frame = ttk.Frame(right_panel)
        export_frame.pack(fill=tk.X, padx=8, pady=(2, 2))
        self.export_btn = ttk.Button(
            export_frame,
            text="Export Episode Package",
            command=self._export_run,
            state=tk.DISABLED,
        )
        self.export_btn.pack(side=tk.RIGHT)

        # ── Status Bar ────────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(
            self.root,
            textvariable=self.status_var,
            style="Status.TLabel",
            anchor=tk.W,
        ).pack(fill=tk.X, padx=0, pady=0)

    def _make_text_tab(self, title: str) -> tk.Text:
        """Create a notebook tab containing a read-only Text widget."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=title)
        text_widget = tk.Text(
            frame, wrap=tk.WORD,
            font=("Segoe UI", 10),
            bg="#0f3460",
            fg="#e0e0e0",
            insertbackground="#e0e0e0",
            selectbackground="#e94560",
            selectforeground="#ffffff",
            borderwidth=0,
            highlightthickness=0,
            padx=10, pady=10,
            state=tk.DISABLED,
        )
        text_widget.pack(fill=tk.BOTH, expand=True)
        return text_widget

    def _make_audio_tab(self) -> ttk.Frame:
        """Create the Audio notebook tab with path, play, and folder controls."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Audio")

        inner = ttk.Frame(frame, padding=16)
        inner.pack(fill=tk.BOTH, expand=True)

        # Audio file path display
        ttk.Label(
            inner, text="Audio:", font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W, pady=(0, 4))
        self.audio_path_var = tk.StringVar(value="Not generated")
        self.audio_path_label = ttk.Label(
            inner, textvariable=self.audio_path_var, wraplength=500,
            background="#16213e", foreground="#e0e0e0",
        )
        self.audio_path_label.pack(anchor=tk.W, pady=(0, 4))

        # Button row
        btn_row = ttk.Frame(inner)
        btn_row.pack(anchor=tk.W, pady=8)

        self.play_btn = ttk.Button(
            btn_row, text="Play", command=self._play_audio, state=tk.DISABLED,
        )
        self.play_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.open_folder_btn = ttk.Button(
            btn_row,
            text="Open Folder",
            command=self._open_audio_folder,
            state=tk.DISABLED,
        )
        self.open_folder_btn.pack(side=tk.LEFT)

        # Status message
        self.audio_status_var = tk.StringVar(value="Ready")
        self.audio_status_label = ttk.Label(
            inner,
            textvariable=self.audio_status_var,
            font=("Segoe UI", 9),
            foreground="#8b8b9e",
            background="#16213e",
        )
        self.audio_status_label.pack(anchor=tk.W, pady=(4, 0))

        return frame

    # ── UI State Helpers ───────────────────────────────────────────────

    def _update_text_widget(self, widget: tk.Text, text: str) -> None:
        widget.config(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.config(state=tk.DISABLED)

    def _update_audio_tab(self) -> None:
        """Refresh the audio tab widgets based on current state."""
        if self.audio_generated and self.audio_path:
            self.audio_path_var.set(self.audio_path)
            self.play_btn.config(state=tk.NORMAL)
            self.open_folder_btn.config(state=tk.NORMAL)
            self.audio_status_var.set("Ready")
            self.audio_status_label.config(foreground="#006600")
        elif self.audio_skipped:
            self.audio_path_var.set("Not available")
            self.play_btn.config(state=tk.DISABLED)
            self.open_folder_btn.config(state=tk.DISABLED)
            self.audio_status_var.set("Skipped: no TTS provider configured")
            self.audio_status_label.config(foreground="#888800")
        elif self.audio_error:
            self.audio_path_var.set("Not available")
            self.play_btn.config(state=tk.DISABLED)
            self.open_folder_btn.config(state=tk.DISABLED)
            self.audio_status_var.set(f"Error: {self.audio_error}")
            self.audio_status_label.config(foreground="#cc0000")
        else:
            self.audio_path_var.set("Not generated")
            self.play_btn.config(state=tk.DISABLED)
            self.open_folder_btn.config(state=tk.DISABLED)
            self.audio_status_var.set("Ready")
            self.audio_status_label.config(foreground="#555555")

    def _get_preset_key(self) -> str:
        mapping = {
            "Deep Dive": "deep_dive",
            "Skeptical Review": "skeptical_review",
            "Beginner Friendly": "beginner_friendly",
            "Founder Pitch Breakdown": "founder_pitch",
            "Research Roundtable": "research_roundtable",
        }
        return mapping.get(self.preset_var.get(), "deep_dive")

    def _update_listbox(self) -> None:
        """Rebuild the listbox from self.selected_files."""
        self.files_listbox.delete(0, tk.END)
        for f in self.selected_files:
            self.files_listbox.insert(tk.END, Path(f).name)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        self.add_btn.config(state=state)
        self.remove_btn.config(state=state)
        if enabled and self.selected_files:
            self.generate_btn.config(state=tk.NORMAL)
        else:
            self.generate_btn.config(state=tk.DISABLED)

    # ── File Management ────────────────────────────────────────────────

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select source files",
            filetypes=[
                ("Supported files", "*.txt *.md *.pdf"),
                ("All files", "*.*"),
            ],
        )
        if not paths:
            return

        added_count = 0
        for p in paths:
            ext = Path(p).suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                messagebox.showerror(
                    "Unsupported File",
                    f"Unsupported file extension: {ext}\n\n"
                    f"Supported extensions: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
                )
                continue
            if p not in self.selected_files:
                self.selected_files.append(p)
                added_count += 1

        if added_count == 0:
            return

        self._update_listbox()
        count = len(self.selected_files)
        self.file_count_label.config(text=f"{count} file(s)")
        self.generate_btn.config(state=tk.NORMAL)
        self.generate_hint.config(
            text=f"Ready to create a podcast from {count} source file(s).",
        )
        self.status_var.set(f"Ready to create podcast from {count} source file(s).")
        self.no_sources_label.pack_forget()

    def _remove_selected(self) -> None:
        selected_indices = self.files_listbox.curselection()
        if not selected_indices:
            return
        # Remove in reverse order so indices remain valid
        for i in reversed(selected_indices):
            del self.selected_files[i]

        self._update_listbox()
        count = len(self.selected_files)
        self.file_count_label.config(text=f"{count} file(s)")
        if not self.selected_files:
            self.generate_btn.config(state=tk.DISABLED)
            self.generate_hint.config(
                text="Add at least one source document to create an episode.",
            )
            self.no_sources_label.pack(fill=tk.X, padx=8, pady=(0, 12))
            self.status_var.set("Ready. Add source documents to begin.")
            self._set_tab_placeholders()
        else:
            self.generate_hint.config(
                text=f"Ready to create a podcast from {count} source file(s).",
            )
            self.status_var.set(
                f"Ready to create podcast from {count} source file(s).",
            )

    # ── Generation Pipeline ────────────────────────────────────────────

    def _generate_episode(self) -> None:
        if not self.selected_files:
            messagebox.showwarning("No files", "Please add at least one source file first.")
            return

        # Validate API key in real mode
        if not self.demo_mode_var.get():
            api_key = os.environ.get("COUNCILCAST_LLM_API_KEY") or os.environ.get(
                "OPENAI_API_KEY"
            )
            if not api_key:
                messagebox.showerror(
                    "API Key Required",
                    "Real LLM mode requires COUNCILCAST_LLM_API_KEY to be set.\n\n"
                    "Either set this environment variable or enable Demo Mode "
                    "to use simulated responses.",
                )
                return

        self._set_buttons_enabled(False)
        self.export_btn.config(state=tk.DISABLED)
        self.status_var.set("Initializing...")
        self.progress_var.set("")

        # Clear previous results
        self.brief = None
        self.discussion = None
        self.script = None
        self.audio_path = None
        self.audio_generated = False
        self.audio_skipped = False
        self.audio_error = None
        self.export_path = None

        # Clear text tabs
        self._update_text_widget(self.brief_tab, "")
        self._update_text_widget(self.discussion_tab, "")
        self._update_text_widget(self.script_tab, "")
        self._update_audio_tab()

        thread = threading.Thread(target=self._run_pipeline, daemon=True)
        thread.start()

    def _run_pipeline(self) -> None:
        """Run the full generation pipeline on a background thread."""
        try:
            # Choose provider based on demo mode toggle
            from councilcast.config import get_llm_provider_for_mode, FakeLLMProvider

            demo_mode = self.demo_mode_var.get()
            provider = get_llm_provider_for_mode(demo_mode)
            if provider is None:
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Configuration Error",
                        "No LLM provider available. Enable Demo Mode or set "
                        "COUNCILCAST_LLM_API_KEY.",
                    ),
                )
                return
            self.llm_provider = provider

            # 1. Read files
            self.root.after(0, lambda: self.status_var.set("Reading source files..."))
            self.root.after(0, lambda: self.progress_var.set("Reading sources..."))
            self.documents = read_documents(self.selected_files)
            file_list_text = format_file_list(self.documents)

            # 2. Generate source brief
            self.root.after(
                0, lambda: self.status_var.set("Generating source brief...")
            )
            self.root.after(
                0, lambda: self.progress_var.set("Creating source brief...")
            )
            combined = combine_documents(self.documents)
            self.brief = generate_source_brief(combined, self.llm_provider)
            self.root.after(
                0,
                lambda: self._update_text_widget(
                    self.brief_tab, self.brief.format()
                ),
            )

            # 3. Generate council discussion
            self.root.after(
                0,
                lambda: self.status_var.set("Generating council discussion..."),
            )
            self.root.after(
                0,
                lambda: self.progress_var.set("Running council discussion..."),
            )
            preset = self._get_preset_key()
            self.discussion = generate_council_discussion(
                self.brief, self.llm_provider, preset
            )
            self.root.after(
                0,
                lambda: self._update_text_widget(
                    self.discussion_tab, self.discussion.format()
                ),
            )

            # 4. Generate podcast script
            self.root.after(
                0,
                lambda: self.status_var.set("Generating episode script..."),
            )
            self.root.after(
                0,
                lambda: self.progress_var.set("Writing podcast script..."),
            )
            self.script = generate_script(self.discussion, self.llm_provider)
            self.root.after(
                0,
                lambda: self._update_text_widget(
                    self.script_tab, self.script.format()
                ),
            )

            # 5. Generate audio
            self.root.after(0, lambda: self.status_var.set("Generating audio..."))
            self.root.after(
                0, lambda: self.progress_var.set("Generating audio...")
            )
            try:
                tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                tmp.close()
                self.audio_path = tmp.name
                success = text_to_speech(self.script.format(), self.audio_path)
                if success:
                    self.audio_generated = True
                else:
                    self.audio_skipped = True
                    # Clean up unused temp file
                    if os.path.exists(self.audio_path):
                        os.unlink(self.audio_path)
                    self.audio_path = None
            except Exception as e:
                self.audio_error = str(e)
                if self.audio_path and os.path.exists(self.audio_path):
                    os.unlink(self.audio_path)
                self.audio_path = None

            self.root.after(0, self._update_audio_tab)

            # 6. Enable export
            self.root.after(0, lambda: self.export_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.status_var.set("Complete!"))
            self.root.after(0, lambda: self.progress_var.set(""))

        except Exception as e:
            self.root.after(
                0,
                lambda: messagebox.showerror("Generation Error", str(e)),
            )
            self.root.after(
                0, lambda: self.status_var.set(f"Error: {e}")
            )
            self.root.after(0, lambda: self.progress_var.set(""))
        finally:
            self.root.after(0, lambda: self._set_buttons_enabled(True))

    # ── Audio Actions ──────────────────────────────────────────────────

    def _play_audio(self) -> None:
        if not self.audio_path or not os.path.exists(self.audio_path):
            return
        try:
            if os.name == "nt":  # Windows
                os.startfile(self.audio_path)
            else:  # macOS / Linux
                opener = "open" if os.uname().sysname == "Darwin" else "xdg-open"
                subprocess.Popen([opener, self.audio_path])
        except Exception as e:
            messagebox.showerror("Play Error", f"Could not play audio:\n{e}")

    def _open_audio_folder(self) -> None:
        if not self.audio_path:
            return
        folder = os.path.dirname(os.path.abspath(self.audio_path))
        try:
            if os.name == "nt":  # Windows
                os.startfile(folder)
            else:
                opener = "open" if os.uname().sysname == "Darwin" else "xdg-open"
                subprocess.Popen([opener, folder])
        except Exception as e:
            messagebox.showerror("Open Folder Error", str(e))

    # ── Export ─────────────────────────────────────────────────────────

    def _export_run(self) -> None:
        if not self.brief or not self.discussion or not self.script:
            messagebox.showwarning(
                "Nothing to export",
                "Generate an episode first before exporting.",
            )
            return
        try:
            preset_key = self._get_preset_key()
            audio_path = self.audio_path if self.audio_generated else None
            run_dir = export_run(
                self.selected_files,
                preset_key,
                self.brief,
                self.discussion,
                self.script,
                audio_path,
            )
            self.export_path = run_dir
            messagebox.showinfo(
                "Export Complete",
                f"Run exported to:\n{run_dir}",
            )
            self.status_var.set(f"Exported to {run_dir}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))
            self.status_var.set(f"Export failed: {e}")

    # ── API Keys Dialog ────────────────────────────────────────────────

    def _configure_api_keys(self) -> None:
        """Open a dialog to view and set API keys, optionally saving to .env."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Configure API Keys")
        dialog.geometry("520x420")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg="#1a1a2e")

        # Helper to mask a key for display
        def _mask(key: str) -> str:
            if not key:
                return ""
            if len(key) <= 10:
                return key[:3] + "..." + key[-3:]
            return key[:5] + "..." + key[-4:]

        main = ttk.Frame(dialog, padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        # -- Explanatory text --
        ttk.Label(
            main,
            text="Configure your OpenAI API keys for CouncilCast Studio.",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W, pady=(0, 2))

        info_lines = [
            "• Demo Mode works without any keys — just check the box in the main window.",
            "• Real LLM Mode requires COUNCILCAST_LLM_API_KEY to be set.",
            "• TTS audio is optional. Set COUNCILCAST_TTS_API_KEY for voice narration.",
            "• You can use the same OpenAI API key for both fields.",
            "• Keys are saved to a .env file in the project root.",
            "• Never commit .env — it is excluded by .gitignore.",
        ]
        for line in info_lines:
            ttk.Label(
                main, text=line, wraplength=480, font=("Segoe UI", 9),
            ).pack(anchor=tk.W, pady=(1, 0))

        ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # -- LLM Key --
        llm_frame = ttk.Frame(main)
        llm_frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(
            llm_frame, text="LLM API Key:",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor=tk.W)
        current_llm = (
            os.environ.get("COUNCILCAST_LLM_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        )
        self._api_llm_var = tk.StringVar(value=current_llm)
        llm_entry = ttk.Entry(
            llm_frame, textvariable=self._api_llm_var, width=60, show="*",
        )
        llm_entry.pack(fill=tk.X, pady=(2, 0))
        llm_status = _mask(current_llm) if current_llm else "(not set)"
        ttk.Label(
            llm_frame, text=f"Current: {llm_status}",
            font=("Segoe UI", 8), foreground="#8b8b9e",
        ).pack(anchor=tk.W)

        # -- TTS Key --
        tts_frame = ttk.Frame(main)
        tts_frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(
            tts_frame, text="TTS API Key:",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor=tk.W)
        current_tts = os.environ.get("COUNCILCAST_TTS_API_KEY") or ""
        self._api_tts_var = tk.StringVar(value=current_tts)
        tts_entry = ttk.Entry(
            tts_frame, textvariable=self._api_tts_var, width=60, show="*",
        )
        tts_entry.pack(fill=tk.X, pady=(2, 0))
        tts_status = _mask(current_tts) if current_tts else "(not set)"
        ttk.Label(
            tts_frame, text=f"Current: {tts_status}",
            font=("Segoe UI", 8), foreground="#8b8b9e",
        ).pack(anchor=tk.W)

        # -- Toggle visibility checkbox --
        self._api_show_var = tk.BooleanVar(value=False)

        def _toggle_visibility() -> None:
            show = self._api_show_var.get()
            llm_entry.config(show="" if show else "*")
            tts_entry.config(show="" if show else "*")

        ttk.Checkbutton(
            main,
            text="Show keys (keep hidden when sharing screen)",
            variable=self._api_show_var,
            command=_toggle_visibility,
        ).pack(anchor=tk.W, pady=(2, 0))

        ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # -- Buttons --
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X)

        def _save() -> None:
            # Find .env file path (project root)
            project_root = Path(__file__).resolve().parent
            env_path = project_root / ".env"

            # Read existing .env (if any) to preserve non-key lines
            existing_lines: dict = {}
            if env_path.exists():
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            existing_lines[k.strip()] = line  # store full raw line

            # Build new .env content
            new_llm = self._api_llm_var.get().strip()
            new_tts = self._api_tts_var.get().strip()

            lines = [
                "# CouncilCast Studio API keys — generated by Configure API Keys dialog",
                f"COUNCILCAST_LLM_API_KEY={new_llm}",
                f"COUNCILCAST_TTS_API_KEY={new_tts}",
            ]

            with open(env_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")

            # Reload environment
            from councilcast.config import load_env

            load_env()

            messagebox.showinfo(
                "Saved",
                f"Keys saved to {env_path}\n\n"
                f"Restart the app for all changes to take effect.\n"
                f"(Keys loaded fresh when you click Generate Episode.)",
            )
            dialog.destroy()

        ttk.Button(
            btn_frame, text="Save to .env", command=_save,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            btn_frame, text="Cancel", command=dialog.destroy,
        ).pack(side=tk.LEFT)


def main() -> None:
    import sys

    validate_mode = "--validate" in sys.argv
    root = tk.Tk()
    app = CouncilCastApp(root)  # noqa: F841 — keep reference alive
    if validate_mode:
        root.after(500, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
