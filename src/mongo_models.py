# This file imports PostgreSQL data into MongoDB using two different aggregation levels.
# This directly satisfies the professor’s requirement to analyze and design a suitable model for importing the data.

from datetime import date, datetime, time
from decimal import Decimal
from src.db import postgres_connection, mongo_database


def to_json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, time):
        return value.strftime("%H:%M:%S")

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, memoryview):
        return None

    if isinstance(value, bytes):
        return None

    return value


def clean_row(row: dict) -> dict:
    return {key: to_json_value(value) for key, value in row.items()}


def fetch_all(table_name: str) -> list[dict]:
    with postgres_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM public.{table_name}")
            return [clean_row(dict(row)) for row in cur.fetchall()]


def import_model_a_normalized():
    """
    MongoDB Model A:
    collection-per-table design, close to PostgreSQL normalized model.
    """

    db = mongo_database()

    tables = [
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
    ]

    for table in tables:
        rows = fetch_all(table)
        collection = db[f"a_{table}"]
        collection.delete_many({})

        if rows:
            collection.insert_many(rows)

    db.a_users.create_index("id")
    db.a_users.create_index("email")
    db.a_users.create_index("position_id")
    db.a_positions.create_index("id")
    db.a_shifts.create_index("position_id")
    db.a_schedules.create_index("id")
    db.a_schedules.create_index("status")
    db.a_schedules.create_index([("start_date", 1), ("end_date", 1)])
    db.a_schedule_assignments.create_index("schedule_id")
    db.a_schedule_assignments.create_index("user_id")
    db.a_schedule_assignments.create_index("position_id")
    db.a_schedule_assignments.create_index("work_date")
    db.a_annual_leaves.create_index("email")
    db.a_annual_leaves.create_index([("start_date", 1), ("end_date", 1)])


def import_model_b_aggregated():
    """
    MongoDB Model B:
    read-optimized document model with embedded schedule assignments.
    """

    db = mongo_database()

    db.b_schedules.delete_many({})
    db.b_positions.delete_many({})
    db.b_employees.delete_many({})

    with postgres_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM public.positions ORDER BY id")
            positions = [clean_row(dict(row)) for row in cur.fetchall()]

            for position in positions:
                cur.execute(
                    "SELECT * FROM public.users WHERE position_id = %s ORDER BY id",
                    (position["id"],),
                )
                employees = [clean_row(dict(row)) for row in cur.fetchall()]

                cur.execute(
                    "SELECT * FROM public.shifts WHERE position_id = %s ORDER BY sequence_order",
                    (position["id"],),
                )
                shifts = [clean_row(dict(row)) for row in cur.fetchall()]

                document = dict(position)
                document["employees"] = employees
                document["shifts"] = shifts
                document["employee_count"] = len(employees)
                document["shift_count"] = len(shifts)

                db.b_positions.insert_one(document)

            cur.execute("SELECT * FROM public.users ORDER BY id")
            users = [clean_row(dict(row)) for row in cur.fetchall()]

            for user in users:
                cur.execute(
                    """
                    SELECT s.*
                    FROM public.user_shift_assignments usa
                    JOIN public.shifts s ON s.id = usa.shift_id
                    WHERE usa.user_id = %s
                    ORDER BY s.sequence_order
                    """,
                    (user["id"],),
                )

                user["eligible_shifts"] = [
                    clean_row(dict(row)) for row in cur.fetchall()
                ]

                db.b_employees.insert_one(user)

            cur.execute("SELECT * FROM public.schedules ORDER BY id")
            schedules = [clean_row(dict(row)) for row in cur.fetchall()]

            for schedule in schedules:
                cur.execute(
                    """
                    SELECT *
                    FROM public.schedule_assignments
                    WHERE schedule_id = %s
                    ORDER BY work_date, position_name, shift_sequence_order
                    """,
                    (schedule["id"],),
                )

                assignments = [clean_row(dict(row)) for row in cur.fetchall()]

                document = dict(schedule)
                document["assignment_count"] = len(assignments)
                document["assignments"] = assignments

                db.b_schedules.insert_one(document)

    db.b_schedules.create_index("id")
    db.b_schedules.create_index("status")
    db.b_schedules.create_index([("start_date", 1), ("end_date", 1)])
    db.b_schedules.create_index("assignments.user_id")
    db.b_schedules.create_index("assignments.position_id")
    db.b_schedules.create_index("assignments.work_date")
    db.b_positions.create_index("id")
    db.b_positions.create_index("position_name")
    db.b_employees.create_index("id")
    db.b_employees.create_index("email")
    db.b_employees.create_index("position_id")


def rebuild_mongo_models():
    print("Importing MongoDB Model A: normalized-like collections...")
    import_model_a_normalized()

    print("Importing MongoDB Model B: aggregated documents...")
    import_model_b_aggregated()

    print("MongoDB import completed.")