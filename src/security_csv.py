#!/usr/bin/env python3
"""Sinh security-results.csv (S01–S12, K01–K06, N01–N04) từ raw evidence của Task 3.

Chạy từ gốc repo, sau khi đã chạy đủ các lệnh Task 3:

    python3 src/security_csv.py --operator "Trung Nguyen" --reviewer "Hai Anh"

Kết quả pass/fail/inconclusive được suy ra từ file evidence, không gõ tay:
  - S3 Allow : HTTP 200 (GET còn phải đúng SHA-256 fixture)
  - S3 Deny  : chỉ pass khi HTTP 403 + AccessDenied. Timeout/DNS/404/credential lỗi
               -> inconclusive. Request bị cấm mà thành công -> fail (control hỏng).
  - RBAC     : Allow pass khi không Forbidden; Deny pass khi Forbidden đúng principal observer.
  - Network  : Blocked chỉ pass khi tcp_connected=false VÀ positive control ngay sau đó true.
Nếu có file *-attempt*.json/txt (lần lỗi cũ), đường dẫn được ghi kèm vào cột evidence.
"""
import argparse
import csv
import glob
import json
import os
import re

FIXTURE_SHA = "9ce4c8bb96c85122c3b386653fbe9150cb2f4df03f25c83408fe11c29b87d6f8"
OBSERVER = "system:serviceaccount:{ns}:observer"

S3 = [
    ("S01", "ingestor", "PUT research-raw/auth-probe.txt", "Allow"),
    ("S02", "ingestor", "GET research-raw/fixture.txt", "Allow"),
    ("S03", "ingestor", "LIST research-raw", "Allow"),
    ("S04", "ingestor", "PUT research-release/auth-probe.txt", "Deny"),
    ("S05", "ingestor", "GET research-release/fixture.txt", "Deny"),
    ("S06", "analyst", "GET research-release/fixture.txt", "Allow"),
    ("S07", "analyst", "LIST research-release", "Allow"),
    ("S08", "analyst", "PUT research-release/auth-probe.txt", "Deny"),
    ("S09", "analyst", "DELETE research-release/delete-probe.txt", "Deny"),
    ("S10", "analyst", "GET research-raw/fixture.txt", "Deny"),
    ("S11", "analyst", "LIST research-raw", "Deny"),
    ("S12", "anonymous", "GET research-release/fixture.txt", "Deny"),
]
K8S = [
    ("K01", "list pods", "Allow"),
    ("K02", "get events", "Allow"),
    ("K03", "get pods/log (storage Pod)", "Allow"),
    ("K04", "get secret s3-config", "Deny"),
    ("K05", "create pod (dry-run=server)", "Deny"),
    ("K06", "delete storage pod (dry-run=server)", "Deny"),
]
NET = [
    ("N01", "owner (access=s3) in {ns}", "objects:8333", "Connect", None),
    ("N02", "blocked (no access label) in {ns}", "objects:8333", "Blocked", "N01-after-N02.txt"),
    ("N03", "owner (access=s3) in {ns}", "storage PodIP:8888", "Blocked", "N01-after-N03.txt"),
    ("N04", "bd-outsider/outsider (access=s3)", "objects.{ns}.svc.cluster.local:8333", "Blocked", "N01-after-N04.txt"),
]


def last_json(path):
    with open(path, encoding="utf-8") as f:
        lines = [x for x in f.read().splitlines() if x.strip().startswith("{")]
    return json.loads(lines[-1]) if lines else None


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return None


def attempts(ev, test_id):
    return sorted(glob.glob(os.path.join(ev, f"{test_id}-attempt*")))


def s3_row(ev, tid, expected):
    path = os.path.join(ev, f"{tid}.json")
    if not os.path.exists(path):
        return "missing evidence", "inconclusive", [path]
    r = last_json(path)
    if r is None:
        return "empty evidence", "inconclusive", [path]
    http, err, ok = r.get("http"), r.get("error"), r.get("ok")
    actual = f"principal={r.get('principal')}; HTTP {http}; error={err}; ok={ok}"
    if r.get("op") == "get" and r.get("sha256"):
        actual += "; sha256=" + ("fixture" if r["sha256"] == FIXTURE_SHA else r["sha256"][:12])
    if r.get("op") == "list" and "keys" in r:
        actual += f"; keys={len(r['keys'])}"
    if expected == "Allow":
        good = http == 200 and ok and (r.get("op") != "get" or r.get("sha256") == FIXTURE_SHA)
        status = "pass" if good else ("inconclusive" if http is None else "fail")
    else:
        if tid == "S12" and r.get("principal") != "anonymous":
            status = "inconclusive"
        elif http == 403 and err == "AccessDenied":
            status = "pass"
        elif ok:
            status = "fail"  # forbidden operation succeeded = failed control
        else:
            status = "inconclusive"  # timeout, DNS, 404, bad credential: not authorization evidence
    return actual, status, [path]


def k8s_row(ev, tid, expected, principal):
    out_p = os.path.join(ev, f"{tid}.stdout.txt")
    err_p = os.path.join(ev, f"{tid}.stderr.txt")
    out, err = read(out_p), read(err_p)
    if out is None and err is None:
        return "missing evidence", "inconclusive", [out_p, err_p]
    out, err = out or "", err or ""
    forbidden = "Forbidden" in err or "forbidden" in err
    if expected == "Allow":
        lines = len([x for x in out.splitlines() if x.strip()])
        if forbidden:
            actual, status = "Forbidden: " + err.strip().splitlines()[-1][:160], "fail"
        elif lines or "No resources found" in err:
            actual, status = f"allowed; stdout_lines={lines}", "pass"
        else:
            actual, status = "no output: " + err.strip()[:160], "inconclusive"
    else:
        if forbidden:
            line = next(x for x in err.splitlines() if "orbidden" in x)
            actual = "Forbidden: " + line.strip()[:200]
            status = "pass" if principal in err else "inconclusive"
        elif out.strip():
            actual, status = "UNEXPECTED SUCCESS: " + out.strip().splitlines()[0][:160], "fail"
        else:
            actual, status = "error: " + err.strip()[:160], "inconclusive"
    return actual, status, [out_p, err_p]


def tcp(path):
    if not os.path.exists(path):
        return None
    r = last_json(path)
    return None if r is None else r


def net_row(ev, tid, expected, control):
    path = os.path.join(ev, f"{tid}.txt")
    r = tcp(path)
    paths = [path]
    if r is None:
        return "missing evidence", "inconclusive", paths
    connected = r.get("tcp_connected")
    actual = f"tcp_connected={str(connected).lower()}"
    if r.get("error"):
        actual += f" ({r['error']})"
    if expected == "Connect":
        return actual, ("pass" if connected else "fail"), paths
    if connected:
        return actual, "fail", paths
    cpath = os.path.join(ev, control)
    paths.append(cpath)
    c = tcp(cpath)
    if c is None or not c.get("tcp_connected"):
        return actual + "; positive control after=missing/false", "inconclusive", paths
    actual += "; positive control after=true"
    status = "pass"
    if tid == "N03":
        lp = os.path.join(ev, "N03-listen-check.txt")
        paths.append(lp)
        if "8888" in (read(lp) or ""):
            actual += "; port 8888 listening (storage log)"
        else:
            actual += "; 8888 listener NOT proven"
            status = "inconclusive"
    if tid == "N04":
        dp = os.path.join(ev, "N04-dns.txt")
        np_ = os.path.join(ev, "N04-outsider-netpol.txt")
        paths += [dp, np_]
        dns = (read(dp) or "").strip()
        if re.search(r"\d+\.\d+\.\d+\.\d+", dns):
            actual += f"; DNS resolved {dns.splitlines()[-1]}"
        else:
            actual += "; DNS NOT proven"
            status = "inconclusive"
        if "No resources found" in (read(np_) or ""):
            actual += "; no NetworkPolicy in bd-outsider"
        else:
            actual += "; bd-outsider NetworkPolicy not ruled out"
            status = "inconclusive"
    return actual, status, paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", default="evidence")
    ap.add_argument("--out", default="security-results.csv")
    ap.add_argument("--ns", default=os.environ.get("NS", "bd-g01"))
    ap.add_argument("--operator", required=True, help="người thật chạy lệnh")
    ap.add_argument("--reviewer", default="PENDING", help="người kiểm tra chéo thật")
    a = ap.parse_args()
    principal = OBSERVER.format(ns=a.ns)

    rows = []

    def add(tid, who, target, expected, result):
        actual, status, paths = result
        old = attempts(a.evidence, tid)
        if old:
            actual += f"; earlier attempt(s) retained: {len(old)}"
        rows.append({
            "test_id": tid, "principal": who, "target": target,
            "expected": expected, "actual": actual, "status": status,
            "operator": a.operator, "reviewer": a.reviewer,
            "evidence": ";".join(p for p in old + paths),
        })

    for tid, who, target, exp in S3:
        add(tid, f"S3:{who}", target, exp, s3_row(a.evidence, tid, exp))
    for tid, target, exp in K8S:
        add(tid, principal, f"{a.ns}: {target}", exp, k8s_row(a.evidence, tid, exp, principal))
    for tid, who, target, exp, control in NET:
        add(tid, who.format(ns=a.ns), target.format(ns=a.ns), exp,
            net_row(a.evidence, tid, exp, control))

    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    width = max(len(r["actual"]) for r in rows)
    for r in rows:
        print(f"{r['test_id']}  {r['expected']:<8} {r['status']:<13} {r['actual'][:min(width, 100)]}")
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"\n{a.out}: {len(rows)} rows, {counts}")


if __name__ == "__main__":
    main()
