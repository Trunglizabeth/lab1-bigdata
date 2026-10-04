# Task 5 — Recovery và bàn giao

> Thay đúng storage Pod, giữ nguyên PVC, đo gián đoạn đọc và kiểm tra lại dữ liệu cùng quyền truy cập.

Chạy trong WSL từ `~/lab1-bigdata`. Task 2 đã tạo storage/PVC/client; Task 3 đã thiết lập quyền; Task 4 đã bàn giao 32 object tại `bench/r1-c1`. Trên cluster luyện tập có thể tạo riêng trial `bench/r1-c1`; evidence nộp chính thức phải được lấy từ **cùng cluster chung** sau khi Task 4 hoàn tất sáu trial. Không commit evidence từ máy cá nhân.

## 0. Preflight và mốc trước recovery

Chỉ một người thao tác cluster chung tại một thời điểm. Dừng benchmark và mọi lệnh ghi trước khi bắt đầu. Kiểm tra context, namespace, storage và PVC:

```bash
cd ~/lab1-bigdata
source env.sh
kubectl config current-context
kubectl -n "$NS" get pod -l app=objects -o wide
kubectl -n "$NS" get pod ingestor
kubectl -n "$NS" get pvc object-data
kubectl -n "$NS" get svc objects
```

Kỳ vọng: một storage Pod `1/1 Running`, `ingestor` Running, PVC `Bound`, Service `ClusterIP:8333`. Nếu Task 4 chưa tạo `bench/r1-c1/000.bin` đến `031.bin` trên **cluster này**, dừng và bàn giao lại cho người phụ trách Task 4. Không dùng kết quả từ cluster khác.

```bash
kubectl -n "$NS" exec ingestor -- \
  python /opt/s3lab.py verify bench/r1-c1 \
  > evidence/before-recovery.jsonl
echo "verify_exit=$?"
tail -n 1 evidence/before-recovery.jsonl

kubectl -n "$NS" get pod -l app=objects -o yaml > evidence/pod-before.yaml
kubectl -n "$NS" get pvc object-data -o yaml > evidence/pvc-before.yaml
kubectl -n "$NS" get pod -l app=objects -o json > evidence/pod-before.json
kubectl -n "$NS" get pvc object-data -o json > evidence/pvc-before.json
```

Chỉ tiếp tục nếu `verify_exit=0` và dòng cuối là `"kind": "verified", "objects": 32`. Giữ file JSON để so UID bằng máy; YAML là bằng chứng cấu hình dễ đọc. Nếu đã có evidence của lần thử cũ, đổi tên file cũ sang `*-attempt1` trước khi chạy lại; không ghi đè lần thất bại.

## 1. Canary và thay Pod

Mở **hai terminal**. Terminal A chạy canary; nó phải còn chạy khi Terminal B xóa Pod. Đừng đợi Terminal A trả lại dấu nhắc rồi mới xóa: như vậy sẽ không đo được gián đoạn.

Terminal A:

```bash
cd ~/lab1-bigdata
source env.sh
kubectl -n "$NS" exec ingestor -- \
  python /opt/s3lab.py watch 180 \
  > evidence/canary.jsonl 2> evidence/canary.stderr
echo "canary_exit=$?"
```

Terminal B, trong khi Terminal A vẫn chạy:

```bash
cd ~/lab1-bigdata
source env.sh
POD=$(kubectl -n "$NS" get pod -l app=objects \
  -o jsonpath='{.items[0].metadata.name}')
echo "$POD"
kubectl -n "$NS" get pod "$POD"
head -n 1 evidence/canary.jsonl
```

Xác nhận `$POD` là **đúng một Pod `objects-...` đang Running** và canary đã ghi mẫu đầu tiên. Nếu một điều kiện không đúng, dừng và kiểm tra; chưa xóa gì. Khi đúng, chạy tiếp ngay trong Terminal B:

```bash
date -u +%FT%TZ > evidence/delete-time.txt
kubectl -n "$NS" delete pod "$POD" --wait=false
kubectl -n "$NS" wait --for=delete pod/"$POD" --timeout=120s
kubectl -n "$NS" rollout status deployment/objects --timeout=120s
date -u +%FT%TZ > evidence/rollout-time.txt
```

Chỉ xóa Pod hiện tại bằng lệnh thông thường. Không force-delete, không xóa Deployment, PVC, PV, namespace hoặc dữ liệu S3. Nếu `rollout` lỗi, giữ nguyên evidence và xem `describe pod`, Events, logs trước khi sửa.

## 2. Sau recovery: trạng thái và toàn vẹn

Đợi Terminal A kết thúc. `canary_exit=0` chỉ nói vòng lặp đã kết thúc; phải kiểm tra từng dòng JSONL để biết có request lỗi không.

```bash
kubectl -n "$NS" get pod -l app=objects -o yaml > evidence/pod-after.yaml
kubectl -n "$NS" get pvc object-data -o yaml > evidence/pvc-after.yaml
kubectl -n "$NS" get pod -l app=objects -o json > evidence/pod-after.json
kubectl -n "$NS" get pvc object-data -o json > evidence/pvc-after.json

kubectl -n "$NS" exec ingestor -- \
  python /opt/s3lab.py verify bench/r1-c1 \
  > evidence/after-recovery.jsonl
echo "verify_exit=$?"
tail -n 1 evidence/after-recovery.jsonl

kubectl -n "$NS" get events --sort-by=.metadata.creationTimestamp \
  > evidence/recovery-events.txt
kubectl -n "$NS" logs deployment/objects > evidence/recovery-storage.log
```

Kỳ vọng: một Pod mới Ready, `verify_exit=0`, `"objects": 32`, các GET đều khớp SHA-256. So UID từ JSON đã lưu:

```bash
python3 -c 'import json; p=lambda f: json.load(open(f)); b=p("evidence/pod-before.json")["items"][0]["metadata"]["uid"]; a=p("evidence/pod-after.json")["items"][0]["metadata"]["uid"]; x=p("evidence/pvc-before.json")["metadata"]["uid"]; y=p("evidence/pvc-after.json")["metadata"]["uid"]; print("pod_before",b,"pod_after",a,"pod_changed",b!=a); print("pvc_before",x,"pvc_after",y,"pvc_unchanged",x==y)'
```

Pod UID phải đổi, PVC UID phải giữ nguyên. Ghi node trước/sau và xác nhận dữ liệu vẫn đọc được qua cùng Service `objects:8333`.

## 3. Tính khoảng gián đoạn quan sát được

Từ `canary.jsonl`, lấy `start_s` của lần đọc lỗi đầu tiên. `stable_read_end_s` là `end_s` của **lần đọc đầu tiên trong chuỗi năm lần đọc đúng liên tiếp** sau lỗi đó. `T_observed = stable_read_end_s - first_failure_start_s`.

```bash
python3 -c 'import json; r=[json.loads(x) for x in open("evidence/canary.jsonl")]; bad=[i for i,x in enumerate(r) if not x.get("ok")]; print("samples",len(r),"failed_reads",len(bad)); f=bad[0] if bad else None; s=next((i for i in range(f+1,len(r)-4) if all(x.get("ok") and x.get("hash_ok") for x in r[i:i+5])),None) if f is not None else None; print("first_failure_start_s",r[f]["start_s"] if f is not None else None); print("stable_read_end_s",r[s]["end_s"] if s is not None else None); print("observed_interruption_s",round(r[s]["end_s"]-r[f]["start_s"],3) if s is not None else None)'
```

Nếu không có mẫu lỗi, ghi `interruption not observed at this sampling resolution`. Nếu không có chuỗi năm mẫu đúng, kết quả phục hồi chưa được chứng minh. Mỗi vòng có khoảng nghỉ một giây và thời gian request biến thiên, nên `T_observed` là khoảng gián đoạn **quan sát được**, không phải độ dài mất dịch vụ chính xác. Mục tiêu bài học: Pod mới Ready trong 120 giây từ lúc xóa và `T_observed <= 120` giây nếu đã quan sát được gián đoạn. Dùng timestamp thực, không cộng các timeout lệnh.

## 4. Retest quyền sau recovery

Task 5 phải chạy lại đúng S06, S08, S10; không dùng lại file Task 3:

```bash
kubectl -n "$NS" exec analyst -- \
  python /opt/s3lab.py probe get research-release fixture.txt \
  > evidence/recovery-S06.json
echo "S06 exit=$?"

kubectl -n "$NS" exec analyst -- \
  python /opt/s3lab.py probe put research-release auth-probe.txt \
  > evidence/recovery-S08.json
echo "S08 exit=$?"

kubectl -n "$NS" exec analyst -- \
  python /opt/s3lab.py probe get research-raw fixture.txt \
  > evidence/recovery-S10.json
echo "S10 exit=$?"
```

S06 cần HTTP 200 và hash fixture đúng. S08/S10 cần **HTTP 403 `AccessDenied`**; `exit=2` là mong đợi cho hai request bị từ chối. Formatter có thể in `FAIL` vì request thất bại, nhưng bài test Deny chỉ PASS khi đúng `AccessDenied`, không phải timeout, 404 hay lỗi credential.

## 5. Bàn giao và giới hạn kết luận

Dùng [mẫu recovery summary](templates/recovery-summary.example.json) để điền **giá trị đo thật** vào `recovery-summary.json`. Sao chép [mẫu evidence index](templates/evidence-index.example.md) thành `evidence/INDEX.md` của buổi chạy chính thức và điền đường dẫn raw evidence cho Tasks 1–5. Tạo một governance record cho **mỗi bucket** theo [mẫu governance](templates/governance.example.json); thay placeholder bằng mã sinh viên, người duyệt, người cleanup, ngày cleanup dự kiến và commit policy thực. Chạy `python3 -m json.tool recovery-summary.json` và `python3 -m json.tool governance.json` trước khi nộp. Không đưa access key, secret key, token, `private/` hay kubeconfig vào Git.

Ghi rõ giới hạn: một storage replica dùng cùng PVC trên cùng node chỉ chứng minh thay Pod có kiểm soát; chưa chứng minh HA, backup/restore, crash consistency, node-loss durability, TLS hay mã hóa lưu trữ. Quota giới hạn tài nguyên khai báo, không giới hạn byte bên trong S3.

Trên cluster cá nhân chỉ giữ evidence local để luyện tập. Buổi chạy chính thức cần chạy lại sau Task 4 trên cluster chung, cùng Pod/PVC/dữ liệu xuyên suốt Tasks 1–5, rồi bàn giao các file evidence không chứa credential. Mỗi thành viên ghi một thay đổi do mình viết, một kiểm tra độc lập và diễn giải vào `contribution.csv` của nhóm; có thể bắt đầu từ [mẫu contribution](templates/contribution.example.csv).
