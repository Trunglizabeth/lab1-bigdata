#!/bin/sh
# Đưa namespace về trạng thái ngay trước Task 2 (giữ nguyên Task 1).
# CHỈ dùng trên cluster luyện tập. KHÔNG chạy trong buổi chạy chính thức (xóa PVC = mất dữ liệu).
#
#   sh src/reset_task2.sh             # xóa tài nguyên Task 2, giữ key trong private/ để dùng lại
#   sh src/reset_task2.sh --new-keys  # như trên + cất key cũ, lần sau make_identities.py tạo key mới
set -eu
: "${NS:?chưa source env.sh}"

echo "Context: $(kubectl config current-context)  Namespace: $NS"
printf 'Gõ "reset" để xóa Pod/PVC/Secret của Task 2: '
read -r ans
[ "$ans" = reset ] || { echo "Hủy."; exit 1; }

TS=$(date -u +%Y%m%dT%H%M%SZ)

echo "== 1. Client Pod"
kubectl -n "$NS" delete pod owner ingestor analyst blocked --ignore-not-found --wait=true

echo "== 2. Storage (Deployment, Service, rồi PVC)"
kubectl -n "$NS" delete deployment objects --ignore-not-found --wait=true
kubectl -n "$NS" wait --for=delete pod -l app=objects --timeout=120s 2>/dev/null || true
kubectl -n "$NS" delete service objects --ignore-not-found
kubectl -n "$NS" delete pvc object-data --ignore-not-found --wait=true

echo "== 3. Secret"
kubectl -n "$NS" delete secret s3-config s3-owner s3-ingestor s3-analyst --ignore-not-found

echo "== 4. File local của Task 2 -> evidence/_reset-$TS/ (không xóa, để giữ lần chạy cũ)"
OLD="evidence/_reset-$TS"
mkdir -p "$OLD"
for f in evidence/seed.jsonl evidence/topology.txt evidence/T2-* \
         manifests/store-applied.yaml policies-redacted.json; do
  [ -e "$f" ] && mv "$f" "$OLD/" && echo "  moved $f"
done
rmdir "$OLD" 2>/dev/null && echo "  (không có file nào)" || true

if [ "${1:-}" = "--new-keys" ]; then
  echo "== 5. Cất key cũ -> private/old-$TS/"
  mkdir -p "private/old-$TS"
  for f in private/s3.json private/owner.env private/ingestor.env private/analyst.env; do
    [ -e "$f" ] && mv "$f" "private/old-$TS/"
  done
  chmod -R go-rwx private
fi

echo "== Xong. Trạng thái hiện tại:"
kubectl -n "$NS" get pod,pvc,secret
