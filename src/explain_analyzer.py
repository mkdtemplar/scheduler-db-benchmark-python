import json
from pathlib import Path

from src.config import get_settings
from src.db import postgres_connection, mongo_database


POSTGRES_EXPLAIN_QUERIES = {
    "dashboard_statistics": """
        SELECT
            (SELECT COUNT(*) FROM public.users) AS users_count,
            (SELECT COUNT(*) FROM public.positions) AS positions_count,
            (SELECT COUNT(*) FROM public.shifts) AS shifts_count,
            (SELECT COUNT(*) FROM public.schedules) AS schedules_count,
            (SELECT COUNT(*) FROM public.schedule_assignments) AS assignments_count
    """,
    "full_schedule": """
        SELECT
            s.id AS schedule_id,
            s.name,
            s.period_type,
            s.status,
            s.start_date,
            s.end_date,
            sa.work_date,
            sa.user_id,
            sa.user_name,
            sa.position_id,
            sa.position_name,
            sa.shift_id,
            sa.shift_name,
            sa.shift_type_name,
            sa.start_time,
            sa.end_time,
            sa.duration_hours
        FROM public.schedules s
        JOIN public.schedule_assignments sa ON sa.schedule_id = s.id
        WHERE s.id = 1
        ORDER BY sa.work_date, sa.position_name, sa.shift_sequence_order
    """,
    "employee_assignments": """
        SELECT
            sa.work_date,
            sa.user_id,
            sa.user_name,
            sa.position_name,
            sa.shift_name,
            sa.start_time,
            sa.end_time,
            s.name AS schedule_name
        FROM public.schedule_assignments sa
        JOIN public.schedules s ON s.id = sa.schedule_id
        WHERE sa.user_id = 1
        ORDER BY sa.work_date
    """,
    "annual_leave_overlap": """
        SELECT *
        FROM public.annual_leaves
        WHERE email = 'employee001@example.com'
          AND start_date <= '2027-12-31'
          AND end_date >= '2026-01-01'
        ORDER BY start_date
    """,
    "position_coverage": """
        SELECT
            work_date,
            position_name,
            shift_name,
            COUNT(*) AS assigned_employees
        FROM public.schedule_assignments
        WHERE work_date BETWEEN '2026-01-01' AND '2027-12-31'
        GROUP BY work_date, position_name, shift_name
        ORDER BY work_date, position_name, shift_name
    """,
}


def collect_postgres_explain() -> dict:
    results = {}

    with postgres_connection() as conn:
        with conn.cursor() as cur:
            for scenario, sql in POSTGRES_EXPLAIN_QUERIES.items():
                print(f"Collecting PostgreSQL EXPLAIN ANALYZE for: {scenario}")

                try:
                    explain_sql = f"""
                    EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                    {sql}
                    """

                    cur.execute(explain_sql)
                    explain_result = cur.fetchone()["QUERY PLAN"]

                    results[scenario] = explain_result

                except Exception as exc:
                    results[scenario] = {
                        "error": str(exc)
                    }

    return results


def collect_mongo_explain() -> dict:
    db = mongo_database()

    results = {}

    print("Collecting MongoDB explain for Model A dashboard_statistics")
    try:
        results["model_a_dashboard_statistics"] = {
            "a_users_count": db.command(
                {
                    "explain": {
                        "count": "a_users",
                        "query": {},
                    },
                    "verbosity": "executionStats",
                }
            ),
            "a_positions_count": db.command(
                {
                    "explain": {
                        "count": "a_positions",
                        "query": {},
                    },
                    "verbosity": "executionStats",
                }
            ),
            "a_shifts_count": db.command(
                {
                    "explain": {
                        "count": "a_shifts",
                        "query": {},
                    },
                    "verbosity": "executionStats",
                }
            ),
        }
    except Exception as exc:
        results["model_a_dashboard_statistics"] = {"error": str(exc)}

    print("Collecting MongoDB explain for Model A full_schedule")
    try:
        results["model_a_full_schedule_schedule"] = db.command(
            {
                "explain": {
                    "find": "a_schedules",
                    "filter": {"id": 1},
                },
                "verbosity": "executionStats",
            }
        )

        results["model_a_full_schedule_assignments"] = db.command(
            {
                "explain": {
                    "find": "a_schedule_assignments",
                    "filter": {"schedule_id": 1},
                    "sort": {
                        "work_date": 1,
                        "position_name": 1,
                        "shift_sequence_order": 1,
                    },
                },
                "verbosity": "executionStats",
            }
        )
    except Exception as exc:
        results["model_a_full_schedule"] = {"error": str(exc)}

    print("Collecting MongoDB explain for Model A employee_assignments")
    try:
        results["model_a_employee_assignments"] = db.command(
            {
                "explain": {
                    "find": "a_schedule_assignments",
                    "filter": {"user_id": 1},
                    "sort": {"work_date": 1},
                },
                "verbosity": "executionStats",
            }
        )
    except Exception as exc:
        results["model_a_employee_assignments"] = {"error": str(exc)}

    print("Collecting MongoDB explain for Model A annual_leave_overlap")
    try:
        results["model_a_annual_leave_overlap"] = db.command(
            {
                "explain": {
                    "find": "a_annual_leaves",
                    "filter": {
                        "email": "employee001@example.com",
                        "start_date": {"$lte": "2027-12-31"},
                        "end_date": {"$gte": "2026-01-01"},
                    },
                    "sort": {"start_date": 1},
                },
                "verbosity": "executionStats",
            }
        )
    except Exception as exc:
        results["model_a_annual_leave_overlap"] = {"error": str(exc)}

    print("Collecting MongoDB explain for Model A position_coverage")
    try:
        pipeline = [
            {
                "$match": {
                    "work_date": {
                        "$gte": "2026-01-01",
                        "$lte": "2027-12-31",
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "work_date": "$work_date",
                        "position_name": "$position_name",
                        "shift_name": "$shift_name",
                    },
                    "assigned_employees": {"$sum": 1},
                }
            },
            {
                "$sort": {
                    "_id.work_date": 1,
                    "_id.position_name": 1,
                    "_id.shift_name": 1,
                }
            },
        ]

        results["model_a_position_coverage"] = db.command(
            {
                "explain": {
                    "aggregate": "a_schedule_assignments",
                    "pipeline": pipeline,
                    "cursor": {},
                },
                "verbosity": "executionStats",
            }
        )
    except Exception as exc:
        results["model_a_position_coverage"] = {"error": str(exc)}

    print("Collecting MongoDB explain for Model B full_schedule")
    try:
        results["model_b_full_schedule"] = db.command(
            {
                "explain": {
                    "find": "b_schedules",
                    "filter": {"id": 1},
                },
                "verbosity": "executionStats",
            }
        )
    except Exception as exc:
        results["model_b_full_schedule"] = {"error": str(exc)}

    print("Collecting MongoDB explain for Model B employee_assignments")
    try:
        pipeline = [
            {"$match": {"assignments.user_id": 1}},
            {"$unwind": "$assignments"},
            {"$match": {"assignments.user_id": 1}},
            {
                "$project": {
                    "_id": 0,
                    "schedule_id": "$id",
                    "schedule_name": "$name",
                    "assignment": "$assignments",
                }
            },
            {"$sort": {"assignment.work_date": 1}},
        ]

        results["model_b_employee_assignments"] = db.command(
            {
                "explain": {
                    "aggregate": "b_schedules",
                    "pipeline": pipeline,
                    "cursor": {},
                },
                "verbosity": "executionStats",
            }
        )
    except Exception as exc:
        results["model_b_employee_assignments"] = {"error": str(exc)}

    print("Collecting MongoDB explain for Model B position_coverage")
    try:
        pipeline = [
            {"$unwind": "$assignments"},
            {
                "$match": {
                    "assignments.work_date": {
                        "$gte": "2026-01-01",
                        "$lte": "2027-12-31",
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "work_date": "$assignments.work_date",
                        "position_name": "$assignments.position_name",
                        "shift_name": "$assignments.shift_name",
                    },
                    "assigned_employees": {"$sum": 1},
                }
            },
            {
                "$sort": {
                    "_id.work_date": 1,
                    "_id.position_name": 1,
                    "_id.shift_name": 1,
                }
            },
        ]

        results["model_b_position_coverage"] = db.command(
            {
                "explain": {
                    "aggregate": "b_schedules",
                    "pipeline": pipeline,
                    "cursor": {},
                },
                "verbosity": "executionStats",
            }
        )
    except Exception as exc:
        results["model_b_position_coverage"] = {"error": str(exc)}

    return results


def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, default=str)


def save_explain_reports():
    settings = get_settings()

    postgres_explain = collect_postgres_explain()
    mongo_explain = collect_mongo_explain()

    postgres_path = settings.explain_dir / "postgres_explain.json"
    mongo_path = settings.explain_dir / "mongo_explain.json"

    save_json(postgres_path, postgres_explain)
    save_json(mongo_path, mongo_explain)

    print()
    print(f"PostgreSQL EXPLAIN ANALYZE saved to: {postgres_path}")
    print(f"MongoDB executionStats saved to: {mongo_path}")


if __name__ == "__main__":
    save_explain_reports()