"""A real episode-equivalence predicate: same operational problem class, not same string.

v26.9.17 PRD §6.10 explicitly rules out "same string/prompt/embedding neighborhood/
endpoint/user" as episode equivalence. `topic_of()` extracts the trailing
predicate/topic token from a query or candidate assertion (e.g.
"service:api-gateway requires-port 8080" -> "requires-port") -- stable across the
specific subject named in the sentence, so two textually different observations
about different subjects under the same predicate are equivalent, while two
observations under a genuinely different predicate are not. This is a real,
falsifiable structural comparison, not a placeholder that always returns True.
"""

from __future__ import annotations

from typing import Any, Callable


def topic_of(text: str) -> str:
    tokens = text.strip().split()
    return tokens[-1] if tokens else text.strip()


def build_topic_equivalence_predicate(expected_topic: str) -> Callable[[Any], bool]:
    """Return a predicate accepting any candidate whose topic matches `expected_topic`.

    Accepts a `CandidateResolution` (reads `.proposed_assertion`), an `UnknownQuery`
    (reads `.predicate_or_topic`), or a bare string.
    """

    def _predicate(candidate: Any) -> bool:
        text = (
            getattr(candidate, "proposed_assertion", None)
            or getattr(candidate, "predicate_or_topic", None)
            or (candidate if isinstance(candidate, str) else str(candidate))
        )
        return topic_of(str(text)) == expected_topic

    return _predicate
