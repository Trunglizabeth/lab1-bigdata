# Hướng dẫn cài đặt môi trường — Lab 1: Cluster Configuration

> **Buổi chạy chính thức và đóng gói bài nộp `team-XX/`:** xem [`SUBMISSION.md`](SUBMISSION.md).

Note này giúp anh em dựng một môi trường giống hệt nhau trên máy cá nhân để làm từng task của mình

> **Lưu ý:** cluster trên máy cá nhân chỉ dùng để luyện tập. Evidence nộp chính thức được chạy trên một cluster duy nhất (máy của t) trong buổi làm chung, để UID, Pod và dữ liệu khớp nhau từ Task 1 đến Task 5. **Không commit thư mục `evidence/` từ máy cá nhân.**

---

## 0. Những gì cần cài

| Công cụ | Vai trò |
|---|---|
| **WSL (Ubuntu)** | Linux chạy trong Windows |
| **Docker Desktop** | Chạy container. Cluster k3d nằm bên trong Docker |
| **k3d** | tạo, bật, tắt, xóa cluster Kubernetes (k3s) trên laptop |
| **kubectl** | mọi thao tác với Kubernetes (apply YAML, xem Pod, exec, log...) |
| **envsubst** | Thay biến như `${NS}` vào file YAML trước khi apply |
| **python3** | Chạy `make_identities.py`, `observer.py` |
| **git** | code và commit |

**Yêu cầu máy:** Windows 10/11 64-bit, RAM ≥ 8 GB, ổ cứng trống ≥ 10 GB.


---

## 1. Cài WSL 

Mở PowerShell bằng quyền Administrator (chuột phải Start → *Terminal (Admin)*):

```powershell
wsl --install -d Ubuntu
```

Khởi động lại máy. Mở Ubuntu từ menu Start, đặt username và password cho Linux. Hãy nhớ password này, vì `sudo` sẽ hỏi.

Kiểm tra trong PowerShell:

```powershell
wsl -l -v
```

Cột `VERSION` của Ubuntu phải là 2. Nếu là 1, chạy `wsl --set-version Ubuntu 2`.

---

## 2. Cài Docker Desktop

1. Tải và cài Docker Desktop từ <https://www.docker.com/products/docker-desktop/>.
2. Mở Docker Desktop, vào Settings:
   - General→ tích *Use the WSL 2 based engine*
   - Resources → WSL integration → bật công tắc cho Ubuntu
   - Bấm Apply & restart
3. Kiểm tra trong Ubuntu:

```bash
docker version
docker run --rm hello-world
```

Phải thấy dòng "Hello from Docker!"

---

## 3. Cài kubectl, k3d và các công cụ phụ

```bash
# Công cụ phụ
sudo apt update
sudo apt install -y gettext-base python3 curl git unzip

# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install kubectl /usr/local/bin/
rm kubectl

# k3d
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

# GitHub CLI 
sudo apt install -y gh
```

```bash
kubectl version --client
k3d version
envsubst --version
python3 --version
git --version
```

---

## 4. Lấy code từ GitHub

```bash
gh auth login        # chọn GitHub.com → HTTPS → Login with a web browser
cd ~
git clone https://github.com/Trunglizabeth/lab1-bigdata.git
cd lab1-bigdata
git config --global user.name "Ten Cua Ban"
git config --global user.email "email-github@example.com"
```

> Để repo trong thư mục nhà của Linux (`~`), không để trong `/mnt/c/...`. 

Cấu trúc repo:

```
lab1-bigdata/
  env.sh          # NS + digest 2 image. Chạy "source env.sh" mỗi khi mở terminal
  src/            # s3lab.py, Dockerfile, make_identities.py, clients.sh, observer.py
  manifests/      # guardrails.yaml, store.yaml, positive.yaml, negative.yaml
  evidence/       # chỉ chứa evidence của buổi chạy chính thức
  individual/     # bài kiểm tra cá nhân
  private/        # key S3, token. Git bỏ qua, KHÔNG BAO GIỜ commit
```

---

## 5. Tạo cluster và kiểm tra đủ điều kiện

Docker Desktop phải đang chạy.

```bash
k3d cluster create bigdata
```

Đợi khoảng 1 phút, rồi kiểm tra từng yêu cầu của đề:

```bash
kubectl config current-context        # phải là: k3d-bigdata
kubectl get nodes                     # STATUS = Ready
kubectl get pods -n kube-system       # coredns, metrics-server, local-path-provisioner = Running
kubectl get storageclass              # local-path (default)
kubectl top nodes                     # có số CPU/RAM (nếu báo "not available yet", đợi 1 phút)
```

| Thành phần | Dùng cho |
|---|---|
| CoreDNS | Client gọi storage bằng tên `objects:8333` |
| metrics-server | `kubectl top pod`, lấy mẫu tài nguyên ở Task 4 |
| StorageClass `local-path` | Cấp ổ đĩa cho PVC 4 GiB ở Task 2, giữ dữ liệu khi thay Pod ở Task 5 |
| Bộ thực thi NetworkPolicy (tích hợp sẵn trong k3s) | Chặn Pod không có label ở Task 3 (N02, N03, N04) |

---

## 6. Tạo namespace và nạp biến môi trường

```bash
cd ~/lab1-bigdata
source env.sh
kubectl create namespace "$NS"          # bd-g01: namespace của nhóm
kubectl create namespace bd-outsider    # namespace người ngoài cho test N04
echo "$NS"; echo "$STORAGE_IMAGE"; echo "$CLIENT_IMAGE"
```

Ba dòng `echo` phải ra giá trị thật, có `@sha256:...`.

---

## 7. Kiểm tra nhanh: cluster kéo được client image

```bash
kubectl -n "$NS" run pull-test --image="$CLIENT_IMAGE" --restart=Never \
  -- python -c "import boto3; print('boto3', boto3.__version__)"
kubectl -n "$NS" get pod pull-test      # đợi tới STATUS = Completed
kubectl -n "$NS" logs pull-test         # phải in: boto3 1.43.107
kubectl -n "$NS" delete pod pull-test
```

Nếu in đúng version, môi trường của bạn đã sẵn sàng. Chuyển sang phần việc của mình. Mỗi người phải chạy lại Task 1 trước (apply `manifests/guardrails.yaml`), vì các task sau phụ thuộc vào task trước.

---

## 8. Các lệnh dùng hằng ngày

Mỗi lần mở terminal mới:

```bash
cd ~/lab1-bigdata
source env.sh
git pull
```

Quản lý cluster:

| Việc | Lệnh |
|---|---|
| Xem cluster | `k3d cluster list` (`1/1` = đang chạy) |
| Tắt (giữ dữ liệu) | `k3d cluster stop bigdata` |
| Bật lại (sau khi khởi động lại máy) | Mở Docker Desktop, rồi `k3d cluster start bigdata` |
| Làm lại từ đầu | `k3d cluster delete bigdata` rồi làm lại mục 5 và 6. Mất hết dữ liệu. |

Lệnh kubectl hay dùng (luôn có `-n "$NS"`):

```bash
kubectl -n "$NS" get pod                 # liệt kê Pod
kubectl -n "$NS" describe pod <ten>      # chi tiết; phần Events ở cuối cho biết lý do lỗi
kubectl -n "$NS" logs <ten>              # xem log
kubectl -n "$NS" exec <ten> -- <lenh>    # chạy lệnh bên trong Pod
```

Git: mỗi người làm trên branch riêng, xong thì tạo Pull Request để t review.

```bash
git checkout -b task2-khanh              # đặt tên branch theo task + tên
git add <file>
git commit -m "Task 2: ..."
git push -u origin task2-khanh
```

---

## 9. Quy tắc bắt buộc

- **Không bao giờ commit** `private/`, file `*.env`, `observer.json`, kubeconfig. Trước mỗi commit, chạy `git status` để kiểm tra.
- **Không commit `evidence/` từ máy cá nhân.** Chỉ evidence của buổi chạy chính thức mới được đưa lên.
- **Không xóa** namespace, PVC hay PV trong buổi chạy chính thức. Chỉ xóa Pod dùng-một-lần đã nêu tên rõ ràng.
- **Giữ lại mọi lần thất bại**: lỗi thì đổi tên file cũ (ví dụ `S05-attempt1.json`), sửa rồi chạy lại. Không ghi đè.
- **Trong buổi chạy chung, mỗi lúc chỉ một người thao tác cluster.** Báo trong nhóm trước và sau khi chạy.
- Debug quá 30 phút không tiến triển thì gửi log lỗi vào nhóm.

---

## 10. Xử lý lỗi thường gặp

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `Cannot connect to the Docker daemon` | Docker Desktop chưa chạy | Mở Docker Desktop, đợi chạy xong rồi thử lại |
| `docker: command not found` trong Ubuntu | Chưa bật WSL integration | Docker Desktop → Settings → Resources → WSL integration → bật Ubuntu |
| `UtilAcceptVsock ... failed 110` / `error getting credentials` | Cầu nối WSL–Windows bị timeout | PowerShell: `wsl --shutdown`, thoát hẳn rồi mở lại Docker Desktop, mở lại Ubuntu |
| `The connection to the server ... was refused` | Cluster đang tắt | `k3d cluster start bigdata` |
| Context không phải `k3d-bigdata` | kubectl trỏ nhầm cluster | `kubectl config use-context k3d-bigdata` |
| `not found` dù chắc chắn đã tạo | Quên `-n "$NS"` hoặc chưa `source env.sh` | Chạy `source env.sh`, thêm `-n "$NS"` |
| Pod `ImagePullBackOff` | Sai biến image hoặc mất mạng | `echo "$CLIENT_IMAGE"`, kiểm tra mạng, `describe pod` |
| Pod hoặc PVC kẹt `Pending` | Thiếu tài nguyên / StorageClass | `kubectl -n "$NS" describe pod <ten>` → đọc Events |
| `SyntaxError: invalid non-printable character U+00A0` | Copy code từ PDF dính ký tự lạ | `sed -i 's/\xC2\xA0/ /g' <file>` |
| `IndentationError` | Thụt lề lệch | Mở bằng `nano`, căn thẳng hàng với dòng cùng cấp |
| Máy rất chậm | Docker/WSL ngốn RAM | Tắt bớt ứng dụng; `k3d cluster stop bigdata` khi không dùng |

---

## Thông tin môi trường chuẩn của nhóm

| Mục | Giá trị |
|---|---|
| Cluster | k3d, tên `bigdata` |
| Namespace | `bd-g01`, outsider `bd-outsider` |
| Storage image | SeaweedFS (digest trong `env.sh`) |
| Client image | `trunglizabeth/s3lab` (digest trong `env.sh`), Python 3.12-slim, boto3 1.43.107 |
| SHA-256 của fixture | `9ce4c8bb96c85122c3b386653fbe9150cb2f4df03f25c83408fe11c29b87d6f8` |
