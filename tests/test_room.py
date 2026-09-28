"""The writers' room: documents the creator steers with, and one step developed in rounds."""

import asyncio
import json
from pathlib import Path

import pytest
import yaml

from storica import room
from storica.agents import system
from storica.authors import load_author
from storica.brief import Brief
from storica.cli import main
from storica.llm import FakeStructuredLLM
from storica.room.document import Document, parse
from storica.room.steps import Assessment, EditorReview

AUTHORS_ROOT = Path(__file__).resolve().parents[1] / "authors"
BRIEF = Brief(author_id="duerrenmatt", spark="Ein Arzt, ein Toter, ein verschneiter Pass.", language="de")

OPTIONS = "## Option A: Der Totenschein\n**Logline:** ...\n\n## Option B: Der Pass\n\n## Option C: Die Witwe"
REVISED = "# Der Totenschein\n**Logline:** Ein junger Arzt ..."


def _review(*questions):
    return EditorReview(
        summary="Drei Richtungen liegen auf dem Tisch.",
        assessments=[Assessment(label="Option A", strengths="klar", risks="dünn")],
        recommendation="A, mit dem Dorf aus C.",
        questions=list(questions),
    )


def _advance(novel, llm):
    author = load_author("duerrenmatt", AUTHORS_ROOT)
    return asyncio.run(room.advance(novel_dir=novel, step_id="pitch", brief=BRIEF, author=author, llm=llm))


def test_a_document_round_trips_through_render_and_parse():
    doc = Document(step="pitch", language="de", status="open", version=2, content=OPTIONS,
                   editor="## Lektorat\n\nGut.", decisions=["v1 → v2: B, aber jünger"], notes="- mehr Schnee")
    back = parse(doc.render(), "de")
    assert (back.content, back.editor, back.decisions, back.notes, back.version) == (
        OPTIONS, "## Lektorat\n\nGut.", ["v1 → v2: B, aber jünger"], "- mehr Schnee", 2)
    assert "## Deine Notizen" in doc.render()


def test_the_first_round_proposes_options_and_the_editor_asks(tmp_path):
    llm = FakeStructuredLLM(texts=[OPTIONS], responses=[_review("Wer steht im Zentrum?")])
    out = _advance(tmp_path, llm)

    assert out.changed and out.doc.version == 1 and out.doc.status == "open"
    writer, editor = llm.calls
    assert writer.system == system("pitch_writer") and "three genuinely different" in writer.prompt
    assert editor.system == system("story_editor") and OPTIONS in editor.prompt
    text = (tmp_path / "01_pitch.md").read_text(encoding="utf-8")
    assert "Option B" in text and "### Fragen an dich" in text and "1. Wer steht im Zentrum?" in text
    assert list((tmp_path / "_trace").glob("*pitch_options.json"))


def test_without_new_notes_nothing_happens(tmp_path):
    _advance(tmp_path, FakeStructuredLLM(texts=[OPTIONS], responses=[_review()]))
    llm = FakeStructuredLLM()
    out = _advance(tmp_path, llm)
    assert not out.changed and "waiting" in out.message and llm.calls == []


def test_notes_drive_a_revision_and_become_decisions(tmp_path):
    _advance(tmp_path, FakeStructuredLLM(texts=[OPTIONS], responses=[_review()]))
    room.add_note(tmp_path, "pitch", "de", "A, aber der Arzt ist jünger")

    llm = FakeStructuredLLM(texts=[REVISED], responses=[_review()])
    out = _advance(tmp_path, llm)

    prompt = llm.calls[0].prompt
    assert "- A, aber der Arzt ist jünger" in prompt and OPTIONS in prompt and "Revise the pitch" in prompt
    assert out.doc.version == 2 and out.doc.content == REVISED and out.doc.notes == ""
    assert out.doc.decisions == ["v1 → v2: - A, aber der Arzt ist jünger"]
    assert "Option B" in (tmp_path / "_history" / "01_pitch.v1.md").read_text(encoding="utf-8")


def test_hand_edits_to_the_document_reach_the_writer(tmp_path):
    _advance(tmp_path, FakeStructuredLLM(texts=[OPTIONS], responses=[_review()]))
    path = tmp_path / "01_pitch.md"
    text = path.read_text(encoding="utf-8").replace("Der Pass", "Der Lawinenwinter")
    path.write_text(text + "Bitte nur noch Option B.\n", encoding="utf-8")

    llm = FakeStructuredLLM(texts=[REVISED], responses=[_review()])
    _advance(tmp_path, llm)
    assert "Der Lawinenwinter" in llm.calls[0].prompt and "Bitte nur noch Option B." in llm.calls[0].prompt


def test_approval_waits_for_notes_and_a_note_reopens(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        room.approve(tmp_path, "pitch", "de")
    _advance(tmp_path, FakeStructuredLLM(texts=[OPTIONS], responses=[_review()]))
    room.add_note(tmp_path, "pitch", "de", "B")
    with pytest.raises(ValueError, match="not worked in"):
        room.approve(tmp_path, "pitch", "de")
    _advance(tmp_path, FakeStructuredLLM(texts=[REVISED], responses=[_review()]))
    assert room.approve(tmp_path, "pitch", "de").approved
    assert room.add_note(tmp_path, "pitch", "de", "doch noch etwas").status == "open"


def test_develop_pauses_for_each_call_and_resumes_under_the_replay_driver(tmp_path, capsys):
    novel = tmp_path / "book"
    (novel / "00_input").mkdir(parents=True)
    (novel / "00_input" / "brief.yaml").write_text(yaml.safe_dump(BRIEF.model_dump(), allow_unicode=True), encoding="utf-8")
    argv = ["develop", str(novel), "pitch", "--authors", str(AUTHORS_ROOT)]

    def answer(suffix, text):
        answered = {p.name.split(".")[0] for p in (novel / "_session" / "responses").glob("*.response.*")}
        pending = [p for p in (novel / "_session" / "requests").glob("*.request.md") if p.name.split(".")[0] not in answered]
        assert len(pending) == 1
        (novel / "_session" / "responses").mkdir(exist_ok=True)
        (novel / "_session" / "responses" / pending[0].name.replace(".request.md", suffix)).write_text(text, encoding="utf-8")

    assert main(argv) == 2
    answer(".response.md", OPTIONS)
    assert main(argv) == 2
    answer(".response.json", _review("Wer?").model_dump_json())
    assert main(argv) == 0
    assert "v1 ready: 1 question(s)" in capsys.readouterr().out

    assert main(["develop", str(novel)]) == 0
    assert "1. Pitch: v1, open (01_pitch.md)" in capsys.readouterr().out
    assert main(argv + ["--approve"]) == 0
    assert main(["develop", str(novel), "nonsense"]) == 1
    assert json.loads(next((novel / "_trace").glob("*pitch_review_v1.json")).read_text())["note"] == "A, mit dem Dorf aus C."
