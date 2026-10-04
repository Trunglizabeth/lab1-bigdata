# Team XX — Lab 1: Private object storage trên Kubernetes

> Bản này copy sang `submission/README.md` rồi thay mọi `<...>` bằng số đo thật. Độ dài yêu cầu: 300–500 từ (`wc -w submission/README.md`). Xóa dòng trích dẫn này trước khi nộp.

## Thiết kế

Cluster `<k3d bigdata, Kubernetes vX.Y>`, namespace `<bd-g01>`. Guardrails (Task 1): ResourceQuota `team-budget` (requests 2 CPU / 2Gi, limits 4 CPU / 4Gi, 2 PVC, 8Gi storage, 10 Pod), NetworkPolicy `private-object-store` chỉ cho Pod cùng namespace có nhãn `access=s3` vào TCP 8333 của Pod `app=objects`, và ServiceAccount `observer` chỉ đọc pods, pods/log, events.

Storage (Task 2): một Deployment SeaweedFS `<image@sha256:...>` (1 replica, Recreate), PVC `object-data` 4Gi `local-path`, Service ClusterIP `objects:8333`. Ba identity S3: owner (Admin), ingestor (Read/Write/List `research-raw`), analyst (Read/List `research-release`). Key chỉ nằm trong Secret, không có trong bundle.

## Kết quả

- Task 1: Pod hợp lệ `<Running>`; Pod xin 3 CPU bị từ chối `<exceeded quota: team-budget>`; tổng budget 900m/3 CPU, 1Gi/3Gi, 4Gi PVC, 5 Pod.
- Task 2: PVC `<Bound, UID ...>`; 4 fixture được seed; ingestor và analyst đọc đúng SHA-256 `9ce4c8bb…`.
- Task 3: `<x>/12` S3, `<x>/6` RBAC, `<x>/4` network pass (`security-results.csv`). `<Ghi các lần lỗi và lần retest, nếu có>`.
- Task 4: 6 trial × 32 object × 4 MiB. PUT median c1 `<…>` MiB/s, c4 `<…>` MiB/s, ratio `<…>`x; GET median c1 `<…>`, c4 `<…>`, ratio `<…>`x. `<192/192>` PUT hợp lệ, `<192/192>` GET đúng hash. p95 báo cáo từng trial, không lấy trung bình.
- Task 5: Pod UID `<cũ → mới>`, PVC UID không đổi; 32/32 object đúng hash trước và sau; rollout `<…>` s sau khi xóa; canary `<n>` lần đọc lỗi, `T_observed = <…>` s (hoặc "interruption not observed at this sampling resolution"); S06 200, S08/S10 403 AccessDenied sau recovery.

## Diễn giải

`<Concurrency 4 có/không tăng goodput; nêu confounder: cache, CPU throttling theo limit, local-path cùng node, cluster dùng chung. Resource samples chỉ hỗ trợ, không chứng minh nguyên nhân.>`

## Giới hạn

Một replica dùng cùng PVC trên cùng node chỉ chứng minh thay Pod có kiểm soát, không chứng minh HA, backup/restore, crash consistency, node-loss durability, TLS hay mã hóa lưu trữ. Quota giới hạn tài nguyên khai báo, không giới hạn byte trong S3. Nhãn `access=s3` là selector, không phải danh tính mật mã: ai tạo được Pod trong namespace có thể gắn nhãn. Log do client sinh ra không phải audit trail bất biến phía server. Benchmark chạy trên hạ tầng `<riêng/dùng chung>` nên không so sánh throughput tuyệt đối.
