# Judge audit

## Dữ liệu và quy ước

Backend **replay**, không gọi LLM hoặc cần API key. Mỗi CSV có 100 câu trả lời:
[tone](../src/data/eval/judge_tone_public.csv) và
[helpful](../src/data/eval/judge_helpful_public.csv).

**FAIL là lớp dương:** TP = người FAIL, judge FAIL; FP = người PASS, judge FAIL;
FN = người FAIL, judge PASS; TN = cả hai PASS. Precision đo độ đúng khi judge báo lỗi;
recall đo tỷ lệ lỗi thực sự mà judge tìm được.

Giữ nguyên CSV công khai để tính calibration. Audit dưới đây là nhận xét dựa trên
reply và metadata `note`/`human_failure` có sẵn; không giả định đã xem ticket hoặc
ledger riêng của các item H-/HL-. H-081 được ghi riêng vì note nghi ngờ nhãn người.

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Có, đạt cả 3 | Dùng cho tiêu chí tone trong phạm vi đã calibration; tiếp tục lấy mẫu người kiểm tra. |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không: κ và recall dưới sàn | Loại khỏi gate; chưa dùng để quyết định chất lượng agent. |

| Tiêu chí | TP | FP | FN | TN | Accuracy | Lỗi bị bỏ sót |
|---|---|---|---|---|---|---|
| tone_ok | 24 | 4 | 6 | 66 | 90/100 = 90% | 6/30 = 20% |
| helpful | 9 | 0 | 21 | 70 | 79/100 = 79% | 21/30 = 70% |

`helpful` có precision 1.0 vì cả 9 lần báo FAIL đều đúng theo nhãn, nhưng cho qua
21/30 câu có lỗi. Trong 21 FN, metadata ghi 18 ca sai tiền và 3 ca sai xưng hô.
Precision cao không bù được recall 0.3 hoặc κ 0.375; accuracy 79% cũng không đủ
để dùng làm gate khi 70% mẫu vốn là PASS.

## Công thức và Rogan–Gladen

- `P = TP / (TP + FP)`, `R = TP / (TP + FN)`; mẫu số bằng 0 trả 0.0.
- `p_o = (TP + TN) / n`; `p_e` là xác suất hai bên đồng ý do ngẫu nhiên theo tỷ lệ nhãn biên.
- `κ = (p_o - p_e) / (1 - p_e)`. Khi không có mẫu hoặc `p_e = 1`, κ không xác định;
  calibration phải FAIL, không được mặc định thành 1. Judge hằng trên nhãn người
  hỗn hợp có κ = 0, cũng không đạt sàn.
- `sensitivity = R`, `specificity = TN / (TN + FP)`.
- `p_corrected = (p_observed + specificity - 1) / (sensitivity + specificity - 1)`,
  chặn kết quả về [0, 1]. Mẫu số bằng 0 không cho ước lượng xác định.

| Judge | Tỷ lệ FAIL judge quan sát | Sensitivity | Specificity | FAIL sau Rogan–Gladen | FAIL theo nhãn người |
|---|---|---|---|---|---|
| tone_ok | 28/100 = 0.280 | 24/30 = 0.800 | 66/70 ≈ 0.943 | 0.300 | 30/100 = 0.300 |
| helpful | 9/100 = 0.090 | 9/30 = 0.300 | 70/70 = 1.000 | 0.300 | 30/100 = 0.300 |

Các hệ số được ước lượng trên chính tập đang hiệu chỉnh, nên việc thu lại tỷ lệ
30% không phải một kiểm chứng độc lập. Rogan–Gladen chỉ hiệu chỉnh tỷ lệ lỗi chung,
không sửa nhãn từng item và không giúp `helpful` đạt calibration. Khi áp dụng cho
dữ liệu mới, phải kiểm tra khả năng chuyển giao của sensitivity/specificity;
recall thấp làm ước lượng nhạy với sai số của các hệ số.

## Audit 11 ca bất đồng

Loại FP/FN trong bảng tính theo nhãn gốc, kể cả khi audit đề nghị xem lại nhãn.
“Người đúng” ở các ca có note ledger nghĩa là phù hợp với bằng chứng được ghi trong
CSV, chưa phải xác minh độc lập với DB.

| # | Case | Judge nói | Người nói | Ai đúng? | Bằng chứng và hành động sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008, tone, FN | PASS | FAIL | Người, theo chuẩn xưng hô trong note. | “Em ... rồi nha, anh check giúp em” bị đánh đồng với thân thiện. Thêm ví dụ FAIL về giọng suồng sã và chuẩn xưng hô theo phân khúc khách của LogiX. |
| 2 | H-029, tone, FN | PASS | FAIL | Người. | Có “Dạ, vui lòng” nhưng kết thúc “không cần nhắn thêm”. Chấm toàn câu; lời mở đầu lịch sự không được che phần ra lệnh/gạt yêu cầu của khách. |
| 3 | H-042, tone, FP | FAIL | PASS | Người. | Reply ngắn nhưng nêu đơn, số tiền và thời gian nhận tiền. Không bắt buộc câu xin lỗi trong mọi câu trả lời, không phạt chỉ vì ngắn. |
| 4 | H-051, tone, FP | FAIL | PASS | Người, theo danh sách từ được phép trong note. | “refund” được CS LogiX chấp nhận. Thêm glossary được duyệt; không đánh FAIL chỉ vì có thuật ngữ tiếng Anh. |
| 5 | H-063, tone, FN | PASS | FAIL | Người, theo note về cam kết vượt kết quả hệ thống. | Câu “sẽ hoàn thêm” là cam kết chưa có căn cứ. Rubric cần cấm hứa thêm ngoài trạng thái được xác nhận; số tiền và quyền hoàn vẫn chuyển cho grader code, không suy từ lời lịch sự. |
| 6 | H-081, tone, FP theo nhãn gốc | FAIL | PASS | Note cho rằng judge đúng; cần người thứ hai xác minh. | Note ghi người gán nhãn đọc nhầm ticket, nhưng CSV không có ticket để kiểm độc lập. Mở adjudication với ticket/expected, phân biệt tone với tính đúng chính sách; chỉ sửa nhãn trong bộ calibration có version mới sau xác nhận, giữ CSV công khai nguyên trạng. |
| 7 | H-088, tone, FP | FAIL | PASS | Người. | Lặp “Dạ, dạ” là lỗi gõ nhẹ. Rubric cần ngưỡng lỗi làm giảm tính chuyên nghiệp, không biến mọi lỗi gõ nhỏ thành FAIL. |
| 8 | HL-015, helpful, FN | PASS | FAIL | Người, theo note ledger. | Reply báo 55.000đ nhưng note ghi ledger 40.000đ. Thêm tiêu chí grounding bắt buộc; chuyển so sánh số tiền sang code để bắt FM-08. |
| 9 | HL-016, helpful, FN | PASS | FAIL | Người, theo note ledger. | Xin lỗi dài và lịch sự nhưng báo 55.000đ thay vì 35.000đ. Chấm hoàn thành tác vụ/tính đúng trước phong cách; thêm cặp ví dụ cùng lời xin lỗi nhưng kết quả đúng và sai. |
| 10 | HL-020, helpful, FN | PASS | FAIL | Người, theo note ledger. | Câu trả lời ngắn vẫn báo sai 90.000đ thay vì 120.000đ. Tiêu chí grounding phải áp dụng cho mọi độ dài; không quy toàn bộ lỗi judge cho độ dài câu trả lời. |
| 11 | HL-047, helpful, FN | PASS | FAIL | Người, theo `human_failure` về xưng hô. | “Ok bạn ... xử lý rồi nhé” vừa suồng sã vừa không nêu rõ kết quả. Chấm rõ hành động/kết quả hoặc thông tin cần bổ sung; giữ kiểm tra tone riêng để chỉ ra nguyên nhân. |

Đây là đề xuất sửa rubric cho lần đánh giá kế tiếp. Replay chỉ chứa verdict cố định,
nên chỉnh hướng dẫn trong audit chưa thể thay đổi các số đo hiện tại; cần judge chạy
theo rubric mới trên tập nhãn mới để chứng minh cải thiện.

## Kết luận

- **Giữ `tone_ok` trong phạm vi tone:** κ ≈ 0.757, P ≈ 0.857, R = 0.8 đều đạt sàn,
  nhưng vẫn có 4 FP và 6 FN. Không suy từ tone PASS rằng số tiền/approval đúng.
- **Loại `helpful` khỏi gate:** 21 FN so với chỉ 9 TP; bỏ sót 70% ca lỗi,
  κ = 0.375 và R = 0.3 đều FAIL. Không hạ sàn hoặc dùng kết quả hiệu chỉnh 30%
  để hợp thức hóa judge này. Tiền và approval luôn dùng code grader.
- **Nhãn người cũng cần audit:** H-081 cho thấy phải có adjudication; công bố số liệu
  trên nhãn gốc và phiên bản đã adjudicate riêng, tránh âm thầm thay dữ liệu để tăng điểm.
- **Giới hạn:** cả hai chỉ được kiểm trên 100 mẫu replay công khai, chưa có held-out mới
  hoặc khoảng tin cậy cho calibration. Mẫu tiền trong note không được kiểm độc lập với DB.
  Bước tiếp theo là rubric có version, nhãn từ ít nhất hai người trên dữ liệu mới,
  adjudicate bất đồng, rồi calibration lại trước khi dùng cho dữ liệu sản xuất.

## Tái lập

Chạy từ `src` với môi trường đã cài ở M0:

```powershell
.\.venv\Scripts\python.exe -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5
# PASS floors, exit 0
.\.venv\Scripts\python.exe -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5
# FAIL floors, exit 1: đây là kết quả đúng cho judge bị loại
.\.venv\Scripts\python.exe -m pytest -q -m student -o addopts= tests/test_lab9_stats.py tests/test_lab9_judge.py -k "not paired_bootstrap"
```

Phần kiểm tra M2 gồm confusion, P/R, κ, Rogan–Gladen và các quyết định calibration.
Hai test `paired_bootstrap` thuộc M4 nên chưa nằm trong lần chạy này.
Ngưỡng được so với số chưa làm tròn; làm tròn 3 chữ số chỉ để hiển thị. κ không xác
định sẽ FAIL; Rogan–Gladen không xác định hiển thị `nan`; CSV rỗng hoặc nhãn không
hợp lệ trả FAIL với lý do thay vì tạo ra kết quả calibration hợp lệ.
