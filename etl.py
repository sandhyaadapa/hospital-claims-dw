"""ETL pipeline: source OLTP -> staging -> data-quality gate -> dimensions (SCD1/SCD2) -> facts -> snapshot."""
import os, sys, json, time, sqlite3, datetime as dt
import numpy as np, pandas as pd
from refdata import *

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
SRC = os.path.join(DATA, "source_oltp.db")
DW = os.path.join(DATA, "claims_dw.db")
FAR = "9999-12-31"

DDL = """
CREATE TABLE IF NOT EXISTS dim_date(date_key INTEGER PRIMARY KEY, full_date TEXT, day_of_month INTEGER, day_name TEXT,
  week_of_year INTEGER, month INTEGER, month_name TEXT, quarter INTEGER, year INTEGER, fiscal_year TEXT, is_weekend INTEGER);
CREATE TABLE IF NOT EXISTS dim_patient(patient_key INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT, gender TEXT, birth_date TEXT,
  age_band TEXT, city TEXT, state TEXT, plan_id TEXT, effective_from TEXT, effective_to TEXT, is_current INTEGER, version_no INTEGER);
CREATE INDEX IF NOT EXISTS ix_dim_patient_patient_id ON dim_patient(patient_id);
CREATE TABLE IF NOT EXISTS dim_provider(provider_key INTEGER PRIMARY KEY AUTOINCREMENT, doctor_id TEXT UNIQUE, doctor_name TEXT, specialty TEXT);
CREATE TABLE IF NOT EXISTS dim_hospital(hospital_key INTEGER PRIMARY KEY AUTOINCREMENT, hospital_id TEXT UNIQUE, hospital_name TEXT, city TEXT, ownership TEXT, bed_count INTEGER);
CREATE TABLE IF NOT EXISTS dim_diagnosis(diagnosis_key INTEGER PRIMARY KEY, icd10_code TEXT UNIQUE, description TEXT, category TEXT, chronic_flag INTEGER);
CREATE TABLE IF NOT EXISTS dim_procedure(procedure_key INTEGER PRIMARY KEY AUTOINCREMENT, proc_code TEXT UNIQUE, description TEXT, proc_category TEXT);
CREATE TABLE IF NOT EXISTS dim_insurer(insurer_key INTEGER PRIMARY KEY AUTOINCREMENT, insurer_id TEXT UNIQUE, insurer_name TEXT, insurer_type TEXT);
CREATE TABLE IF NOT EXISTS dim_plan(plan_key INTEGER PRIMARY KEY AUTOINCREMENT, plan_id TEXT UNIQUE, plan_name TEXT, sum_insured INTEGER, copay_pct INTEGER);
CREATE TABLE IF NOT EXISTS dim_claim_status(claim_status_key INTEGER PRIMARY KEY AUTOINCREMENT, claim_status TEXT, denial_reason TEXT,
  claim_type TEXT, admission_type TEXT, UNIQUE(claim_status, denial_reason, claim_type, admission_type));
CREATE TABLE IF NOT EXISTS fact_claim_line(claim_line_key INTEGER PRIMARY KEY AUTOINCREMENT, claim_id TEXT, line_no INTEGER,
  service_date_key INTEGER, submit_date_key INTEGER, adjudication_date_key INTEGER,
  patient_key INTEGER, provider_key INTEGER, hospital_key INTEGER, diagnosis_key INTEGER, procedure_key INTEGER,
  insurer_key INTEGER, plan_key INTEGER, claim_status_key INTEGER,
  quantity INTEGER, billed_amount REAL, allowed_amount REAL, denied_amount REAL, copay_amount REAL, paid_amount REAL,
  processing_days INTEGER, claim_weight REAL, batch_id INTEGER, UNIQUE(claim_id, line_no));
CREATE TABLE IF NOT EXISTS fact_claim_monthly_snapshot(month_key INTEGER, insurer_key INTEGER, hospital_key INTEGER,
  claim_count REAL, line_count INTEGER, billed_amount REAL, allowed_amount REAL, denied_amount REAL, paid_amount REAL,
  PRIMARY KEY(month_key, insurer_key, hospital_key));
CREATE TABLE IF NOT EXISTS dq_reject(batch_id INTEGER, entity TEXT, record_id TEXT, rule_id TEXT, rule_text TEXT, action TEXT);
CREATE TABLE IF NOT EXISTS etl_audit(batch_id INTEGER PRIMARY KEY, as_of TEXT, started TEXT, finished TEXT, watermark_in TEXT, watermark_out TEXT,
  claims_extracted INTEGER, lines_extracted INTEGER, duplicates_removed INTEGER, lines_rejected INTEGER, lines_inserted INTEGER, lines_updated INTEGER,
  patient_versions_added INTEGER, seconds REAL);
"""
INDEXES = ["service_date_key", "submit_date_key", "patient_key", "provider_key", "hospital_key", "diagnosis_key",
           "procedure_key", "insurer_key", "plan_key", "claim_status_key"]
RULES = {
 "R1": "Duplicate claim header (same claim_id received twice) - keep first",
 "R2": "billed_amount must be >= 0",
 "R3": "paid_amount must not exceed allowed_amount",
 "R4": "service_date must lie within the warehouse calendar (2023-01-01 .. 2025-12-31)",
 "R5": "Claim line without a matching claim header",
 "R6": "Primary diagnosis missing or not in ICD-10 reference - mapped to 'Unknown' member",
}

class Log:
    def __init__(self, path): self.f = open(path, "a"); self.t0 = time.time()
    def __call__(self, msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"; print(line); self.f.write(line + "\n"); self.f.flush()

def age_band(birth, as_of):
    a = (pd.Timestamp(as_of) - pd.to_datetime(birth)).dt.days / 365.25
    return pd.cut(a, [-1, 17.999, 34.999, 49.999, 64.999, 200], labels=["0-17", "18-34", "35-49", "50-64", "65+"]).astype(str)

def load_dim_date(con):
    if con.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0]: return 0
    d = pd.date_range("2022-01-01", "2026-12-31")
    df = pd.DataFrame({"date_key": d.strftime("%Y%m%d").astype(int), "full_date": d.strftime("%Y-%m-%d"), "day_of_month": d.day,
                       "day_name": d.day_name(), "week_of_year": d.isocalendar().week.astype(int).values, "month": d.month,
                       "month_name": d.month_name(), "quarter": d.quarter, "year": d.year,
                       "fiscal_year": np.where(d.month >= 4, "FY" + d.year.astype(str) + "-" + (d.year + 1).astype(str).str[-2:],
                                               "FY" + (d.year - 1).astype(str) + "-" + d.year.astype(str).str[-2:]),
                       "is_weekend": (d.dayofweek >= 5).astype(int)})
    unk = pd.DataFrame([{"date_key": 0, "full_date": "N/A", "day_of_month": 0, "day_name": "N/A", "week_of_year": 0, "month": 0,
                         "month_name": "N/A", "quarter": 0, "year": 0, "fiscal_year": "N/A", "is_weekend": 0}])
    pd.concat([unk, df]).to_sql("dim_date", con, if_exists="append", index=False)
    return len(df) + 1

def upsert_scd1(con, table, nk, df):
    """Type-1 dimension: insert new natural keys, overwrite changed attributes. Returns (inserted, updated)."""
    cur = pd.read_sql(f"SELECT * FROM {table}", con).drop(columns=[c for c in [table.replace('dim_', '') + '_key'] if c in pd.read_sql(f'SELECT * FROM {table} LIMIT 0', con).columns])
    cols = [c for c in df.columns if c != nk]
    merged = df.merge(cur[[nk] + cols], on=nk, how="left", suffixes=("", "_old"), indicator=True)
    new = merged[merged["_merge"] == "left_only"][df.columns]
    if len(new): new.to_sql(table, con, if_exists="append", index=False)
    both = merged[merged["_merge"] == "both"]
    chg = both[(both[cols].astype(str).values != both[[c + "_old" for c in cols]].astype(str).values).any(axis=1)]
    for r in chg.itertuples(index=False):
        d = r._asdict()
        con.execute(f"UPDATE {table} SET " + ",".join(f"{c}=?" for c in cols) + f" WHERE {nk}=?", [d[c] for c in cols] + [d[nk]])
    return len(new), len(chg)

def scd2_patient(con, P, as_of):
    """Type-2 dimension for tracked attributes city / state / plan_id."""
    cur = pd.read_sql("SELECT * FROM dim_patient WHERE is_current=1", con)
    P = P.copy(); P["age_band"] = age_band(P.birth_date, as_of)
    m = P.merge(cur[["patient_key", "patient_id", "city", "state", "plan_id", "version_no"]], on="patient_id", how="left", suffixes=("", "_cur"))
    new = m[m.patient_key.isna()]
    chg = m[m.patient_key.notna() & ((m.city != m.city_cur) | (m.state != m.state_cur) | (m.plan_id != m.plan_id_cur))]
    ins = pd.DataFrame({"patient_id": new.patient_id, "gender": new.gender, "birth_date": new.birth_date, "age_band": new.age_band,
                        "city": new.city, "state": new.state, "plan_id": new.plan_id, "effective_from": "2022-01-01",
                        "effective_to": FAR, "is_current": 1, "version_no": 1})
    for r in chg.itertuples():   # expire old version, open a new one
        eff = dt.date.fromisoformat(r.profile_updated_on)
        con.execute("UPDATE dim_patient SET effective_to=?, is_current=0 WHERE patient_key=?", ((eff - dt.timedelta(days=1)).isoformat(), int(r.patient_key)))
    ins2 = pd.DataFrame({"patient_id": chg.patient_id, "gender": chg.gender, "birth_date": chg.birth_date, "age_band": chg.age_band,
                         "city": chg.city, "state": chg.state, "plan_id": chg.plan_id, "effective_from": chg.profile_updated_on,
                         "effective_to": FAR, "is_current": 1, "version_no": chg.version_no.astype(int) + 1})
    pd.concat([ins, ins2]).to_sql("dim_patient", con, if_exists="append", index=False)
    # Type-1 refresh of the derived age band on every version
    ab = P.set_index("patient_id").age_band.to_dict()
    con.executemany("UPDATE dim_patient SET age_band=? WHERE patient_id=?", [(v, k) for k, v in ab.items()])
    return len(ins) + len(ins2)

def run_batch(batch_id, as_of, logf):
    log = Log(logf); t0 = time.time(); started = time.strftime("%Y-%m-%d %H:%M:%S")
    src = sqlite3.connect(SRC); dw = sqlite3.connect(DW); dw.executescript(DDL)
    log(f"===== ETL batch {batch_id}  (business date {as_of}) =====")
    wm = dw.execute("SELECT COALESCE(MAX(watermark_out),'1900-01-01') FROM etl_audit").fetchone()[0]
    # ---------------- EXTRACT
    ts = time.time()
    C = pd.read_sql("SELECT * FROM src_claim WHERE last_updated > ?", src, params=[wm])
    L = pd.read_sql("SELECT * FROM src_claim_line WHERE last_updated > ?", src, params=[wm])
    ref = {t: pd.read_sql(f"SELECT * FROM {t}", src) for t in ["src_insurer", "src_plan", "src_hospital", "src_doctor", "src_diagnosis_ref", "src_procedure_ref", "src_patient"]}
    wm_out = max(C.last_updated.max(), L.last_updated.max()) if len(C) else wm
    log(f"EXTRACT   watermark {wm} -> {wm_out}: {len(C):,} claim rows, {len(L):,} line rows, {len(ref['src_patient']):,} patients  ({time.time()-ts:.1f}s)")
    # ---------------- TRANSFORM / DQ
    ts = time.time(); rej = []
    dup = C.duplicated("claim_id", keep="first"); n_dup = int(dup.sum())
    rej += [(batch_id, "claim", i, "R1", RULES["R1"], "removed") for i in C.claim_id[dup]]
    C = C[~dup].copy()
    bad = L.billed_amount < 0
    rej += [(batch_id, "claim_line", f"{a}/{b}", "R2", RULES["R2"], "rejected") for a, b in zip(L.claim_id[bad], L.line_no[bad])]
    bad3 = (~bad) & (L.paid_amount > L.allowed_amount + 0.005)
    rej += [(batch_id, "claim_line", f"{a}/{b}", "R3", RULES["R3"], "rejected") for a, b in zip(L.claim_id[bad3], L.line_no[bad3])]
    sd = pd.to_datetime(L.service_date)
    bad4 = (~bad) & (~bad3) & ((sd < "2023-01-01") | (sd > "2025-12-31"))
    rej += [(batch_id, "claim_line", f"{a}/{b}", "R4", RULES["R4"], "rejected") for a, b in zip(L.claim_id[bad4], L.line_no[bad4])]
    bad5 = (~bad) & (~bad3) & (~bad4) & (~L.claim_id.isin(C.claim_id))
    rej += [(batch_id, "claim_line", f"{a}/{b}", "R5", RULES["R5"], "rejected") for a, b in zip(L.claim_id[bad5], L.line_no[bad5])]
    n_rej = int((bad | bad3 | bad4 | bad5).sum())
    L = L[~(bad | bad3 | bad4 | bad5)].copy()
    valid_dx = set(ref["src_diagnosis_ref"].icd10)
    udx = ~C.primary_icd10.isin(valid_dx)
    rej += [(batch_id, "claim", i, "R6", RULES["R6"], "mapped to Unknown") for i in C.claim_id[udx]]
    C.loc[udx, "primary_icd10"] = "UNK"
    pd.DataFrame(rej, columns=["batch_id", "entity", "record_id", "rule_id", "rule_text", "action"]).to_sql("dq_reject", dw, if_exists="append", index=False)
    log(f"TRANSFORM data-quality gate: {n_dup} duplicate headers removed, {n_rej} lines rejected "
        f"(R2={int(bad.sum())}, R3={int(bad3.sum())}, R4={int(bad4.sum())}, R5={int(bad5.sum())}), {int(udx.sum())} claims mapped to Unknown diagnosis  ({time.time()-ts:.1f}s)")
    # ---------------- DIMENSIONS
    ts = time.time()
    s = ref
    r = {}
    r["dim_hospital"] = upsert_scd1(dw, "dim_hospital", "hospital_id", s["src_hospital"].rename(columns={"name": "hospital_name", "beds": "bed_count"})[["hospital_id", "hospital_name", "city", "ownership", "bed_count"]])
    r["dim_provider"] = upsert_scd1(dw, "dim_provider", "doctor_id", s["src_doctor"].rename(columns={"name": "doctor_name"})[["doctor_id", "doctor_name", "specialty"]])
    dx = s["src_diagnosis_ref"].rename(columns={"icd10": "icd10_code"})
    r["dim_diagnosis"] = upsert_scd1(dw, "dim_diagnosis", "icd10_code", dx[["icd10_code", "description", "category", "chronic_flag"]])
    dw.execute("INSERT OR IGNORE INTO dim_diagnosis(diagnosis_key,icd10_code,description,category,chronic_flag) VALUES(-1,'UNK','Unknown / not recorded','Unknown',0)")
    r["dim_procedure"] = upsert_scd1(dw, "dim_procedure", "proc_code", s["src_procedure_ref"][["proc_code", "description", "proc_category"]])
    r["dim_insurer"] = upsert_scd1(dw, "dim_insurer", "insurer_id", s["src_insurer"].rename(columns={"name": "insurer_name"})[["insurer_id", "insurer_name", "insurer_type"]])
    r["dim_plan"] = upsert_scd1(dw, "dim_plan", "plan_id", s["src_plan"][["plan_id", "plan_name", "sum_insured", "copay_pct"]])
    nd = load_dim_date(dw)
    P = s["src_patient"][["patient_id", "gender", "birth_date", "city", "state", "plan_id", "profile_updated_on"]]
    nv = scd2_patient(dw, P, as_of)
    st = C.assign(claim_status=C.status)[["claim_status", "denial_reason", "claim_type", "admission_type"]].drop_duplicates()
    ex = pd.read_sql("SELECT claim_status,denial_reason,claim_type,admission_type FROM dim_claim_status", dw)
    stn = st.merge(ex, how="left", indicator=True).query("_merge=='left_only'")[st.columns]
    if len(stn): stn.to_sql("dim_claim_status", dw, if_exists="append", index=False)
    dw.commit()
    log(f"DIMENSIONS dim_date +{nd}, hospital/provider/diagnosis/procedure/insurer/plan (SCD-1) new={sum(v[0] for v in r.values())} changed={sum(v[1] for v in r.values())}, "
        f"dim_patient (SCD-2) +{nv} versions, dim_claim_status +{len(stn)}  ({time.time()-ts:.1f}s)")
    # ---------------- FACT
    ts = time.time()
    key = {t: pd.read_sql(f"SELECT * FROM {t}", dw) for t in ["dim_provider", "dim_hospital", "dim_diagnosis", "dim_procedure", "dim_insurer", "dim_plan", "dim_claim_status"]}
    plan_ins = s["src_plan"][["plan_id", "insurer_id"]]
    F = L.merge(C, on="claim_id", suffixes=("", "_c"))
    F = F.merge(plan_ins, on="plan_id", how="left")
    F = F.merge(key["dim_provider"][["doctor_id", "provider_key"]], on="doctor_id", how="left")
    F = F.merge(key["dim_hospital"][["hospital_id", "hospital_key"]], on="hospital_id", how="left")
    F = F.merge(key["dim_diagnosis"][["icd10_code", "diagnosis_key"]].rename(columns={"icd10_code": "primary_icd10"}), on="primary_icd10", how="left")
    F = F.merge(key["dim_procedure"][["proc_code", "procedure_key"]], on="proc_code", how="left")
    F = F.merge(key["dim_insurer"][["insurer_id", "insurer_key"]], on="insurer_id", how="left")
    F = F.merge(key["dim_plan"][["plan_id", "plan_key"]], on="plan_id", how="left")
    F = F.merge(key["dim_claim_status"].rename(columns={"claim_status": "status"}), on=["status", "denial_reason", "claim_type", "admission_type"], how="left")
    pv = pd.read_sql("SELECT patient_key, patient_id, effective_from, effective_to FROM dim_patient", dw)
    F = F.merge(pv, on="patient_id", how="left")
    F = F[(F.admission_date >= F.effective_from) & (F.admission_date <= F.effective_to)].copy()   # point-in-time lookup
    dk = lambda col: pd.to_datetime(F[col]).dt.strftime("%Y%m%d").astype(float).fillna(0).astype(int)
    F["service_date_key"], F["submit_date_key"], F["adjudication_date_key"] = dk("service_date"), dk("submit_date"), dk("adjudication_date")
    F["processing_days"] = (pd.to_datetime(F.adjudication_date) - pd.to_datetime(F.submit_date)).dt.days
    F["claim_weight"] = 1.0 / F.groupby("claim_id").claim_id.transform("size")
    F["batch_id"] = batch_id
    assert F[["patient_key", "provider_key", "hospital_key", "diagnosis_key", "procedure_key", "insurer_key", "plan_key", "claim_status_key"]].notna().all().all()
    cols = ["claim_id", "line_no", "service_date_key", "submit_date_key", "adjudication_date_key", "patient_key", "provider_key", "hospital_key",
            "diagnosis_key", "procedure_key", "insurer_key", "plan_key", "claim_status_key", "quantity", "billed_amount", "allowed_amount",
            "denied_amount", "copay_amount", "paid_amount", "processing_days", "claim_weight", "batch_id"]
    F = F[cols]
    existing = set(map(tuple, pd.read_sql("SELECT claim_id, line_no FROM fact_claim_line", dw).values))
    is_upd = np.array([(a, int(b)) in existing for a, b in zip(F.claim_id, F.line_no)])
    n_upd, n_ins = int(is_upd.sum()), int((~is_upd).sum())
    upd = ",".join(f"{c}=excluded.{c}" for c in cols[2:])
    dw.executemany(f"INSERT INTO fact_claim_line({','.join(cols)}) VALUES({','.join('?'*len(cols))}) ON CONFLICT(claim_id,line_no) DO UPDATE SET {upd}",
                   [tuple(None if (isinstance(v, float) and np.isnan(v)) else (v.item() if hasattr(v, 'item') else v) for v in row) for row in F.itertuples(index=False)])
    dw.commit()
    log(f"FACT      fact_claim_line: {n_ins:,} inserted, {n_upd:,} updated (late-arriving adjudication)  ({time.time()-ts:.1f}s)")
    # ---------------- INDEXES + SNAPSHOT
    ts = time.time()
    for c in INDEXES: dw.execute(f"CREATE INDEX IF NOT EXISTS ix_fact_{c} ON fact_claim_line({c})")
    for t, c in [("dim_patient", "patient_id"), ("dim_date", "year, month")]: dw.execute(f"CREATE INDEX IF NOT EXISTS ix_{t}_{c.split(',')[0]} ON {t}({c})")
    dw.execute("DELETE FROM fact_claim_monthly_snapshot")
    dw.execute("""INSERT INTO fact_claim_monthly_snapshot
      SELECT (d.year*100+d.month), f.insurer_key, f.hospital_key, SUM(f.claim_weight), COUNT(*), SUM(f.billed_amount), SUM(f.allowed_amount), SUM(f.denied_amount), SUM(f.paid_amount)
      FROM fact_claim_line f JOIN dim_date d ON d.date_key=f.submit_date_key GROUP BY 1,2,3""")
    dw.commit()
    nsnap = dw.execute("SELECT COUNT(*) FROM fact_claim_monthly_snapshot").fetchone()[0]
    log(f"SNAPSHOT  fact_claim_monthly_snapshot rebuilt: {nsnap:,} rows; indexes created  ({time.time()-ts:.1f}s)")
    secs = time.time() - t0
    dw.execute("INSERT INTO etl_audit VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (batch_id, as_of, started, time.strftime("%Y-%m-%d %H:%M:%S"), wm, wm_out,
               len(C) + n_dup, len(L) + n_rej, n_dup, n_rej, n_ins, n_upd, nv, round(secs, 2)))
    dw.commit()
    log(f"BATCH {batch_id} COMPLETE in {secs:.1f}s  (rows in fact: {dw.execute('SELECT COUNT(*) FROM fact_claim_line').fetchone()[0]:,})")
    return dict(batch=batch_id, secs=secs)

if __name__ == "__main__":
    b = int(sys.argv[1]); src_db = sys.argv[2] if len(sys.argv) > 2 else SRC
    SRC = src_db
    run_batch(b, "2024-12-31" if b == 1 else "2025-12-31", os.path.join(DATA, "..", "results", "etl_log.txt"))
