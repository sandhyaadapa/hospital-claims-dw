# ClaimsLens web application

Flask app over the claims data warehouse (SQLite star schema). Reads the database live.

1. Build the databases (see top-level README: generate_source.py, etl.py, olap.py).
2. `pip install flask`
3. `python3 app.py`  ->  open http://127.0.0.1:5000

Tabs: Dashboard (filters over the monthly snapshot), Claim lookup (search a claim and see its lines joined across every dimension), OLAP queries (run Q1-Q6 on star schema or 3NF with live timings), Patient history (SCD Type 2 versions).
