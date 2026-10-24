"""ClaimsLens - Streamlit app for the hospital insurance-claims data warehouse.

Run locally:   py -3.13 -m streamlit run streamlit_app.py
Streamlit Community Cloud: deploy this file from the GitHub repository.

If the warehouse database (data/claims_dw.db) exists, the extra tabs
"Claim lookup" and "Run OLAP" query it live. Without it (for example on
Streamlit Cloud) the app uses the saved aggregates in app/data.json.
"""
import json
import os
import sqlite3
import sys
import time

import pandas as pd
import streamlit as st

ROOT = os.path.dirname(os.path.abspath(__file__))
DW = os.path.join(ROOT, "data", "claims_dw.db")
BASE = os.path.join(ROOT, "data", "baseline_3nf.db")
LIVE = os.path.exists(DW)
MN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

st.set_page_config(page_title="ClaimsLens", page_icon="🏥", layout="wide")


@st.cache_data
def load():
    with open(os.path.join(ROOT, "app", "data.json"), encoding="utf-8") as f:
        return json.load(f)


D = load()
CR = 1e7


def label(m):
    return f"{MN[m % 100 - 1]} {str(m // 100)[2:]}"


snap = pd.DataFrame(D["snap"], columns=["month", "ins", "hos", "claims", "billed", "allowed", "denied", "paid"])
snap["insurer"] = snap.ins.map(lambda i: D["insurers"][i])
snap["hospital"] = snap.hos.map(lambda i: D["hospitals"][i][0])

st.title("ClaimsLens")
st.caption("Hospital insurance-claims data warehouse: star schema, SCD Type 2, incremental ETL. "
           "All data is synthetic. Source: " + ("live SQLite warehouse" if LIVE else "saved warehouse aggregates"))

names = ["Overview", "Denials", "Patient history", "ETL and quality", "Warehouse model"]
if LIVE:
    names += ["Claim lookup", "Run OLAP"]
tabs = st.tabs(names)

# ---------------------------------------------------------------- Overview
with tabs[0]:
    c1, c2, c3, c4 = st.columns(4)
    ins = c1.selectbox("Insurer", ["All insurers"] + D["insurers"])
    hos = c2.selectbox("Hospital", ["All hospitals"] + [h[0] for h in D["hospitals"]])
    months = sorted(snap.month.unique())
    m1 = c3.selectbox("From", months, index=0, format_func=label)
    m2 = c4.selectbox("To", months, index=len(months) - 1, format_func=label)
    if m1 > m2:
        m1, m2 = m2, m1
    f = snap[(snap.month >= m1) & (snap.month <= m2)]
    if ins != "All insurers":
        f = f[f.insurer == ins]
    if hos != "All hospitals":
        f = f[f.hospital == hos]
    t = f[["claims", "billed", "paid", "denied"]].sum()
    k = st.columns(5)
    k[0].metric("Claims", f"{t.claims:,.0f}")
    k[1].metric("Billed", f"₹{t.billed / CR:,.1f} Cr")
    k[2].metric("Paid", f"₹{t.paid / CR:,.1f} Cr", f"{100 * t.paid / t.billed:.1f}% of billed" if t.billed else None, delta_color="off")
    k[3].metric("Denied", f"₹{t.denied / CR:,.1f} Cr", f"{100 * t.denied / t.billed:.1f}% of billed" if t.billed else None, delta_color="off")
    k[4].metric("Avg paid per claim", f"₹{(t.paid / t.claims if t.claims else 0):,.0f}")

    st.subheader("Monthly billed and paid (₹ crore)")
    tr = f.groupby("month")[["billed", "paid"]].sum().div(CR)
    tr.index = [label(m) for m in tr.index]
    st.bar_chart(tr, stack=False)

    a, b = st.columns(2)
    with a:
        st.subheader("Paid by insurer (₹ crore)")
        g = f.groupby("insurer")[["paid", "billed", "denied"]].sum()
        st.bar_chart(g.paid.div(CR).sort_values(), horizontal=True)
    with b:
        st.subheader("Paid by hospital (₹ crore)")
        g = f.groupby("hospital")[["paid", "billed", "denied"]].sum()
        st.bar_chart(g.paid.div(CR).sort_values(), horizontal=True)

    st.subheader("Billed by diagnosis category (₹ crore)")
    cat = pd.DataFrame(D["cat"], columns=["month", "category", "claims", "billed", "paid"])
    cat = cat[(cat.month >= m1) & (cat.month <= m2)].groupby("category").billed.sum().div(CR).sort_values()
    st.bar_chart(cat, horizontal=True)
    st.caption("The category chart reads the line-level fact table, so the insurer and hospital filters do not apply to it.")

# ---------------------------------------------------------------- Denials
with tabs[1]:
    stt = pd.DataFrame(D["status"], columns=["status", "reason", "claims", "billed"])
    a, b = st.columns(2)
    with a:
        st.subheader("Claim outcomes")
        o = stt.groupby("status").claims.sum()
        st.bar_chart(o.sort_values(), horizontal=True)
        st.dataframe((o / o.sum() * 100).round(1).rename("share %"), use_container_width=True)
    with b:
        st.subheader("Reasons for denial and part payment")
        r = stt[stt.reason != "NA"].set_index("reason").claims.sort_values()
        st.bar_chart(r, horizontal=True)
    st.subheader("Average days to adjudicate, by insurer")
    days = pd.Series({D["insurers"][i]: v for i, v in D["procDays"]})
    st.bar_chart(days.sort_values(), horizontal=True)

# ---------------------------------------------------------------- Patient history
with tabs[2]:
    st.subheader("Patient history (SCD Type 2)")
    st.write("When a patient's city, state or plan changes, the warehouse keeps the old row and adds a new version. "
             "Claims join to the version valid on the admission date.")
    scd = pd.DataFrame(D["scd"], columns=["patient", "version", "city", "state", "plan", "valid_from", "valid_to", "current"])
    pid = st.selectbox("Patient", sorted(scd.patient.unique()))
    st.dataframe(scd[scd.patient == pid].drop(columns="patient"), use_container_width=True, hide_index=True)
    st.subheader("Claims by city: history-correct against current address")
    h = pd.DataFrame(D["olap"]["scd2"]["history_correct"], columns=["city", "history-correct"]).set_index("city")
    c = pd.DataFrame(D["olap"]["scd2"]["current_state"], columns=["city", "current-address only"]).set_index("city")
    st.bar_chart(h.join(c), stack=False)

# ---------------------------------------------------------------- ETL
with tabs[3]:
    st.subheader("Load batches")
    st.dataframe(pd.DataFrame(D["audit"]), use_container_width=True, hide_index=True)
    st.subheader("Rejected records by rule")
    dq = pd.DataFrame(D["dq"], columns=["rule", "check", "rows"])
    st.bar_chart(dq.set_index("rule").rows)
    st.dataframe(dq, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- Model
with tabs[4]:
    st.subheader("Star schema")
    st.write("Grain: one claim service line. The date dimension plays three roles: service, submission and adjudication.")
    cnt = D["counts"]
    st.dataframe(pd.DataFrame({"table": list(cnt), "rows": list(cnt.values())}), use_container_width=True, hide_index=True)
    st.subheader("Star schema against normalised copy (milliseconds, median of 7 runs)")
    tm = D["olap"]["timings"]
    ttl = D["olap"]["queries"]
    rows = [{"query": f"{q} {ttl[q]['title'][:40]}", "Normalised (3NF)": tm[q]["3nf_ms"], "Star schema": tm[q]["star_ms"]}
            for q in ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"]]
    st.bar_chart(pd.DataFrame(rows).set_index("query"), stack=False)
    st.caption("Star is faster on Q1, Q3, Q5 and Q6. It is slower on Q2 and Q4, which count claims from line-level rows.")

# ---------------------------------------------------------------- Live tabs
if LIVE:
    sys.path.insert(0, os.path.join(ROOT, "src"))

    def db(path):
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        return c

    with tabs[5]:
        st.subheader("Find a claim")
        q = st.text_input("Claim number starts with", "CL00000").strip().upper()
        stat = st.selectbox("Status", ["Any", "Approved", "Partially Approved", "Denied", "Pending"])
        sql = ("SELECT f.claim_id, MIN(d.full_date) AS service_date, i.insurer_name, h.hospital_name, s.claim_status, "
               "COUNT(*) AS lines, ROUND(SUM(f.billed_amount),2) AS billed, ROUND(SUM(f.paid_amount),2) AS paid "
               "FROM fact_claim_line f JOIN dim_date d ON d.date_key=f.service_date_key "
               "JOIN dim_insurer i USING(insurer_key) JOIN dim_hospital h USING(hospital_key) "
               "JOIN dim_claim_status s USING(claim_status_key) WHERE f.claim_id LIKE ?")
        p = [q + "%"]
        if stat != "Any":
            sql += " AND s.claim_status=?"
            p.append(stat)
        sql += " GROUP BY f.claim_id ORDER BY f.claim_id LIMIT 25"
        found = pd.read_sql(sql, db(DW), params=p)
        st.dataframe(found, use_container_width=True, hide_index=True)
        if len(found):
            cid = st.selectbox("Open claim", found.claim_id)
            lines = pd.read_sql(
                """SELECT f.line_no, d.full_date AS service_date, g.icd10_code, g.description AS diagnosis,
                   pr.description AS procedure_name, pv.doctor_name, pl.plan_name, s.claim_status, s.denial_reason,
                   f.billed_amount, f.allowed_amount, f.denied_amount, f.paid_amount, f.processing_days,
                   pt.patient_id, pt.city, pt.plan_id, pt.version_no
                   FROM fact_claim_line f JOIN dim_date d ON d.date_key=f.service_date_key
                   JOIN dim_diagnosis g USING(diagnosis_key) JOIN dim_procedure pr USING(procedure_key)
                   JOIN dim_provider pv USING(provider_key) JOIN dim_plan pl USING(plan_key)
                   JOIN dim_claim_status s USING(claim_status_key) JOIN dim_patient pt USING(patient_key)
                   WHERE f.claim_id=? ORDER BY f.line_no""", db(DW), params=[cid])
            st.write("Claim lines joined across every dimension, with the patient version valid at admission.")
            st.dataframe(lines, use_container_width=True, hide_index=True)

    with tabs[6]:
        from olap import Q
        st.subheader("Run an OLAP query")
        qid = st.selectbox("Query", list(Q), format_func=lambda k: f"{k}: {Q[k][0]}")
        engine = st.radio("Run on", ["Star schema", "Normalised (3NF)"], horizontal=True)
        if st.button("Run"):
            sql = Q[qid][1] if engine == "Star schema" else Q[qid][2]
            con = db(DW if engine == "Star schema" else BASE)
            con.execute(sql).fetchall()
            ts = []
            for _ in range(3):
                t0 = time.perf_counter()
                cur = con.execute(sql)
                rows = cur.fetchall()
                ts.append((time.perf_counter() - t0) * 1000)
            st.metric("Time (median of 3)", f"{sorted(ts)[1]:.1f} ms", f"{len(rows)} rows", delta_color="off")
            st.code(" ".join(sql.split()), language="sql")
            st.dataframe(pd.DataFrame(rows, columns=[c[0] for c in cur.description]), use_container_width=True, hide_index=True)
