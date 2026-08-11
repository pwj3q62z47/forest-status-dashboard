import json
import os
import base64
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

from flask import Flask, jsonify, request


APP = Flask(__name__)
DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
STATE_FILE = DATA_DIR / "forest_public_status.json"
UPLOAD_TOKEN = os.environ.get("UPLOAD_TOKEN", "")
VIEW_TOKEN = os.environ.get("VIEW_TOKEN", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.environ.get("GITHUB_REPO", "").strip()
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main").strip()
GITHUB_STATE_PATH = os.environ.get("GITHUB_STATE_PATH", "forest_public_status.json").strip()


def default_state():
    return {
        "created_at": None,
        "received_at": None,
        "count": 0,
        "reservations": 0,
        "waits": 0,
        "rows": [],
    }


def github_enabled():
    return bool(GITHUB_TOKEN and GITHUB_REPO and GITHUB_STATE_PATH)


def github_api_url():
    path = GITHUB_STATE_PATH.lstrip("/")
    return f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"


def github_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "forest-status-dashboard",
    }


def load_github_state():
    if not github_enabled():
        return None
    url = f"{github_api_url()}?ref={GITHUB_BRANCH}"
    req = request.Request(url, headers=github_headers(), method="GET")
    try:
        with request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        encoded = payload.get("content", "")
        raw = base64.b64decode(encoded).decode("utf-8")
        return json.loads(raw)
    except Exception:
        return None


def get_github_file_sha():
    if not github_enabled():
        return None
    url = f"{github_api_url()}?ref={GITHUB_BRANCH}"
    req = request.Request(url, headers=github_headers(), method="GET")
    try:
        with request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload.get("sha")
    except error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def save_github_state(data):
    if not github_enabled():
        return False
    body = {
        "message": "Update forest public status",
        "content": base64.b64encode(
            json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        ).decode("ascii"),
        "branch": GITHUB_BRANCH,
    }
    sha = get_github_file_sha()
    if sha:
        body["sha"] = sha
    req = request.Request(
        github_api_url(),
        data=json.dumps(body).encode("utf-8"),
        headers={**github_headers(), "Content-Type": "application/json"},
        method="PUT",
    )
    try:
        with request.urlopen(req, timeout=15):
            return True
    except Exception:
        return False


def load_state():
    if not STATE_FILE.exists():
        return load_github_state() or default_state()
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return load_github_state() or default_state()


def save_state(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    save_github_state(data)


def authorized():
    if not UPLOAD_TOKEN:
        return False
    return request.headers.get("X-Upload-Token", "") == UPLOAD_TOKEN


def can_view():
    if not VIEW_TOKEN:
        return True
    token = request.args.get("token", "")
    return token == VIEW_TOKEN


@APP.get("/api/status")
def api_status():
    if not can_view():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    return jsonify(load_state())


@APP.post("/api/upload")
def api_upload():
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(force=True, silent=True) or {}
    rows = data.get("rows") or []
    safe_rows = []
    for row in rows:
        safe_rows.append(
            {
                "account_name": row.get("account_name", ""),
                "kind": row.get("kind", ""),
                "status": row.get("status", ""),
                "period": row.get("period", ""),
                "dday": row.get("dday", ""),
                "source": row.get("source", ""),
                "forest": row.get("forest", ""),
                "room": row.get("room", ""),
                "amount": row.get("amount", ""),
                "note": row.get("note", ""),
            }
        )
    payload = {
        "created_at": data.get("created_at"),
        "received_at": datetime.now(timezone.utc).isoformat(),
        "count": len(safe_rows),
        "reservations": sum(1 for row in safe_rows if row.get("kind") == "예약"),
        "waits": sum(1 for row in safe_rows if row.get("kind") == "대기"),
        "rows": safe_rows,
    }
    save_state(payload)
    return jsonify({"ok": True, "count": len(safe_rows)})


@APP.get("/")
def index():
    if not can_view():
        return """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>접근 제한</title><style>
body{font-family:Malgun Gothic,Segoe UI,Arial,sans-serif;background:#f5f7f9;color:#172033;margin:0}
main{max-width:520px;margin:80px auto;background:#fff;border:1px solid #d9e0e8;border-radius:8px;padding:22px}
h1{font-size:22px;margin:0 0 10px} p{color:#64748b;line-height:1.6}
</style></head><body><main>
<h1>접근 제한</h1>
<p>현황을 보려면 올바른 보기 비밀번호가 필요합니다.</p>
<p>주소 뒤에 <b>?token=보기비밀번호</b>를 붙여 접속하세요.</p>
</main></body></html>""", 401
    return """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>예약/대기 현황</title>
  <style>
    body{margin:0;font-family:Malgun Gothic,Segoe UI,Arial,sans-serif;background:#f5f7f9;color:#172033}
    header{background:#14532d;color:#fff;padding:16px 22px}
    main{max-width:1280px;margin:0 auto;padding:16px}
    h1{font-size:21px;margin:0 0 5px} h2{font-size:17px;margin:18px 0 10px}
    .muted{color:#64748b;font-size:13px}.header-muted{color:#d9f99d;font-size:13px}
    .grid{display:grid;grid-template-columns:repeat(3,minmax(150px,1fr));gap:10px;margin-bottom:12px}
    .card{background:#fff;border:1px solid #d9e0e8;border-radius:8px;padding:12px}
    .metric strong{display:block;font-size:25px;margin-top:5px}
    .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}
    button{border:1px solid #15803d;background:#fff;color:#166534;border-radius:6px;padding:8px 12px;font-weight:700;cursor:pointer}
    table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #d9e0e8;font-size:13px}
    th,td{border-bottom:1px solid #e6ebf0;padding:7px 8px;text-align:left;vertical-align:top}
    th{background:#edf2f7;position:sticky;top:0;z-index:1}.table-wrap{max-height:480px;overflow:auto;border-radius:8px}
    .wait1 td{background:#fff7ed}.urgent td{border-left:4px solid #dc2626}
    .tab{display:none}.tab.active{display:block}
    details{background:#fff;border:1px solid #d9e0e8;border-radius:8px;margin:8px 0}
    summary{padding:10px 12px;cursor:pointer;font-weight:700}
    details table{border-left:0;border-right:0;border-bottom:0}
    @media(max-width:760px){.grid{grid-template-columns:1fr}.table-wrap{max-height:none} th,td{font-size:12px;padding:6px}}
  </style>
</head>
<body>
  <header>
    <h1>예약/대기 현황</h1>
    <div id="subtitle" class="header-muted">불러오는 중...</div>
  </header>
  <main>
    <section class="grid">
      <div class="card metric"><span class="muted">예약</span><strong id="reserveCount">0</strong></div>
      <div class="card metric"><span class="muted">대기</span><strong id="waitCount">0</strong></div>
      <div class="card metric"><span class="muted">전체</span><strong id="totalCount">0</strong></div>
    </section>
    <div class="tabs">
      <button onclick="showTab('reservations')">예약현황</button>
      <button onclick="showTab('waits')">대기현황</button>
      <button onclick="showTab('accounts')">계정별 정리</button>
      <button onclick="showTab('dates')">날짜별 정리</button>
    </div>
    <section id="reservations" class="tab active card"><h2>예약현황</h2><div class="table-wrap" id="reservationTable"></div></section>
    <section id="waits" class="tab card"><h2>대기현황</h2><div class="table-wrap" id="waitTable"></div></section>
    <section id="accounts" class="tab card"><h2>계정별 정리</h2><div id="accountGroups"></div></section>
    <section id="dates" class="tab card"><h2>날짜별 정리</h2><div id="dateGroups"></div></section>
  </main>
<script>
function escapeHtml(v){return String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}[m]));}
function parseStart(period){const m=String(period||"").match(/\\d{4}-\\d{2}-\\d{2}/);return m?new Date(m[0]+"T00:00:00"):new Date("9999-12-31");}
function sortRows(rows){return [...rows].sort((a,b)=>parseStart(a.period)-parseStart(b.period)||String(a.account_name).localeCompare(String(b.account_name),"ko")||String(a.forest).localeCompare(String(b.forest),"ko"));}
function rowClass(r){const cls=[];if(r.kind==="대기"&&r.status==="대기1순위")cls.push("wait1");if(["오늘","D-1","D-2","D-3"].includes(r.dday))cls.push("urgent");return cls.join(" ");}
function table(rows, showAccount=true){if(!rows.length)return '<p class="muted">데이터 없음</p>';const labels=showAccount?["상태","이용기간","D-Day","계정","출처","시설","객실","금액","비고"]:["상태","이용기간","D-Day","출처","시설","객실","금액","비고"];const head=labels.map(c=>`<th>${c}</th>`).join("");const body=sortRows(rows).map(r=>{const account=showAccount?`<td>${escapeHtml(r.account_name)}</td>`:"";return `<tr class="${rowClass(r)}"><td>${escapeHtml(r.status)}</td><td>${escapeHtml(r.period)}</td><td>${escapeHtml(r.dday)}</td>${account}<td>${escapeHtml(r.source)}</td><td>${escapeHtml(r.forest)}</td><td>${escapeHtml(r.room)}</td><td>${escapeHtml(r.amount)}</td><td>${escapeHtml(r.note)}</td></tr>`}).join("");return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;}
function groupBy(rows,keyFn){return rows.reduce((m,r)=>{const k=keyFn(r)||"미확인";(m[k] ||= []).push(r);return m;},{});}
function accountGroups(rows){const g=groupBy(rows,r=>r.account_name);return Object.keys(g).sort((a,b)=>a.localeCompare(b,"ko")).map(k=>{const rs=g[k].filter(r=>r.kind==="예약");const ws=g[k].filter(r=>r.kind==="대기");return `<details><summary>${escapeHtml(k)} <span class="muted">예약 ${rs.length} / 대기 ${ws.length}/3 / 남음 ${Math.max(0,3-ws.length)}</span></summary><h2>예약</h2>${table(rs,false)}<h2>대기</h2>${table(ws,false)}</details>`}).join("")||'<p class="muted">데이터 없음</p>';}
function dateGroups(rows){const g=groupBy(rows,r=>r.period);return Object.keys(g).sort((a,b)=>parseStart(a)-parseStart(b)).map(k=>{const rs=g[k].filter(r=>r.kind==="예약");const ws=g[k].filter(r=>r.kind==="대기");return `<details><summary>${escapeHtml(k)} <span class="muted">${escapeHtml((g[k][0]||{}).dday||"")} / 예약 ${rs.length} / 대기 ${ws.length}</span></summary><h2>예약</h2>${table(rs)}<h2>대기</h2>${table(ws)}</details>`}).join("")||'<p class="muted">데이터 없음</p>';}
function showTab(id){document.querySelectorAll(".tab").forEach(el=>el.classList.remove("active"));document.getElementById(id).classList.add("active");}
async function loadData(){const data=await fetch("/api/status"+window.location.search).then(r=>r.json());const rows=data.rows||[];const rs=rows.filter(r=>r.kind==="예약");const ws=rows.filter(r=>r.kind==="대기");document.getElementById("subtitle").textContent=`최근 갱신: ${data.created_at||"-"}`;document.getElementById("reserveCount").textContent=rs.length;document.getElementById("waitCount").textContent=ws.length;document.getElementById("totalCount").textContent=rows.length;document.getElementById("reservationTable").innerHTML=table(rs);document.getElementById("waitTable").innerHTML=table(ws);document.getElementById("accountGroups").innerHTML=accountGroups(rows);document.getElementById("dateGroups").innerHTML=dateGroups(rows);}
setInterval(loadData,10000);loadData();
</script>
</body>
</html>"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8787"))
    APP.run(host="0.0.0.0", port=port)
