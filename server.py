"""Acadza faculty console backend.
Run from the project root:  uvicorn server:app --reload   ->  http://127.0.0.1:8000

Read-only sources (never modified): data/questions.json, data/reports.json, investigation.json
(set RESULTS_FILE=results.json to serve the final Milestone-2 output instead).
All faculty/student changes live in store/review_state.json, so originals stay untouched and
corrections are overlaid on top of the questions when they are served.
"""
import json, os, threading, time
from pathlib import Path
from typing import Dict, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).parent
DATA = ROOT / "data"
RESULTS_FILE = ROOT / os.getenv("RESULTS_FILE", "investigation.json")
STATE_FILE = ROOT / "store" / "review_state.json"
FRONT = ROOT / "frontend"
FIELDS = {"answer", "solution", "html"}  # the only fields faculty/AI edits may touch
LOCK = threading.Lock()

OK_MSG = ("Sorry for the mistake – you're right, and thanks for catching it! We've corrected the "
          "question. Good work, keep flagging anything that looks off.")
NO_MSG = ("Thanks for checking! We reviewed this question carefully and the solution is correct as given. "
          "Please revisit the solution key or watch the video explanation to review the steps. "
          "If a specific step still looks unclear, tell us which part and we'll be happy to help!")

app = FastAPI(title="Acadza Faculty Console API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------- file helpers ----------
def read_json(*paths, default=None):
    for p in paths:
        if Path(p).exists():
            try:
                return json.loads(Path(p).read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise HTTPException(500, f"{p} is not valid JSON: {e}")
    return default


def as_list(raw, keys=("questions", "reports", "results", "items", "data")):
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for k in keys:
            if isinstance(raw.get(k), list):
                return raw[k]
        return [{"_id": k, **v} if isinstance(v, dict) else v for k, v in raw.items()]
    return []


def pick(d, *keys, default=""):
    for k in keys:
        if d.get(k) is not None:
            return d[k]
    return default


def text(v):
    if isinstance(v, str):
        return v
    if isinstance(v, (list, tuple)):
        return ",".join(map(str, v))
    if isinstance(v, dict):
        return str(v.get("html") or v.get("text") or json.dumps(v, ensure_ascii=False))
    return str(v)


# ---------- persistent review state ----------
def load_state():
    s = read_json(STATE_FILE, default={}) or {}
    for k, v in (("overrides", {}), ("decisions", {}), ("reopen", {}), ("audit", []), ("new_reports", [])):
        s.setdefault(k, v)
    return s


STATE = load_state()


def save_state():
    STATE_FILE.parent.mkdir(exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(STATE, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


# ---------- normalisation (adjust the key lists if your files differ) ----------
def norm_q(q):
    qid = pick(q, "_id", "id", "questionId")
    if isinstance(qid, dict):
        qid = qid.get("$oid", json.dumps(qid))
    qtype = pick(q, "type", "questionType", default="scq")
    sub = q.get(qtype) if isinstance(q.get(qtype), dict) else {}
    if not sub:
        for k in ("scq", "mcq", "integerQuestion"):
            if isinstance(q.get(k), dict):
                sub = q[k]
                break
    raw_html = pick(sub, "question", "stem", "html", "body", default=pick(q, "question", "stem", "html", "body"))
    raw_ans = pick(sub, "answer", "correctAnswer", "correct", "ans", default=pick(q, "answer", "correctAnswer", "correct", "ans"))
    raw_sol = pick(sub, "solution", "explanation", default=pick(q, "solution", "explanation"))
    if isinstance(raw_ans, list):
        clean_ans = [str(x).strip() for x in raw_ans if str(x).strip()]
        ans_str = ", ".join(clean_ans)
    else:
        ans_str = text(raw_ans)
    return {"id": str(qid), "type": str(qtype),
            "html": text(raw_html),
            "answer": ans_str,
            "solution": text(raw_sol)}


def base_questions():
    raw = read_json(DATA / "questions.json", ROOT / "questions.json", default=[])
    return {q["id"]: q for q in map(norm_q, as_list(raw, ("questions",)))}


def effective(qid):
    q = base_questions().get(qid)
    if not q:
        return None
    ov = STATE["overrides"].get(qid, {})
    return {**q, **ov, "edited": sorted(ov)}


def norm_r(r):
    return {"reportId": str(pick(r, "reportId", "id", "report_id")),
            "questionId": str(pick(r, "questionId", "question_id", "qid")),
            "comment": text(pick(r, "comment", "text", "report", "message")),
            "studentId": "S1",
            "origStudentId": pick(r, "studentId", "student_id", "userId", default="S1")}


def results():
    return as_list(read_json(RESULTS_FILE, ROOT / "investigation.json", ROOT / "result.json", ROOT / "results.json", default=[]), ("results",))


def find_result(rid):
    for r in results():
        if str(r.get("reportId")) == rid:
            return r
    for r in get_reports():
        if str(r.get("reportId")) == rid:
            return {
                "reportId": rid,
                "questionId": r.get("questionId"),
                "status": "pending_investigation",
                "route": "faculty_review",
                "faculty_brief": "Direct report awaiting investigation.",
                "suggested_change": None,
                "independent_answer": None,
                "guard_log": []
            }
    raise HTTPException(404, f"No investigation found for report {rid}")


def audit(**kw):
    STATE["audit"].append({"by": "Faculty (demo)", "ts": int(time.time() * 1000), **kw})


# ---------- read endpoints ----------
@app.get("/api/questions")
def get_questions():
    with LOCK:
        return [effective(i) for i in base_questions()]


@app.get("/api/reports")
def get_reports():
    inv_data = read_json(RESULTS_FILE, ROOT / "investigation.json", ROOT / "result.json", ROOT / "results.json", default=[])
    inv_list = as_list(inv_data, ("results", "items"))
    raw_reports = read_json(DATA / "reports.json", ROOT / "reports.json", default=[])
    rep_map = {str(pick(r, "reportId", "id", "report_id")): r for r in as_list(raw_reports, ("reports",))}
    with LOCK:
        out = []
        for item in inv_list:
            rid = str(pick(item, "reportId", "id", "report_id"))
            qid = str(pick(item, "questionId", "question_id", "qid"))
            rep = rep_map.get(rid, {})
            comment = text(pick(item, "comment", default=pick(rep, "comment", "text", "report", "message")))
            out.append({
                "reportId": rid,
                "questionId": qid,
                "comment": comment,
                "studentId": "S1",
                "origStudentId": pick(rep, "studentId", "student_id", default="S1")
            })
        out.extend(STATE.get("new_reports", []))
        return out


@app.get("/api/results")
def get_results():
    return results()


@app.get("/api/state")
def get_state():
    with LOCK:
        return {k: STATE[k] for k in ("decisions", "reopen", "audit")}


# ---------- write endpoints ----------
class ReviewIn(BaseModel):
    reportId: str
    action: Literal["approved", "edited", "rejected"]
    field: Optional[str] = None
    to: Optional[str] = None
    reply: Optional[str] = None


@app.post("/api/review")
def review(b: ReviewIn):
    res = find_result(b.reportId)
    qid = str(res["questionId"])
    with LOCK:
        if b.reportId in STATE["decisions"]:
            raise HTTPException(409, "This report already has a faculty decision")
        entry = {"reportId": b.reportId, "qid": qid, "action": b.action}
        if b.action != "rejected":
            if b.field not in FIELDS or b.to is None or len(b.to) > 50000:
                raise HTTPException(422, f"An edit needs a field in {sorted(FIELDS)} and a new value")
            q = effective(qid)
            if not q:
                raise HTTPException(404, "Question not found")
            entry.update(field=b.field, before=q[b.field], after=b.to)
            STATE["overrides"].setdefault(qid, {})[b.field] = b.to
        entry["reply"] = (b.reply or "").strip() or (NO_MSG if b.action == "rejected" else OK_MSG)
        audit(**entry)
        STATE["decisions"][b.reportId] = {**STATE["audit"][-1]}
        STATE["reopen"].pop(b.reportId, None)
        save_state()
    return {"ok": True}


class ReportRef(BaseModel):
    reportId: str


@app.post("/api/reopen")
def reopen(b: ReportRef):
    res = find_result(b.reportId)
    with LOCK:
        if b.reportId in STATE["decisions"]:
            raise HTTPException(409, "Already decided by faculty")
        STATE["reopen"][b.reportId] = True
        audit(reportId=b.reportId, qid=str(res["questionId"]), action="reopened AI decision")
        save_state()
    return {"ok": True}


class ReplyIn(BaseModel):
    reportId: str
    reply: str = ""


@app.post("/api/reply")
def set_reply(b: ReplyIn):
    with LOCK:
        d = STATE["decisions"].get(b.reportId)
        if not d:
            raise HTTPException(404, "No decision recorded for this report yet")
        d["reply"] = b.reply.strip() or (NO_MSG if d["action"] == "rejected" else OK_MSG)
        save_state()
    return {"ok": True}


@app.post("/api/questions/{qid}")
def edit_question(qid: str, changes: Dict[str, str]):
    with LOCK:
        q = effective(qid)
        if not q:
            raise HTTPException(404, "Question not found")
        bad = set(changes) - FIELDS
        if bad:
            raise HTTPException(422, f"Fields not editable: {sorted(bad)}")
        for f, v in changes.items():
            if v != q[f]:
                audit(reportId="—", qid=qid, action="manual edit", field=f, before=q[f], after=v)
                STATE["overrides"].setdefault(qid, {})[f] = v
        save_state()
    return {"ok": True}


class NewReport(BaseModel):
    questionId: str
    comment: str


@app.post("/api/reports")
def new_report(b: NewReport):
    comment = b.comment.strip()
    with LOCK:
        if not effective(b.questionId):
            raise HTTPException(404, "Question not found")
        if not comment or len(comment) > 2000:
            raise HTTPException(422, "Comment must be 1-2000 characters")
        r = {"reportId": f"N{len(STATE['new_reports']) + 1:04d}", "questionId": b.questionId,
             "comment": comment, "studentId": "S1", "submittedByStudent": True}
        STATE["new_reports"].append(r)
        save_state()
    return r  # run investigator.py on new reports to produce an investigation for them


# ---------- frontend (must be mounted last) ----------
if FRONT.exists():
    app.mount("/", StaticFiles(directory=FRONT, html=True), name="web")
