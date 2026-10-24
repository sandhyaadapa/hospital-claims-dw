"""Reference (master) data used by the synthetic source-system generator."""
import datetime as dt

CUT1 = dt.date(2024, 12, 31)   # business date of batch 1 (initial load)
CUT2 = dt.date(2025, 12, 31)   # business date of batch 2 (incremental load)
DATA_START = dt.date(2023, 1, 1)
LAST_ADMISSION = dt.date(2025, 12, 20)

HOSPITALS = [  # id, name, city, ownership, beds, tariff multiplier
    ("H01", "Godavari Multispeciality Hospital", "Eluru", "Corporate", 320, 1.20),
    ("H02", "Krishna Institute of Medical Care", "Vijayawada", "Corporate", 450, 1.25),
    ("H03", "Sagar Super Speciality Hospital", "Visakhapatnam", "Corporate", 500, 1.30),
    ("H04", "Amaravati General Hospital", "Guntur", "Trust", 260, 0.90),
    ("H05", "Rajahmundry Community Hospital", "Rajahmundry", "Trust", 180, 0.85),
    ("H06", "Tirumala Heart and Kidney Centre", "Tirupati", "Corporate", 280, 1.15),
    ("H07", "Kakinada District Hospital", "Kakinada", "Government", 400, 0.70),
    ("H08", "Nellore Medical College Hospital", "Nellore", "Government", 600, 0.72),
]

# id, name, type, denial multiplier, mean adjudication lag (days), tariff ratio (allowed/billed)
INSURERS = [
    ("I01", "Sanjeevani Health Insurance", "Private", 0.9, 11, 0.93),
    ("I02", "Arogya Mutual General", "Private", 1.1, 15, 0.90),
    ("I03", "Suraksha Care TPA", "TPA", 1.5, 24, 0.86),
    ("I04", "Bharat Swasthya Assurance", "Private", 0.7, 9, 0.95),
    ("I05", "State Health Assurance Trust", "Government", 1.2, 30, 0.82),
    ("I06", "Kalyan Corporate Health", "Private", 0.8, 13, 0.92),
]
# plan tiers: name, sum insured, co-pay %
TIERS = [("Basic", 300000, 20), ("Standard", 500000, 10), ("Premium", 1000000, 0)]

SPECIALTIES = ["General Medicine", "Cardiology", "Nephrology", "Orthopaedics",
               "Obstetrics and Gynaecology", "General Surgery", "Pulmonology",
               "Oncology", "Ophthalmology", "Gastroenterology", "Neurology"]

# code: (description, category, base unit rate INR)
PROCS = {
 "ROOM": ("General ward bed charge (per day)", "Accommodation", 2500),
 "ICU": ("ICU bed charge (per day)", "Accommodation", 9000),
 "CONS": ("Doctor consultation / visit", "Professional fees", 800),
 "HEM": ("Haematology investigations", "Laboratory", 600),
 "BIO": ("Biochemistry investigations", "Laboratory", 1400),
 "XRAY": ("X-ray", "Imaging", 700),
 "USG": ("Ultrasonography", "Imaging", 1200),
 "CT": ("CT scan", "Imaging", 4500),
 "MRI": ("MRI scan", "Imaging", 8500),
 "ECG": ("ECG / Echocardiography", "Cardiac diagnostics", 2200),
 "PHARM": ("Pharmacy and consumables (bundle)", "Pharmacy", 3500),
 "OT": ("Operation theatre charges", "Surgical", 15000),
 "ANAES": ("Anaesthesia charges", "Surgical", 12000),
 "SURGMIN": ("Minor surgical procedure", "Surgical", 18000),
 "SURGMAJ": ("Major surgical procedure", "Surgical", 85000),
 "DIAL": ("Haemodialysis session", "Renal", 3200),
 "CHEMO": ("Chemotherapy cycle", "Oncology", 45000),
 "PHYSIO": ("Physiotherapy session", "Rehabilitation", 700),
 "BLOOD": ("Blood transfusion (per unit)", "Blood bank", 2800),
 "AMB": ("Ambulance transfer", "Transport", 2500),
 "LABOUR": ("Labour room charges", "Obstetric", 9000),
 "PHACO": ("Phacoemulsification with IOL", "Ophthalmic", 32000),
 "PTCA": ("Coronary angioplasty with stent", "Cardiac procedures", 190000),
 "JOINT": ("Joint replacement surgery", "Orthopaedic", 240000),
}
PROC_CODE = {k: f"PR{str(i+1).zfill(3)}" for i, k in enumerate(PROCS)}

# icd10, description, ICD chapter, chronic, weight, specialty, (agemin, agemax), sex,
# (los_min, los_max), P(emergency), P(daycare), season, denial multiplier, extras[(proc, prob, qmin, qmax)]
DX = [
 ("A01.0", "Typhoid fever", "Infectious and parasitic diseases", 0, 3.0, "General Medicine", (3, 70), None, (3, 6), .5, 0, "monsoon", .8, [("HEM", 1, 1, 3), ("BIO", .8, 1, 2), ("PHARM", 1, 1, 2)]),
 ("A09", "Infectious gastroenteritis and colitis, unspecified", "Infectious and parasitic diseases", 0, 3.5, "General Medicine", (1, 80), None, (2, 4), .6, 0, "monsoon", .7, [("HEM", .9, 1, 2), ("BIO", .6, 1, 1), ("PHARM", 1, 1, 2)]),
 ("A90", "Dengue fever", "Infectious and parasitic diseases", 0, 4.0, "General Medicine", (3, 70), None, (3, 7), .6, 0, "monsoon", .8, [("HEM", 1, 2, 5), ("BIO", .8, 1, 2), ("PHARM", 1, 1, 3), ("BLOOD", .08, 1, 3)]),
 ("B50.9", "Plasmodium falciparum malaria, unspecified", "Infectious and parasitic diseases", 0, 2.0, "General Medicine", (3, 70), None, (3, 6), .6, 0, "monsoon", .8, [("HEM", 1, 1, 3), ("BIO", .7, 1, 2), ("PHARM", 1, 1, 2)]),
 ("U07.1", "COVID-19, virus identified", "Special purposes", 0, 1.2, "Pulmonology", (5, 85), None, (4, 9), .7, 0, "winter", 1.0, [("HEM", 1, 2, 4), ("BIO", 1, 1, 3), ("CT", .5, 1, 1), ("ICU", .15, 1, 4), ("PHARM", 1, 2, 4)]),
 ("J18.9", "Pneumonia, unspecified organism", "Respiratory system", 0, 6.0, "Pulmonology", (1, 85), None, (3, 8), .7, 0, "winter", .9, [("HEM", 1, 1, 3), ("XRAY", .9, 1, 2), ("CT", .2, 1, 1), ("ICU", .12, 1, 4), ("PHARM", 1, 1, 3)]),
 ("J45.9", "Asthma, unspecified", "Respiratory system", 1, 3.0, "Pulmonology", (2, 75), None, (2, 5), .7, 0, "winter", .8, [("XRAY", .6, 1, 1), ("HEM", .7, 1, 1), ("PHARM", 1, 1, 2)]),
 ("J44.9", "Chronic obstructive pulmonary disease, unspecified", "Respiratory system", 1, 3.0, "Pulmonology", (45, 90), None, (3, 8), .7, 0, "winter", 1.0, [("XRAY", .8, 1, 2), ("HEM", .8, 1, 2), ("ICU", .15, 1, 3), ("PHARM", 1, 1, 3)]),
 ("E11.9", "Type 2 diabetes mellitus without complications", "Endocrine, nutritional and metabolic diseases", 1, 7.0, "General Medicine", (30, 85), None, (2, 5), .3, .05, None, 1.1, [("BIO", 1, 1, 3), ("HEM", .8, 1, 1), ("ECG", .3, 1, 1), ("PHARM", 1, 1, 2)]),
 ("I10", "Essential (primary) hypertension", "Circulatory system", 1, 6.0, "Cardiology", (30, 90), None, (1, 4), .3, .1, None, 1.0, [("ECG", .7, 1, 1), ("BIO", .6, 1, 2), ("PHARM", 1, 1, 2)]),
 ("I21.9", "Acute myocardial infarction, unspecified", "Circulatory system", 0, 3.2, "Cardiology", (40, 90), None, (4, 9), .95, 0, None, 1.3, [("ECG", 1, 1, 2), ("BIO", 1, 1, 2), ("ICU", 1, 2, 4), ("PTCA", .45, 1, 1), ("OT", .45, 1, 1), ("PHARM", 1, 2, 4), ("AMB", .5, 1, 1)]),
 ("I50.9", "Heart failure, unspecified", "Circulatory system", 1, 2.5, "Cardiology", (50, 90), None, (4, 9), .8, 0, None, 1.2, [("ECG", 1, 1, 2), ("BIO", 1, 1, 2), ("XRAY", .8, 1, 1), ("ICU", .3, 1, 3), ("PHARM", 1, 2, 4)]),
 ("I63.9", "Cerebral infarction, unspecified", "Circulatory system", 0, 2.2, "Neurology", (45, 90), None, (4, 10), .9, 0, None, 1.3, [("CT", 1, 1, 1), ("MRI", .6, 1, 1), ("ICU", .35, 1, 4), ("PHYSIO", .8, 3, 8), ("PHARM", 1, 2, 4), ("AMB", .5, 1, 1)]),
 ("N18.9", "Chronic kidney disease, unspecified", "Genitourinary system", 1, 3.0, "Nephrology", (35, 85), None, (1, 3), .4, .1, None, 1.2, [("DIAL", .95, 1, 3), ("BIO", 1, 1, 3), ("HEM", .8, 1, 2), ("BLOOD", .1, 1, 2), ("PHARM", 1, 1, 2)]),
 ("N20.0", "Calculus of kidney", "Genitourinary system", 0, 2.8, "Nephrology", (20, 75), None, (1, 3), .4, .2, None, .9, [("USG", 1, 1, 1), ("OT", .6, 1, 1), ("ANAES", .6, 1, 1), ("SURGMIN", .6, 1, 1), ("PHARM", 1, 1, 2)]),
 ("N39.0", "Urinary tract infection, site not specified", "Genitourinary system", 0, 3.0, "General Medicine", (5, 85), None, (2, 5), .5, 0, None, .7, [("BIO", .8, 1, 2), ("HEM", .8, 1, 1), ("USG", .4, 1, 1), ("PHARM", 1, 1, 2)]),
 ("K35.8", "Acute appendicitis, other and unspecified", "Digestive system", 0, 3.0, "General Surgery", (6, 70), None, (2, 5), .9, 0, None, .8, [("USG", .8, 1, 1), ("OT", 1, 1, 1), ("ANAES", 1, 1, 1), ("SURGMIN", 1, 1, 1), ("HEM", 1, 1, 2), ("PHARM", 1, 1, 3)]),
 ("K80.2", "Calculus of gallbladder without cholecystitis", "Digestive system", 0, 3.0, "General Surgery", (25, 75), None, (1, 3), .2, .2, None, .9, [("USG", 1, 1, 1), ("OT", 1, 1, 1), ("ANAES", 1, 1, 1), ("SURGMIN", 1, 1, 1), ("BIO", .8, 1, 1), ("PHARM", 1, 1, 2)]),
 ("K29.7", "Gastritis, unspecified", "Digestive system", 0, 2.0, "Gastroenterology", (15, 80), None, (1, 3), .4, .2, None, .7, [("HEM", .7, 1, 1), ("PHARM", 1, 1, 2)]),
 ("K74.6", "Other and unspecified cirrhosis of liver", "Digestive system", 1, 1.6, "Gastroenterology", (35, 80), None, (4, 10), .7, 0, None, 1.4, [("BIO", 1, 2, 4), ("HEM", 1, 2, 3), ("USG", 1, 1, 1), ("BLOOD", .3, 1, 3), ("ICU", .2, 1, 3), ("PHARM", 1, 2, 4)]),
 ("O80", "Single spontaneous delivery", "Pregnancy, childbirth and the puerperium", 0, 4.5, "Obstetrics and Gynaecology", (19, 38), "F", (2, 3), .3, 0, None, .6, [("LABOUR", 1, 1, 1), ("USG", .8, 1, 1), ("HEM", 1, 1, 2), ("PHARM", 1, 1, 2)]),
 ("O82", "Encounter for caesarean delivery without indication", "Pregnancy, childbirth and the puerperium", 0, 3.8, "Obstetrics and Gynaecology", (19, 40), "F", (4, 6), .35, 0, None, .6, [("OT", 1, 1, 1), ("ANAES", 1, 1, 1), ("SURGMIN", 1, 1, 1), ("LABOUR", .4, 1, 1), ("HEM", 1, 1, 2), ("USG", .8, 1, 1), ("PHARM", 1, 2, 3)]),
 ("S72.0", "Fracture of neck of femur", "Injury and external causes", 0, 1.6, "Orthopaedics", (50, 90), None, (5, 10), .9, 0, None, 1.0, [("XRAY", 1, 1, 3), ("OT", 1, 1, 1), ("ANAES", 1, 1, 1), ("JOINT", .6, 1, 1), ("SURGMAJ", .4, 1, 1), ("PHYSIO", 1, 3, 8), ("BLOOD", .4, 1, 3), ("PHARM", 1, 2, 4), ("AMB", .5, 1, 1)]),
 ("S52.5", "Fracture of lower end of radius", "Injury and external causes", 0, 2.6, "Orthopaedics", (8, 80), None, (1, 3), .8, .2, None, .8, [("XRAY", 1, 1, 3), ("OT", .7, 1, 1), ("ANAES", .7, 1, 1), ("SURGMIN", .7, 1, 1), ("PHARM", 1, 1, 2)]),
 ("M17.9", "Osteoarthritis of knee, unspecified", "Musculoskeletal system", 1, 2.6, "Orthopaedics", (50, 85), None, (4, 7), .05, 0, None, 1.1, [("XRAY", 1, 1, 2), ("OT", 1, 1, 1), ("ANAES", 1, 1, 1), ("JOINT", 1, 1, 1), ("PHYSIO", 1, 3, 7), ("BLOOD", .3, 1, 2), ("PHARM", 1, 2, 4)]),
 ("M51.2", "Other thoracic, thoracolumbar and lumbosacral intervertebral disc displacement", "Musculoskeletal system", 0, 1.8, "Orthopaedics", (25, 70), None, (2, 5), .2, 0, None, .9, [("MRI", 1, 1, 1), ("PHYSIO", 1, 2, 6), ("OT", .35, 1, 1), ("ANAES", .35, 1, 1), ("SURGMAJ", .35, 1, 1), ("PHARM", 1, 1, 2)]),
 ("C50.9", "Malignant neoplasm of breast, unspecified", "Neoplasms", 1, 1.6, "Oncology", (30, 80), "F", (1, 3), .1, .5, None, 1.3, [("CHEMO", .8, 1, 2), ("CT", .5, 1, 1), ("BIO", 1, 1, 2), ("HEM", 1, 1, 2), ("OT", .25, 1, 1), ("ANAES", .25, 1, 1), ("SURGMAJ", .25, 1, 1), ("PHARM", 1, 1, 3)]),
 ("C34.9", "Malignant neoplasm of bronchus or lung, unspecified", "Neoplasms", 1, 1.4, "Oncology", (45, 85), None, (1, 4), .15, .4, None, 1.5, [("CHEMO", .85, 1, 2), ("CT", .8, 1, 1), ("BIO", 1, 1, 2), ("HEM", 1, 1, 2), ("PHARM", 1, 1, 3)]),
 ("H25.9", "Senile cataract, unspecified", "Eye and adnexa", 0, 4.5, "Ophthalmology", (50, 90), None, (1, 1), 0, .85, None, .6, [("PHACO", 1, 1, 1), ("ANAES", .5, 1, 1), ("PHARM", 1, 1, 1)]),
 ("D64.9", "Anaemia, unspecified", "Diseases of the blood", 0, 2.4, "General Medicine", (3, 85), None, (2, 5), .4, 0, None, .8, [("HEM", 1, 1, 3), ("BLOOD", .5, 1, 3), ("BIO", .6, 1, 1), ("PHARM", 1, 1, 2)]),
]
SEASON = {  # month weights (Jan..Dec)
    None: [1]*12,
    "monsoon": [.6, .5, .5, .6, .8, 1.2, 1.7, 2.0, 2.2, 1.9, 1.0, .7],
    "winter": [1.9, 1.6, 1.0, .7, .5, .5, .8, .8, .9, 1.0, 1.4, 1.9],
}
DENIAL_REASONS = (["Pre-existing condition", "Incomplete documentation", "Not medically necessary",
                   "Policy lapsed or not in force", "Waiting period not completed", "Sum insured exhausted"],
                  [.20, .30, .16, .10, .14, .10])
PARTIAL_REASONS = (["Room rent capping", "Non-payable items", "Proportionate deduction", "Exceeds package rate"],
                   [.30, .30, .20, .20])
CITIES = [("Eluru", "Andhra Pradesh", 14), ("Vijayawada", "Andhra Pradesh", 16), ("Visakhapatnam", "Andhra Pradesh", 16),
          ("Guntur", "Andhra Pradesh", 12), ("Rajahmundry", "Andhra Pradesh", 9), ("Tirupati", "Andhra Pradesh", 8),
          ("Kakinada", "Andhra Pradesh", 7), ("Nellore", "Andhra Pradesh", 7), ("Hyderabad", "Telangana", 11)]
FIRST_M = ["Ravi", "Suresh", "Venkat", "Srinivas", "Naga", "Anil", "Kiran", "Prasad", "Mahesh", "Ramesh", "Satish", "Rajesh", "Harsha", "Pavan", "Vijay", "Sai", "Krishna", "Gopal", "Mohan", "Tarun"]
FIRST_F = ["Lakshmi", "Sravani", "Padmaja", "Anitha", "Swathi", "Divya", "Sirisha", "Madhavi", "Kavitha", "Bhavani", "Sowmya", "Haritha", "Jyothi", "Rani", "Sunitha", "Deepika", "Pooja", "Vasavi", "Mounika", "Geetha"]
LAST = ["Reddy", "Naidu", "Rao", "Varma", "Sastry", "Chowdary", "Raju", "Murthy", "Kumar", "Babu", "Prasad", "Sharma", "Yadav", "Goud", "Patnaik"]
