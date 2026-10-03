# Task 2 — Triển khai persistent object storage

> 25 phút · 12 điểm nhóm · Kết quả: một S3 service **private, có xác thực**, dữ liệu nằm trên PVC.

**Điều kiện:** đã chạy Task 1 trên cluster của mình. Mọi lệnh chạy trong WSL, từ `~/lab1-bigdata`.

**Cách đọc:** mỗi bước có 1 khối lệnh, các lệnh được đánh số `①②③…`. Bảng ngay dưới cho biết từng lệnh phải ra gì. Nếu khác → làm theo cột *Nếu khác*, không chạy bước tiếp theo.

**Output khó đọc** (quota, kết quả S3 dạng JSON, UID/digest) được đưa qua `src/fmt.py` để in thành bảng, rồi so với khối **Mẫu output** trong tutorial. `fmt.py` chỉ để xem; evidence vẫn lưu bản gốc.

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
| R | Reset (luyện tập) | Về lại trạng thái sau Task 1, chạy lại từ Bước 0 |

| File | Nội dung |
|---|---|
| `src/make_identities.py` | Sinh key owner / ingestor / analyst vào `private/` + `policies-redacted.json` (không key) |
| `manifests/store.yaml` | PVC `object-data` 4Gi · Deployment `objects` (1 replica, Recreate) · Service `objects:8333` |
| `src/fmt.py` | In quota, kết quả S3, UID/digest thành bảng để đối chiếu |
| `src/reset_task2.sh` | Xóa tài nguyên Task 2, đưa namespace về trạng thái ngay sau Task 1 |
| `src/clients.sh` | Pod owner, ingestor, analyst (nhãn `access: s3` + Secret) và blocked (không nhãn, không key) |

---

## Bước 0 — Kiểm tra trước

```bash
cd ~/lab1-bigdata && source env.sh
echo "$NS"; echo "$STORAGE_IMAGE"; echo "$CLIENT_IMAGE"                  # ①
ls src/make_identities.py src/clients.sh manifests/store.yaml           # ②
kubectl config current-context                                          # ③
kubectl -n "$NS" get resourcequota team-budget -o json | python3 src/fmt.py quota   # ④
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
| ④ | Bảng 7 dòng, cột USED toàn `0` — xem mẫu bên dưới | `NotFound` → chưa làm Task 1 · USED ≠ 0 → còn Pod/PVC cũ |
| ⑤ | `POD-SELECTOR` = `app=objects` | Apply lại `guardrails.yaml` |
| ⑥ | Đủ 3 dòng: serviceaccount, role, rolebinding `observer` | Apply lại `guardrails.yaml` |
| ⑦ | `No resources found in bd-g01 namespace.` | Còn `quota-positive` → `kubectl -n "$NS" delete pod quota-positive` |
| ⑧ | `local-path (default)` | Không có `(default)` → PVC sẽ kẹt `Pending` |
| ⑨ | `drwx------ … private` | `chmod 700 private` |

Mẫu output ④:

```text
RESOURCE                USED  HARD
----------------------  ----  ----
limits.cpu              0     4
limits.memory           0     4Gi
persistentvolumeclaims  0     2
pods                    0     10
requests.cpu            0     2
requests.memory         0     2Gi
requests.storage        0     8Gi
```

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
kubectl -n "$NS" get pod -L app,role,access                             # ②
kubectl -n "$NS" get pod,pvc,svc,endpointslice -o wide > evidence/topology.txt
grep -c Running evidence/topology.txt                                   # ③
kubectl -n "$NS" get resourcequota team-budget -o json | python3 src/fmt.py quota   # ④
```

| # | Kỳ vọng | Nếu khác |
|---|---|---|
| ① | 4 dòng `pod/<role> created`, rồi 4 dòng `condition met` | Timeout → `describe pod <role>` |
| ② | 5 Pod `1/1 Running`, cột APP/ROLE/ACCESS như mẫu bên dưới | blocked có `s3` ở cột ACCESS → sai, xóa và tạo lại |
| ③ | `5` | Có Pod chưa Running |
| ④ | Cột USED như mẫu bên dưới, khớp cột "Tổng" trong `evidence/budget.md` | Khác → tìm Pod thừa: `kubectl -n "$NS" get pod` |

Mẫu output ② (tên Pod storage và AGE sẽ khác):

```text
NAME                       READY   STATUS    RESTARTS   AGE   APP       ROLE       ACCESS
analyst                    1/1     Running   0          1m              analyst    s3
blocked                    1/1     Running   0          1m              blocked
ingestor                   1/1     Running   0          1m              ingestor   s3
objects-xxxxxxxxxx-xxxxx   1/1     Running   0          5m    objects
owner                      1/1     Running   0          1m              owner      s3
```

Mẫu output ④:

```text
RESOURCE                USED  HARD
----------------------  ----  ----
limits.cpu              3     4
limits.memory           3Gi   4Gi
persistentvolumeclaims  1     2
pods                    5     10
requests.cpu            900m  2
requests.memory         1Gi   2Gi
requests.storage        4Gi   8Gi
```

---

## Bước 4 — Seed và đọc kiểm chứng

```bash
kubectl -n "$NS" exec owner -- python /opt/s3lab.py seed > evidence/seed.jsonl
echo "exit=$?"                                                          # ①

kubectl -n "$NS" exec ingestor -- python /opt/s3lab.py \
  probe get research-raw fixture.txt > evidence/T2-ingestor-read-raw.json
echo "exit=$?"                                                          # ②

kubectl -n "$NS" exec analyst -- python /opt/s3lab.py \
  probe get research-release fixture.txt > evidence/T2-analyst-read-release.json
echo "exit=$?"                                                          # ③

python3 src/fmt.py results evidence/seed.jsonl \
  evidence/T2-ingestor-read-raw.json evidence/T2-analyst-read-release.json   # ④
```

| # | Kỳ vọng | Nếu khác |
|---|---|---|
| ① | `exit=0` | Khác 0 → xem dòng `FAIL` ở ④ |
| ② | `exit=0` | `exit=2` → xem dòng `FAIL` ở ④ |
| ③ | `exit=0` | như trên |
| ④ | Bảng 6 dòng giống mẫu: 4 dòng PUT của owner, 2 dòng GET; tất cả `200` + `OK`; 2 dòng GET có SHA256 = `khớp` | `FAIL` + `InvalidAccessKeyId` / `EndpointConnectionError` → Lỗi thường gặp · SHA256 không phải `khớp` → fixture sai, không được tính pass |

Mẫu output ④:

```text
PRINCIPAL  OP   BUCKET            KEY               HTTP  KẾT QUẢ  BYTES  SHA256
---------  ---  ----------------  ----------------  ----  -------  -----  ------
owner      PUT  research-raw      fixture.txt       200   OK       25     -
owner      PUT  research-raw      delete-probe.txt  200   OK       25     -
owner      PUT  research-release  fixture.txt       200   OK       25     -
owner      PUT  research-release  delete-probe.txt  200   OK       25     -
ingestor   GET  research-raw      fixture.txt       200   OK       25     khớp
analyst    GET  research-release  fixture.txt       200   OK       25     khớp
```

`khớp` nghĩa là SHA-256 trả về bằng `9ce4c8bb96c85122c3b386653fbe9150cb2f4df03f25c83408fe11c29b87d6f8` (hằng số trong README).

---

## Bước 5 — Evidence nguồn gốc

```bash
kubectl -n "$NS" get pod,pvc -o json > evidence/T2-provenance.json
kubectl get storageclass > evidence/T2-storageclass.txt
python3 src/fmt.py uids < evidence/T2-provenance.json                   # ①

kubectl -n "$NS" exec deploy/objects -- ls -la /data > evidence/T2-data-mount.txt
cat evidence/T2-data-mount.txt                                          # ②

grep -l -E 'secretKey|AWS_SECRET' manifests/*.yaml policies-redacted.json evidence/* \
  || echo "sạch"                                                        # ③
```

| # | Kỳ vọng | Nếu khác |
|---|---|---|
| ① | Bảng 6 dòng như mẫu: 5 Pod `Running` cùng node, 1 PVC `Bound`. Không ô nào là `-`. Digest storage bắt đầu `d7f3fdf6fb9c`, client `b9e7cf4d42d7` (khớp `env.sh`) | Ô `-` → Pod chưa Running · digest khác `env.sh` → sai image |
| ② | `/data` không rỗng (file/thư mục do SeaweedFS tạo), chủ sở hữu `1000` | Rỗng → server không ghi vào PVC |
| ③ | `sạch` | In ra tên file → file đó chứa secret, không được nộp |

Mẫu output ① (UID, tên Pod storage và volume sẽ khác):

```text
KIND  NAME                      UID                                   PHASE    NODE / SC             IMAGE / VOLUME
----  ------------------------  ------------------------------------  -------  --------------------  ------------------------------------------
Pod   analyst                   1a2b3c4d-…                            Running  k3d-bigdata-server-0  s3lab@b9e7cf4d42d7…
Pod   blocked                   …                                     Running  k3d-bigdata-server-0  s3lab@b9e7cf4d42d7…
Pod   ingestor                  …                                     Running  k3d-bigdata-server-0  s3lab@b9e7cf4d42d7…
Pod   objects-xxxxxxxxxx-xxxxx  …                                     Running  k3d-bigdata-server-0  seaweedfs@d7f3fdf6fb9c…
Pod   owner                     …                                     Running  k3d-bigdata-server-0  s3lab@b9e7cf4d42d7…
PVC   object-data               …                                     Bound    local-path            pvc-…
```

Ghi lại UID của Pod `objects-…` và PVC `object-data`: Task 5 sẽ so với hai giá trị này (Pod UID đổi, PVC UID giữ nguyên).

---

## Reset — quay về trạng thái trước Task 2

> ⚠️ **Chỉ dùng trên cluster luyện tập.** Không chạy trong buổi chạy chính thức: xóa PVC = mất dữ liệu, đề cấm xóa PVC.
> Task 1 (quota, NetworkPolicy, observer) được **giữ nguyên**. File evidence cũ không bị xóa mà được cất vào `evidence/_reset-<thời gian>/`.

```bash
cd ~/lab1-bigdata && source env.sh
sh src/reset_task2.sh                                                   # ①  (giữ key cũ)
# hoặc: sh src/reset_task2.sh --new-keys                                #     (cất key cũ, lần sau tạo key mới)
kubectl -n "$NS" get resourcequota team-budget -o json | python3 src/fmt.py quota   # ②
kubectl -n "$NS" get networkpolicy,serviceaccount,role,rolebinding      # ③
kubectl get pv | grep "$NS/object-data" || echo "PV đã xóa"            # ④
ls private/                                                             # ⑤
```

| # | Kỳ vọng | Nếu khác |
|---|---|---|
| ① | Hỏi `Gõ "reset"…` → gõ `reset`. Sau đó lần lượt `pod "owner" deleted`… `deployment.apps "objects" deleted`, `service "objects" deleted`, `persistentvolumeclaim "object-data" deleted`, 4 dòng `secret "…" deleted`, các dòng `moved …`, cuối cùng `No resources found in bd-g01 namespace.` | Gõ sai → `Hủy.`, không có gì bị xóa · kẹt ở PVC → đợi, hoặc kiểm tra còn Pod nào mount `object-data` |
| ② | Giống mẫu ở Bước 0: cột USED toàn `0` | USED ≠ 0 → còn Pod/PVC khác: `kubectl -n "$NS" get pod,pvc` |
| ③ | Còn `private-object-store`, `observer` (serviceaccount, role, rolebinding) — Task 1 không bị đụng | Thiếu → apply lại `guardrails.yaml` |
| ④ | `PV đã xóa` (local-path tự xóa PV khi xóa PVC) | Còn PV `Released` → `kubectl delete pv <tên>` |
| ⑤ | Không `--new-keys`: còn `s3.json`, `owner.env`, `ingestor.env`, `analyst.env` · Có `--new-keys`: chỉ còn thư mục `old-…` | — |

**Chạy lại Task 2 sau reset:**

- Giữ key (mặc định): ở Bước 1 bỏ qua ① `make_identities.py` (nó sẽ báo `đã tồn tại`), chạy tiếp từ ② để tạo lại 4 Secret.
- `--new-keys`: chạy Bước 1 từ đầu như bình thường.

---

## Tiêu chí nghiệm thu (12 điểm)

| Hạng mục | Kiểm tra | Evidence |
|---|---|---|
| Triển khai private (4đ) | 1 replica Ready; ClusterIP 8333; server dùng `s3-config` | `topology.txt`, `store-applied.yaml` |
| PVC bind/mount (3đ) | PVC Bound, mount tại `/data` | `T2-provenance.json`, `T2-data-mount.txt` |
| Fixture + đọc verify (3đ) | 2 bucket, 4 fixture; ingestor đọc raw, analyst đọc release, hash khớp | `seed.jsonl`, `T2-*-read-*.json` |
| Nguồn gốc (2đ) | imageID digest, UID Pod/PVC, StorageClass, manifest không secret | `T2-provenance.json`, `T2-storageclass.txt`, `policies-redacted.json` |

**Để giải thích khi được hỏi:** lab dùng HTTP nội bộ vì dữ liệu là tổng hợp · Secret chỉ là base64, không phải mã hóa · một port TCP đang mở không chứng minh S3 có xác thực, phải có lần đọc đúng identity.

## Kiểm chéo (E kiểm tra B)

E tự chạy: `get pvc object-data` → so UID với `python3 src/fmt.py uids < evidence/T2-provenance.json`; chạy lệnh đọc của analyst ở Bước 4 → so sha256.

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

`private/`, `*.env`, `s3.json`. Chỉ commit `src/make_identities.py`, `src/clients.sh`, `src/fmt.py`, `src/reset_task2.sh`, `manifests/store.yaml`, `Task2Tutorial.md`. `evidence/`, `store-applied.yaml`, `policies-redacted.json` chỉ commit từ buổi chạy chính thức.
