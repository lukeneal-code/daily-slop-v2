"""Style prefix for the cartoon image generator.

This is the Charles-Addams-via-Private-Eye direction agreed for v2 — explicitly
NOT the gothic Addams Family aesthetic of v1. The forbidden tokens (gothic,
macabre, darkly, horror, speech bubble) are exercised by `tests/unit/test_prompts.py`.
"""

from __future__ import annotations

STYLE_PREFIX = (
    "Charles Addams-style ink cartoon for a satirical British newspaper, in the spirit "
    "of Private Eye. Elegant black-and-white pen-and-ink illustration with detailed "
    "crosshatching, witty New Yorker-style composition, single panel, clean negative "
    "space, dry observational humour. No text, words, letters, captions, or speech "
    "bubbles. No gothic or horror motifs."
)


def build_prompt(image_description: str) -> str:
    """Compose the final image prompt from the writer's description.

    Format: <style prefix> | <writer's description>. The single-pipe separator
    keeps the two halves visually distinct in logs/LangFuse without confusing the model.
    """
    return f"{STYLE_PREFIX} | {image_description.strip()}"
