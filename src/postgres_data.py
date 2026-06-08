
# This file analyzes the PostgreSQL database and creates additional benchmark data if the imported database is too small.
from datetime import date, datetime, timedelta, time
import random
from src.db import postgres_connection


def table_count(conn, table_name: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS c FROM public.{table_name}")
        return int(cur.fetchone()["c"])


def analyze_database() -> dict:
    tables = [
        "admins",
        "positions",
        "users",
        "shifts",
        "annual_leaves",
        "daily_schedules",
        "daily_assignments",
        "schedules",
        "schedule_assignments",
        "user_shift_assignments",
        "schedule_pdfs",
    ]

    result = {}

    with postgres_connection() as conn:
        for table in tables:
            try:
                result[table] = table_count(conn, table)
            except Exception as exc:
                result[table] = f"ERROR: {exc}"

    return result


def seed_if_empty(scale: int = 1000) -> None:
    """
    Creates realistic benchmark data if the imported SQL contains the schema
    but not enough rows for performance testing.
    """

    random.seed(42)

    with postgres_connection() as conn:
        if table_count(conn, "schedule_assignments") >= scale:
            print("PostgreSQL already contains enough schedule assignments. Seeding skipped.")
            return

        print("Seeding PostgreSQL benchmark data...")

        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.schedule_pdfs")
            cur.execute("DELETE FROM public.schedule_assignments")
            cur.execute("DELETE FROM public.user_shift_assignments")
            cur.execute("DELETE FROM public.annual_leaves")
            cur.execute("DELETE FROM public.schedules")
            cur.execute("DELETE FROM public.shifts")
            cur.execute("DELETE FROM public.users")
            cur.execute("DELETE FROM public.positions")
            cur.execute("DELETE FROM public.admins")

            cur.execute(
                """
                INSERT INTO public.admins(user_name, email, password, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    "System Admin",
                    "admin@example.com",
                    "password_hash",
                    datetime.now(),
                    datetime.now(),
                ),
            )

            admin_id = cur.fetchone()["id"]

            position_ids = []
            coverage_types = ["8h", "12h", "24h"]

            for i in range(1, 16):
                cur.execute(
                    """
                    INSERT INTO public.positions(position_name, coverage_type, required_employees)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (
                        f"Position {i:02d}",
                        coverage_types[i % len(coverage_types)],
                        random.randint(1, 4),
                    ),
                )
                position_ids.append(cur.fetchone()["id"])

            user_ids = []

            for i in range(1, 151):
                position_id = random.choice(position_ids)
                position_name = f"Position {position_ids.index(position_id) + 1:02d}"

                cur.execute(
                    """
                    INSERT INTO public.users(
                        name_surname,
                        email,
                        password,
                        position_id,
                        position_name,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        f"Employee {i:03d}",
                        f"employee{i:03d}@example.com",
                        "password_hash",
                        position_id,
                        position_name,
                        datetime.now(),
                        datetime.now(),
                    ),
                )

                user_ids.append(cur.fetchone()["id"])

            shift_templates = [
                ("Morning", "First Shift", 1, False, time(7, 0), time(15, 0), 8),
                ("Afternoon", "Second Shift", 2, False, time(15, 0), time(23, 0), 8),
                ("Night", "Third Shift", 3, True, time(23, 0), time(7, 0), 8),
            ]

            for position_id in position_ids:
                for name, shift_type, sequence_order, is_night, start_time, end_time, duration in shift_templates:
                    cur.execute(
                        """
                        INSERT INTO public.shifts(
                            name,
                            shift_type_name,
                            sequence_order,
                            is_night_shift,
                            start_time,
                            end_time,
                            position_id,
                            is_active
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, true)
                        """,
                        (
                            name,
                            shift_type,
                            sequence_order,
                            is_night,
                            start_time,
                            end_time,
                            position_id,
                        ),
                    )

            for user_id in user_ids:
                cur.execute(
                    "SELECT position_id FROM public.users WHERE id = %s",
                    (user_id,),
                )
                position_id = cur.fetchone()["position_id"]

                cur.execute(
                    "SELECT id FROM public.shifts WHERE position_id = %s",
                    (position_id,),
                )

                possible_shifts = [row["id"] for row in cur.fetchall()]

                for shift_id in possible_shifts:
                    cur.execute(
                        """
                        INSERT INTO public.user_shift_assignments(user_id, shift_id, is_active)
                        VALUES (%s, %s, true)
                        """,
                        (user_id, shift_id),
                    )

            base_date = date.today() - timedelta(days=60)
            schedule_count = max(10, scale // 250)
            assignment_counter = 0

            for schedule_number in range(1, schedule_count + 1):
                start_date = base_date + timedelta(days=(schedule_number - 1) * 7)
                end_date = start_date + timedelta(days=6)

                cur.execute(
                    """
                    INSERT INTO public.schedules(
                        name,
                        period_type,
                        start_date,
                        end_date,
                        status,
                        created_by_user_id,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, 'weekly', %s, %s, 'published', %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        f"Weekly Schedule {schedule_number:03d}",
                        start_date,
                        end_date,
                        admin_id,
                        datetime.now(),
                        datetime.now(),
                    ),
                )

                schedule_id = cur.fetchone()["id"]

                for day_offset in range(7):
                    work_date = start_date + timedelta(days=day_offset)

                    for position_id in position_ids:
                        cur.execute(
                            "SELECT position_name FROM public.positions WHERE id = %s",
                            (position_id,),
                        )
                        position_name = cur.fetchone()["position_name"]

                        cur.execute(
                            """
                            SELECT id, name, shift_type_name, sequence_order,
                                   is_night_shift, start_time, end_time
                            FROM public.shifts
                            WHERE position_id = %s
                            """,
                            (position_id,),
                        )
                        shifts = cur.fetchall()

                        cur.execute(
                            """
                            SELECT id, name_surname
                            FROM public.users
                            WHERE position_id = %s
                            ORDER BY random()
                            LIMIT 3
                            """,
                            (position_id,),
                        )
                        users = cur.fetchall()

                        for shift in shifts:
                            if not users:
                                continue

                            user = random.choice(users)

                            try:
                                cur.execute(
                                    """
                                    INSERT INTO public.schedule_assignments(
                                        schedule_id,
                                        work_date,
                                        user_id,
                                        user_name,
                                        position_id,
                                        position_name,
                                        shift_id,
                                        shift_name,
                                        shift_type_name,
                                        shift_sequence_order,
                                        is_night_shift,
                                        start_time,
                                        end_time,
                                        duration_hours,
                                        created_at,
                                        updated_at
                                    )
                                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                    """,
                                    (
                                        schedule_id,
                                        work_date,
                                        user["id"],
                                        user["name_surname"],
                                        position_id,
                                        position_name,
                                        shift["id"],
                                        shift["name"],
                                        shift["shift_type_name"],
                                        shift["sequence_order"],
                                        shift["is_night_shift"],
                                        shift["start_time"],
                                        shift["end_time"],
                                        8,
                                        datetime.now(),
                                        datetime.now(),
                                    ),
                                )

                                assignment_counter += 1

                            except Exception:
                                conn.rollback()
                                continue

                            if assignment_counter >= scale:
                                conn.commit()
                                print(f"Seeded {assignment_counter} schedule assignments.")
                                return

            for i in range(1, 31):
                user_id = random.choice(user_ids)

                cur.execute(
                    "SELECT email, position_name FROM public.users WHERE id = %s",
                    (user_id,),
                )
                user = cur.fetchone()

                start = date.today() + timedelta(days=random.randint(1, 90))
                end = start + timedelta(days=random.randint(1, 10))

                cur.execute(
                    """
                    INSERT INTO public.annual_leaves(email, position_name, start_date, end_date)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        user["email"],
                        user["position_name"],
                        start,
                        end,
                    ),
                )

        conn.commit()
        print("Seeding completed.")