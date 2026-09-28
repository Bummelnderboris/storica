"""
`storica map`: draw the agents, what each is told and what each reads — and, for a run, what each
one was actually handed.

Output quality is decided by how the agents are organised and instructed, and until now that
organisation was only visible by reading the code. This renders it as one self-contained HTML page:

- the workflow, as phases (the writers' room → plan → per scene → per chapter → the book, plus the
  adjudicator, which can be reached from anywhere), with each agent's model and family;
- per agent, its wiring from the frontmatter of `agents/<id>.md` and the full instructions: the
  system prompt and every named section the code places inside the prompt;
- given a novel, every call from its trace (`04_trace/` for the pipeline, `_trace/` for the room):
  the exact prompt the agent received and what it returned.

A trace record is attributed to an agent by its system prompt first — an exact match means the call
ran under the instructions the file holds today — and otherwise by the stage-name patterns in the
agent's `trace:` list. A call matched only by pattern ran under instructions that have since
changed, and the page says so. Records with no system prompt are bookkeeping (consensus tallies,
assembly, reconcile decisions), not model calls, and are counted separately.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from .agents import Agent, all_agents

PHASES = [
    ("room", "Writers' room", "developed with the creator (storica develop)"),
    ("plan", "Plan", "once per novel, and one chapter ahead"),
    ("scene", "Per scene", "draft, select, gate, repair"),
    ("chapter", "Per chapter", "after the scenes pass"),
    ("book", "The book", "after assembly"),
    ("any", "Any time", "when an escalation reaches it"),
]


def _attribute(records: List[dict], agents: List[Agent]) -> Dict[str, List[dict]]:
    by_system = {a.system: a.id for a in agents}
    patterns = [(a.id, [re.compile(p) for p in a.meta.get("trace", [])]) for a in agents]
    out: Dict[str, List[dict]] = {a.id: [] for a in agents}
    out["_bookkeeping"], out["_unmatched"] = [], []
    for r in records:
        if not r.get("system"):
            out["_bookkeeping"].append(r)
            continue
        aid = by_system.get(r["system"])
        r["current"] = aid is not None
        if aid is None:
            aid = next((i for i, ps in patterns if any(p.search(r.get("stage", "")) for p in ps)), "_unmatched")
        out[aid].append(r)
    return out


#: The autonomous pipeline traces to 04_trace/, the writers' room to _trace/.
TRACE_DIRS = ("04_trace", "_trace")


def has_trace(novel_dir: Path) -> bool:
    return any((novel_dir / d).is_dir() for d in TRACE_DIRS)


def _load_trace(novel_dir: Path) -> List[dict]:
    records = []
    paths = [p for d in TRACE_DIRS for p in sorted((novel_dir / d).glob("*.json"))]
    for path in paths:
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return records


def _call_row(r: dict) -> dict:
    art = r.get("artifact")
    return {
        "seq": r.get("seq"),
        "stage": r.get("stage", ""),
        "model": r.get("model", ""),
        "note": (r.get("note") or "")[:300],
        "current": r.get("current", True),
        "prompt": r.get("prompt") or "",
        "output": art if isinstance(art, str) else json.dumps(art, ensure_ascii=False, indent=2),
    }


def build_map(novel_dir: Optional[Path] = None, agents_root: Optional[Path] = None) -> str:
    agents = all_agents(agents_root)
    calls: Dict[str, List[dict]] = {}
    bookkeeping = unmatched = 0
    if novel_dir is not None:
        grouped = _attribute(_load_trace(novel_dir), agents)
        bookkeeping, unmatched = len(grouped.pop("_bookkeeping")), grouped.pop("_unmatched")
        calls = {aid: [_call_row(r) for r in rs] for aid, rs in grouped.items()}
        if unmatched:
            calls["_unmatched"] = [_call_row(r) for r in unmatched]
        unmatched = len(unmatched)

    data = {
        "novel": novel_dir.name if novel_dir else None,
        "phases": [{"id": p, "title": t, "sub": s} for p, t, s in PHASES],
        "agents": [
            {
                "id": a.id, "name": a.name, "model": a.model, "system": a.system, "blocks": a.blocks,
                "file": f"agents/{a.path.name}", **{k: v for k, v in a.meta.items() if k != "trace"},
            }
            for a in agents
        ],
        "calls": calls,
        "bookkeeping": bookkeeping,
        "unmatched": unmatched,
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    title = f"Agent map · {novel_dir.name}" if novel_dir else "Agent map"
    return _PAGE.replace("__TITLE__", html.escape(title)).replace("__DATA__", payload)


def write_map(out: Path, novel_dir: Optional[Path] = None, agents_root: Optional[Path] = None) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_map(novel_dir, agents_root), encoding="utf-8")
    return out


_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{
  --ground:#F3F5F6; --surface:#FFFFFF; --ink:#17212B; --muted:#586772; --rule:#D5DCE0;
  --accent:#2F5286; --accent-soft:#E2E9F3; --warn:#9A5B00; --warn-soft:#FBF0D9;
  --maker:#2E6B4A; --judge:#2F5286; --extractor:#7A4E8C; --arbiter:#A63A2E;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
}
@media (prefers-color-scheme: dark){
  :root{
    --ground:#10151A; --surface:#171F27; --ink:#E2E7EB; --muted:#95A3AE; --rule:#2B3741;
    --accent:#93B3DD; --accent-soft:#1D2A3A; --warn:#F0B75A; --warn-soft:#33270F;
    --maker:#86C4A0; --judge:#93B3DD; --extractor:#C7A2D6; --arbiter:#E0897E;
    color-scheme:dark;
  }
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font:14px/1.55 var(--sans)}
header{padding:20px 20px 8px;display:flex;flex-wrap:wrap;gap:8px 24px;align-items:baseline}
h1{font-size:20px;margin:0}
h2{font-size:16px;margin:0}
.muted{color:var(--muted)}
.flow{display:grid;grid-template-columns:repeat(6,minmax(160px,1fr));gap:12px;padding:12px 20px 20px;overflow-x:auto}
.phase{display:flex;flex-direction:column;gap:8px;min-width:0}
.phase h3{margin:0;font-size:12px;text-transform:uppercase;letter-spacing:.07em}
.phase small{color:var(--muted);font-size:12px;margin-top:-6px}
.phase.arrow h3::after{content:" →";color:var(--muted)}
.card{all:unset;box-sizing:border-box;cursor:pointer;background:var(--surface);border:1px solid var(--rule);border-left:4px solid var(--fam);padding:8px 10px;display:flex;flex-direction:column;gap:2px}
.card:hover{border-color:var(--accent);border-left-color:var(--fam)}
.card:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.card[aria-pressed="true"]{background:var(--accent-soft)}
.card b{font-size:14px}
.card span{font-size:12px;color:var(--muted)}
.fam-maker{--fam:var(--maker)} .fam-judge{--fam:var(--judge)} .fam-extractor{--fam:var(--extractor)} .fam-arbiter{--fam:var(--arbiter)}
.legend{display:flex;flex-wrap:wrap;gap:14px;padding:0 20px 12px;font-size:12px;color:var(--muted)}
.legend i{display:inline-block;width:10px;height:10px;background:var(--fam);margin-right:5px}
main{padding:0 20px 40px;display:grid;grid-template-columns:minmax(0,1fr);gap:16px}
.panel{background:var(--surface);border:1px solid var(--rule);padding:16px 18px;display:flex;flex-direction:column;gap:14px;min-width:0}
dl{display:grid;grid-template-columns:9rem 1fr;gap:6px 14px;margin:0}
dt{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.05em;padding-top:2px}
dd{margin:0;min-width:0;overflow-wrap:anywhere}
dd ul{margin:0;padding-left:18px}
code{font-family:var(--mono);font-size:12.5px;background:var(--accent-soft);padding:1px 4px}
pre{margin:0;font:12.5px/1.5 var(--mono);white-space:pre-wrap;overflow-wrap:anywhere;background:var(--ground);border:1px solid var(--rule);padding:10px 12px;max-height:520px;overflow:auto}
details{border:1px solid var(--rule)}
details>summary{cursor:pointer;padding:8px 12px;font-weight:600;background:var(--ground)}
details>pre{border:0;border-top:1px solid var(--rule)}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--rule);vertical-align:top}
th{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
tbody tr{cursor:pointer}
tbody tr:hover,tbody tr[aria-selected="true"]{background:var(--accent-soft)}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.old{color:var(--warn);background:var(--warn-soft);font-size:11px;padding:0 5px;white-space:nowrap}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.pair>div{display:flex;flex-direction:column;gap:6px;min-width:0}
@media (max-width:760px){ dl{grid-template-columns:1fr} .pair{grid-template-columns:1fr} }
</style>
</head>
<body>
<header>
  <h1 id="title"></h1>
  <span class="muted" id="summary"></span>
</header>
<div class="legend">
  <span class="fam-maker"><i></i>maker: writes a unit</span>
  <span class="fam-judge"><i></i>judge: returns a verdict, never rewrites</span>
  <span class="fam-extractor"><i></i>extractor: proposes canon</span>
  <span class="fam-arbiter"><i></i>arbiter: binding ruling</span>
</div>
<div class="flow" id="flow"></div>
<main><div class="panel" id="detail"></div><div class="panel" id="call" hidden></div></main>
<script type="application/json" id="data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById("data").textContent);
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const n = id => (D.calls[id] || []).length;

$("#title").textContent = D.novel ? `Agent map · ${D.novel}` : "Agent map";
if (D.novel) {
  const total = Object.values(D.calls).reduce((a, c) => a + c.length, 0);
  $("#summary").textContent = `${total} model calls in the run` +
    (D.bookkeeping ? ` · ${D.bookkeeping} bookkeeping records not shown` : "") +
    (D.unmatched ? ` · ${D.unmatched} calls matched no agent` : "");
} else {
  $("#summary").textContent = `${D.agents.length} agents · run "storica map <novel_dir>" to add a run's calls`;
}

$("#flow").innerHTML = D.phases.map((p, i) => `
  <div class="phase ${i < 4 ? "arrow" : ""}">
    <h3>${esc(p.title)}</h3><small>${esc(p.sub)}</small>
    ${D.agents.filter(a => a.phase === p.id).map(a => `
      <button class="card fam-${esc(a.family)}" data-id="${esc(a.id)}" aria-pressed="false">
        <b>${esc(a.name)}</b>
        <span>${esc(a.model)} · ${esc(a.family)}${D.novel ? ` · ${n(a.id)} calls` : ""}</span>
      </button>`).join("")}
  </div>`).join("");

function list(v) {
  if (!v) return "";
  return Array.isArray(v) ? `<ul>${v.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : esc(v);
}

function showAgent(id) {
  document.querySelectorAll(".card").forEach(c => c.setAttribute("aria-pressed", c.dataset.id === id));
  const a = D.agents.find(x => x.id === id);
  const calls = D.calls[id] || [];
  const blocks = Object.entries(a.blocks || {});
  $("#detail").innerHTML = `
    <h2>${esc(a.name)} <span class="muted">· ${esc(a.step || "")}</span></h2>
    <dl>
      <dt>Model</dt><dd>${esc(a.model)}</dd>
      <dt>Fires</dt><dd>${esc(a.fires)}</dd>
      <dt>Reads</dt><dd>${list(a.reads)}</dd>
      <dt>Writes</dt><dd>${esc(a.writes)}</dd>
      <dt>Authority</dt><dd>${esc(a.authority)}</dd>
      ${a.also_used_as ? `<dt>Also used as</dt><dd>${list(a.also_used_as)}</dd>` : ""}
      <dt>Instructions</dt><dd><code>${esc(a.file)}</code></dd>
      <dt>Input built in</dt><dd>${list(a.input_built_in)}</dd>
    </dl>
    <details open><summary>System prompt</summary><pre>${esc(a.system)}</pre></details>
    ${blocks.map(([k, v]) => `<details><summary>Section in the prompt: ${esc(k)}</summary><pre>${esc(v)}</pre></details>`).join("")}
    ${D.novel ? `<h2>Calls in this run (${calls.length})</h2>` + (calls.length ? `
      <table><thead><tr><th>#</th><th>Stage</th><th>Model</th><th>Result</th><th>Input</th></tr></thead><tbody>
      ${calls.map((c, i) => `<tr data-i="${i}" tabindex="0">
        <td class="num">${esc(c.seq)}</td>
        <td>${esc(c.stage)} ${c.current ? "" : '<span class="old">older instructions</span>'}</td>
        <td>${esc(c.model)}</td><td>${esc(c.note.slice(0, 90))}</td>
        <td class="num">${(c.prompt.length / 1000).toFixed(1)}k chars</td></tr>`).join("")}
      </tbody></table>` : `<p class="muted">Not called in this run.</p>`) : ""}`;
  $("#call").hidden = true;
  $("#detail").querySelectorAll("tbody tr").forEach(tr => {
    const open = () => showCall(id, +tr.dataset.i, tr);
    tr.addEventListener("click", open);
    tr.addEventListener("keydown", e => { if (e.key === "Enter") open(); });
  });
  try { history.replaceState(null, "", "#" + id); } catch (e) {}
}

function showCall(id, i, tr) {
  document.querySelectorAll("tbody tr").forEach(r => r.setAttribute("aria-selected", r === tr));
  const c = D.calls[id][i];
  const box = $("#call");
  box.hidden = false;
  box.innerHTML = `
    <h2>Call ${esc(c.seq)} · ${esc(c.stage)}</h2>
    ${c.current ? "" : '<p class="old">This call ran under instructions that have since changed; its system prompt is not the one in the file today.</p>'}
    ${c.note ? `<p><b>Result:</b> ${esc(c.note)}</p>` : ""}
    <div class="pair">
      <div><b>Input it was given</b><pre>${esc(c.prompt)}</pre></div>
      <div><b>What it returned</b><pre>${esc(c.output)}</pre></div>
    </div>`;
  box.scrollIntoView({behavior: "smooth", block: "start"});
}

document.querySelectorAll(".card").forEach(c => c.addEventListener("click", () => showAgent(c.dataset.id)));
const start = location.hash.slice(1);
showAgent(D.agents.some(a => a.id === start) ? start : (D.agents.find(a => a.id === "prose") || D.agents[0]).id);
</script>
</body>
</html>
"""
