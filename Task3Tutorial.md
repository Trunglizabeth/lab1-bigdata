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

```bash
cd ~/lab1-bigdata
source env.sh

kubectl config current-context
echo "$NS"
kubectl -n "$NS" get pod
kubectl -n "$NS" get pvc
kubectl -n "$NS" get svc objects
kubectl -n "$NS" get networkpolicy private-object-store
kubectl -n "$NS" get serviceaccount,role,rolebinding observer
ls -l observer.py
ls -l policies-redacted.json
```

Kỳ vọng:

- context: `k3d-bigdata`
- namespace: `bd-g01`
- `owner`, `ingestor`, `analyst`, `blocked`, `objects-...` đều Running
- PVC `object-data` ở trạng thái Bound
- Service `objects` là ClusterIP, port `8333/TCP`
- NetworkPolicy `private-object-store` tồn tại
- ServiceAccount/Role/RoleBinding `observer` tồn tại

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

Kiểm tra:

```bash
kubectl get namespaces
```

Trong môi trường chính thức cần có outsider fixture được chỉ định, ví dụ:

```text
bd-outsider
```

Đích N04:

```text
objects.${NS}.svc.cluster.local:8333
```

Outsider phải được xác nhận:

- DNS hoạt động
- routing hoạt động
- không bị Egress policy khác chặn
- nằm ngoài namespace `bd-g01`

Không tự lấy một Pod bất kỳ rồi coi N04 là PASS.

Nếu cluster luyện tập không có outsider fixture:

```bash
kubectl get namespaces > evidence/N04-platform-check.txt
```

Ghi:

```text
N04 = PLATFORM-BLOCKED / inconclusive
Reason: designated outsider fixture is not available.
```

Không ghi PASS giả.

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
| Không có outsider fixture | PLATFORM-BLOCKED / inconclusive |
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

Kết quả đã quan sát:

```text
S01–S12 : 12/12 PASS
K01–K06 : 6/6 PASS
N01      : PASS
N02      : PASS
N03      : PASS
N04      : PLATFORM-BLOCKED / inconclusive
```

N04 chưa chạy đúng specification vì cluster luyện tập hiện không có outsider fixture được chỉ định.

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

Các kết quả này chỉ là mốc tham khảo cho lần chạy chính thức.

---

# 20. Checklist bàn giao

```text
[ ] observer.py tồn tại
[ ] private/observer.json permission 600
[ ] private/ được gitignore
[ ] S01–S12 đã chạy
[ ] K01–K06 đã chạy
[ ] N01–N03 đã chạy
[ ] N04 đã chạy hoặc ghi PLATFORM-BLOCKED
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
