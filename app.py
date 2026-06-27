"""CouncilCast Studio — a polished desktop UI for AI-powered podcast script generation."""

import os
import subprocess
import threading
import tempfile
from pathlib import Path
from typing import List, Optional

import customtkinter as ctk
import tkinter.messagebox as messagebox
from tkinter import filedialog, Listbox, EXTENDED

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

    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

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
        self.demo_mode_var = ctk.BooleanVar(value=not has_real_llm())

        self._build_ui()

        # Show provider info in status on startup
        if self.demo_mode_var.get():
            self.status_var.set("Ready. Add source documents to begin.")
        else:
            self.status_var.set("Ready (real LLM configured). Add source documents to begin.")

    # ── UI State Helpers ───────────────────────────────────────────────

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

    # ── UI Construction ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # ── Hero Header ───────────────────────────────────────────────
        hero = ctk.CTkFrame(self.root, fg_color="transparent")
        hero.pack(fill="x", padx=20, pady=(14, 6))

        # Left side: name + subtitle
        hero_left = ctk.CTkFrame(hero, fg_color="transparent")
        hero_left.pack(side="left")

        ctk.CTkLabel(
            hero_left, text="CouncilCast Studio",
            font=("Segoe UI", 22, "bold"), text_color="#ffffff",
        ).pack(anchor="w")

        ctk.CTkLabel(
            hero_left,
            text="Turn source documents into AI podcast episodes.",
            font=("Segoe UI", 11), text_color="#8b8b9e",
        ).pack(anchor="w", pady=(2, 0))

        # Right side: status pill + API Keys
        hero_right = ctk.CTkFrame(hero, fg_color="transparent")
        hero_right.pack(side="right")

        is_real = has_real_llm()
        pill_text = "◉  Real Mode" if is_real else "◉  Demo Mode"
        pill_bg = "#1b5e20" if is_real else "#4a4a5e"
        self.status_pill = ctk.CTkLabel(
            hero_right,
            text=pill_text,
            fg_color=pill_bg,
            text_color="#ffffff",
            font=("Segoe UI", 9, "bold"),
            corner_radius=10,
        )
        self.status_pill.pack(side="left", padx=(0, 10), ipadx=10, ipady=3)

        ctk.CTkButton(
            hero_right, text="API Keys",
            fg_color="#2d2d44", hover_color="#3d3d5c", text_color="#cccccc",
            font=("Segoe UI", 11), height=36, corner_radius=6,
            command=self._configure_api_keys,
        ).pack(side="left")

        # ── Workflow Strip ────────────────────────────────────────────
        strip = ctk.CTkFrame(self.root, fg_color="#16213e", height=32)
        strip.pack(fill="x", padx=0, pady=0)
        strip.pack_propagate(False)
        ctk.CTkLabel(
            strip,
            text="Add Sources  →  Choose Style  →  Create Episode  →  Export",
            text_color="#8b8b9e",
            font=("Segoe UI", 9),
        ).pack(expand=True)

        # ── Master Content ────────────────────────────────────────────
        main_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=(8, 8))

        # ── Left Sidebar: Source Documents ────────────────────────────
        left_frame = ctk.CTkFrame(
            main_frame, width=260, fg_color="#16213e",
            border_width=1, border_color="#2d2d44",
        )
        left_frame.pack(side="left", fill="both", padx=(0, 8))
        left_frame.pack_propagate(False)

        ctk.CTkLabel(
            left_frame, text="Source Documents",
            font=("Segoe UI", 12, "bold"), text_color="#ffffff",
        ).pack(anchor="w", padx=12, pady=(10, 4))

        # Buttons inside sidebar
        sidebar_btns = ctk.CTkFrame(left_frame, fg_color="transparent")
        sidebar_btns.pack(fill="x", padx=8, pady=(4, 4))

        self.add_btn = ctk.CTkButton(
            sidebar_btns, text="Add Source Documents",
            command=self._add_files,
            fg_color="#2d2d44", hover_color="#3d3d5c", text_color="#cccccc",
            font=("Segoe UI", 11), height=36, corner_radius=6,
        )
        self.add_btn.pack(fill="x", pady=(0, 4))

        self.remove_btn = ctk.CTkButton(
            sidebar_btns, text="Remove Selected",
            command=self._remove_selected,
            fg_color="#2d2d44", hover_color="#3d3d5c", text_color="#cccccc",
            font=("Segoe UI", 11), height=36, corner_radius=6,
        )
        self.remove_btn.pack(fill="x")

        # Thin separator line
        separator = ctk.CTkFrame(left_frame, height=1, fg_color="#2d2d44")
        separator.pack(fill="x", padx=8, pady=4)

        # File listbox
        listbox_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        listbox_frame.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        scrollbar = ctk.CTkScrollbar(listbox_frame, command=self._on_listbox_scroll)
        self.files_listbox = Listbox(
            listbox_frame,
            selectmode=EXTENDED,
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
        self.files_listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.files_listbox.pack(side="left", fill="both", expand=True)

        # Empty state for file list
        self.no_sources_label = ctk.CTkLabel(
            left_frame,
            text="No sources yet.\nAdd a document to begin.",
            text_color="#555565",
            font=("Segoe UI", 10),
            justify="center",
        )
        self.no_sources_label.pack(fill="x", padx=8, pady=(0, 12))

        # ── Right Panel ───────────────────────────────────────────────
        right_panel = ctk.CTkFrame(main_frame, fg_color="transparent")
        right_panel.pack(side="left", fill="both", expand=True)

        # ── Style Selector Card ───────────────────────────────────────
        style_card = ctk.CTkFrame(
            right_panel, fg_color="#16213e",
            border_width=1, border_color="#2d2d44",
        )
        style_card.pack(fill="x", padx=0, pady=(0, 6))

        style_top = ctk.CTkFrame(style_card, fg_color="transparent")
        style_top.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(
            style_top, text="Episode Style:",
            font=("Segoe UI", 10, "bold"), text_color="#ffffff",
        ).pack(side="left", padx=(0, 8))

        self.preset_var = ctk.StringVar(value="Deep Dive")
        preset_values = [
            "Deep Dive",
            "Skeptical Review",
            "Beginner Friendly",
            "Founder Pitch Breakdown",
            "Research Roundtable",
        ]
        self.preset_combo = ctk.CTkOptionMenu(
            style_top,
            values=preset_values,
            command=self._on_style_change,
            fg_color="#2d2d44",
            button_color="#2d2d44",
            button_hover_color="#3d3d5c",
            text_color="#e0e0e0",
            dropdown_fg_color="#1a1a2e",
            dropdown_hover_color="#2d2d44",
            dropdown_text_color="#e0e0e0",
            width=200,
        )
        self.preset_combo.pack(side="left")

        self.demo_mode_check = ctk.CTkCheckBox(
            style_top,
            text="Demo Mode", variable=self.demo_mode_var,
            text_color="#aaaaaa", font=("Segoe UI", 11),
            checkbox_width=20, checkbox_height=20, corner_radius=4,
        )
        self.demo_mode_check.pack(side="right")

        # Style descriptions
        descriptions = {
            "Deep Dive": "Nuanced, detailed, and exploratory.",
            "Skeptical Review": "Challenges assumptions and weak claims.",
            "Beginner Friendly": "Plain-language explanation with jargon reduced.",
            "Founder Pitch Breakdown": "Product, market, risks, and opportunity.",
            "Research Roundtable": "Balanced academic-style discussion.",
        }
        self.preset_desc_var = ctk.StringVar(value=descriptions["Deep Dive"])
        ctk.CTkLabel(
            style_card, textvariable=self.preset_desc_var,
            text_color="#8b8b9e", font=("Segoe UI", 10),
        ).pack(anchor="w", padx=12, pady=(0, 10))

        # ── Primary Action Card ───────────────────────────────────────
        action_card = ctk.CTkFrame(
            right_panel, fg_color="#16213e",
            border_width=1, border_color="#2d2d44",
        )
        action_card.pack(fill="x", padx=0, pady=(0, 6))

        action_inner = ctk.CTkFrame(action_card, fg_color="transparent")
        action_inner.pack(fill="x", padx=20, pady=16)

        self.generate_btn = ctk.CTkButton(
            action_inner,
            text="Create Podcast From Sources",
            command=self._generate_episode,
            state="disabled",
            fg_color="#e94560", hover_color="#ff6b81", text_color="white",
            font=("Segoe UI", 13, "bold"), height=44, corner_radius=8,
        )
        self.generate_btn.pack(fill="x")

        self.generate_hint = ctk.CTkLabel(
            action_inner,
            text="Add at least one source document to create an episode.",
            text_color="#555565", font=("Segoe UI", 10),
            justify="center",
        )
        self.generate_hint.pack(pady=(6, 0))

        self.file_count_label = ctk.CTkLabel(
            action_inner, text="",
            text_color="#555565", font=("Segoe UI", 10),
        )

        # ── Progress Area ─────────────────────────────────────────────
        self.progress_var = ctk.StringVar(value="")
        self.progress_label = ctk.CTkLabel(
            right_panel,
            textvariable=self.progress_var,
            text_color="#888888",
            font=("Segoe UI", 11),
            justify="center",
        )
        self.progress_label.pack(fill="x", padx=8, pady=(0, 4))

        # ── Output Tabs ───────────────────────────────────────────────
        self.tabview = ctk.CTkTabview(right_panel)
        self.tabview.pack(fill="both", expand=True, padx=0, pady=(0, 4))

        self.brief_tab_frame = self.tabview.add("Brief")
        self.discussion_tab_frame = self.tabview.add("Council")
        self.script_tab_frame = self.tabview.add("Script")
        self.audio_tab_frame = self.tabview.add("Audio")

        self.brief_tab = ctk.CTkTextbox(
            self.brief_tab_frame, wrap="word",
            font=("Segoe UI", 11), text_color="#e0e0e0", fg_color="#1a1a2e",
        )
        self.brief_tab.pack(fill="both", expand=True, padx=4, pady=4)

        self.discussion_tab = ctk.CTkTextbox(
            self.discussion_tab_frame, wrap="word",
            font=("Segoe UI", 11), text_color="#e0e0e0", fg_color="#1a1a2e",
        )
        self.discussion_tab.pack(fill="both", expand=True, padx=4, pady=4)

        self.script_tab = ctk.CTkTextbox(
            self.script_tab_frame, wrap="word",
            font=("Segoe UI", 11), text_color="#e0e0e0", fg_color="#1a1a2e",
        )
        self.script_tab.pack(fill="both", expand=True, padx=4, pady=4)

        self._make_audio_tab(self.audio_tab_frame)
        self._set_tab_placeholders()

        # ── Export Button ─────────────────────────────────────────────
        export_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        export_frame.pack(fill="x", padx=0, pady=(2, 2))
        self.export_btn = ctk.CTkButton(
            export_frame,
            text="Export Episode Package",
            command=self._export_run,
            state="disabled",
            fg_color="#2d2d44", hover_color="#3d3d5c", text_color="#cccccc",
            font=("Segoe UI", 11), height=36, corner_radius=6,
        )
        self.export_btn.pack(side="right")

        # ── Status Bar ────────────────────────────────────────────────
        self.status_var = ctk.StringVar(value="Ready")
        ctk.CTkLabel(
            self.root,
            textvariable=self.status_var,
            text_color="#666680",
            font=("Segoe UI", 10),
            anchor="w",
        ).pack(fill="x", padx=0, pady=0)

    def _on_listbox_scroll(self, *args: object) -> None:
        """Bridge CTkScrollbar command to Listbox yview."""
        self.files_listbox.yview(*args)

    def _on_style_change(self, choice: str) -> None:
        """Called when the style dropdown changes."""
        descriptions = {
            "Deep Dive": "Nuanced, detailed, and exploratory.",
            "Skeptical Review": "Challenges assumptions and weak claims.",
            "Beginner Friendly": "Plain-language explanation with jargon reduced.",
            "Founder Pitch Breakdown": "Product, market, risks, and opportunity.",
            "Research Roundtable": "Balanced academic-style discussion.",
        }
        self.preset_desc_var.set(descriptions.get(choice, ""))

    def _make_audio_tab(self, parent: ctk.CTkFrame) -> None:
        """Populate the Audio tab with path, play, and folder controls."""
        inner = ctk.CTkFrame(parent, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            inner, text="Audio:",
            font=("Segoe UI", 12, "bold"), text_color="#ffffff",
        ).pack(anchor="w", pady=(0, 6))

        self.audio_path_var = ctk.StringVar(value="Not generated")
        self.audio_path_label = ctk.CTkLabel(
            inner, textvariable=self.audio_path_var,
            wraplength=500, text_color="#e0e0e0",
        )
        self.audio_path_label.pack(anchor="w", pady=(0, 6))

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(anchor="w", pady=8)

        self.play_btn = ctk.CTkButton(
            btn_row, text="Play",
            command=self._play_audio, state="disabled",
            fg_color="#2d2d44", hover_color="#3d3d5c", text_color="#cccccc",
            font=("Segoe UI", 11), height=36, corner_radius=6,
        )
        self.play_btn.pack(side="left", padx=(0, 8))

        self.open_folder_btn = ctk.CTkButton(
            btn_row, text="Open Folder",
            command=self._open_audio_folder, state="disabled",
            fg_color="#2d2d44", hover_color="#3d3d5c", text_color="#cccccc",
            font=("Segoe UI", 11), height=36, corner_radius=6,
        )
        self.open_folder_btn.pack(side="left")

        self.audio_status_var = ctk.StringVar(value="Ready")
        self.audio_status_label = ctk.CTkLabel(
            inner, textvariable=self.audio_status_var,
            font=("Segoe UI", 10), text_color="#8b8b9e",
        )
        self.audio_status_label.pack(anchor="w", pady=(4, 0))

    # ── UI State Helpers ───────────────────────────────────────────────

    def _update_text_widget(self, widget: ctk.CTkTextbox, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("0.0", "end")
        widget.insert("0.0", text)
        widget.configure(state="disabled")

    def _update_audio_tab(self) -> None:
        """Refresh the audio tab widgets based on current state."""
        if self.audio_generated and self.audio_path:
            self.audio_path_var.set(self.audio_path)
            self.play_btn.configure(state="normal")
            self.open_folder_btn.configure(state="normal")
            self.audio_status_var.set("Ready")
            self.audio_status_label.configure(text_color="#4caf50")
        elif self.audio_skipped:
            self.audio_path_var.set("Not available")
            self.play_btn.configure(state="disabled")
            self.open_folder_btn.configure(state="disabled")
            self.audio_status_var.set("Skipped: no TTS provider configured")
            self.audio_status_label.configure(text_color="#888800")
        elif self.audio_error:
            self.audio_path_var.set("Not available")
            self.play_btn.configure(state="disabled")
            self.open_folder_btn.configure(state="disabled")
            self.audio_status_var.set(f"Error: {self.audio_error}")
            self.audio_status_label.configure(text_color="#cc0000")
        else:
            self.audio_path_var.set("Not generated")
            self.play_btn.configure(state="disabled")
            self.open_folder_btn.configure(state="disabled")
            self.audio_status_var.set("Ready")
            self.audio_status_label.configure(text_color="#555555")

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
        self.files_listbox.delete(0, "end")
        for f in self.selected_files:
            self.files_listbox.insert("end", Path(f).name)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.add_btn.configure(state=state)
        self.remove_btn.configure(state=state)
        if enabled and self.selected_files:
            self.generate_btn.configure(state="normal")
        else:
            self.generate_btn.configure(state="disabled")

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
        self.file_count_label.configure(text=f"{count} file(s)")
        self.generate_btn.configure(state="normal")
        self.generate_hint.configure(
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
        self.file_count_label.configure(text=f"{count} file(s)")
        if not self.selected_files:
            self.generate_btn.configure(state="disabled")
            self.generate_hint.configure(
                text="Add at least one source document to create an episode.",
            )
            self.no_sources_label.pack(fill="x", padx=8, pady=(0, 12))
            self.status_var.set("Ready. Add source documents to begin.")
            self._set_tab_placeholders()
        else:
            self.generate_hint.configure(
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
        self.export_btn.configure(state="disabled")
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
            from councilcast.config import get_llm_provider_for_mode

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
                0, lambda: self.status_var.set("Generating source brief..."),
            )
            self.root.after(
                0, lambda: self.progress_var.set("Creating source brief..."),
            )
            combined = combine_documents(self.documents)
            self.brief = generate_source_brief(combined, self.llm_provider)
            self.root.after(
                0,
                lambda: self._update_text_widget(
                    self.brief_tab, self.brief.format(),
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
                self.brief, self.llm_provider, preset,
            )
            self.root.after(
                0,
                lambda: self._update_text_widget(
                    self.discussion_tab, self.discussion.format(),
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
                    self.script_tab, self.script.format(),
                ),
            )

            # 5. Generate audio
            self.root.after(0, lambda: self.status_var.set("Generating audio..."))
            self.root.after(
                0, lambda: self.progress_var.set("Generating audio..."),
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
            self.root.after(0, lambda: self.export_btn.configure(state="normal"))
            self.root.after(0, lambda: self.status_var.set("Complete!"))
            self.root.after(0, lambda: self.progress_var.set(""))

        except Exception as e:
            self.root.after(
                0,
                lambda: messagebox.showerror("Generation Error", str(e)),
            )
            self.root.after(
                0, lambda: self.status_var.set(f"Error: {e}"),
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
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Configure API Keys")
        dialog.geometry("560x460")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # Helper to mask a key for display
        def _mask(key: str) -> str:
            if not key:
                return ""
            if len(key) <= 10:
                return key[:3] + "..." + key[-3:]
            return key[:5] + "..." + key[-4:]

        main = ctk.CTkFrame(dialog, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=16, pady=16)

        # -- Explanatory text --
        ctk.CTkLabel(
            main,
            text="Configure your OpenAI API keys for CouncilCast Studio.",
            font=("Segoe UI", 10, "bold"), text_color="#ffffff",
        ).pack(anchor="w", pady=(0, 2))

        info_lines = [
            "• Demo Mode works without any keys — just check the box in the main window.",
            "• Real LLM Mode requires COUNCILCAST_LLM_API_KEY to be set.",
            "• TTS audio is optional. Set COUNCILCAST_TTS_API_KEY for voice narration.",
            "• You can use the same OpenAI API key for both fields.",
            "• Keys are saved to a .env file in the project root.",
            "• Never commit .env — it is excluded by .gitignore.",
        ]
        for line in info_lines:
            ctk.CTkLabel(
                main, text=line, wraplength=500,
                font=("Segoe UI", 9), text_color="#e0e0e0",
                justify="left",
            ).pack(anchor="w", pady=(1, 0))

        # Thin separator
        sep1 = ctk.CTkFrame(main, height=1, fg_color="#2d2d44")
        sep1.pack(fill="x", pady=10)

        # -- LLM Key --
        llm_frame = ctk.CTkFrame(main, fg_color="transparent")
        llm_frame.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            llm_frame, text="LLM API Key:",
            font=("Segoe UI", 9, "bold"), text_color="#ffffff",
        ).pack(anchor="w")
        current_llm = (
            os.environ.get("COUNCILCAST_LLM_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        )
        self._api_llm_var = ctk.StringVar(value=current_llm)
        llm_entry = ctk.CTkEntry(
            llm_frame, textvariable=self._api_llm_var,
            width=500, show="*", placeholder_text="sk-...",
        )
        llm_entry.pack(fill="x", pady=(2, 0))
        llm_status = _mask(current_llm) if current_llm else "(not set)"
        ctk.CTkLabel(
            llm_frame, text=f"Current: {llm_status}",
            font=("Segoe UI", 8), text_color="#8b8b9e",
        ).pack(anchor="w")

        # -- TTS Key --
        tts_frame = ctk.CTkFrame(main, fg_color="transparent")
        tts_frame.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            tts_frame, text="TTS API Key:",
            font=("Segoe UI", 9, "bold"), text_color="#ffffff",
        ).pack(anchor="w")
        current_tts = os.environ.get("COUNCILCAST_TTS_API_KEY") or ""
        self._api_tts_var = ctk.StringVar(value=current_tts)
        tts_entry = ctk.CTkEntry(
            tts_frame, textvariable=self._api_tts_var,
            width=500, show="*", placeholder_text="sk-...",
        )
        tts_entry.pack(fill="x", pady=(2, 0))
        tts_status = _mask(current_tts) if current_tts else "(not set)"
        ctk.CTkLabel(
            tts_frame, text=f"Current: {tts_status}",
            font=("Segoe UI", 8), text_color="#8b8b9e",
        ).pack(anchor="w")

        # -- Toggle visibility checkbox --
        self._api_show_var = ctk.BooleanVar(value=False)

        def _toggle_visibility() -> None:
            show = self._api_show_var.get()
            llm_entry.configure(show="" if show else "*")
            tts_entry.configure(show="" if show else "*")

        ctk.CTkCheckBox(
            main,
            text="Show keys (keep hidden when sharing screen)",
            variable=self._api_show_var,
            command=_toggle_visibility,
            text_color="#aaaaaa", font=("Segoe UI", 11),
            checkbox_width=20, checkbox_height=20, corner_radius=4,
        ).pack(anchor="w", pady=(2, 0))

        # Thin separator
        sep2 = ctk.CTkFrame(main, height=1, fg_color="#2d2d44")
        sep2.pack(fill="x", pady=10)

        # -- Buttons --
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill="x")

        def _save() -> None:
            project_root = Path(__file__).resolve().parent
            env_path = project_root / ".env"

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

        ctk.CTkButton(
            btn_frame, text="Save to .env",
            command=_save,
            fg_color="#2d2d44", hover_color="#3d3d5c", text_color="#cccccc",
            font=("Segoe UI", 11), height=36, corner_radius=6,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_frame, text="Cancel",
            command=dialog.destroy,
            fg_color="#2d2d44", hover_color="#3d3d5c", text_color="#cccccc",
            font=("Segoe UI", 11), height=36, corner_radius=6,
        ).pack(side="left")


def main() -> None:
    import sys

    validate_mode = "--validate" in sys.argv
    root = ctk.CTk()
    root.title("CouncilCast Studio")
    root.geometry("1100x780")
    root.minsize(800, 600)
    app = CouncilCastApp(root)  # noqa: F841 — keep reference alive
    if validate_mode:
        root.after(500, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
