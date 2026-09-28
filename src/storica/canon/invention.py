"""
What prose may invent, and what it may not — one rule, read by the writer and its readers alike.

This exists because the rule used to be stated twice and the two statements disagreed. The writer
was told to "invent texture freely, invent facts never" and was never told where texture ends; the
micro-sense reader was told that *any* concrete detail without a canon basis — a date, a distance, a
procedure — is a hallucination. P6's first chapter died on that gap: a scene said *"Am elften
März"*, the reader called the date an invention, and three fresh readings later the chapter was
quarantined for a detail no later chapter depended on (`calibration/FINDINGS.md` C7).

Fiction is made of specifics nobody planned. A pipeline that forbids them pushes every scene toward
the vague, correct, lifeless middle that the vitality reader then has to fight. So the line is drawn
where the danger actually is — at identity, relationships, knowledge and the story's open questions
— and everything on the near side of it is the writer's to imagine. What the prose invents there is
not lost or left floating: reconcile extracts it into canon after the chapter passes, and every
later chapter is held to it (DESIGN §7, the up-leg).
"""

from ..agents import shared

# The text lives in agents/_shared/invention-policy.md, where the writer and micro-sense both include it.
INVENTION_POLICY = shared("invention-policy")
