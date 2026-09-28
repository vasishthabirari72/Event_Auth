"""Synthetic matcher-only scaling; no images, model inference or accuracy claims."""

import argparse
import json
import os
import platform
import random
import time
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from event_auth.core.face.contracts import Template
from event_auth.core.face.matching import Thresholds, identify, normalize
from event_auth.evaluation.metrics import percentile

MODEL_VERSION = "sface_2021dec"


def machine_info() -> dict[str, str | int | None]:
    cpu = platform.processor() or platform.machine()
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.partition(":")[2].strip()
                break
    memory: int | None = None
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        memory = int(meminfo.read_text().splitlines()[0].split()[1]) * 1024
    return {
        "cpu": cpu,
        "logical_cpus": os.cpu_count(),
        "memory_bytes": memory,
        "os": platform.system(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
    }


def synthetic_gallery(
    members: int, dimensions: int = 128, seed: int = 20260925
) -> tuple[list[Template], tuple[float, ...]]:
    if members < 1 or dimensions < 2:
        raise ValueError("Positive member count and at least two dimensions required")
    rng = random.Random(seed)
    templates = []
    for index in range(members):
        member = UUID(int=index + 1)
        for _ in range(3):
            templates.append(
                Template(
                    member,
                    MODEL_VERSION,
                    normalize(tuple(rng.gauss(0, 1) for _ in range(dimensions))),
                )
            )
    query = normalize(tuple(rng.gauss(0, 1) for _ in range(dimensions)))
    return templates, query


def run_benchmark(
    sizes: Sequence[int] = (300, 2000), repeats: int = 10, seed: int = 20260925
) -> dict[str, object]:
    if repeats < 1:
        raise ValueError("At least one repetition required")
    results = []
    thresholds = Thresholds(0.363, 0.6)  # Synthetic workload settings, not calibration.
    for members in sizes:
        templates, query = synthetic_gallery(members, seed=seed)
        candidates = {t.member_id for t in templates}
        identify(query, templates, candidates, MODEL_VERSION, thresholds)
        durations = []
        for _ in range(repeats):
            start = time.perf_counter()
            identify(query, templates, candidates, MODEL_VERSION, thresholds)
            durations.append(time.perf_counter() - start)
        results.append(
            {
                "members": members,
                "templates": len(templates),
                "dimensions": 128,
                "repeats": repeats,
                "median_seconds": percentile(durations, 0.5),
                "p95_seconds": percentile(durations, 0.95),
                "max_seconds": max(durations),
            }
        )
    return {
        "kind": "synthetic_matcher_only",
        "seed": seed,
        "machine": machine_info(),
        "thresholds": asdict(thresholds),
        "results": results,
        "accuracy_evaluated": False,
        "full_pipeline_evaluated": False,
        "m1_acceptance": "NOT VERIFIED",
    }


def write_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents accidentally replacing a previous evaluation.
    with path.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2, allow_nan=False)
        output.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    if args.output.exists():
        parser.error("Output already exists; choose a new report path")
    write_report(args.output, run_benchmark(repeats=args.repeats))
    print("Synthetic matcher report written; accuracy and M1 acceptance remain unverified.")


if __name__ == "__main__":
    main()
