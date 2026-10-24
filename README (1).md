# A Fact-Dimension Data-Warehouse Model for Hospital Insurance-Claims

Mini project, Dept. of AI&DS, Ramachandra College of Engineering, Eluru.
Student: Adapa Sai Sandhya | Guide: Mrs. M.S.R. Pavani

Star-schema warehouse (SQLite) with SCD Type-1/2, incremental ETL, data-quality rules and OLAP queries. All data is synthetic.

## Run
```
pip install pandas numpy matplotlib
cd src
python3 generate_source.py 1      # build source OLTP data, batch 1
python3 etl.py 1 ../data/source_batch1.db
python3 generate_source.py 2      # late-arriving changes, batch 2
python3 etl.py 2
python3 olap.py                   # Q1-Q6, star vs 3NF timings
python3 tests.py                  # 13 test cases
```
Database files are not stored in Git (they are large); the steps above rebuild them.

## App
`app/index.html` is the ClaimsLens dashboard (single file, open in a browser).

## Report
`report/Mini_Project_Report.pdf`

## Web application (for demo)
`webapp/` is a Flask app that reads the warehouse live: `cd webapp && pip install flask && python3 app.py`, then open http://127.0.0.1:5000.
