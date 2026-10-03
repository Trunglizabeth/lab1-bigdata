# Task 2 — Triển khai persistent object storage

> 25 phút · 12 điểm nhóm · Kết quả: một S3 service **private, có xác thực**, dữ liệu nằm trên PVC.

**Điều kiện:** đã chạy Task 1 trên cluster của mình. Mọi lệnh chạy trong WSL, từ `~/lab1-bigdata`.

**Cách đọc:** mỗi bước có 1 khối lệnh, các lệnh được đánh số `①②③…`. Bảng ngay dưới cho biết từng lệnh phải ra gì. Nếu khác → làm theo cột *Nếu khác*, không chạy bước tiếp theo.

---

## Tổng quan

| Bước | Việc | Kết quả |
|---|---|---|
| 0 | Kiểm tra trước | Cluster, quota, policy sẵn sàng; namespace trống |
| 1 | Credentials | 3 identity S3 + 4 Secret |
| 2 | Storage | Pod `objects` Ready, PVC Bound, Service ClusterIP |
| 3 | Client | 4 Pod client, quota dùng đúng budget |
| 4 | Seed & đọc | 2 bucket, 4 fixture, 2 lần đọc khớp SHA-256 |
| 5 | Evidence | UID, imageID, `/data`, không lộ secret |

| File | Nội dung |
|---|---|
| `src/make_identities.py` | Sinh key owner / ingestor / analyst vào `private/` + `policies-redacted.json` (không key) |
| `manifests/store.yaml` | PVC `object-data` 4Gi · Deployment `objects` (1 replica, Recreate) · Service `objects:8333` |
| `src/clients.sh` | Pod owner, ingestor, analyst (nhãn `access: s3` + Secret) và blocked (không nhãn, không key) |

---

## Bước 0 — Kiểm tra trước

```bash
cd ~/lab1-bigdata && source env.sh
echo "$NS"; echo "$STORAGE_IMAGE"; echo "$CLIENT_IMAGE"                  # ①
ls src/make_identities.py src/clients.sh manifests/store.yaml           # ②
kubectl config current-context                                          # ③
kubectl -n "$NS" get resourcequota team-budget                          # ④
kubectl -n "$NS" get networkpolicy private-object-store                 # ⑤
kubectl -n "$NS" get serviceaccount,role,rolebinding observer           # ⑥
kubectl -n "$NS" get pod,pvc,secret                                     # ⑦
kubectl get storageclass                                                # ⑧
mkdir -p evidence private && chmod 700 private && ls -ld private        # ⑨
```

| # | Kỳ vọng | Nếu khác |
|---|---|---|
| ① | `bd-g01` · `chrislusf/seaweedfs@sha256:d7f3…` · `trunglizabeth/s3lab@sha256:b9e7…` | Dòng trống → chưa `source env.sh` |
| ② | In đủ 3 đường dẫn | `No such file` → WSL chưa có file Task 2, `git pull` / checkout branch |
| ③ | `k3d-bigdata` | `kubectl config use-context k3d-bigdata` |
| ④ | `team-budget` với `pods: 0/10`, `requests.cpu: 0/2`, `requests.memory: 0/2Gi`, `requests.storage: 0/8Gi` | `NotFound` → chưa làm Task 1 · Used ≠ 0 → còn Pod/PVC cũ |
| ⑤ | `POD-SELECTOR` = `app=objects` | Apply lại `guardrails.yaml` |
| ⑥ | Đủ 3 dòng: serviceaccount, role, rolebinding `observer` | Apply lại `guardrails.yaml` |
| ⑦ | `No resources found in bd-g01 namespace.` | Còn `quota-positive` → `kubectl -n "$NS" delete pod quota-positive` |
| ⑧ | `local-path (default)` | Không có `(default)` → PVC sẽ kẹt `Pending` |
| ⑨ | `drwx------ … private` | `chmod 700 private` |

---

## Bước 1 — Credentials (chỉ chạy MỘT lần)

```bash
python3 src/make_identities.py                                          # ①
ls -l private/ policies-redacted.json                                   # ②
cat policies-redacted.json                                              # ③

kubectl -n "$NS" create secret generic s3-config \
  --from-file=s3.json=private/s3.json                                   # ④
for role in owner ingestor analyst; do
  kubectl -n "$NS" create secret generic "s3-$role" \
    --from-env-file="private/$role.env"
done                                                                    # ⑤
kubectl -n "$NS" get secret                                             # ⑥  (KHÔNG -o yaml)
```

| # | Kỳ vọng | Nếu khác |
|---|---|---|
| ① | `OK: private/s3.json, private/{owner,ingestor,analyst}.env, policies-redacted.json` | `đã tồn tại` → key có rồi, **không xóa**, chạy tiếp ② |
| ② | 4 file `analyst.env`, `ingestor.env`, `owner.env`, `s3.json`, quyền `-rw-------` | — |
| ③ | Chỉ có tên vai trò + action (`"Admin"`, `"Read:research-raw"`…), không có `lab-…` | Có key → không được nộp file này |
| ④ | `secret/s3-config created` | `already exists` → bỏ qua |
| ⑤ | `secret/s3-owner created` · `s3-ingestor created` · `s3-analyst created` | `already exists` → bỏ qua |
| ⑥ | 4 Secret `Opaque`: `s3-config` DATA=1, ba `s3-<role>` DATA=2 | Thiếu → chạy lại ④ hoặc ⑤ |

> Không `cat private/s3.json`, không bật `set -x`.

---

## Bước 2 — Storage

```bash
envsubst '${STORAGE_IMAGE}' < manifests/store.yaml > manifests/store-applied.yaml
grep 'image:' manifests/store-applied.yaml                              # ①
kubectl -n "$NS" apply -f manifests/store-applied.yaml                  # ②
kubectl -n "$NS" rollout status deployment/objects --timeout=120s       # ③
kubectl -n "$NS" get pod -l app=objects                                 # ④
kubectl -n "$NS" get pvc object-data                                    # ⑤
kubectl -n "$NS" get svc objects                                        # ⑥
```

| # | Kỳ vọng | Nếu khác |
|---|---|---|
| ① | `image: chrislusf/seaweedfs@sha256:d7f3…` | Còn `${STORAGE_IMAGE}` → chưa `source env.sh` |
| ② | `persistentvolumeclaim/object-data created` · `deployment.apps/objects created` · `service/objects created` | `exceeded quota` → còn Pod/PVC rác |
| ③ | `deployment "objects" successfully rolled out` (lần đầu 30–90 giây) | `describe pod -l app=objects`, `logs deploy/objects` |
| ④ | 1 Pod `objects-…`, READY `1/1`, `Running`, RESTARTS `0` | Xem Lỗi thường gặp |
| ⑤ | `Bound` · `4Gi` · `RWO` · `local-path` | `Pending` → `describe pvc object-data` |
| ⑥ | `ClusterIP` · EXTERNAL-IP `<none>` · `8333/TCP` | Không được là NodePort/LoadBalancer |

---

## Bước 3 — Client

```bash
sh src/clients.sh                                                       # ①
kubectl -n "$NS" get pod --show-labels                                  # ②
kubectl -n "$NS" get pod,pvc,svc,endpointslice -o wide > evidence/topology.txt
grep -c Running evidence/topology.txt                                   # ③
kubectl -n "$NS" describe resourcequota team-budget                     # ④
```

| # | Kỳ vọng | Nếu khác |
|---|---|---|
| ① | 4 dòng `pod/<role> created`, rồi 4 dòng `condition met` | Timeout → `describe pod <role>` |
| ② | 5 Pod `1/1 Running`. owner/ingestor/analyst: `access=s3,role=…` · blocked: chỉ `role=blocked` · storage: `app=objects` | blocked có `access=s3` → sai, xóa và tạo lại |
| ③ | `5` | Có Pod chưa Running |
| ④ | Used: `pods 5/10` · `requests.cpu 900m/2` · `limits.cpu 3/4` · `requests.memory 1Gi/2Gi` · `limits.memory 3Gi/4Gi` · `requests.storage 4Gi/8Gi` | Khác → so với `evidence/budget.md`, tìm Pod thừa |

---

## Bước 4 — Seed và đọc kiểm chứng

```bash
kubectl -n "$NS" exec owner -- python /opt/s3lab.py seed > evidence/seed.jsonl
grep -c '"ok": true' evidence/seed.jsonl                                # ①

kubectl -n "$NS" exec ingestor -- python /opt/s3lab.py \
  probe get research-raw fixture.txt > evidence/T2-ingestor-read-raw.json
echo "exit=$?"                                                          # ②

kubectl -n "$NS" exec analyst -- python /opt/s3lab.py \
  probe get research-release fixture.txt > evidence/T2-analyst-read-release.json
echo "exit=$?"                                                          # ③

grep -h -o '"sha256": "[0-9a-f]*"' evidence/T2-*-read-*.json            # ④
```

| # | Kỳ vọng | Nếu khác |
|---|---|---|
| ① | `4` (fixture.txt + delete-probe.txt × 2 bucket, `"http": 200`) | `InvalidAccessKeyId` / timeout → Lỗi thường gặp |
| ② | `exit=0`; file có `"ok": true`, `"http": 200`, `"principal": "ingestor"`, `"bytes": 25` | `exit=2` → `cat` file xem `"error"` |
| ③ | `exit=0`; như ② nhưng `"principal": "analyst"` | như trên |
| ④ | 2 dòng giống hệt: `"sha256": "9ce4c8bb96c85122c3b386653fbe9150cb2f4df03f25c83408fe11c29b87d6f8"` | Hash khác → fixture sai, không được tính pass |

---

## Bước 5 — Evidence nguồn gốc

```bash
{
  echo "# storage pod";  kubectl -n "$NS" get pod -l app=objects \
    -o jsonpath='{.items[0].metadata.name} uid={.items[0].metadata.uid} node={.items[0].spec.nodeName} imageID={.items[0].status.containerStatuses[0].imageID}{"\n"}'
  echo "# pvc";          kubectl -n "$NS" get pvc object-data \
    -o jsonpath='uid={.metadata.uid} volume={.spec.volumeName} sc={.spec.storageClassName} phase={.status.phase}{"\n"}'
  echo "# client pods";  kubectl -n "$NS" get pod owner ingestor analyst blocked \
    -o jsonpath='{range .items[*]}{.metadata.name} uid={.metadata.uid} imageID={.status.containerStatuses[0].imageID}{"\n"}{end}'
  echo "# storageclass"; kubectl get storageclass
} > evidence/T2-provenance.txt
cat evidence/T2-provenance.txt                                          # ①

kubectl -n "$NS" exec deploy/objects -- ls -la /data > evidence/T2-data-mount.txt
cat evidence/T2-data-mount.txt                                          # ②

grep -l -E 'secretKey|AWS_SECRET' manifests/*.yaml policies-redacted.json evidence/* \
  || echo "sạch"                                                        # ③
```

| # | Kỳ vọng | Nếu khác |
|---|---|---|
| ① | Không ô trống sau `uid=` / `imageID=`. Storage: `imageID=docker.io/chrislusf/seaweedfs@sha256:…` · 4 client: `…/s3lab@sha256:b9e7…` · PVC: `sc=local-path phase=Bound volume=pvc-…` | Ô trống → Pod chưa Running, chạy lại |
| ② | `/data` không rỗng (file/thư mục do SeaweedFS tạo), chủ sở hữu `1000` | Rỗng → server không ghi vào PVC |
| ③ | `sạch` | In ra tên file → file đó chứa secret, không được nộp |

---

## Tiêu chí nghiệm thu (12 điểm)

| Hạng mục | Kiểm tra | Evidence |
|---|---|---|
| Triển khai private (4đ) | 1 replica Ready; ClusterIP 8333; server dùng `s3-config` | `topology.txt`, `store-applied.yaml` |
| PVC bind/mount (3đ) | PVC Bound, mount tại `/data` | `T2-provenance.txt`, `T2-data-mount.txt` |
| Fixture + đọc verify (3đ) | 2 bucket, 4 fixture; ingestor đọc raw, analyst đọc release, hash khớp | `seed.jsonl`, `T2-*-read-*.json` |
| Nguồn gốc (2đ) | imageID digest, UID Pod/PVC, StorageClass, manifest không secret | `T2-provenance.txt`, `policies-redacted.json` |

**Để giải thích khi được hỏi:** lab dùng HTTP nội bộ vì dữ liệu là tổng hợp · Secret chỉ là base64, không phải mã hóa · một port TCP đang mở không chứng minh S3 có xác thực, phải có lần đọc đúng identity.

## Kiểm chéo (E kiểm tra B)

E tự chạy: `get pvc object-data` → so UID với `T2-provenance.txt`; chạy lệnh đọc của analyst ở Bước 4 → so sha256.

## Lỗi thường gặp

| Hiện tượng | Nguyên nhân / cách xử lý |
|---|---|
| Pod `objects` `CreateContainerConfigError` | Chưa có Secret `s3-config` hoặc sai key (phải là `s3.json`) |
| Pod `objects` CrashLoop, log `permission denied` | `kubectl -n "$NS" logs deploy/objects`; kiểm tra StorageClass / fsGroup |
| `exceeded quota` | Còn Pod rác (vd. `quota-positive`): `kubectl -n "$NS" get pod` |
| Rollout không Ready | `describe pod` → readinessProbe 8333; `weed mini` khởi động chậm, đợi thêm |
| `InvalidAccessKeyId` / `SignatureDoesNotMatch` | Key trong `private/` lệch với Secret. Xóa 4 Secret, tạo lại từ `private/` hiện tại, `kubectl -n "$NS" rollout restart deploy/objects` |
| Seed timeout / lỗi DNS | Pod owner thiếu nhãn `access: s3`? `get pod --show-labels`, kiểm tra endpointslice `objects` |

Lỗi thì **giữ file cũ** (đổi tên `…-attempt1`), sửa rồi chạy lại, không ghi đè.

## Không commit

`private/`, `*.env`, `s3.json`. Chỉ commit `src/make_identities.py`, `src/clients.sh`, `manifests/store.yaml`, `Task2Tutorial.md`. `evidence/`, `store-applied.yaml`, `policies-redacted.json` chỉ commit từ buổi chạy chính thức.
