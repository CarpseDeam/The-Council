"""Text-to-speech module — delegates to configured TTS provider."""

import re
from pathlib import Path

from councilcast.config import get_tts_provider


def _clean_for_tts(text: str) -> str:
    """Strip markdown formatting for clearer spoken output."""
    # Remove bold/italic markers but keep inner text
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
    # Remove heading markers (#, ##, etc.) but keep text
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
    # Remove image references
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # Collapse multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def text_to_speech(text: str, output_path: str) -> bool:
    """Synthesize speech from text using the configured TTS provider.

    Returns True if audio was successfully generated, False otherwise.
    """
    provider = get_tts_provider()
    if provider is None:
        print("[audio] No TTS provider available. Skipping audio generation.")
        return False
    try:
        cleaned = _clean_for_tts(text)
        return provider.synthesize(cleaned, output_path)
    except Exception as e:
        print(f"[audio] TTS synthesis failed: {e}")
        return False
