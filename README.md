# CouncilCast

CouncilCast is a Python desktop application that transforms source documents into AI-generated podcast scripts. It uses a simulated "council" of AI roles (Moderator, Explainer, Skeptic, Practical Expert, Simplifier) to discuss your source material, then converts that discussion into a two-host podcast script.

**No API keys required** — the built-in `FakeLLMProvider` generates realistic canned content so you can try the full workflow immediately.

## Quick Start

```bash
# Requires Python 3.9+
python app.py
```

No dependencies beyond the Python standard library. The UI uses `tkinter` (included with most Python installations).

## How to Use

1. Click **Select Files** and choose one or more `.txt` or `.md` files
2. Click **Generate Overview** to run the full pipeline:
   - Files are read and displayed in the Source Files tab
   - A structured source brief is generated (Main Topics, Key Claims, Important Details, Open Questions)
   - A council discussion is created with five distinct AI roles
   - A two-host podcast script is produced
3. Click **Save Script** to write the podcast script to a `.txt` file

## Project Structure

| File | Purpose |
|------|---------|
| `app.py` | Tkinter desktop UI entry point |
| `councilcast/__init__.py` | Package marker, version |
| `councilcast/models.py` | Dataclasses: SourceDocument, SourceBrief, CouncilTurn, CouncilDiscussion, PodcastScript |
| `councilcast/config.py` | LLMProvider ABC, FakeLLMProvider, RealLLMProvider stub, factory function |
| `councilcast/ingestion.py` | File reading, validation, merging, and formatting |
| `councilcast/source_brief.py` | Source brief generation and parsing |
| `councilcast/council.py` | Council discussion generation with five AI roles |
| `councilcast/script_writer.py` | Podcast script generation from council discussion |
| `councilcast/audio.py` | TTS stub (placeholder for future integration) |
| `samples/example_source.md` | Sample markdown document about the future of remote work |

## Notes

- **FakeLLMProvider**: Returns deterministic canned responses based on prompt keywords. Useful for development and demonstration without API costs.
- **RealLLMProvider**: A stub class that currently delegates to FakeLLMProvider. To integrate a real LLM (e.g., OpenAI), implement the `generate` method in `RealLLMProvider` and set the `OPENAI_API_KEY` environment variable.
- **Audio**: The `text_to_speech` function in `audio.py` is a stub that prints a message and returns `False`. Future integration with a TTS library (pyttsx3, gTTS, OpenAI TTS) can be added there.