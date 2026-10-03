"""Định dạng output khó đọc thành bảng để đối chiếu với Task2Tutorial.md.
Chỉ dùng để XEM; evidence vẫn lưu bản gốc (JSON/JSONL).

  kubectl -n "$NS" get resourcequota team-budget -o json | python3 src/fmt.py quota
  python3 src/fmt.py results evidence/seed.jsonl evidence/T2-*.json
  kubectl -n "$NS" get pod,pvc -o json | python3 src/fmt.py uids
"""
import json, sys

FIXTURE_SHA = "9ce4c8bb96c85122c3b386653fbe9150cb2f4df03f25c83408fe11c29b87d6f8"


def table(header, rows):
    rows = [[("-" if c is None or c == "" else str(c)) for c in r] for r in rows]
    w = [max(len(str(x)) for x in col) for col in zip(header, *rows)]
    line = lambda r: "  ".join(str(c).ljust(n) for c, n in zip(r, w)).rstrip()
    print(line(header))
    print("  ".join("-" * n for n in w))
    for r in rows:
        print(line(r))


def quota(doc):
    hard, used = doc["status"]["hard"], doc["status"].get("used", {})
    table(["RESOURCE", "USED", "HARD"],
          [[k, used.get(k, "0"), hard[k]] for k in sorted(hard)])


def results(paths):
    rows = []
    for p in paths:
        for raw in open(p, encoding="utf-8"):
            raw = raw.strip()
            if not raw.startswith("{"):
                continue
            r = json.loads(raw)
            if "op" not in r:
                continue
            sha = r.get("sha256")
            rows.append([r.get("principal"), r.get("op", "").upper(), r.get("bucket"),
                         r.get("key"), r.get("http") or r.get("error"),
                         "OK" if r.get("ok") else "FAIL", r.get("bytes"),
                         ("khớp" if sha == FIXTURE_SHA else sha[:12] + "…") if sha else None])
    table(["PRINCIPAL", "OP", "BUCKET", "KEY", "HTTP", "KẾT QUẢ", "BYTES", "SHA256"], rows)


def short_image(image_id):
    if not image_id:
        return None
    repo, _, dig = image_id.partition("@sha256:")
    return repo.split("/")[-1] + "@" + dig[:12] + "…"


def uids(doc):
    rows = []
    for it in doc.get("items", [doc]):
        m, kind = it["metadata"], it["kind"]
        if kind == "Pod":
            cs = (it.get("status", {}).get("containerStatuses") or [{}])[0]
            rows.append(["Pod", m["name"], m["uid"], it["status"].get("phase"),
                         it["spec"].get("nodeName"), short_image(cs.get("imageID"))])
        elif kind == "PersistentVolumeClaim":
            rows.append(["PVC", m["name"], m["uid"], it["status"].get("phase"),
                         it["spec"].get("storageClassName"), it["spec"].get("volumeName")])
    table(["KIND", "NAME", "UID", "PHASE", "NODE / SC", "IMAGE / VOLUME"], rows)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    mode = sys.argv[1]
    if mode == "quota":
        quota(json.load(sys.stdin))
    elif mode == "results":
        results(sys.argv[2:])
    elif mode == "uids":
        uids(json.load(sys.stdin))
    else:
        raise SystemExit(__doc__)
