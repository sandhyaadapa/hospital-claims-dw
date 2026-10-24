"""ClaimsLens - Flask web application over the hospital insurance-claims data warehouse.
Run:  python3 app.py   then open http://127.0.0.1:5000
"""
import os, sys, time, sqlite3
from flask import Flask, jsonify, request, send_from_directory, abort
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
from olap import Q, DW, BASE          # the six OLAP queries used in the report

app = Flask(__name__, static_folder=os.path.join(HERE, "static"), static_url_path="/static")

def db(path):
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA cache_size=-100000")
    return c

@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.get("/api/meta")
def meta():
    c = db(DW)
    return jsonify(
        insurers=[r[0] for r in c.execute("SELECT insurer_name FROM dim_insurer ORDER BY insurer_key")],
        hospitals=[r[0] for r in c.execute("SELECT hospital_name FROM dim_hospital ORDER BY hospital_key")],
        months=[r[0] for r in c.execute("SELECT DISTINCT month_key FROM fact_claim_monthly_snapshot ORDER BY 1")],
        counts={t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in
                ["fact_claim_line", "fact_claim_monthly_snapshot", "dim_patient", "dim_hospital", "dim_insurer", "dq_reject"]},
        queries={k: v[0] for k, v in Q.items()})

@app.get("/api/overview")
def overview():
    a = request.args.get("from", type=int, default=0); b = request.args.get("to", type=int, default=999999)
    ins = request.args.get("insurer", type=int); hos = request.args.get("hospital", type=int)
    w, p = ["month_key BETWEEN ? AND ?"], [a, b]
    if ins is not None: w.append("insurer_key=?"); p.append(ins + 1)
    if hos is not None: w.append("hospital_key=?"); p.append(hos + 1)
    where = " AND ".join(w); c = db(DW)
    agg = "SUM(claim_count) claims, SUM(billed_amount) billed, SUM(paid_amount) paid, SUM(denied_amount) denied"
    t0 = time.perf_counter()
    kpi = dict(c.execute(f"SELECT {agg} FROM fact_claim_monthly_snapshot WHERE {where}", p).fetchone())
    trend = [dict(r) for r in c.execute(f"SELECT month_key, {agg} FROM fact_claim_monthly_snapshot WHERE {where} GROUP BY 1 ORDER BY 1", p)]
    by_ins = [dict(r) for r in c.execute(f"SELECT i.insurer_name name, SUM(s.paid_amount) paid, SUM(s.billed_amount) billed, SUM(s.denied_amount) denied FROM fact_claim_monthly_snapshot s JOIN dim_insurer i USING(insurer_key) WHERE {where.replace('month_key','s.month_key').replace('insurer_key','s.insurer_key').replace('hospital_key','s.hospital_key')} GROUP BY 1 ORDER BY 2 DESC", p)]
    by_hos = [dict(r) for r in c.execute(f"SELECT h.hospital_name name, SUM(s.paid_amount) paid, SUM(s.billed_amount) billed, SUM(s.denied_amount) denied FROM fact_claim_monthly_snapshot s JOIN dim_hospital h USING(hospital_key) WHERE {where.replace('month_key','s.month_key').replace('insurer_key','s.insurer_key').replace('hospital_key','s.hospital_key')} GROUP BY 1 ORDER BY 2 DESC", p)]
    return jsonify(kpi=kpi, trend=trend, by_insurer=by_ins, by_hospital=by_hos, ms=round((time.perf_counter() - t0) * 1000, 1))

@app.get("/api/claims")
def claims():
    q = (request.args.get("q") or "").strip().upper()
    status = request.args.get("status") or ""
    c = db(DW)
    sql = ("SELECT f.claim_id, MIN(d.full_date) service_date, i.insurer_name, h.hospital_name, s.claim_status, "
           "COUNT(*) lines, ROUND(SUM(f.billed_amount),2) billed, ROUND(SUM(f.paid_amount),2) paid "
           "FROM fact_claim_line f JOIN dim_date d ON d.date_key=f.service_date_key JOIN dim_insurer i USING(insurer_key) "
           "JOIN dim_hospital h USING(hospital_key) JOIN dim_claim_status s USING(claim_status_key) WHERE f.claim_id LIKE ?")
    p = [q + "%"]
    if status: sql += " AND s.claim_status=?"; p.append(status)
    sql += " GROUP BY f.claim_id ORDER BY f.claim_id LIMIT 25"
    return jsonify([dict(r) for r in c.execute(sql, p)])

@app.get("/api/claim/<claim_id>")
def claim(claim_id):
    c = db(DW)
    rows = c.execute("""SELECT f.line_no, d.full_date service_date, g.icd10_code, g.description dx, pr.description procedure_name,
        pv.doctor_name, pv.specialty, h.hospital_name, i.insurer_name, pl.plan_name, s.claim_status, s.denial_reason,
        f.quantity, f.billed_amount, f.allowed_amount, f.denied_amount, f.copay_amount, f.paid_amount, f.processing_days,
        pt.patient_id, pt.gender, pt.age_band, pt.city, pt.plan_id, pt.version_no
        FROM fact_claim_line f JOIN dim_date d ON d.date_key=f.service_date_key JOIN dim_diagnosis g USING(diagnosis_key)
        JOIN dim_procedure pr USING(procedure_key) JOIN dim_provider pv USING(provider_key) JOIN dim_hospital h USING(hospital_key)
        JOIN dim_insurer i USING(insurer_key) JOIN dim_plan pl USING(plan_key) JOIN dim_claim_status s USING(claim_status_key)
        JOIN dim_patient pt USING(patient_key) WHERE f.claim_id=? ORDER BY f.line_no""", (claim_id,)).fetchall()
    if not rows: abort(404)
    return jsonify([dict(r) for r in rows])

@app.get("/api/patient/<pid>")
def patient(pid):
    c = db(DW)
    rows = [dict(r) for r in c.execute("SELECT version_no, city, state, plan_id, effective_from, effective_to, is_current FROM dim_patient WHERE patient_id=? ORDER BY version_no", (pid,))]
    if not rows: abort(404)
    return jsonify(rows)

@app.get("/api/patients/changed")
def changed():
    c = db(DW)
    return jsonify([r[0] for r in c.execute("SELECT patient_id FROM dim_patient GROUP BY 1 HAVING COUNT(*)>1 LIMIT 40")])

@app.get("/api/olap/<qid>")
def olap(qid):
    if qid not in Q: abort(404)
    engine = request.args.get("engine", "star")
    sql = Q[qid][1] if engine == "star" else Q[qid][2]
    c = db(DW if engine == "star" else BASE)
    c.execute(sql).fetchall()
    ts = []
    for _ in range(3):
        t0 = time.perf_counter(); cur = c.execute(sql); rows = cur.fetchall(); ts.append((time.perf_counter() - t0) * 1000)
    return jsonify(title=Q[qid][0], engine=engine, sql=" ".join(sql.split()), columns=[d[0] for d in cur.description],
                   rows=[list(r) for r in rows[:200]], ms=round(sorted(ts)[1], 1), row_count=len(rows))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
