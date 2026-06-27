import os
import warnings
from abc import ABC, abstractmethod
from pathlib import Path


def load_env() -> None:
    """Load environment variables from .env file in project root (or parent)."""
    # Search from cwd upward for .env
    candidates = [Path.cwd() / ".env"]
    candidates.append(Path(__file__).resolve().parent.parent / ".env")
    for env_path in candidates:
        if env_path.exists():
            try:
                from dotenv import load_dotenv

                load_dotenv(env_path)
                return
            except ImportError:
                # Manual .env parsing
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            value = value.strip().strip("\"'")
                            if key and not os.environ.get(key):
                                os.environ[key] = value
                return


# Load env on import
load_env()


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        return ""


class FakeLLMProvider(LLMProvider):
    """Returns canned responses matching the new prompt formats."""

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        prompt_lower = prompt.lower()
        if "podcast episode script" in prompt_lower or "two-host podcast" in prompt_lower:
            return _FAKE_SCRIPT.lstrip()
        if "council discussion" in prompt_lower and "five distinct roles" in prompt_lower:
            return _FAKE_COUNCIL_DISCUSSION.lstrip()
        if "structured brief" in prompt_lower or "source brief" in prompt_lower:
            return _FAKE_SOURCE_BRIEF.lstrip()
        return _FAKE_SOURCE_BRIEF.lstrip()


class RealLLMProvider(LLMProvider):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        import openai

        client = openai.OpenAI(api_key=self.api_key)
        messages: list = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7,
        )
        return response.choices[0].message.content


class TTSProvider(ABC):
    @abstractmethod
    def synthesize(self, text: str, output_path: str) -> bool:
        return False


class RealTTSProvider(TTSProvider):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def synthesize(self, text: str, output_path: str) -> bool:
        import openai

        client = openai.OpenAI(api_key=self.api_key)
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text,
        )
        response.stream_to_file(output_path)
        return Path(output_path).exists()


class GTTSTTSProvider(TTSProvider):
    """Free TTS fallback using gTTS — no API key required."""

    def synthesize(self, text: str, output_path: str) -> bool:
        from gtts import gTTS

        tts = gTTS(text=text, lang="en")
        tts.save(output_path)
        return Path(output_path).exists()


def get_llm_provider() -> LLMProvider:
    """Return a RealLLMProvider if a key is configured, otherwise FakeLLMProvider."""
    api_key = os.environ.get("COUNCILCAST_LLM_API_KEY")
    if api_key:
        return RealLLMProvider(api_key)
    # Legacy fallback
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        warnings.warn(
            "Using OPENAI_API_KEY. Rename to COUNCILCAST_LLM_API_KEY for clarity.",
            UserWarning,
        )
        return RealLLMProvider(api_key)
    return FakeLLMProvider()


def get_tts_provider() -> TTSProvider | None:
    """Return a TTS provider if available, else None."""
    api_key = os.environ.get("COUNCILCAST_TTS_API_KEY")
    if api_key:
        return RealTTSProvider(api_key)
    # Try gTTS as free fallback
    try:
        import gtts  # noqa: F401

        return GTTSTTSProvider()
    except ImportError:
        return None


def has_real_llm() -> bool:
    """Check whether a real LLM API key is configured."""
    return bool(os.environ.get("COUNCILCAST_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY"))


# Backward-compatible alias for app.py
get_provider = get_llm_provider


# ── Canned content for FakeLLMProvider ──────────────────────────────────

_FAKE_SOURCE_BRIEF = """## Title
The Future of Remote Work: Benefits, Challenges, and Emerging Solutions

## Summary
The source document examines the transformation of work culture accelerated by the global pandemic, presenting a comprehensive overview of remote work's benefits including improved work-life balance, cost savings, and productivity gains. It also addresses major challenges such as communication barriers, company culture erosion, and management adaptation. The document concludes with emerging hybrid work models and open questions about long-term implications for career advancement, urban economies, and innovation.

## Key Points
• 76% of workers report higher job satisfaction when working remotely
• Companies save an average of $11,000 per year per remote employee
• Remote work can increase productivity by up to 40%
• 94% of employers say productivity has been the same or higher since switching to remote work
• Hybrid models are becoming the most popular approach post-pandemic

## Important Details
• The shift to remote work accelerated dramatically during the 2020 pandemic
• Hybrid models include fixed hybrid, flex hybrid, office-first, and remote-first approaches
• Technology infrastructure is critical for successful remote work
• Asynchronous communication practices are key for distributed teams
• 67% of remote workers report feeling less connected to colleagues

## Questions Worth Discussing
• How will long-term remote work affect company culture and team cohesion?
• What is the ideal balance between remote and in-office work?
• How can companies ensure equitable career advancement for remote workers?
• What impact will widespread remote work have on urban centers and commercial real estate?
• Can fully remote companies maintain innovation at the same rate as in-person teams?
"""

_FAKE_COUNCIL_DISCUSSION = """**Moderator**: Welcome everyone to today's council discussion on the future of remote work. We've reviewed a source document covering key benefits, challenges, and emerging solutions. Let's begin by examining the core claim that remote work increases productivity by up to 40%.

**Explainer**: That's a fascinating statistic. The productivity gains come from several factors. Workers experience fewer interruptions in a focused home environment, they save commuting time that can be redirected to work, and many report greater autonomy over their schedules which boosts motivation. The Stanford study referenced in the source confirms a 13% average productivity increase across industries.

**Skeptic**: I'd push back on the 40% figure. While it sounds impressive, we need to consider selection bias. Companies that track and report productivity metrics are often those already optimized for remote work. For traditional industries like manufacturing or hospitality, the numbers would look very different. Also, self-reported productivity has known reliability issues.

**Practical Expert**: From implementation experience, productivity gains depend heavily on role type. Knowledge workers and individual contributors adapt very well to remote work. But collaborative roles, sales teams, and hands-on positions face real challenges. I've seen a 20-30% retention boost when companies invest in intentional remote culture, but that takes deliberate effort and budget.

**Simplifier**: So what I'm hearing is: remote work can boost productivity for some people in some jobs, but it's not universal. The key is matching the work model to the role and investing in the right infrastructure and culture.

**Moderator**: Excellent synthesis. Let's move to the challenge of company culture and team cohesion, which the source identifies as a major concern with 67% of remote workers feeling less connected.

**Explainer**: Company culture traditionally relies on informal interactions — water cooler conversations, spontaneous brainstorming, team lunches. Remote work strips these away unless organizations deliberately recreate them. The source notes that 76% of workers report higher satisfaction, but satisfaction doesn't always equal strong cultural connection. Leading companies are using virtual coffee chats, structured team rituals, and regular in-person meetups.

**Skeptic**: I'd argue that forced in-office culture was often problematic before remote work became widespread. Many companies had poor culture long before the pandemic. The real issue isn't remote work itself, but whether companies invest in intentional culture building regardless of where employees sit. Hybrid models can create a two-tier system where in-office employees get better assignments and faster promotions.

**Practical Expert**: The most effective hybrid models use a core hours approach — everyone in the office on the same 2-3 days. This avoids FOMO and ensures collaboration happens naturally. Async-first communication is also critical: written documentation over verbal instruction, recorded meetings instead of live attendance, and clear response time expectations.

**Simplifier**: So culture doesn't have to suffer with remote work — you just have to be more intentional. Have clear policies, invest in the right tools, and make sure everyone gets equal opportunities whether they're in the office or at home.

**Moderator**: Thank you all. Let's wrap up by considering the open questions about long-term impacts on career advancement and urban economies. What should our listeners take away from this discussion?

**Explainer**: The key takeaway is that remote work isn't disappearing. The source makes clear that the pandemic accelerated an existing trend, and now we're figuring out how to make it work long-term. Companies that invest in intentional culture-building, good async communication practices, and thoughtful hybrid policies will thrive.

**Skeptic**: But we should remain skeptical of one-size-fits-all solutions. Different industries, company sizes, and roles need different approaches. The data is still evolving, and long-term studies on career advancement for remote workers are only now beginning.

**Practical Expert**: My advice to organizations: start with clear principles about what you value in collaboration and culture, then design your remote or hybrid policy around those principles. Invest in manager training — the shift from oversight-by-observation to outcomes-based management is one of the hardest but most important changes.

**Simplifier**: Bottom line: remote work works when you work at it. There's no magic formula, but the companies that will succeed are the ones that are thoughtful, intentional, and willing to adapt as we learn more.

**Moderator**: Thank you all for this rich discussion. We've covered productivity, culture, hybrid models, and practical advice. Let's move now to drafting our podcast script based on these insights.
"""

_FAKE_SCRIPT = """## Title: The Remote Work Revolution — What the Data Really Says

**Host A**: Welcome back to CouncilCast! I'm your host, Alex.

**Host B**: And I'm Jordan. Today we're diving into one of the biggest workplace transformations of our time: the future of remote work. Alex, the numbers in the source document are pretty staggering — 76% higher job satisfaction, 40% productivity gains, massive cost savings for companies.

**Host A**: Absolutely, Jordan. But as our council discussion revealed, these headline numbers come with important caveats. The productivity gains, for instance, depend heavily on role type and industry. Knowledge workers thrive remotely, but hands-on and collaborative roles face real challenges.

**Host B**: And that 40% figure? Our skeptic pointed out there's likely selection bias in those reports. Companies already optimized for remote work are the ones measuring and publishing those numbers.

**Host A**: Good point. Let's talk about culture, because that's where 67% of remote workers say they feel less connected. The council discussed how intentional culture-building — virtual coffee chats, structured rituals, async-first communication — can bridge that gap.

**Host B**: The hybrid model is emerging as the compromise everyone's looking for. But it brings its own complications. In-office employees can get more face time with leadership, better assignments, and faster promotions. Our practical expert recommended a core-hours approach where everyone is together on the same days.

**Host A**: That avoids what some call the two-tier system. And the simplifier made a great point: remote work works when you work at it. There's no magic formula.

**Host B**: So what's the bottom line for our listeners? Companies that invest in intentional culture, good async practices, and thoughtful hybrid policies will be the ones that thrive. Different roles need different approaches, and the data is still evolving.

**Host A**: Exactly. Remote work isn't going away. The pandemic accelerated a trend that was already in motion, and now we're figuring out how to make it work long-term. Thanks for joining us on CouncilCast!

**Host B**: If you enjoyed this episode, subscribe and leave us a review. Until next time!
"""
