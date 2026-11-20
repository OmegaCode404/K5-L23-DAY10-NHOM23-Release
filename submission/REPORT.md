# Báo cáo nhóm <<XX>>

## 1. Số liệu luyện tập
- Seed luyện tập dùng trong báo cáo: `r23007`.
- F1 trên `r23007`: lỗi luật ≈ `1.0`; lỗi gán nhãn ≈ `0.2`; tổng ≈ `0.8`.
- Đã nộp 13 lỗi: 10 lỗi luật + 3 lỗi gán nhãn đã `confirmed` (`000000000632` `instance_merge`, `000000006723` `class_swap`, `000000012667` `bbox_drift`).
- Số lỗi luật trên `r23007`: 10 (`missing_image=2`, `wrong_hash=2`, `bbox_out_of_bounds=2`, `duplicate_box=1`, `scene_leak=1`, `guideline_mismatch=1`, `thing_overlap=1`).
- Candidates `r23007`: 112 trên 99 ảnh, 105 nhóm review; `class_swap=7`, `category_swap=7`, `bbox_drift=3`, `missing_box=1`, `instance_merge=94`. `class_swap` và `category_swap` là hai giả thuyết thay thế cho 7 bất đồng lớp.
- Lô sạch (`--no-faults`, seed 5): 0 lỗi luật; 25 candidates `instance_merge` trên 25 ảnh, cần xem ảnh để đo nhiễu tự nhiên.
- Review ảnh đã chạy cho toàn bộ 105 nhóm: `confirmed` 4 dòng (3 cặp lỗi), `rejected` phần lớn, còn 8 dòng `unresolved` (5 nhóm class_disagreement và ảnh `000000004134` thiếu file).
- Vì sao F1 lỗi gán nhãn chỉ ≈ `0.2`: 94/112 ứng viên là `instance_merge`, và hầu hết bị `rejected` khi mở ảnh. Recall thấp là do cách sinh ứng viên quá thô (box chồng nhau cùng lớp), không phải do bỏ sót lỗi luật. Điều này đúng nghĩa vụ "ứng viên khác lỗi".
- `instance_merge` chưa được kiểm chứng đầy đủ bằng mask: chỉ vet được bằng ảnh, và mask panoptic là bản đồ màu đơn sắc không có chú giải; các dòng `rejected` cho `instance_merge` là phán đoán thận trọng, cần kiểm lại bằng mask khi có thời gian.
- Đã đo candidates với cấu hình mặc định của `crosscheck.py`; ngưỡng `merge_max_box_iou=0.5`, `min_segment_pixels=64`, `min_segment_fraction=0.0005`. Chưa hiệu chỉnh lại sau review. Không đọc `_private`.

## 2. Vì sao báo hết ứng viên làm F1 giảm?
`errors.json` chấm theo cặp `(type, target)`. Báo ứng viên chưa được xem ảnh tạo false positive. Precision giảm, nên F1 giảm dù recall có thể tăng. Vì vậy chỉ đưa lỗi gán nhãn vào `errors.json` sau khi xem ảnh và ghi `confirmed` trong `review_log.csv`.

## 3. Quyết định và lineage
M2 mới xác nhận phần validator lỗi luật. Chưa đủ dữ liệu để kết luận QC v1, ghi HOLD, phát hành v2 hoặc đánh giá ảnh hưởng R-021. Nhóm phải hoàn tất cross-check, review, bàn giao và lineage ở các pha sau.

## 4. Hash chứng minh gì, không chứng minh gì?
Hash chứng minh bytes hiện tại của file khớp với hash đã ghi trong manifest. Hash giúp phát hiện file bị thay đổi hoặc sai bản giao. Hash không chứng minh nội dung ảnh đúng, nhãn đúng, chất lượng annotation, hay ảnh không có lỗi gán nhãn.

## 5. Truy vết
Chưa hoàn thành trong phần M2. Khi làm pha truy vết, `tier_a` và `tier_b` phải dùng ảnh có job guideline cũ và có box detection thuộc lớp bị đổi quy tắc. `guideline` phải lấy từ `jobs.csv`, không lấy từ metadata ảnh, vì metadata có thể chứa `guideline_mismatch`.

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
- Báo cáo này chỉ dùng `runs/r23007`; các thư mục `runs/r3007` và `runs/r3011` không dùng.
- `F1` lỗi gán nhãn ≈ `0.2` vì ứng viên `instance_merge` quá nhiều và phần lớn không phải lỗi khi mở ảnh.
- Lô sạch có 25 candidates `instance_merge`; đây là ứng viên lệch tự nhiên cần review, không tự động tính là lỗi.
- Ảnh `000000004134` không có trong delivery đã tải, nên nhóm đó để `unresolved`.
