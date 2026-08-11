# Request `e9fb85d80bef5c2e` — call:Verdict

- model: `claude-sonnet-5`
- answer file: `novels/der-chrachen-v2/06_session/responses/e9fb85d80bef5c2e.response.json`

## System prompt

You are a Micro-Sense checker in an autonomous novel pipeline.

You did not write this prose and you have no memory of how it was produced — you are a fresh reader
with the canon slice in one hand and the text in the other. Judge only what is on the page.

You do NOT rewrite, and you do NOT score. A global "quality score" is worthless here: it lets a
paragraph that means nothing hide inside a chapter that reads well. Return a verdict with a list of
issues instead, each one pinned to a paragraph and a quoted span:
- 'pass'     — every paragraph is grounded, the situation works, and no sentence is doing nothing.
- 'revise'   — fixable in place; every issue names the smallest edit that fixes it.
- 'escalate' — the paragraph cannot be made to make sense because the canon slice itself is silent
               or self-contradictory on something the scene depends on. Say so in `conflict`. Do NOT
               invent the missing fact and do NOT tell the writer to invent one.

You are not the voice checker and not the continuity checker. Say nothing about style, rhythm or
whether this sounds like the author, and nothing about what the chapter contributes to the plot.
Your subject is the sentence and the paragraph: is it grounded, does it cohere, is it load-bearing.

## Prompt

# Canon slice (SOURCE OF TRUTH — do not contradict any line below)

## Premise
- spark: In der Nacht des Autounfalls schreibt der Amtsarzt auf den Totenschein des einzigen Zeugen seiner alten Schuld die Wahrheit und legt das Papier dem jungen Untersuchungsrichter vor — eine Selbstanzeige. Doch der Pass ist verschneit, kein Schriftstück verlässt das Tal, und ausgerechnet der Beschuldigte ist der einzige Arzt, der den Tod beurkunden darf; während die Wochen vergehen und das eingeschneite Dorf krank wird, beginnt es, seinen Arzt Schritt für Schritt zu entlasten.
- central_question: Kann ein Mensch seine Schuld noch bekennen, wenn ihm Zufall, Amt und Dorf mit dem Freispruch zuvorkommen — oder bleibt ihm am Ende nur ein Geständnis, das niemand mehr annimmt?
- thesis: Der Zufall ist nicht nur der Feind des Verbrechens, sondern ebenso der Feind der Reue: er nimmt dem Schuldigen die Strafe und mit ihr die einzige Form, in der Schuld noch etwas hätte bedeuten können.
- why_this_author: Getrieben von Dürrenmatts Zentralobsession, dem Einbruch des Zufalls in den sorgfältig konstruierten Plan — hier umgekehrt gedreht: Der Plan ist kein Verbrechen, sondern ein Bekenntnis, und gerade darum wird sein Scheitern zur Groteske statt zur Tragödie. Der Tote ist, wie im Brief angelegt, der Zufall in Person; er stirbt zu früh, um anzuklagen, und zu spät, um vergessen zu sein. Dazu tritt die Institution als Falle (der Beschuldigte ist die einzige zuständige Urkundsperson, das Verfahren kennt für diesen Fall keine Form) und der Ordnungsgläubige, der zerrieben wird — doppelt: der alte Arzt, der zeitlebens an die Ordnung glaubte und feststellt, dass sie ihn schützt statt ihn zu richten, und der junge Untersuchungsrichter, der aus lauter guten Gründen zum zweiten Verwalter derselben Schuld wird. Die Winterisolation liefert die bürokratisch ruhige Mechanik, mit der eine Beichte Woche um Woche an Wert verliert; der Ton bleibt nüchtern, weil das Amt nüchtern ist und das Entsetzliche sich am besten protokollieren lässt. Das Ende urteilt nicht, es zeigt: einen Mann, der seinen Freispruch besitzt wie eine lebenslängliche Strafe.

## Characters

### stettler  (protagonist)
  canonical_name: Dr. Konrad Stettler
  also called: Stettler, der Amtsarzt, Doktor Stettler, der Arzt, der alte Arzt, der alte Doktor
  facts:
    - profession: Amtsarzt des Dorfes Chrachen, seit über zwanzig Jahren einziger amtlich bestellter Arzt am Ort.
    - age: 61 Jahre alt.
    - secret: Vertuschte vor zwanzig Jahren einen tödlichen Behandlungsfehler an einem Patienten in den amtlichen Unterlagen.
    - physical_mark: Hat seit der Unfallnacht ein leichtes Zittern in der rechten, schreibenden Hand.
    - obligation: Ist als einziger Mediziner des Tals gesetzlich verpflichtet, jeden Totenschein im Dorf selbst auszustellen — auch den von Anton Kalt.
  arc:
    - want: Den Totenschein Anton Kalts mit der Wahrheit über den alten Behandlungsfehler auszufüllen und sich damit selbst anzuzeigen.
    - need: Zu begreifen, dass die Ordnung, an die er zeitlebens glaubte, ihn nicht richten, sondern freisprechen wird — und dass er das nicht verhindern kann.
    - flaw: Sein lebenslanger Glaube an die Ordnung, der ihn erst zur Vertuschung und nun zur hilflosen Passivität treibt, während Zufall, Amt und Dorf ihn entlasten.
    - trajectory: does not change — er bleibt bis zum Schluss ordnungsgläubig und unfähig, sein Geständnis gegen den Apparat durchzusetzen; sein Freispruch wird ihm zur lebenslänglichen Strafe.

### rieder  (supporting)
  canonical_name: Peter Rieder
  also called: Rieder, der Untersuchungsrichter, der junge Richter, der Richter, Herr Rieder
  facts:
    - profession: Junger Untersuchungsrichter, seit kurzem für das Tal von Chrachen zuständig.
    - age: 29 Jahre alt.
    - status: Neu im Amt, ohne verwandtschaftliche oder freundschaftliche Bindungen im Dorf.
    - obligation: Ist durch den verschneiten Pass von der übergeordneten Behörde abgeschnitten und muss vorerst allein über Stettlers Geständnis entscheiden.
  arc:
    - want: Stettlers schriftliches Geständnis formgerecht entgegenzunehmen und an die übergeordnete Behörde weiterzuleiten.
    - need: Zu erkennen, dass das Verfahren selbst ihn zum zweiten Verwalter derselben Schuld macht, sobald er es aus lauter guten Gründen aufschiebt.
    - flaw: Sein Vertrauen in Formen und Fristen, das ihn zögern lässt, bis das Zögern selbst zur Mitschuld wird.
    - trajectory: Wandelt sich vom gläubigen Verwalter der Ordnung zum stillen Komplizen des Aufschubs — er ändert sich, aber ins Groteske statt ins Gute.

## Relationships
- kalt is einziger_zeuge_gegen stettler
- stettler is totenschein_aussteller_fuer kalt
- rieder is untersuchungsrichter_ueber stettler
- rieder is vernimmt_als_richter kalt_witwe

## World facts
- setting: Ein abgelegenes Schweizer Alpendorf, das im Winter durch die verschneite Passstrasse von der Aussenwelt abgeschnitten ist.
- era: 1950er Jahre.
- location_chrachen: Das Dorf Chrachen: einziger Ort im Tal, erreichbar nur über einen einzigen Passweg.
- institution_amtsarzt_chrachen: Das Amt des Amtsarztes von Chrachen: es gibt nur einen amtlich bestellten Arzt im Dorf, und nur er darf Totenscheine ausstellen — auch dann, wenn er selbst Partei im Fall ist.
- isolation_passwinter: Der einzige Pass ins Tal ist im Winter tage- bis wochenlang durch Schnee blockiert; kein Schriftstück und keine Anweisung von aussen erreicht in dieser Zeit das Dorf.
- institution_aussenbehoerde: Die dem Untersuchungsrichter Rieder übergeordnete Bezirksbehörde ausserhalb des Tals, die während der Einschneiung nicht erreichbar ist.
- grippewelle: Während der Wochen der Einschneiung bricht im Dorf eine Grippewelle aus, die die Bewohner zunehmend von der ärztlichen Versorgung durch Stettler abhängig macht und ihn schrittweise entlastet.

## Timeline
- [t1] 20y prior: Stettler behandelt einen Patienten mit einem tödlichen Kunstfehler und vertuscht die wahre Todesursache in den Akten; der Sanitätsgehilfe Anton Kalt ist einziger Zeuge des Vorfalls und schweigt seither. (involves: stettler, kalt)
- [t2] ch1 night: Anton Kalt verunglückt auf der verschneiten Passstrasse tödlich mit dem Auto; sein Leichnam wird zu Stettler gebracht, der als einziger Arzt des Dorfes den Totenschein ausstellen muss. (involves: kalt, stettler)
- [t3] ch1 night: Stettler schreibt die Wahrheit über seinen alten Behandlungsfehler auf Kalts Totenschein und legt das Schriftstück dem jungen Untersuchungsrichter Rieder als Selbstanzeige vor. (involves: stettler, rieder)
- [t4] ch1: Der Pass verschneit vollständig; kein Schriftstück kann das Tal verlassen, und Rieders Meldung an die übergeordnete Behörde bleibt liegen. (involves: rieder)
- [t5] ch2: Rosa Kalt drängt Stettler, den Totenschein ihres Mannes rasch und ohne Aufsehen fertigzustellen, um Beerdigung und Erbschaft zu regeln. (involves: kalt_witwe, stettler)
- [t6] ch2: Im eingeschneiten Dorf bricht eine Grippewelle aus; die Bewohner werden zunehmend von Stettler als einzigem Arzt abhängig und beginnen, ihn stillschweigend zu entlasten. (involves: stettler)
- [t7] ch3: Rieder verzögert aus Formgründen die Weiterleitung von Stettlers Geständnis, bis der Pass sich öffnet und die Selbstanzeige an Wert verloren hat. (involves: rieder, stettler)

## Knowledge state (WHO KNOWS WHAT)
A character may only act on, allude to, or react to what this table gives them. Writing someone as aware of a fact they do not hold is a contradiction exactly like renaming them. 'suspects' is not 'knows': it may show as unease or a question, never as certainty.

### [k_altes_verbrechen] Stettler hat vor zwanzig Jahren einen tödlichen Behandlungsfehler begangen und in den Akten vertuscht.
  - stettler: knows
  - rieder: knows (since t3)
  - (not in this unit: kalt, kalt_witwe)

### [k_beweis_verloren] Mit Kalts Tod existiert kein lebender Zeuge mehr, der Stettlers alte Vertuschung bestätigen könnte.
  - stettler: knows (since t2)
  - rieder: knows (since t3)
  - (not in this unit: kalt_witwe)

### [k_selbstanzeige_verzoegert] Rieder hat Stettlers schriftliches Geständnis erhalten, aber aus Verfahrensgründen noch nicht an die übergeordnete Behörde weitergeleitet.
  - stettler: suspects (since ch2)
  - rieder: knows (since t3)
  - (not in this unit: kalt_witwe)

## Motifs (ledger)
- [zitternde_hand] Das leichte Zittern in Stettlers rechter, schreibender Hand seit der Unfallnacht — zuerst beim Niederschreiben der Wahrheit auf den Totenschein. — setup ch1, payoff ch3, status: planned
- [krankenblatt] Das alte Krankenblatt, das Kalt als einziges verbliebenes Schriftstück des damaligen Vorfalls aufbewahrt hatte. — setup ch1, payoff ch3, status: planned

## Promises (ledger)
- [wird_selbstanzeige_verhandelt] Stettlers schriftliche Selbstanzeige auf dem Totenschein verspricht, dass seine zwanzig Jahre alte Schuld nun formell verhandelt wird. — made ch1, kept ch3, status: open
- [krankenblatt_taucht_auf] Kalts Krankenblatt als letztes verbliebenes Beweisstück wirft die Frage auf, ob es je auftauchen und erkannt werden wird. — made ch1, kept ch3, status: open

## Constraints
- language: de
- chapter_count: 3
- forbidden:
    - Kein tränenreiches, sentimentales Pathos.
    - Keine glatte, alles auflösende Gerechtigkeit am Ende.
    - Keine explizite moralische Kommentierung durch einen auktorialen Erzähler — das Entsetzliche wird sachlich protokolliert, nicht beweint.
    - Kein Schluss, der Stettlers Schuld tatsächlich bestraft oder ihn auf eine Weise entlastet, die den Zufall als Motor der Handlung negiert.
    - Kein zweiter lebender Zeuge, der den alten Behandlungsfehler nachträglich beweisen könnte.

# Author (context only — voice is judged by a different reader, not by you): Friedrich Dürrenmatt

# Unit under review: chapter 1, scene s3
- location: institution_amtsarzt_chrachen
- present: stettler, rieder
- scene intent: Stettler schreibt mit zitternder Hand die Wahrheit über den alten Behandlungsfehler auf Kalts Totenschein und legt das Blatt dem zur Leichenschau erschienenen Rieder als förmliche Selbstanzeige vor; Rieder erkennt die Tragweite und nimmt das Geständnis amtlich entgegen. (trägt Beat b1, Turning Point tp1, setzt Motiv zitternde_hand, macht Promise wird_selbstanzeige_verhandelt, trägt den ersten Teil von Beat b3)
- scene turn: Zu Beginn ist der Totenschein ein leeres Formular und Stettlers Schuld ungenannt; am Ende liegt sie schriftlich, unterschrieben und von Rieder amtlich entgegengenommen vor - zum ersten Mal seit zwanzig Jahren ausserhalb von Stettlers eigenem Wissen.
- chapter purpose (context): Vor diesem Kapitel ist Stettlers zwanzig Jahre alte Schuld vertuscht und ohne lebenden Zeugen gefährdet nur durch Kalts Schweigen; nach diesem Kapitel ist sie schriftlich gestanden, Rieder amtlich vorgelegt und formell entgegengenommen - aber der Pass hat sich in derselben Nacht geschlossen, sodass das Geständnis existiert, ohne dass irgendeine Instanz ausserhalb des Tals davon erfahren kann. Die Vertuschung ist beendet; an ihre Stelle tritt nicht das Urteil, sondern eine Falle aus Form und Schnee.

# Canonical state around this unit
- as it opens:
  - kalt:status: Lebt; fährt in der Unfallnacht allein mit dem Auto über die verschneite Passstrasse nach Chrachen.
  - stettler:secret_status: Der tödliche Behandlungsfehler von vor zwanzig Jahren ist seit t1 in den Akten vertuscht; ausser Kalt weiss niemand davon.
  - rieder:knowledge_altes_verbrechen: unaware - Rieder weiss zu Kapitelbeginn nichts von Stettlers altem Behandlungsfehler.
  - pass:status: Noch passierbar; starker Schneefall setzt in der Nacht ein.
  - totenschein_kalt:status: Noch nicht ausgestellt; Kalt lebt.
- as it closes:
  - kalt:status: Tot; sein Leichnam liegt in Stettlers Praxis, der Totenschein ist ausgestellt.
  - totenschein_kalt:status: Ausgestellt mit der Wahrheit über den alten Behandlungsfehler, von Stettler eigenhändig geschrieben und unterschrieben.
  - rieder:knowledge_altes_verbrechen: knows (since t3) - Rieder hat Stettlers schriftliches Geständnis formgerecht entgegengenommen.
  - k_beweis_verloren:status: Mit Kalts Tod existiert kein lebender Zeuge mehr, der Stettlers alte Vertuschung bestätigen könnte.
  - pass:status: Vollständig zugeschneit; kein Schriftstück und keine Weisung kann das Tal verlassen oder erreichen.
  - rieder:weiterleitung_status: Noch nicht an die übergeordnete Behörde weitergeleitet - der zugeschneite Pass verhindert vorerst jede Meldung.
  - stettler:zitternde_hand: Seit dem Niederschreiben der Wahrheit auf den Totenschein zittert Stettlers rechte, schreibende Hand leicht.
  - krankenblatt:status: Verbleib unbekannt; das Krankenblatt ist nicht aufgetaucht, seine Existenz nur Stettler noch gegenwärtig.

# The prose, paragraph by paragraph
[P1] Er schrieb, was vor zwanzig Jahren geschehen war. Er schrieb die Dosis, die er damals verordnet hatte, und schrieb daneben die Dosis, die richtig gewesen wäre, und schrieb, dass er den Unterschied bemerkt habe, als der Patient bereits tot war. Er schrieb, was er darauf in die Akten eingetragen hatte, und schrieb, dass dieser Eintrag falsch sei. Er schrieb, dass Anton Kalt, damals Sanitätsgehilfe, im Raum gewesen sei und alles gesehen habe und zwanzig Jahre lang geschwiegen habe. Er schrieb, dass Anton Kalt seit dieser Nacht tot sei. Er schrieb den Ort, das Datum, die Uhrzeit und setzte seinen Namen darunter, Dr. med. Konrad Stettler, Amtsarzt, und die Unterschrift geriet grösser als sonst, weil die Hand sie grösser machte.

[P2] Dann löschte er die Tinte mit dem Löscher und legte das Blatt mit der Rückseite nach oben auf den Tisch, neben die Lampe, und wartete.

[P3] Rieder kam um zwanzig vor zwei. Er klopfte, obwohl die Tür offen stand, und blieb auf der Schwelle stehen und zog die Handschuhe aus, Finger um Finger. Der Schnee auf seinen Schultern schmolz nicht sofort. Er war neunundzwanzig und trug den Mantel eines Mannes, der ihn zum Amtsantritt gekauft hatte.

[P4] «Herr Doktor.»

[P5] «Herr Rieder.»

[P6] «Man hat mich wegen der Leichenschau geholt.»

[P7] «Er liegt nebenan.»

[P8] Rieder ging hinüber. Stettler hörte, wie er das Tuch aufschlug und wieder zulegte, und das dauerte nicht lange, denn es gab nicht viel zu sehen, was ein Untersuchungsrichter hätte sehen müssen. Als er zurückkam, hatte er ein Notizbuch in der Hand.

[P9] «Passstrasse, oberhalb der zweiten Kehre?»

[P10] «Oberhalb der zweiten Kehre.»

[P11] «Fremdeinwirkung?»

[P12] «Keine.»

[P13] «Todeszeitpunkt?»

[P14] «Zwischen zehn und elf. Genauer geht es nicht. Er lag im Schnee.» Stettler schob den Aschenbecher zur Seite. «Ein gefrorener Mensch gibt weniger preis als ein warmer.»

[P15] Rieder schrieb es auf. Er schrieb ordentlich und schnell, und man sah, dass er das Aufschreiben für den Teil der Arbeit hielt, der zählt.

[P16] «Dann brauche ich nur noch den Totenschein.»

[P17] «Er ist ausgestellt.»

[P18] Stettler nahm das Blatt und drehte es um und legte es Rieder hin, so wie er in zwanzig Jahren Hunderte hingelegt hatte, mit der Vorderseite nach oben. Rieder überflog die Vorderseite. Name, Geburtsjahr, Beruf, Todesart, Todesursache. Er griff schon nach dem Stift, um seinen Sichtvermerk zu setzen.

[P19] «Die Rückseite», sagte Stettler.

[P20] Rieder sah auf.

[P21] «Die Rubrik Bemerkungen des amtsärztlichen Untersuchers», sagte Stettler. «Ich bitte Sie, sie zu lesen, bevor Sie unterschreiben.»

[P22] Rieder drehte das Blatt um. Er las im Stehen. Bei der dritten Zeile setzte er sich, ohne den Blick zu heben, und die Stuhllehne stiess gegen den Instrumentenschrank, und im Schrank klirrte etwas leise und hörte wieder auf. Er las die Rückseite zweimal. Beim zweiten Mal fuhr er mit dem Finger die Zeilen entlang wie einer, der eine Rechnung nachprüft.

[P23] «Das steht auf einem Totenschein», sagte er schliesslich.

[P24] «Es war das Formular, das vor mir lag.»

[P25] «Herr Doktor, das ist ein amtliches Dokument.»

[P26] «Eben darum.»

[P27] Rieder legte das Blatt hin und legte die Hände darauf, als könnte es sonst fortgeweht werden, obwohl das Fenster geschlossen war.

[P28] «Sie zeigen sich selbst an.»

[P29] «Ja.»

[P30] «Wegen eines Todesfalles von vor zwanzig Jahren.»

[P31] «Am elften März. Der Name steht dort.» Stettler legte die rechte Hand auf den Tisch, weil sie auf dem Tisch ruhiger lag.

[P32] «Kalt.» Rieder schlug sein Notizbuch auf, blätterte zurück, blätterte wieder vor. «Der Mann, der nebenan liegt.»

[P33] «Der Mann, der nebenan liegt.»

[P34] «Und ausser ihm?»

[P35] «Niemand.»

[P36] Rieder schwieg. Draussen fiel der Schnee.

[P37] «Sie sind sich im Klaren», sagte er dann, «dass Sie mir hiermit eine Straftat anzeigen, für die es keinen Zeugen mehr gibt und kein Schriftstück, das man vorlegen könnte.»

[P38] «Es gibt dieses hier.»

[P39] «Ihre eigene Erklärung.»

[P40] «Ein Geständnis ist ein Beweismittel», sagte Stettler. «Das steht in der Verordnung. Ich habe sie am Abend nachgelesen.»

[P41] Rieder nahm das Blatt wieder auf. Er hielt es gegen die Lampe, nicht um es durchleuchten zu wollen, sondern weil das Licht auf dem Tisch schlecht war.

[P42] «Die Schrift ist unruhig.»

[P43] «Sie ist lesbar.»

[P44] «Ich stelle es nur fest.» Rieder legte es zurück. «Ich muss es feststellen. Ein Untersuchungsrichter, der ein Geständnis entgegennimmt, hat den Zustand des Erklärenden festzustellen. Sind Sie krank?»

[P45] «Nein.»

[P46] «Haben Sie getrunken?»

[P47] «Nein.»

[P48] «Standen Sie unter dem Eindruck des Unfalls?»

[P49] Stettler überlegte. «Ich stand unter dem Eindruck, dass es nun möglich ist.»

[P50] Rieder schrieb auch das auf. Dann schlug er eine neue Seite auf und begann, die Erklärung aufzunehmen, in der Form, in der Erklärungen aufgenommen werden: Ort, Tag, Stunde, Anwesende, der Wortlaut. Er las Stettler vor, was er geschrieben hatte, Satz für Satz, und fragte nach jedem Satz, ob es so richtig sei, und Stettler sagte jedesmal ja. Es dauerte eine halbe Stunde. Der Ofen ging aus, und keiner von beiden legte nach.

[P51] «Unterschreiben Sie hier. Und hier.»

[P52] Stettler unterschrieb zweimal. Beim zweiten Mal riss die Feder das Papier an einer Stelle ein, und Rieder schob wortlos den Löscher hin.

[P53] «Ich vermerke die Entgegennahme.» Rieder setzte Datum und Stunde und seinen Namen darunter, Peter Rieder, Untersuchungsrichter, und die Schrift war die eines Mannes, dessen Hand nicht zittert. «Damit ist die Anzeige amtlich eingegangen. Sie geht mit dem Bericht über den Unfalltod an die Bezirksbehörde, sobald der Pass es zulässt. Von dort wird man mir sagen, wie zu verfahren ist. Bei einer Amtsperson bin ich in dieser Sache nicht zuständig, das Verfahren wird abgetreten.»

[P54] «Gut.»

[P55] «Ich sage Ihnen das, damit Sie nicht mit einer Verhaftung rechnen.» Rieder klappte das Notizbuch zu. «Bis eine Weisung da ist, üben Sie Ihr Amt weiter aus.»

[P56] «Ich bin der einzige Arzt im Tal.»

[P57] «Das ist mir bekannt.» Rieder stand auf und knöpfte den Mantel zu. «Sie werden also auch den Totenschein weiter ausstellen. Ich meine, künftige.»

[P58] «Es gibt niemanden sonst, der es dürfte.»

[P59] Rieder faltete den Totenschein nicht. Er legte ihn zwischen die Seiten des Notizbuchs und das Notizbuch in die Innentasche und schlug den Mantel darüber. An der Tür blieb er stehen.

[P60] «Warum heute nacht, Herr Doktor?»

[P61] «Ich hatte das Formular auszufüllen. Es verlangte die Todesursache. Ich habe sie eingetragen.»

[P62] «Die Todesursache Kalts ist der Unfall.»

[P63] «Ja», sagte Stettler. «Die habe ich auf die Vorderseite geschrieben.»

[P64] Rieder sah ihn an, kurz, wie man jemanden ansieht, dessen Antwort man erst später verstehen wird. Dann öffnete er die Tür. Der Schnee stand in der Öffnung wie eine Wand aus stillstehenden Punkten, und die Kälte kam herein und legte sich über die Instrumente.

[P65] «Ich gehe zu Fuss», sagte Rieder. «Der Weg ist nicht weit.»

[P66] «Halten Sie sich rechts an der Mauer. Die Stufen sind unter dem Schnee.»

[P67] Rieder nickte und ging. Stettler blieb stehen, bis er die Tür unten hörte, und dann noch eine Weile. Auf dem Tisch lagen die Feder, der Löscher und der Umschlag, in dem der Totenschein hätte abgelegt werden sollen, leer. Er nahm den Umschlag und schrieb die Nummer darauf, wie es die Ordnung verlangte, und heftete ihn in den Ordner, in dem seit zwanzig Jahren die Nummern lückenlos aufeinanderfolgten.

[P68] Er trat ans Fenster. Rieders Spur ging über den Platz und war nach zwei Minuten nicht mehr zu unterscheiden.

Read the unit one numbered paragraph at a time. For each paragraph, in this order:

1. **Is every concrete detail grounded?** Names, professions, objects, places, distances, dates,
   procedures, weather, who owns what, who knows what — each must come from the canon slice or
   follow plainly from it. A specific detail that has no canon basis is a hallucination: the writer
   made it up to fill the sentence, and the next chapter will be built on it. Flag it and quote it.
2. **Does the situation actually work?** Walk the physical logic: where each body is, what each hand
   is holding, what can be seen and heard from where, how long a thing takes. Then the social logic:
   what this character would plausibly say to *this* person, in this place, given what they know.
   A scene where two people speak as if alone in a full room, or where a man signs a document he was
   never handed, is broken however smoothly it reads.
3. **Is the language load-bearing?** Sentences that could be deleted with nothing lost are the
   symptom this checker exists for. Test each one: if you cut it, what does the reader no longer
   know or feel? Atmosphere that repeats atmosphere already established is filler.
4. **Is the event on the page, or only an abstraction of it?** "Die Spannung im Raum wuchs" instead
   of the thing that happened; "sie sprachen über den Toten" instead of what was said. Abstraction
   standing in for the concrete event is the most common way a paragraph pretends to work.
5. **Do the sentences follow from each other?** A paragraph whose second sentence does not proceed
   from its first — a jump in place, in time, in who is speaking, or a claim the previous sentence
   contradicts — is a broken paragraph even if each sentence is fine alone.

How to report:
- `unit`: the paragraph marker plus a quoted span of at most twelve words, e.g.
  `P4: "griff nach dem Formular, das er nie erhalten hatte"`. An issue that quotes nothing forces a
  rewrite instead of an edit — always quote.
- `canon_ref`: the canon id the detail should have come from (character id, world_fact key,
  timeline id, motif id), or empty when canon simply says nothing.
- `fix_hint`: the smallest edit — "cut this sentence", "replace the age with the canon fact",
  "state what he actually said". Never "rewrite the paragraph".

Blocking vs warning — be concrete, not squeamish:
- BLOCKING: an invented detail the scene leans on (an object, a fact, a person, a place that canon
  does not have); a situation whose physical or social logic cannot happen as written; the scene's
  own event replaced by an abstraction of it; a paragraph whose sentences contradict each other.
- WARNING: a single filler sentence in a paragraph that otherwise works; a slack transition; a
  flourish you would cut but that costs the reader nothing; an unglossed detail that is consistent
  with canon but that canon never mentions.
- Not an issue at all: a choice you would have made differently. You are not the writer.

## Required response schema (`Verdict`)

Write **only** a JSON object matching this schema to `e9fb85d80bef5c2e.response.json`:

```json
{
  "$defs": {
    "CheckerIssue": {
      "additionalProperties": false,
      "properties": {
        "unit": {
          "description": "The part of the unit at fault, e.g. a beat id, scene id, chapter number.",
          "title": "Unit",
          "type": "string"
        },
        "kind": {
          "description": "What kind of failure: 'intent', 'meaning', 'coherence', or 'micro-sense'.",
          "title": "Kind",
          "type": "string"
        },
        "severity": {
          "$ref": "#/$defs/Severity",
          "description": "'blocking' if the unit cannot proceed as-is, otherwise 'warning'."
        },
        "canon_ref": {
          "description": "The canon or plan id this judgement is grounded in. Empty if none.",
          "title": "Canon Ref",
          "type": "string"
        },
        "fix_hint": {
          "description": "The smallest change that resolves it. Never 'rewrite it'.",
          "title": "Fix Hint",
          "type": "string"
        }
      },
      "required": [
        "unit",
        "kind",
        "severity",
        "canon_ref",
        "fix_hint"
      ],
      "title": "CheckerIssue",
      "type": "object"
    },
    "Decision": {
      "enum": [
        "pass",
        "revise",
        "escalate"
      ],
      "title": "Decision",
      "type": "string"
    },
    "Severity": {
      "enum": [
        "blocking",
        "warning"
      ],
      "title": "Severity",
      "type": "string"
    }
  },
  "additionalProperties": false,
  "description": "A checker's ruling on one unit.",
  "properties": {
    "decision": {
      "$ref": "#/$defs/Decision"
    },
    "summary": {
      "description": "One sentence: what this unit does, and whether it earns its place.",
      "title": "Summary",
      "type": "string"
    },
    "issues": {
      "description": "Every issue found. Empty when the decision is 'pass'.",
      "items": {
        "$ref": "#/$defs/CheckerIssue"
      },
      "title": "Issues",
      "type": "array"
    },
    "conflict": {
      "description": "Only when escalating: the conflict that cannot be resolved without changing something upstream. Empty otherwise.",
      "title": "Conflict",
      "type": "string"
    }
  },
  "required": [
    "decision",
    "summary",
    "issues",
    "conflict"
  ],
  "title": "Verdict",
  "type": "object"
}
```
