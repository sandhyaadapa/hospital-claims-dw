import os, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Ellipse, Circle, Rectangle, FancyArrowPatch, Polygon
plt.rcParams["font.family"] = "Liberation Serif"
OUT = os.path.join(os.path.dirname(__file__), "..", "figures")
NAVY, TEAL, ORG, LIGHT, TL, OL = "#1F3A5F", "#1B7F79", "#C8691E", "#E8EEF5", "#D7EEEC", "#FBE9D8"

def canvas(w, h, W=100, H=60):
    fig = plt.figure(figsize=(w, h)); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off"); return fig, ax
def box(ax, x, y, w, h, t, fc=LIGHT, ec=NAVY, fs=8, bold=False, rnd=1.2, lw=1.2, ha="center"):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle=f"round,pad=0,rounding_size={rnd}", fc=fc, ec=ec, lw=lw, zorder=2))
    ax.text(x, y, t, ha=ha, va="center", fontsize=fs, fontweight="bold" if bold else "normal", zorder=3, linespacing=1.15)
    return (x, y, w, h)
def band(ax, x0, y0, x1, y1, label, fs=8, bottom=False):
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="#FAFAFA", ec="#BBBBBB", lw=.8, ls="--", zorder=0))
    ax.text(x1 - 1, (y0 + 1.2) if bottom else (y1 - 1.2), label, fontsize=fs, color=NAVY, fontweight="bold", va="bottom" if bottom else "top", ha="right", zorder=1)
def A(ax, p, q, label=None, ls="-", fs=7, off=(0, 1), rad=0, both=False, color=NAVY):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="<|-|>" if both else "-|>", mutation_scale=9, lw=1.1, color=color, ls=ls, connectionstyle=f"arc3,rad={rad}", zorder=2.6, shrinkA=0, shrinkB=0))
    if label: ax.text((p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1], label, fontsize=fs, ha="center", va="center", zorder=4, bbox=dict(fc="white", ec="none", pad=.6))
def save(fig, name): fig.savefig(os.path.join(OUT, name + ".png"), dpi=220); plt.close(fig)
def cyl(ax, x, y, w, h, t, fs=7):
    ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc="white", ec=NAVY, lw=1.2, zorder=2))
    for dy in (h / 2, -h / 2): ax.add_patch(Ellipse((x, y + dy), w, h * .25, fc="white", ec=NAVY, lw=1.2, zorder=2.5))
    ax.text(x, y, t, ha="center", va="center", fontsize=fs, zorder=3)

# ---------- Fig 1 architecture
fig, ax = canvas(7.4, 5.0, 100, 72)
band(ax, 2, 58, 98, 71, "SOURCE SYSTEMS"); band(ax, 2, 31, 98, 56, "STAGING AND ETL (Python)"); band(ax, 2, 16, 98, 29.5, "DATA WAREHOUSE (SQLite, star schema)"); band(ax, 2, 1, 98, 14.5, "ANALYTICS AND USERS", bottom=True)
for x, t in [(20, "Hospital billing / HIS\nclaim tables"), (50, "Insurer adjudication feed\n(status, payments)"), (80, "Patient registration\nand master data")]: box(ax, x, 63, 26, 7, t)
box(ax, 50, 50.8, 88, 5.2, "1. Incremental extract (watermark on last_updated)", OL, ORG)
e2 = box(ax, 18, 43, 25, 8, "2. Data-quality gate\n(rules R1 to R6)", OL, ORG); e3 = box(ax, 50, 43, 25, 8, "3. Transform: SCD-1 / SCD-2,\nsurrogate keys, measures", OL, ORG); e4 = box(ax, 82, 43, 25, 8, "4. Load and upsert facts\nrebuild snapshot", OL, ORG)
cyl(ax, 18, 35, 22, 4.2, "DQ reject log, ETL audit", 6.5)
box(ax, 20, 23, 26, 8, "9 conformed dimensions\n(date, patient, provider, ...)", TL, TEAL); box(ax, 50, 23, 26, 8, "fact_claim_line\n(claim-line grain)", TL, TEAL, bold=True); box(ax, 82, 23, 26, 8, "fact_claim_monthly_\nsnapshot (aggregate)", TL, TEAL)
box(ax, 18, 9, 22, 8, "Claims manager,\nFinance, Analyst", "white", NAVY); box(ax, 50, 9, 26, 8, "OLAP SQL queries\n(roll-up, drill-down, slice, dice)"); box(ax, 82, 9, 26, 8, "Dashboard\nand reports")
for x in (20, 50, 80): A(ax, (x, 59.5), (50 + (x - 50) * .8, 53.4))
A(ax, (18, 48.2), (18, 47)); A(ax, (50, 48.2), (50, 47)); A(ax, (82, 48.2), (82, 47))
A(ax, (29, 43), (37.5, 43)); A(ax, (62.5, 43), (69.5, 43)); A(ax, (18, 39), (18, 37.1), ls="--")
A(ax, (45, 39), (23, 27)); A(ax, (82, 39), (55, 27)); A(ax, (33, 23), (37, 23), ls=":"); A(ax, (63, 23), (69, 23)); A(ax, (50, 19), (50, 13)); A(ax, (82, 19), (82, 13)); A(ax, (63, 9), (69, 9)); A(ax, (37, 9), (29, 9))
save(fig, "fig1_architecture")

# ---------- Fig 2 DFD 0
fig, ax = canvas(7.4, 3.6, 100, 48)
box(ax, 13, 36, 22, 9, "Hospital Billing /\nHIS system", "white", NAVY, fs=9, rnd=.3); box(ax, 13, 12, 22, 9, "Insurer / TPA\nadjudication feed", "white", NAVY, fs=9, rnd=.3)
box(ax, 87, 24, 22, 10, "Claims analyst /\nfinance manager", "white", NAVY, fs=9, rnd=.3)
ax.add_patch(Circle((50, 24), 13.5, fc=TL, ec=TEAL, lw=1.6, zorder=2)); ax.text(50, 24, "0\nHospital Insurance-\nClaims Data\nWarehouse System", ha="center", va="center", fontsize=9.5, fontweight="bold", zorder=3)
A(ax, (24, 36), (38, 29.6), "claim headers, claim lines,\npatient master", off=(2, 6), fs=7.5); A(ax, (24, 12), (38, 18.4), "claim status, denial reason,\npayment amounts", off=(2, -6), fs=7.5)
A(ax, (63.5, 27), (76, 27), "OLAP results,\ndashboard, reports", off=(0, 5), fs=7.5); A(ax, (76, 21), (63.5, 21), "analysis requests", off=(0, -3.5), fs=7.5)
save(fig, "fig2_dfd0")

# ---------- Fig 3 DFD 1
fig, ax = canvas(7.4, 4.6, 100, 64)
def P(x, y, t, c=OL, e=ORG): ax.add_patch(Circle((x, y), 6.3, fc=c, ec=e, lw=1.4, zorder=2)); ax.text(x, y, t, ha="center", va="center", fontsize=6.8, zorder=3, linespacing=1.1)
def D(x, y, t, w=14): ax.add_patch(Rectangle((x - w / 2, y - 2.6), w, 5.2, fc="white", ec=NAVY, lw=1.2, zorder=2)); ax.plot([x - w / 2 + 2, x - w / 2 + 2], [y - 2.6, y + 2.6], color=NAVY, lw=1); ax.text(x + 1, y, t, ha="center", va="center", fontsize=6.8, zorder=3)
box(ax, 14, 59, 20, 5.5, "Source systems", "white", NAVY, fs=7.5, rnd=.3)
P(14, 46, "1.0\nExtract\n(watermark)"); P(32, 46, "2.0\nValidate\nand clean"); P(50, 46, "3.0\nBuild\ndimensions"); P(68, 46, "4.0\nLoad\nfacts"); P(86, 46, "5.0\nAggregate\nsnapshot")
D(23, 31, "D1 Staging"); D(41, 31, "D2 DQ rejects", 16); D(59, 31, "D3 Dimensions", 16); D(77, 31, "D4 Fact tables", 16); D(93, 31, "D5 Audit", 11)
P(50, 10, "6.0\nOLAP\nquery", TL, TEAL); box(ax, 12, 10, 20, 5.5, "Analyst", "white", NAVY, fs=7.5, rnd=.3)
A(ax, (14, 56.2), (14, 52.3), "delta rows", off=(5, 0), fs=6.5); A(ax, (18, 41.5), (22, 34)); A(ax, (26, 34), (29, 41)); A(ax, (34, 40), (39, 34), "rejects", off=(-3.5, 0), fs=6.5)
A(ax, (38, 46), (44, 46), "clean rows", off=(0, 2.3), fs=6.5); A(ax, (54, 41.5), (58, 34)); A(ax, (62, 34), (65, 41)); A(ax, (56, 46), (62, 46), "keys", off=(0, 2.3), fs=6.5)
A(ax, (72, 41.5), (76, 34)); A(ax, (80, 34), (83, 41)); A(ax, (90, 41), (92, 34), "audit", off=(4, 0), ls="--", fs=6.5); A(ax, (88, 40), (82, 34), ls=":", color=NAVY)
A(ax, (59, 28.4), (55.5, 15.5)); A(ax, (74, 28.4), (56, 13.5)); A(ax, (43.7, 11.5), (22, 11.5), "results", off=(0, 2), fs=6.5); A(ax, (22, 8.2), (43.9, 8.2), "request", off=(0, -2), fs=6.5)
A(ax, (74, 38), (72, 34), ls=":", color="white")
save(fig, "fig3_dfd1")

# ---------- Fig 4 use case
fig, ax = canvas(7.0, 4.4, 100, 66)
band(ax, 24, 2, 76, 64, "")
ax.text(50, 62, "Hospital Insurance-Claims Data Warehouse", ha="center", fontsize=8.5, color=NAVY, fontweight="bold")
UC = ["Run incremental ETL load", "Review data-quality rejects", "Manage dimensions (SCD)", "Run OLAP queries", "Analyse denial reasons", "Track settlement ratio\nand revenue cycle", "View claims dashboard", "Export reports"]
ys = [54, 46.5, 39, 31.5, 24, 16.5, 9.5, 3.5]
ys = [55, 47.5, 40, 32.5, 25, 17.5, 10.5, 4.5]
uc = {}
for i, (t, y) in enumerate(zip(UC, ys)):
    ax.add_patch(Ellipse((50, y), 38, 5.4, fc=LIGHT, ec=NAVY, lw=1.1, zorder=2)); ax.text(50, y, t, ha="center", va="center", fontsize=7.5, zorder=3, linespacing=1.05); uc[i] = y
def actor(x, y, name):
    ax.add_patch(Circle((x, y + 4), 1.6, fc="white", ec=NAVY, lw=1.2, zorder=3)); ax.plot([x, x], [y + 2.4, y - 2], color=NAVY, lw=1.2); ax.plot([x - 2.5, x + 2.5], [y + 1, y + 1], color=NAVY, lw=1.2)
    ax.plot([x, x - 2], [y - 2, y - 5], color=NAVY, lw=1.2); ax.plot([x, x + 2], [y - 2, y - 5], color=NAVY, lw=1.2); ax.text(x, y - 7.5, name, ha="center", fontsize=8, fontweight="bold")
def link(x, y, i, side): ax.plot([x + (2.5 if side == "L" else -2.5), 50 + (-19 if side == "L" else 19)], [y + 1, uc[i]], color=NAVY, lw=.9, zorder=1)
actor(10, 46, "Data Engineer"); [link(10, 46, i, "L") for i in (0, 1, 2)]
actor(10, 22, "Claims Analyst"); [link(10, 22, i, "L") for i in (3, 4, 6)]
actor(90, 40, "Insurer Liaison"); [link(90, 40, i, "R") for i in (4, 5)]
actor(90, 14, "Finance Manager"); [link(90, 14, i, "R") for i in (5, 6, 7)]
save(fig, "fig4_usecase")

# ---------- Fig 5 sequence
fig, ax = canvas(7.4, 4.4, 100, 62)
names = ["Data Engineer", "ETL Engine", "Source OLTP", "Data Warehouse", "Claims Analyst"]; xs = [10, 30, 50, 70, 90]
for x, n in zip(xs, names):
    box(ax, x, 58, 17, 4.5, n, LIGHT, NAVY, fs=7.5, bold=True); ax.plot([x, x], [55.5, 2], color="#888888", lw=.9, ls="--", zorder=0)
msgs = [(0, 1, "1: start batch(as_of)", 52, 0), (1, 3, "2: read watermark", 47.5, 0), (3, 1, "3: watermark", 44.5, 1), (1, 2, "4: SELECT rows > watermark", 40.5, 0), (2, 1, "5: delta claims and lines", 37.5, 1),
        (1, 1, "6: validate, dedupe, reject (R1-R6)", 33, 0), (1, 3, "7: upsert dimensions (SCD-1/2)", 26.5, 0), (1, 3, "8: lookup keys, upsert facts", 22, 0), (1, 3, "9: rebuild snapshot, write audit", 17.5, 0),
        (1, 0, "10: batch summary", 13.5, 1), (4, 3, "11: OLAP query (SQL)", 9, 0), (3, 4, "12: result set / dashboard data", 4.5, 1)]
for a, b, t, y, ret in msgs:
    if a == b:
        ax.add_patch(Rectangle((xs[a], y - 2.2), 3, 4.4, fc=OL, ec=ORG, zorder=2)); ax.text(xs[a] + 4.5, y, t, fontsize=7.3, va="center", bbox=dict(fc="white", ec="none", pad=.4)); continue
    A(ax, (xs[a], y), (xs[b], y), ls="--" if ret else "-"); ax.text((xs[a] + xs[b]) / 2, y + 1.6, t, fontsize=7.3, ha="center", bbox=dict(fc="white", ec="none", pad=.4))
save(fig, "fig5_sequence")

# ---------- Fig 6 star schema
fig, ax = canvas(6.8, 5.4, 100, 80)
def table(x, y, w, title, rows, hc=TEAL, fs=6.4, rh=2.35):
    h = rh * (len(rows) + 1.3)
    ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc="white", ec=hc, lw=1.2, zorder=2)); ax.add_patch(Rectangle((x - w / 2, y + h / 2 - rh * 1.3), w, rh * 1.3, fc=hc, ec=hc, zorder=2.2))
    ax.text(x, y + h / 2 - rh * .65, title, ha="center", va="center", color="white", fontsize=fs + .6, fontweight="bold", zorder=3)
    for i, r in enumerate(rows): ax.text(x - w / 2 + 1, y + h / 2 - rh * 1.3 - rh * (i + .55), r, fontsize=fs, va="center", zorder=3)
    return (x, y, w, h)
fact = table(50, 43, 33, "fact_claim_line  (grain: one claim line)", ["claim_line_key (PK)", "claim_id, line_no  (degenerate)", "service_date_key (FK)", "submit_date_key (FK)", "adjudication_date_key (FK)", "patient_key (FK)", "provider_key (FK)", "hospital_key (FK)", "diagnosis_key (FK)", "procedure_key (FK)", "insurer_key (FK)", "plan_key (FK)", "claim_status_key (FK)",
        "quantity, billed_amount, allowed_amount", "denied_amount, copay_amount, paid_amount", "processing_days, claim_weight"], ORG, 6.3, 2.2)
L = [("dim_date", ["date_key (PK)", "full_date, day_name", "month, quarter, year", "fiscal_year, is_weekend"], 71), ("dim_patient (SCD-2)", ["patient_key (PK)", "patient_id, gender, age_band", "city, state, plan_id", "effective_from / effective_to", "is_current, version_no"], 53), ("dim_provider", ["provider_key (PK)", "doctor_id, doctor_name", "specialty"], 36), ("dim_hospital", ["hospital_key (PK)", "hospital_name, city", "ownership, bed_count"], 20)]
R = [("dim_diagnosis", ["diagnosis_key (PK)", "icd10_code, description", "category, chronic_flag"], 71), ("dim_procedure", ["procedure_key (PK)", "proc_code, description", "proc_category"], 55), ("dim_insurer", ["insurer_key (PK)", "insurer_name", "insurer_type"], 39), ("dim_plan", ["plan_key (PK)", "plan_name", "sum_insured, copay_pct"], 23)]
for (t, r, y) in L:
    b = table(14, y, 25, t, r); pass
for (t, r, y) in R:
    b = table(86, y, 25, t, r); ax.plot([73.5, 66.5], [y, min(max(y, 27), 59)], color=NAVY, lw=1)
b = table(50, 8, 30, "dim_claim_status (junk dimension)", ["claim_status_key (PK)", "claim_status, denial_reason", "claim_type, admission_type"]); ax.plot([50, 50], [13.2, 22.6], color=NAVY, lw=1)
snap = table(50, 74, 36, "fact_claim_monthly_snapshot", ["month_key, insurer_key, hospital_key (PK)", "claim_count, line_count, billed_amount", "allowed_amount, denied_amount, paid_amount"], TEAL, 6.0, 2.2)
ax.text(52, 66.6, "aggregated from fact_claim_line", fontsize=6.3, ha="left", style="italic"); A(ax, (50, 63.6), (50, 69.4), ls="--")
for y in (71, 53, 36, 20): ax.plot([26.5, 33.5], [y, min(max(y, 27), 59)], color=NAVY, lw=1)
save(fig, "fig6_star_schema")

# ---------- Fig 7 modules
fig, ax = canvas(7.4, 3.3, 100, 44)
mods = [("M1\nSource data\nsimulation and\nextraction", LIGHT, NAVY), ("M2\nData quality\nand staging", OL, ORG), ("M3\nDimension\nmodelling\n(SCD-1 / SCD-2)", TL, TEAL), ("M4\nFact loading\nand snapshot", TL, TEAL), ("M5\nOLAP analytics,\ntesting and\nreporting", LIGHT, NAVY)]
xs = [10, 30, 50, 70, 90]
for x, (t, f, e) in zip(xs, mods): box(ax, x, 27, 16, 14, t, f, e, fs=7.6)
for a, l in zip(range(4), ["delta rows", "clean rows", "surrogate keys", "facts"]):
    A(ax, (xs[a] + 8.2, 27), (xs[a + 1] - 8.2, 27)); ax.text((xs[a] + xs[a + 1]) / 2, 35.2, l, fontsize=7, ha="center")
cyl(ax, 50, 9, 36, 7, "ETL audit and data-quality reject log", 7.3)
for x in (30, 50, 70): A(ax, (x, 20), (x if x == 50 else (43 if x == 30 else 57), 12.4), ls="--")
ax.text(50, 1.5, "Each batch repeats M1 to M4; M5 queries the warehouse built by M3 and M4", fontsize=7.2, ha="center", style="italic")
save(fig, "fig7_modules")

# ---------- Fig 8 ETL flowchart
items = [("Start batch (business date)", 6, "white", NAVY), ("Read watermark from etl_audit", 6, LIGHT, NAVY), ("Extract rows with last_updated > watermark\n(claims, lines, reference tables, patients)", 9, LIGHT, NAVY), ("Remove duplicate claim headers (R1)", 6, OL, ORG),
         ("Validate claim lines\nR2 negative billed | R3 paid > allowed\nR4 service date range | R5 orphan line", 12, OL, ORG), ("DIAMOND", 12, None, None),
         ("Map missing / invalid ICD-10 to Unknown key (R6)", 6, OL, ORG), ("Upsert SCD-1 dimensions (hospital, provider,\ndiagnosis, procedure, insurer, plan, status)", 9, TL, TEAL), ("SCD-2 patient: expire old version,\ninsert new version on city / plan change", 9, TL, TEAL),
         ("Surrogate-key and point-in-time lookup;\ncompute measures, processing_days, claim_weight", 9, LIGHT, NAVY), ("Upsert fact_claim_line on (claim_id, line_no)\nINSERT new, UPDATE late adjudications", 9, TL, TEAL), ("Rebuild monthly snapshot fact; create indexes", 6, LIGHT, NAVY),
         ("Write etl_audit row; advance watermark", 6, LIGHT, NAVY), ("End batch", 6, "white", NAVY)]
GAP = 5; H = sum(h for _, h, _, _ in items) + GAP * (len(items) - 1) + 4
fig, ax = canvas(5.2, 5.2 * H / 100 + .0, 100, H); cx = 36; W = 62; top = H - 2; prev = None
for t, h, fc, ec in items:
    yc = top - h / 2
    if t == "DIAMOND":
        ax.add_patch(Polygon([[cx, yc + 6], [cx + 15, yc], [cx, yc - 6], [cx - 15, yc]], fc="white", ec=NAVY, lw=1.2, zorder=2)); ax.text(cx, yc, "Line valid?", ha="center", va="center", fontsize=8.3, zorder=3)
        cyl(ax, 86, yc, 22, 8, "dq_reject\n(logged)", 7.5); A(ax, (cx + 15, yc), (75, yc), "No", off=(0, 2.3), fs=8)
    else: box(ax, cx, yc, W, h, t, fc, ec, fs=8.3)
    if prev is not None: A(ax, (cx, prev), (cx, top), "Yes" if t.startswith("Map") else None, off=(4, 0), fs=8)
    prev = yc - h / 2; top = prev - GAP
save(fig, "fig8_etl_flow")
print("ok")
