# -*- coding: utf-8 -*-
"""
ETF 투자 트렌드 컨텐츠 관리 파일럿 (레벨 2)
- 실행:  pip install fastapi uvicorn python-multipart
         python main.py
- 관리자: http://localhost:8000/admin
- 고객:   http://localhost:8000/app   (팀 공유: http://<내PC IP>:8000/app)
- 데이터: etf_cms.db (SQLite, 자동 생성) / 업로드 파일: ./uploads
"""
import os, sqlite3, time, json, shutil
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "etf_cms.db")
UP = os.path.join(BASE, "uploads")
os.makedirs(UP, exist_ok=True)

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init():
    con = db(); c = con.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS series(
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, intro TEXT DEFAULT '',
      use INTEGER DEFAULT 1, base INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS contents(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT, summary TEXT DEFAULT '', main_image TEXT DEFAULT '',
      use INTEGER DEFAULT 0, start_at TEXT, end_at TEXT, no_end INTEGER DEFAULT 0,
      series_id INTEGER, k1 TEXT DEFAULT '', k2 TEXT DEFAULT '', k3 TEXT DEFAULT '', k4 TEXT DEFAULT '',
      simsa TEXT DEFAULT '', notice TEXT DEFAULT '',
      body_html TEXT DEFAULT '', body_text TEXT DEFAULT '',
      cta_label TEXT DEFAULT '', cta_type TEXT DEFAULT '', cta_target TEXT DEFAULT '',
      pop_mode TEXT DEFAULT 'latest',
      pdf_url TEXT DEFAULT '', pdf_name TEXT DEFAULT '',
      etfs TEXT DEFAULT '',
      views INTEGER DEFAULT 0, ups INTEGER DEFAULT 0, downs INTEGER DEFAULT 0,
      deleted INTEGER DEFAULT 0, created_at TEXT);
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
    """)
    for col, dd in [("format","TEXT DEFAULT 'article'"),("video_id","TEXT DEFAULT ''"),("video_url","TEXT DEFAULT ''"),("cta_screen","TEXT DEFAULT ''"),("pop_ids","TEXT DEFAULT ''")]:
        try: c.execute(f"ALTER TABLE contents ADD COLUMN {col} {dd}")
        except sqlite3.OperationalError: pass
    for col in ["image", "icon", "label_image"]:
        try: c.execute(f"ALTER TABLE series ADD COLUMN {col} TEXT DEFAULT ''")
        except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE series ADD COLUMN sort_order INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass
    c.execute("UPDATE series SET sort_order=id WHERE sort_order IS NULL OR sort_order=0")  # 기존 데이터: 등록순 초기화
    if not c.execute("SELECT 1 FROM series").fetchone():
        c.executemany("INSERT INTO series(name,intro,use,base) VALUES(?,?,1,1)", [
            ("ETF 시황", "ETF 투자 시황을 쉽고 명확하게 알려드려요"),
            ("신규 ETF", "새로 나온 ETF를 소개해 드려요"),
            ("ETF 투자가이드", "ETF 투자, 기초부터 차근차근 알려드려요"),
        ])
    if not c.execute("SELECT 1 FROM settings WHERE key='common_notice'").fetchone():
        c.execute("INSERT INTO settings VALUES('common_notice',?)", (
            "본 자료는 투자 참고자료이며, 투자권유 또는 종목 추천을 목적으로 하지 않습니다.\n"
            "금융투자상품은 예금자보호법에 따라 보호되지 않으며, 투자원금의 손실이 발생할 수 있습니다.\n"
            "과거의 수익률이 미래의 수익률을 보장하지 않습니다.",))
    if not c.execute("SELECT 1 FROM contents").fetchone():
        now = datetime.now().strftime("%Y-%m-%dT%H:%M")
        c.execute("""INSERT INTO contents(title,summary,use,start_at,end_at,no_end,series_id,
            k1,k2,k3,simsa,body_html,body_text,cta_label,cta_type,cta_screen,etfs,views,ups,created_at)
            VALUES(?,?,1,?,?,1,1,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            "ETF 금리인상 그림자", "금리 인상기 ETF 자금 흐름을 3분 만에 정리했어요",
            now, now, "금리인상", "미국증시", "월배당ETF",
            "준법감시인 심사필 제2026-1234호 (2026.10.28)",
            "<p>미국 증시는 CPI 발표를 앞두고 혼조세로 마감했어요. 10년물 금리 상승 영향으로 기술주 중심의 차익 실현 매물이 출회됐습니다.</p>"
            "<h3>오늘의 국내 증시는?</h3><p>국내 증시에서는 반도체 레버리지 ETF가 <b>순유입 1위(+1,240억 원)</b>를 기록하며 개인 수급을 이끌었어요.</p>",
            "미국 증시 CPI 혼조 반도체 레버리지 순유입 월배당",
            "ETF 탐색하기", "화면이동", "2851",
            "487550, 458730", 128, 14, now))
    if not c.execute("SELECT 1 FROM contents WHERE format='shorts'").fetchone():
        now = datetime.now().strftime("%Y-%m-%dT%H:%M")
        c.execute("""INSERT INTO contents(title,summary,use,start_at,end_at,no_end,series_id,k1,k2,
            simsa,format,video_id,video_url,etfs,views,ups,created_at,body_html,body_text)
            VALUES(?,?,1,?,?,1,1,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            "1분 만에 보는 이번 주 ETF 자금 동향", "이번 주 ETF 자금 흐름 1분 요약",
            now, now, "자금동향", "숏츠",
            "준법감시인 심사필 제2026-1235호", "shorts", "qIk2ssybKrA",
            "https://www.youtube.com/shorts/qIk2ssybKrA",
            "KODEX 미국AI전력인프라(487550)", 84, 9, now, "", ""))
    c.execute("UPDATE series SET sort_order=id WHERE sort_order IS NULL OR sort_order=0")  # 시드 포함 등록순 초기화
    con.commit(); con.close()

init()

# 종목 마스터 (파일럿 샘플) — 실서비스: 사내 종목 마스터 연동. 여기 없는 코드는 고객 화면 미노출
ETF_MASTER = {
    "487550": "KODEX 미국AI전력인프라",
    "458730": "TIGER 미국배당다우존스",
    "091160": "KODEX 반도체",
    "069500": "KODEX 200",
    "122630": "KODEX 레버리지",
    "360750": "TIGER 미국S&P500",
    "133690": "TIGER 미국나스닥100",
    "476690": "TIGER 글로벌비만치료제TOP2Plus",
}
def resolve_etfs(codes_str: str):
    """쉼표 구분 종목코드 → 마스터 등록분만 [{code,name}] 반환 (미등록 코드는 제외 = 미노출)"""
    items = []
    for c in (codes_str or "").split(","):
        c = c.strip()
        if c and c in ETF_MASTER:
            items.append({"code": c, "name": ETF_MASTER[c]})
    return items

app = FastAPI(title="ETF 투자 트렌드 CMS 파일럿")
app.mount("/uploads", StaticFiles(directory=UP), name="uploads")

# ---------- 관리자 인증 (Basic Auth) ----------
# Render 배포 시 환경변수 ADMIN_USER / ADMIN_PASS 로 반드시 변경하세요.
import base64
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "kiwoom2026")

@app.middleware("http")
async def admin_auth(request, call_next):
    path = request.url.path
    protected = (
        path.startswith("/admin")
        or (path.startswith("/api") and request.method in ("POST", "PUT", "DELETE")
            and not path.endswith("/react"))   # 고객 추천/비추천은 인증 제외
    )
    if protected:
        auth = request.headers.get("authorization", "")
        ok = False
        if auth.startswith("Basic "):
            try:
                u, p = base64.b64decode(auth[6:]).decode().split(":", 1)
                ok = (u == ADMIN_USER and p == ADMIN_PASS)
            except Exception:
                pass
        if not ok:
            return JSONResponse({"detail": "인증 필요"}, status_code=401,
                                headers={"WWW-Authenticate": 'Basic realm="admin"'})
    return await call_next(request)

# ---------- 페이지 ----------
@app.get("/")
def root(): return RedirectResponse("/app")
NOCACHE = {"Cache-Control": "no-store, must-revalidate", "Pragma": "no-cache"}
@app.get("/admin")
def admin_page(): return FileResponse(os.path.join(BASE, "static", "admin.html"), headers=NOCACHE)
@app.get("/app")
def app_page(): return FileResponse(os.path.join(BASE, "static", "app.html"), headers=NOCACHE)

# ---------- 업로드 ----------
@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    name = f"{int(time.time()*1000)}_{file.filename}"
    with open(os.path.join(UP, name), "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"url": f"/uploads/{name}", "name": file.filename}

# ---------- 종목코드 조회 (관리자 폼) ----------
@app.get("/api/etf/lookup")
def etf_lookup(codes: str = ""):
    out = []
    for c in codes.split(","):
        c = c.strip()
        if not c: continue
        out.append({"code": c, "name": ETF_MASTER.get(c), "found": c in ETF_MASTER})
    return out

# ---------- 시리즈 ----------
class SeriesIn(BaseModel):
    name: str; intro: str = ""; use: int = 1; image: str = ""; label_image: str = ""; icon: str = ""
@app.get("/api/series")
def series_list():
    con = db()
    now = now_str()
    rows = [dict(r) for r in con.execute(
        "SELECT s.*, (SELECT COUNT(*) FROM contents c WHERE c.series_id=s.id AND c.deleted=0) AS cnt, "
        "(SELECT COUNT(*) FROM contents c WHERE c.series_id=s.id AND c.deleted=0 AND c.use=1 "
        " AND c.format='article' AND c.start_at<=? AND (c.no_end=1 OR c.end_at>=?)) AS live_cnt FROM series s "
        "ORDER BY s.sort_order, s.id", (now, now))]   # 노출 우선순위 — 홈 카드·칩·등록폼 공통
    con.close(); return rows
@app.post("/api/series")
def series_add(s: SeriesIn):
    con = db()
    try:
        nxt = (con.execute("SELECT COALESCE(MAX(sort_order),0)+1 FROM series").fetchone()[0])  # 신규는 맨 뒤
        con.execute("INSERT INTO series(name,intro,use,image,icon,label_image,sort_order) VALUES(?,?,?,?,?,?,?)",
                    (s.name, s.intro, s.use, s.image, s.icon, s.label_image, nxt)); con.commit()
    except sqlite3.IntegrityError: raise HTTPException(400, "이미 존재하는 트렌드명입니다")
    finally: con.close()
    return {"ok": 1}
@app.put("/api/series/{sid}/move")
def series_move(sid: int, body: dict):
    """노출 우선순위 이동 — 이웃 시리즈와 sort_order 교환 (up/down)"""
    con = db()
    rows = [dict(r) for r in con.execute("SELECT id, sort_order FROM series ORDER BY sort_order, id")]
    idx = next((i for i, r in enumerate(rows) if r["id"] == sid), None)
    j = idx - 1 if body.get("dir") == "up" else idx + 1 if idx is not None else None
    if idx is None or j is None or j < 0 or j >= len(rows):
        con.close(); return {"ok": 0}
    a_, b_ = rows[idx], rows[j]
    con.execute("UPDATE series SET sort_order=? WHERE id=?", (b_["sort_order"], a_["id"]))
    con.execute("UPDATE series SET sort_order=? WHERE id=?", (a_["sort_order"], b_["id"]))
    con.commit(); con.close(); return {"ok": 1}

@app.put("/api/series/{sid}")
def series_edit(sid: int, s: SeriesIn):
    con = db(); con.execute("UPDATE series SET name=?,intro=?,use=?,image=?,icon=?,label_image=? WHERE id=?", (s.name, s.intro, s.use, s.image, s.icon, s.label_image, sid))
    con.commit(); con.close(); return {"ok": 1}

# ---------- 공통 유의문구 (SCR-04) ----------
class NoticeIn(BaseModel): value: str
@app.get("/api/notice")
def notice_get():
    con = db(); v = con.execute("SELECT value FROM settings WHERE key='common_notice'").fetchone()
    con.close(); return {"value": v["value"] if v else ""}
@app.put("/api/notice")
def notice_put(n: NoticeIn):
    con = db(); con.execute("REPLACE INTO settings VALUES('common_notice',?)", (n.value,))
    con.commit(); con.close(); return {"ok": 1}

# ---------- 컨텐츠 ----------
class ContentIn(BaseModel):
    title: str; summary: str = ""; main_image: str = ""
    use: int = 0; start_at: str = ""; end_at: str = ""; no_end: int = 0
    series_id: int; k1: str = ""; k2: str = ""; k3: str = ""; k4: str = ""
    simsa: str = ""; notice: str = ""
    body_html: str = ""; body_text: str = ""
    cta_label: str = ""; cta_type: str = ""; cta_target: str = ""; cta_screen: str = ""
    pop_mode: str = "latest"; pop_ids: str = ""
    pdf_url: str = ""; pdf_name: str = ""; etfs: str = ""
    format: str = "article"; video_id: str = ""; video_url: str = ""

VISIBLE_SQL = """c.deleted=0 AND c.use=1 AND s.use=1 AND c.start_at<=? AND (c.no_end=1 OR c.end_at>=?)"""

def now_str(): return datetime.now().strftime("%Y-%m-%dT%H:%M")

@app.get("/api/contents")
def contents(admin: int = 0, q: str = "", series: int = 0, sort: str = "latest", fmt: str = "article"):
    con = db(); now = now_str()
    sql = "SELECT c.*, s.name AS series_name, s.use AS series_use FROM contents c JOIN series s ON s.id=c.series_id WHERE "
    args = []
    if admin:
        sql += "c.deleted=0"
    else:
        sql += VISIBLE_SQL; args += [now, now]
    if not admin and fmt != "all":
        sql += " AND c.format=?"; args.append(fmt)
    if series:
        sql += " AND c.series_id=?"; args.append(series)
    if q:
        sql += " AND (c.title LIKE ? OR c.summary LIKE ? OR c.k1 LIKE ? OR c.k2 LIKE ? OR c.k3 LIKE ? OR c.k4 LIKE ? OR c.body_text LIKE ?)"
        args += [f"%{q}%"] * 7
    order = {"latest": "c.id DESC", "ups": "c.ups DESC", "views": "c.views DESC"}.get(sort, "c.id DESC")
    sql += f" ORDER BY {order}"
    rows = [dict(r) for r in con.execute(sql, args)]
    con.close()
    if not admin:
        for r in rows: r.pop("body_html", None); r.pop("body_text", None)
    return rows

@app.get("/api/contents/{cid}")
def content_get(cid: int, view: int = 0):
    con = db()
    if view: con.execute("UPDATE contents SET views=views+1 WHERE id=?", (cid,)); con.commit()
    r = con.execute("SELECT c.*, s.name AS series_name FROM contents c JOIN series s ON s.id=c.series_id WHERE c.id=?", (cid,)).fetchone()
    if not r: con.close(); raise HTTPException(404, "not found")
    d = dict(r)
    d["etf_items"] = resolve_etfs(d.get("etfs", ""))   # 미등록 코드 제외 — 없으면 빈 배열(섹션 미노출)
    # ⑬ 인기 콘텐츠 — 수동: pop_ids 지정 순서(노출 조건 충족 글만) / 자동: 동일 시리즈 內 정렬 TOP3
    now = now_str()
    base = ("SELECT c.id, c.title, c.main_image, c.created_at, s.icon AS sicon "
            "FROM contents c JOIN series s ON s.id=c.series_id WHERE " + VISIBLE_SQL +
            " AND c.format='article' AND c.id != ?")
    if d.get("pop_mode") == "manual":
        ids = [int(x) for x in (d.get("pop_ids") or "").split(",") if x.strip().isdigit()][:3]
        if ids:
            q = base + f" AND c.id IN ({','.join('?'*len(ids))})"
            found = {row["id"]: dict(row) for row in con.execute(q, (now, now, cid, *ids))}
            d["pop_items"] = [found[i] for i in ids if i in found]   # 지정 순서 유지, 미노출 글 제외
        else:
            d["pop_items"] = []
    else:
        order = {"latest": "c.id DESC", "ups": "c.ups DESC", "views": "c.views DESC"}.get(d.get("pop_mode") or "latest", "c.id DESC")
        d["pop_items"] = [dict(row) for row in con.execute(
            base + " AND c.series_id=? ORDER BY " + order + " LIMIT 3", (now, now, cid, d["series_id"]))]
    con.close()
    return d

@app.post("/api/contents")
def content_add(x: ContentIn):
    con = db()
    cur = con.execute("""INSERT INTO contents(title,summary,main_image,use,start_at,end_at,no_end,series_id,
        k1,k2,k3,k4,simsa,notice,body_html,body_text,cta_label,cta_type,cta_target,cta_screen,pop_mode,pop_ids,pdf_url,pdf_name,etfs,format,video_id,video_url,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (x.title, x.summary, x.main_image, x.use, x.start_at, x.end_at, x.no_end, x.series_id,
         x.k1, x.k2, x.k3, x.k4, x.simsa, x.notice, x.body_html, x.body_text,
         x.cta_label, x.cta_type, x.cta_target, x.cta_screen, x.pop_mode, x.pop_ids, x.pdf_url, x.pdf_name, x.etfs,
         x.format, x.video_id, x.video_url, now_str()))
    con.commit(); cid = cur.lastrowid; con.close()
    return {"ok": 1, "id": cid}

@app.put("/api/contents/{cid}")
def content_edit(cid: int, x: ContentIn):
    con = db()
    con.execute("""UPDATE contents SET title=?,summary=?,main_image=?,use=?,start_at=?,end_at=?,no_end=?,series_id=?,
        k1=?,k2=?,k3=?,k4=?,simsa=?,notice=?,body_html=?,body_text=?,cta_label=?,cta_type=?,cta_target=?,cta_screen=?,pop_mode=?,pop_ids=?,
        pdf_url=?,pdf_name=?,etfs=?,format=?,video_id=?,video_url=? WHERE id=?""",
        (x.title, x.summary, x.main_image, x.use, x.start_at, x.end_at, x.no_end, x.series_id,
         x.k1, x.k2, x.k3, x.k4, x.simsa, x.notice, x.body_html, x.body_text,
         x.cta_label, x.cta_type, x.cta_target, x.cta_screen, x.pop_mode, x.pop_ids, x.pdf_url, x.pdf_name, x.etfs,
         x.format, x.video_id, x.video_url, cid))
    con.commit(); con.close(); return {"ok": 1}

@app.delete("/api/contents/{cid}")
def content_del(cid: int):
    con = db(); con.execute("UPDATE contents SET deleted=1 WHERE id=?", (cid,))
    con.commit(); con.close(); return {"ok": 1}

@app.post("/api/contents/{cid}/react")
def react(cid: int, body: dict):
    col = "ups" if body.get("type") == "up" else "downs"
    con = db(); con.execute(f"UPDATE contents SET {col}={col}+1 WHERE id=?", (cid,))
    con.commit()
    r = con.execute("SELECT ups,downs FROM contents WHERE id=?", (cid,)).fetchone()
    con.close(); return dict(r)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))   # Render는 PORT 환경변수를 지정함
    print(f"\n  관리자: http://localhost:{port}/admin\n  고객:   http://localhost:{port}/app\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
