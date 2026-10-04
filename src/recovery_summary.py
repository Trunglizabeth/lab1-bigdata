#!/usr/bin/env python3
"""Task 5: điền recovery-summary.json bằng giá trị đo thật từ evidence/.

    python3 src/recovery_summary.py

Đọc pod-/pvc-before|after.json, before-/after-recovery.jsonl, canary.jsonl,
delete-time.txt, rollout-time.txt, recovery-S06/S08/S10.json. Không có giá trị nào gõ tay.
"""
import json
import os
from datetime import datetime

EV = "evidence"
FIXTURE_SHA = "9ce4c8bb96c85122c3b386653fbe9150cb2f4df03f25c83408fe11c29b87d6f8"
TARGET_S = 120


def p(name):
    return os.path.join(EV, name)


def load(name):
    with open(p(name)) as f:
        return json.load(f)


def jsonl(name):
    with open(p(name)) as f:
        return [json.loads(x) for x in f if x.strip().startswith("{")]


def ts(name):
    with open(p(name)) as f:
        return datetime.fromisoformat(f.read().strip().replace("Z", "+00:00"))


def verified(name):
    rows = jsonl(name)
    last = rows[-1] if rows else {}
    ok = sum(1 for r in rows if r.get("op") == "get" and r.get("hash_ok"))
    return {"objects_verified": ok, "complete": last.get("kind") == "verified" and last.get("objects") == 32}


def probe(name, expect):
    r = jsonl(name)[-1]
    if expect == "allow":
        passed = r.get("http") == 200 and r.get("ok") and r.get("sha256") == FIXTURE_SHA
    else:
        passed = r.get("http") == 403 and r.get("error") == "AccessDenied"
    return {"http": r.get("http"), "error": r.get("error"), "expected": expect, "pass": bool(passed)}


def main():
    pb, pa = load("pod-before.json")["items"], load("pod-after.json")["items"]
    xb, xa = load("pvc-before.json"), load("pvc-after.json")
    canary = jsonl("canary.jsonl")
    bad = [i for i, r in enumerate(canary) if not r.get("ok")]
    first = bad[0] if bad else None
    stable = None
    if first is not None:
        stable = next((i for i in range(first + 1, len(canary) - 4)
                       if all(r.get("ok") and r.get("hash_ok") for r in canary[i:i + 5])), None)
    deleted, rolled = ts("delete-time.txt"), ts("rollout-time.txt")
    ready_s = (rolled - deleted).total_seconds()
    t_obs = round(canary[stable]["end_s"] - canary[first]["start_s"], 3) if stable is not None else None

    out = {
        "pod_name_before": pb[0]["metadata"]["name"],
        "pod_name_after": pa[0]["metadata"]["name"] if len(pa) == 1 else [x["metadata"]["name"] for x in pa],
        "pod_uid_before": pb[0]["metadata"]["uid"],
        "pod_uid_after": pa[0]["metadata"]["uid"],
        "pod_uid_changed": pb[0]["metadata"]["uid"] != pa[0]["metadata"]["uid"],
        "pods_after": len(pa),
        "pvc_uid_before": xb["metadata"]["uid"],
        "pvc_uid_after": xa["metadata"]["uid"],
        "pvc_uid_unchanged": xb["metadata"]["uid"] == xa["metadata"]["uid"],
        "pvc_phase_after": xa["status"].get("phase"),
        "pv_volume": xa["spec"].get("volumeName"),
        "node_before": pb[0]["spec"].get("nodeName"),
        "node_after": pa[0]["spec"].get("nodeName"),
        "image_id_after": pa[0]["status"]["containerStatuses"][0].get("imageID"),
        "verified_before": verified("before-recovery.jsonl"),
        "verified_after": verified("after-recovery.jsonl"),
        "delete_time_utc": deleted.isoformat(),
        "rollout_complete_utc": rolled.isoformat(),
        "delete_to_rollout_s": round(ready_s, 3),
        "recovery_target_s": TARGET_S,
        "ready_within_target": ready_s <= TARGET_S,
        "canary_samples": len(canary),
        "failed_reads": len(bad),
        "first_failure_start_s": canary[first]["start_s"] if first is not None else None,
        "first_failure_utc": canary[first].get("utc") if first is not None else None,
        "first_failure_error": canary[first].get("error") if first is not None else None,
        "stable_read_end_s": canary[stable]["end_s"] if stable is not None else None,
        "observed_interruption_s": t_obs,
        "interruption_within_target": (t_obs <= TARGET_S) if t_obs is not None else None,
        "interruption_note": ("interruption not observed at this sampling resolution" if first is None
                              else "recovery not proven: no 5 consecutive good reads" if stable is None
                              else "T_observed = stable_read_end_s - first_failure_start_s"),
        "sampling_limit": "Canary reads approximately once per second; request durations vary. "
                          "Observed interruption is not exact downtime.",
        "policy_retests": {
            "S06": probe("recovery-S06.json", "allow"),
            "S08": probe("recovery-S08.json", "deny"),
            "S10": probe("recovery-S10.json", "deny"),
        },
        "unproven": ["high availability", "backup restore", "crash consistency",
                     "node-loss durability", "TLS", "encryption at rest"],
    }
    with open("recovery-summary.json", "w") as f:
        json.dump(out, f, indent=2)
        f.write("\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
