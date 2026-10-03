# Evidence index — điền từ lần chạy chính thức

Thay `<...>` bằng người vận hành, người kiểm tra chéo và kết quả thực tế. Giữ đường dẫn raw evidence cùng bundle nộp; không link tới file credential.

| Kết luận cần kiểm chứng | Raw evidence | Người chạy / kiểm tra chéo | Kết quả thực tế |
| --- | --- | --- | --- |
| 32 object đúng hash trước thay Pod | `evidence/before-recovery.jsonl` | `<operator> / <reviewer>` | `<32/32 hoặc thực tế>` |
| Pod UID đổi, một Pod mới Ready | `evidence/pod-before.json`, `evidence/pod-after.json`, `evidence/rollout-time.txt` | `<...>` | `<UID cũ → UID mới; thời điểm rollout>` |
| PVC UID giữ nguyên và Bound | `evidence/pvc-before.json`, `evidence/pvc-after.json` | `<...>` | `<UID trước = UID sau>` |
| Canary chạy xuyên thời điểm xóa Pod | `evidence/canary.jsonl`, `evidence/delete-time.txt` | `<...>` | `<failed reads, first failure, stable read, T_observed>` |
| 32 object đúng hash sau thay Pod | `evidence/after-recovery.jsonl` | `<...>` | `<32/32 hoặc thực tế>` |
| Quyền S3 không đổi | `evidence/recovery-S06.json`, `evidence/recovery-S08.json`, `evidence/recovery-S10.json` | `<...>` | `<200, 403 AccessDenied, 403 AccessDenied>` |
| Quá trình thay Pod và node | `evidence/recovery-events.txt`, `evidence/recovery-storage.log`, `evidence/pod-before.yaml`, `evidence/pod-after.yaml` | `<...>` | `<node, mốc thời gian, cảnh báo nếu có>` |

`recovery-summary.json` là bản tóm tắt có cấu trúc; các file trong bảng là nguồn kiểm chứng. Nếu có lần chạy lỗi, giữ lại file `*-attempt1` và ghi rõ lần nào là kết quả cuối. Giới hạn của phép thử: không chứng minh HA, backup/restore, crash consistency hoặc node-loss durability.
