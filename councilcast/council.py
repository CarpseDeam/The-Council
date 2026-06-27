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
    """Parse role-labeled turns from the LLM response."""
    turns: list[CouncilTurn] = []
    pattern = re.compile(r"^\*\*(.+?)\*\*\s*:\s*(.+)$", re.MULTILINE)
    for match in pattern.finditer(response):
        role = match.group(1).strip()
        text = match.group(2).strip()
        turns.append(CouncilTurn(role=role, text=text))
    if not turns:
        turns.append(
            CouncilTurn(
                role="Moderator",
                text="No discussion could be parsed from the generated content.",
            )
        )
    return CouncilDiscussion(turns=turns)
