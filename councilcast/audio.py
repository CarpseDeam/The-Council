"""Text-to-speech module — delegates to configured TTS provider."""

from pathlib import Path

from councilcast.config import get_tts_provider


def text_to_speech(text: str, output_path: str) -> bool:
    """Synthesize speech from text using the configured TTS provider.

    Returns True if audio was successfully generated, False otherwise.
    """
    provider = get_tts_provider()
    if provider is None:
        print("[audio] No TTS provider available. Skipping audio generation.")
        return False
    try:
        return provider.synthesize(text, output_path)
    except Exception as e:
        print(f"[audio] TTS synthesis failed: {e}")
        return False
