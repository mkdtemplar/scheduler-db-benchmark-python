# This file defines the realistic data-usage scenarios.

from src.db import postgres_connection, mongo_database


DEFAULT_SCHEDULE_ID = 1
DEFAULT_USER_ID = 1
DEFAULT_EMAIL = "employee001@example.com"
DEFAULT_START_DATE = "2026-01-01"
DEFAULT_END_DATE = "2027-12-31"


def pg_dashboard_statistics():
    sql = """
    SELECT
        (SELECT COUNT(*) FROM public.users) AS users_count,
        (SELECT COUNT(*) FROM public.positions) AS positions_count,
        (SELECT COUNT(*) FROM public.shifts) AS shifts_count,
        (SELECT COUNT(*) FROM public.schedules) AS schedules_count,
        (SELECT COUNT(*) FROM public.schedule_assignments) AS assignments_count
    """

    with postgres_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [dict(cur.fetchone())]


def pg_full_schedule(schedule_id: int = DEFAULT_SCHEDULE_ID):
    sql = """
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
    WHERE s.id = %s
    ORDER BY sa.work_date, sa.position_name, sa.shift_sequence_order
    """

    with postgres_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (schedule_id,))
            return [dict(row) for row in cur.fetchall()]


def pg_employee_assignments(user_id: int = DEFAULT_USER_ID):
    sql = """
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
    WHERE sa.user_id = %s
    ORDER BY sa.work_date
    """

    with postgres_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (user_id,))
            return [dict(row) for row in cur.fetchall()]


def pg_annual_leave_overlap(
    email: str = DEFAULT_EMAIL,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
):
    sql = """
    SELECT *
    FROM public.annual_leaves
    WHERE email = %s
      AND start_date <= %s
      AND end_date >= %s
    ORDER BY start_date
    """

    with postgres_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (email, end_date, start_date))
            return [dict(row) for row in cur.fetchall()]


def pg_position_coverage(
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
):
    sql = """
    SELECT
        work_date,
        position_name,
        shift_name,
        COUNT(*) AS assigned_employees
    FROM public.schedule_assignments
    WHERE work_date BETWEEN %s AND %s
    GROUP BY work_date, position_name, shift_name
    ORDER BY work_date, position_name, shift_name
    """

    with postgres_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (start_date, end_date))
            return [dict(row) for row in cur.fetchall()]


def mongo_a_dashboard_statistics():
    db = mongo_database()

    return [
        {
            "users_count": db.a_users.count_documents({}),
            "positions_count": db.a_positions.count_documents({}),
            "shifts_count": db.a_shifts.count_documents({}),
            "schedules_count": db.a_schedules.count_documents({}),
            "assignments_count": db.a_schedule_assignments.count_documents({}),
        }
    ]


def mongo_a_full_schedule(schedule_id: int = DEFAULT_SCHEDULE_ID):
    db = mongo_database()

    schedule = db.a_schedules.find_one(
        {"id": schedule_id},
        {"_id": 0},
    )

    assignments = list(
        db.a_schedule_assignments.find(
            {"schedule_id": schedule_id},
            {"_id": 0},
        ).sort(
            [
                ("work_date", 1),
                ("position_name", 1),
                ("shift_sequence_order", 1),
            ]
        )
    )

    return [
        {
            "schedule": schedule,
            "assignments": assignments,
        }
    ]


def mongo_a_employee_assignments(user_id: int = DEFAULT_USER_ID):
    db = mongo_database()

    return list(
        db.a_schedule_assignments.find(
            {"user_id": user_id},
            {"_id": 0},
        ).sort("work_date", 1)
    )


def mongo_a_annual_leave_overlap(
    email: str = DEFAULT_EMAIL,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
):
    db = mongo_database()

    return list(
        db.a_annual_leaves.find(
            {
                "email": email,
                "start_date": {"$lte": end_date},
                "end_date": {"$gte": start_date},
            },
            {"_id": 0},
        ).sort("start_date", 1)
    )


def mongo_a_position_coverage(
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
):
    db = mongo_database()

    pipeline = [
        {
            "$match": {
                "work_date": {
                    "$gte": start_date,
                    "$lte": end_date,
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

    return list(db.a_schedule_assignments.aggregate(pipeline))


def mongo_b_dashboard_statistics():
    db = mongo_database()

    return [
        {
            "users_count": db.b_employees.count_documents({}),
            "positions_count": db.b_positions.count_documents({}),
            "schedules_count": db.b_schedules.count_documents({}),
            "assignments_count": sum(
                doc.get("assignment_count", 0)
                for doc in db.b_schedules.find({}, {"assignment_count": 1})
            ),
        }
    ]


def mongo_b_full_schedule(schedule_id: int = DEFAULT_SCHEDULE_ID):
    db = mongo_database()

    doc = db.b_schedules.find_one(
        {"id": schedule_id},
        {"_id": 0},
    )

    return [doc] if doc else []


def mongo_b_employee_assignments(user_id: int = DEFAULT_USER_ID):
    db = mongo_database()

    pipeline = [
        {"$match": {"assignments.user_id": user_id}},
        {"$unwind": "$assignments"},
        {"$match": {"assignments.user_id": user_id}},
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

    return list(db.b_schedules.aggregate(pipeline))


def mongo_b_annual_leave_overlap(
    email: str = DEFAULT_EMAIL,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
):
    db = mongo_database()

    return list(
        db.a_annual_leaves.find(
            {
                "email": email,
                "start_date": {"$lte": end_date},
                "end_date": {"$gte": start_date},
            },
            {"_id": 0},
        ).sort("start_date", 1)
    )


def mongo_b_position_coverage(
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
):
    db = mongo_database()

    pipeline = [
        {"$unwind": "$assignments"},
        {
            "$match": {
                "assignments.work_date": {
                    "$gte": start_date,
                    "$lte": end_date,
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

    return list(db.b_schedules.aggregate(pipeline))


SCENARIOS = [
    ("PostgreSQL", "Relational", "dashboard_statistics", pg_dashboard_statistics),
    ("PostgreSQL", "Relational", "full_schedule", pg_full_schedule),
    ("PostgreSQL", "Relational", "employee_assignments", pg_employee_assignments),
    ("PostgreSQL", "Relational", "annual_leave_overlap", pg_annual_leave_overlap),
    ("PostgreSQL", "Relational", "position_coverage", pg_position_coverage),

    ("MongoDB", "Model A - normalized", "dashboard_statistics", mongo_a_dashboard_statistics),
    ("MongoDB", "Model A - normalized", "full_schedule", mongo_a_full_schedule),
    ("MongoDB", "Model A - normalized", "employee_assignments", mongo_a_employee_assignments),
    ("MongoDB", "Model A - normalized", "annual_leave_overlap", mongo_a_annual_leave_overlap),
    ("MongoDB", "Model A - normalized", "position_coverage", mongo_a_position_coverage),

    ("MongoDB", "Model B - aggregated", "dashboard_statistics", mongo_b_dashboard_statistics),
    ("MongoDB", "Model B - aggregated", "full_schedule", mongo_b_full_schedule),
    ("MongoDB", "Model B - aggregated", "employee_assignments", mongo_b_employee_assignments),
    ("MongoDB", "Model B - aggregated", "annual_leave_overlap", mongo_b_annual_leave_overlap),
    ("MongoDB", "Model B - aggregated", "position_coverage", mongo_b_position_coverage),
]