# PostgreSQL vs MongoDB Scheduler Benchmark in Python

This project compares a PostgreSQL relational scheduling database with two MongoDB document models.

## Quick run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
docker compose -f docker/docker-compose.yml up -d