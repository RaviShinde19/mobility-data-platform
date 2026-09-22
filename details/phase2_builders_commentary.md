# Phase 2 — Builder's Commentary 🧠

> This is a narrated replay of how Phase 2 was built. 
> It shows the EXACT thought process, in the EXACT order things were created.
> Read this like you're sitting next to the builder, watching them think out loud.

---

## Step 0: Before Writing Any Code — The Thinking

Before I touched a single file, I asked myself:

**"What is the end state?"**
→ I need `python main.py load-postgres` to work. That means:
  - PostgreSQL must be running (Docker)
  - Tables must exist (SQL DDL)
  - Python must connect to PostgreSQL (connection module)
  - Python must create tables (schema module)
  - Python must load CSVs into tables (loader module)
  - Roles must be set up (RBAC)
  - main.py must tie it all together (CLI)

**"What depends on what?"**
→ I drew this dependency chain in my head:

```
Docker running
    ↓
connection.py works (needs Docker)
    ↓
create_tables.sql exists (just a file, no dependency)
    ↓
schema.py works (needs connection.py + create_tables.sql)
    ↓
loader.py works (needs schema.py to create tables first)
    ↓
create_roles.sql exists (just a file)
    ↓
main.py ties everything together
    ↓
test_database.py verifies it all
```

**KEY INSIGHT**: The build order follows the dependency chain.
You CANNOT write `loader.py` before `connection.py` — it needs a connection to load data!
You CANNOT write `schema.py` before `create_tables.sql` — it needs SQL to execute!

This is called a **DAG (Directed Acyclic Graph)** — the same concept we use when loading tables in order (customers before rides before payments).

---

## Step 1: Docker Compose — The Foundation

### What I thought:
> "Before ANY Python code, PostgreSQL needs to exist. Without a running database, 
> I can't test anything. Docker is the foundation — it must come first."

### What I created:

**File: `docker/docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:16-alpine    # WHY alpine? Smaller download (~80MB vs ~400MB)
    container_name: mobility-postgres  # WHY named? So we can reference it easily
    env_file: .env               # WHY env_file? Password comes from .env, not hardcoded
    ports:
      - "5432:5432"              # WHY this port? 5432 is PostgreSQL's default
    volumes:
      - mobility-pgdata:/var/lib/postgresql/data  # WHY volume? Data survives restarts
    healthcheck:
      test: pg_isready -U mobility_admin  # WHY? So we KNOW when it's ready, not guess
```

**My thought on each decision:**

| Decision | Why |
|----------|-----|
| `postgres:16-alpine` not `postgres:latest` | `latest` changes over time → breaks reproducibility. Pin the version. |
| Named container `mobility-postgres` | If I run `docker ps`, I see a readable name, not `abc123xyz` |
| `env_file: .env` | AGENTS.md Rule 1: "Zero Hardcoded Secrets". Password lives in `.env`, which is gitignored |
| Volume `mobility-pgdata` | Without this, `docker compose down` DELETES all your data. With it, data persists. |
| Health check | `docker compose up` returns immediately, but PostgreSQL takes 2-3 seconds to start. The health check tells us WHEN it's actually ready to accept connections. |

**Then I created `docker/.env` and `docker/.env.example`:**

Why TWO files? 
- `.env` = your actual password (gitignored — never goes to GitHub)
- `.env.example` = template showing what variables are needed (committed — helps teammates)

### How to verify this step worked:
```bash
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml ps
# Should show: mobility-postgres  running (healthy)
```

---

## Step 2: SQL DDL — Define the Table Structure

### What I thought:
> "Now PostgreSQL is running, but it's empty — no tables. I need to define 
> the SHAPE of the data: what columns, what types, what rules."
>
> "I'll write pure SQL first, NOT Python. Why? Because SQL is the source 
> of truth for the schema. If I hardcode SQL inside Python strings, it 
> becomes impossible to read, edit, or use with other tools."

### What I created:

**File: `sql/ddl/create_tables.sql`**

**Order of tables in the file matters!** I wrote them in dependency order:

```
1. customers  ← no foreign keys, depends on nothing
2. drivers    ← no foreign keys, depends on nothing  
3. rides      ← FK → customers AND FK → drivers (MUST come after both!)
4. payments   ← FK → rides AND FK → customers (MUST come after rides!)
```

**If I wrote `rides` BEFORE `customers`**, PostgreSQL would say:
```
ERROR: relation "customers" does not exist
```
Because the FK `REFERENCES customers(customer_id)` tries to point to a table that doesn't exist yet!

**Key decisions in the SQL:**

```sql
-- WHY DECIMAL(10,2) for fare, not FLOAT?
fare DECIMAL(10,2)  
-- FLOAT stores 0.1 as 0.10000000000000001 (binary approximation)
-- DECIMAL stores 0.1 as exactly 0.10 (exact decimal)
-- NEVER use FLOAT for money. Banks use DECIMAL. So do we.

-- WHY CHECK constraints?
CHECK (distance_km >= 0)
CHECK (fare >= 0)
-- Our Phase 1 data has ~200 rides with negative distances (intentional bad data)
-- The database should REJECT them. This is our first validation layer.

-- WHY indexes?
CREATE INDEX idx_rides_customer ON rides(customer_id);
-- Without an index, finding rides for customer C0500 scans ALL 10,000 rows
-- With an index, it jumps directly to C0500's rides. Like a book's index vs reading every page.
```

---

## Step 3: connection.py — The Bridge Between Python and PostgreSQL

### What I thought:
> "Now I have PostgreSQL (running) and SQL (written). I need Python to 
> TALK to PostgreSQL. This is the bridge. Every other module will use this."
>
> "This module must be ROCK SOLID because everything depends on it.
> If the connection fails, nothing else works."

### What I created:

**File: `src/database/connection.py`**

**Why a context manager?** 

```python
# BAD — what if line 3 throws an error? Connection NEVER closes. Leaked!
conn = psycopg2.connect(...)
cur = conn.cursor()
cur.execute("SELECT * FROM nonexistent_table")  # BOOM! Error!
conn.close()  # This line NEVER runs

# GOOD — context manager guarantees cleanup
with get_connection() as conn:
    cur = conn.cursor()
    cur.execute("SELECT * FROM nonexistent_table")  # BOOM! Error!
# conn.close() runs AUTOMATICALLY, even after the error
```

**Where does the password come from?** (This was a deliberate chain of lookups)

```python
# Priority order:
# 1. Environment variable POSTGRES_PASSWORD (highest priority — for Docker/CI)
# 2. docker/.env file (loaded by python-dotenv)
# 3. NEVER from config.yaml or hardcoded strings

password = os.environ.get("POSTGRES_PASSWORD")
if not password:
    load_dotenv("docker/.env")     # reads the .env file into environment
    password = os.environ.get("POSTGRES_PASSWORD")
```

**Why this priority?** In production:
- Docker sets `POSTGRES_PASSWORD` as an environment variable automatically
- In CI/CD (GitHub Actions), you set it as a secret
- On your laptop, `docker/.env` provides it
- The code works in ALL three environments without changes

### How to verify:
```python
from src.database.connection import get_connection
with get_connection() as conn:
    cur = conn.cursor()
    cur.execute("SELECT 1;")
    print(cur.fetchone())  # (1,)
```

---

## Step 4: schema.py — Execute the DDL

### What I thought:
> "connection.py can talk to PostgreSQL. create_tables.sql defines the tables.
> Now I need a module that READS the SQL file and EXECUTES it via the connection.
> This is the glue between Step 2 and Step 3."

### What I created:

**File: `src/database/schema.py`**

```python
def create_tables():
    # 1. Find the SQL file (relative path resolution)
    sql_path = os.path.join(BASE_DIR, "..", "..", "sql", "ddl", "create_tables.sql")
    
    # 2. Read the entire file as a string
    with open(sql_path) as f:
        ddl_sql = f.read()
    
    # 3. Execute it against PostgreSQL
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(ddl_sql)  # runs ALL CREATE TABLE statements
        conn.commit()         # makes the changes permanent
```

**Why read from a file instead of writing SQL in Python?**
- SQL files get syntax highlighting in your editor
- A DBA can review the SQL without knowing Python
- You can run the same SQL file directly in `psql` for debugging
- It's the industry standard — SQL files live in `sql/` directories

**The idempotency trick:**
```sql
CREATE TABLE IF NOT EXISTS customers (...)
```
`IF NOT EXISTS` means: "Create it if it's not there. If it IS there, skip silently."
This makes the script safe to run 100 times — it won't error on the 2nd run.

---

## Step 5: loader.py — The Hardest Module 🔥

### What I thought:
> "Tables exist. Now I need to get CSV data INTO them. This is where 
> Phase 2 gets interesting — because the data has intentional bad rows."
>
> "If I just COPY the CSV directly into rides (which has CHECK fare >= 0),
> PostgreSQL will reject the ENTIRE file because of 200 bad rows. 
> That means 9,800 good rows also get thrown away. Unacceptable."
>
> "I need the STAGING PATTERN."

### The Staging Pattern — My Thought Process:

```
Problem: COPY is all-or-nothing. 1 bad row = entire file rejected.

Attempt 1 (naive): INSERT row by row, skip bad ones
  → Works but takes 200 seconds for 10,000 rows. Too slow.

Attempt 2 (staging): 
  1. COPY into a TEMP table with NO constraints → accepts ALL 10,000 rows
  2. INSERT INTO real table SELECT * FROM temp WHERE conditions pass
  3. Count: 10,000 staged - 9,780 loaded = 220 rejected
  → Fast AND handles bad data. This is the industry standard.
```

### Load order matters! (same DAG thinking as DDL):

```python
load_sequence = [
    "customers",   # 1. Load first — no dependencies
    "drivers",     # 2. Load second — no dependencies  
    "rides",       # 3. Load third — FK references customers AND drivers
    "payments",    # 4. Load last — FK references rides AND customers
]
```

**If I loaded `payments` before `rides`**: the FK check `ride_id REFERENCES rides(ride_id)` would fail because the rides table is empty!

### The Bug We Hit — Duplicate Emails:

```
psycopg2.errors.UniqueViolation: duplicate key value violates 
unique constraint "uq_customer_email"
DETAIL: Key (email)=(wkohli@example.com) already exists.
```

**What happened**: Our Phase 1 generator created two customers with the same email. The UNIQUE constraint on `email` caught it.

**How I debugged it**:
1. Read the error → it's a UNIQUE violation on email
2. The staging INSERT was `SELECT * FROM staging_customers` → this includes BOTH duplicate rows
3. PostgreSQL tries to insert both → second one violates UNIQUE → entire INSERT fails

**The fix**: `DISTINCT ON (email)` in the SELECT:
```sql
INSERT INTO customers 
SELECT DISTINCT ON (email)        -- keeps only FIRST row per email
    customer_id, first_name, ...
FROM staging_customers
ORDER BY email, customer_id       -- determines WHICH duplicate to keep
```

**Lesson**: Source data ALWAYS has duplicates. Your loader must handle dedup.

### Cascading Rejections (a real-world phenomenon):

```
customers: 1,000 staged → 998 loaded (2 rejected — dup emails)
rides:     10,000 staged → 9,780 loaded (220 rejected — bad data + orphan customers)
payments:  7,965 staged → 7,790 loaded (175 rejected — orphan rides)
```

Notice: 220 rides were rejected → 175 payments that referenced those rides ALSO got rejected. Bad data cascades downstream. This is why you load in dependency order and check FK relationships.

---

## Step 6: create_roles.sql — Security

### What I thought:
> "The data is loaded. Now I need to lock it down. AGENTS.md Rule 5 
> says we need 3 roles. Let me think about WHO needs WHAT access."

```
etl_writer   → needs everything (it loads data)
data_analyst → needs to READ everything (run queries, build reports)
bi_reader    → should ONLY see aggregated views (no raw PII like names/emails)
```

**Why views for bi_reader?**
The `customers` table has `first_name`, `last_name`, `email`, `phone` — all PII (Personally Identifiable Information). A BI tool (Tableau/PowerBI) doesn't need individual customer names. It needs aggregated metrics like "rides per city" or "revenue by month".

So I created views like:
```sql
CREATE VIEW v_rides_by_city AS
SELECT pickup_city, COUNT(*) as total_rides, AVG(fare) as avg_fare
FROM rides GROUP BY pickup_city;
```

`bi_reader` can see `v_rides_by_city` but NOT the `customers` table directly.

---

## Step 7: main.py — The Orchestrator

### What I thought:
> "All the modules work individually. Now I need ONE command that runs 
> everything in the right order. Same pattern as Phase 1's `generate` command."

```
python main.py load-postgres
    │
    ├─ [1/4] test_connection()     → Can we reach PostgreSQL?
    ├─ [2/4] create_tables()       → DDL execution
    ├─ [3/4] load_all_tables()     → Staging pattern for all 4 CSVs
    └─ [4/4] create_roles()        → RBAC setup
```

**Why test_connection() first?** If Docker isn't running, we want a clear message:
```
❌ Cannot connect to PostgreSQL!
   Make sure Docker is running:
   docker compose -f docker/docker-compose.yml up -d
```
Not a scary traceback that a beginner can't understand.

---

## Step 8: test_database.py — Prove It Works

### What I thought:
> "How do I PROVE all of this works? Not just 'it ran without errors' but 
> 'the data is correct, the constraints are active, the roles are enforced'."

I organized tests by WHAT they verify:

```
TestConnection          → Is the engine alive?
TestSchema              → Are the tables shaped correctly?
TestDataLoading         → Are the row counts right?
TestConstraints         → Do constraints actually reject bad data?
TestReferentialIntegrity → Are all FK relationships valid?
TestRBAC                → Can analysts NOT delete data?
```

**The auto-skip trick:**
```python
@pytest.fixture(scope="session", autouse=True)
def require_postgres():
    if not test_connection():
        pytest.skip("PostgreSQL is not running")
```

This means: if Docker is off, skip ALL database tests gracefully (not crash with an error). Phase 1 tests still run fine.

---

## The Complete Build Order (Summary)

```
1. docker-compose.yml  → Foundation (PostgreSQL exists)
2. .env + .env.example → Credentials (secure)  
3. create_tables.sql   → Table structure (SQL, no Python yet)
4. connection.py       → Python ↔ PostgreSQL bridge
5. schema.py           → Execute DDL via Python
6. loader.py           → CSV → staging → validate → load
7. create_roles.sql    → RBAC security
8. main.py update      → Orchestrate everything
9. test_database.py    → Prove it all works
```

Each step depends on the ones before it. You cannot shuffle this order.
