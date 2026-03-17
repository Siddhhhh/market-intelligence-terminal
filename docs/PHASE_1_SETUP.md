# Phase 1 — Development Environment Setup

## Market Intelligence Terminal

This guide walks you through installing every tool needed for the project.
Complete each section in order. Do not skip ahead.

---

## 1.1 — Prerequisites Checklist

You need the following software installed on your machine:

| Tool            | Purpose                          | Minimum Version |
|-----------------|----------------------------------|-----------------|
| Python          | Data pipeline, AI engine, API    | 3.10+           |
| Node.js         | Frontend dashboard               | 18+             |
| PostgreSQL      | Database                         | 15+             |
| TimescaleDB     | Time-series extension            | 2.x             |
| Git             | Version control                  | 2.x             |
| Ollama          | Local LLM runtime                | 0.1+            |

---

## 1.2 — Install Python

### macOS
```bash
brew install python@3.12
```

### Ubuntu / Debian
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip -y
```

### Windows
Download from https://www.python.org/downloads/
During install, CHECK "Add Python to PATH".

### Verify
```bash
python3 --version
```
Expected output: `Python 3.12.x` (or 3.10+ is fine)

---

## 1.3 — Install Node.js

### macOS
```bash
brew install node
```

### Ubuntu / Debian
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### Windows
Download from https://nodejs.org/ (LTS version)

### Verify
```bash
node --version
npm --version
```
Expected: `v20.x.x` and `10.x.x`

---

## 1.4 — Install PostgreSQL

### macOS
```bash
brew install postgresql@16
brew services start postgresql@16
```

### Ubuntu / Debian
```bash
sudo apt install postgresql postgresql-contrib -y
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### Windows
Download from https://www.postgresql.org/download/windows/
Use the installer. Remember the password you set for the `postgres` user.

### Verify
```bash
psql --version
```
Expected: `psql (PostgreSQL) 16.x`

---

## 1.5 — Install TimescaleDB

TimescaleDB is a PostgreSQL extension for time-series data.
It makes querying stock prices across date ranges extremely fast.

### macOS
```bash
brew tap timescale/tap
brew install timescaledb
timescaledb-tune --quiet --yes
brew services restart postgresql@16
```

### Ubuntu / Debian
```bash
sudo apt install gnupg postgresql-common apt-transport-https lsb-release wget -y

# Add TimescaleDB repository
echo "deb https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -cs) main" | \
  sudo tee /etc/apt/sources.list.d/timescaledb.list

wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | \
  sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/timescaledb.gpg

sudo apt update
sudo apt install timescaledb-2-postgresql-16 -y
sudo timescaledb-tune --quiet --yes
sudo systemctl restart postgresql
```

### Verify
```bash
psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```
You should see: `CREATE EXTENSION`

If you get a password prompt, use the password you set during PostgreSQL install.

---

## 1.6 — Install Ollama

Ollama runs large language models locally on your machine.

### macOS
```bash
brew install ollama
```

### Linux
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Windows
Download from https://ollama.com/download

### Start Ollama and Download Models
```bash
# Start the Ollama service (run in a separate terminal)
ollama serve

# In another terminal, download the models
ollama pull llama3
ollama pull mistral
```

This will download approximately 4-8 GB per model. Be patient.

### Verify
```bash
ollama list
```
Expected output should show `llama3` and `mistral` in the list.

Test that it works:
```bash
ollama run llama3 "Say hello in one sentence"
```
You should get a response from the model.

---

## 1.7 — Install Git

### macOS
```bash
brew install git
```

### Ubuntu / Debian
```bash
sudo apt install git -y
```

### Windows
Download from https://git-scm.com/download/win

### Verify
```bash
git --version
```

---

## 1.8 — Create the Project

Now let's create the project folder structure and initialize everything.

### Step 1: Create the project directory
```bash
mkdir -p ~/market-intelligence-terminal
cd ~/market-intelligence-terminal
```

### Step 2: Initialize Git
```bash
git init
```

### Step 3: Create the folder structure
```bash
mkdir -p backend/data_pipeline
mkdir -p backend/database
mkdir -p backend/ai_engine
mkdir -p backend/api
mkdir -p frontend
mkdir -p scripts
mkdir -p docs
```

### Step 4: Verify the structure
```bash
find . -type d | head -20
```

Expected output:
```
.
./backend
./backend/data_pipeline
./backend/database
./backend/ai_engine
./backend/api
./frontend
./scripts
./docs
```

---

## 1.9 — Set Up Python Virtual Environment

A virtual environment keeps your project's Python packages isolated.

```bash
cd ~/market-intelligence-terminal

# Create virtual environment
python3 -m venv venv

# Activate it
# macOS / Linux:
source venv/bin/activate

# Windows:
# venv\Scripts\activate
```

Your terminal prompt should now show `(venv)` at the beginning.

### Install Python Dependencies

Create the requirements file first:

```bash
cat > requirements.txt << 'EOF'
# Data Pipeline
yfinance==0.2.40
pandas==2.2.2
numpy==1.26.4
requests==2.32.3

# Database
psycopg2-binary==2.9.9
sqlalchemy==2.0.30
alembic==1.13.1

# API Server
fastapi==0.111.0
uvicorn==0.30.1
pydantic==2.7.4

# AI Engine
ollama==0.2.1
langchain==0.2.5
langchain-community==0.2.5

# Scheduling
schedule==1.2.2
python-crontab==3.1.0

# Utilities
python-dotenv==1.0.1
loguru==0.7.2
tqdm==4.66.4
EOF
```

Now install everything:

```bash
pip install -r requirements.txt
```

This will take a few minutes. If you see errors about `psycopg2-binary`, make sure PostgreSQL is installed first.

### Verify key packages
```bash
python3 -c "import yfinance; print('yfinance:', yfinance.__version__)"
python3 -c "import pandas; print('pandas:', pandas.__version__)"
python3 -c "import sqlalchemy; print('sqlalchemy:', sqlalchemy.__version__)"
python3 -c "import fastapi; print('fastapi:', fastapi.__version__)"
python3 -c "import ollama; print('ollama: OK')"
```

All five should print without errors.

---

## 1.10 — Create the Database

### Step 1: Connect to PostgreSQL
```bash
# macOS / Linux:
sudo -u postgres psql

# If that doesn't work (especially on macOS with Homebrew):
psql -U postgres

# Windows:
# Open pgAdmin or use:
# psql -U postgres
```

### Step 2: Create the database and user
Run these SQL commands inside the `psql` prompt:

```sql
-- Create dedicated user
CREATE USER market_user WITH PASSWORD 'market_pass_2024';

-- Create the database
CREATE DATABASE market_intelligence OWNER market_user;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE market_intelligence TO market_user;

-- Connect to the new database
\c market_intelligence

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Exit
\q
```

### Step 3: Verify the connection
```bash
psql -U market_user -d market_intelligence -c "SELECT version();"
```

If prompted for a password, enter: `market_pass_2024`

You should see PostgreSQL version information.

---

## 1.11 — Create Environment Configuration

Create a `.env` file to store configuration securely:

```bash
cd ~/market-intelligence-terminal

cat > .env << 'EOF'
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=market_intelligence
DB_USER=market_user
DB_PASSWORD=market_pass_2024

# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3

# API
API_HOST=0.0.0.0
API_PORT=8000

# Data
DATA_START_DATE=1990-01-01
SP500_ENABLED=true
CRYPTO_ENABLED=true
EOF
```

### Create .gitignore to protect secrets

```bash
cat > .gitignore << 'EOF'
# Environment
.env
venv/
__pycache__/
*.pyc

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Data
*.csv
*.parquet
data/raw/

# Node
node_modules/
.next/
EOF
```

---

## 1.12 — Final Verification Script

Create and run this script to verify everything is working:

```bash
cat > scripts/verify_setup.py << 'PYEOF'
"""
Market Intelligence Terminal — Setup Verification
Run this to confirm all dependencies are correctly installed.
"""

import sys
import subprocess

def check(name, test_fn):
    try:
        result = test_fn()
        print(f"  [OK]  {name}: {result}")
        return True
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        return False

def main():
    print("\n" + "=" * 60)
    print("  MARKET INTELLIGENCE TERMINAL — SETUP VERIFICATION")
    print("=" * 60 + "\n")

    results = []

    # Python version
    results.append(check(
        "Python version",
        lambda: f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ))

    # Key packages
    results.append(check("yfinance", lambda: __import__("yfinance").__version__))
    results.append(check("pandas", lambda: __import__("pandas").__version__))
    results.append(check("numpy", lambda: __import__("numpy").__version__))
    results.append(check("sqlalchemy", lambda: __import__("sqlalchemy").__version__))
    results.append(check("fastapi", lambda: __import__("fastapi").__version__))
    results.append(check("psycopg2", lambda: __import__("psycopg2").__version__))
    results.append(check("ollama", lambda: __import__("ollama") and "installed"))
    results.append(check("loguru", lambda: __import__("loguru") and "installed"))
    results.append(check("tqdm", lambda: __import__("tqdm").__version__))
    results.append(check("dotenv", lambda: __import__("dotenv") and "installed"))

    # Database connection
    def test_db():
        from sqlalchemy import create_engine, text
        from dotenv import load_dotenv
        import os
        load_dotenv()
        url = (
            f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
            f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
        )
        engine = create_engine(url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
        return version[:40] + "..."

    results.append(check("PostgreSQL connection", test_db))

    # TimescaleDB
    def test_timescale():
        from sqlalchemy import create_engine, text
        from dotenv import load_dotenv
        import os
        load_dotenv()
        url = (
            f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
            f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
        )
        engine = create_engine(url)
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
            )
            row = result.fetchone()
            if row:
                return f"v{row[0]}"
            return "NOT INSTALLED"

    results.append(check("TimescaleDB extension", test_timescale))

    # Node.js
    def test_node():
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        return result.stdout.strip()

    results.append(check("Node.js", test_node))

    # Ollama
    def test_ollama():
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            models = [l.split()[0] for l in lines[1:] if l.strip()]
            return f"{len(models)} model(s): {', '.join(models[:3])}"
        return "Service not running — start with: ollama serve"

    results.append(check("Ollama", test_ollama))

    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {passed}/{total} checks passed")
    if passed == total:
        print("  STATUS: All systems go! Ready for Phase 2.")
    else:
        print("  STATUS: Some checks failed. Fix them before continuing.")
    print(f"{'=' * 60}\n")

if __name__ == "__main__":
    main()
PYEOF
```

### Run the verification:
```bash
cd ~/market-intelligence-terminal
source venv/bin/activate
python3 scripts/verify_setup.py
```

---

## 1.13 — Create Base Project Configuration

```bash
cd ~/market-intelligence-terminal

cat > backend/__init__.py << 'EOF'
EOF

cat > backend/data_pipeline/__init__.py << 'EOF'
EOF

cat > backend/database/__init__.py << 'EOF'
EOF

cat > backend/ai_engine/__init__.py << 'EOF'
EOF

cat > backend/api/__init__.py << 'EOF'
EOF

cat > backend/config.py << 'PYEOF'
"""
Central configuration for Market Intelligence Terminal.
Loads settings from .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Database
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "market_intelligence")
    DB_USER: str = os.getenv("DB_USER", "market_user")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "market_pass_2024")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # Ollama
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

    # API
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    # Data parameters
    DATA_START_DATE: str = os.getenv("DATA_START_DATE", "1990-01-01")
    SP500_ENABLED: bool = os.getenv("SP500_ENABLED", "true").lower() == "true"
    CRYPTO_ENABLED: bool = os.getenv("CRYPTO_ENABLED", "true").lower() == "true"


settings = Settings()
PYEOF
```

---

## Troubleshooting

### "psycopg2 failed to install"
Install the PostgreSQL development headers:
```bash
# Ubuntu/Debian
sudo apt install libpq-dev python3-dev -y

# macOS
brew install libpq
```

### "permission denied" on PostgreSQL
```bash
# Reset the postgres user password
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'your_password';"
```

### "ollama: command not found"
Make sure Ollama is in your PATH. Try restarting your terminal.

### "TimescaleDB extension not found"
Make sure you ran `timescaledb-tune` and restarted PostgreSQL.
Check that the shared library is loaded:
```bash
psql -U postgres -c "SHOW shared_preload_libraries;"
```
It should include `timescaledb`.

---

## What's Next

Once ALL checks pass in the verification script, you are ready for:

**Phase 2 — Database Schema Design**

We will create the full database schema with tables for:
- companies
- stocks (time-series with TimescaleDB hypertable)
- crypto_prices
- market_events
- macro_events
- sectors

Tell me when you're ready to proceed.
