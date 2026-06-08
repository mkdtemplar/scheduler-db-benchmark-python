from src.db import postgres_connection, mongo_database


def validate_postgres():
    print("Checking PostgreSQL connection...")

    with postgres_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database() AS database_name")
            database_name = cur.fetchone()["database_name"]

            print(f"Connected to PostgreSQL database: {database_name}")

            tables = [
                "admins",
                "positions",
                "users",
                "shifts",
                "annual_leaves",
                "schedules",
                "schedule_assignments",
                "user_shift_assignments",
            ]

            print()
            print("PostgreSQL table counts")
            print("=======================")

            for table in tables:
                try:
                    cur.execute(f"SELECT COUNT(*) AS count FROM public.{table}")
                    count = cur.fetchone()["count"]
                    print(f"{table}: {count}")
                except Exception as exc:
                    print(f"{table}: ERROR - {exc}")

            print("=======================")


def validate_mongodb():
    print()
    print("Checking MongoDB connection...")

    db = mongo_database()

    ping_result = db.command("ping")
    print(f"MongoDB ping result: {ping_result}")
    print(f"Connected to MongoDB database: {db.name}")

    print()
    print("MongoDB collection counts")
    print("=========================")

    collection_names = sorted(db.list_collection_names())

    if not collection_names:
        print("No collections found. Run: python -m src.create_mongo_database")
    else:
        for collection_name in collection_names:
            count = db[collection_name].count_documents({})
            print(f"{collection_name}: {count}")

    print("=========================")


def validate_setup():
    validate_postgres()
    validate_mongodb()


if __name__ == "__main__":
    validate_setup()