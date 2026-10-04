"""Task 2 — tạo 3 S3 identity theo vai trò (Phụ lục B1).

Chạy MỘT lần từ thư mục gốc repo:  python3 src/make_identities.py
Sinh ra:
  private/s3.json            -> Secret s3-config (cấu hình server, chứa key)
  private/{owner,ingestor,analyst}.env -> Secret s3-<role> (credentials từng client)
  policies-redacted.json     -> chỉ gồm action, KHÔNG có key (được nộp)
Đây là action theo bucket của SeaweedFS, không phải AWS IAM JSON policy.
Write cho phép sửa và xóa, nên bucket raw không immutable.
"""
import json, os, secrets
from pathlib import Path

root = Path("private")
root.mkdir(exist_ok=True, mode=0o700)
if (root / "s3.json").exists():
    raise SystemExit("private/s3.json đã tồn tại — không tạo lại key (sẽ lệch với Secret đang chạy).")

policies = {
    "owner": ["Admin", "Read", "Write", "List"],
    "ingestor": ["Read:research-raw", "Write:research-raw",
                 "List:research-raw"],
    "analyst": ["Read:research-release", "List:research-release"],
}
identities = []
for name, actions in policies.items():
    key = "lab-" + secrets.token_hex(10)
    secret = secrets.token_urlsafe(32)
    identities.append({"name": name, "actions": actions,
                       "credentials": [{"accessKey": key, "secretKey": secret}]})
    path = root / (name + ".env")
    path.write_text("AWS_ACCESS_KEY_ID=" + key + "\n" +
                    "AWS_SECRET_ACCESS_KEY=" + secret + "\n")
    os.chmod(path, 0o600)
path = root / "s3.json"
path.write_text(json.dumps({"identities": identities}, indent=2))
os.chmod(path, 0o600)
Path("policies-redacted.json").write_text(json.dumps(policies, indent=2))
print("OK: private/s3.json, private/{owner,ingestor,analyst}.env, policies-redacted.json")
