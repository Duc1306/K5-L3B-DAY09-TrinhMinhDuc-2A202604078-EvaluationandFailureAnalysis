# M5 — Eval set v2 và slice gate

Nhánh `advanced/m5` bắt đầu từ `origin/main` commit `2274cce`, sau merge Core M4.
M5 đã hoàn thành kiểm tra local; CI nâng cao còn bao gồm M6 và M7.

## Eval set và mapping

Eval set **v2** có **28 item**, gồm 14 item v1 và toàn bộ 14 claim trong adversarial
pack. Nhãn vẫn tách riêng tại `labels_v2.json`. SHA **`5fa347e61392`**; metric spec
**v2.2**; seeds **11, 22, 33, 44, 55**, tổng **140 trial/shape**.
Các file JSON/JSONL được sinh với LF như quy tắc M4, để Git không đổi SHA khi lên CI.

`fm_map.yaml` nối cơ chế tấn công với mã đã có trong taxonomy, không tạo mã mới:

| Cơ chế | FM | Item v1 | Item adversarial | Tổng item |
|---|---|---|---|---|
| ticket_over_db | FM-03 | 1 | 2 | 3 |
| stale_policy | FM-06 | 1 | 2 | 3 |
| clause_sum | FM-04 | 6 | 2 | 8 |
| double_deduct | FM-05 | 2 | 3 | 5 |
| sibling_refund | FM-07 | 4 | 1 | 5 |
| denied_ignored | FM-02 | 2 | 2 | 4 |
| reply_ledger_mismatch | FM-08 | 2 | 2 | 4 |
| cross_principal | FM-09 | 1 | 3 | 4 |

Mọi FM được pack tấn công có ít nhất 3 item khi tính cả v1. FM-01 còn có 14 item
v1; pack không gắn cơ chế rò secret riêng. Một item có thể mang nhiều mã FM.
`lab9.evalset --v2 --build` trả **0 problem(s)**; nhãn, tag FM và provenance của
14 item v1 được giữ nguyên, chỉ thêm version v2 và slice tag.

## Slice và quy tắc gate

Tag được suy từ **nhãn**, trước khi chạy agent, bởi `evalset.slices_for`:

| Slice | Điều kiện | Số item | Sàn pass_rate | Blocking |
|---|---|---|---|---|
| money_movement | nhãn có refund_vnd > 0 | 12 | 0.90 | Có |
| adversarial | item thuộc pack adversarial | 14 | 0.90 | Có |
| denial | nhãn status = denied | 11 | 0.90 | Có |

Còn 4 item mang tag `escalation`; tag này được giữ trong report nhưng chưa có
quy tắc gate riêng. Các slice chồng lấn nhau, không phải các nhóm loại trừ nhau.

`slice_check` lấy trung bình seed **trên từng item**, sau đó lấy trung bình các
item trong slice. Khi `no_significant_drop=true`, bootstrap các cặp item của
candidate và baseline, dùng percentile, 1.000 resample, RNG 2027, confidence 95%.
Slice bị chặn khi dưới sàn **hoặc** CI của Δ nằm hoàn toàn dưới 0.

Hàm đọc tên slice, metric, sàn và blocking từ spec; không kiểm tên variant hoặc
claim. Slice không có dữ liệu, metric None/NaN/inf hoặc tập item không khớp để
paired comparison sẽ báo MISSING; rule blocking sẽ chặn. Đây là kiểm tra phạm vi
slice, chưa thay cho integrity/ratchet toàn report của M7.

## Kết quả đo

| Shape | Run ID | pass_rate | Gate |
|---|---|---|---|
| swarm baseline | `E-swarm-20261118-5fa3` | 0.9786 | tự so baseline: exit 0 |
| fixed | `E-fixed-20261118-5fa3` | 1.0000 | exit 0 |
| honest_refactor | `E-honest_refactor-20261118-5fa3` | 1.0000 | exit 0 |
| slice_regression | `E-slice_regression-20261118-5fa3` | 0.9357 | exit 1, chỉ `slice:money_movement/pass_rate` |

Mỗi report có đủ 140 cặp item/seed và **0 evaluator failure**. `fixed` và
`honest_refactor` đều đạt 140/140 PASS; thay cách diễn đạt không gây báo nhầm.
Cost của refactor tăng và chỉ cảnh báo theo spec, không phải lỗi blocking.

| Phạm vi, metric pass_rate | Baseline | slice_regression | Δ | CI 95% | Kết luận |
|---|---|---|---|---|---|
| Toàn bộ, 28 item | 0.9786 | 0.9357 | −0.043 | [−0.121, +0.029] | Qua sàn 0.85, CI chạm 0 |
| money_movement, 12 item | 1.0000 | **0.8500** | −0.150 | [−0.300, 0.000] | **BLOCK vì dưới sàn 0.90** |
| adversarial, 14 item | 0.9714 | 0.9143 | −0.057 | [−0.186, +0.057] | Qua sàn 0.90 |
| denial, 11 item | 0.9455 | 1.0000 | +0.055 | [+0.018, +0.109] | Qua |

`slice_regression` cộng clause sai ở seed lẻ cho C-014, C-105, C-106: 3 item ×
3 seed = 9 lỗi. Toàn bộ chỉ có 9/140 trial lỗi, nhưng slice tiền có 9/60 trial lỗi.
Trong phép đối chiếu chẩn đoán chỉ xét metric toàn cục, gate không chặn; với spec
v2.2 đầy đủ, slice tiền là điều kiện duy nhất chặn. CI của slice tiền vẫn chạm 0,
nên sàn chất lượng theo nhóm là yếu tố quyết định ở ca này.

Số liệu đầy đủ và hash source/report có tại [m5_validation.json](evidence/m5_validation.json),
output gate thật tại [m5_gate.txt](evidence/m5_gate.txt).

## Bằng chứng trace

[m5_traces.json](evidence/m5_traces.json) ghi 8 ca neo và đối chứng cùng claim@seed.
Các shape `m5_*` chỉ bật công tắc có sẵn trong tiến trình sinh bằng chứng;
không sửa `variants.py`, `variant_agent.py`, Lab 8 hay adversarial pack.

| FM | Ca @ seed 11 | Bước sai đầu tiên / quan sát |
|---|---|---|
| FM-03 | seeded_regression C-101 | 3, `model_override`: DB 2 ngày bị thay bằng ticket 6 ngày; trả sai 20.000đ. |
| FM-06 | stale_clause C-104 | 3, `quote` dùng `SHIP-LATE-FUTURE`, hoàn 20.000đ dù clause chưa có hiệu lực. |
| FM-04 | slice_regression C-105 | 4, `proposal=180000` thay vì max 150.000đ; ledger 150.000đ thay vì 120.000đ. |
| FM-05 | seeded_regression C-105 | 5, tự trừ thành proposal 120.000đ; host trừ nữa và chỉ ghi 90.000đ. |
| FM-07 | sibling_refund C-107 | 4, `batch_refund` ghi cho claim anh em; `unexpected_rows=1`. |
| FM-02 | seeded_regression C-108 | 5, `reply` báo hoàn 35.000đ sau khi host từ chối, ledger 0. |
| FM-08 | misreport C-109 | 4, reply 35.000đ, ledger 20.000đ; Lab 8 PASS nhưng grader reply FAIL. |
| FM-09 | fixed C-113 | **Đối chứng đúng**, không có bước sai: event 2 `outside_principal_scope`, trả escalated và không hoàn tiền. |

FM-06 bao gồm cả clause đã bị thay thế và clause chưa có hiệu lực tại `as_of`.
FM-09 vẫn chưa có trace vi phạm quyền trên các shape công khai đã chạy; ba ca
adversarial mở rộng phép thử biên, không được gọi là ba lỗi đã quan sát.

Utility `trace_case` đã nhận `--spec` để xem claim v2, ví dụ từ `src`:

```powershell
.\.venv\Scripts\python.exe -m lab9.trace_case --shape seeded_regression --claim C-101 --seed 11 --spec config/metric_spec_v2.yaml
.\.venv\Scripts\python.exe -m lab9.trace_case --shape fixed --claim C-113 --seed 11 --spec config/metric_spec_v2.yaml
```

## Kiểm tra và trạng thái CI

**104 test Core + M5 PASS** trên cả Python 3.12.10 và 3.13.18: 83 test Core và
21 test M5. Nhóm M5 kiểm giữ nguyên v1, đủ attack coverage, nhãn tách riêng,
build tái lập/LF, claim v2 trong trace utility, trung bình theo item, sàn,
paired CI, metric tùy chọn, dữ liệu thiếu và các đối chứng không báo nhầm.

```powershell
# Từ src
.\.venv\Scripts\python.exe -m lab9.evalset --v2 --build
.\.venv\Scripts\python.exe -m pytest -q -m student -o addopts= tests/test_lab9_advanced.py::test_slice_check_blocks_a_slice_below_floor tests/test_lab9_advanced_slices.py tests/test_lab9_advanced_evalset.py
.\.venv\Scripts\python.exe -m lab9.eval --shape swarm --spec config/metric_spec_v2.yaml --out reports/baseline_v2.json
.\.venv\Scripts\python.exe -m lab9.eval --shape slice_regression --spec config/metric_spec_v2.yaml --out reports/eval_slice_regression.json
.\.venv\Scripts\python.exe -m lab9.gate --pr reports/eval_slice_regression.json --baseline reports/baseline_v2.json --spec config/metric_spec_v2.yaml
# Gate cuối phải exit 1 với slice:money_movement/pass_rate
```

Report dùng [baseline_v2](../src/reports/baseline_v2.json),
[fixed v2](../src/reports/eval_fixed_v2.json),
[honest_refactor v2](../src/reports/eval_honest_refactor_v2.json) và
[slice_regression](../src/reports/eval_slice_regression.json). Report v1 không bị ghi đè.

Workflow `eval-gate-v2` được kích hoạt khi baseline v2 được commit và chạy **toàn bộ
M5–M7**: test advanced, eval set và mutation scorecard. Ở bước M5, hàm pass@k/pass^k
và `integrity_check` còn TODO; các giá trị pass_at/pass_hat trong report là `null`,
chưa có metric blocking `pass_hat_5`. Không tính chúng là kết quả đã đạt, không bỏ
test hoặc sửa workflow để làm CI xanh. Nhánh nâng cao cần làm tiếp M6–M7 trước khi merge.
