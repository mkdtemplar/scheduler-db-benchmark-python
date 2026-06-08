import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.config import get_settings


def read_results() -> pd.DataFrame:
    settings = get_settings()
    path = settings.results_dir / "benchmark_results.csv"

    if not path.exists():
        raise FileNotFoundError(
            f"Benchmark results not found: {path}. "
            f"Run: python -m src.main benchmark --runs 5 --workers 4 --cache both"
        )

    df = pd.read_csv(path)

    numeric_columns = [
        "duration_ms",
        "rows_returned",
        "python_cpu_percent",
        "python_memory_mb",
        "python_memory_diff_mb",
        "docker_cpu_percent",
        "docker_memory_percent",
    ]

    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    return df


def create_summary(df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        df.groupby(
            [
                "database",
                "model",
                "scenario",
                "cache_mode",
                "execution_mode",
                "workers",
            ],
            dropna=False,
        )
        .agg(
            average_duration_ms=("duration_ms", "mean"),
            median_duration_ms=("duration_ms", "median"),
            min_duration_ms=("duration_ms", "min"),
            max_duration_ms=("duration_ms", "max"),
            average_rows_returned=("rows_returned", "mean"),
            average_python_cpu_percent=("python_cpu_percent", "mean"),
            average_python_memory_mb=("python_memory_mb", "mean"),
            average_python_memory_diff_mb=("python_memory_diff_mb", "mean"),
            average_docker_cpu_percent=("docker_cpu_percent", "mean"),
            average_docker_memory_percent=("docker_memory_percent", "mean"),
            runs=("duration_ms", "count"),
        )
        .reset_index()
    )

    return summary


def save_summary_files(summary: pd.DataFrame):
    settings = get_settings()

    csv_path = settings.results_dir / "benchmark_summary.csv"
    json_path = settings.results_dir / "benchmark_summary.json"

    summary.to_csv(csv_path, index=False)

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(
            summary.to_dict(orient="records"),
            file,
            indent=2,
            default=str,
        )

    print(f"Summary CSV saved to: {csv_path}")
    print(f"Summary JSON saved to: {json_path}")


def model_label(row) -> str:
    return f"{row['database']} | {row['model']}"


def save_chart(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"Chart saved to: {path}")


def plot_average_duration_by_scenario(summary: pd.DataFrame):
    """
    Clean grouped chart:
    X-axis = scenarios
    bars = database/model combinations
    value = average duration
    """

    settings = get_settings()

    filtered = summary[
        (summary["cache_mode"] == "warm")
        & (summary["execution_mode"] == "single_process")
    ].copy()

    if filtered.empty:
        return

    filtered["db_model"] = filtered.apply(model_label, axis=1)

    pivot = filtered.pivot_table(
        index="scenario",
        columns="db_model",
        values="average_duration_ms",
        aggfunc="mean",
    )

    pivot = pivot.sort_index()

    ax = pivot.plot(
        kind="bar",
        figsize=(14, 7),
        width=0.8,
    )

    ax.set_title("Average Duration by Scenario - Warm Cache, Single Process")
    ax.set_xlabel("Scenario")
    ax.set_ylabel("Average duration in milliseconds")
    ax.legend(title="Database model", loc="upper left", bbox_to_anchor=(1.01, 1))
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    plt.xticks(rotation=30, ha="right")

    save_chart(settings.charts_dir / "average_duration_by_scenario.png")


def plot_median_duration_by_scenario(summary: pd.DataFrame):
    settings = get_settings()

    filtered = summary[
        (summary["cache_mode"] == "warm")
        & (summary["execution_mode"] == "single_process")
    ].copy()

    if filtered.empty:
        return

    filtered["db_model"] = filtered.apply(model_label, axis=1)

    pivot = filtered.pivot_table(
        index="scenario",
        columns="db_model",
        values="median_duration_ms",
        aggfunc="mean",
    )

    pivot = pivot.sort_index()

    ax = pivot.plot(
        kind="bar",
        figsize=(14, 7),
        width=0.8,
    )

    ax.set_title("Median Duration by Scenario - Warm Cache, Single Process")
    ax.set_xlabel("Scenario")
    ax.set_ylabel("Median duration in milliseconds")
    ax.legend(title="Database model", loc="upper left", bbox_to_anchor=(1.01, 1))
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    plt.xticks(rotation=30, ha="right")

    save_chart(settings.charts_dir / "median_duration_by_scenario.png")


def plot_top_10_slowest(summary: pd.DataFrame):
    """
    Instead of plotting all rows, show only the top 10 slowest benchmark combinations.
    This is readable and useful for discussion.
    """

    settings = get_settings()

    plot_df = summary.sort_values(
        "average_duration_ms",
        ascending=False,
    ).head(10).copy()

    if plot_df.empty:
        return

    plot_df["label"] = (
        plot_df["database"]
        + " | "
        + plot_df["model"]
        + " | "
        + plot_df["scenario"]
        + " | "
        + plot_df["cache_mode"]
        + " | "
        + plot_df["execution_mode"]
    )

    plot_df = plot_df.sort_values("average_duration_ms", ascending=True)

    plt.figure(figsize=(13, 7))
    plt.barh(plot_df["label"], plot_df["average_duration_ms"])
    plt.title("Top 10 Slowest Benchmark Cases")
    plt.xlabel("Average duration in milliseconds")
    plt.ylabel("")
    plt.grid(axis="x", linestyle="--", alpha=0.4)

    save_chart(settings.charts_dir / "top_10_slowest_cases.png")


def plot_cache_comparison(summary: pd.DataFrame):
    """
    Shows warm vs cold cache without overcrowding.
    """

    settings = get_settings()

    filtered = summary[
        summary["execution_mode"] == "single_process"
    ].copy()

    if filtered.empty:
        return

    grouped = (
        filtered.groupby(["database", "model", "cache_mode"])
        ["average_duration_ms"]
        .mean()
        .reset_index()
    )

    grouped["db_model"] = grouped.apply(model_label, axis=1)

    pivot = grouped.pivot_table(
        index="db_model",
        columns="cache_mode",
        values="average_duration_ms",
        aggfunc="mean",
    )

    ax = pivot.plot(
        kind="bar",
        figsize=(12, 6),
        width=0.75,
    )

    ax.set_title("Warm Cache vs Cold Cache - Average Duration")
    ax.set_xlabel("Database model")
    ax.set_ylabel("Average duration in milliseconds")
    ax.legend(title="Cache mode")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    plt.xticks(rotation=25, ha="right")

    save_chart(settings.charts_dir / "warm_vs_cold_cache.png")


def plot_execution_mode_comparison(summary: pd.DataFrame):
    """
    Shows single process vs multi process in one readable chart.
    """

    settings = get_settings()

    grouped = (
        summary.groupby(["database", "model", "execution_mode"])
        ["average_duration_ms"]
        .mean()
        .reset_index()
    )

    if grouped.empty:
        return

    grouped["db_model"] = grouped.apply(model_label, axis=1)

    pivot = grouped.pivot_table(
        index="db_model",
        columns="execution_mode",
        values="average_duration_ms",
        aggfunc="mean",
    )

    ax = pivot.plot(
        kind="bar",
        figsize=(12, 6),
        width=0.75,
    )

    ax.set_title("Single-Process vs Multi-Process Execution")
    ax.set_xlabel("Database model")
    ax.set_ylabel("Average duration in milliseconds")
    ax.legend(title="Execution mode")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    plt.xticks(rotation=25, ha="right")

    save_chart(settings.charts_dir / "single_vs_multi_process.png")


def plot_cpu_usage(summary: pd.DataFrame):
    settings = get_settings()

    grouped = (
        summary.groupby(["database", "model"])
        ["average_python_cpu_percent"]
        .mean()
        .reset_index()
    )

    if grouped.empty:
        return

    grouped["db_model"] = grouped.apply(model_label, axis=1)
    grouped = grouped.sort_values("average_python_cpu_percent", ascending=True)

    plt.figure(figsize=(11, 5))
    plt.barh(grouped["db_model"], grouped["average_python_cpu_percent"])
    plt.title("Average Python CPU Usage by Database Model")
    plt.xlabel("Average Python CPU percent")
    plt.ylabel("")
    plt.grid(axis="x", linestyle="--", alpha=0.4)

    save_chart(settings.charts_dir / "python_cpu_by_model.png")


def plot_memory_usage(summary: pd.DataFrame):
    settings = get_settings()

    grouped = (
        summary.groupby(["database", "model"])
        ["average_python_memory_mb"]
        .mean()
        .reset_index()
    )

    if grouped.empty:
        return

    grouped["db_model"] = grouped.apply(model_label, axis=1)
    grouped = grouped.sort_values("average_python_memory_mb", ascending=True)

    plt.figure(figsize=(11, 5))
    plt.barh(grouped["db_model"], grouped["average_python_memory_mb"])
    plt.title("Average Python Memory Usage by Database Model")
    plt.xlabel("Average Python memory in MB")
    plt.ylabel("")
    plt.grid(axis="x", linestyle="--", alpha=0.4)

    save_chart(settings.charts_dir / "python_memory_by_model.png")


def plot_docker_resource_usage(summary: pd.DataFrame):
    settings = get_settings()

    grouped = (
        summary.groupby(["database", "model"])
        .agg(
            average_docker_cpu_percent=("average_docker_cpu_percent", "mean"),
            average_docker_memory_percent=("average_docker_memory_percent", "mean"),
        )
        .reset_index()
    )

    if grouped.empty:
        return

    grouped["db_model"] = grouped.apply(model_label, axis=1)

    ax = grouped.plot(
        x="db_model",
        y=[
            "average_docker_cpu_percent",
            "average_docker_memory_percent",
        ],
        kind="bar",
        figsize=(12, 6),
        width=0.75,
    )

    ax.set_title("Average Docker CPU and Memory Usage by Database Model")
    ax.set_xlabel("Database model")
    ax.set_ylabel("Average percent")
    ax.legend(["Docker CPU %", "Docker memory %"])
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    plt.xticks(rotation=25, ha="right")

    save_chart(settings.charts_dir / "docker_resource_usage_by_model.png")


def generate_charts(summary: pd.DataFrame):
    plot_average_duration_by_scenario(summary)
    plot_median_duration_by_scenario(summary)
    plot_top_10_slowest(summary)
    plot_cache_comparison(summary)
    plot_execution_mode_comparison(summary)
    plot_cpu_usage(summary)
    plot_memory_usage(summary)
    plot_docker_resource_usage(summary)


def generate_dashboard(summary: pd.DataFrame):
    settings = get_settings()
    settings.dashboard_dir.mkdir(parents=True, exist_ok=True)

    table_html = summary.to_html(index=False, classes="summary-table")

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PostgreSQL vs MongoDB Scheduler Benchmark</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 32px;
            background: #f5f7fb;
            color: #1f2937;
        }}

        h1, h2 {{
            color: #111827;
        }}

        .card {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
        }}

        img {{
            max-width: 100%;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            background: white;
        }}

        table {{
            border-collapse: collapse;
            width: 100%;
            font-size: 13px;
        }}

        th, td {{
            border: 1px solid #e5e7eb;
            padding: 8px;
            text-align: left;
        }}

        th {{
            background: #eff6ff;
        }}

        .note {{
            color: #4b5563;
            font-size: 14px;
            line-height: 1.6;
        }}
    </style>
</head>
<body>
    <h1>PostgreSQL vs MongoDB Scheduler Benchmark</h1>

    <div class="card">
        <h2>Project Purpose</h2>
        <p class="note">
            This dashboard presents the benchmark results for comparing PostgreSQL
            relational storage with two MongoDB document models:
            a normalized-like model and an aggregated schedule-document model.
        </p>
        <p class="note">
            The charts are separated by analytical purpose in order to avoid
            overcrowded labels and to support clearer academic interpretation.
        </p>
    </div>

    <div class="card">
        <h2>Average Duration by Scenario</h2>
        <img src="../results/charts/average_duration_by_scenario.png" alt="Average duration by scenario">
    </div>

    <div class="card">
        <h2>Median Duration by Scenario</h2>
        <img src="../results/charts/median_duration_by_scenario.png" alt="Median duration by scenario">
    </div>

    <div class="card">
        <h2>Top 10 Slowest Cases</h2>
        <img src="../results/charts/top_10_slowest_cases.png" alt="Top 10 slowest cases">
    </div>

    <div class="card">
        <h2>Warm Cache vs Cold Cache</h2>
        <img src="../results/charts/warm_vs_cold_cache.png" alt="Warm vs cold cache">
    </div>

    <div class="card">
        <h2>Single Process vs Multi Process</h2>
        <img src="../results/charts/single_vs_multi_process.png" alt="Single vs multi process">
    </div>

    <div class="card">
        <h2>Python CPU Usage</h2>
        <img src="../results/charts/python_cpu_by_model.png" alt="Python CPU usage by model">
    </div>

    <div class="card">
        <h2>Python Memory Usage</h2>
        <img src="../results/charts/python_memory_by_model.png" alt="Python memory usage by model">
    </div>

    <div class="card">
        <h2>Docker Resource Usage</h2>
        <img src="../results/charts/docker_resource_usage_by_model.png" alt="Docker resource usage">
    </div>

    <div class="card">
        <h2>Summary Table</h2>
        {table_html}
    </div>
</body>
</html>
"""

    dashboard_path = settings.dashboard_dir / "index.html"

    with dashboard_path.open("w", encoding="utf-8") as file:
        file.write(html)

    print(f"Dashboard saved to: {dashboard_path}")


def generate_reports():
    settings = get_settings()
    settings.results_dir.mkdir(parents=True, exist_ok=True)
    settings.charts_dir.mkdir(parents=True, exist_ok=True)

    df = read_results()

    if df.empty:
        raise ValueError("Benchmark results file is empty.")

    summary = create_summary(df)

    save_summary_files(summary)
    generate_charts(summary)
    generate_dashboard(summary)

    print()
    print("Reports generated successfully.")


if __name__ == "__main__":
    generate_reports()