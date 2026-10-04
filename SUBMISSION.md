# Chạy lại Task 1 → 5 và đóng gói bài nộp `team-XX/`

Runbook cho **buổi chạy chính thức**: một cluster, một namespace, cùng Pod/PVC/dữ liệu từ Task 1 đến Task 5, rồi đóng gói đúng cấu trúc đề yêu cầu. Chi tiết "kỳ vọng / nếu khác" của từng lệnh vẫn nằm trong `Task1Tutorial.md` … `Task5Tutorial.md`; file này chỉ gom lại **thứ tự chạy, tên file evidence và bước đóng gói**, và bổ sung những phần các tutorial chưa có: Task 1 evidence, sinh `security-results.csv`, `benchmark-summary.csv` và `recovery-summary.json` từ raw evidence, rồi đóng gói và quét secret.

Bundle đích:

```text
team-XX/
  README.md                 # 300–500 từ: thiết kế, kết quả, giới hạn   ← submission/README.md
  manifests/                # YAML đã apply, không có giá trị Secret    ← manifests/*-applied.yaml, positive/negative
  policies-redacted.json    # chỉ action                                ← Task 2 (make_identities.py)
  governance.json           #                                            ← Bước 6.2
  security-results.csv      # S01–S12, K01–K06, N01–N04                  ← src/security_csv.py
  benchmark-summary.csv     # 6 trial × 2 phase                          ← src/bench_summary.py
  recovery-summary.json     #                                            ← src/recovery_summary.py
  evidence/                 # raw request, status, events, image digest
  contribution.csv          # operator, reviewer, artifact, commit       ← Bước 6.3
  individual/               # 5 kết quả độc lập: A/ B/ C/ D/ E/
```

Vai trò dùng trong file này:

| Vai trò | Task | Người |
|---|---|---|
| A | 1 · Guardrails | `<người làm Task 1>` |
| B | 2 · Storage | Khánh |
| C | 3 · Governance | Trung Nguyễn |
| D | 4 · Measurement | Tất Tú |
| E | 5 · Recovery | Hải Anh |

---

## Quy tắc trong buổi chạy chính thức

1. **Một cluster, một người thao tác tại một thời điểm.** Báo nhóm trước và sau mỗi task. Mỗi task ghi lại *ai gõ lệnh* (operator) và *ai kiểm tra chéo* (reviewer). Không điền reviewer khi chưa có người kiểm tra thật.
2. **Không xóa** namespace, PVC, PV, Deployment. **Không chạy `src/reset_task2.sh`.** Chỉ xóa đúng các Pod tạm có tên trong runbook (`quota-positive`, Pod storage ở Task 5).
3. **Lệnh lỗi thì giữ file lỗi.** Đổi tên trước khi chạy lại: `mv evidence/S05.json evidence/S05-attempt1.json`. Không ghi đè, không sửa raw output. Các script ở Bước 6 tự ghi file `*-attempt*` vào cột evidence.
4. **Không bao giờ** `cat private/*`, `kubectl get secret -o yaml` hay `set -x`. `private/` đã có trong `.gitignore`.
5. Mỗi terminal mới: `cd ~/lab1-bigdata && source env.sh`.

---

## Bước 0 — Chuẩn bị (máy chạy chính thức)

```bash
cd ~/lab1-bigdata
git checkout main && git pull
source env.sh

# Cluster sạch: UID/Pod/dữ liệu phải liền mạch từ Task 1 → 5
k3d cluster delete bigdata            # chỉ khi cluster cũ là cluster luyện tập
k3d cluster create bigdata
kubectl config current-context        # k3d-bigdata
kubectl get nodes                     # Ready
kubectl get storageclass              # local-path (default)
kubectl top nodes                     # có số; nếu "not available yet" đợi 1 phút

kubectl create namespace "$NS"
kubectl create namespace bd-outsider

# Cất evidence cũ (luyện tập / lần trước) ra khỏi bundle, không xóa
TS=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "evidence/_practice-$TS"
find evidence -maxdepth 1 -type f -exec mv {} "evidence/_practice-$TS/" \;
cp "evidence/_practice-$TS/budget.md" evidence/ 2>/dev/null || true   # bảng budget là tài liệu, giữ lại
mkdir -p evidence individual/A individual/B individual/C individual/D individual/E submission
```

Nếu `private/` còn key cũ của cluster khác, cất đi: `mkdir -p private/old-$TS && mv private/*.env private/s3.json private/old-$TS/ 2>/dev/null`. Task 2 sẽ tạo key mới.

---

## Task 1 — Guardrails (A) · 10 điểm

```bash
kubectl version -o yaml                       > evidence/versions.yaml
kubectl config current-context                > evidence/context.txt

envsubst '${NS}' < manifests/guardrails.yaml  > manifests/guardrails-applied.yaml
kubectl -n "$NS" apply -f manifests/guardrails-applied.yaml | tee evidence/guardrails-apply.txt
kubectl -n "$NS" get resourcequota team-budget -o yaml > evidence/quota-before.yaml
kubectl -n "$NS" get rolebinding observer -o jsonpath='{.subjects[0].namespace}'; echo   # bd-g01

# Pod nhỏ hợp lệ → được nhận
kubectl -n "$NS" create -f manifests/positive.yaml > evidence/quota-positive.txt 2>&1
kubectl -n "$NS" wait --for=condition=Ready pod/quota-positive --timeout=120s
kubectl -n "$NS" get pod quota-positive -o wide >> evidence/quota-positive.txt
kubectl -n "$NS" describe resourcequota team-budget > evidence/quota-used-positive.txt

# Pod xin 3 CPU → bị quota từ chối
kubectl -n "$NS" create -f manifests/negative.yaml > evidence/quota-reject.txt 2>&1; echo "exit=$?"
cat evidence/quota-reject.txt

# Dọn Pod tạm để Task 2 bắt đầu với USED = 0
kubectl -n "$NS" delete pod quota-positive
```

| Kiểm tra | Kỳ vọng |
|---|---|
| `quota-positive.txt` | `pod/quota-positive created` + dòng `Running` |
| `quota-used-positive.txt` | `requests.cpu 100m / 2`, `pods 1 / 10` |
| `quota-reject.txt` | `exit=1`, `forbidden: exceeded quota: team-budget`, `requested: …requests.cpu=3`, `limited: …requests.cpu=2`. Lỗi khác (RBAC, YAML) không được tính |
| `evidence/budget.md` | Bảng tổng storage + 4 client so với quota (đã có sẵn) |

---

## Task 2 — Storage (B) · 12 điểm

Theo `Task2Tutorial.md` Bước 0 → 5, **bỏ phần Reset**. Tóm tắt:

```bash
# Bước 0: quota USED toàn 0, namespace chưa có Pod/PVC/Secret
kubectl -n "$NS" get resourcequota team-budget -o json | python3 src/fmt.py quota
mkdir -p private && chmod 700 private

# Bước 1: credentials (chỉ một lần)
python3 src/make_identities.py
cat policies-redacted.json                         # chỉ action, không "lab-…"
kubectl -n "$NS" create secret generic s3-config --from-file=s3.json=private/s3.json
for role in owner ingestor analyst; do
  kubectl -n "$NS" create secret generic "s3-$role" --from-env-file="private/$role.env"
done
kubectl -n "$NS" get secret                        # KHÔNG -o yaml

# Bước 2: storage
envsubst '${STORAGE_IMAGE}' < manifests/store.yaml > manifests/store-applied.yaml
kubectl -n "$NS" apply -f manifests/store-applied.yaml
kubectl -n "$NS" rollout status deployment/objects --timeout=120s

# Bước 3: client (script tự lưu manifests/clients-applied.yaml)
sh src/clients.sh
kubectl -n "$NS" get pod,pvc,svc,endpointslice -o wide > evidence/topology.txt
kubectl -n "$NS" describe resourcequota team-budget   > evidence/quota-after-task2.txt   # tổng budget thật

# Bước 4: seed + 2 lần đọc kiểm chứng
kubectl -n "$NS" exec owner -- python /opt/s3lab.py seed > evidence/seed.jsonl; echo "exit=$?"
kubectl -n "$NS" exec ingestor -- python /opt/s3lab.py probe get research-raw fixture.txt \
  > evidence/T2-ingestor-read-raw.json; echo "exit=$?"
kubectl -n "$NS" exec analyst -- python /opt/s3lab.py probe get research-release fixture.txt \
  > evidence/T2-analyst-read-release.json; echo "exit=$?"
python3 src/fmt.py results evidence/seed.jsonl evidence/T2-ingestor-read-raw.json evidence/T2-analyst-read-release.json

# Bước 5: provenance
kubectl -n "$NS" get pod,pvc -o json > evidence/T2-provenance.json
kubectl get storageclass > evidence/T2-storageclass.txt
kubectl -n "$NS" get pod -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.uid}{"\t"}{.status.containerStatuses[0].imageID}{"\n"}{end}' \
  > evidence/image-digests.txt
kubectl -n "$NS" exec deploy/objects -- ls -la /data > evidence/T2-data-mount.txt
python3 src/fmt.py uids < evidence/T2-provenance.json
grep -l -E 'secretKey|AWS_SECRET' manifests/*.yaml policies-redacted.json evidence/* || echo "sạch"
```

Đối chiếu từng lệnh với bảng "Kỳ vọng" trong `Task2Tutorial.md`. Ghi lại UID Pod `objects-…` và PVC `object-data`.

**Kiểm chéo (E kiểm tra B):** E tự chạy `kubectl -n "$NS" get pvc object-data -o jsonpath='{.metadata.uid}'` và đọc lại fixture bằng analyst, lưu vào `individual/E/` (xem Bước 6.4).

---

## Task 3 — Governance (C) · 20 điểm

Theo `Task3Tutorial.md` mục 3 → 8. Chạy đúng các lệnh S01–S12, K01–K06, N01–N04 ở đó (tên file `evidence/S01.json`, `evidence/K01.stdout.txt` / `.stderr.txt`, `evidence/N01.txt`, `evidence/N01-after-N02.txt`…). Ba bổ sung để `src/security_csv.py` chấm được N03/N04 từ evidence thay vì từ lời khẳng định:

```bash
# Sau K03, trước N03: chứng minh 8888 thật sự listen
grep -E '8888|Filer service' evidence/K03.stdout.txt > evidence/N03-listen-check.txt

# Trước N04: DNS và không có NetworkPolicy riêng trong bd-outsider
kubectl -n bd-outsider exec outsider -- \
  python -c 'import socket; print(socket.gethostbyname("objects.bd-g01.svc.cluster.local"))' \
  > evidence/N04-dns.txt
kubectl -n bd-outsider get networkpolicy > evidence/N04-outsider-netpol.txt 2>&1
kubectl -n bd-outsider get pod outsider -o yaml > manifests/outsider-applied.yaml

# Cross-check quota (C kiểm tra A)
kubectl -n "$NS" create -f manifests/negative.yaml \
  > evidence/quota-crosscheck-C.stdout.txt 2> evidence/quota-crosscheck-C.stderr.txt
```

Sau khi đủ 22 test, sinh CSV từ evidence (không gõ tay pass/fail):

```bash
python3 src/security_csv.py --operator "Trung Nguyen" --reviewer "<tên người kiểm tra chéo>"
```

Script in ra bảng 22 dòng. Cách chấm: S3 Deny chỉ `pass` khi `HTTP 403 AccessDenied`; timeout/DNS/404/lỗi credential là `inconclusive`; request bị cấm mà thành công là `fail`. Network Blocked chỉ `pass` khi positive control ngay sau đó connect. Dòng nào `fail` hoặc `inconclusive` thì: đổi tên file lỗi thành `*-attempt1`, tìm nguyên nhân, chạy lại lệnh đó, rồi chạy lại script; dòng đó sẽ ghi kèm `earlier attempt(s) retained`. Nếu giảng viên xác nhận một mục là **PLATFORM-BLOCKED**, sửa tay `status` của dòng đó thành `pending`, ghi lý do vào `actual` và thêm evidence của bài retest tương đương.

Individual C (mục 9 trong tutorial) lưu vào `individual/C/`: `analyst-allow.json`, `analyst-deny.json`, `analyst-explanation.txt`.

---

## Task 4 — Measurement (D) · 14 điểm

Theo `Task4Tutorial.md` Bước 0 → 7: warm-up, sampler ở terminal 2 ghi `evidence/resource-samples.txt`, 6 trial **đúng thứ tự** `r1-c1, r1-c4, r2-c4, r2-c1, r3-c1, r3-c4` vào `evidence/<run>.jsonl`, rồi retest S08/S10 vào `evidence/task4-retest-S08.json` / `task4-retest-S10.json`.

**Không dùng đoạn Python tạo CSV ở Bước 5 của tutorial.** Đoạn đó glob `evidence/r*-c*.jsonl` nên sẽ đếm cả `r1-c4-attempt1.jsonl` nếu có lần lỗi, và ghi CSV vào `evidence/` thay vì gốc bundle. Dùng script:

```bash
python3 src/bench_summary.py; echo "exit=$?"
cat benchmark-summary.csv
```

Script chỉ đọc 6 file tên chuẩn, tự tính lại goodput (`bytes / 2^20 / wall_s`) và p95 nearest-rank (`rank = ceil(0.95·n)`, chỉ request thành công) từ raw record rồi so với summary của helper. Kết quả ghi vào `benchmark-summary.csv` (13 dòng), `evidence/benchmark-analysis.txt` (median, ratio c4/c1, 192/192) và `evidence/benchmark-sha256.txt` (hash của raw file). `exit=0` khi không có sai lệch; `exit=1` thì đọc phần "Kiểm tra" để biết sai ở đâu.

Individual D (Bước 8 trong tutorial): tự tính tay một trial, lưu `individual/D/task4-recalc.txt`.

**Không xóa `bench/r1-c1`** — Task 5 cần nó.

---

## Task 5 — Recovery (E) · 14 điểm

Theo `Task5Tutorial.md` mục 0 → 4, trên **cùng cluster ngay sau Task 4**:

1. `before-recovery.jsonl` (32 object), `pod-before.{yaml,json}`, `pvc-before.{yaml,json}`.
2. Terminal A: `watch 180` → `evidence/canary.jsonl`. Terminal B, khi canary đã có dòng đầu: `delete-time.txt` → `delete pod` (không force) → `wait --for=delete` → `rollout status` → `rollout-time.txt`.
3. Đợi canary xong → `pod-after.*`, `pvc-after.*`, `after-recovery.jsonl`, `recovery-events.txt`, `recovery-storage.log`.
4. `recovery-S06.json`, `recovery-S08.json`, `recovery-S10.json`.

Thêm image digest của Pod mới:

```bash
kubectl -n "$NS" get pod -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.uid}{"\t"}{.status.containerStatuses[0].imageID}{"\n"}{end}' \
  > evidence/image-digests-after-recovery.txt
```

Sinh `recovery-summary.json` từ evidence (thay cho việc điền tay template):

```bash
python3 src/recovery_summary.py
```

Phải thấy: `pod_uid_changed: true`, `pvc_uid_unchanged: true`, `verified_before/after.complete: true`, `ready_within_target: true`, `policy_retests` S06/S08/S10 đều `pass: true`. `observed_interruption_s` là `null` kèm `interruption_note` nếu canary không bắt được lần lỗi nào; đó là kết quả hợp lệ, ghi đúng như vậy trong README.

---

## Bước 6 — Hồ sơ nhóm

### 6.1 Evidence index

```bash
cp templates/evidence-index.example.md evidence/INDEX.md
```

Điền cột người chạy / kiểm tra chéo và kết quả thực tế. Thêm dòng cho các file mới: `evidence/quota-reject.txt`, `evidence/quota-after-task2.txt`, `evidence/image-digests*.txt`, `evidence/N03-listen-check.txt`, `evidence/N04-*.txt`, `evidence/benchmark-analysis.txt`, `evidence/benchmark-sha256.txt`, `evidence/task4-retest-*.json`. Sửa `evidence/N*.json` thành `evidence/N*.txt` cho đúng tên file thật.

### 6.2 `governance.json`

```bash
cp templates/governance.example.json governance.json
git log -1 --format=%H -- src/make_identities.py      # → policy_revision
```

Thay `STUDENT_ID_*` bằng mã sinh viên thật, `intended_cleanup_date` bằng ngày cụ thể, `policy_revision` bằng commit ở trên. Kiểm tra: `python3 -m json.tool governance.json`.

### 6.3 `contribution.csv`

```bash
cp templates/contribution.example.csv contribution.csv
```

Mỗi người một dòng: `student_id, role, authored_change` (một thay đổi chính mình viết), `independent_test` (một kiểm tra mình chạy độc lập), `interpretation`, `reviewer` (người thật), `evidence_path`, `commit_id` (commit của chính mình, `git log --author="<tên>" --format=%h`).

### 6.4 `individual/` — 5 kết quả độc lập

| Thư mục | Nội dung |
|---|---|
| `individual/A/` | `<theo đề bài individual của vai trò A>` |
| `individual/B/` | `<theo đề bài individual của vai trò B>` |
| `individual/C/` | `analyst-allow.json`, `analyst-deny.json`, `analyst-explanation.txt` (Task 3 mục 9) |
| `individual/D/` | `task4-recalc.txt` (Task 4 Bước 8) |
| `individual/E/` | Kiểm chéo Task 2 (UID PVC + đọc fixture) và giải thích kết quả recovery |

Tutorial chỉ ghi rõ yêu cầu cá nhân của C và D; A, B, E làm theo đề. Mỗi người tự chạy lệnh của mình, không copy file của người khác.

### 6.5 README nhóm

```bash
cp templates/team-README.example.md submission/README.md
# điền số đo thật từ: security-results.csv, evidence/benchmark-analysis.txt, recovery-summary.json
wc -w submission/README.md      # 300–500
```

---

## Bước 7 — Đóng gói và kiểm tra

```bash
TEAM=team-01 sh src/build_bundle.sh      # đổi 01 thành số nhóm
```

Script dừng nếu thiếu file, JSON hỏng, hoặc tìm thấy credential (theo mẫu và theo đúng giá trị key trong `private/*.env`). Khi chạy xong nó in số dòng `security-results.csv`, phân bố pass/fail, các dòng reviewer còn `PENDING`, và số dòng `benchmark-summary.csv`. Danh sách file nằm ở `team-01/evidence/FILES.txt`.

Kiểm tra cuối:

```bash
git status --short | grep -E '^\?\?|^ M' | grep -E 'private/|\.env$|s3\.json|observer\.json|kubeconfig' \
  || echo "OK: không có file credential"
git add team-01/ src/ SUBMISSION.md
git commit -m "Team 01: official evidence bundle"
git push
```

## Đối chiếu với thang điểm

| Hạng mục | Điểm | Evidence trong bundle |
|---|---:|---|
| 1 · Pod nhỏ được nhận | 2 | `evidence/quota-positive.txt`, `quota-used-positive.txt` |
| 1 · Quota từ chối đúng | 3 | `evidence/quota-reject.txt`, `quota-crosscheck-C.stderr.txt` |
| 1 · Tổng budget | 3 | `evidence/budget.md`, `quota-after-task2.txt` |
| 1 · Manifest tái lập được | 2 | `manifests/guardrails-applied.yaml`, `positive.yaml`, `negative.yaml` |
| 2 · Triển khai private | 4 | `manifests/store-applied.yaml`, `evidence/topology.txt` |
| 2 · PVC bind/mount | 3 | `evidence/T2-provenance.json`, `T2-data-mount.txt` |
| 2 · Fixture + đọc kiểm chứng | 3 | `evidence/seed.jsonl`, `T2-*-read-*.json` |
| 2 · Nguồn gốc image/config | 2 | `evidence/image-digests.txt`, `T2-storageclass.txt`, `policies-redacted.json` |
| 3 · 12 S3 / 6 RBAC / 4 network | 12 + 3 + 2 | `security-results.csv`, `evidence/S*.json`, `K*.txt`, `N*.txt` |
| 3 · Ranh giới kiểm soát + governance | 3 | `governance.json`, `policies-redacted.json`, README phần Giới hạn |
| 4 · Thiết kế 6 trial có kiểm soát | 4 | `evidence/r*-c*.jsonl` (đúng thứ tự), `resource-samples.txt` |
| 4 · Kết quả đầy đủ + hash | 4 | `benchmark-summary.csv` (successes, hash_failures), `benchmark-sha256.txt` |
| 4 · Thống kê / đơn vị đúng | 3 | `evidence/benchmark-analysis.txt`, `individual/D/task4-recalc.txt` |
| 4 · Diễn giải có căn cứ | 3 | README phần Diễn giải |
| 5 · Pod đổi / PVC giữ | 3 | `pod-before/after.json`, `pvc-before/after.json`, `recovery-summary.json` |
| 5 · Toàn vẹn trước/sau | 4 | `before-recovery.jsonl`, `after-recovery.jsonl` |
| 5 · Canary + mục tiêu phục hồi | 3 | `canary.jsonl`, `delete-time.txt`, `rollout-time.txt` |
| 5 · Retest quyền / giới hạn | 2 | `recovery-S06/S08/S10.json`, `recovery-summary.json.unproven` |
| 5 · Evidence index | 2 | `evidence/INDEX.md` |
