"""The verification layer: fresh, canon-armed readers with teeth (DESIGN §6)."""

from .auditor import FinalAuditor, audit_ledger
from .base import Checker, CheckerIssue, Decision, Escalation, Verdict
from .canon_consistency import CanonConsistencyChecker
from .intent import IntentChecker
from .micro_sense import MicroSenseChecker
from .prose_base import ProseChecker
from .voice import AuthorVoiceChecker

__all__ = [
    # contracts
    "Checker", "CheckerIssue", "Decision", "Escalation", "Verdict", "ProseChecker",
    # plan units
    "IntentChecker",
    # prose units — one per failure class (DESIGN §2)
    "CanonConsistencyChecker",   # coherence
    "MicroSenseChecker",         # micro-truth
    "AuthorVoiceChecker",        # voice + the brief's forbidden list
    # the whole book, once, at the end
    "FinalAuditor", "audit_ledger",
]
