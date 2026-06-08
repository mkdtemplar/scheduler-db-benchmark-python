# Comparative Performance Evaluation of PostgreSQL and MongoDB for a Workforce Scheduling System

## 1. Introduction

This project evaluates PostgreSQL and MongoDB using a workforce scheduling database.

The main goal is to compare a normalized relational database model with two MongoDB document-oriented models under realistic scheduling workloads.

## 2. Installation

This section documents the installation of:

- Python
- PostgreSQL
- MongoDB
- Docker
- Python packages
- Prometheus

## 3. Data Import and Modeling

The original PostgreSQL database is imported from `scheduler.sql`.

The PostgreSQL model is relational and includes users, positions, shifts, schedules, schedule assignments, annual leaves, and schedule PDFs.

Two MongoDB models are created:

1. Model A: normalized-like collections
2. Model B: aggregated schedule documents

## 4. Data Usage Scenarios

The following access scenarios are evaluated:

1. Dashboard statistics
2. Full schedule retrieval
3. Employee assignment lookup
4. Annual leave overlap check
5. Position coverage aggregation

## 5. Benchmark Methodology

The benchmark measures:

- execution time
- CPU usage
- memory usage
- Docker container statistics
- warm-cache performance
- cold-cache performance
- single-process execution
- multi-process execution

## 6. Results

Results are generated in:

- `results/benchmark_results.csv`
- `results/benchmark_summary.csv`
- `results/benchmark_summary.json`
- `results/charts`
- `dashboard/index.html`

## 7. Execution Plan Analysis

PostgreSQL execution plans are collected using `EXPLAIN ANALYZE`.

MongoDB execution plans are collected using `explain`.

## 8. Discussion

This section compares PostgreSQL and MongoDB according to workload type.

## 9. Conclusion

The conclusion should not claim that one database is always better. Instead, it should explain which database is better for which type of workload.

## 10. Future Work

Possible future improvements:

- larger datasets
- p95 and p99 latency
- statistical significance testing
- index sensitivity analysis
- comparison with and without indexes
- integration with Grafana