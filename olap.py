"""OLAP queries on the star schema vs the same business questions on a normalized (3NF) cleansed copy."""
import os, json, time, sqlite3, statistics, shutil
import pandas as pd, numpy as np
from etl import DATA, SRC, DW
RES = os.path.join(DATA, "..", "results")
BASE = os.path.join(DATA, "baseline_3nf.db")

def build_baseline():
    """Cleansed normalized copy of the source (what an analyst would query without a warehouse)."""
    if os.path.exists(BASE): os.remove(BASE)
    s = sqlite3.connect(SRC); b = sqlite3.connect(BASE)
    C = pd.read_sql("SELECT * FROM src_claim", s).drop_duplicates("claim_id")
    L = pd.read_sql("SELECT * FROM src_claim_line", s)
    ok = (L.billed_amount >= 0) & (L.paid_amount <= L.allowed_amount + .005) & (L.service_date >= "2023-01-01") & (L.service_date <= "2025-12-31")
    L = L[ok & L.claim_id.isin(C.claim_id)]
    dx = pd.read_sql("SELECT * FROM src_diagnosis_ref", s)
    C.loc[~C.primary_icd10.isin(dx.icd10), "primary_icd10"] = "UNK"
    dx = pd.concat([dx, pd.DataFrame([{"icd10": "UNK", "description": "Unknown / not recorded", "category": "Unknown", "chronic_flag": 0}])])
    C.to_sql("claim", b, index=False); L.to_sql("claim_line", b, index=False); dx.to_sql("diagnosis_ref", b, index=False)
    for t in ["patient", "plan", "insurer", "hospital", "doctor", "procedure_ref"]:
        pd.read_sql(f"SELECT * FROM src_{t}", s).to_sql(t, b, index=False)
    for sql in ["CREATE UNIQUE INDEX i1 ON claim(claim_id)", "CREATE INDEX i2 ON claim_line(claim_id)", "CREATE INDEX i3 ON claim(patient_id)",
                "CREATE INDEX i4 ON claim(plan_id)", "CREATE INDEX i5 ON claim(hospital_id)", "CREATE INDEX i6 ON claim(primary_icd10)",
                "CREATE UNIQUE INDEX i7 ON patient(patient_id)", "CREATE UNIQUE INDEX i8 ON plan(plan_id)", "CREATE UNIQUE INDEX i9 ON insurer(insurer_id)",
                "CREATE UNIQUE INDEX i10 ON hospital(hospital_id)", "CREATE UNIQUE INDEX i11 ON diagnosis_ref(icd10)", "CREATE INDEX i12 ON claim(submit_date)"]:
        b.execute(sql)
    b.commit(); b.close(); s.close()

AGE = "(julianday('2025-12-31')-julianday(p.birth_date))/365.25"
Q = {
"Q1": ("Monthly claims, billed and paid amount (roll-up to month)",
  """SELECT d.year, d.month, ROUND(SUM(f.claim_weight)) AS claims, ROUND(SUM(f.billed_amount),2) AS billed, ROUND(SUM(f.paid_amount),2) AS paid
     FROM fact_claim_line f JOIN dim_date d ON d.date_key=f.submit_date_key GROUP BY d.year, d.month ORDER BY 1,2""",
  """SELECT CAST(strftime('%Y',c.submit_date) AS INT), CAST(strftime('%m',c.submit_date) AS INT), COUNT(DISTINCT c.claim_id),
            ROUND(SUM(l.billed_amount),2), ROUND(SUM(l.paid_amount),2)
     FROM claim_line l JOIN claim c ON c.claim_id=l.claim_id GROUP BY 1,2 ORDER BY 1,2"""),
"Q2": ("Denial rate by insurer and year (slice and dice)",
  """SELECT i.insurer_name, d.year, ROUND(SUM(f.claim_weight)) AS claims,
            ROUND(SUM(CASE WHEN s.claim_status='Denied' THEN f.claim_weight END)) AS denied,
            ROUND(100.0*SUM(CASE WHEN s.claim_status='Denied' THEN f.claim_weight END)/SUM(CASE WHEN s.claim_status<>'Pending' THEN f.claim_weight END),2) AS denial_rate_pct
     FROM fact_claim_line f JOIN dim_insurer i ON i.insurer_key=f.insurer_key JOIN dim_date d ON d.date_key=f.submit_date_key
     JOIN dim_claim_status s ON s.claim_status_key=f.claim_status_key GROUP BY 1,2 ORDER BY 1,2""",
  """SELECT i.name, CAST(strftime('%Y',c.submit_date) AS INT), COUNT(*), SUM(c.status='Denied'),
            ROUND(100.0*SUM(c.status='Denied')/SUM(c.status<>'Pending'),2)
     FROM claim c JOIN plan pl ON pl.plan_id=c.plan_id JOIN insurer i ON i.insurer_id=pl.insurer_id
     WHERE EXISTS (SELECT 1 FROM claim_line l WHERE l.claim_id=c.claim_id) GROUP BY 1,2 ORDER BY 1,2"""),
"Q3": ("Top 10 diagnoses by insurer-paid amount",
  """SELECT g.icd10_code, g.description, ROUND(SUM(f.claim_weight)) AS claims, ROUND(SUM(f.paid_amount),2) AS paid,
            ROUND(SUM(f.paid_amount)/SUM(f.claim_weight),2) AS paid_per_claim
     FROM fact_claim_line f JOIN dim_diagnosis g ON g.diagnosis_key=f.diagnosis_key GROUP BY g.icd10_code ORDER BY paid DESC LIMIT 10""",
  """SELECT g.icd10, g.description, COUNT(DISTINCT c.claim_id), ROUND(SUM(l.paid_amount),2), ROUND(SUM(l.paid_amount)/COUNT(DISTINCT c.claim_id),2)
     FROM claim_line l JOIN claim c ON c.claim_id=l.claim_id JOIN diagnosis_ref g ON g.icd10=c.primary_icd10
     GROUP BY g.icd10 ORDER BY SUM(l.paid_amount) DESC LIMIT 10"""),
"Q4": ("Hospital by claim type: claims, avg processing days, settlement ratio",
  """SELECT h.hospital_name, s.claim_type, ROUND(SUM(f.claim_weight)) AS claims,
            ROUND(SUM(CASE WHEN f.processing_days IS NOT NULL THEN f.processing_days*f.claim_weight END)/SUM(CASE WHEN f.processing_days IS NOT NULL THEN f.claim_weight END),2) AS avg_days,
            ROUND(100.0*SUM(f.paid_amount)/SUM(f.billed_amount),2) AS settlement_pct
     FROM fact_claim_line f JOIN dim_hospital h ON h.hospital_key=f.hospital_key JOIN dim_claim_status s ON s.claim_status_key=f.claim_status_key
     GROUP BY 1,2 ORDER BY 1,2""",
  """SELECT h.name, c.claim_type, COUNT(*), ROUND(AVG(julianday(c.adjudication_date)-julianday(c.submit_date)),2), ROUND(100.0*SUM(t.paid)/SUM(t.billed),2)
     FROM claim c JOIN hospital h ON h.hospital_id=c.hospital_id
     JOIN (SELECT claim_id, SUM(billed_amount) billed, SUM(paid_amount) paid FROM claim_line GROUP BY claim_id) t ON t.claim_id=c.claim_id
     GROUP BY 1,2 ORDER BY 1,2"""),
"Q5": ("Utilisation by age band and gender",
  """SELECT p.age_band, p.gender, ROUND(SUM(f.claim_weight)) AS claims, ROUND(SUM(f.billed_amount)/SUM(f.claim_weight),2) AS billed_per_claim
     FROM fact_claim_line f JOIN dim_patient p ON p.patient_key=f.patient_key GROUP BY 1,2 ORDER BY 1,2""",
  f"""SELECT CASE WHEN {AGE}<18 THEN '0-17' WHEN {AGE}<35 THEN '18-34' WHEN {AGE}<50 THEN '35-49' WHEN {AGE}<65 THEN '50-64' ELSE '65+' END AS ab,
            p.gender, COUNT(DISTINCT c.claim_id), ROUND(SUM(l.billed_amount)/COUNT(DISTINCT c.claim_id),2)
     FROM claim_line l JOIN claim c ON c.claim_id=l.claim_id JOIN patient p ON p.patient_id=c.patient_id GROUP BY 1,2 ORDER BY 1,2"""),
"Q6": ("Denied amount by denial reason and insurer type",
  """SELECT s.denial_reason, i.insurer_type, ROUND(SUM(f.claim_weight)) AS claims, ROUND(SUM(f.denied_amount),2) AS denied_amount
     FROM fact_claim_line f JOIN dim_claim_status s ON s.claim_status_key=f.claim_status_key JOIN dim_insurer i ON i.insurer_key=f.insurer_key
     WHERE s.denial_reason<>'NA' GROUP BY 1,2 ORDER BY 1,2""",
  """SELECT c.denial_reason, i.insurer_type, COUNT(DISTINCT c.claim_id), ROUND(SUM(l.denied_amount),2)
     FROM claim_line l JOIN claim c ON c.claim_id=l.claim_id JOIN plan pl ON pl.plan_id=c.plan_id JOIN insurer i ON i.insurer_id=pl.insurer_id
     WHERE c.denial_reason<>'NA' GROUP BY 1,2 ORDER BY 1,2"""),
}
SNAP_Q1 = """SELECT month_key/100, month_key%100, ROUND(SUM(claim_count)), ROUND(SUM(billed_amount),2), ROUND(SUM(paid_amount),2)
             FROM fact_claim_monthly_snapshot GROUP BY month_key ORDER BY month_key"""

def conn(path):
    c = sqlite3.connect(path); c.execute("PRAGMA cache_size=-300000"); return c

def timed(c, sql, runs=7):
    c.execute(sql).fetchall()   # warm-up
    t = []
    for _ in range(runs):
        t0 = time.perf_counter(); rows = c.execute(sql).fetchall(); t.append((time.perf_counter() - t0) * 1000)
    return statistics.median(t), rows

def equal(a, b):
    if len(a) != len(b): return False
    for ra, rb in zip(a, b):
        for x, y in zip(ra, rb):
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                if abs((x or 0) - (y or 0)) > 0.011: return False
            elif x != y: return False
    return True

def run_all():
    build_baseline()
    dw, bs = conn(DW), conn(BASE)
    out = {"queries": {}, "timings": {}, "equal": {}}
    for k, (title, qd, qb) in Q.items():
        td, rd = timed(dw, qd); tb, rb = timed(bs, qb)
        cols = [d[0] for d in dw.execute(qd).description]
        out["queries"][k] = {"title": title, "columns": cols, "rows": rd}
        out["timings"][k] = {"3nf_ms": round(tb, 1), "star_ms": round(td, 1)}
        out["equal"][k] = equal(rd, rb)
    ts, rs = timed(dw, SNAP_Q1); out["timings"]["Q1_snapshot"] = {"star_ms": round(ts, 1)}
    out["equal"]["Q1_snapshot"] = equal(rs, out["queries"]["Q1"]["rows"])
    # SCD-2 demonstration
    hist = dw.execute("""SELECT p.city, ROUND(SUM(f.claim_weight)) FROM fact_claim_line f JOIN dim_patient p ON p.patient_key=f.patient_key
                         WHERE p.patient_id IN (SELECT patient_id FROM dim_patient WHERE version_no=2) GROUP BY p.city ORDER BY 2 DESC""").fetchall()
    curr = dw.execute("""SELECT p2.city, ROUND(SUM(f.claim_weight)) FROM fact_claim_line f JOIN dim_patient p ON p.patient_key=f.patient_key
                         JOIN dim_patient p2 ON p2.patient_id=p.patient_id AND p2.is_current=1
                         WHERE p.patient_id IN (SELECT patient_id FROM dim_patient WHERE version_no=2) GROUP BY p2.city ORDER BY 2 DESC""").fetchall()
    out["scd2"] = {"history_correct": hist, "current_state": curr}
    sizes = {t: dw.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in
             ["dim_date", "dim_patient", "dim_provider", "dim_hospital", "dim_diagnosis", "dim_procedure", "dim_insurer", "dim_plan", "dim_claim_status", "fact_claim_line", "fact_claim_monthly_snapshot", "dq_reject"]}
    sizes.update({"3nf_claim": bs.execute("SELECT COUNT(*) FROM claim").fetchone()[0], "3nf_claim_line": bs.execute("SELECT COUNT(*) FROM claim_line").fetchone()[0]})
    out["sizes"] = sizes
    out["files_mb"] = {"source_oltp": round(os.path.getsize(SRC) / 1e6, 1), "dw": round(os.path.getsize(DW) / 1e6, 1), "baseline_3nf": round(os.path.getsize(BASE) / 1e6, 1)}
    json.dump(out, open(os.path.join(RES, "olap_results.json"), "w"), indent=1, default=str)
    return out

if __name__ == "__main__":
    o = run_all()
    for k, v in o["timings"].items(): print(k, v, o["equal"].get(k))
    print(o["sizes"], o["files_mb"])
    print("SCD2 hist", o["scd2"]["history_correct"][:4]); print("SCD2 curr", o["scd2"]["current_state"][:4])
