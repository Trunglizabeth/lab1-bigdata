#!/usr/bin/env python3
"""Task 4: tạo benchmark-summary.csv từ đúng 6 trial chính thức và tự kiểm lại số liệu.

    python3 src/bench_summary.py            # đọc evidence/r{1,2,3}-c{1,4}.jsonl

Chỉ đọc 6 file tên chuẩn, nên file *-attempt*.jsonl (lần lỗi được giữ lại) không lọt vào
thống kê. Goodput và p95 (nearest-rank, chỉ request thành công) được tính lại từ raw
request records và so với dòng summary của helper; lệch thì báo MISMATCH.
Ghi ra:
  benchmark-summary.csv              12 dòng (6 trial x put/get)
  evidence/benchmark-analysis.txt    median theo concurrency, ratio c4/c1, kiểm tra
  evidence/benchmark-sha256.txt      SHA-256 của 6 file raw
"""
import csv
import hashlib
import json
import math
import os
import statistics
import sys

RUNS = ["r1-c1", "r1-c4", "r2-c4", "r2-c1", "r3-c1", "r3-c4"]  # thứ tự chạy bắt buộc
MIB = 2 ** 20


def nearest_rank_p95(values):
    values = sorted(values)
    return values[math.ceil(0.95 * len(values)) - 1] if values else None


def main(ev="evidence"):
    rows, problems, report, sums = [], [], [], []
    for run in RUNS:
        path = os.path.join(ev, f"{run}.jsonl")
        if not os.path.exists(path):
            problems.append(f"{run}: thiếu {path}")
            continue
        with open(path, "rb") as f:
            raw = f.read()
        sums.append(f"{hashlib.sha256(raw).hexdigest()}  {path}")
        records = [json.loads(x) for x in raw.decode().splitlines() if x.strip()]
        for phase in ("put", "get"):
            summary = [r for r in records if r.get("kind") == "summary" and r.get("phase") == phase]
            reqs = [r for r in records if r.get("kind") != "summary" and r.get("op") == phase]
            if len(summary) != 1:
                problems.append(f"{run}/{phase}: có {len(summary)} summary (cần 1)")
                continue
            s = summary[0]
            good = [r for r in reqs if r.get("ok")]
            hash_failures = sum(1 for r in reqs if phase == "get" and r.get("hash_ok") is False)
            goodput = sum(r["bytes"] for r in good) / MIB / s["wall_s"]
            p95 = nearest_rank_p95([r["ms"] for r in good])
            if len(reqs) != s["n"]:
                problems.append(f"{run}/{phase}: {len(reqs)} request records, summary n={s['n']}")
            if len(good) != s["successes"]:
                problems.append(f"{run}/{phase}: MISMATCH successes {len(good)} vs {s['successes']}")
            if not math.isclose(goodput, s["goodput_MiB_s"], rel_tol=1e-9):
                problems.append(f"{run}/{phase}: MISMATCH goodput {goodput} vs {s['goodput_MiB_s']}")
            if p95 != s["p95_success_ms"]:
                problems.append(f"{run}/{phase}: MISMATCH p95 {p95} vs {s['p95_success_ms']}")
            if len(good) != s["n"] or hash_failures:
                problems.append(f"{run}/{phase}: successes={len(good)}/{s['n']} hash_failures={hash_failures}")
            rows.append({
                "run": run, "phase": phase, "concurrency": s["concurrency"],
                "objects": s["n"], "successes": len(good), "hash_failures": hash_failures,
                "wall_s": round(s["wall_s"], 4), "MiB_s": round(goodput, 4),
                "p95_ms": round(p95, 3) if p95 is not None else "",
            })

    with open("benchmark-summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["run", "phase", "concurrency", "objects", "successes",
                                          "hash_failures", "wall_s", "MiB_s", "p95_ms"])
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(ev, "benchmark-sha256.txt"), "w") as f:
        f.write("\n".join(sums) + "\n")

    report.append("Goodput = successful bytes / 2^20 / phase wall time (MiB/s)")
    report.append("p95 = nearest-rank, rank = ceil(0.95*n) trên latency request thành công; "
                  "p95 từng trial, KHÔNG lấy trung bình")
    for phase in ("put", "get"):
        report.append(f"\n=== {phase.upper()} ===")
        med = {}
        for c in (1, 4):
            vals = [r["MiB_s"] for r in rows if r["phase"] == phase and r["concurrency"] == c]
            p95s = [r["p95_ms"] for r in rows if r["phase"] == phase and r["concurrency"] == c]
            if vals:
                med[c] = statistics.median(vals)
                report.append(f"c{c} goodput MiB/s: {vals}  median={med[c]:.3f}")
                report.append(f"c{c} p95 ms per trial: {p95s}")
        if 1 in med and 4 in med and med[1]:
            report.append(f"ratio median(c4)/median(c1) = {med[4] / med[1]:.3f}x")
    total_put = sum(r["successes"] for r in rows if r["phase"] == "put")
    total_get = sum(r["successes"] for r in rows if r["phase"] == "get" and not r["hash_failures"])
    report.append(f"\nvalid PUT = {total_put}/192, verified GET = {total_get}/192")
    report.append("\nKiểm tra: " + ("OK, không có sai lệch" if not problems else ""))
    report += [f"  - {p}" for p in problems]

    text = "\n".join(report)
    with open(os.path.join(ev, "benchmark-analysis.txt"), "w") as f:
        f.write(text + "\n")
    print(f"benchmark-summary.csv: {len(rows)} dòng\n")
    print(text)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
