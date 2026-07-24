# Multi-Armed Bandit Optimization API

A small FastAPI service that stores experiment results in SQLite and recommends the next-day traffic allocation for each variant using Thompson Sampling.

## Solution approach

The API supports experiments with two or more variants.

For each variant, the client submits:

- impressions
- clicks
- observation date

SQL is used to store and aggregate the historical data. The aggregated totals are then passed to the bandit engine.

I chose **Thompson Sampling** because CTR is a binary outcome:

- click = success
- no click = failure

Each variant is represented by a Beta distribution:

```text
alpha = prior_alpha + clicks
beta = prior_beta + non_clicks
```

The algorithm samples a possible CTR for every variant across multiple simulations. The percentage of simulations won by each variant becomes its `probability_best`.

The API returns both:

- `probability_best`: the raw statistical result
- `allocation`: the final traffic recommendation

These can differ because the project applies a configurable minimum allocation to keep exploration active.

Example:

```text
Raw probability:
Control: 1%
Variant: 99%

Final allocation with a minimum traffic rule:
Control: 5.9%
Variant: 94.1%
```

### Main design choices

- **FastAPI** for the REST API and generated documentation
- **SQLite** to keep the challenge easy to run without external infrastructure
- **Async SQLAlchemy** for database access
- **Thompson Sampling** for adaptive allocation
- **Beta distributions** for click/non-click rewards
- **SQL aggregation** for historical impressions and clicks
- **Upserts** so daily results can be corrected without duplicates
- **Multiple-variant support**, not only A/B tests
- **Minimum traffic allocation** to preserve exploration
- **Domain validation** inside the bandit models, independent from HTTP validation
- **Fixed random seeds in tests** to make stochastic results reproducible

The statistical code is intentionally independent from FastAPI and SQLAlchemy, which makes it easier to test and replace the database or API layer later.

## Run the project

Requirements:

- Python 3.12+
- uv

Install dependencies:

```bash
uv sync
```

Create a `.env` file at project root:

```env
ENVIRONMENT=local

API__TITLE=Multi-Armed Bandit Optimization API
API__VERSION=0.1.0
API__DEBUG=true

DATABASE__PATH=bandit.db
DATABASE__ECHO=false

THOMPSON_SAMPLING__SIMULATIONS=10000 # Number of simulations to compute probabilities
THOMPSON_SAMPLING__PRIOR_ALPHA=1.0
THOMPSON_SAMPLING__PRIOR_BETA=1.0

ALLOCATION__MINIMUM_ALLOCATION=0.05 # Minimum allocation for each variant
ALLOCATION__PERCENTAGE_PRECISION=2 # Decimal places (e.g.: 2 -> 9.45)

LOGGING__LEVEL=INFO
```

Start the API:

```bash
uv run uvicorn src.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

Run tests:

```bash
uv run pytest -v
```

## API flow

Create an experiment:

```http
POST /experiments
```

Submit daily results:

```http
POST /experiments/{experiment_id}/observations
```

Calculate the next-day allocation:

```http
GET /experiments/{experiment_id}/allocation
```

## Project structure

```text
src/
├── api/routes/          # HTTP endpoints and request/response handling
├── bandits/             # Thompson Sampling and allocation rules
├── core/                # Database, logging and shared exceptions
├── models/              # SQLAlchemy database models
├── config.py            # Typed environment configuration
└── main.py              # Application startup and router registration

tests/
├── conftest.py          # Isolated in-memory SQLite test setup
└── unit/bandits/        # Tests for models, constraints and algorithm behavior
```

### Important files

- `src/api/routes/experiments.py`  
  Creates and retrieves experiments and variants.

- `src/api/routes/observations.py`  
  Inserts or updates daily impressions and clicks.

- `src/api/routes/allocations.py`  
  Aggregates historical data with SQL and calls the bandit engine.

- `src/bandits/thompson_sampling.py`  
  Runs the simulations and calculates each variant's probability of being best.

- `src/bandits/constraints.py`  
  Normalizes allocations and applies the minimum traffic rule.

- `src/bandits/models.py`  
  Contains validated domain objects used by the statistical engine.

- `src/core/database.py`  
  Configures the async SQLite engine and sessions.

- `src/models/`  
  Defines the experiment, variant and observation tables.

## Notes

For this challenge, tables are created automatically on startup to keep setup simple.
# takehome-mutliarmedbandit
