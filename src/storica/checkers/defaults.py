"""
The default prose gate.

Which readers run, on what, and with how much authority is one table in `registry.py` — this
module is only the entry point the pipeline calls. It kept its name because the run loop, the CLI
and the tests all speak it.
"""

from __future__ import annotations

from typing import List, Optional

from ..llm import StructuredLLM
from ..trace import Tracer
from .prose_base import ProseChecker
from .registry import build_prose_gate


def default_prose_checkers(
    llm: StructuredLLM, tracer: Optional[Tracer] = None, *, samples: int = 3
) -> List[ProseChecker]:
    """
    The readers a run uses, assembled from `registry.PROSE_GATE`.

    One lens per failure class (DESIGN §2), cheapest-to-satisfy first: canon-consistency leads
    because a contradiction makes every other judgement moot, and the gate stops there when it
    blocks. Vitality is last and is the odd one out — the others ask whether the prose conforms,
    it asks whether the prose is alive.
    """
    return build_prose_gate(llm, tracer, samples=samples)
