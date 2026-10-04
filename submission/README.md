# Lab 1 — Governed research-data landing zone (team-01)

## Thiết kế

Cluster k3d (k3s v1.35.5) chạy trên một laptop qua WSL. Namespace `bd-g01` có ResourceQuota `team-budget`, NetworkPolicy `private-object-store` và observer RBAC chỉ đọc. Storage là SeaweedFS 4.12 (`weed mini`, 1 replica, Recreate) với PVC 4Gi `local-path` mount tại `/data`, Service ClusterIP 8333, chạy non-root UID 1000. Ba identity S3 theo bucket: ingestor (raw), analyst (release, chỉ đọc), owner. Image ghim theo digest. kubectl client 1.37 lệch hơn một minor version so với server 1.35; các lệnh dùng trong lab không bị ảnh hưởng.

## Kết quả

Task 1: Pod 100m được admit; Pod 3 CPU bị từ chối `exceeded quota`; budget storage + 4 client (900m/3 CPU, 1Gi/3Gi) khớp đúng Used sau Task 2. Task 2: 4 fixture được seed, ingestor và analyst đọc đúng SHA-256. Task 3: 22/22 test đúng ma trận; S3 deny đều 403 AccessDenied; RBAC deny đúng principal observer; N02–N04 bị chặn với positive control ngay sau mỗi lần; N04 bị chặn dù outsider gắn `access=s3`. Task 4: 192/192 PUT, 192/192 GET verified; concurrency 4 chậm hơn (PUT 0,82×, GET 0,84×), p95 tăng 3–7 lần. Một lần đo chẩn đoán ngoài 6 trial cho thấy cả ingestor (limit 500m) và storage (limit 1 CPU) đều bị bóp CPU khi chạy 4 luồng. Task 5: Pod mới sau 19 s, UID đổi, PVC UID giữ nguyên, 32/32 object khớp hash trước và sau, T_observed = 5,0 s (5 lần đọc lỗi), S06/S08/S10 giữ đúng quyền.

## Giới hạn

Một replica nên không có HA, backup, crash-consistency hay độ bền khi mất node; volume local-path gắn với một node. HTTP nội bộ, Secret chỉ base64, không có encryption at rest. Label là selector, không phải identity mật mã; không chống được namespace administrator độc hại. Log do client sinh ra không phải audit trail bất biến. Metrics-server cập nhật khoảng 15 s/lần trong khi mỗi trial chỉ khoảng 3 s, nên số liệu tài nguyên chỉ để tham khảo; bộ đếm throttling cộng dồn từ lúc Pod khởi động. Kết luận về điểm nghẽn là giả thuyết. Canary đọc khoảng 1 lần/giây nên T_observed không phải downtime chính xác. Retention là cam kết, chưa được enforce. Log storage đã che key trước khi nộp.

## Quy trình

Từng thành viên xây dựng và luyện tập phần của mình (tutorial và script trong repo). Evidence chính thức là một lần chạy hợp nhất Task 1–5 trên cluster sạch do Trung thao tác; `evidence/_practice-*` là các lần luyện tập, giữ lại cả các lỗi đã sửa. Danh sách evidence: `evidence/INDEX.md`.
