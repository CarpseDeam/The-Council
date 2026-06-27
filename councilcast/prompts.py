"""Prompt templates for LLM generation."""

PRESET_INSTRUCTIONS = {
    "deep_dive": "This should be a DEEP DIVE discussion. Be thorough, nuanced, and explore the source material in depth. Each speaker should provide detailed analysis and explore subtleties.",
    "skeptical_review": "This is a SKEPTICAL REVIEW. Emphasize challenging assumptions, questioning weak claims, and identifying missing evidence. Push back on unsupported statements.",
    "beginner_friendly": "This is a BEGINNER-FRIENDLY discussion. Use plain language, define jargon, and avoid unexplained terms. Assume the audience knows nothing about the topic.",
    "founder_pitch": "This is a FOUNDER PITCH BREAKDOWN. Focus on value proposition, product-market fit, business viability, risks, and opportunities. Analyze from an investor/entrepreneur perspective.",
    "research_roundtable": "This is a RESEARCH ROUNDTABLE. Maintain a balanced, academic-style discussion. Present evidence, cite sources, and engage in rigorous intellectual exchange.",
}

ROLE_DESCRIPTIONS = {
    "Moderator": "Guides the conversation, asks questions, and ensures balanced discussion.",
    "Explainer": "Provides clear explanations of concepts and data from the source document.",
    "Skeptic": "Challenges assumptions, asks critical questions, and points out potential flaws.",
    "Practical Expert": "Offers real-world implementation insights and practical advice based on experience.",
    "Simplifier": "Summarizes complex points in simple terms and highlights key takeaways.",
}


def build_brief_prompt(text: str) -> str:
    """Build prompt for source brief generation."""
    return (
        "Analyze the following source document and produce a structured brief with these sections:\n\n"
        "## Title\n"
        "(a concise, descriptive title for this brief)\n\n"
        "## Summary\n"
        "(1-2 paragraph summary of the source material)\n\n"
        "## Key Points\n"
        "• (list the main points covered in the source)\n"
        "• ...\n\n"
        "## Important Details\n"
        "• (list important supporting details, data, or context)\n"
        "• ...\n\n"
        "## Questions Worth Discussing\n"
        "• (list open questions, unresolved issues, or topics worth further discussion)\n"
        "• ...\n\n"
        "Use bullet items (•) for each entry in the lists. "
        "Ensure each section header is exactly as shown (## Title, ## Summary, etc.).\n\n"
        "SOURCE DOCUMENT:\n"
        "---\n"
        f"{text}\n"
        "---"
    )


def build_discussion_prompt(brief_text: str, preset: str = "deep_dive") -> str:
    """Build prompt for council discussion generation based on preset."""
    roles_text = "\n".join(
        f"- **{role}**: {desc}" for role, desc in ROLE_DESCRIPTIONS.items()
    )
    preset_instr = PRESET_INSTRUCTIONS.get(preset, PRESET_INSTRUCTIONS["deep_dive"])

    return (
        f"Based on the following source brief, generate a council discussion "
        f"with five distinct roles:\n\n"
        f"{roles_text}\n\n"
        f"{preset_instr}\n\n"
        f"Each turn must start with **Role**: Text on the same line.\n"
        f"Each role should speak at least twice.\n"
        f"The discussion should explore the source material, challenge ideas, "
        f"and build toward insights.\n\n"
        f"SOURCE BRIEF:\n"
        f"---\n"
        f"{brief_text}\n"
        f"---"
    )


def build_script_prompt(discussion_text: str) -> str:
    """Build prompt for two-host episode script generation."""
    return (
        "Convert the following council discussion into a polished two-host podcast episode script.\n\n"
        "Use ONLY these two speakers:\n"
        "- **Host A**\n"
        "- **Host B**\n\n"
        "The script MUST include:\n"
        "- A title (prefixed with ## Title:)\n"
        "- A short intro\n"
        "- Clear sections with natural host transitions\n"
        "- Important source-backed points drawn from the discussion\n"
        "- A short closing/outro\n\n"
        "Format each line as:\n"
        "**Host A**: <dialogue>\n"
        "**Host B**: <dialogue>\n\n"
        "Keep the conversation natural and engaging for listeners.\n\n"
        "COUNCIL DISCUSSION:\n"
        "---\n"
        f"{discussion_text}\n"
        "---"
    )
