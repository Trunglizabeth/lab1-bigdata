# Evidence index — team-01 · Lab 1 Cluster Configuration

Lần chạy chính thức: 2026-10-04, cluster k3d `bigdata` (k3s v1.35.5+k3s1), namespace `bd-g01`, outsider `bd-outsider`.
Operator mọi lần chạy chính thức: **Trung**. Cột Reviewer chỉ điền tên khi người đó đã thật sự kiểm tra file; chưa kiểm tra thì để `PENDING`.

`evidence/_practice-*` là các lần luyện tập trên cluster trước (kể cả lỗi đã sửa: `*-attempt1*`), **không** phải evidence chính thức.

---

## Task 0 — Preflight

| File | Chứng minh | Kết quả thực tế | Operator | Reviewer |
|---|---|---|---|---|
| `evidence/versions.yaml` | Version kubectl / k3s / k3d | client v1.37.1, server v1.35.5+k3s1 (cảnh báo version skew, không ảnh hưởng lệnh dùng trong lab) | Trung | PENDING |
| `evidence/context.txt` | Đúng cluster | `k3d-bigdata` | Trung | PENDING |

## Task 1 — Guardrails (10 điểm)

| File | Chứng minh | Kết quả thực tế | Operator | Reviewer |
|---|---|---|---|---|
| `manifests/guardrails-applied.yaml` | Manifest đã apply (`${NS}` = `bd-g01`) | Quota, NetworkPolicy, ServiceAccount, Role, RoleBinding `observer` | Trung | PENDING |
| `evidence/guardrails-apply.txt` | Output apply | 5 đối tượng `created` | Trung | PENDING |
| `evidence/quota-before.yaml` | Quota tồn tại trước khi tạo Pod thử | `used` toàn 0 | Trung | PENDING |
| `manifests/positive.yaml` | Pod hợp lệ nhỏ | requests 100m/128Mi, limits 200m/256Mi, securityContext hardened | Trung | PENDING |
| `evidence/quota-positive.txt` | Pod nhỏ được admit | `pod/quota-positive created`, `Running` | Trung | PENDING |
| `evidence/quota-used-positive.txt` | Quota tính Pod positive | requests.cpu 100m, limits.cpu 200m, pods 1 | Trung | PENDING |
| `manifests/negative.yaml` | Pod quá khổ, chỉ khác tên và CPU | requests = limits = 3 CPU | Trung | PENDING |
| `evidence/quota-reject.txt` | Pod lớn bị từ chối đúng lý do, không được tạo | `exceeded quota: team-budget, requested: requests.cpu=3, used: requests.cpu=100m, limited: requests.cpu=2` + `NotFound` | Trung | PENDING |
| `evidence/budget.md` | Tổng resource budget | storage + 4 client = 900m/3 CPU, 1Gi/3Gi RAM, PVC 4Gi, 5 Pod, dưới quota | Trung | PENDING |
| `evidence/quota-after-task2.txt` | Budget khớp thực tế | Used sau Task 2 = 900m / 3 / 1Gi / 3Gi / 4Gi / 1 PVC / 5 Pod, đúng bảng budget | Trung | PENDING |
| `evidence/quota-crosscheck-C.stdout.txt`, `.stderr.txt` | Kiểm tra chéo quota | `exceeded quota: team-budget` | Trung | PENDING |

## Task 2 — Storage (12 điểm)

| File | Chứng minh | Kết quả thực tế | Operator | Reviewer |
|---|---|---|---|---|
| `manifests/store-applied.yaml` | PVC, Deployment, Service đã apply | 1 replica, Recreate, PVC 4Gi, ClusterIP 8333 | Trung | PENDING |
| `policies-redacted.json` | Quyền S3 theo vai trò, không có key | owner Admin; ingestor Read/Write/List research-raw; analyst Read/List research-release | Trung | PENDING |
| `evidence/topology.txt` | Pod, PVC, Service, EndpointSlice | 5 Pod Running, PVC Bound, Service ClusterIP | Trung | PENDING |
| `evidence/seed.jsonl` | Tạo bucket và fixture | 4 PUT `200 OK` (fixture.txt, delete-probe.txt × 2 bucket) | Trung | PENDING |
| `evidence/T2-ingestor-read-raw.json` | Ingestor đọc raw | `200`, SHA-256 `9ce4c8bb…d6f8` khớp | Trung | PENDING |
| `evidence/T2-analyst-read-release.json` | Analyst đọc release | `200`, SHA-256 khớp | Trung | PENDING |
| `evidence/T2-provenance.json` | UID Pod / PVC, imageID | Pod `objects-69888b7969-cqk8z` UID `c5b82e5c-…`; PVC `object-data` UID `fa79cc71-…` | Trung | PENDING |
| `evidence/T2-storageclass.txt` | StorageClass | `local-path (default)` | Trung | PENDING |
| `evidence/image-digests.txt` | Digest image đang chạy | storage `seaweedfs@sha256:d7f3fdf6fb9c…`, client `s3lab@sha256:b9e7cf4d42d7…` | Trung | PENDING |
| `evidence/T2-data-mount.txt` | Dữ liệu và metadata nằm trên PVC | `/data` có volume `*.dat/*.idx`, `filerldb2/`, `m9333/`; setgid từ fsGroup | Trung | PENDING |
| `evidence/T2-runas.txt` | Chạy non-root | uid 1000 | Trung | PENDING |

## Task 3 — Governance (20 điểm)

| File | Chứng minh | Kết quả thực tế | Operator | Reviewer |
|---|---|---|---|---|
| `security-results.csv` | Bảng 22 test, sinh từ evidence | 22/22 pass | Trung | PENDING |
| `evidence/S01.json` … `S03.json` | ingestor PUT / GET / LIST research-raw | `200 OK` (S02 hash khớp) | Trung | PENDING |
| `evidence/S04.json`, `S05.json` | ingestor PUT / GET research-release | `403 AccessDenied` | Trung | PENDING |
| `evidence/S06.json`, `S07.json` | analyst GET / LIST research-release | `200 OK` (S06 hash khớp) | Trung | PENDING |
| `evidence/S08.json` … `S11.json` | analyst PUT / DELETE release, GET / LIST raw | `403 AccessDenied` | Trung | PENDING |
| `evidence/S12.json` | anonymous GET release | `403 AccessDenied`, principal `anonymous` | Trung | PENDING |
| `evidence/K01.*`, `K02.*`, `K03.*` | Observer list Pod / get events / đọc log storage | Allow, stderr trống | Trung | PENDING |
| `evidence/K04.*`, `K05.*`, `K06.*` | Observer đọc Secret / tạo Pod / xóa Pod (dry-run server) | `Forbidden`, principal `system:serviceaccount:bd-g01:observer` | Trung | PENDING |
| `evidence/N01.txt` | Positive control | `tcp_connected: true` | Trung | PENDING |
| `evidence/N02.txt` + `N01-after-N02.txt` | blocked → objects:8333 | `false`, control sau `true` | Trung | PENDING |
| `evidence/N03-listen-check.txt` | Cổng 8888 thật sự listen | `Filer service is ready at http://10.42.0.11:8888` (trùng Pod IP) | Trung | PENDING |
| `evidence/N03.txt` + `N01-after-N03.txt` | owner → Pod IP:8888 | `false`, control sau `true` | Trung | PENDING |
| `evidence/N04-dns.txt` | Outsider phân giải được Service | `10.43.229.103` (= ClusterIP) | Trung | PENDING |
| `evidence/N04-outsider-netpol.txt` | Không có policy gây nhiễu | `No resources found in bd-outsider` | Trung | PENDING |
| `manifests/outsider-applied.yaml` | Outsider fixture | Pod `outsider` ở `bd-outsider`, cố tình gắn `access=s3` | Trung | PENDING |
| `evidence/N04.txt` + `N01-after-N04.txt` | outsider → FQDN:8333 | `false` (ConnectionRefusedError), control sau `true` | Trung | PENDING |
| `governance.json` | Trách nhiệm và retention cho 2 bucket | `retention_enforced: false` | Trung | PENDING |

## Task 4 — Measurement (14 điểm)

| File | Chứng minh | Kết quả thực tế | Operator | Reviewer |
|---|---|---|---|---|
| `evidence/r1-c1.jsonl` … `r3-c4.jsonl` | 6 trial thô, đúng thứ tự r1-c1, r1-c4, r2-c4, r2-c1, r3-c1, r3-c4 | mỗi trial 32/32 PUT, 32/32 GET verified | Trung | PENDING |
| `evidence/bench-times.txt` | Thời điểm bắt đầu / kết thúc từng trial | 15:17:47 → 15:18:07, tất cả `exit=0` | Trung | PENDING |
| `benchmark-summary.csv` | 6 trial × 2 phase | 12 dòng, hash_failures = 0 | Trung | PENDING |
| `evidence/benchmark-analysis.txt` | Median, ratio, tổng | PUT median c1 109,16 / c4 89,51 MiB/s (0,820×); GET 367,88 / 307,50 MiB/s (0,836×); 192/192 PUT, 192/192 GET | Trung | PENDING |
| `evidence/benchmark-sha256.txt` | Hash của file thô | — | Trung | PENDING |
| `evidence/resource-samples.txt` | Lấy mẫu CPU/RAM/Pod mỗi 5 s | metrics-server cập nhật ~15 s/lần; chỉ có ~1 điểm dữ liệu thật trong benchmark | Trung | PENDING |
| `evidence/task4-cpustat-ingestor.txt`, `task4-cpustat-objects.txt` | Bộ đếm throttling cgroup (cộng dồn từ lúc Pod khởi động) | ingestor 119/255 chu kỳ bị bóp; objects 38/6835 | Trung | PENDING |
| `evidence/task4-diag-c4.jsonl`, `task4-throttle-diag.txt` | **Chẩn đoán bổ sung, ngoài 6 trial** (prefix `diag/`) | trong lần chạy c4: ingestor +25, objects +10 chu kỳ bị bóp | Trung | PENDING |
| `evidence/task4-retest-S08.json`, `task4-retest-S10.json` | Quyền không đổi sau benchmark | `403 AccessDenied` | Trung | PENDING |

## Task 5 — Recovery (14 điểm)

| File | Chứng minh | Kết quả thực tế | Operator | Reviewer |
|---|---|---|---|---|
| `evidence/before-recovery.jsonl` | Toàn vẹn trước | 32/32 `bench/r1-c1` verified | Trung | PENDING |
| `evidence/pod-before.yaml`, `.json` | Pod trước | `objects-69888b7969-cqk8z`, UID `c5b82e5c-fbd1-4a16-bba9-027d17bf9c1b` | Trung | PENDING |
| `evidence/pvc-before.yaml`, `.json` | PVC trước | UID `fa79cc71-194b-4483-a8bf-ecd44ded0499` | Trung | PENDING |
| `evidence/canary.jsonl` | Đọc liên tục trong lúc thay Pod | 180 mẫu, 5 lần lỗi (`EndpointConnectionError`) | Trung | PENDING |
| `evidence/delete-time.txt` | Thời điểm xóa Pod | 2026-10-04T15:28:35Z | Trung | PENDING |
| `evidence/rollout-time.txt` | Thời điểm Pod mới sẵn sàng | 2026-10-04T15:28:54Z (19 s) | Trung | PENDING |
| `evidence/pod-after.yaml`, `.json` | Pod sau | `objects-69888b7969-zd4bz`, UID `88abb925-89d1-429e-8922-30abe2ab7ef6` (đã đổi) | Trung | PENDING |
| `evidence/pvc-after.yaml`, `.json` | PVC sau | UID `fa79cc71-…` (giữ nguyên), `Bound` | Trung | PENDING |
| `evidence/after-recovery.jsonl` | Toàn vẹn sau | 32/32 verified | Trung | PENDING |
| `evidence/recovery-events.txt` | Sự kiện Kubernetes khi thay Pod | — | Trung | PENDING |
| `evidence/recovery-storage.redacted.log` | Log storage mới (đã che key) | — | Trung | PENDING |
| `evidence/image-digests-after-recovery.txt` | Pod mới dùng đúng image | `seaweedfs@sha256:d7f3fdf6fb9c…` | Trung | PENDING |
| `evidence/recovery-S06.json`, `S08.json`, `S10.json` | Quyền không đổi sau khôi phục | S06 `200` hash khớp; S08, S10 `403 AccessDenied` | Trung | PENDING |
| `recovery-summary.json` | Tổng hợp từ evidence | pod_uid_changed, pvc_uid_unchanged, T_observed = 5,023 s, ready trong 19 s ≤ 120 s | Trung | PENDING |

## Individual và kiểm tra chéo

| Thư mục / file | Người tự làm | Trạng thái |
|---|---|---|
| `individual/A/` | Trung | PENDING |
| `individual/B/` | Khánh | PENDING |
| `individual/C/` | Trung Nguyễn | PENDING |
| `individual/D/` | Tất Tú | PENDING |
| `individual/E/` | Hải Anh | PENDING |
| `evidence/review-D-S08.json`, `review-D-S10.json` | Tất Tú (kiểm tra chéo C) | PENDING |

## Ghi chú

- Log storage gốc chứa chuỗi nhạy cảm nên chỉ nộp bản đã che (`*.redacted.log`); bản gốc giữ trong `private/`, không commit.
- Log do client sinh ra không phải audit trail bất biến phía server.
