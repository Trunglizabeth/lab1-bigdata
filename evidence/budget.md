| | Storage | 4 client | Tổng | Quota |
|---|---|---|---|---|
| requests.cpu | 500m | 400m | 900m | 2 |
| limits.cpu | 1 | 2 | 3 | 4 |
| requests.memory | 512Mi | 512Mi | 1Gi | 2Gi |
| limits.memory | 1Gi | 2Gi | 3Gi | 4Gi |
| requests.storage | 4Gi | - | 4Gi | 8Gi |
| pods | 1 | 4 | 5 | 10 |

Quota team-budget giới hạn tổng tài nguyên được khai báo trong namespace. Storage cộng bốn client cần 900m CPU request, 3 CPU limit, 1Gi RAM request, 3Gi limit, một PVC 4Gi và 5 Pod, đều dưới trần. Phần dư cho phép tạo Pod probe tạm. Pod negative xin 3 CPU request, vượt trần 2 CPU nên bị admission từ chối trước khi tạo. Quota không phải phần cứng được đặt trước và không giới hạn byte trong S3.
