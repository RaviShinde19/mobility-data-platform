# Phase 1 — Complete Beginner Explanation

## Start Here: What Are We Even Building?

Imagine you work at **Ola or Uber**. Every day:
- Customers book rides
- Drivers pick them up
- Rides happen across cities
- Payments get processed

All of this generates **data**. Thousands of records every minute.

Now, a business person asks: *"Which city had the most rides last month?"*

You can't answer that if your data is:
- Scattered across 10 different systems
- Full of errors (someone typed "mumbai" instead of "Mumbai")
- Has duplicate records
- Isn't organized for analysis

**Our project builds a system that takes this messy data and turns it into clean, organized, queryable information.**

But we don't work at Ola. We don't have real data. So **Phase 1 is about creating realistic fake data** that we'll process in later phases.

---

## The Very First Thing: What Is This Folder Structure?

When you open the project folder, you see something like this:

```
mobility platform/
├── config/          ← Settings (like your phone's Settings app)
├── src/             ← Source code (the actual program)
├── data/            ← Where generated data goes
├── tests/           ← Code that checks if our code works
├── logs/            ← Records of what happened when program ran
├── venv/            ← Virtual environment (explained below)
├── main.py          ← The "Start" button
├── requirements.txt ← Shopping list of tools we need
└── .gitignore       ← List of files Git should ignore
```

Think of it like a kitchen:
- `config/` = Recipe card (tells us quantities, settings)
- `src/` = The chef (does the actual cooking)
- `data/` = The serving plates (where food/data ends up)
- `tests/` = Quality tester (checks if food tastes right)
- `main.py` = The "Order" button (starts everything)

Let's go through each piece, starting from the very bottom.

---

## 1. Virtual Environment (`venv/`) — Why Does This Exist?

### The Problem

Python has thousands of "packages" (tools other people wrote). For example:
- `Faker` — generates fake names, emails, phones
- `PyYAML` — reads YAML config files
- `pandas` — works with data tables
- `pytest` — runs tests

But here's the problem: **different projects need different versions of the same tool**.

```
Project A needs: pandas version 1.5
Project B needs: pandas version 2.2

If you install both globally, they FIGHT each other.
```

### The Solution: Virtual Environment

A virtual environment is like a **separate box for each project**.

```
Your Computer
├── Project A/venv/ → has pandas 1.5 (only for Project A)
├── Project B/venv/ → has pandas 2.2 (only for Project B)
└── Global Python    → stays clean, no conflicts
```

### What We Did

```bash
python -m venv venv           # Created the box
.\venv\Scripts\activate       # "Stepped into" the box
pip install -r requirements.txt  # Installed our tools INTO the box
```

### What's `requirements.txt`?

It's a **shopping list**. It tells anyone: *"To run this project, you need these exact tools."*

```
Faker==37.1.0          ← Generates fake data (names, emails, phones)
PyYAML==6.0.2          ← Reads our config.yaml file
python-dotenv==1.1.0   ← Reads secret passwords from .env file
pandas==2.2.3          ← Data table manipulation
pytest==8.3.5          ← Runs our test suite
```

Without this file, if you gave someone your code, they'd get errors because they don't have these tools installed.

> **Takeaway**: Virtual environment = isolated tool box. requirements.txt = shopping list. Every serious project has both.

---

## 2. Configuration (`config/config.yaml`) — The Brain of the Project

### The Problem: Magic Numbers

Imagine you wrote this code:

```python
# BAD — "magic numbers" embedded in code
for i in range(1000):       # Why 1000? Where did this come from?
    city = "Mumbai"          # What if I want Pune too?
    fare = random.uniform(30, 80)  # Why 30? Why 80?
```

Problems:
- If someone asks "how many customers did you generate?" you have to READ THE CODE
- If you want to change from 1000 to 5000, you have to FIND and EDIT the code
- If a number appears in 10 places, you might miss one

### The Solution: Config File

Put ALL settings in ONE file. The code READS from this file.

```yaml
# config/config.yaml — This is YAML format (like a cleaner version of JSON)

data_generation:
  num_customers: 1000    ← Change this ONE place, everywhere updates
  num_drivers: 500
  num_rides: 10000
  num_payments: 8000
```

Now our code does:

```python
# GOOD — reads from config
num_customers = config.get("data_generation", "num_customers")  # Gets 1000
```

### What's In Our Config?

Let me break down the actual file:

```yaml
# ── How much data to generate ──
data_generation:
  num_customers: 1000       # 1000 registered users
  num_drivers: 500          # 500 registered drivers
  num_rides: 10000          # 10,000 trip records
  num_payments: 8000        # 8,000 payment transactions
  random_seed: 42           # Makes random data REPRODUCIBLE (explained below)
```

```yaml
# ── Which cities and areas ──
geography:
  cities:
    - name: "Mumbai"
      areas: ["Andheri", "Bandra", "Colaba", ...]   # Real neighborhoods
      lat_range: [18.90, 19.25]                       # GPS coordinates for Mumbai
      lon_range: [72.77, 72.97]
    - name: "Pune"
      areas: ["Koregaon Park", "Hinjewadi", ...]
      ...
```

```yaml
# ── Ride behavior ──
ride_params:
  statuses:
    - status: "completed"    # 72% of rides complete successfully
      weight: 0.72
    - status: "cancelled"    # 15% get cancelled
      weight: 0.15
    - status: "ongoing"      # 8% are currently happening
      weight: 0.08
    - status: "no_show"      # 5% — driver came but customer didn't
      weight: 0.05
```

### What's "random_seed: 42"?

Random numbers in computers aren't truly random. They follow a **sequence** based on a starting number (the seed).

```
Seed 42 → generates: 0.37, 0.95, 0.12, 0.54, ...
Seed 42 → generates: 0.37, 0.95, 0.12, 0.54, ...  ← SAME sequence!
Seed 99 → generates: 0.81, 0.22, 0.67, 0.43, ...  ← Different sequence
```

Why is this useful? **Reproducibility.** If you run the program today and I run it tomorrow, we both get **the exact same data**. This makes debugging much easier.

> **Takeaway**: Config file = one place to control everything. No magic numbers in code. Seed = reproducible randomness.

---

## 3. Where Does the Data Come From? (Data Generators)

### In Real Life vs Our Project

```
REAL COMPANY (Ola/Uber):                    OUR PROJECT:
────────────────────────                     ──────────────
Customer registers on app                    Faker generates fake name/email/phone
  → data goes to User Database               → we write it to CSV file

Driver accepts a ride                        Random picks a customer + driver
  → GPS sends location data                  → random generates coordinates
  → payment service charges card              → random generates fare amount
```

We're **simulating** what a real company's systems would produce.

### The Faker Library

`Faker` is a Python library that generates realistic fake data:

```python
from faker import Faker
fake = Faker("en_IN")    # "en_IN" = English, India locale

fake.first_name()   →  "Rajesh"
fake.last_name()    →  "Sharma"  
fake.email()        →  "rajesh.sharma@gmail.com"
fake.phone_number() →  "+91 98765 43210"
```

The `"en_IN"` locale means it generates **Indian names** instead of "John Smith".

### The Four Generators — What Each One Does

We have 4 data generators. They must run in a **specific order** because they depend on each other:

```
STEP 1: Generate Customers    (no dependencies — can run first)
STEP 2: Generate Drivers      (no dependencies — can run first)
         │                │
         └────────┬───────┘
                  ↓
STEP 3: Generate Rides         (NEEDS customer_ids AND driver_ids)
                  │
                  ↓
STEP 4: Generate Payments      (NEEDS ride_ids and ride fares)
```

**Why this order?** Because a ride must say "Customer C0042 took a ride with Driver D0108". If we haven't generated customers yet, we don't have C0042 to reference!

This concept of "Task B depends on Task A" is called a **DAG** (Directed Acyclic Graph). You'll see this same pattern in:
- Phase 10 (Airflow — orchestrating pipeline tasks)
- Any data pipeline in the real world

---

## 4. Let's Walk Through Each Generator

### 4a. Customer Generator (customers.py)

**What it does**: Creates 1000 fake customers.

**Each customer has:**

| Field | Example | How It's Generated |
|-------|---------|-------------------|
| customer_id | `C0001` | Sequential: C0001, C0002, C0003... |
| first_name | `Priya` | Faker generates realistic Indian name |
| last_name | `Patel` | Faker |
| email | `priya.patel@gmail.com` | Faker |
| phone | `+91 98765 43210` | Faker |
| city | `Mumbai` | Randomly picked from our 6 cities |
| signup_date | `2025-03-15` | Random date in the last 2 years |
| is_active | `True` | 95% active, 5% inactive (realistic churn) |

**Key code explained:**

```python
# This creates a customer ID like "C0001", "C0042", "C0999"
customer_id = f"C{i:04d}"
# f"..." is an f-string (format string)
# {i:04d} means: take number i, pad it to 4 digits
# So if i=1  → "C0001"
# If i=42 → "C0042"
# If i=999 → "C0999"
```

```python
# Why 5% inactive?
is_active = random.random() > 0.05
# random.random() gives a number between 0 and 1
# If it's > 0.05 (95% chance) → True (active)
# If it's ≤ 0.05 (5% chance)  → False (inactive)
# This simulates real user churn — not everyone stays active
```

**Output:** A list of 1000 dictionaries, each looking like:
```python
{
    "customer_id": "C0001",
    "first_name": "Priya",
    "last_name": "Patel",
    "email": "priya.patel@example.com",
    "phone": "+91 98765 43210",
    "city": "Mumbai",
    "signup_date": "2025-03-15",
    "is_active": True
}
```

---

### 4b. Driver Generator (drivers.py)

**What it does**: Creates 500 fake drivers.

**Special thing — Weighted Random Selection:**

In reality, not all vehicle types are equally common. There are more Sedans than Bikes on the road. We simulate this:

```
What we DON'T do (equal probability):
  Sedan: 20% | Hatchback: 20% | SUV: 20% | Auto: 20% | Bike: 20%
  
What we DO (weighted probability — realistic):
  Sedan: 35% ████████
  Hatchback: 30% ██████
  SUV: 20% ████
  Auto: 10% ██
  Bike: 5% █
```

**How?**

```python
vehicle_types   = ["Sedan", "Hatchback", "SUV", "Auto", "Bike"]
vehicle_weights = [0.35,    0.30,        0.20,  0.10,   0.05]

# random.choices picks based on weights
vehicle_type = random.choices(vehicle_types, weights=vehicle_weights, k=1)[0]
# "Sedan" has 35% chance, "Bike" has 5% chance
```

**Ratings use Beta Distribution:**

Driver ratings aren't uniform 3.0–5.0. Most drivers are rated 4.0+. We use a mathematical distribution called "beta" to skew ratings higher:

```
What we DON'T do:        What we DO:
3.0 ████                 3.0 █
3.5 ████                 3.5 ██
4.0 ████                 4.0 ████████
4.5 ████                 4.5 ██████████████
5.0 ████                 5.0 ██████████
(Uniform — unrealistic)  (Beta — realistic, skewed high)
```

**Our actual results: Average rating was 4.43** — which feels realistic!

---

### 4c. Ride Generator (rides.py)

This is the **most complex** generator and the **core dataset**.

**What it does**: Creates 10,000 ride records.

**Referential Integrity — The Most Important Concept:**

```python
# We don't do this (WRONG):
customer_id = f"C{random.randint(1, 9999):04d}"  # Random ID — might not exist!

# We do this (RIGHT):
customer_id = random.choice(customer_ids)  # Pick from ACTUAL generated customers
```

Why does this matter? Because later (Phase 5), we'll JOIN rides with customers:

```
"Show me rides by customers from Mumbai"

  Ride R00742: customer_id = C0231
       ↓ JOIN
  Customer C0231: city = Mumbai  ✅ FOUND!

  If C0231 didn't exist in customers, the join would FAIL.
```

**Peak Hour Simulation:**

In reality, ride demand isn't uniform throughout the day. More people book rides during commute hours:

```
Hour:  1AM  5AM  8AM  12PM  5PM  8PM  11PM
       ▁    ▁    ████  ██   ████ ████  ▂
       Low  Low  PEAK  Med  PEAK PEAK  Low

We simulate this with weighted hour selection:
  8-10 AM: weight 1.0 (high demand — morning commute)
  5-9 PM:  weight 0.9-1.0 (high — evening commute)
  2-4 AM:  weight 0.08-0.1 (very low — most people sleeping)
```

**Intentionally Bad Data (THIS IS ON PURPOSE!):**

We deliberately create ~3% "dirty" data:

```python
# ~2% of rides have NEGATIVE distances (like a GPS error)
if random.random() < 0.02:
    distance_km = -12.5  # This is WRONG and should be caught

# ~1% have ZERO fare (like a payment bug)
if random.random() < 0.01:
    fare = 0.0  # This is WRONG

# ~3% have messy city names
messy_variants = {
    "Mumbai": ["Mumbai", "mumbai", "MUMBAI", "mumbai "],
    "Pune":   ["Pune", "pune", "PUNE", "pune "],
}
# So some rides say "mumbai" instead of "Mumbai"
```

**Why inject bad data?** Because in Phase 4, we build the **Silver layer** that CLEANS this data. If our test data is already perfect, we can't demonstrate that our cleaning code works!

**NULL values for incomplete rides:**

```
Status = "completed"  → has pickup_time AND dropoff_time
Status = "ongoing"    → has pickup_time, NO dropoff_time (still driving)
Status = "cancelled"  → MAYBE has pickup_time (50/50), NO dropoff_time
Status = "no_show"    → NO pickup_time, NO dropoff_time
```

This is realistic — not all rides have complete data.

---

### 4d. Payment Generator (payments.py)

**What it does**: Creates ~8000 payment records linked to rides.

**Key logic — Not every ride gets a payment:**

```
Ride completed  → ALWAYS has a payment (you pay for your ride)
Ride cancelled  → 30% chance of payment (cancellation fee)
Ride ongoing    → NO payment (ride isn't finished yet)
Ride no_show    → 50% chance of payment (no-show penalty)
```

This is why we generated 7,965 payments instead of 8,000 — there weren't enough eligible rides.

**Payment amount logic:**

```
Completed ride:  payment amount = ride fare (full price)
Cancelled ride:  payment amount = 10-30% of fare (cancellation fee)
Failed payment:  payment amount = ₹0 (charge didn't go through)
```

**20% of completed rides include a tip** (random ₹10–₹100).

---

## 5. Schemas (schemas.py) — The Data Contract

### What's a Schema?

A schema defines the **shape** of your data — what columns exist and what type they should be.

Think of it like a **form template**:

```
┌─────────────────────────────────┐
│ CUSTOMER REGISTRATION FORM      │
│                                 │
│ Customer ID: _______ (text)     │
│ First Name:  _______ (text)     │
│ Last Name:   _______ (text)     │
│ Email:       _______ (text)     │
│ Phone:       _______ (text)     │
│ City:        _______ (text)     │
│ Signup Date: _______ (date)     │
│ Active:      _______ (yes/no)   │
└─────────────────────────────────┘
```

In Python, we express this using **dataclasses**:

```python
@dataclass
class Customer:
    customer_id: str      # "C0001" — text
    first_name: str       # "Priya" — text
    last_name: str        # "Patel" — text
    email: str            # "priya@email.com" — text
    phone: str            # "+91..." — text
    city: str             # "Mumbai" — text
    signup_date: date     # 2025-03-15 — date (not text!)
    is_active: bool       # True or False — boolean
```

**Why do we need this?**

Without a schema, anything can happen:
```
Row 1: customer_id="C0001", fare=500.00        ← fare is a number ✅
Row 2: customer_id="C0002", fare="five hundred" ← fare is TEXT! ❌
```

The schema is a **contract**: "Every customer MUST have these exact fields with these exact types." If the data doesn't match, something is wrong.

This same schema will be reused in:
- Phase 2: To create PostgreSQL tables
- Phase 4: To define PySpark column types
- Phase 7: To configure AWS Glue catalog
- Phase 9: To create Redshift warehouse tables

---

## 6. Config Loader (config_loader.py) — Reading the Settings

This reads the `config.yaml` file and makes it accessible from any Python file.

```python
# Without config loader (BAD — hardcoded)
num_customers = 1000

# With config loader (GOOD — reads from config.yaml)
config = ConfigLoader.load()
num_customers = config.get("data_generation", "num_customers")  # → 1000
```

**How `config.get("data_generation", "num_customers")` works:**

```yaml
# config.yaml has nested structure:
data_generation:          ← Level 1 key
  num_customers: 1000     ← Level 2 key → value
  num_drivers: 500
```

```python
config.get("data_generation", "num_customers")
#           ↑ Level 1           ↑ Level 2
# Goes to data_generation → then gets num_customers → returns 1000
```

It's like giving directions: "Go to the **data_generation** section, then find **num_customers**."

---

## 7. Logger (logger.py) — Recording What Happened

### Why Not Just `print()`?

```python
# Using print() — BAD for production
print("Generated 1000 customers")
# Problems:
# - No timestamp (WHEN did this happen?)
# - No severity (is this info or an error?)
# - Disappears when terminal closes
# - Can't search through it later
```

```python
# Using logger — GOOD
logger.info("Generated 1000 customers")
# Output: 2026-09-01 21:19:18 | INFO | customers | Generated 1000 customers
#         ↑ WHEN              ↑ LEVEL ↑ WHERE     ↑ WHAT
```

**Log Levels** (from least to most severe):

```
DEBUG   → Tiny details (usually only during development)
INFO    → Normal operations ("Generated 1000 records" ✅)
WARNING → Something unusual but not broken ("47 rides had missing data" ⚠️)
ERROR   → Something failed ("Could not write to S3" ❌)
```

Our logger writes to TWO places:
1. **Console** (your terminal) — see logs while developing
2. **File** (`logs/mobility_platform.log`) — permanent record, searchable later

---

## 8. The Orchestrator (generator.py) — Putting It All Together

This is the **conductor** of the orchestra. It doesn't generate data itself — it coordinates the four generators in the right order.

```python
def run_data_generation(config):
    # Step 1: Generate customers (no dependencies)
    customers = generate_customers(1000, cities, seed=42)
    
    # Step 2: Generate drivers (no dependencies)  
    drivers = generate_drivers(500, cities, ...)
    
    # Step 3: Generate rides (NEEDS customer_ids + driver_ids)
    customer_ids = [c["customer_id"] for c in customers]  # ["C0001", "C0002", ...]
    driver_ids = [d["driver_id"] for d in drivers]         # ["D0001", "D0002", ...]
    rides = generate_rides(10000, customer_ids, driver_ids, ...)
    
    # Step 4: Generate payments (NEEDS rides data)
    payments = generate_payments(8000, rides, ...)
    
    # Step 5: Write everything to files
    write_csv(customers, "data/raw/customers/customers.csv")
    write_csv(drivers, "data/raw/drivers/drivers.csv")
    write_csv(rides, "data/raw/rides/rides.csv")
    write_csv(payments, "data/raw/payments/payments.csv")
    # Also writes JSON versions of each
```

**It also writes JSON files** because some systems prefer JSON over CSV. Having both formats demonstrates working with multiple data formats.

---

## 9. The Entry Point (main.py) — The "Start" Button

When you type `python main.py generate`, this is what happens:

```
YOU type: python main.py generate
              │         │
              ↓         ↓
         runs main.py   "generate" is the command argument
              │
              ↓
         Loads config.yaml
              │
              ↓
         Sets up logging
              │
              ↓
         Calls run_data_generation()
              │
              ↓
         Prints summary to screen
```

**Why use commands like `generate`?** Because as we add phases, main.py grows:

```
Phase 1: python main.py generate          ← Generate fake data
Phase 2: python main.py load-postgres     ← Load into database
Phase 3: python main.py upload-bronze     ← Upload to S3
Phase 4: python main.py transform-silver  ← Clean the data
...
```

One entry point, many commands. This is called a **CLI (Command Line Interface)**.

---

## 10. Tests (test_data_generator.py) — Does Our Code Actually Work?

### Why Test a Data Generator?

*"But it's just generating random data. What's there to test?"*

A LOT. If the generator produces bad data, every later phase breaks:

```
Generator makes rides with random customer_ids
  → Phase 4: PySpark join fails (customer not found)
  → Phase 5: Gold layer has missing dimensions
  → Phase 9: Redshift queries return wrong results
  → Phase 11: Dashboard shows wrong numbers
  → Recruiter: "This project is broken" ❌
```

### What Our 27 Tests Check

**Shape tests** — "Is the data the right shape?"
```python
def test_correct_count(self, customers):
    assert len(customers) == 100  # Did we get exactly 100?

def test_correct_columns(self, customers):
    # Does each record have ALL required columns?
    expected = {"customer_id", "first_name", "last_name", ...}
    for c in customers:
        assert set(c.keys()) == expected
```

**Uniqueness tests** — "Are IDs unique?"
```python
def test_unique_ids(self, customers):
    ids = [c["customer_id"] for c in customers]
    assert len(ids) == len(set(ids))  # set removes duplicates
    # If these lengths match → no duplicates ✅
```

**Referential integrity tests** — "Do references actually point to real things?"
```python
def test_referential_integrity_customers(self, rides, customers):
    valid_customer_ids = {c["customer_id"] for c in customers}
    for r in rides:
        assert r["customer_id"] in valid_customer_ids
        # Every ride's customer_id MUST exist in the customer list
```

**Distribution tests** — "Is the data realistically distributed?"
```python
def test_status_distribution(self, rides):
    statuses = {r["ride_status"] for r in rides}
    assert len(statuses) >= 2
    # Not all rides should be "completed" — some cancelled, etc.
```

**Bad data tests** — "Did we actually inject the intentional errors?"
```python
def test_has_intentional_bad_data(self, rides):
    negative_distances = [r for r in rides if r["distance_km"] < 0]
    assert len(negative_distances) >= 1
    # We WANT bad data for testing our cleaning pipeline later
```

---

## 11. The Output — What Was Actually Generated?

When you ran `python main.py generate`, it created these files:

```
data/raw/
├── customers/
│   ├── customers.csv      ← 1,000 rows, 0.08 MB
│   └── customers.json     ← Same data in JSON format
├── drivers/
│   ├── drivers.csv        ← 500 rows, 0.04 MB
│   └── drivers.json
├── rides/
│   ├── rides.csv          ← 10,000 rows, 1.65 MB ← THE BIG ONE
│   └── rides.json
└── payments/
    ├── payments.csv       ← 7,965 rows, 0.52 MB
    └── payments.json
```

### What does the data look like?

**customers.csv** (open this in Excel or VS Code):
```
customer_id,first_name,last_name,email,phone,city,signup_date,is_active
C0001,Priya,Sharma,priya@email.com,+91 98765 43210,Mumbai,2025-03-15,True
C0002,Rahul,Patel,rahul@email.com,+91 87654 32109,Pune,2024-11-22,True
C0003,Anjali,Gupta,anjali@email.com,+91 76543 21098,Bangalore,2025-07-08,False
...
```

**rides.csv:**
```
ride_id,customer_id,driver_id,pickup_city,pickup_area,...,distance_km,fare,ride_status
R00001,C0231,D0089,Mumbai,Andheri,...,12.5,487.30,completed
R00002,C0742,D0156,mumbai,Bandra,...,-3.2,0.00,cancelled    ← BAD DATA (intentional)
R00003,C0088,D0341,Pune,Hinjewadi,...,28.7,891.50,completed
...
```

### Summary of what was generated:

```
Customers: 1,000  (956 active, 44 inactive)
Drivers:   500    (avg rating 4.43)
                  (181 Sedans, 143 Hatchbacks, 104 SUVs, 48 Autos, 24 Bikes)
Rides:     10,000 (7,274 completed, 1,413 cancelled, 802 ongoing, 511 no-show)
                  (200 with negative distances, 104 with zero fare — intentional)
Payments:  7,965  (₹38.4 lakh total revenue, ₹73.8K in tips)
                  (3,128 UPI, 1,625 Credit Card, 1,236 Cash, 1,166 Debit Card, 810 Wallet)
                  (6,950 completed, 593 failed, 238 refunded, 184 pending)
```

---

## 12. The `.gitignore` File — What NOT to Share

When you put code on GitHub, you don't want to share:
- `venv/` — everyone creates their own virtual environment
- `.env` — contains passwords and API keys!
- `data/raw/` — generated data is large and regeneratable
- `logs/` — your local logs aren't useful to others
- `__pycache__/` — Python's compiled cache files

The `.gitignore` file lists all these. Git will ignore them.

---

## 13. How It All Connects — The Full Picture

```
YOU type: python main.py generate
              │
              ↓
    ┌─── main.py ───┐
    │                │
    │  1. Load       │──→ config/config.yaml (settings)
    │     config     │
    │                │
    │  2. Setup      │──→ logs/mobility_platform.log
    │     logger     │
    │                │
    │  3. Call       │──→ generator.py (orchestrator)
    │     generator  │        │
    │                │        ├→ customers.py → 1000 customers
    │                │        ├→ drivers.py   → 500 drivers
    │                │        ├→ rides.py     → 10000 rides
    │                │        └→ payments.py  → 7965 payments
    │                │              │
    │  4. Write      │              ↓
    │     files      │──→ data/raw/customers/customers.csv + .json
    │                │──→ data/raw/drivers/drivers.csv + .json
    │                │──→ data/raw/rides/rides.csv + .json
    │                │──→ data/raw/payments/payments.csv + .json
    │                │
    │  5. Print      │──→ Summary to your terminal
    │     summary    │
    └────────────────┘
```

---

## 14. What Happens Next (Phase 2 Preview)

Right now our data sits in CSV files on your laptop. That's not very useful. You can't easily ask: *"What's the average fare in Mumbai?"*

In **Phase 2**, we'll:
1. Install Docker (a tool that runs a database on your laptop)
2. Start PostgreSQL (a relational database)
3. Create tables matching our schemas
4. Load our CSV data INTO the database
5. Write SQL queries to answer business questions

```
Phase 1 (done):  Python → CSV files (sitting on disk)
Phase 2 (next):  CSV files → PostgreSQL → SQL queries → answers!
```

---

## Try These Things Now

1. **Open the CSV files** — Go to `data/raw/rides/rides.csv` and look at the data in VS Code or Excel

2. **Find the bad data** — Search for negative distances or zero fares in the rides CSV

3. **Re-run with different volume** — Try generating more data:
   ```bash
   .\venv\Scripts\activate
   python main.py generate --count 50000
   ```

4. **Run the tests** — See all 27 pass:
   ```bash
   pytest tests/ -v
   ```

5. **Read the log** — Open `logs/mobility_platform.log` and see the structured output

6. **Change config** — Edit `config/config.yaml`, change `num_rides` to 500, re-run, see fewer rides generated

Tell me when you're ready for Phase 2, or ask any questions about Phase 1! 🚀
