"""
The default prose gate: which readers run, in which order, and which of them are sampled.

Both of those are policy, and both were argued for rather than guessed — which is why they live
next to the checkers they configure rather than in the module that wires the pipeline together.
"""

from __future__ import annotations

from typing import List, Optional

from ..llm import StructuredLLM
from ..trace import Tracer
from .canon_consistency import CanonConsistencyChecker
from .consensus import with_consensus
from .micro_sense import MicroSenseChecker
from .prose_base import ProseChecker
from .vitality import VitalityChecker
from .voice import AuthorVoiceChecker


def default_prose_checkers(
    llm: StructuredLLM, tracer: Optional[Tracer] = None, *, samples: int = 3
) -> List[ProseChecker]:
    """
    One reader per failure class (DESIGN §2), cheapest-to-satisfy first.

    Canon-consistency runs before micro-sense and voice because a contradiction makes the other two
    judgements moot: there is no point polishing the texture of a paragraph that says the wrong man
    signed the certificate.

    Vitality runs last, and it is the odd one out: the first three ask whether the prose conforms,
    and it asks whether the prose is alive. Without it a chapter that matches canon, hits its beats
    and sounds like the author passes the whole gate no matter how inert it is — and since repair
    moves prose toward the rubric, that is the chapter this pipeline naturally produces.
    """
    return with_consensus(
        [
            CanonConsistencyChecker(llm, tracer=tracer),
            MicroSenseChecker(llm, tracer=tracer),
            AuthorVoiceChecker(llm, tracer=tracer),
            VitalityChecker(llm, tracer=tracer),
        ],
        samples=samples,
        tracer=tracer,
    )
