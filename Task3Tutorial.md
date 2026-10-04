# Task 3 — Access Governance

> 30 phút · 20 điểm nhóm · Kết quả: chứng minh quyền truy cập S3, Kubernetes RBAC và NetworkPolicy bằng evidence thực tế.

**Điều kiện:** đã hoàn thành Task 1 và Task 2 trên cluster. Storage `objects`, PVC, Service, các client Pod và fixture phải đang tồn tại.

**Cách đọc:** chạy lần lượt từng bước. Với mỗi test, so kết quả thực tế với kết quả dự kiến. Nếu khác kỳ vọng thì dừng, kiểm tra nguyên nhân và giữ lại evidence lần lỗi; không tự coi là PASS.

> **Lưu ý:** nếu đang chạy trên cluster cá nhân để luyện tập thì **không commit `evidence/` luyện tập vào bài chính thức**. Evidence nộp bài phải lấy từ lần chạy chính thức của nhóm.

---

## 1. Tổng quan

| Phần | Số test | Mục tiêu |
|---|---:|---|
| S3 authorization | 12 | S01–S12 |
| Kubernetes RBAC | 6 | K01–K06 |
| Network reachability | 4 | N01–N04 |
| Cross-check | 1 | Xác nhận quota reject của Task 1 |
| Individual test | 2 request | `analyst`: 1 Allow + 1 Deny + giải thích |

Artifact chính:

```text
observer.py
policies-redacted.json
security-results.csv
individual/
evidence/
```

Tuyệt đối không commit:

```text
private/
private/s3.json
private/*.env
private/observer.json
access key
secret key
kubeconfig có token
```

---

## 2. Bước 0 — Preflight

### 2.1 Kiểm tra Docker / k3d / kubectl

```bash
cd ~/lab1-bigdata
source env.sh

docker ps
k3d cluster list
kubectl config current-context
echo "$NS"
kubectl get namespaces
```

Kỳ vọng:

- Docker truy cập được từ WSL.
- cluster `bigdata` / context `k3d-bigdata` đang chạy.
- `NS=bd-g01`.
- có namespace `bd-g01`.
- theo Task 1 local setup, cần thêm namespace `bd-outsider` để chạy N04.

Nếu gặp:

```text
The connection to the server ... was refused
```

hoặc:

```text
Cannot connect to the Docker daemon
```

thì chưa được chạy Task 3. Trên Windows mở:

```text
Docker Desktop
→ Settings
→ Resources
→ WSL Integration
→ bật Ubuntu-24.04
→ Apply & Restart
```

sau đó quay lại WSL và kiểm tra lại `docker ps`, `k3d cluster list`, `kubectl get namespaces`.

### 2.2 Kiểm tra tài nguyên Task 1 + Task 2

```bash
kubectl -n "$NS" get pod
kubectl -n "$NS" get pvc
kubectl -n "$NS" get svc objects
kubectl -n "$NS" get networkpolicy private-object-store
kubectl -n "$NS" get serviceaccount,role,rolebinding observer
ls -l observer.py
ls -l policies-redacted.json
```

Kỳ vọng:

- `owner`, `ingestor`, `analyst`, `blocked`, `objects-...` đều Running.
- PVC `object-data` ở trạng thái Bound.
- Service `objects` là ClusterIP, port `8333/TCP`.
- NetworkPolicy `private-object-store` tồn tại.
- ServiceAccount/Role/RoleBinding `observer` tồn tại.

Nếu storage/client chưa tồn tại hoặc fixture chưa được seed → hoàn thành Task 2 trước.

---

## 3. Bước 1 — Tạo kubeconfig observer

```bash
python3 observer.py
```

Kiểm tra:

```bash
ls -l private/observer.json
```

Kỳ vọng:

```text
-rw------- ... private/observer.json
```

Không `cat private/observer.json` vì file chứa token.

Đặt biến:

```bash
OBS=private/observer.json

POD=$(kubectl -n "$NS" get pod -l app=objects \
  -o jsonpath='{.items[0].metadata.name}')

echo "$POD"
```

Task 3 phải chứng minh RBAC bằng request API thật dưới identity `observer`, không chỉ dùng `kubectl auth can-i`.

---

# 4. Bước 2 — 12 S3 authorization tests

## 4.1 Matrix

| ID | Identity | Request | Dự kiến |
|---|---|---|---|
| S01 | ingestor | PUT `research-raw/auth-probe.txt` | Allow |
| S02 | ingestor | GET `research-raw/fixture.txt` | Allow |
| S03 | ingestor | LIST `research-raw` | Allow |
| S04 | ingestor | PUT `research-release/auth-probe.txt` | Deny |
| S05 | ingestor | GET `research-release/fixture.txt` | Deny |
| S06 | analyst | GET `research-release/fixture.txt` | Allow |
| S07 | analyst | LIST `research-release` | Allow |
| S08 | analyst | PUT `research-release/auth-probe.txt` | Deny |
| S09 | analyst | DELETE `research-release/delete-probe.txt` | Deny |
| S10 | analyst | GET `research-raw/fixture.txt` | Deny |
| S11 | analyst | LIST `research-raw` | Deny |
| S12 | anonymous | GET `research-release/fixture.txt` | Deny |

### S01

```bash
kubectl -n "$NS" exec ingestor -- \
  python /opt/s3lab.py probe put research-raw auth-probe.txt \
  > evidence/S01.json
```

Kỳ vọng: `HTTP 200`, `ok=true`.

### S02

```bash
kubectl -n "$NS" exec ingestor -- \
  python /opt/s3lab.py probe get research-raw fixture.txt \
  > evidence/S02.json
```

Kỳ vọng: `HTTP 200`, `ok=true`.

SHA-256 fixture:

```text
9ce4c8bb96c85122c3b386653fbe9150cb2f4df03f25c83408fe11c29b87d6f8
```

### S03

```bash
kubectl -n "$NS" exec ingestor -- \
  python /opt/s3lab.py probe list research-raw "" \
  > evidence/S03.json
```

Kỳ vọng: `HTTP 200`, list thành công.

### S04

```bash
kubectl -n "$NS" exec ingestor -- \
  python /opt/s3lab.py probe put research-release auth-probe.txt \
  > evidence/S04.json
```

Kỳ vọng: `HTTP 403 AccessDenied`.

### S05

```bash
kubectl -n "$NS" exec ingestor -- \
  python /opt/s3lab.py probe get research-release fixture.txt \
  > evidence/S05.json
```

Kỳ vọng: `HTTP 403 AccessDenied`.

### S06

```bash
kubectl -n "$NS" exec analyst -- \
  python /opt/s3lab.py probe get research-release fixture.txt \
  > evidence/S06.json
```

Kỳ vọng: `HTTP 200`, `ok=true`.

### S07

```bash
kubectl -n "$NS" exec analyst -- \
  python /opt/s3lab.py probe list research-release "" \
  > evidence/S07.json
```

Kỳ vọng: `HTTP 200`.

### S08

```bash
kubectl -n "$NS" exec analyst -- \
  python /opt/s3lab.py probe put research-release auth-probe.txt \
  > evidence/S08.json
```

Kỳ vọng: `HTTP 403 AccessDenied`.

### S09

```bash
kubectl -n "$NS" exec analyst -- \
  python /opt/s3lab.py probe delete research-release delete-probe.txt \
  > evidence/S09.json
```

Kỳ vọng: `HTTP 403 AccessDenied`.

> Chỉ dùng `delete-probe.txt`; không DELETE dữ liệu thật.

### S10

```bash
kubectl -n "$NS" exec analyst -- \
  python /opt/s3lab.py probe get research-raw fixture.txt \
  > evidence/S10.json
```

Kỳ vọng: `HTTP 403 AccessDenied`.

### S11

```bash
kubectl -n "$NS" exec analyst -- \
  python /opt/s3lab.py probe list research-raw "" \
  > evidence/S11.json
```

Kỳ vọng: `HTTP 403 AccessDenied`.

### S12

```bash
kubectl -n "$NS" exec owner -- \
  python /opt/s3lab.py probe get research-release fixture.txt anon \
  > evidence/S12.json
```

Kỳ vọng:

```text
principal=anonymous
HTTP 403
AccessDenied
ok=false
```

## 4.2 Quy tắc PASS cho S3 Deny

Một S3 Deny chỉ PASS khi request đúng trả về:

```text
HTTP 403
AccessDenied
```

Các trường hợp sau không đủ để chứng minh authorization:

```text
timeout
DNS error
HTTP 404
InvalidAccessKeyId
SignatureDoesNotMatch
service unavailable
```

Các test Deny có thể khiến `kubectl exec` báo:

```text
command terminated with exit code 2
```

Điều đó vẫn bình thường nếu JSON evidence chứa:

```text
"http": 403
"error": "AccessDenied"
"ok": false
```

---

# 5. Bước 3 — 6 Kubernetes RBAC tests

## 5.1 Matrix

| ID | Request observer | Dự kiến |
|---|---|---|
| K01 | LIST Pods | Allow |
| K02 | GET Events | Allow |
| K03 | Read storage Pod logs | Allow |
| K04 | GET Secret `s3-config` | Deny |
| K05 | CREATE Pod | Deny |
| K06 | DELETE storage Pod | Deny |

### K01 — List Pods

```bash
kubectl --kubeconfig="$OBS" get pods \
  > evidence/K01.stdout.txt \
  2> evidence/K01.stderr.txt
```

Kỳ vọng list được Pod, không có `Forbidden`.

### K02 — Get Events

```bash
kubectl --kubeconfig="$OBS" get events \
  > evidence/K02.stdout.txt \
  2> evidence/K02.stderr.txt
```

Nếu chỉ có:

```text
No resources found in bd-g01 namespace.
```

vẫn PASS vì API request được phép.

### K03 — Read storage Pod logs

```bash
kubectl --kubeconfig="$OBS" logs "$POD" \
  > evidence/K03.stdout.txt \
  2> evidence/K03.stderr.txt
```

Kỳ vọng đọc được log SeaweedFS.

Dùng tên Pod thật vì observer không được cấp quyền đọc Deployment.

### K04 — Deny Secret

```bash
kubectl --kubeconfig="$OBS" get secret s3-config \
  > evidence/K04.stdout.txt \
  2> evidence/K04.stderr.txt
```

Kỳ vọng:

```text
Forbidden
User "system:serviceaccount:bd-g01:observer"
cannot get resource "secrets"
```

Principal phải đúng:

```text
system:serviceaccount:bd-g01:observer
```

### K05 — Deny Create Pod

```bash
kubectl --kubeconfig="$OBS" create \
  -f manifests/positive.yaml \
  --dry-run=server \
  > evidence/K05.stdout.txt \
  2> evidence/K05.stderr.txt
```

Kỳ vọng:

```text
Forbidden
cannot create resource "pods"
```

### K06 — Deny Delete Pod

```bash
kubectl --kubeconfig="$OBS" delete pod "$POD" \
  --dry-run=server \
  > evidence/K06.stdout.txt \
  2> evidence/K06.stderr.txt
```

Kỳ vọng:

```text
Forbidden
cannot delete resource "pods"
```

K05/K06 bắt buộc dùng `--dry-run=server` để API server kiểm tra authorization mà không thay đổi cluster.

---

# 6. Bước 4 — 4 Network reachability tests

## 6.1 Matrix

| ID | Kết nối | Dự kiến |
|---|---|---|
| N01 | owner → `objects:8333` | Connect |
| N02 | blocked → `objects:8333` | Blocked |
| N03 | owner → storage PodIP:`8888` | Blocked |
| N04 | outsider → `objects.${NS}.svc.cluster.local:8333` | Blocked |

NetworkPolicy `private-object-store` chọn storage Pod bằng:

```text
app=objects
```

Ingress được phép từ Pod cùng namespace có:

```text
access=s3
```

và chỉ TCP port:

```text
8333
```

## 6.2 N01 — Positive control

```bash
kubectl -n "$NS" exec owner -- \
  python /opt/s3lab.py tcp objects 8333 \
  > evidence/N01.txt
```

Kỳ vọng:

```text
"tcp_connected": true
```

N01 phải thành công trước các deny network.

## 6.3 N02 — blocked → objects:8333

```bash
kubectl -n "$NS" exec blocked -- \
  python /opt/s3lab.py tcp objects 8333 \
  > evidence/N02.txt
```

Kỳ vọng:

```text
"tcp_connected": false
```

Có thể nhận `ConnectionRefusedError`.

Sau đó chạy positive control mới, không ghi đè N01:

```bash
kubectl -n "$NS" exec owner -- \
  python /opt/s3lab.py tcp objects 8333 \
  > evidence/N01-after-N02.txt
```

Kỳ vọng `"tcp_connected": true`.

## 6.4 N03 — owner → storage PodIP:8888

Lấy Pod IP:

```bash
POD_IP=$(kubectl -n "$NS" get pod -l app=objects \
  -o jsonpath='{.items[0].status.podIP}')

echo "$POD_IP"
```

Trước khi kết luận N03, phải chứng minh process thật sự listen ở port 8888.

Dùng log K03:

```bash
grep -E '8888|Filer service' evidence/K03.stdout.txt
```

Kỳ vọng có dòng kiểu:

```text
Filer: 8888
Start Seaweed Filer ... :8888
Filer service is ready ... :8888
```

Sau đó:

```bash
kubectl -n "$NS" exec owner -- \
  python /opt/s3lab.py tcp "$POD_IP" 8888 \
  > evidence/N03.txt
```

Kỳ vọng:

```text
"tcp_connected": false
```

Chạy lại positive control:

```bash
kubectl -n "$NS" exec owner -- \
  python /opt/s3lab.py tcp objects 8333 \
  > evidence/N01-after-N03.txt
```

Kỳ vọng `"tcp_connected": true`.

Nếu port 8888 vốn không listen thì N03 không chứng minh được NetworkPolicy.

## 6.5 N04 — outsider namespace

### Mục tiêu

N04 phải chứng minh:

```text
Pod ở namespace khác
        ↓
objects.bd-g01.svc.cluster.local:8333
        ↓
BỊ CHẶN
```

Điểm quan trọng: outsider có thể mang cùng label `access=s3`, nhưng vì nằm ngoài namespace `bd-g01` nên `podSelector` trong ingress peer không match.

### 6.5.1 Kiểm tra namespace outsider

```bash
kubectl get namespaces
```

Nếu chưa có:

```bash
kubectl create namespace bd-outsider
```

Kiểm tra lại:

```bash
kubectl get namespaces
```

Kỳ vọng có:

```text
bd-g01       Active
bd-outsider  Active
```

> Với local setup của nhóm, `bd-outsider` là phần sinh viên tự tạo khi chạy lại Task 1.

### 6.5.2 Tạo outsider Pod

Tạo Pod ở namespace khác nhưng cố tình gắn `access=s3`:

```bash
kubectl -n bd-outsider run outsider \
  --image="$CLIENT_IMAGE" \
  --labels=access=s3 \
  --restart=Never \
  --command -- sleep 3600
```

Chờ Ready:

```bash
kubectl -n bd-outsider wait \
  --for=condition=Ready pod/outsider \
  --timeout=120s
```

Kiểm tra:

```bash
kubectl -n bd-outsider get pod outsider --show-labels
```

Kỳ vọng:

```text
outsider   1/1   Running   ...   access=s3
```

### 6.5.3 Chứng minh DNS hoạt động

```bash
kubectl -n bd-outsider exec outsider -- \
  python -c 'import socket; print(socket.gethostbyname("objects.bd-g01.svc.cluster.local"))'
```

Kỳ vọng trả về ClusterIP dạng:

```text
10.43.x.x
```

Nếu DNS không resolve được thì **không được tính N04 PASS**, vì lúc đó lỗi không chứng minh NetworkPolicy.

### 6.5.4 Loại trừ Egress NetworkPolicy không liên quan

```bash
kubectl -n bd-outsider get networkpolicy
```

Kỳ vọng:

```text
No resources found in bd-outsider namespace.
```

Nếu outsider có Egress policy riêng, cần kiểm tra policy đó trước; không được quy mọi lỗi kết nối cho `private-object-store`.

### 6.5.5 Chạy N04

```bash
kubectl -n bd-outsider exec outsider -- \
  python /opt/s3lab.py tcp objects.bd-g01.svc.cluster.local 8333 \
  > evidence/N04.txt
```

Xem raw evidence:

```bash
cat evidence/N04.txt
```

Kỳ vọng:

```text
"tcp_connected": false
```

Có thể thấy:

```text
"error": "ConnectionRefusedError"
```

### 6.5.6 Positive control sau N04

Ngay sau N04 phải chứng minh Service vẫn sống:

```bash
kubectl -n "$NS" exec owner -- \
  python /opt/s3lab.py tcp objects 8333 \
  > evidence/N01-after-N04.txt
```

Kiểm tra:

```bash
cat evidence/N01-after-N04.txt
```

Kỳ vọng:

```text
"tcp_connected": true
```

### 6.5.7 Điều kiện để N04 PASS

Chỉ kết luận N04 PASS khi đồng thời có:

```text
[✓] outsider nằm ngoài bd-g01
[✓] outsider Ready
[✓] outsider resolve được DNS Service
[✓] không có unrelated Egress NetworkPolicy
[✓] outsider → FQDN:8333 có tcp_connected=false
[✓] owner → objects:8333 ngay sau đó có tcp_connected=true
```

Evidence cuối:

```text
evidence/N04.txt
evidence/N01-after-N04.txt
```

Nếu trước đó từng lưu:

```text
evidence/N04-platform-check.txt
```

thì **giữ lại file đó** như evidence của attempt cũ, không xóa/ghi đè.

### 6.5.8 Trạng thái thực tế đã kiểm chứng

Lần chạy local hiện tại:

```text
DNS outsider → objects.bd-g01.svc.cluster.local : OK
bd-outsider NetworkPolicy                     : none
N04 outsider → Service:8333                   : tcp_connected=false
N01 after N04 owner → objects:8333            : tcp_connected=true
Kết luận                                      : N04 PASS
```

---

# 7. Bước 5 — security-results.csv

Phải có:

```text
S01–S12 = 12
K01–K06 = 6
N01–N04 = 4
Total   = 22
```

Mỗi row gồm:

```text
test ID
principal/context
target
expected
actual HTTP/error/network result
pass/fail/inconclusive
operator
reviewer
evidence path
```

Không tự điền reviewer nếu chưa có người review thật.

Kiểm tra:

```bash
wc -l security-results.csv
```

Kỳ vọng:

```text
23 security-results.csv
```

Kiểm tra ID:

```bash
python3 - <<'PY'
import csv

expected = (
    [f"S{i:02d}" for i in range(1, 13)]
    + [f"K{i:02d}" for i in range(1, 7)]
    + [f"N{i:02d}" for i in range(1, 5)]
)

with open("security-results.csv", newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

ids = [r["test_id"] for r in rows]

print("rows:", len(rows))
print("columns:", len(rows[0]) if rows else 0)
print("unique_ids:", len(set(ids)))
print("missing:", [x for x in expected if x not in ids])
print("extra:", [x for x in ids if x not in expected])
PY
```

Kỳ vọng:

```text
rows: 22
columns: 9
unique_ids: 22
missing: []
extra: []
```

### 7.1 Cập nhật N04 sau khi chạy outsider thành công

Dòng N04 cuối cùng nên có:

```text
expected = Blocked
actual   = tcp_connected=false; positive control after N04=true
status   = pass
evidence = evidence/N04.txt;evidence/N01-after-N04.txt
```

Có thể cập nhật bằng Python:

```bash
python3 - <<'PY'
import csv

path = "security-results.csv"

with open(path, newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
    fields = rows[0].keys()

for r in rows:
    if r["test_id"] == "N04":
        r["actual"] = "tcp_connected=false; positive control after N04=true"
        r["status"] = "pass"
        r["evidence"] = "evidence/N04.txt;evidence/N01-after-N04.txt"

with open(path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
PY
```

Kiểm tra:

```bash
grep '^N04,' security-results.csv
```

### 7.2 Kiểm tra tổng trạng thái 22 test

```bash
python3 - <<'PY'
import csv
from collections import Counter

with open("security-results.csv", newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

print("total =", len(rows))
print("status =", Counter(r["status"] for r in rows))

for prefix in ("S", "K", "N"):
    part = [r for r in rows if r["test_id"].startswith(prefix)]
    print(prefix, Counter(r["status"] for r in part))
PY
```

Kết quả hiện tại đã kiểm chứng:

```text
total = 22
status = Counter({'pass': 22})
S Counter({'pass': 12})
K Counter({'pass': 6})
N Counter({'pass': 4})
```

---

# 8. Bước 6 — Cross-check Task 1 quota

Access Engineer phải kiểm tra Pod negative của Task 1 bị reject đúng vì ResourceQuota.

```bash
kubectl -n "$NS" create -f manifests/negative.yaml \
  > evidence/quota-crosscheck-C.stdout.txt \
  2> evidence/quota-crosscheck-C.stderr.txt
```

Xem:

```bash
cat evidence/quota-crosscheck-C.stderr.txt
```

Kỳ vọng có:

```text
Forbidden
exceeded quota: team-budget
requested: ... requests.cpu=3
limited: ... requests.cpu=2
```

Ví dụ:

```text
pods "quota-negative" is forbidden:
exceeded quota: team-budget,
requested: limits.cpu=3,requests.cpu=3,
used: limits.cpu=3,requests.cpu=900m,
limited: limits.cpu=4,requests.cpu=2
```

Nếu lỗi do RBAC, YAML invalid hoặc admission khác thì không kết luận cross-check quota PASS.

---

# 9. Bước 7 — Individual Test của Trung Nguyễn

Yêu cầu:

> Chạy một request được phép và một request bị cấm bằng cùng identity `analyst`, rồi giải thích sự khác nhau.

Tạo thư mục:

```bash
mkdir -p individual
```

## Allow

```bash
kubectl -n "$NS" exec analyst -- \
  python /opt/s3lab.py probe get research-release fixture.txt \
  > individual/analyst-allow.json
```

Kỳ vọng:

```text
principal=analyst
HTTP 200
ok=true
```

## Deny

```bash
kubectl -n "$NS" exec analyst -- \
  python /opt/s3lab.py probe get research-raw fixture.txt \
  > individual/analyst-deny.json
```

Kỳ vọng:

```text
principal=analyst
HTTP 403
AccessDenied
ok=false
```

## Giải thích

Lưu vào:

```text
individual/analyst-explanation.txt
```

Ý chính:

- hai request dùng cùng identity `analyst`
- cùng action GET
- khác bucket
- analyst chỉ có `Read/List` trên `research-release`
- không có `Read` trên `research-raw`
- `GET release` → HTTP 200
- `GET raw` → HTTP 403 AccessDenied
- network reachability không đồng nghĩa với S3 authorization

---

# 10. Bước 8 — Kiểm tra policies-redacted.json

```bash
python3 -m json.tool policies-redacted.json
```

Kỳ vọng chỉ có policy:

```json
{
    "owner": [
        "Admin",
        "Read",
        "Write",
        "List"
    ],
    "ingestor": [
        "Read:research-raw",
        "Write:research-raw",
        "List:research-raw"
    ],
    "analyst": [
        "Read:research-release",
        "List:research-release"
    ]
}
```

Không được chứa access key, secret key, token hoặc nội dung `private/s3.json`.

---

# 11. Bước 9 — Handoff cho Task 4

## Tất Tú — Performance Engineer

Theo phân công, Tất Tú phải chạy lại độc lập **2 test Deny của Task 3**.

Có thể chọn:

```text
S08 — analyst PUT research-release → HTTP 403 AccessDenied
S10 — analyst GET research-raw     → HTTP 403 AccessDenied
```

Không ghi đè evidence của Trung Nguyễn.

Ví dụ:

```text
evidence/review-D-S08.json
evidence/review-D-S10.json
```

Trong lúc benchmark không thay đổi:

```text
S3 policy
NetworkPolicy
observer RBAC
PVC
storage configuration
```

---

# 12. Bước 10 — Handoff cho Task 5

## Hải Anh — Reliability / Governance

Sau recovery, Task 5 phải retest:

```text
S06
S08
S10
```

Kết quả vẫn phải là:

```text
S06 analyst GET research-release → Allow / HTTP 200
S08 analyst PUT research-release → Deny / HTTP 403
S10 analyst GET research-raw     → Deny / HTTP 403
```

Không ghi đè evidence Task 3.

Ví dụ:

```text
evidence/recovery-S06.json
evidence/recovery-S08.json
evidence/recovery-S10.json
```

Mục đích: chứng minh thay storage Pod không làm thay đổi policy truy cập.

---

# 13. Nguyên tắc evidence

Nếu test lỗi:

1. giữ evidence cũ
2. tìm nguyên nhân
3. sửa
4. chạy lại
5. lưu tên file mới

Ví dụ:

```text
S10-attempt1.json
S10-retest.json
```

Không:

```text
ghi đè file cũ
sửa raw output
xóa evidence FAIL
```

Client-generated log không phải immutable server audit trail, vì vậy báo cáo phải mô tả đúng giới hạn của evidence.

---

# 14. Tiêu chí nghiệm thu

| Hạng mục | Tiêu chí |
|---|---|
| S3 | 12/12 test đúng matrix |
| RBAC | 6/6 test dùng API request thật |
| Network | 4/4 đúng expected hoặc ghi rõ PLATFORM-BLOCKED nếu fixture hạ tầng thiếu |
| Positive control | N01 trước/sau deny network |
| N03 | xác nhận process listen ở 8888 |
| N04 | outsider fixture hợp lệ |
| CSV | đủ 22 ID |
| Policy | `policies-redacted.json` không secret |
| Observer | kubeconfig riêng, quyền giới hạn |
| Cross-check | quota reject đúng vì `team-budget` |
| Individual | analyst 1 Allow + 1 Deny + explanation |
| Evidence | raw output, không overwrite |

---

# 15. Trust Boundary

Ba lớp kiểm soát là độc lập:

## Kubernetes RBAC

Observer được đọc:

```text
pods
pods/log
events
```

nhưng không được:

```text
read Secret
create Pod
delete Pod
```

## S3 authorization

Ví dụ analyst:

```text
Read/List research-release
không Read research-raw
không Write/Delete release
```

## NetworkPolicy

Policy dùng label:

```text
access=s3
```

Label là Kubernetes selector, không phải cryptographic identity.

Namespace operator có thể có quyền tạo Pod hoặc thay label nếu quyền được cấp đủ lớn, nên lab không chứng minh khả năng chống lại một namespace administrator độc hại.

---

# 16. Lỗi thường gặp

| Hiện tượng | Nguyên nhân / xử lý |
|---|---|
| S3 Deny timeout | Không phải authorization evidence; kiểm tra service/network |
| S3 Deny HTTP 404 | Fixture/key không tồn tại |
| `InvalidAccessKeyId` | Credential sai |
| `SignatureDoesNotMatch` | Credential/request signing sai |
| K01–K03 Forbidden | observer Role/RoleBinding sai |
| K04–K06 principal khác observer | dùng sai kubeconfig |
| K02 `No resources found` | vẫn PASS nếu API request được phép |
| N02/N03 false nhưng N01 cũng false | storage/service lỗi |
| N03 port 8888 không listen | chưa chứng minh NetworkPolicy |
| Không có `bd-outsider` ở local | Tạo namespace theo Task 1 tutorial, sau đó tạo outsider Pod và chạy lại N04 |
| Evidence bị overwrite | giữ attempt cũ, tạo file mới |

---

# 17. Kiểm tra secret trước Git

Kiểm tra `.gitignore`:

```bash
git check-ignore -v private/observer.json private/s3.json
```

Kỳ vọng có rule `private/`.

Kiểm tra staged files:

```bash
git diff --cached --name-only | \
grep -E '(^private/|s3\\.json$|observer\\.json$)' \
|| echo "OK: no private/key/kubeconfig staged"
```

Kỳ vọng:

```text
OK: no private/key/kubeconfig staged
```

---

# 18. Không commit evidence từ cluster luyện tập

Nếu đây là cluster cá nhân:

```text
KHÔNG commit evidence/ luyện tập.
```

Các file hướng dẫn/code có thể commit:

```text
Task3Tutorial.md
observer.py
```

Các artifact sau chỉ nên đưa vào evidence bundle khi nhóm xác nhận đó là lần chạy chính thức:

```text
security-results.csv
policies-redacted.json
individual/
evidence/
```

Tuyệt đối không commit:

```text
private/
private/s3.json
private/*.env
private/observer.json
```

---

# 19. Trạng thái lần chạy luyện tập hiện tại

Kết quả đã kiểm chứng:

```text
S01–S12 : 12/12 PASS
K01–K06 : 6/6 PASS
N01–N04 : 4/4 PASS
-------------------
TOTAL    : 22/22 PASS
```

Chi tiết network:

```text
N01 owner → objects:8333                         PASS
N02 blocked → objects:8333                       PASS
N03 owner → storage PodIP:8888                   PASS
N04 bd-outsider/outsider → Service FQDN:8333     PASS
```

N04 đã được hoàn thiện bằng cách:

```text
1. tạo namespace bd-outsider
2. tạo outsider Pod trong namespace đó
3. gắn access=s3 để chứng minh label một mình không đủ
4. xác nhận DNS resolve được Service
5. xác nhận bd-outsider không có unrelated NetworkPolicy
6. outsider → objects.bd-g01.svc.cluster.local:8333 = blocked
7. owner → objects:8333 ngay sau đó = connect
```

Cross-check quota:

```text
PASS
quota-negative rejected by ResourceQuota team-budget
```

Individual test:

```text
analyst GET research-release/fixture.txt → HTTP 200
analyst GET research-raw/fixture.txt     → HTTP 403 AccessDenied
```

`security-results.csv` hiện có:

```text
22 rows
22 pass
12/12 S3
6/6 RBAC
4/4 Network
```

Các kết quả này là mốc tham khảo cho lần chạy chính thức nếu cluster hiện tại vẫn chỉ là cluster luyện tập.

---

# 20. Quick rerun — kiểm tra lại Task 3 nhanh

Phần này dùng khi cần review nhanh mà không đọc lại toàn bộ tutorial.

```bash
cd ~/lab1-bigdata
source env.sh

# Runtime / cluster
docker ps
k3d cluster list
kubectl config current-context

# Task 1 + 2 resources
kubectl -n "$NS" get pod,pvc,svc
kubectl -n "$NS" get networkpolicy private-object-store
kubectl -n "$NS" get serviceaccount,role,rolebinding observer

# Observer
python3 observer.py
OBS=private/observer.json
POD=$(kubectl -n "$NS" get pod -l app=objects -o jsonpath='{.items[0].metadata.name}')

# N04 namespace
kubectl get ns bd-outsider >/dev/null 2>&1 || kubectl create namespace bd-outsider

# N04 Pod
kubectl -n bd-outsider get pod outsider >/dev/null 2>&1 || \
kubectl -n bd-outsider run outsider \
  --image="$CLIENT_IMAGE" \
  --labels=access=s3 \
  --restart=Never \
  --command -- sleep 3600

kubectl -n bd-outsider wait --for=condition=Ready pod/outsider --timeout=120s

# DNS
kubectl -n bd-outsider exec outsider -- \
  python -c 'import socket; print(socket.gethostbyname("objects.bd-g01.svc.cluster.local"))'

# N04
kubectl -n bd-outsider exec outsider -- \
  python /opt/s3lab.py tcp objects.bd-g01.svc.cluster.local 8333 \
  > evidence/N04.txt

# Positive control
kubectl -n "$NS" exec owner -- \
  python /opt/s3lab.py tcp objects 8333 \
  > evidence/N01-after-N04.txt

cat evidence/N04.txt
cat evidence/N01-after-N04.txt
```

Kỳ vọng cuối:

```text
N04           tcp_connected=false
N01-after-N04 tcp_connected=true
```

---

# 21. Checklist bàn giao

```text
[ ] observer.py tồn tại
[ ] private/observer.json permission 600
[ ] private/ được gitignore
[ ] S01–S12 đã chạy
[ ] K01–K06 đã chạy
[ ] N01–N03 đã chạy
[ ] bd-outsider tồn tại
[ ] outsider Pod Ready
[ ] DNS outsider resolve được Service FQDN
[ ] N04 outsider bị block
[ ] N01-after-N04 vẫn connect
[ ] security-results.csv đủ 22 test
[ ] policies-redacted.json không chứa key
[ ] quota cross-check đúng ResourceQuota
[ ] individual/analyst-allow.json
[ ] individual/analyst-deny.json
[ ] individual/analyst-explanation.txt
[ ] không overwrite failed evidence
[ ] không stage private/key/kubeconfig
[ ] đã bàn giao 2 deny retest cho Task 4
[ ] đã bàn giao S06/S08/S10 cho Task 5
```


---

# 22. Backup cá nhân

Nếu cần backup toàn bộ trạng thái local, kể cả `private/`, chỉ dùng cho **lưu trữ cá nhân**:

```bash
cd ~/lab1-bigdata && \
zip -r ~/Task3_TrungNguyen_FINAL_PRIVATE_BACKUP.zip . \
  -x ".git/*" "*.zip"
```

File ZIP này có thể chứa:

```text
private/s3.json
private/*.env
private/observer.json
S3 access key / secret key
observer token
```

Do đó:

```text
KHÔNG push ZIP lên GitHub
KHÔNG gửi vào nhóm chat công khai
KHÔNG dùng làm evidence nộp bài
```

Nếu chỉ cần cập nhật tài liệu trên GitHub thì chỉ upload:

```text
Task3Tutorial.md
```
