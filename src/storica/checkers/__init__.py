"""The verification layer: fresh, canon-armed readers with teeth (DESIGN §6)."""

from .auditor import FinalAuditor, audit_ledger
from .base import Checker, CheckerIssue, Decision, Escalation, Verdict
from .canon_consistency import CanonConsistencyChecker
from .consensus import ConsensusProseChecker, majority_threshold, with_consensus
from .defaults import default_prose_checkers
from .intent import IntentChecker
from .micro_sense import MicroSenseChecker
from .prose_base import ProseChecker, ProseCheckerBase, unit_label
from .registry import (
    PROSE_GATE,
    Authority,
    BoundedProseChecker,
    ReaderSpec,
    Scope,
    ScopedProseChecker,
    build_prose_gate,
)
from .vitality import VitalityChecker
from .voice import AuthorVoiceChecker

__all__ = [
    # contracts
    "Checker", "CheckerIssue", "Decision", "Escalation", "Verdict",
    "ProseChecker", "ProseCheckerBase", "unit_label",
    # sampling: majority-blocking over k draws (calibration C4)
    "ConsensusProseChecker", "with_consensus", "majority_threshold",
    # the gate as policy: lens x trigger x authority, in one table
    "PROSE_GATE", "ReaderSpec", "Scope", "Authority", "build_prose_gate",
    "ScopedProseChecker", "BoundedProseChecker",
    "default_prose_checkers",
    # the assignment, at three seams: arc, spec, and the chapter that came out
    "IntentChecker",
    # prose units — one per failure class (DESIGN §2)
    "CanonConsistencyChecker",   # coherence
    "MicroSenseChecker",         # micro-truth
    "AuthorVoiceChecker",        # voice + the brief's forbidden list
    "VitalityChecker",           # inertness — the only reader that fails prose for being safe
    # the whole book, once, at the end
    "FinalAuditor", "audit_ledger",
]
