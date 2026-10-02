## 10. Thành viên khác chạy lại task 1

Ai làm Task 2–5 cũng phải chạy lại Task 1 trước trên cluster của mình, vì storage và client phải nằm trong quota. Mất khoảng 5 phút. Đây là bản luyện tập: **không commit `evidence/` từ máy cá nhân**.

1. Cài môi trường theo `SETUP.md` (WSL, Docker Desktop, kubectl, k3d), tạo cluster `bigdata` và namespace `bd-g01`, `bd-outsider`.
2. Lấy code mới nhất: `git clone` (lần đầu) hoặc `git pull`, rồi `cd ~/lab1-bigdata && source env.sh`.
3. Apply guardrails: `envsubst '${NS}' < manifests/guardrails.yaml | kubectl -n "$NS" apply -f -`.
4. Kiểm tra: `kubectl -n "$NS" describe resourcequota team-budget` (Namespace `bd-g01`, Used toàn 0) và `kubectl -n "$NS" get rolebinding observer -o jsonpath='{.subjects[0].namespace}'` (in `bd-g01`).
5. Tùy chọn, để hiểu quota: `kubectl -n "$NS" create -f manifests/negative.yaml` phải báo `exceeded quota`.
6. Tạo branch riêng trước khi làm phần mình: `git checkout -b task2-khanh` (đổi theo task và tên), làm xong thì push và mở Pull Request vào `main` để Trung review.

**Các task sau dùng gì từ Task 1:**

| Task | Người | Dùng lại |
| --- | --- | --- |
| 2 · Storage | Khánh | Quota: storage 500m/512Mi + 4 client 100m/128Mi phải lọt vào. Nhãn `app: objects` của Pod storage khớp NetworkPolicy. Pod client có nhãn `access: s3` mới vào được cổng 8333 |
| 3 · Access governance | Trung Nguyễn | ServiceAccount, Role, RoleBinding `observer` cho K01–K06; NetworkPolicy cho N01–N04. Đồng thời kiểm tra chéo `evidence/quota-reject.txt` |
| 4 · Đo lường | Tất Tú | `kubectl top pod` (metrics-server) để lấy mẫu tài nguyên; budget để giải thích bottleneck CPU |
| 5 · Recovery | Hải Anh | Quota `pods: 10` đủ chỗ cho Pod storage mới khi thay Pod; PVC đã tính trong `requests.storage` |

Có lỗi thì xem mục 7 và mục 9 trước, sau đó gửi output lệnh vào nhóm.
