"""
Deterministic validation of the plan against canon. No LLM.

Same contract as `canon.validation`: return `Issue`s, blocking ones fail the gate. This is the
cheap checker that runs before any LLM checker (DESIGN §6: "cheap checkers first ... expensive LLM
checkers only on what passes" — the F3 cost reclaim).

What it can prove mechanically:
- every id the plan references exists in canon or in the arc (no dangling intent),
- acts partition the chapters and the tension curve covers them,
- the ledger is schedulable (payoff after setup, kept after made, all within range),
- a chapter spec delivers *exactly* the beats/setups/payoffs the arc scheduled for that chapter —
  a spec that quietly advances something scheduled elsewhere is the plan drifting from itself.

What it cannot: whether a beat is *worth* a chapter. That is the Intent checker's job (§6).
"""

from __future__ import annotations

from typing import List, Optional

from ..canon import Issue, Severity, StoryModel
from .model import ChapterSpec, MacroArc, MacroArcDraft


def _range_issue(code: str, ref: str, what: str, chapter: int, count: int) -> Issue:
    return Issue(code, Severity.BLOCKING, f"{what} is chapter {chapter}, outside 1..{count}", ref)


def validate_macro_arc_draft(draft: MacroArcDraft, canon: StoryModel) -> List[Issue]:
    """Validate the stage-3 draft (ledger still inline) against canon."""
    issues: List[Issue] = []
    n = draft.chapter_count
    ids = canon.character_ids()

    if n < 1:
        issues.append(Issue("arc.chapter_count", Severity.BLOCKING, f"chapter_count is {n}", "chapter_count"))
        return issues
    if canon.constraints.chapter_count and canon.constraints.chapter_count != n:
        issues.append(Issue(
            "arc.chapter_count", Severity.BLOCKING,
            f"arc plans {n} chapters but canon constraints say {canon.constraints.chapter_count}",
            "chapter_count"))

    # 1) Acts must partition the chapters exactly ------------------------------------------------
    seen: dict[int, int] = {}
    for act in draft.acts:
        for ch in act.chapters:
            if not 1 <= ch <= n:
                issues.append(_range_issue("arc.act_range", f"act{act.number}", "act chapter", ch, n))
            elif ch in seen:
                issues.append(Issue(
                    "arc.act_overlap", Severity.BLOCKING,
                    f"chapter {ch} is in act {seen[ch]} and act {act.number}", f"act{act.number}"))
            else:
                seen[ch] = act.number
    missing = [ch for ch in range(1, n + 1) if ch not in seen]
    if missing:
        issues.append(Issue(
            "arc.act_gap", Severity.BLOCKING,
            f"chapters {missing} belong to no act", "acts"))

    # 2) Turning points --------------------------------------------------------------------------
    if not draft.turning_points:
        issues.append(Issue("arc.no_turning_point", Severity.WARNING, "the arc has no turning point", "turning_points"))
    for tp in draft.turning_points:
        if not 1 <= tp.chapter <= n:
            issues.append(_range_issue("arc.tp_range", tp.id, "turning point", tp.chapter, n))

    # 3) Arc beats — the intent carriers ---------------------------------------------------------
    seen_beats: set[str] = set()
    beat_chars: set[str] = set()
    for b in draft.arc_beats:
        if b.id in seen_beats:
            issues.append(Issue("arc.dup_beat_id", Severity.BLOCKING, f"duplicate beat id '{b.id}'", b.id))
        seen_beats.add(b.id)
        if b.character_id not in ids:
            issues.append(Issue(
                "arc.beat_character", Severity.BLOCKING,
                f"beat '{b.id}' is assigned to unknown character id '{b.character_id}'", b.id))
        else:
            beat_chars.add(b.character_id)
        if not 1 <= b.chapter <= n:
            issues.append(_range_issue("arc.beat_range", b.id, "beat", b.chapter, n))
    for cid, ch in canon.characters.items():
        if ch.role.value in ("protagonist", "antagonist") and cid not in beat_chars:
            issues.append(Issue(
                "arc.character_no_beat", Severity.WARNING,
                f"{ch.role.value} '{cid}' has no arc beat anywhere in the book", cid))

    # 4) The meaning ledger ----------------------------------------------------------------------
    seen_m: set[str] = set()
    for m in draft.motifs:
        if m.id in seen_m:
            issues.append(Issue("arc.dup_motif_id", Severity.BLOCKING, f"duplicate motif id '{m.id}'", m.id))
        seen_m.add(m.id)
        for label, ch in (("setup_ch", m.setup_ch), ("payoff_ch", m.payoff_ch)):
            if not 1 <= ch <= n:
                issues.append(_range_issue("arc.motif_range", m.id, f"motif {label}", ch, n))
        if m.payoff_ch < m.setup_ch:
            issues.append(Issue(
                "arc.motif_payoff_before_setup", Severity.BLOCKING,
                f"motif '{m.id}' pays off (ch{m.payoff_ch}) before setup (ch{m.setup_ch})", m.id))

    seen_p: set[str] = set()
    for p in draft.promises:
        if p.id in seen_p:
            issues.append(Issue("arc.dup_promise_id", Severity.BLOCKING, f"duplicate promise id '{p.id}'", p.id))
        seen_p.add(p.id)
        if not 1 <= p.made_ch <= n:
            issues.append(_range_issue("arc.promise_range", p.id, "promise made_ch", p.made_ch, n))
        if p.kept_ch == 0:
            # 0 means "deliberately unresolved" — allowed, but it must be a decision, not a slip.
            issues.append(Issue(
                "arc.promise_unkept", Severity.WARNING,
                f"promise '{p.id}' is never kept — this must be deliberate", p.id))
        elif not 1 <= p.kept_ch <= n:
            issues.append(_range_issue("arc.promise_range", p.id, "promise kept_ch", p.kept_ch, n))
        elif p.kept_ch < p.made_ch:
            issues.append(Issue(
                "arc.promise_kept_before_made", Severity.BLOCKING,
                f"promise '{p.id}' is kept (ch{p.kept_ch}) before it is made (ch{p.made_ch})", p.id))

    # 5) Tension curve ---------------------------------------------------------------------------
    curve = {t.chapter for t in draft.tension_curve}
    gaps = [ch for ch in range(1, n + 1) if ch not in curve]
    if gaps:
        issues.append(Issue(
            "arc.tension_gap", Severity.BLOCKING,
            f"tension curve has no entry for chapters {gaps}", "tension_curve"))
    for t in draft.tension_curve:
        if not 1 <= t.tension <= 10:
            issues.append(Issue(
                "arc.tension_range", Severity.WARNING,
                f"chapter {t.chapter} tension {t.tension} is outside 1..10", str(t.chapter)))

    return issues


def validate_chapter_spec(spec: ChapterSpec, canon: StoryModel, arc: MacroArc) -> List[Issue]:
    """Validate one JIT chapter spec against canon and the macro arc."""
    issues: List[Issue] = []
    ids = canon.character_ids()
    ref = f"ch{spec.chapter:02d}"

    if not 1 <= spec.chapter <= arc.chapter_count:
        issues.append(_range_issue("spec.range", ref, "spec", spec.chapter, arc.chapter_count))
    if not spec.purpose.strip():
        issues.append(Issue(
            "spec.no_purpose", Severity.BLOCKING,
            "chapter has no stated purpose — it advances nothing", ref))

    # 1) Cast ------------------------------------------------------------------------------------
    present = set(spec.present_character_ids)
    for cid in spec.present_character_ids:
        if cid not in ids:
            issues.append(Issue("spec.character", Severity.BLOCKING, f"unknown character id '{cid}'", ref))
    if spec.pov_character_id not in ids:
        issues.append(Issue(
            "spec.pov", Severity.BLOCKING, f"unknown POV character id '{spec.pov_character_id}'", ref))
    elif spec.pov_character_id not in present:
        issues.append(Issue(
            "spec.pov_absent", Severity.BLOCKING,
            f"POV character '{spec.pov_character_id}' is not in present_character_ids", ref))

    # 2) The spec must deliver exactly what the arc scheduled here --------------------------------
    scheduled = {b.id for b in arc.beats_for(spec.chapter)}
    assigned = set(spec.advances_beats)
    for bid in assigned - arc.beat_ids():
        issues.append(Issue("spec.beat_unknown", Severity.BLOCKING, f"unknown arc beat id '{bid}'", ref))
    for bid in (assigned & arc.beat_ids()) - scheduled:
        issues.append(Issue(
            "spec.beat_misplaced", Severity.BLOCKING,
            f"beat '{bid}' is scheduled for another chapter, not {spec.chapter}", ref))
    for bid in scheduled - assigned:
        issues.append(Issue(
            "spec.beat_dropped", Severity.BLOCKING,
            f"arc beat '{bid}' is scheduled for chapter {spec.chapter} but the spec does not carry it", ref))

    # 3) Ledger placement must match canon --------------------------------------------------------
    motifs = {m.id: m for m in canon.motifs}
    for mid in spec.setups:
        if mid not in motifs:
            issues.append(Issue("spec.motif_unknown", Severity.BLOCKING, f"unknown motif id '{mid}'", ref))
        elif motifs[mid].setup_ch != spec.chapter:
            issues.append(Issue(
                "spec.motif_misplaced", Severity.BLOCKING,
                f"motif '{mid}' is set up in ch{motifs[mid].setup_ch}, not ch{spec.chapter}", ref))
    for mid in spec.payoffs:
        if mid not in motifs:
            issues.append(Issue("spec.motif_unknown", Severity.BLOCKING, f"unknown motif id '{mid}'", ref))
        elif motifs[mid].payoff_ch != spec.chapter:
            issues.append(Issue(
                "spec.motif_misplaced", Severity.BLOCKING,
                f"motif '{mid}' pays off in ch{motifs[mid].payoff_ch}, not ch{spec.chapter}", ref))
    for mid, m in motifs.items():
        if m.setup_ch == spec.chapter and mid not in spec.setups:
            issues.append(Issue(
                "spec.motif_dropped", Severity.BLOCKING,
                f"motif '{mid}' is scheduled to be set up in this chapter but the spec omits it", ref))
        if m.payoff_ch == spec.chapter and mid not in spec.payoffs:
            issues.append(Issue(
                "spec.motif_dropped", Severity.BLOCKING,
                f"motif '{mid}' is scheduled to pay off in this chapter but the spec omits it", ref))

    promises = {p.id: p for p in canon.promises}
    for pid in spec.promises_made:
        if pid not in promises:
            issues.append(Issue("spec.promise_unknown", Severity.BLOCKING, f"unknown promise id '{pid}'", ref))
        elif promises[pid].made_ch != spec.chapter:
            issues.append(Issue(
                "spec.promise_misplaced", Severity.BLOCKING,
                f"promise '{pid}' is made in ch{promises[pid].made_ch}, not ch{spec.chapter}", ref))
    for pid in spec.promises_kept:
        if pid not in promises:
            issues.append(Issue("spec.promise_unknown", Severity.BLOCKING, f"unknown promise id '{pid}'", ref))
        elif promises[pid].kept_ch != spec.chapter:
            issues.append(Issue(
                "spec.promise_misplaced", Severity.BLOCKING,
                f"promise '{pid}' is kept in ch{promises[pid].kept_ch}, not ch{spec.chapter}", ref))
    for pid, p in promises.items():
        if p.made_ch == spec.chapter and pid not in spec.promises_made:
            issues.append(Issue(
                "spec.promise_dropped", Severity.BLOCKING,
                f"promise '{pid}' is scheduled to be made in this chapter but the spec omits it", ref))
        if p.kept_ch == spec.chapter and pid not in spec.promises_kept:
            issues.append(Issue(
                "spec.promise_dropped", Severity.BLOCKING,
                f"promise '{pid}' is scheduled to be kept in this chapter but the spec omits it", ref))

    # 4) Scenes ----------------------------------------------------------------------------------
    if not spec.scenes:
        issues.append(Issue("spec.no_scenes", Severity.BLOCKING, "chapter has no scenes", ref))
    seen_scenes: set[str] = set()
    for sc in spec.scenes:
        if sc.id in seen_scenes:
            issues.append(Issue("spec.dup_scene_id", Severity.BLOCKING, f"duplicate scene id '{sc.id}'", ref))
        seen_scenes.add(sc.id)
        for cid in sc.character_ids:
            if cid not in present:
                issues.append(Issue(
                    "spec.scene_cast", Severity.BLOCKING,
                    f"scene '{sc.id}' uses '{cid}', who is not in the chapter's cast", ref))
        if not sc.intent.strip():
            issues.append(Issue("spec.scene_intent", Severity.BLOCKING, f"scene '{sc.id}' has no intent", ref))
        if not sc.turn.strip():
            issues.append(Issue(
                "spec.scene_no_turn", Severity.BLOCKING,
                f"scene '{sc.id}' changes nothing — nothing turns in it", ref))

    return issues


def validate_continuity(spec: ChapterSpec, previous: Optional[ChapterSpec]) -> List[Issue]:
    """Warn where the previous chapter's exit state is dropped instead of carried or changed."""
    if previous is None:
        return []
    entry_keys = {s.key for s in spec.entry_state}
    return [
        Issue(
            "spec.continuity_gap", Severity.WARNING,
            f"ch{previous.chapter} exits with '{s.key}' but ch{spec.chapter} does not carry it",
            f"ch{spec.chapter:02d}",
        )
        for s in previous.exit_state
        if s.key not in entry_keys
    ]
