# Evidence index — điền từ lần chạy chính thức

Thay `<...>` bằng người vận hành, người kiểm tra chéo và kết quả thực tế. Giữ đường dẫn raw evidence cùng bundle nộp; không link tới file credential.

| Kết luận cần kiểm chứng | Raw evidence | Người chạy / kiểm tra chéo | Kết quả thực tế |
| --- | --- | --- | --- |
| Môi trường và phiên bản Kubernetes | `evidence/versions.yaml` | `<...>` | `<context, client/server version>` |
| Task 1: Pod hợp lệ được nhận, Pod vượt quota bị từ chối | `evidence/quota-before.yaml`, `evidence/quota-positive.txt`, `evidence/quota-reject.txt`, `evidence/budget.md` | `<...>` | `<Running; exceeded quota; budget>` |
| Task 2: Service riêng, PVC Bound và imageID | `manifests/store-applied.yaml`, `evidence/topology.txt`, `evidence/T2-provenance.json`, `evidence/T2-storageclass.txt` | `<...>` | `<1 Ready, ClusterIP 8333, PVC 4Gi>` |
| Task 2: hai bucket, fixture và hai lần đọc đúng hash | `evidence/seed.jsonl`, `evidence/T2-ingestor-read-raw.json`, `evidence/T2-analyst-read-release.json` | `<...>` | `<4 PUT, 2 GET, SHA-256>` |
| Task 3: 12 S3, 6 RBAC, 4 network | `security-results.csv`, `evidence/S*.json`, `evidence/K*.txt`, `evidence/N*.json` | `<...>` | `<22 kết quả; nêu các lần sửa>` |
| Governance: trách nhiệm, phân loại, retention và policy | `governance.json`, `policies-redacted.json`, `contribution.csv` | `<...>` | `<hai bucket, mã sinh viên, ngày cleanup, commit policy>` |
| Task 4: sáu trial và mẫu tài nguyên | `evidence/r*-c*.jsonl`, `evidence/benchmark-summary.csv`, `evidence/resource-samples.txt` | `<...>` | `<192 PUT, 192 GET nếu đủ; median/ratio>` |
| 32 object đúng hash trước thay Pod | `evidence/before-recovery.jsonl` | `<operator> / <reviewer>` | `<32/32 hoặc thực tế>` |
| Pod UID đổi, một Pod mới Ready | `evidence/pod-before.json`, `evidence/pod-after.json`, `evidence/rollout-time.txt` | `<...>` | `<UID cũ → UID mới; thời điểm rollout>` |
| PVC UID giữ nguyên và Bound | `evidence/pvc-before.json`, `evidence/pvc-after.json` | `<...>` | `<UID trước = UID sau>` |
| Canary chạy xuyên thời điểm xóa Pod | `evidence/canary.jsonl`, `evidence/delete-time.txt` | `<...>` | `<failed reads, first failure, stable read, T_observed>` |
| 32 object đúng hash sau thay Pod | `evidence/after-recovery.jsonl` | `<...>` | `<32/32 hoặc thực tế>` |
| Quyền S3 không đổi | `evidence/recovery-S06.json`, `evidence/recovery-S08.json`, `evidence/recovery-S10.json` | `<...>` | `<200, 403 AccessDenied, 403 AccessDenied>` |
| Quá trình thay Pod và node | `evidence/recovery-events.txt`, `evidence/recovery-storage.log`, `evidence/pod-before.yaml`, `evidence/pod-after.yaml` | `<...>` | `<node, mốc thời gian, cảnh báo nếu có>` |

`recovery-summary.json` là bản tóm tắt có cấu trúc; các file trong bảng là nguồn kiểm chứng. Nếu có lần chạy lỗi, giữ lại file `*-attempt1` và ghi rõ lần nào là kết quả cuối. Giới hạn của phép thử: không chứng minh HA, backup/restore, crash consistency hoặc node-loss durability.
