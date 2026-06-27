# CouncilCast Studio

CouncilCast Studio is a Python desktop application that transforms source documents into AI-generated podcast episodes. It uses a simulated "council" of AI roles (Moderator, Explainer, Skeptic, Practical Expert, Simplifier) to discuss your source material, converts that discussion into a two-host podcast script, and can optionally generate audio narration via TTS.

## Features

- **Add Source Documents** — Select `.txt`, `.md`, or `.pdf` files
- **Episode Style** — Choose from Deep Dive, Skeptical Review, Beginner Friendly, Founder Pitch Breakdown, or Research Roundtable
- **Create Podcast From Sources** — Run the full pipeline: source brief → council discussion → podcast script → audio
- **Export Episode Package** — Save all generated artifacts to a timestamped directory
- **Demo Mode** — Try the full workflow immediately with simulated responses, no API key required
- **Real Mode** — Connect to OpenAI for genuine AI-generated content

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Launch the app
python app.py
```

The UI uses `customtkinter` (included in `requirements.txt`). It provides a consistent dark theme with no platform-specific white scrollbar or widget issues.

No API key is required for Demo Mode. The UI uses `customtkinter` for a modern dark theme.

## Configuration

Copy or create a `.env` file in the project root with any of the following:

```
COUNCILCAST_LLM_API_KEY=sk-...           # Required for real LLM mode (OpenAI)
COUNCILCAST_TTS_API_KEY=sk-...           # Optional — for OpenAI TTS audio
```

If `COUNCILCAST_LLM_API_KEY` is not set, the app falls back to `OPENAI_API_KEY` (with a deprecation warning).

### TTS Audio

- If `COUNCILCAST_TTS_API_KEY` is set, OpenAI TTS is used.
- Otherwise, the app attempts to use **gTTS** as a free fallback (requires internet).
  Install it with: `pip install gtts`
- If neither is available, audio generation is skipped gracefully.

### Demo Mode vs Real Mode

- **Demo Mode** (default when no API key is configured): Uses a built-in `FakeLLMProvider` that returns realistic canned content. No API calls are made. All features work end-to-end.
- **Real Mode**: Uses `RealLLMProvider` (OpenAI GPT-4o). Requires `COUNCILCAST_LLM_API_KEY` to be set. Toggle between modes with the **Demo Mode** checkbox in the UI.

### Supported Files

| Extension | Type       | Notes                         |
|-----------|------------|-------------------------------|
| `.txt`    | Plain text |                               |
| `.md`     | Markdown   |                               |
| `.pdf`    | PDF        | Requires `pypdf` (included in requirements) |

## Adding API Keys

To use real AI-generated content (instead of Demo Mode):

1. Copy the example file: `cp .env.example .env`
2. Open `.env` in a text editor
3. Paste your OpenAI API key after `COUNCILCAST_LLM_API_KEY=`
4. Optionally set `COUNCILCAST_TTS_API_KEY=` (can use the same key)
5. Run `python app.py`
6. **Uncheck "Demo Mode"** in the UI to use real generation
7. Or click **Configure Keys** in the app to set keys graphically

## How to Use

1. Click **Add Source Documents** and select one or more supported files.
2. Choose an **Episode Style** from the dropdown (Deep Dive, etc.).
3. (Optional) Uncheck **Demo Mode** and set `COUNCILCAST_LLM_API_KEY` for real AI generation.
4. Click **Create Podcast From Sources** to run the full pipeline.
5. Review results in the **Brief**, **Council**, **Script**, and **Audio** tabs.
6. Click **Export Episode Package** to save all artifacts to a timestamped directory.

## Audio

V1 audio is single-voice narration generated from the podcast script. The Audio tab shows the file path and provides **Play** and **Open Folder** buttons.

## App Flow

Add sources, choose an episode style, create the podcast, then export the episode package.

## Project Structure

| File / Module                 | Purpose                                                  |
|-------------------------------|----------------------------------------------------------|
| `app.py`                      | Tkinter desktop UI entry point                           |
| `councilcast/__init__.py`     | Package marker                                           |
| `councilcast/models.py`       | Dataclasses: SourceDocument, SourceBrief, CouncilTurn, CouncilDiscussion, PodcastScript, RunMetadata |
| `councilcast/config.py`       | LLMProvider ABC, FakeLLMProvider, RealLLMProvider, TTS providers, factory functions |
| `councilcast/ingestion.py`    | File reading, validation, merging, and formatting        |
| `councilcast/prompts.py`      | Prompt builders for brief, discussion, and script        |
| `councilcast/source_brief.py` | Source brief generation and parsing                      |
| `councilcast/council.py`      | Council discussion generation with five AI roles         |
| `councilcast/script_writer.py`| Podcast script generation from council discussion        |
| `councilcast/audio.py`        | Text-to-speech module with markdown cleaning             |
| `councilcast/export.py`       | Export run artifacts to timestamped directory            |
| `samples/example_source.md`   | Sample markdown document about the future of remote work |

## Notes

- **FakeLLMProvider**: Returns deterministic canned responses based on prompt keywords. Useful for development and demonstration without API costs.
- **RealLLMProvider**: Uses OpenAI's GPT-4o via the `openai` Python package. Set `COUNCILCAST_LLM_API_KEY` in your environment or `.env` file.
- **Audio TTS**: Markdown formatting (bold, headings, horizontal rules) is automatically stripped before synthesis so that syntax is not spoken aloud.
