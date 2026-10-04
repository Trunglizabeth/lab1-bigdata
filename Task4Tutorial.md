# Task 4 — Đo hiệu năng object storage

> Benchmark object storage với concurrency `1` và `4`. Kết quả cần có 6 trial, raw request records, goodput, nearest-rank p95, resource samples, kiểm tra integrity và policy retest.

**Điều kiện:** Task 1–3 đã hoàn thành. Storage `objects` và client `ingestor` đang Running, fixture của Task 2 vẫn tồn tại.

**Cách đọc:** mỗi bước có khối lệnh và bảng **Kỳ vọng / Nếu khác**. Nếu kết quả khác kỳ vọng thì dừng để kiểm tra, không chạy tiếp và không ghi đè evidence thất bại.

---

## Tổng quan

| Bước | Việc | Kết quả |
|---|---|---|
| 0 | Kiểm tra trước | Storage/client/PVC/metrics sẵn sàng |
| 1 | Warm-up | GET fixture thành công |
| 2 | Resource sampling | CPU/RAM/Pod/node được lấy mẫu mỗi 5 giây |
| 3 | Benchmark | 6 trial × PUT/GET |
| 4 | Kiểm tra raw evidence | Đủ 6 JSONL, request thành công và hash đúng |
| 5 | Summary | `benchmark-summary.csv` có 12 dòng kết quả |
| 6 | Phân tích | Median goodput c1/c4 và ratio |
| 7 | Policy retest | 2 expected-deny vẫn trả 403 AccessDenied |
| 8 | Individual Role D | Tự tính lại goodput + nearest-rank p95 |
| 9 | Handoff | Giữ `bench/r1-c1` cho Task 5 |

---

## Bước 0 — Kiểm tra trước

```bash
cd ~/lab1-bigdata
source env.sh

echo "$NS"                                                   # ①
kubectl config current-context                               # ②
kubectl -n "$NS" get pods                                    # ③
kubectl -n "$NS" get pvc                                     # ④
kubectl -n "$NS" get svc objects                             # ⑤
kubectl -n "$NS" top pod                                     # ⑥
mkdir -p evidence individual                                 # ⑦
```

| # | Kỳ vọng | Nếu khác |
|---|---|---|
| ① | Namespace của nhóm, ví dụ `bd-g01` | Trống → `source env.sh` |
| ② | Đúng cluster dùng cho lab | Sai → chuyển đúng context trước khi tiếp tục |
| ③ | `objects`, `ingestor` và các client cần thiết đều `Running` | Pod lỗi → `describe` / `logs`, chưa benchmark |
| ④ | `object-data` ở trạng thái `Bound` | `Pending`/không có → Task 2 chưa sẵn sàng |
| ⑤ | Service `objects` là ClusterIP, port `8333/TCP` | Không có → kiểm tra Task 2 |
| ⑥ | `kubectl top` trả CPU/RAM | Lỗi Metrics API → sửa metrics trước |
| ⑦ | Có `evidence/` và `individual/` | Tạo lại thư mục |

Không reset Task 2, không xóa PVC và không xóa storage trước benchmark.

---

## Bước 1 — Warm-up

Chạy một GET trước khi bắt đầu đo:

```bash
kubectl -n "$NS" exec ingestor -- \
  python /opt/s3lab.py probe get research-raw fixture.txt

echo "exit=$?"
```

| Kỳ vọng | Nếu khác |
|---|---|
| HTTP `200`, `ok=true`, `exit=0` | 403 → kiểm tra identity/policy; timeout/DNS → kiểm tra Service/NetworkPolicy |
| SHA-256 của fixture hợp lệ | Hash khác → fixture sai, chưa benchmark |

Warm-up **không tính là một trial**.

---

## Bước 2 — Resource sampling

Mở **Terminal 2** và chạy:

```bash
cd ~/lab1-bigdata
source env.sh
mkdir -p evidence

while true; do
  echo "===== $(date -Iseconds) ====="
  kubectl -n "$NS" top pod
  kubectl -n "$NS" get pod -o wide
  echo
  sleep 5
done | tee evidence/resource-samples.txt
```

Giữ terminal này chạy trong toàn bộ 6 benchmark trials.

Evidence phải ghi nhận:

- timestamp;
- CPU;
- memory;
- Pod status;
- Pod IP;
- node placement.

Nếu đang chạy trên shared cluster, ghi nhận thêm hoạt động đồng thời của nhóm khác nếu có.

> Không dừng sampler giữa các trial.

---

## Bước 3 — Chạy 6 benchmark trials

Mỗi trial sử dụng:

- `32` objects;
- `4 MiB/object`;
- `128 MiB/phase`;
- phase PUT;
- phase GET-with-verify.

Chỉ thay đổi concurrency. Client, credentials, object content và tài nguyên storage phải được giữ cố định.

### Thứ tự bắt buộc

| # | Run | Concurrency |
|---|---|---:|
| 1 | `r1-c1` | 1 |
| 2 | `r1-c4` | 4 |
| 3 | `r2-c4` | 4 |
| 4 | `r2-c1` | 1 |
| 5 | `r3-c1` | 1 |
| 6 | `r3-c4` | 4 |

### ① r1-c1

```bash
kubectl -n "$NS" exec ingestor -- \
  python /opt/s3lab.py bench 1 bench/r1-c1 \
  > evidence/r1-c1.jsonl

echo "exit=$?"
grep '"kind": "summary"' evidence/r1-c1.jsonl
```

### ② r1-c4

```bash
kubectl -n "$NS" exec ingestor -- \
  python /opt/s3lab.py bench 4 bench/r1-c4 \
  > evidence/r1-c4.jsonl

echo "exit=$?"
grep '"kind": "summary"' evidence/r1-c4.jsonl
```

### ③ r2-c4

```bash
kubectl -n "$NS" exec ingestor -- \
  python /opt/s3lab.py bench 4 bench/r2-c4 \
  > evidence/r2-c4.jsonl

echo "exit=$?"
grep '"kind": "summary"' evidence/r2-c4.jsonl
```

### ④ r2-c1

```bash
kubectl -n "$NS" exec ingestor -- \
  python /opt/s3lab.py bench 1 bench/r2-c1 \
  > evidence/r2-c1.jsonl

echo "exit=$?"
grep '"kind": "summary"' evidence/r2-c1.jsonl
```

### ⑤ r3-c1

```bash
kubectl -n "$NS" exec ingestor -- \
  python /opt/s3lab.py bench 1 bench/r3-c1 \
  > evidence/r3-c1.jsonl

echo "exit=$?"
grep '"kind": "summary"' evidence/r3-c1.jsonl
```

### ⑥ r3-c4

```bash
kubectl -n "$NS" exec ingestor -- \
  python /opt/s3lab.py bench 4 bench/r3-c4 \
  > evidence/r3-c4.jsonl

echo "exit=$?"
grep '"kind": "summary"' evidence/r3-c4.jsonl
```

Sau mỗi trial:

| Kỳ vọng | Nếu khác |
|---|---|
| `exit=0` | Giữ failed evidence, không ghi đè |
| Có summary `put` và `get` | Thiếu phase → trial chưa hợp lệ |
| `n=32` | Kiểm tra benchmark helper |
| `successes=32` | Xem request records bị lỗi |
| `success_ratio=1.0` | Xác định request thất bại |
| GET verify hash thành công | Hash mismatch → không tính verified GET |

Nếu một attempt thất bại, giữ file cũ, ví dụ:

```text
r1-c4-attempt1.jsonl
```

sau đó mới sửa lỗi và chạy lại.

---

## Bước 4 — Dừng sampler và kiểm tra raw evidence

Sau khi `r3-c4` hoàn thành, sang Terminal 2 nhấn:

```text
Ctrl+C
```

Kiểm tra:

```bash
ls -lh evidence/r*-c*.jsonl evidence/resource-samples.txt

wc -l evidence/r*-c*.jsonl

grep -h '"kind": "summary"' evidence/r*-c*.jsonl
```

Với helper hiện tại, mỗi trial gồm:

```text
32 PUT request records
 1 PUT summary
32 GET request records
 1 GET summary
----------------------
66 dòng/trial
```

Sáu trial tương ứng `396` dòng.

Không dùng số dòng làm tiêu chí duy nhất: vẫn phải kiểm tra summary, successes và hash.

---

## Bước 5 — Metrics và benchmark-summary.csv

### Goodput

Tính riêng cho PUT và GET:

```text
Goodput (MiB/s)
= successful bytes / 2^20 / phase wall time
```

Nếu cả 32 object đều thành công:

```text
32 × 4 MiB = 128 MiB
```

### Nearest-rank p95

Chỉ sử dụng successful request latency:

```text
rank = ceil(0.95 × n)
```

Với `n=32`:

```text
ceil(0.95 × 32)
= ceil(30.4)
= 31
```

Do đó p95 là phần tử thứ `31` sau khi sort latency tăng dần.

**Không average p95 của nhiều trial.**

### CSV bắt buộc

```text
run,phase,concurrency,objects,successes,hash_failures,wall_s,MiB_s,p95_ms
```

Tạo CSV:

```bash
python3 - <<'PY'
import json
import csv
import glob

rows = []

for filename in sorted(glob.glob("evidence/r*-c*.jsonl")):
    with open(filename) as f:
        records = [json.loads(line) for line in f]

    summaries = [r for r in records if r.get("kind") == "summary"]

    for s in summaries:
        phase = s["phase"]

        if phase == "get":
            reqs = [
                r for r in records
                if r.get("kind") != "summary"
                and r.get("op") == "get"
            ]

            hash_failures = sum(
                1 for r in reqs
                if r.get("ok") and r.get("hash_ok") is False
            )
        else:
            hash_failures = 0

        rows.append([
            s["run"].split("/")[-1],
            phase,
            s["concurrency"],
            s["n"],
            s["successes"],
            hash_failures,
            s["wall_s"],
            s["goodput_MiB_s"],
            s["p95_success_ms"],
        ])

with open("evidence/benchmark-summary.csv", "w", newline="") as f:
    w = csv.writer(f)

    w.writerow([
        "run", "phase", "concurrency", "objects",
        "successes", "hash_failures",
        "wall_s", "MiB_s", "p95_ms"
    ])

    w.writerows(rows)

print("Created evidence/benchmark-summary.csv")
PY
```

Kiểm tra:

```bash
cat evidence/benchmark-summary.csv
wc -l evidence/benchmark-summary.csv
```

| Kỳ vọng | Nếu khác |
|---|---|
| Header + 12 result rows = 13 dòng | Thiếu → kiểm tra 6 JSONL |
| Mỗi trial có PUT và GET | Thiếu → trial không hoàn chỉnh |
| `objects=32` | Kiểm tra helper |
| `successes=32` | Kiểm tra request failures |
| `hash_failures=0` | GET integrity chưa đạt |

---

## Bước 6 — Median goodput và ratio

So sánh **median của 3 trial** cho mỗi concurrency.

```bash
python3 - <<'PY'
import csv
import statistics

data = []

with open("evidence/benchmark-summary.csv") as f:
    data = list(csv.DictReader(f))

for phase in ["put", "get"]:
    print(f"\n=== {phase.upper()} ===")

    medians = {}

    for c in [1, 4]:
        values = [
            float(r["MiB_s"])
            for r in data
            if r["phase"] == phase
            and int(r["concurrency"]) == c
        ]

        medians[c] = statistics.median(values)

        print(f"c{c} values :", [round(x, 3) for x in values])
        print(f"c{c} median : {medians[c]:.3f} MiB/s")

    print(f"c4/c1 ratio: {medians[4] / medians[1]:.3f}x")
PY
```

Phải báo cáo riêng:

```text
PUT median(c1)
PUT median(c4)
PUT ratio = median(c4) / median(c1)

GET median(c1)
GET median(c4)
GET ratio = median(c4) / median(c1)
```

Giả thuyết là concurrency `4` **có thể** tăng application goodput so với concurrency `1`.

Concurrency `4` không nhanh hơn **không có nghĩa benchmark thất bại**. Kết quả âm hoặc chưa kết luận vẫn được chấp nhận nếu phép đo và evidence hợp lệ.

---

## Bước 7 — Post-benchmark policy retest

Sau benchmark, chạy lại hai expected-deny cases từ Task 3.

### S08 — analyst PUT research-release

```bash
kubectl -n "$NS" exec analyst -- \
  python /opt/s3lab.py probe put research-release auth-probe.txt \
  > evidence/task4-retest-S08.json

echo "exit=$?"
cat evidence/task4-retest-S08.json
```

Kỳ vọng:

```text
HTTP 403
AccessDenied
ok=false
exit=2
```

### S10 — analyst GET research-raw

```bash
kubectl -n "$NS" exec analyst -- \
  python /opt/s3lab.py probe get research-raw fixture.txt \
  > evidence/task4-retest-S10.json

echo "exit=$?"
cat evidence/task4-retest-S10.json
```

Kỳ vọng:

```text
HTTP 403
AccessDenied
ok=false
exit=2
```

Timeout, DNS failure, HTTP 404 hoặc invalid credentials **không được tính là expected-deny PASS**.

---

## Bước 8 — Individual requirement (Role D)

Role D phải tự tính lại goodput và nearest-rank p95 cho một trial từ raw request records.

Có thể chọn `r1-c1`.

### PUT p95

```bash
python3 - <<'PY'
import json
import math

with open("evidence/r1-c1.jsonl") as f:
    records = [json.loads(line) for line in f]

put = [
    r for r in records
    if r.get("kind") != "summary"
    and r.get("op") == "put"
    and r.get("ok")
]

latencies = sorted(r["ms"] for r in put)

rank = math.ceil(0.95 * len(latencies))

print("Successful PUT:", len(put))
print("p95 rank:", rank)
print("p95:", latencies[rank - 1], "ms")
```

### PUT goodput

```bash
python3 - <<'PY'
import json

with open("evidence/r1-c1.jsonl") as f:
    records = [json.loads(line) for line in f]

put = [
    r for r in records
    if r.get("kind") != "summary"
    and r.get("op") == "put"
    and r.get("ok")
]

summary = next(
    r for r in records
    if r.get("kind") == "summary"
    and r.get("phase") == "put"
)

successful_bytes = sum(r["bytes"] for r in put)
mib = successful_bytes / (2**20)
goodput = mib / summary["wall_s"]

print("Successful MiB:", mib)
print("Wall time:", summary["wall_s"])
print("Recalculated goodput:", goodput)
print("Summary goodput:", summary["goodput_MiB_s"])
```

Làm tương tự với GET.

Lưu phép tính và kết quả vào:

```text
individual/task4-recalc.txt
```

Giá trị tự tính phải khớp summary.

---

## Bước 9 — Diễn giải kết quả

Báo cáo:

- success rate;
- hash failures;
- median PUT goodput;
- median GET goodput;
- ratio `c4/c1`;
- p95 của từng trial;
- resource observations;
- policy retest.

Không average các p95 thành một p95 chung.

Các confounder cần cân nhắc:

- cache;
- CPU scheduling;
- network;
- storage backend;
- shared-cluster activity.

Resource samples có thể hỗ trợ diễn giải nhưng **không tự chứng minh nguyên nhân**.

Ví dụ: CPU tăng cùng lúc với latency tăng không đủ để kết luận CPU là nguyên nhân nếu chưa có bằng chứng bổ sung.

---

## Bước 10 — Handoff cho Task 5

Task 5 cần verify object tại:

```text
bench/r1-c1
```

Sau Task 4:

- không xóa namespace;
- không xóa PVC;
- không reset Task 2;
- không xóa object `bench/r1-c1`;
- bàn giao cluster cho người phụ trách Task 5.

Trên shared/official cluster, chỉ một người thao tác cluster tại một thời điểm.

---

## Tiêu chí nghiệm thu

| Hạng mục | Kiểm tra | Evidence |
|---|---|---|
| Benchmark | Đủ 6 trial theo đúng thứ tự | `r*-c*.jsonl` |
| PUT | 32 successful PUT/trial | raw JSONL + summary |
| GET integrity | 32 verified GET/trial, hash failure = 0 | raw JSONL + CSV |
| Metrics | Goodput + nearest-rank p95 đúng | `benchmark-summary.csv` |
| Comparison | Median c1/c4 + ratio cho PUT/GET | analysis |
| Resources | Sampling khoảng 5 giây trong benchmark | `resource-samples.txt` |
| Security | 2 expected-deny retest PASS | `task4-retest-*.json` |
| Individual D | Tự tính lại một trial | `individual/task4-recalc.txt` |
| Handoff | `bench/r1-c1` còn nguyên | Task 5 verify |

Mục tiêu integrity nếu cả sáu trial thành công:

```text
6 × 32 = 192 valid PUT
6 × 32 = 192 verified GET
```

---

## Lỗi thường gặp

| Hiện tượng | Nguyên nhân / cách xử lý |
|---|---|
| `kubectl top` lỗi | Metrics API chưa sẵn sàng |
| Warm-up 403 | Sai identity/policy |
| Warm-up timeout/DNS | Kiểm tra Service, endpoint và NetworkPolicy |
| Benchmark `exit != 0` | Giữ evidence attempt cũ, kiểm tra raw error |
| `successes < 32` | Xem request record thất bại |
| `hash_failures > 0` | Integrity GET không đạt |
| Chỉ có 1 summary | Một phase không hoàn thành |
| CSV thiếu 12 rows | Thiếu trial/phase hoặc glob sai |
| c4 chậm hơn c1 | Không tự coi là lỗi; báo cáo đúng kết quả |
| p95 khác khi tự tính | Kiểm tra chỉ lấy successful requests và nearest-rank |
| Task 5 không thấy `bench/r1-c1` | Có thể object/storage đã bị reset hoặc xóa |

Lỗi thì **giữ evidence cũ**, đổi tên thành `...-attempt1`, sửa rồi chạy lại. Không ghi đè failed evidence.

---

## Không commit

Không commit:

```text
private/
*.env
s3.json
observer.json
kubeconfig/token
```

`evidence/` của cluster luyện tập cá nhân không được dùng làm official evidence.

Chỉ đưa official evidence vào submission khi nhóm thực hiện buổi chạy chính thức theo quy trình của lab.

`Task4Tutorial.md` là tài liệu hướng dẫn và có thể commit vào branch Task 4.
