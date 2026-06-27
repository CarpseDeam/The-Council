"""Export — save a full run as a timestamped folder."""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from councilcast.models import SourceBrief, CouncilDiscussion, PodcastScript

EXPORT_BASE = Path("exports")


def export_run(
    source_files: List[str],
    preset: str,
    brief: SourceBrief,
    discussion: CouncilDiscussion,
    script: PodcastScript,
    audio_path: Optional[str] = None,
) -> Path:
    """Export a complete run to a timestamped folder.

    Returns the path to the created folder.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = EXPORT_BASE / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Write source brief
    brief_path = run_dir / "source_brief.md"
    brief_path.write_text(brief.format(), encoding="utf-8")

    # Write council discussion
    discussion_path = run_dir / "council_discussion.md"
    discussion_path.write_text(discussion.format(), encoding="utf-8")

    # Write episode script
    script_path = run_dir / "episode_script.md"
    script_path.write_text(script.format(), encoding="utf-8")

    # Copy audio if generated
    audio_generated = False
    audio_filename: Optional[str] = None
    if audio_path and Path(audio_path).exists():
        suffix = Path(audio_path).suffix
        audio_filename = f"episode_audio{suffix}"
        shutil.copy2(audio_path, run_dir / audio_filename)
        audio_generated = True

    # Build output paths dict
    output_paths = {
        "source_brief": str(brief_path),
        "council_discussion": str(discussion_path),
        "episode_script": str(script_path),
        "episode_audio": str(run_dir / audio_filename) if audio_filename else None,
    }

    # Write run summary JSON
    summary = {
        "timestamp": datetime.now().isoformat(),
        "source_files": [Path(f).name for f in source_files],
        "council_preset": preset,
        "audio_generated": audio_generated,
        "output_paths": output_paths,
    }
    summary_path = run_dir / "run_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return run_dir
