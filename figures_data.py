import os, json, sqlite3, textwrap, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt, numpy as np
plt.rcParams["font.family"] = "Liberation Serif"; plt.rcParams["axes.spines.top"] = False; plt.rcParams["axes.spines.right"] = False
D = os.path.join(os.path.dirname(__file__), ".."); OUT = os.path.join(D, "figures"); RES = os.path.join(D, "results")
NAVY, TEAL, ORG, GREY = "#1F3A5F", "#1B7F79", "#C8691E", "#8A8F98"
ol = json.load(open(os.path.join(RES, "olap_results.json")))
dw = sqlite3.connect(os.path.join(D, "data", "claims_dw.db"))

# Fig 9 ETL load profile
a = dw.execute("SELECT batch_id, lines_extracted, lines_rejected, lines_inserted, lines_updated, seconds FROM etl_audit ORDER BY 1").fetchall()
rules = dw.execute("SELECT rule_id, COUNT(*) FROM dq_reject GROUP BY 1 ORDER BY 1").fetchall()
fig, (x1, x2) = plt.subplots(1, 2, figsize=(7.4, 3.5), gridspec_kw={"width_ratios": [1.25, 1]})
lab = ["Extracted", "Rejected", "Inserted", "Updated"]; cols = [GREY, ORG, TEAL, NAVY]; w = .2
for i, l in enumerate(lab):
    vals = [r[i + 1] for r in a]; b = x1.bar(np.arange(len(a)) + (i - 1.5) * w, vals, w, label=l, color=cols[i])
    for rect, v in zip(b, vals): x1.text(rect.get_x() + rect.get_width() / 2, v + 4000, f"{v:,}", ha="center", fontsize=6.3, rotation=90)
x1.set_xticks(range(len(a))); x1.set_xticklabels([f"Batch {r[0]}\n({'initial' if r[0]==1 else 'incremental'}, {r[5]:.0f} s)" for r in a], fontsize=8)
x1.set_ylabel("Claim lines", fontsize=8.5); x1.set_ylim(0, max(r[1] for r in a) * 1.28); x1.legend(fontsize=7.5, frameon=False, loc="upper right"); x1.tick_params(labelsize=7.5)
x1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: f"{int(v/1000)}k")); x1.set_title("(a) Rows per ETL batch", fontsize=9, loc="left")
names = {"R1": "R1 duplicate\nheader", "R2": "R2 negative\nbilled", "R3": "R3 paid >\nallowed", "R4": "R4 bad service\ndate", "R6": "R6 unknown\ndiagnosis"}
rr = [(names[r], c) for r, c in rules if r in names]
b = x2.barh([r[0] for r in rr][::-1], [r[1] for r in rr][::-1], color=[ORG] * len(rr), height=.6)
for rect, (n, v) in zip(b, rr[::-1]): x2.text(v + 15, rect.get_y() + rect.get_height() / 2, f"{v:,}", va="center", fontsize=7.5)
x2.set_xlim(0, max(r[1] for r in rr) * 1.18); x2.tick_params(labelsize=7.3); x2.set_xlabel("Records logged in dq_reject", fontsize=8.5); x2.set_title("(b) Data-quality outcomes", fontsize=9, loc="left")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig9_etl_profile.png"), dpi=220); plt.close(fig)

# Fig 10 ETL console
lines = open(os.path.join(RES, "etl_log.txt")).read().splitlines()
wrapped = []
for l in lines: wrapped += textwrap.wrap(l, 112, subsequent_indent="            ") or [""]
fig = plt.figure(figsize=(7.4, 0.5 + 0.19 * len(wrapped) + .3)); fig.patch.set_facecolor("#14181F")
ax = fig.add_axes([0, 0, 1, 1]); ax.set_facecolor("#14181F"); ax.axis("off")
ax.text(.015, 1 - .25 / fig.get_figheight(), "$ python etl.py 1 && python etl.py 2", color="#7EE787", family="Liberation Mono", fontsize=6.9, va="top", transform=ax.transAxes)
for i, l in enumerate(wrapped):
    c = "#FFD479" if "=====" in l else ("#7EE787" if "COMPLETE" in l else "#D6DEEB")
    ax.text(.015, 1 - (.55 + .19 * i) / fig.get_figheight(), l, color=c, family="Liberation Mono", fontsize=6.4, va="top", transform=ax.transAxes)
fig.savefig(os.path.join(OUT, "fig10_etl_console.png"), dpi=220, facecolor=fig.get_facecolor()); plt.close(fig)

# Fig 11 dashboard
q = ol["queries"]; fig = plt.figure(figsize=(7.4, 5.6)); gs = fig.add_gridspec(3, 2, height_ratios=[.38, 2, 2], hspace=.7, wspace=.62)
tot = dw.execute("SELECT ROUND(SUM(claim_count)), SUM(billed_amount), SUM(paid_amount), SUM(denied_amount) FROM fact_claim_monthly_snapshot").fetchone()
den = dw.execute("""SELECT ROUND(100.0*SUM(CASE WHEN s.claim_status='Denied' THEN f.claim_weight END)/SUM(CASE WHEN s.claim_status<>'Pending' THEN f.claim_weight END),2)
                    FROM fact_claim_line f JOIN dim_claim_status s ON s.claim_status_key=f.claim_status_key""").fetchone()[0]
pdays = dw.execute("SELECT ROUND(SUM(processing_days*claim_weight)/SUM(claim_weight),1) FROM fact_claim_line WHERE processing_days IS NOT NULL").fetchone()[0]
ax = fig.add_subplot(gs[0, :]); ax.axis("off")
kp = [("Claims", f"{int(tot[0]):,}"), ("Billed (INR)", f"{tot[1]/1e7:,.1f} Cr"), ("Paid by insurers", f"{tot[2]/1e7:,.1f} Cr"), ("Denial rate", f"{den}%"), ("Avg. processing", f"{pdays} days")]
for i, (k, v) in enumerate(kp):
    ax.add_patch(plt.Rectangle((i / 5 + .005, 0), .19, 1, fc="#E8EEF5", ec=NAVY, lw=.8, transform=ax.transAxes)); ax.text(i / 5 + .1, .66, v, ha="center", va="center", fontsize=11, fontweight="bold", color=NAVY, transform=ax.transAxes); ax.text(i / 5 + .1, .22, k, ha="center", va="center", fontsize=7.5, transform=ax.transAxes)
ax = fig.add_subplot(gs[1, 0]); m = q["Q1"]["rows"]; lbl = [f"{int(r[0])%100:02d}-{int(r[1]):02d}" for r in m]
ax.bar(range(len(m)), [r[2] for r in m], color="#C9D6E6", label="Claims (left)"); ax.set_ylabel("Claims", fontsize=8); ax2 = ax.twinx(); ax2.plot(range(len(m)), [r[4] / 1e6 for r in m], color=ORG, lw=1.6, label="Paid, INR million (right)"); ax2.spines["right"].set_visible(True); ax2.set_ylabel("Paid (INR m)", fontsize=8)
ax.set_xticks(range(0, len(m), 5)); ax.set_xticklabels([lbl[i] for i in range(0, len(m), 5)], fontsize=6.5, rotation=45); ax.tick_params(labelsize=7); ax2.tick_params(labelsize=7); ax.set_title("(a) Monthly claims and paid amount (YY-MM)", fontsize=8.5, loc="left")
ax = fig.add_subplot(gs[1, 1]); rows = q["Q2"]["rows"]; ins = sorted({r[0] for r in rows}); yrs = sorted({r[1] for r in rows}); ww = .27
for i, y in enumerate(yrs): ax.bar(np.arange(len(ins)) + (i - 1) * ww, [next(r[4] for r in rows if r[0] == n and r[1] == y) for n in ins], ww, label=str(y), color=[GREY, TEAL, ORG][i])
ax.set_xticks(range(len(ins))); ax.set_xticklabels([n.split()[0] for n in ins], fontsize=7); ax.set_ylabel("Denial rate (%)", fontsize=8); ax.legend(fontsize=6.8, frameon=False, ncol=3); ax.tick_params(axis="y", labelsize=7); ax.set_title("(b) Denial rate by insurer and year", fontsize=8.5, loc="left")
ax = fig.add_subplot(gs[2, 0]); t = q["Q3"]["rows"][::-1]; ax.barh([f"{r[0]}  {r[1].split(',')[0][:22]}" for r in t], [r[3] / 1e6 for r in t], color=TEAL, height=.65); ax.tick_params(labelsize=6.3); ax.set_xlabel("Paid (INR million)", fontsize=8); ax.set_title("(c) Top 10 diagnoses by paid amount", fontsize=8.5, loc="left")
ax = fig.add_subplot(gs[2, 1]); r4 = q["Q4"]["rows"]; hs = sorted({r[0] for r in r4}); 
for i, ct in enumerate(["Cashless", "Reimbursement"]): ax.barh(np.arange(len(hs)) + (i - .5) * .38, [next(r[3] for r in r4 if r[0] == h and r[1] == ct) for h in hs], .38, label=ct, color=[TEAL, ORG][i])
ax.set_yticks(range(len(hs))); ax.set_yticklabels([h.split(" ")[0] + " " + h.split(" ")[1] for h in hs], fontsize=6.5); ax.set_xlabel("Average processing days", fontsize=8); ax.set_xlim(0, 33); ax.legend(fontsize=6.8, frameon=False, loc="upper right"); ax.tick_params(axis="x", labelsize=7); ax.set_title("(d) Processing time by hospital and claim type", fontsize=8.5, loc="left")
fig.savefig(os.path.join(OUT, "fig11_dashboard.png"), dpi=220, bbox_inches="tight"); plt.close(fig)

# Fig 12 timings
tm = ol["timings"]; ks = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"]
fig, ax = plt.subplots(figsize=(7.2, 3.5)); x = np.arange(len(ks)); w = .27
b1 = ax.bar(x - w, [tm[k]["3nf_ms"] for k in ks], w, label="Normalized (3NF) copy", color=GREY); b2 = ax.bar(x, [tm[k]["star_ms"] for k in ks], w, label="Star schema (transaction fact)", color=TEAL)
sn = [tm["Q1_snapshot"]["star_ms"] if k == "Q1" else 0 for k in ks]; b3 = ax.bar(x + w, sn, w, label="Star schema (monthly snapshot)", color=ORG)
for bs in (b1, b2): 
    for r in bs: ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 12, f"{r.get_height():.0f}", ha="center", fontsize=7)
ax.text(x[0] + w, tm["Q1_snapshot"]["star_ms"] + 12, f"{tm['Q1_snapshot']['star_ms']}", ha="center", fontsize=7)
ax.set_xticks(x); ax.set_xticklabels([f"{k}" for k in ks]); ax.set_ylabel("Median response time (ms)", fontsize=9); ax.legend(fontsize=8, frameon=False); ax.set_ylim(0, 1250)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig12_timing.png"), dpi=220); plt.close(fig)
print("done")
