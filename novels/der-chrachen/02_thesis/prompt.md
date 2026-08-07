# FILLED PROMPT — Phase 2: Thesis Development  (model: Sonnet)

> Template: `thesis_development.yaml`. `{topic_exploration}` = the full Phase 1 artifact
> (the app threads `topic.get("raw_exploration")`). `{story_dna}` = `json.dumps(dna, indent=2)`.

## SYSTEM
You are developing the central thesis for a novel in the style of Friedrich Dürrenmatt.

A story thesis is the core argument or insight the story makes about human nature,
society, or existence. It guides every narrative decision.

Consider the author's worldview and how they typically construct meaning in their works.

## USER
## Topic Exploration

[The full Phase 1 Topic Exploration artifact — see `../01_topic_exploration/artifact.md`. Passed verbatim.]

## Story DNA

{
  "spark": { "description": "In einem abgelegenen Schweizer Bergdorf stirbt bei einem Autounfall in einer Winternacht der einzige Mann, der beweisen könnte, dass der Amtsarzt des Dorfes vor zwanzig Jahren einen tödlichen Behandlungsfehler vertuscht hat. Nun liegt der Tote auf dem Tisch eben dieses Arztes, der als einziger Mediziner am Ort den Totenschein ausstellen muss." },
  "genre": { "primary_genre": "Kriminalroman / Tragikomödie (philosophisch)", "subgenres": ["Justizdrama", "Dorfgroteske"] },
  "world": { "setting": "Abgelegenes Schweizer Alpendorf, durch einen Passwinter von der Welt abgeschnitten", "era": "1950er Jahre", "atmosphere": "Eng, verschneit, von Schweigen und stillschweigenden Übereinkünften regiert" },
  "characters": { "protagonist_seed": "Der Amtsarzt: müde, ordnungsgläubig, seit zwanzig Jahren Verwalter seiner eigenen Schuld", "notes": "Der Tote fungiert als Antagonist; eine junge Amtsperson; die Witwe des Toten" },
  "conflict": { "core": "Die Wahrheit auf dem Totenschein wäre die Selbstanzeige des Arztes; das Schweigen überlässt es dem Zufall, die alte Schuld zu begraben." },
  "structure": { "structure_type": "three_act", "chapter_count": 3 },
  "voice": { "language": "de", "tone": "Nüchtern, grotesk, ironisch" }
}

## Your Task

Develop a compelling story thesis that:

1. **Central Thesis**: One sentence that captures what this story argues about the human condition

2. **Antithesis**: The opposing view that will be challenged or complicated

3. **Thematic Questions**: 3-5 questions the story will explore (not answer definitively)

4. **Moral Complexity**: How the story avoids simple moralizing

5. **Resonance with Author**: How this thesis connects to Friedrich Dürrenmatt's body of work

The thesis should be debatable, not a truism. It should create productive tension.
