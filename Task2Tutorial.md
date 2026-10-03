# Task 2 — Triển khai persistent object storage

25 phút · 12 điểm nhóm. Kết quả: một S3 service **private, có xác thực**, dữ liệu nằm trên PVC — không chỉ là "một container đang chạy".

Điều kiện: đã làm Task 1 trên cluster của mình (`guardrails.yaml` đã apply, quota `team-budget` có trong `bd-g01`). Mọi lệnh chạy từ thư mục gốc repo sau `source env.sh`.

## File của Task 2

| File | Nội dung |
|---|---|
| `src/make_identities.py` | Sinh key cho owner / ingestor / analyst vào `private/` + `policies-redacted.json` (không có key) |
| `manifests/store.yaml` | PVC `object-data` 4Gi, Deployment `objects` (1 replica, Recreate, `weed mini`), Service ClusterIP `objects:8333` |
| `src/clients.sh` | 4 Pod client: owner, ingestor, analyst (nhãn `access: s3` + Secret riêng), blocked (không nhãn, không key) |

## 0. Kiểm tra trước

```bash
cd ~/lab1-bigdata && source env.sh
echo "$NS"; echo "$STORAGE_IMAGE"; echo "$CLIENT_IMAGE"
kubectl config current-context
kubectl -n "$NS" get resourcequota team-budget
kubectl -n "$NS" get networkpolicy private-object-store
kubectl -n "$NS" get serviceaccount,role,rolebinding observer
kubectl -n "$NS" get pod,pvc,secret
kubectl get storageclass
mkdir -p evidence private && chmod 700 private && ls -ld private
```

Kết quả mong đợi:

| Lệnh | Phải thấy | Nếu khác |
|---|---|---|
| `echo` 3 biến | `bd-g01`, `chrislusf/seaweedfs@sha256:d7f3...`, `trunglizabeth/s3lab@sha256:b9e7...` | Chưa `source env.sh` |
| `current-context` | `k3d-bigdata` | `kubectl config use-context k3d-bigdata` |
| `get resourcequota team-budget` | Dòng `team-budget` với `requests.cpu: 0/2, requests.memory: 0/2Gi, requests.storage: 0/8Gi, pods: 0/10, persistentvolumeclaims: 0/2` (cột REQUEST/LIMIT) | `NotFound` → chưa làm Task 1. `Used` khác 0 → còn Pod/PVC cũ |
| `get networkpolicy private-object-store` | `POD-SELECTOR = app=objects` | Apply lại `guardrails.yaml` |
| `get serviceaccount,role,rolebinding observer` | Đủ 3 dòng: `serviceaccount/observer`, `role.../observer`, `rolebinding.../observer` | Apply lại `guardrails.yaml` |
| `get pod,pvc,secret` | `No resources found in bd-g01 namespace.` | Còn `quota-positive` → `kubectl -n "$NS" delete pod quota-positive`. Đã có `s3-*` / `object-data` → đây là lần chạy lại, xem mục Lỗi thường gặp |
| `get storageclass` | `local-path (default)` | Cluster không có StorageClass mặc định → PVC sẽ kẹt `Pending` |
| `ls -ld private` | `drwx------` | `chmod 700 private` |

## 1. Credentials (chạy MỘT lần)

```bash
python3 src/make_identities.py
kubectl -n "$NS" create secret generic s3-config --from-file=s3.json=private/s3.json
for role in owner ingestor analyst; do
  kubectl -n "$NS" create secret generic "s3-$role" --from-env-file="private/$role.env"
done
kubectl -n "$NS" get secret            # chỉ xem tên, KHÔNG -o yaml
```

Không `cat private/s3.json`, không bật `set -x`. Script tự từ chối chạy lại nếu `private/s3.json` đã có, để key không lệch với Secret.

## 2. Storage

```bash
envsubst '${STORAGE_IMAGE}' < manifests/store.yaml | tee manifests/store-applied.yaml \
  | kubectl -n "$NS" apply -f -
kubectl -n "$NS" rollout status deployment/objects --timeout=120s
kubectl -n "$NS" get pvc object-data            # STATUS = Bound
```

`manifests/store-applied.yaml` chỉ chứa digest image, không chứa secret → nộp được.

## 3. Client

```bash
sh src/clients.sh
kubectl -n "$NS" get pod,pvc,svc,endpointslice -o wide > evidence/topology.txt
```

## 4. Seed và đọc kiểm chứng

```bash
kubectl -n "$NS" exec owner -- python /opt/s3lab.py seed > evidence/seed.jsonl
kubectl -n "$NS" exec ingestor -- python /opt/s3lab.py probe get research-raw fixture.txt \
  > evidence/T2-ingestor-read-raw.json
kubectl -n "$NS" exec analyst -- python /opt/s3lab.py probe get research-release fixture.txt \
  > evidence/T2-analyst-read-release.json
grep -h -o '"sha256": "[0-9a-f]*"' evidence/T2-*-read-*.json
```

`seed.jsonl` phải có 4 dòng `"ok": true` (2 bucket × fixture.txt, delete-probe.txt). Cả hai lần đọc phải `"ok": true` và sha256 bằng hằng số:

```
9ce4c8bb96c85122c3b386653fbe9150cb2f4df03f25c83408fe11c29b87d6f8
```

## 5. Nguồn gốc image và cấu hình

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
kubectl -n "$NS" exec deploy/objects -- ls -la /data > evidence/T2-data-mount.txt
kubectl -n "$NS" describe resourcequota team-budget > evidence/quota-after-task2.txt
```

`T2-data-mount.txt` chứng minh dữ liệu/metadata nằm trong `/data` (PVC), không phải trong filesystem của container.

## Tiêu chí nghiệm thu

| Hạng mục | Kiểm tra | Evidence |
|---|---|---|
| Triển khai private (4đ) | 1 replica Ready; Service ClusterIP port 8333; server dùng `s3-config` | `topology.txt`, `store-applied.yaml` |
| PVC bind/mount (3đ) | PVC Bound, mount tại `/data` | `T2-provenance.txt`, `T2-data-mount.txt` |
| Fixture seed + đọc verify (3đ) | 2 bucket, 4 fixture; ingestor đọc raw, analyst đọc release, hash khớp | `seed.jsonl`, `T2-*-read-*.json` |
| Nguồn gốc (2đ) | imageID digest thật, UID Pod/PVC, StorageClass, manifest không có secret | `T2-provenance.txt`, `policies-redacted.json` |

Ghi chú để giải thích: lab dùng HTTP nội bộ cluster vì dữ liệu là tổng hợp; giá trị Secret chỉ là base64, không phải mã hóa; một port TCP đang listen không chứng minh S3 có xác thực — phải có lần đọc với đúng identity.

## Kiểm chéo (E kiểm tra B)

E chạy lại độc lập: `kubectl -n "$NS" get pvc object-data`, lệnh `probe get` của analyst và so sha256, rồi so UID PVC với `T2-provenance.txt`.

## Lỗi thường gặp

| Hiện tượng | Kiểm tra |
|---|---|
| Pod `objects` `CreateContainerConfigError` | Secret `s3-config` chưa tạo hoặc sai key (`s3.json`) |
| Pod `objects` CrashLoop, log `permission denied` /data | `kubectl -n "$NS" logs deploy/objects`; StorageClass / fsGroup |
| Pod bị `exceeded quota` | Chưa xóa `quota-positive` của Task 1, hoặc còn Pod rác: `kubectl -n "$NS" get pod` |
| Rollout không Ready | `describe pod` → readinessProbe 8333; `weed mini` khởi động chậm, đợi thêm |
| seed `InvalidAccessKeyId` / `SignatureDoesNotMatch` | Chạy lại `make_identities.py` sau khi tạo Secret → key lệch. Xóa 4 Secret, tạo lại từ `private/` hiện tại, `kubectl rollout restart deploy/objects` |
| seed timeout / lỗi DNS | Pod owner có nhãn `access: s3` chưa? `kubectl -n "$NS" get pod --show-labels`; endpointslice của `objects` |

Lỗi thì giữ file cũ (đổi tên `...-attempt1`), sửa rồi chạy lại — không ghi đè.

## Không commit

`private/`, `*.env`, `s3.json`. Chỉ commit: `src/make_identities.py`, `src/clients.sh`, `manifests/store.yaml`, `Task2Tutorial.md` (và `evidence/`, `store-applied.yaml`, `policies-redacted.json` chỉ từ buổi chạy chính thức).
