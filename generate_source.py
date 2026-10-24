"""Synthetic hospital billing / claims OLTP source system (normalized, 3NF).
Creates data/source_oltp.db after batch 1 and applies batch 2 on demand."""
import os, sys, json, sqlite3, datetime as dt
import numpy as np, pandas as pd
from refdata import *

SEED = 2026
N_PATIENTS, N_CLAIMS = 25000, 100000
DATA = os.path.join(os.path.dirname(__file__), "..", "data")
SRC = os.path.join(DATA, "source_oltp.db")

DDL = """
CREATE TABLE src_insurer(insurer_id TEXT, name TEXT, insurer_type TEXT);
CREATE TABLE src_plan(plan_id TEXT, insurer_id TEXT, plan_name TEXT, sum_insured INTEGER, copay_pct INTEGER);
CREATE TABLE src_hospital(hospital_id TEXT, name TEXT, city TEXT, ownership TEXT, beds INTEGER);
CREATE TABLE src_doctor(doctor_id TEXT, name TEXT, specialty TEXT, hospital_id TEXT);
CREATE TABLE src_diagnosis_ref(icd10 TEXT, description TEXT, category TEXT, chronic_flag INTEGER);
CREATE TABLE src_procedure_ref(proc_code TEXT, description TEXT, proc_category TEXT);
CREATE TABLE src_patient(patient_id TEXT, name TEXT, gender TEXT, birth_date TEXT, city TEXT, state TEXT,
                         plan_id TEXT, policy_no TEXT, profile_updated_on TEXT, last_updated TEXT);
CREATE TABLE src_claim(claim_id TEXT, patient_id TEXT, hospital_id TEXT, doctor_id TEXT, plan_id TEXT,
                       admission_date TEXT, discharge_date TEXT, submit_date TEXT, adjudication_date TEXT,
                       claim_type TEXT, admission_type TEXT, primary_icd10 TEXT, status TEXT, denial_reason TEXT,
                       last_updated TEXT);
CREATE TABLE src_claim_line(claim_id TEXT, line_no INTEGER, proc_code TEXT, service_date TEXT, quantity INTEGER,
                            billed_amount REAL, allowed_amount REAL, denied_amount REAL, copay_amount REAL,
                            paid_amount REAL, last_updated TEXT);
"""

def _names(rng, n, gender):
    f = FIRST_M if gender == "M" else FIRST_F
    return [f"{f[i]} {LAST[j]}" for i, j in zip(rng.integers(0, len(f), n), rng.integers(0, len(LAST), n))]

def build_truth(rng):
    """Create the complete 'ground truth' tables (final state at CUT2) and the injected-defect log."""
    # ---- reference data
    ins = pd.DataFrame(INSURERS, columns=["insurer_id", "name", "insurer_type", "dmult", "lag", "tariff"])
    plans = []
    for i, r in ins.iterrows():
        for t, (tn, si, cp) in enumerate(TIERS):
            plans.append((f"P{i*3+t+1:02d}", r.insurer_id, f"{r['name'].split()[0]} {tn}", si, cp))
    plans = pd.DataFrame(plans, columns=["plan_id", "insurer_id", "plan_name", "sum_insured", "copay_pct"])
    hosp = pd.DataFrame(HOSPITALS, columns=["hospital_id", "name", "city", "ownership", "beds", "mult"])
    docs = []
    d = 1
    for h in hosp.hospital_id:
        for sp in SPECIALTIES:
            for k in range(int(rng.integers(1, 3))):
                g = "M" if rng.random() < .6 else "F"
                docs.append((f"D{d:03d}", "Dr. " + _names(rng, 1, g)[0], sp, h)); d += 1
    docs = pd.DataFrame(docs, columns=["doctor_id", "name", "specialty", "hospital_id"])
    dxref = pd.DataFrame([(x[0], x[1], x[2], x[3]) for x in DX], columns=["icd10", "description", "category", "chronic_flag"])
    prref = pd.DataFrame([(PROC_CODE[k], v[0], v[1]) for k, v in PROCS.items()], columns=["proc_code", "description", "proc_category"])

    # ---- patients
    n = N_PATIENTS
    gender = np.where(rng.random(n) < .52, "M", "F")
    age = np.clip(rng.gamma(4.2, 11.5, n), 0, 92).astype(int)
    dob = [dt.date(2025, 6, 30) - dt.timedelta(days=int(a * 365.25 + rng.integers(0, 365))) for a in age]
    cw = np.array([c[2] for c in CITIES], float); cw /= cw.sum()
    ci = rng.choice(len(CITIES), n, p=cw)
    pw = np.array([3, 3, 1.5] * 6, float); pw /= pw.sum()  # basic/standard/premium by insurer weights
    iw = np.array([20, 16, 14, 12, 22, 16], float)
    p_ins = rng.choice(6, n, p=iw / iw.sum()); p_tier = rng.choice(3, n, p=[.45, .38, .17])
    plan0 = [f"P{i*3+t+1:02d}" for i, t in zip(p_ins, p_tier)]
    pat = pd.DataFrame({
        "patient_id": [f"PT{i+1:06d}" for i in range(n)],
        "name": ["" for _ in range(n)], "gender": gender, "birth_date": [x.isoformat() for x in dob],
        "city": [CITIES[i][0] for i in ci], "state": [CITIES[i][1] for i in ci],
        "plan_id": plan0, "policy_no": [f"POL{rng.integers(10**8, 10**9)}" for _ in range(n)]})
    for g in "MF":
        m = pat.gender == g; pat.loc[m, "name"] = _names(rng, int(m.sum()), g)
    pat["age"] = age
    pat["profile_updated_on"] = [(DATA_START - dt.timedelta(days=int(x))).isoformat() for x in rng.integers(30, 1500, n)]
    # changes effective 2025-01-01 (applied in batch 2)
    chg_plan = rng.random(n) < .06; chg_city = (rng.random(n) < .04)
    new_plan = pat.plan_id.copy(); new_city = pat.city.copy(); new_state = pat.state.copy()
    for i in np.where(chg_plan)[0]:
        t = int(rng.integers(0, 3)); k = int(rng.choice([j for j in range(6) if j != p_ins[i]]))
        new_plan.iloc[i] = f"P{k*3+t+1:02d}"
    for i in np.where(chg_city)[0]:
        j = int(rng.choice([k for k in range(len(CITIES)) if CITIES[k][0] != pat.city.iloc[i]]))
        new_city.iloc[i], new_state.iloc[i] = CITIES[j][0], CITIES[j][1]
    chg = pd.DataFrame({"patient_id": pat.patient_id, "plan_id": new_plan, "city": new_city, "state": new_state,
                        "changed": chg_plan | chg_city})

    # ---- claims
    days = pd.date_range(DATA_START, LAST_ADMISSION)
    yw = {2023: .30, 2024: .33, 2025: .37}
    dxw = np.array([x[4] for x in DX]); dxw = dxw / dxw.sum()
    cnt = rng.multinomial(N_CLAIMS, dxw)
    hw = np.array([1.2, 1.5, 1.7, 1.0, .7, .9, 1.1, 1.3]); hw /= hw.sum()
    ins_ix = {r.insurer_id: r for r in ins.itertuples()}
    plan_ix = plans.set_index("plan_id")
    claims, lines = [], []
    cid = 0
    U = rng.random((N_CLAIMS, 64)); up = 0
    pat_idx_all = np.arange(n)
    for dxi, x in enumerate(DX):
        (code, desc, chap, chronic, w, spec, (amin, amax), sex, (lmin, lmax), pem, pdc, season, dm, extras) = x
        k = cnt[dxi]
        if k == 0: continue
        elig = pat_idx_all[(pat.age.values >= amin) & (pat.age.values <= amax) & ((pat.gender.values == sex) if sex else True)]
        pidx = rng.choice(elig, k)
        dw = np.array([yw[d.year] * SEASON[season][d.month - 1] for d in days]); dw /= dw.sum()
        adm = days[rng.choice(len(days), k, p=dw)]
        hs = rng.choice(len(hosp), k, p=hw)
        for j in range(k):
            r = U[up]; up += 1; q = 0
            cid += 1; claim_id = f"CL{cid:07d}"
            pi = pidx[j]; p = pat.iloc[pi]
            h = hosp.iloc[hs[j]]
            sp_docs = docs[(docs.hospital_id == h.hospital_id) & (docs.specialty == spec)].doctor_id.values
            doc = sp_docs[int(r[q] * len(sp_docs))]; q += 1
            los = int(lmin + r[q] * (lmax - lmin + 1)); q += 1
            u = r[q]; q += 1
            atype = "Emergency" if u < pem else ("Day-care" if u < pem + pdc else "Planned")
            if atype == "Day-care": los = 1
            a = adm[j].date(); disc = a + dt.timedelta(days=los if atype != "Day-care" else 0)
            sub = min(disc + dt.timedelta(days=int(r[q] * 8)), CUT2); q += 1
            ctype = "Cashless" if r[q] < .62 else "Reimbursement"; q += 1
            plan_id = p.plan_id if a < dt.date(2025, 1, 1) else chg.plan_id.iloc[pi]
            pl = plan_ix.loc[plan_id]; I = ins_ix[pl.insurer_id]
            # final adjudication outcome
            dp = min(.07 * I.dmult * dm * (1.35 if ctype == "Reimbursement" else 1.0), .6)
            u = r[q]; q += 1
            if u < dp: status = "Denied"
            elif u < dp + .11: status = "Partially Approved"
            else: status = "Approved"
            lagm = I.lag * (0.6 if ctype == "Cashless" else 1.2)
            lag = max(1, int(round(rng.gamma(4.0, lagm / 4.0))))
            adj = sub + dt.timedelta(days=lag)
            reason = "NA"
            if status == "Denied": reason = rng.choice(DENIAL_REASONS[0], p=DENIAL_REASONS[1])
            if status == "Partially Approved": reason = rng.choice(PARTIAL_REASONS[0], p=PARTIAL_REASONS[1])
            claims.append([claim_id, p.patient_id, h.hospital_id, doc, plan_id, a, disc, sub, adj, ctype, atype, code, status, reason])
            # lines
            ln = 0
            def add(proc, qty, sdate):
                nonlocal ln, q
                ln += 1
                unit = PROCS[proc][2] * h.mult * float(np.exp(rng.normal(0, .10)))
                billed = round(unit * qty, 2)
                allowed = round(billed * I.tariff, 2)
                lines.append([claim_id, ln, PROC_CODE[proc], sdate, qty, billed, allowed])
            add("ROOM", max(los, 1) if atype != "Day-care" else 1, a)
            add("CONS", int(1 + r[q % 60] * min(los, 3)), a + dt.timedelta(days=int(r[(q + 1) % 60] * (los - 1 if los > 1 else 0)))); q += 2
            for (proc, pr, qa, qb) in extras:
                if rng.random() < pr:
                    qty = int(rng.integers(qa, qb + 1))
                    add(proc, qty, a + dt.timedelta(days=int(rng.integers(0, max(los, 1)))))
    C = pd.DataFrame(claims, columns=["claim_id", "patient_id", "hospital_id", "doctor_id", "plan_id", "admission_date", "discharge_date",
                                      "submit_date", "adjudication_date", "claim_type", "admission_type", "primary_icd10", "status", "denial_reason"])
    L = pd.DataFrame(lines, columns=["claim_id", "line_no", "proc_code", "service_date", "quantity", "billed_amount", "allowed_amount"])
    # outcome amounts per line (final)
    st = C.set_index("claim_id")
    copay = plans.set_index("plan_id").copay_pct
    cp = st.plan_id.map(copay) / 100.0
    s = L.claim_id.map(st.status)
    frac = pd.Series(0.0, index=L.index)
    frac[s == "Denied"] = 1.0
    pm = s == "Partially Approved"
    frac[pm] = np.round(rng.uniform(.10, .40, int(pm.sum())), 3)
    L["denied_amount"] = (L.allowed_amount * frac).round(2)
    L["copay_amount"] = ((L.allowed_amount - L.denied_amount) * L.claim_id.map(cp)).round(2)
    L["paid_amount"] = (L.allowed_amount - L.denied_amount - L.copay_amount).round(2)

    # ---- changed claims between batch 1 and batch 2 (submitted <=CUT1 but adjudicated >CUT1)
    changed = (C.submit_date <= CUT1) & (C.adjudication_date > CUT1) & (C.adjudication_date <= CUT2)
    pending2 = C.adjudication_date > CUT2
    # ---- inject data-quality defects (never on claims whose state changes between batches)
    inj = {}
    elig_claims = C.index[~changed & ~pending2]
    pick = lambda idx, frac_: rng.choice(idx, int(len(idx) * frac_), replace=False)
    ix = pick(C.index, .004); C.loc[ix, "primary_icd10"] = None; inj["claims_missing_diagnosis"] = len(ix)
    ix2 = pick(C.index.difference(ix), .003); C.loc[ix2, "primary_icd10"] = "ZZ99.9"; inj["claims_invalid_diagnosis"] = len(ix2)
    # defects on lines
    ok_lines = L.index[L.claim_id.isin(C.claim_id[elig_claims])]
    ixn = pick(ok_lines, .0015); L.loc[ixn, "billed_amount"] = -L.loc[ixn, "billed_amount"]; inj["lines_negative_billed"] = len(ixn)
    rest = pd.Index(ok_lines).difference(ixn)
    ixp = pick(rest[L.loc[rest, "paid_amount"] > 0], .0)  # placeholder
    cand = rest[L.loc[rest, "paid_amount"] > 0]
    ixp = rng.choice(cand, int(len(ok_lines) * .002), replace=False)
    L.loc[ixp, "paid_amount"] = (L.loc[ixp, "allowed_amount"] * 1.5 + 100).round(2); inj["lines_paid_exceeds_allowed"] = len(ixp)
    rest2 = pd.Index(rest).difference(ixp)
    ixd = rng.choice(rest2, int(len(ok_lines) * .001), replace=False)
    L["service_date"] = L.service_date.astype(object)
    L.loc[ixd, "service_date"] = dt.date(2031, 5, 14); inj["lines_invalid_service_date"] = len(ixd)
    inj["claims_changed_between_batches"] = int(changed.sum())
    inj["patients_plan_changed"] = int(chg_plan.sum()); inj["patients_city_changed"] = int(chg_city.sum())
    inj["patients_any_change"] = int(chg.changed.sum())
    return dict(ins=ins, plans=plans, hosp=hosp, docs=docs, dxref=dxref, prref=prref, pat=pat, chg=chg, C=C, L=L, inj=inj)

def _iso(df, cols):
    df = df.copy()
    for c in cols:
        df[c] = df[c].map(lambda v: v.isoformat() if hasattr(v, "isoformat") else v)
    return df

def view_asof(T, cut, prev=None):
    """Source-system content visible at business date `cut` (claims not yet adjudicated are 'Pending')."""
    C, L = T["C"].copy(), T["L"].copy()
    C = C[C.submit_date <= cut].copy()
    pend = C.adjudication_date > cut
    C.loc[pend, "status"] = "Pending"; C.loc[pend, "denial_reason"] = "NA"
    C["adjudication_date"] = C.adjudication_date.where(~pend, None)
    L = L[L.claim_id.isin(C.claim_id)].copy()
    pl = L.claim_id.isin(C.claim_id[pend])
    for c in ["allowed_amount", "denied_amount", "copay_amount", "paid_amount"]:
        L.loc[pl, c] = 0.0
    return C, L, set(C.claim_id[pend])

def write_batch1():
    os.makedirs(DATA, exist_ok=True)
    if os.path.exists(SRC): os.remove(SRC)
    rng = np.random.default_rng(SEED)
    T = build_truth(rng)
    import pickle; pickle.dump(T, open(os.path.join(DATA, "truth.pkl"), "wb"))
    con = sqlite3.connect(SRC); con.executescript(DDL)
    T["ins"][["insurer_id", "name", "insurer_type"]].to_sql("src_insurer", con, if_exists="append", index=False)
    T["plans"].to_sql("src_plan", con, if_exists="append", index=False)
    T["hosp"][["hospital_id", "name", "city", "ownership", "beds"]].to_sql("src_hospital", con, if_exists="append", index=False)
    T["docs"].rename(columns={}).to_sql("src_doctor", con, if_exists="append", index=False)
    T["dxref"].to_sql("src_diagnosis_ref", con, if_exists="append", index=False)
    T["prref"].to_sql("src_procedure_ref", con, if_exists="append", index=False)
    P = T["pat"][["patient_id", "name", "gender", "birth_date", "city", "state", "plan_id", "policy_no", "profile_updated_on"]].copy()
    P["last_updated"] = P.profile_updated_on
    P.to_sql("src_patient", con, if_exists="append", index=False)
    C, L, pend = view_asof(T, CUT1)
    C["last_updated"] = C.submit_date; L["last_updated"] = L.claim_id.map(C.set_index("claim_id").submit_date)
    # duplicate header rows (defect) - exact copies of already-sent claim headers
    rng2 = np.random.default_rng(SEED + 1)
    ok = C.index[~C.claim_id.isin(T["C"].claim_id[(T["C"].submit_date <= CUT1) & (T["C"].adjudication_date > CUT1)])]
    dup = C.loc[rng2.choice(ok, int(len(C) * .0025), replace=False)]
    T["inj"]["duplicate_claim_rows_batch1"] = len(dup)
    C = pd.concat([C, dup]); 
    _iso(C, ["admission_date", "discharge_date", "submit_date", "adjudication_date"]).to_sql("src_claim", con, if_exists="append", index=False)
    _iso(L, ["service_date"]).to_sql("src_claim_line", con, if_exists="append", index=False)
    for t, c in [("src_claim", "claim_id"), ("src_claim_line", "claim_id"), ("src_claim", "last_updated")]:
        con.execute(f"CREATE INDEX ix_{t}_{c} ON {t}({c})")
    con.commit(); con.close()
    json.dump(T["inj"], open(os.path.join(DATA, "injected_defects.json"), "w"), indent=1)
    print("batch 1 written:", len(C), "claim rows,", len(L), "line rows")
    return T

def apply_batch2():
    import pickle
    T = pickle.load(open(os.path.join(DATA, "truth.pkl"), "rb"))
    con = sqlite3.connect(SRC)
    C1, L1, pend1 = view_asof(T, CUT1)
    C2, L2, pend2 = view_asof(T, CUT2)
    # (a) late-adjudicated claims -> UPDATE existing source rows
    chg_ids = sorted(set(pend1) - pend2)
    key = C2.set_index("claim_id")
    rows = [(key.at[c, "adjudication_date"].isoformat(), key.at[c, "status"], key.at[c, "denial_reason"], CUT2.isoformat(), c) for c in chg_ids]
    con.executemany("UPDATE src_claim SET adjudication_date=?, status=?, denial_reason=?, last_updated=? WHERE claim_id=?", rows)
    Lk = L2.set_index(["claim_id", "line_no"])
    lrows = []
    for c in chg_ids:
        for (cc, ln), r in Lk.loc[[c]].iterrows() if False else []:
            pass
    sub = L2[L2.claim_id.isin(chg_ids)]
    con.executemany("UPDATE src_claim_line SET allowed_amount=?, denied_amount=?, copay_amount=?, paid_amount=?, last_updated=? WHERE claim_id=? AND line_no=?",
                    [(r.allowed_amount, r.denied_amount, r.copay_amount, r.paid_amount, CUT2.isoformat(), r.claim_id, int(r.line_no)) for r in sub.itertuples()])
    # (b) brand-new claims
    new_ids = set(C2.claim_id) - set(C1.claim_id)
    Cn = C2[C2.claim_id.isin(new_ids)].copy(); Ln = L2[L2.claim_id.isin(new_ids)].copy()
    Cn["last_updated"] = Cn.submit_date; Ln["last_updated"] = Ln.claim_id.map(Cn.set_index("claim_id").submit_date)
    rng2 = np.random.default_rng(SEED + 2)
    ok = Cn.index[~Cn.claim_id.isin(T["C"].claim_id[T["C"].adjudication_date > CUT2])]
    dup = Cn.loc[rng2.choice(ok, int(len(Cn) * .0025), replace=False)]
    T["inj"]["duplicate_claim_rows_batch2"] = len(dup)
    Cn = pd.concat([Cn, dup])
    _iso(Cn, ["admission_date", "discharge_date", "submit_date", "adjudication_date"]).to_sql("src_claim", con, if_exists="append", index=False)
    _iso(Ln, ["service_date"]).to_sql("src_claim_line", con, if_exists="append", index=False)
    # (c) patient master changes (OLTP overwrites old values - history is lost)
    ch = T["chg"][T["chg"].changed]
    con.executemany("UPDATE src_patient SET plan_id=?, city=?, state=?, profile_updated_on='2025-01-01', last_updated='2025-01-01' WHERE patient_id=?",
                    [(r.plan_id, r.city, r.state, r.patient_id) for r in ch.itertuples()])
    con.commit(); con.close()
    inj = json.load(open(os.path.join(DATA, "injected_defects.json"))); inj.update({k: v for k, v in T["inj"].items() if k.endswith("batch2")})
    inj["duplicate_claim_rows"] = inj["duplicate_claim_rows_batch1"] + inj["duplicate_claim_rows_batch2"]
    json.dump(inj, open(os.path.join(DATA, "injected_defects.json"), "w"), indent=1)
    print("batch 2 applied:", len(new_ids), "new claims,", len(chg_ids), "late-adjudicated claims,", len(ch), "patients changed")

if __name__ == "__main__":
    if sys.argv[1] == "1": write_batch1()
    else: apply_batch2()
