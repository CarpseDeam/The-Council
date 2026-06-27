"""Podcast script generation — converts council discussion into two-host script."""

from councilcast.config import LLMProvider
from councilcast.models import CouncilDiscussion, PodcastScript
from councilcast.prompts import build_script_prompt


def generate_script(
    discussion: CouncilDiscussion, provider: LLMProvider
) -> PodcastScript:
    """Generate a two-host podcast script from a council discussion."""
    prompt = build_script_prompt(discussion.format())
    response = provider.generate(prompt)
    return PodcastScript(full_text=response)
