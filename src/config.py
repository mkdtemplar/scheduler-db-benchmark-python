from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    postgres_dsn: str
    mongo_uri: str
    mongo_db: str
    results_dir: Path
    charts_dir: Path
    dashboard_dir: Path
    explain_dir: Path


def get_settings() -> Settings:
    return Settings(
        postgres_dsn=os.getenv(
            "POSTGRES_DSN",
            "postgresql://scheduling:scheduling@localhost:5433/scheduling",
        ),
        mongo_uri=os.getenv(
            "MONGO_URI",
            "mongodb://scheduling:scheduling@localhost:27017/?authSource=admin",
        ),
        mongo_db=os.getenv("MONGO_DB", "scheduling_benchmark"),
        results_dir=ROOT_DIR / "results",
        charts_dir=ROOT_DIR / "results" / "charts",
        dashboard_dir=ROOT_DIR / "dashboard",
        explain_dir=ROOT_DIR / "explain",
    )


TABLES = [
    "admins",
    "positions",
    "users",
    "shifts",
    "annual_leaves",
    "daily_schedules",
    "daily_schedule_positions",
    "daily_assignments",
    "schedules",
    "schedule_assignments",
    "user_responses",
    "user_shift_assignments",
    "schedule_pdfs",
]