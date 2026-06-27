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
            self.status_var.set("Ready (demo mode). Add source documents to begin.")
        else:
            self.status_var.set("Ready (real LLM configured). Add source documents to begin.")

    # ── UI Construction ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        style = ttk.Style()
        style.configure("Primary.TButton", font=("TkDefaultFont", 11, "bold"), padding=(16, 6))

        # ── Title bar ──────────────────────────────────────────────
        title_frame = ttk.Frame(self.root)
        title_frame.pack(fill=tk.X, padx=12, pady=(10, 2))
        ttk.Label(
            title_frame,
            text="CouncilCast Studio",
            font=("TkDefaultFont", 16, "bold"),
        ).pack(side=tk.LEFT)
        ttk.Label(
            title_frame,
            text="[version 1.0.0]",
            font=("TkDefaultFont", 9),
            foreground="gray",
        ).pack(side=tk.LEFT, padx=(8, 0))

        # ── Workflow header ────────────────────────────────────────
        workflow_frame = ttk.Frame(self.root)
        workflow_frame.pack(fill=tk.X, padx=12, pady=(6, 2))
        ttk.Label(
            workflow_frame,
            text="1. Add sources  →  2. Choose style  →  3. Create podcast",
            font=("TkDefaultFont", 10, "bold"),
            foreground="#444444",
        ).pack(anchor=tk.W)

        # ── Button row 1 ───────────────────────────────────────────
        row1 = ttk.Frame(self.root)
        row1.pack(fill=tk.X, padx=12, pady=(6, 2))

        self.add_btn = ttk.Button(row1, text="Add Source Documents", command=self._add_files)
        self.add_btn.pack(side=tk.LEFT, padx=(0, 4))

        self.remove_btn = ttk.Button(
            row1, text="Remove Selected", command=self._remove_selected
        )
        self.remove_btn.pack(side=tk.LEFT, padx=4)

        # ── Preset selector ────────────────────────────────────────
        preset_frame = ttk.Frame(self.root)
        preset_frame.pack(fill=tk.X, padx=12, pady=(4, 2))

        ttk.Label(preset_frame, text="Council Style:").pack(side=tk.LEFT, padx=(0, 6))
        self.preset_var = tk.StringVar(value="Deep Dive")
        self.preset_combo = ttk.Combobox(
            preset_frame,
            textvariable=self.preset_var,
            values=[
                "Deep Dive",
                "Skeptical Review",
                "Beginner Friendly",
                "Founder Pitch Breakdown",
                "Research Roundtable",
            ],
            state="readonly",
            width=28,
        )
        self.preset_combo.pack(side=tk.LEFT)

        self.demo_mode_check = ttk.Checkbutton(
            preset_frame,
            text="Demo Mode (simulated responses)",
            variable=self.demo_mode_var,
        )
        self.demo_mode_check.pack(side=tk.LEFT, padx=(12, 0))

        self.config_keys_btn = ttk.Button(
            preset_frame,
            text="API Keys",
            command=self._configure_api_keys,
        )
        self.config_keys_btn.pack(side=tk.LEFT, padx=(12, 0))

        # ── Primary action row ─────────────────────────────────────
        row2 = ttk.Frame(self.root)
        row2.pack(fill=tk.X, padx=12, pady=(4, 2))

        self.generate_btn = ttk.Button(
            row2,
            text="Create Podcast From Sources",
            command=self._generate_episode,
            state=tk.DISABLED,
            style="Primary.TButton",
        )
        self.generate_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.generate_hint = ttk.Label(
            row2,
            text="Add at least one source file to begin.",
            font=("TkDefaultFont", 9),
            foreground="#888888",
        )
        self.generate_hint.pack(side=tk.LEFT)

        self.export_btn = ttk.Button(
            row2,
            text="Export Run",
            command=self._export_run,
            state=tk.DISABLED,
        )
        self.export_btn.pack(side=tk.RIGHT, padx=4)

        self.file_count_label = ttk.Label(row2, text="")
        self.file_count_label.pack(side=tk.RIGHT, padx=(4, 8))

        # ── Main split area ────────────────────────────────────────
        main_pw = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pw.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        # Left panel — Source Files list
        left_frame = ttk.LabelFrame(main_pw, text="Source Files", width=280)
        left_frame.pack_propagate(False)
        main_pw.add(left_frame, weight=0)

        listbox_frame = ttk.Frame(left_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL)
        self.files_listbox = tk.Listbox(
            listbox_frame,
            selectmode=tk.EXTENDED,
            yscrollcommand=scrollbar.set,
            font=("TkDefaultFont", 10),
        )
        scrollbar.config(command=self.files_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.files_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Right panel — Notebook with 4 tabs
        self.notebook = ttk.Notebook(main_pw)
        main_pw.add(self.notebook, weight=1)

        self.brief_tab = self._make_text_tab("Source Brief")
        self.discussion_tab = self._make_text_tab("Council Discussion")
        self.script_tab = self._make_text_tab("Podcast Script")
        self.audio_frame = self._make_audio_tab()

        # ── Welcome / empty-state message ──────────────────────────
        welcome_text = (
            "Add a source document to begin.\n\n"
            "CouncilCast Studio will read your source, create a source brief, "
            "run an AI council discussion, write a two-host podcast script, "
            "and optionally generate audio."
        )
        self._update_text_widget(self.brief_tab, welcome_text)

        # ── Status bar ─────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
        )
        status_bar.pack(fill=tk.X, padx=12, pady=(2, 8))

    def _make_text_tab(self, title: str) -> tk.Text:
        """Create a notebook tab containing a read-only Text widget."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=title)
        text_widget = tk.Text(
            frame, wrap=tk.WORD, font=("TkDefaultFont", 10), state=tk.DISABLED
        )
        text_widget.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        return text_widget

    def _make_audio_tab(self) -> ttk.Frame:
        """Create the Audio notebook tab with path, play, and folder controls."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Audio")

        inner = ttk.Frame(frame, padding=16)
        inner.pack(fill=tk.BOTH, expand=True)

        # Audio file path display
        ttk.Label(inner, text="Audio:", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 4)
        )
        self.audio_path_var = tk.StringVar(value="Not generated")
        self.audio_path_label = ttk.Label(
            inner, textvariable=self.audio_path_var, wraplength=500
        )
        self.audio_path_label.grid(row=0, column=1, sticky=tk.W, pady=(0, 4))

        # Button row
        btn_row = ttk.Frame(inner)
        btn_row.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=8)

        self.play_btn = ttk.Button(
            btn_row, text="Play", command=self._play_audio, state=tk.DISABLED
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
            font=("TkDefaultFont", 9),
            foreground="#555555",
        )
        self.audio_status_label.grid(
            row=2, column=0, columnspan=2, sticky=tk.W, pady=(4, 0)
        )

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
            self.generate_hint.pack_forget()
        else:
            self.generate_btn.config(state=tk.DISABLED)
            if not self.selected_files:
                self.generate_hint.pack(side=tk.LEFT)

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
        self.generate_hint.pack_forget()
        self.status_var.set(f"Ready to create podcast from {count} source file(s).")

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
            self.generate_hint.pack(side=tk.LEFT)
            self.status_var.set("Ready. Add source documents to begin.")
            # Restore welcome message
            welcome_text = (
                "Add a source document to begin.\n\n"
                "CouncilCast Studio will read your source, create a source brief, "
                "run an AI council discussion, write a two-host podcast script, "
                "and optionally generate audio."
            )
            self._update_text_widget(self.brief_tab, welcome_text)
        else:
            self.status_var.set(f"Ready to create podcast from {count} source file(s).")

    # ── Generation Pipeline ────────────────────────────────────────────

    def _generate_episode(self) -> None:
        if not self.selected_files:
            messagebox.showwarning("No files", "Please add at least one source file first.")
            return

        # Validate API key in real mode
        if not self.demo_mode_var.get():
            api_key = os.environ.get("COUNCILCAST_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                messagebox.showerror(
                    "API Key Required",
                    "Real LLM mode requires COUNCILCAST_LLM_API_KEY to be set.\n\n"
                    "Either set this environment variable or enable Demo Mode "
                    "to use simulated responses.",
                )
                return

        self.generate_hint.pack_forget()

        self._set_buttons_enabled(False)
        self.export_btn.config(state=tk.DISABLED)
        self.status_var.set("Initializing...")

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
                self.root.after(0, lambda: messagebox.showerror(
                    "Configuration Error",
                    "No LLM provider available. Enable Demo Mode or set COUNCILCAST_LLM_API_KEY.",
                ))
                return
            self.llm_provider = provider

            # 1. Read files
            self.root.after(0, lambda: self.status_var.set("Reading source files..."))
            self.documents = read_documents(self.selected_files)
            file_list_text = format_file_list(self.documents)

            # 2. Generate source brief
            self.root.after(0, lambda: self.status_var.set("Generating source brief..."))
            combined = combine_documents(self.documents)
            self.brief = generate_source_brief(combined, self.llm_provider)
            self.root.after(
                0, lambda: self._update_text_widget(self.brief_tab, self.brief.format())
            )

            # 3. Generate council discussion
            self.root.after(
                0, lambda: self.status_var.set("Generating council discussion...")
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
                0, lambda: self.status_var.set("Generating episode script...")
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
            try:
                tmp = tempfile.NamedTemporaryFile(
                    suffix=".mp3", delete=False
                )
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

        except Exception as e:
            self.root.after(
                0,
                lambda: messagebox.showerror("Generation Error", str(e)),
            )
            self.root.after(0, lambda: self.status_var.set(f"Error: {e}"))
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
            font=("TkDefaultFont", 10, "bold"),
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
            ttk.Label(main, text=line, wraplength=480, font=("TkDefaultFont", 9)).pack(
                anchor=tk.W, pady=(1, 0)
            )

        ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # -- LLM Key --
        llm_frame = ttk.Frame(main)
        llm_frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(llm_frame, text="LLM API Key:", font=("TkDefaultFont", 9, "bold")).pack(anchor=tk.W)
        current_llm = os.environ.get("COUNCILCAST_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
        self._api_llm_var = tk.StringVar(value=current_llm)
        llm_entry = ttk.Entry(llm_frame, textvariable=self._api_llm_var, width=60, show="*")
        llm_entry.pack(fill=tk.X, pady=(2, 0))
        llm_status = _mask(current_llm) if current_llm else "(not set)"
        ttk.Label(llm_frame, text=f"Current: {llm_status}", font=("TkDefaultFont", 8),
                  foreground="#555555").pack(anchor=tk.W)

        # -- TTS Key --
        tts_frame = ttk.Frame(main)
        tts_frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(tts_frame, text="TTS API Key:", font=("TkDefaultFont", 9, "bold")).pack(anchor=tk.W)
        current_tts = os.environ.get("COUNCILCAST_TTS_API_KEY") or ""
        self._api_tts_var = tk.StringVar(value=current_tts)
        tts_entry = ttk.Entry(tts_frame, textvariable=self._api_tts_var, width=60, show="*")
        tts_entry.pack(fill=tk.X, pady=(2, 0))
        tts_status = _mask(current_tts) if current_tts else "(not set)"
        ttk.Label(tts_frame, text=f"Current: {tts_status}", font=("TkDefaultFont", 8),
                  foreground="#555555").pack(anchor=tk.W)

        # -- Toggle visibility checkbox --
        self._api_show_var = tk.BooleanVar(value=False)

        def _toggle_visibility():
            show = self._api_show_var.get()
            llm_entry.config(show="" if show else "*")
            tts_entry.config(show="" if show else "*")

        ttk.Checkbutton(
            main, text="Show keys (keep hidden when sharing screen)",
            variable=self._api_show_var, command=_toggle_visibility,
        ).pack(anchor=tk.W, pady=(2, 0))

        ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # -- Buttons --
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X)

        def _save():
            # Find .env file path (project root)
            project_root = Path(__file__).resolve().parent
            env_path = project_root / ".env"

            # Read existing .env (if any) to preserve non-key lines
            existing_lines = {}
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

            lines = []
            lines.append("# CouncilCast Studio API keys — generated by Configure API Keys dialog")
            lines.append(f"COUNCILCAST_LLM_API_KEY={new_llm}")
            lines.append(f"COUNCILCAST_TTS_API_KEY={new_tts}")

            with open(env_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")

            # Reload environment
            from councilcast.config import load_env
            load_env()

            messagebox.showinfo("Saved", f"Keys saved to {env_path}\n\nRestart the app for all changes to take effect.\n(Keys loaded fresh when you click Generate Episode.)")
            dialog.destroy()

        ttk.Button(btn_frame, text="Save to .env", command=_save).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)


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
