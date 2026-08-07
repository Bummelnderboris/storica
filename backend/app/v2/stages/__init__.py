"""Pipeline stages (DESIGN §5). Each stage reads canon, writes canon or plan, and is gated."""

from .chapter_spec import ChapterSpecGateFailed, ChapterSpecResult, build_chapter_spec
from .conception import ConceptionChoice, PremiseCandidate, conceive
from .gate import GateFailed, GateOutcome, run_gated
from .macro_arc import MacroArcGateFailed, MacroArcResult, build_macro_arc, promote_ledger, to_macro_arc
from .prose import SCENE_DIVIDER, ProseGateFailed, ProseResult, assemble_chapter, write_chapter
from .reconcile import (
    ChapterExtraction,
    Flag,
    FlagKind,
    LedgerUpdate,
    Promotion,
    PromotionKind,
    ReconcileFailed,
    ReconcileResult,
    reconcile_chapter,
)
from .world_cast import (
    CanonGateFailed,
    WorldCastDraft,
    WorldCastResult,
    develop_world_and_cast,
    draft_to_canon,
)

__all__ = [
    # shared gate
    "GateFailed", "GateOutcome", "run_gated",
    # stage 1 — conception
    "PremiseCandidate", "ConceptionChoice", "conceive",
    # stage 2 — world & cast
    "WorldCastDraft", "WorldCastResult", "CanonGateFailed", "develop_world_and_cast", "draft_to_canon",
    # stage 3 — macro arc
    "MacroArcResult", "MacroArcGateFailed", "build_macro_arc", "promote_ledger", "to_macro_arc",
    # stage 4 — JIT chapter spec
    "ChapterSpecResult", "ChapterSpecGateFailed", "build_chapter_spec",
    # stage 5 — grounded prose
    "ProseResult", "ProseGateFailed", "write_chapter", "assemble_chapter", "SCENE_DIVIDER",
    # stage 6 — reconcile
    "ReconcileResult", "ReconcileFailed", "reconcile_chapter", "ChapterExtraction",
    "Promotion", "PromotionKind", "Flag", "FlagKind", "LedgerUpdate",
]
