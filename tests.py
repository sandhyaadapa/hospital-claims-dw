"""Automated test cases for the warehouse (run after batch 1 and batch 2)."""
import os, json, shutil, sqlite3
import etl
from etl import DATA, SRC, DW
RES = os.path.join(DATA, "..", "results")

def q1(c, sql): return c.execute(sql).fetchone()[0]

def run():
    inj = json.load(open(os.path.join(DATA, "injected_defects.json")))
    ol = json.load(open(os.path.join(RES, "olap_results.json")))
    dw = sqlite3.connect(DW); dw.execute(f"ATTACH '{SRC}' AS src")
    T = []
    def add(i, desc, inp, exp, act, ok): T.append(dict(id=f"TC{i:02d}", desc=desc, input=inp, expected=str(exp), actual=str(act), status="Pass" if ok else "Fail"))
    VALID = "billed_amount>=0 AND paid_amount<=allowed_amount+0.005 AND service_date BETWEEN '2023-01-01' AND '2025-12-31'"
    e = q1(dw, f"SELECT COUNT(*) FROM src.src_claim_line WHERE {VALID}"); a = q1(dw, "SELECT COUNT(*) FROM fact_claim_line")
    add(1, "Row-count reconciliation", "Source lines passing DQ rules vs fact rows", f"{e:,}", f"{a:,}", e == a)
    e = q1(dw, f"SELECT ROUND(SUM(paid_amount),2) FROM src.src_claim_line WHERE {VALID}"); a = q1(dw, "SELECT ROUND(SUM(paid_amount),2) FROM fact_claim_line")
    add(2, "Paid-amount reconciliation", "SUM(paid) source vs fact", f"{e:,.2f}", f"{a:,.2f}", abs(e - a) < 0.5)
    fks = ["patient_key:dim_patient", "provider_key:dim_provider", "hospital_key:dim_hospital", "diagnosis_key:dim_diagnosis", "procedure_key:dim_procedure",
           "insurer_key:dim_insurer", "plan_key:dim_plan", "claim_status_key:dim_claim_status", "service_date_key:dim_date", "submit_date_key:dim_date", "adjudication_date_key:dim_date"]
    orphans = sum(q1(dw, f"SELECT COUNT(*) FROM fact_claim_line f LEFT JOIN {d} ON {d}.{(k if k.endswith('patient_key') or not k.endswith('date_key') else 'date_key')}=f.{k} WHERE {d}.{(k if not k.endswith('date_key') else 'date_key')} IS NULL")
                  for k, d in (x.split(':') for x in fks))
    add(3, "Referential integrity", "Orphan foreign keys across 11 fact-to-dimension links", 0, orphans, orphans == 0)
    e = q1(dw, f"SELECT COUNT(DISTINCT claim_id) FROM src.src_claim_line WHERE {VALID}"); a = q1(dw, "SELECT COUNT(DISTINCT claim_id) FROM fact_claim_line")
    add(4, "Duplicate claim headers removed", f"{inj['duplicate_claim_rows']} duplicate headers injected; distinct claims compared", f"{e:,}", f"{a:,}", e == a and q1(dw, "SELECT COUNT(*) FROM dq_reject WHERE rule_id='R1'") == inj["duplicate_claim_rows"])
    a = q1(dw, "SELECT COUNT(*) FROM dq_reject WHERE rule_id='R2'"); neg = q1(dw, "SELECT COUNT(*) FROM fact_claim_line WHERE billed_amount<0")
    add(5, "Negative billed amount rejected", f"{inj['lines_negative_billed']} negative lines injected", f"{inj['lines_negative_billed']} rejected, 0 in fact", f"{a} rejected, {neg} in fact", a == inj["lines_negative_billed"] and neg == 0)
    a = q1(dw, "SELECT COUNT(DISTINCT claim_id) FROM fact_claim_line WHERE diagnosis_key=-1"); e = inj["claims_missing_diagnosis"] + inj["claims_invalid_diagnosis"]
    add(6, "Missing / invalid diagnosis mapped to Unknown", "NULL and invalid ICD-10 codes injected", f"{e} claims on key -1", f"{a} claims on key -1", a == e)
    cur = q1(dw, "SELECT COUNT(*) FROM dim_patient WHERE is_current=1"); two = q1(dw, "SELECT COUNT(*) FROM dim_patient WHERE version_no=2")
    ov = q1(dw, "SELECT COUNT(*) FROM dim_patient a JOIN dim_patient b ON a.patient_id=b.patient_id AND a.version_no=1 AND b.version_no=2 AND a.effective_to>=b.effective_from")
    add(7, "SCD Type-2 versioning", f"{inj['patients_any_change']} patients changed city or plan", f"25,000 current rows; {inj['patients_any_change']} new versions; 0 overlaps", f"{cur:,} current rows; {two} new versions; {ov} overlaps", cur == 25000 and two == inj["patients_any_change"] and ov == 0)
    bad = q1(dw, """SELECT COUNT(*) FROM fact_claim_line f JOIN dim_patient p ON p.patient_key=f.patient_key
                    WHERE NOT EXISTS (SELECT 1 FROM src.src_claim c WHERE c.claim_id=f.claim_id AND c.admission_date BETWEEN p.effective_from AND p.effective_to)""")
    add(8, "Point-in-time dimension lookup", "Admission date must fall in the linked patient version's validity period", 0, bad, bad == 0)
    n = q1(dw, "SELECT COUNT(*) FROM dim_date WHERE date_key<>0"); span = q1(dw, "SELECT CAST(julianday(MAX(full_date))-julianday(MIN(full_date)) AS INT)+1 FROM dim_date WHERE date_key<>0")
    add(9, "Date dimension continuity", "Calendar 2022-01-01 to 2026-12-31 without gaps", f"{span:,} days", f"{n:,} rows", n == span == 1826)
    p1 = q1(dw, "SELECT ROUND(SUM(paid_amount),2) FROM fact_claim_line"); p2 = q1(dw, "SELECT ROUND(SUM(paid_amount),2) FROM fact_claim_monthly_snapshot")
    c1 = q1(dw, "SELECT COUNT(DISTINCT claim_id) FROM fact_claim_line"); c2 = q1(dw, "SELECT ROUND(SUM(claim_count)) FROM fact_claim_monthly_snapshot")
    add(10, "Snapshot fact reconciliation", "Monthly snapshot vs transaction fact (paid amount, claim count)", f"{p1:,.2f}; {c1:,}", f"{p2:,.2f}; {int(c2):,}", abs(p1 - p2) < 0.5 and c1 == int(c2))
    eq = [k for k, v in ol["equal"].items() if v]
    add(11, "Query-result equivalence", "Six OLAP queries run on 3NF copy and on star schema", "6 of 6 identical (+ snapshot)", f"{len([k for k in eq if k.startswith('Q') and k != 'Q1_snapshot'])} of 6 identical", all(ol["equal"].values()))
    a = q1(dw, """SELECT COUNT(DISTINCT f.claim_id) FROM fact_claim_line f JOIN dim_claim_status s ON s.claim_status_key=f.claim_status_key
                  JOIN src.src_claim c ON c.claim_id=f.claim_id WHERE s.claim_status='Pending' AND c.adjudication_date IS NOT NULL""")
    upd = q1(dw, "SELECT lines_updated FROM etl_audit WHERE batch_id=2")
    add(12, "Late-arriving adjudication update", f"{inj['claims_changed_between_batches']:,} claims pending in batch 1 adjudicated later", "0 stale Pending claims; lines updated in place", f"{a} stale; {upd:,} lines updated", a == 0 and upd > 0)
    # idempotent replay on a copy
    tmp = os.path.join(DATA, "replay.db"); shutil.copy(DW, tmp)
    c = sqlite3.connect(tmp); c.execute("UPDATE etl_audit SET watermark_out='2024-12-31' WHERE batch_id=2"); c.commit()
    pre = (q1(c, "SELECT COUNT(*) FROM fact_claim_line"), q1(c, "SELECT ROUND(SUM(paid_amount),2) FROM fact_claim_line")); c.close()
    etl.DW = tmp
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()): etl.run_batch(3, "2025-12-31", os.path.join(RES, "replay_log.txt"))
    c = sqlite3.connect(tmp)
    post = (q1(c, "SELECT COUNT(*) FROM fact_claim_line"), q1(c, "SELECT ROUND(SUM(paid_amount),2) FROM fact_claim_line")); ins = q1(c, "SELECT lines_inserted FROM etl_audit WHERE batch_id=3"); c.close(); os.remove(tmp)
    add(13, "Idempotent re-load (replay of batch 2)", "Watermark reset; batch 2 data loaded again", f"0 new rows; totals unchanged ({pre[0]:,})", f"{ins} new rows; totals {'unchanged' if pre == post else 'changed'} ({post[0]:,})", ins == 0 and pre == post)
    json.dump(T, open(os.path.join(RES, "test_results.json"), "w"), indent=1)
    for t in T: print(t["id"], t["status"], "|", t["desc"], "|", t["expected"], "|", t["actual"])

if __name__ == "__main__": run()
