import csv
import json
import os
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import psutil

from src.config import get_settings
from src.query_scenarios import SCENARIOS


POSTGRES_CONTAINER = "scheduling-postgres"
MONGO_CONTAINER = "scheduler_mongo"


def ensure_results_file(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "timestamp",
                "database",
                "model",
                "scenario",
                "cache_mode",
                "execution_mode",
                "workers",
                "run_number",
                "duration_ms",
                "rows_returned",
                "python_cpu_percent",
                "python_memory_mb",
                "python_memory_diff_mb",
                "docker_container",
                "docker_cpu_percent",
                "docker_memory_usage",
                "docker_memory_percent",
                "error",
            ],
        )

        writer.writeheader()


def append_result(path: Path, result: dict):
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "timestamp",
                "database",
                "model",
                "scenario",
                "cache_mode",
                "execution_mode",
                "workers",
                "run_number",
                "duration_ms",
                "rows_returned",
                "python_cpu_percent",
                "python_memory_mb",
                "python_memory_diff_mb",
                "docker_container",
                "docker_cpu_percent",
                "docker_memory_usage",
                "docker_memory_percent",
                "error",
            ],
        )

        writer.writerow(result)


def parse_percent(value: str) -> float:
    if not value:
        return 0.0

    cleaned = value.replace("%", "").strip()

    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def read_docker_stats(container_name: str) -> dict:
    try:
        command = [
            "docker",
            "stats",
            "--no-stream",
            "--format",
            "{{json .}}",
            container_name,
        ]

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

        raw = completed.stdout.strip()

        if not raw:
            return {
                "container": container_name,
                "cpu_percent": 0.0,
                "memory_usage": "",
                "memory_percent": 0.0,
            }

        parsed = json.loads(raw)

        return {
            "container": parsed.get("Name", container_name),
            "cpu_percent": parse_percent(parsed.get("CPUPerc", "0")),
            "memory_usage": parsed.get("MemUsage", ""),
            "memory_percent": parse_percent(parsed.get("MemPerc", "0")),
        }

    except Exception as exc:
        return {
            "container": container_name,
            "cpu_percent": 0.0,
            "memory_usage": f"ERROR: {exc}",
            "memory_percent": 0.0,
        }


def get_container_for_database(database: str) -> str:
    if database == "PostgreSQL":
        return POSTGRES_CONTAINER

    return MONGO_CONTAINER


def count_rows(result) -> int:
    if result is None:
        return 0

    if isinstance(result, list):
        return len(result)

    if isinstance(result, tuple):
        return len(result)

    if isinstance(result, dict):
        return 1

    if isinstance(result, int):
        return result

    return 1


def measure_single_query(
    database: str,
    model: str,
    scenario: str,
    query_function,
    cache_mode: str,
    execution_mode: str,
    workers: int,
    run_number: int,
) -> dict:
    process = psutil.Process(os.getpid())

    container_name = get_container_for_database(database)
    docker_stats_before = read_docker_stats(container_name)

    memory_before = process.memory_info().rss / 1024 / 1024
    process.cpu_percent(interval=None)

    start = time.perf_counter()

    error = ""
    rows_returned = 0

    try:
        result = query_function()
        rows_returned = count_rows(result)
    except Exception as exc:
        error = str(exc)

    duration_ms = (time.perf_counter() - start) * 1000

    python_cpu_percent = process.cpu_percent(interval=None)
    memory_after = process.memory_info().rss / 1024 / 1024
    memory_diff = memory_after - memory_before

    docker_stats_after = read_docker_stats(container_name)

    return {
        "timestamp": datetime.now().isoformat(),
        "database": database,
        "model": model,
        "scenario": scenario,
        "cache_mode": cache_mode,
        "execution_mode": execution_mode,
        "workers": workers,
        "run_number": run_number,
        "duration_ms": round(duration_ms, 4),
        "rows_returned": rows_returned,
        "python_cpu_percent": round(python_cpu_percent, 4),
        "python_memory_mb": round(memory_after, 4),
        "python_memory_diff_mb": round(memory_diff, 4),
        "docker_container": docker_stats_after["container"],
        "docker_cpu_percent": docker_stats_after["cpu_percent"],
        "docker_memory_usage": docker_stats_after["memory_usage"],
        "docker_memory_percent": docker_stats_after["memory_percent"],
        "error": error,
    }


def run_function_for_parallel(query_function):
    result = query_function()
    return count_rows(result)


def measure_parallel_query(
    database: str,
    model: str,
    scenario: str,
    query_function,
    cache_mode: str,
    workers: int,
    run_number: int,
) -> dict:
    process = psutil.Process(os.getpid())

    container_name = get_container_for_database(database)
    docker_stats_before = read_docker_stats(container_name)

    memory_before = process.memory_info().rss / 1024 / 1024
    process.cpu_percent(interval=None)

    start = time.perf_counter()

    error = ""
    rows_returned = 0

    try:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(run_function_for_parallel, query_function)
                for _ in range(workers)
            ]

            for future in as_completed(futures):
                rows_returned += future.result()

    except Exception as exc:
        error = str(exc)

    duration_ms = (time.perf_counter() - start) * 1000

    python_cpu_percent = process.cpu_percent(interval=None)
    memory_after = process.memory_info().rss / 1024 / 1024
    memory_diff = memory_after - memory_before

    docker_stats_after = read_docker_stats(container_name)

    return {
        "timestamp": datetime.now().isoformat(),
        "database": database,
        "model": model,
        "scenario": scenario,
        "cache_mode": cache_mode,
        "execution_mode": "multi_process",
        "workers": workers,
        "run_number": run_number,
        "duration_ms": round(duration_ms, 4),
        "rows_returned": rows_returned,
        "python_cpu_percent": round(python_cpu_percent, 4),
        "python_memory_mb": round(memory_after, 4),
        "python_memory_diff_mb": round(memory_diff, 4),
        "docker_container": docker_stats_after["container"],
        "docker_cpu_percent": docker_stats_after["cpu_percent"],
        "docker_memory_usage": docker_stats_after["memory_usage"],
        "docker_memory_percent": docker_stats_after["memory_percent"],
        "error": error,
    }


def warm_up_scenarios():
    print("Running warm-up queries...")

    for database, model, scenario, query_function in SCENARIOS:
        try:
            query_function()
        except Exception as exc:
            print(f"Warm-up warning for {database} / {model} / {scenario}: {exc}")


def restart_database_containers():
    print("Restarting database containers for cold-cache approximation...")

    subprocess.run(
        ["docker", "restart", POSTGRES_CONTAINER, MONGO_CONTAINER],
        check=False,
    )

    print("Waiting for containers to become ready...")
    time.sleep(10)


def run_benchmark_for_cache_mode(
    results_path: Path,
    runs: int,
    workers: int,
    cache_mode: str,
):
    if cache_mode == "warm":
        warm_up_scenarios()

    if cache_mode == "cold":
        restart_database_containers()

    for database, model, scenario, query_function in SCENARIOS:
        print()
        print(f"Scenario: {database} | {model} | {scenario} | cache={cache_mode}")

        for run_number in range(1, runs + 1):
            single_result = measure_single_query(
                database=database,
                model=model,
                scenario=scenario,
                query_function=query_function,
                cache_mode=cache_mode,
                execution_mode="single_process",
                workers=1,
                run_number=run_number,
            )

            append_result(results_path, single_result)

            print(
                f"  single run {run_number}: "
                f"{single_result['duration_ms']} ms, "
                f"rows={single_result['rows_returned']}, "
                f"error={single_result['error'] or '-'}"
            )

            if workers > 1:
                parallel_result = measure_parallel_query(
                    database=database,
                    model=model,
                    scenario=scenario,
                    query_function=query_function,
                    cache_mode=cache_mode,
                    workers=workers,
                    run_number=run_number,
                )

                append_result(results_path, parallel_result)

                print(
                    f"  multi run {run_number}: "
                    f"{parallel_result['duration_ms']} ms, "
                    f"workers={workers}, "
                    f"rows={parallel_result['rows_returned']}, "
                    f"error={parallel_result['error'] or '-'}"
                )


def run_benchmark(runs: int = 5, workers: int = 4, cache_mode: str = "both"):
    settings = get_settings()
    results_path = settings.results_dir / "benchmark_results.csv"

    ensure_results_file(results_path)

    if cache_mode in ["warm", "both"]:
        run_benchmark_for_cache_mode(
            results_path=results_path,
            runs=runs,
            workers=workers,
            cache_mode="warm",
        )

    if cache_mode in ["cold", "both"]:
        run_benchmark_for_cache_mode(
            results_path=results_path,
            runs=runs,
            workers=workers,
            cache_mode="cold",
        )

    print()
    print(f"Benchmark finished. Results written to: {results_path}")


if __name__ == "__main__":
    run_benchmark()