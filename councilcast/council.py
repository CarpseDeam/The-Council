"""Council discussion generation — five AI roles discuss the source brief."""

import re

from councilcast.config import LLMProvider
from councilcast.models import CouncilDiscussion, CouncilTurn, SourceBrief
from councilcast.prompts import build_discussion_prompt


def generate_council_discussion(
    brief: SourceBrief, provider: LLMProvider, preset: str = "deep_dive"
) -> CouncilDiscussion:
    """Generate a council discussion from a source brief with the given preset style."""
    prompt = build_discussion_prompt(brief.format(), preset)
    response = provider.generate(prompt)
    return _parse_discussion(response)


def _parse_discussion(response: str) -> CouncilDiscussion:
    """Parse role-labeled turns from the LLM response.

    Captures multi-line text for each turn until the next role label.
    """
    turns: list[CouncilTurn] = []
    # Match role labels like **Moderator**: at start of line
    pattern = re.compile(r'^\*\*(.+?)\*\*\s*:\s*', re.MULTILINE)
    matches = list(pattern.finditer(response))
    if not matches:
        turns.append(CouncilTurn(
            role="Moderator",
            text="No discussion could be parsed from the generated content.",
        ))
        return CouncilDiscussion(turns=turns)
    for i, match in enumerate(matches):
        role = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(response)
        text = response[start:end].strip()
        turns.append(CouncilTurn(role=role, text=text))
    return CouncilDiscussion(turns=turns)
