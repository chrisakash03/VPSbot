from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI


@dataclass(frozen=True)
class DigestItem:
    feed_title: str
    title: str
    link: str


def _build_prompt(items: list[DigestItem]) -> str:
    lines = []
    for item in items:
        feed = item.feed_title or "Feed"
        lines.append(f"- [{feed}] {item.title} ({item.link})")
    body = "\n".join(lines)
    return (
        "Summarize these RSS headlines into one concise Telegram message. "
        "Group by topic or feed, use bullet points, keep under 4000 characters.\n\n"
        f"{body}"
    )


def summarize_digest(
    items: list[DigestItem],
    *,
    api_key: str,
    model: str = "gpt-5.6-luna",
) -> str:
    """Produce a concise grouped digest. Isolated from Telegram/RSS orchestration."""
    if not items:
        return ""

    client = OpenAI(api_key=api_key)
    prompt = _build_prompt(items)

    try:
        response = client.responses.create(
            model=model,
            reasoning={"effort": "low"},
            input=[{"role": "user", "content": prompt}],
        )
        text = getattr(response, "output_text", None)
        if text:
            return text.strip()
    except Exception:
        pass

    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        extra_body={"reasoning_effort": "low"},
    )
    return (completion.choices[0].message.content or "").strip()
