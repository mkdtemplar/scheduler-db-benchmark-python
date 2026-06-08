import argparse

from src.benchmark_runner import run_benchmark
from src.create_mongo_database import create_mongo_database
from src.explain_analyzer import save_explain_reports
from src.postgres_data import analyze_database, seed_if_empty
from src.report_generator import generate_reports
from src.validate_setup import validate_setup


def main():
    parser = argparse.ArgumentParser(
        description="PostgreSQL vs MongoDB Scheduler Benchmark"
    )

    parser.add_argument(
        "command",
        choices=[
            "validate",
            "analyze",
            "seed",
            "mongo-create",
            "benchmark",
            "explain",
            "report",
            "all",
        ],
    )

    parser.add_argument(
        "--scale",
        type=int,
        default=10000,
        help="Target number of schedule assignments if seed is used",
    )

    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Number of benchmark runs per scenario",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of workers for multi-process benchmark",
    )

    parser.add_argument(
        "--cache",
        choices=["warm", "cold", "both"],
        default="both",
        help="Cache mode",
    )

    args = parser.parse_args()

    if args.command == "validate":
        validate_setup()

    elif args.command == "analyze":
        result = analyze_database()

        print()
        print("PostgreSQL database analysis")
        print("============================")

        for table_name, count in result.items():
            print(f"{table_name}: {count}")

        print("============================")

    elif args.command == "seed":
        seed_if_empty(args.scale)

    elif args.command == "mongo-create":
        create_mongo_database()

    elif args.command == "benchmark":
        run_benchmark(
            runs=args.runs,
            workers=args.workers,
            cache_mode=args.cache,
        )

    elif args.command == "explain":
        save_explain_reports()

    elif args.command == "report":
        generate_reports()

    elif args.command == "all":
        print("Step 1: Validating current setup...")
        validate_setup()

        print()
        print("Step 2: Analyzing PostgreSQL database...")
        result = analyze_database()

        for table_name, count in result.items():
            print(f"{table_name}: {count}")

        print()
        print("Step 3: Creating MongoDB collections and importing data...")
        create_mongo_database()

        print()
        print("Step 4: Running benchmark...")
        run_benchmark(
            runs=args.runs,
            workers=args.workers,
            cache_mode=args.cache,
        )

        print()
        print("Step 5: Collecting EXPLAIN and executionStats reports...")
        save_explain_reports()

        print()
        print("Step 6: Generating reports, charts, and dashboard...")
        generate_reports()

        print()
        print("Complete workflow finished.")


if __name__ == "__main__":
    main()