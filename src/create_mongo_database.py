from datetime import date, datetime, time
from decimal import Decimal

from src.db import postgres_connection, mongo_database


POSTGRES_TABLES = [
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


def convert_value(value):
    """
    Converts PostgreSQL-specific Python values into MongoDB-compatible values.
    """

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
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


def clean_document(row):
    """
    Converts one PostgreSQL row into a MongoDB document.
    """

    return {
        key: convert_value(value)
        for key, value in row.items()
    }


def fetch_table(table_name):
    """
    Reads all records from one PostgreSQL table.
    """

    with postgres_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM public.{table_name}")
            rows = cur.fetchall()

    return [clean_document(dict(row)) for row in rows]


def create_normalized_mongodb_model(db):
    """
    MongoDB Model A:
    One MongoDB collection for each PostgreSQL table.

    PostgreSQL table:
        users

    becomes MongoDB collection:
        a_users

    PostgreSQL table:
        schedule_assignments

    becomes MongoDB collection:
        a_schedule_assignments
    """

    print("Creating MongoDB Model A: normalized-like collections")

    for table_name in POSTGRES_TABLES:
        collection_name = f"a_{table_name}"
        collection = db[collection_name]

        print(f"Clearing collection: {collection_name}")
        collection.delete_many({})

        print(f"Reading PostgreSQL table: {table_name}")
        documents = fetch_table(table_name)

        if documents:
            print(f"Inserting {len(documents)} documents into {collection_name}")
            collection.insert_many(documents)
        else:
            print(f"No records found in PostgreSQL table: {table_name}")

    print("Creating indexes for MongoDB Model A")

    db.a_admins.create_index("id")
    db.a_admins.create_index("email")

    db.a_positions.create_index("id")
    db.a_positions.create_index("position_name")

    db.a_users.create_index("id")
    db.a_users.create_index("email")
    db.a_users.create_index("position_id")
    db.a_users.create_index("position_name")

    db.a_shifts.create_index("id")
    db.a_shifts.create_index("position_id")
    db.a_shifts.create_index("sequence_order")

    db.a_annual_leaves.create_index("email")
    db.a_annual_leaves.create_index([("start_date", 1), ("end_date", 1)])

    db.a_schedules.create_index("id")
    db.a_schedules.create_index("status")
    db.a_schedules.create_index([("start_date", 1), ("end_date", 1)])

    db.a_schedule_assignments.create_index("id")
    db.a_schedule_assignments.create_index("schedule_id")
    db.a_schedule_assignments.create_index("user_id")
    db.a_schedule_assignments.create_index("position_id")
    db.a_schedule_assignments.create_index("shift_id")
    db.a_schedule_assignments.create_index("work_date")
    db.a_schedule_assignments.create_index(
        [
            ("schedule_id", 1),
            ("work_date", 1),
            ("position_name", 1),
            ("shift_sequence_order", 1),
        ]
    )

    db.a_user_shift_assignments.create_index("user_id")
    db.a_user_shift_assignments.create_index("shift_id")

    print("MongoDB Model A created successfully")


def create_aggregated_schedule_model(db):
    """
    MongoDB Model B:
    Aggregated schedule documents.

    Instead of keeping schedules and schedule_assignments separate,
    each schedule document contains its assignments inside an array.
    """

    print("Creating MongoDB Model B: aggregated schedule documents")

    db.b_schedules.delete_many({})
    db.b_positions.delete_many({})
    db.b_employees.delete_many({})

    with postgres_connection() as conn:
        with conn.cursor() as cur:
            print("Creating b_positions collection")

            cur.execute("SELECT * FROM public.positions ORDER BY id")
            positions = [clean_document(dict(row)) for row in cur.fetchall()]

            for position in positions:
                position_id = position["id"]

                cur.execute(
                    """
                    SELECT *
                    FROM public.users
                    WHERE position_id = %s
                    ORDER BY id
                    """,
                    (position_id,),
                )
                employees = [clean_document(dict(row)) for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT *
                    FROM public.shifts
                    WHERE position_id = %s
                    ORDER BY sequence_order
                    """,
                    (position_id,),
                )
                shifts = [clean_document(dict(row)) for row in cur.fetchall()]

                position_document = dict(position)
                position_document["employees"] = employees
                position_document["shifts"] = shifts
                position_document["employee_count"] = len(employees)
                position_document["shift_count"] = len(shifts)

                db.b_positions.insert_one(position_document)

            print("Creating b_employees collection")

            cur.execute("SELECT * FROM public.users ORDER BY id")
            users = [clean_document(dict(row)) for row in cur.fetchall()]

            for user in users:
                user_id = user["id"]

                cur.execute(
                    """
                    SELECT s.*
                    FROM public.user_shift_assignments usa
                    JOIN public.shifts s ON s.id = usa.shift_id
                    WHERE usa.user_id = %s
                    ORDER BY s.sequence_order
                    """,
                    (user_id,),
                )

                eligible_shifts = [clean_document(dict(row)) for row in cur.fetchall()]

                employee_document = dict(user)
                employee_document["eligible_shifts"] = eligible_shifts
                employee_document["eligible_shift_count"] = len(eligible_shifts)

                db.b_employees.insert_one(employee_document)

            print("Creating b_schedules collection")

            cur.execute("SELECT * FROM public.schedules ORDER BY id")
            schedules = [clean_document(dict(row)) for row in cur.fetchall()]

            for schedule in schedules:
                schedule_id = schedule["id"]

                cur.execute(
                    """
                    SELECT *
                    FROM public.schedule_assignments
                    WHERE schedule_id = %s
                    ORDER BY work_date, position_name, shift_sequence_order
                    """,
                    (schedule_id,),
                )

                assignments = [clean_document(dict(row)) for row in cur.fetchall()]

                schedule_document = dict(schedule)
                schedule_document["assignments"] = assignments
                schedule_document["assignment_count"] = len(assignments)

                db.b_schedules.insert_one(schedule_document)

    print("Creating indexes for MongoDB Model B")

    db.b_schedules.create_index("id")
    db.b_schedules.create_index("status")
    db.b_schedules.create_index([("start_date", 1), ("end_date", 1)])
    db.b_schedules.create_index("assignments.user_id")
    db.b_schedules.create_index("assignments.position_id")
    db.b_schedules.create_index("assignments.shift_id")
    db.b_schedules.create_index("assignments.work_date")

    db.b_positions.create_index("id")
    db.b_positions.create_index("position_name")
    db.b_positions.create_index("employees.id")
    db.b_positions.create_index("shifts.id")

    db.b_employees.create_index("id")
    db.b_employees.create_index("email")
    db.b_employees.create_index("position_id")
    db.b_employees.create_index("eligible_shifts.id")

    print("MongoDB Model B created successfully")


def print_mongodb_summary(db):
    print()
    print("MongoDB database summary")
    print("========================")

    collection_names = sorted(db.list_collection_names())

    for collection_name in collection_names:
        count = db[collection_name].count_documents({})
        print(f"{collection_name}: {count} documents")

    print("========================")
    print()


def create_mongo_database():
    """
    Main function that creates the MongoDB database and all collections.
    """

    db = mongo_database()

    print("Connected to MongoDB database:", db.name)

    create_normalized_mongodb_model(db)
    create_aggregated_schedule_model(db)

    print_mongodb_summary(db)

    print("MongoDB database creation completed.")


if __name__ == "__main__":
    create_mongo_database()