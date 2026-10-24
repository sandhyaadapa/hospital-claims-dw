import subprocess, os
OUT = os.path.join(os.path.dirname(__file__), "..", "figures")
F = 'fontname="Liberation Serif"'
def render(name, dot, engine="dot"):
    p = os.path.join(OUT, name + ".dot"); open(p, "w").write(dot)
    subprocess.run([engine, "-Tpng", "-Gdpi=220", p, "-o", os.path.join(OUT, name + ".png")], check=True)

NAVY, TEAL, ORG, LIGHT, GREY = "#1F3A5F", "#1B7F79", "#C8691E", "#E8EEF5", "#F4F4F4"
def hdr(extra=""): return f'digraph G {{ {extra} graph [{F}, pad=0.15, bgcolor=white]; node [{F}, fontsize=12, style="filled,rounded", shape=box, fillcolor="{LIGHT}", color="{NAVY}", penwidth=1.3]; edge [{F}, fontsize=10, color="{NAVY}", penwidth=1.2];\n'

# Fig 1 architecture
render("fig1_architecture", hdr("rankdir=TB; nodesep=0.3; ranksep=0.5; newrank=true;") + f'''
subgraph cluster_src {{ label="SOURCE SYSTEMS"; fontsize=12; style="rounded,dashed"; color="{GREY}"; fontcolor="{NAVY}";
  s1 [label="Hospital billing /\\nHIS claim tables"]; s2 [label="Insurer adjudication\\nfeed (status, payments)"]; s3 [label="Patient registration\\nand master data"]; }}
subgraph cluster_etl {{ label="STAGING AND ETL (Python)"; fontsize=12; style="rounded,dashed"; color="{GREY}"; fontcolor="{NAVY}";
  e1 [label="1. Incremental\\nextract", fillcolor="#FBE9D8", color="{ORG}"]; e2 [label="2. Data-quality\\ngate (R1-R6)", fillcolor="#FBE9D8", color="{ORG}"];
  e3 [label="3. Transform:\\nSCD, surrogate keys", fillcolor="#FBE9D8", color="{ORG}"]; e4 [label="4. Load and\\nupsert facts", fillcolor="#FBE9D8", color="{ORG}"]; rej [label="DQ reject log\\nand ETL audit", shape=cylinder, fillcolor="white"]; }}
subgraph cluster_dw {{ label="DATA WAREHOUSE (SQLite)"; fontsize=12; style="rounded,dashed"; color="{GREY}"; fontcolor="{NAVY}";
  d1 [label="9 conformed\\ndimensions", fillcolor="#D7EEEC", color="{TEAL}"]; d2 [label="fact_claim_line\\n(transaction grain)", fillcolor="#D7EEEC", color="{TEAL}"]; d3 [label="monthly snapshot\\nfact (aggregate)", fillcolor="#D7EEEC", color="{TEAL}"]; }}
subgraph cluster_bi {{ label="ANALYTICS"; fontsize=12; style="rounded,dashed"; color="{GREY}"; fontcolor="{NAVY}";
  a1 [label="OLAP SQL queries\\n(roll-up, drill-down,\\nslice, dice)"]; a2 [label="Dashboard and\\nreports"]; }}
u [label="Claims manager\\nFinance / Analyst", shape=oval, fillcolor="white"];
{{rank=same; s1; s2; s3}} {{rank=same; e1; e2; e3; e4}} {{rank=same; d1; d2; d3}} {{rank=same; a1; a2}}
s1 -> e1; s2 -> e1; s3 -> e1; e1 -> e2 -> e3 -> e4 [constraint=false]; e1 -> e2 [constraint=false]; e2 -> rej [style=dashed]; e3 -> d1; e4 -> d2; d2 -> d3 [constraint=false]; d1 -> d2 [constraint=false, style=dotted, dir=none]; d2 -> a1; d3 -> a1; a1 -> a2 [constraint=false]; a2 -> u; a1 -> u [style=invis];
}}''')

# Fig 2 DFD level 0
render("fig2_dfd0", hdr("rankdir=LR; nodesep=0.6; ranksep=1.1;") + f'''
a [label="Hospital Billing /\\nHIS System", shape=box, style="filled", fillcolor="white"];
b [label="Insurer / TPA\\nAdjudication Feed", shape=box, style="filled", fillcolor="white"];
c [label="Claims Analyst /\\nFinance Manager", shape=box, style="filled", fillcolor="white"];
p [label="0\\nHospital Insurance-Claims\\nData Warehouse System", shape=circle, fillcolor="#D7EEEC", color="{TEAL}", width=2.3, fontsize=13];
a -> p [label="claim headers,\\nclaim lines, patient master"]; b -> p [label="status, denial reason,\\npayment amounts"];
p -> c [label="OLAP results, KPI dashboard,\\nreports"]; c -> p [label="analysis requests\\n(query parameters)"];
}}''')

# Fig 3 DFD level 1
render("fig3_dfd1", hdr("rankdir=TB; nodesep=0.35; ranksep=0.35;") + f'''
node [fontsize=11];
ext1 [label="Source\\nsystems", style=filled, fillcolor=white]; ext2 [label="Analyst", style=filled, fillcolor=white];
p1 [label="1.0\\nExtract\\n(watermark)", shape=circle, fillcolor="#FBE9D8", color="{ORG}"]; p2 [label="2.0\\nValidate\\nand clean", shape=circle, fillcolor="#FBE9D8", color="{ORG}"];
p3 [label="3.0\\nBuild\\ndimensions", shape=circle, fillcolor="#FBE9D8", color="{ORG}"]; p4 [label="4.0\\nLoad\\nfacts", shape=circle, fillcolor="#FBE9D8", color="{ORG}"];
p5 [label="5.0\\nAggregate\\nsnapshot", shape=circle, fillcolor="#FBE9D8", color="{ORG}"]; p6 [label="6.0\\nOLAP\\nquery", shape=circle, fillcolor="#D7EEEC", color="{TEAL}"];
d1 [label="D1 Staging", shape=cylinder, fillcolor=white]; d2 [label="D2 DQ reject log", shape=cylinder, fillcolor=white]; d3 [label="D3 Dimensions", shape=cylinder, fillcolor=white];
d4 [label="D4 Fact tables", shape=cylinder, fillcolor=white]; d5 [label="D5 ETL audit", shape=cylinder, fillcolor=white];
ext1 -> p1 [label="delta rows"]; p1 -> d1; d1 -> p2; p2 -> d2 [label="rejects"]; p2 -> p3 [label="clean rows"]; p3 -> d3; p3 -> p4 [label="keys"]; d3 -> p4; p4 -> d4; d4 -> p5; p5 -> d4 [label="snapshot", constraint=false]; p4 -> d5 [style=dashed]; d4 -> p6; d3 -> p6; p6 -> ext2 [label="results"]; ext2 -> p6 [label="request", constraint=false];
}}''')

# Fig 4 use case
render("fig4_usecase", hdr("rankdir=LR; nodesep=0.18; ranksep=1.3;") + f'''
node [fontsize=11];
an [label="Claims\\nAnalyst", shape=box, style=filled, fillcolor=white]; fm [label="Finance\\nManager", shape=box, style=filled, fillcolor=white];
de [label="Data\\nEngineer", shape=box, style=filled, fillcolor=white]; il [label="Insurer\\nLiaison", shape=box, style=filled, fillcolor=white];
subgraph cluster_sys {{ label="Hospital Insurance-Claims Data Warehouse"; fontsize=12; style=rounded; color="{NAVY}"; fontcolor="{NAVY}";
 node [shape=ellipse, style=filled, fillcolor="#E8EEF5"];
 u1 [label="Run incremental ETL load"]; u2 [label="Review data-quality rejects"]; u3 [label="Manage dimensions (SCD)"];
 u4 [label="Run OLAP queries"]; u5 [label="View claims dashboard"]; u6 [label="Analyse denial reasons"]; u7 [label="Track settlement ratio\\nand revenue cycle"]; u8 [label="Export reports"]; }}
de -> u1 [dir=none]; de -> u2 [dir=none]; de -> u3 [dir=none]; an -> u4 [dir=none]; an -> u5 [dir=none]; an -> u6 [dir=none];
fm -> u5 [dir=none]; fm -> u7 [dir=none]; fm -> u8 [dir=none]; il -> u6 [dir=none]; il -> u7 [dir=none];
}}''')

# Fig 7 module interaction
render("fig7_modules", hdr("rankdir=LR; nodesep=0.3; ranksep=0.4;") + f'''
m1 [label="M1\\nSource data\\nsimulation and\\nextraction"]; m2 [label="M2\\nData quality\\nand staging", fillcolor="#FBE9D8", color="{ORG}"];
m3 [label="M3\\nDimension\\nmodelling\\n(SCD-1 / SCD-2)", fillcolor="#D7EEEC", color="{TEAL}"]; m4 [label="M4\\nFact loading\\nand snapshot", fillcolor="#D7EEEC", color="{TEAL}"];
m5 [label="M5\\nOLAP analytics,\\ntesting and\\nreporting"]; au [label="ETL audit and\\nDQ reject log", shape=cylinder, fillcolor=white];
m1 -> m2 [label="delta rows"]; m2 -> m3 [label="clean rows"]; m3 -> m4 [label="surrogate keys"]; m4 -> m5 [label="facts"]; m3 -> m5 [label="dimensions", constraint=false];
m2 -> au [style=dashed]; m4 -> au [style=dashed]; m5 -> m1 [label="next batch", style=dotted, constraint=false];
}}''')

# Fig 8 ETL flowchart
render("fig8_etl_flow", hdr("rankdir=TB; nodesep=0.2; ranksep=0.18;") + f'''
node [fontsize=10.5, margin="0.10,0.04"];
st [label="Start batch", shape=oval]; w [label="Read watermark from etl_audit"]; ex [label="Extract rows with last_updated > watermark"];
dd [label="Remove duplicate claim headers (R1)"]; vr [label="Validate lines: R2 negative billed, R3 paid > allowed,\\nR4 service date range, R5 orphan line", fillcolor="#FBE9D8", color="{ORG}"];
ok [label="Line valid?", shape=diamond, style=filled, fillcolor="white", margin="0.02,0.02"]; rj [label="Write to dq_reject", shape=cylinder, fillcolor=white];
uk [label="Map missing / invalid ICD-10 to Unknown key (R6)"]; d1 [label="Upsert SCD-1 dimensions;\\nSCD-2 patient: expire old row, add new version", fillcolor="#D7EEEC", color="{TEAL}"];
lk [label="Surrogate-key and point-in-time lookup; compute measures"]; up [label="Upsert fact_claim_line on (claim_id, line_no)", fillcolor="#D7EEEC", color="{TEAL}"];
sn [label="Rebuild monthly snapshot and indexes"]; au [label="Write etl_audit row; advance watermark"]; en [label="End", shape=oval];
st -> w -> ex -> dd -> vr -> ok; ok -> rj [label=" no"]; ok -> uk [label=" yes"]; uk -> d1 -> lk -> up -> sn -> au -> en;
}}''')
print("dot figures done")
