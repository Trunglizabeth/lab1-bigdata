#!/bin/sh
# Đóng gói bundle nộp bài team-XX/ từ lần chạy chính thức.
#   TEAM=team-01 sh src/build_bundle.sh
# Chỉ sao chép; không chạy lệnh nào lên cluster. Dừng nếu thiếu file hoặc thấy dấu hiệu secret.
set -eu
TEAM="${TEAM:?đặt TEAM=team-XX}"
OUT="$TEAM"
[ -e "$OUT" ] && { echo "$OUT đã tồn tại; đổi tên/xóa trước khi đóng gói lại"; exit 1; }

missing=0
need() { for f in "$@"; do [ -e "$f" ] || { echo "THIẾU: $f"; missing=1; }; done; }
need submission/README.md policies-redacted.json governance.json security-results.csv \
     benchmark-summary.csv recovery-summary.json contribution.csv evidence/INDEX.md \
     manifests/guardrails-applied.yaml manifests/store-applied.yaml manifests/clients-applied.yaml \
     manifests/positive.yaml manifests/negative.yaml
for d in A B C D E; do
  ls individual/"$d"/* >/dev/null 2>&1 || { echo "THIẾU: individual/$d/ (kết quả cá nhân)"; missing=1; }
done
[ "$missing" = 0 ] || { echo "Chưa đủ file, chưa đóng gói."; exit 1; }

python3 -m json.tool governance.json >/dev/null
python3 -m json.tool recovery-summary.json >/dev/null
python3 -m json.tool policies-redacted.json >/dev/null

words=$(wc -w < submission/README.md)
[ "$words" -ge 300 ] && [ "$words" -le 500 ] || echo "CẢNH BÁO: README có $words từ (yêu cầu 300–500)"

mkdir -p "$OUT/manifests" "$OUT/evidence" "$OUT/individual"
cp submission/README.md "$OUT/README.md"
cp manifests/*-applied.yaml manifests/positive.yaml manifests/negative.yaml "$OUT/manifests/"
cp policies-redacted.json governance.json security-results.csv benchmark-summary.csv \
   recovery-summary.json contribution.csv "$OUT/"
# Raw evidence của lần chạy chính thức, giữ cả *-attempt*; bỏ thư mục luyện tập/reset.
for f in evidence/*; do
  case "$(basename "$f")" in _reset-*|_practice-*) continue ;; esac
  cp -R "$f" "$OUT/evidence/"
done
cp -R individual/. "$OUT/individual/"

echo "== Quét secret trong $OUT/"
leak=0
grep -rIl -E 'secretKey|accessKey|AWS_SECRET|AWS_ACCESS_KEY_ID=|"token"|BEGIN [A-Z ]*PRIVATE KEY|client-key-data|lab-[0-9a-f]{20}' "$OUT" && leak=1
# So khớp đúng giá trị key/secret đang có trong private/*.env (không in giá trị ra màn hình).
hits=$(for f in private/*.env; do
  [ -e "$f" ] || continue
  cut -d= -f2- "$f" | while read -r v; do
    [ -n "$v" ] && grep -rIlF -- "$v" "$OUT" | sed "s|\$|  (chứa giá trị trong $f)|"
  done
done)
[ -n "$hits" ] && { echo "$hits"; leak=1; }
[ "$leak" = 0 ] || { echo "DỪNG: có thể lộ credential. Kiểm tra, xóa $OUT rồi đóng gói lại."; exit 1; }
echo "sạch"

echo "== Kiểm tra số dòng"
python3 - "$OUT" <<'PY'
import csv, sys, os
d = sys.argv[1]
sec = list(csv.DictReader(open(os.path.join(d, "security-results.csv"))))
ids = {r["test_id"] for r in sec}
want = {f"S{i:02d}" for i in range(1, 13)} | {f"K{i:02d}" for i in range(1, 7)} | {f"N{i:02d}" for i in range(1, 5)}
print("security rows:", len(sec), "missing:", sorted(want - ids))
print("status:", {s: sum(r["status"] == s for r in sec) for s in {r["status"] for r in sec}})
print("reviewer PENDING:", [r["test_id"] for r in sec if r["reviewer"] in ("", "PENDING")])
bench = list(csv.DictReader(open(os.path.join(d, "benchmark-summary.csv"))))
print("benchmark rows:", len(bench), "(cần 12)")
PY
find "$OUT" -type f | sort > "$OUT/evidence/FILES.txt"
echo "Xong: $OUT/  ($(wc -l < "$OUT/evidence/FILES.txt") file)"
