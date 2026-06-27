"""Source brief generation — creates structured brief from document text."""

from councilcast.config import LLMProvider
from councilcast.models import SourceBrief
from councilcast.prompts import build_brief_prompt


def generate_source_brief(text: str, provider: LLMProvider) -> SourceBrief:
    """Generate a structured source brief from the given text."""
    prompt = build_brief_prompt(text)
    response = provider.generate(prompt)
    return _parse_brief(response)


def _parse_brief(response: str) -> SourceBrief:
    """Parse the LLM response into a SourceBrief dataclass."""
    sections: dict = {
        "Title": "",
        "Summary": "",
        "Key Points": [],
        "Important Details": [],
        "Questions Worth Discussing": [],
    }
    current_section: str | None = None

    for line in response.splitlines():
        stripped = line.strip()

        # Section heading (## Title, ## Summary, etc.)
        if stripped.startswith("## "):
            heading = stripped[3:].strip()
            if heading in sections:
                current_section = heading
            else:
                current_section = None

        # Title from # Title (first line)
        elif stripped.startswith("# ") and current_section is None:
            sections["Title"] = stripped[2:].strip()

        # Summary accumulates lines
        elif current_section == "Summary":
            if stripped:
                if sections["Summary"]:
                    sections["Summary"] += " " + stripped
                else:
                    sections["Summary"] = stripped

        # Bullet items for list sections
        elif current_section in ("Key Points", "Important Details", "Questions Worth Discussing"):
            for marker in ("•", "-", "*"):
                if stripped.startswith(marker):
                    item = stripped[len(marker):].strip()
                    if item:
                        sections[current_section].append(item)
                    break

    brief = SourceBrief(
        title=sections["Title"],
        summary=sections["Summary"],
        key_points=sections["Key Points"],
        important_details=sections["Important Details"],
        questions_worth_discussing=sections["Questions Worth Discussing"],
    )

    # Fallbacks for empty fields
    if not brief.title:
        brief.title = "Source Brief"
    if not brief.summary:
        brief.summary = "(No summary could be parsed from the source.)"
    if not brief.key_points:
        brief.key_points = ["(No key points could be parsed.)"]
    if not brief.important_details:
        brief.important_details = ["(No important details could be parsed.)"]
    if not brief.questions_worth_discussing:
        brief.questions_worth_discussing = ["(No questions could be parsed.)"]

    return brief
