from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class SourceDocument:
    path: str
    content: str


@dataclass
class SourceBrief:
    title: str = ""
    summary: str = ""
    key_points: List[str] = field(default_factory=list)
    important_details: List[str] = field(default_factory=list)
    questions_worth_discussing: List[str] = field(default_factory=list)

    def format(self) -> str:
        lines: List[str] = []
        if self.title:
            lines.append(f"# {self.title}")
            lines.append("")
        if self.summary:
            lines.append("## Summary")
            lines.append(self.summary)
            lines.append("")
        if self.key_points:
            lines.append("## Key Points")
            for kp in self.key_points:
                lines.append(f"• {kp}")
            lines.append("")
        if self.important_details:
            lines.append("## Important Details")
            for d in self.important_details:
                lines.append(f"• {d}")
            lines.append("")
        if self.questions_worth_discussing:
            lines.append("## Questions Worth Discussing")
            for q in self.questions_worth_discussing:
                lines.append(f"• {q}")
            lines.append("")
        return "\n".join(lines)


@dataclass
class CouncilTurn:
    role: str
    text: str


@dataclass
class CouncilDiscussion:
    turns: List[CouncilTurn] = field(default_factory=list)

    def format(self) -> str:
        lines: List[str] = []
        for turn in self.turns:
            lines.append(f"**{turn.role}**: {turn.text}")
            lines.append("")
        return "\n".join(lines)


@dataclass
class PodcastScript:
    full_text: str

    def format(self) -> str:
        return self.full_text


@dataclass
class RunMetadata:
    timestamp: str = ""
    source_files: List[str] = field(default_factory=list)
    council_preset: str = ""
    audio_generated: bool = False
    output_paths: dict = field(default_factory=dict)
