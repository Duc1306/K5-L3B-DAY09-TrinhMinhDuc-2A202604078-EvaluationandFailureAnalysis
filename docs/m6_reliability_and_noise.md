# M6 — Nhiễu A/A và độ ổn định qua nhiều trial

M6 được thực hiện trên `advanced/m5`, tiếp nối commit M5 `8e17653`.
Eval set vẫn là v2 SHA **`5fa347e61392`**, 28 item × 5 seed; spec tăng từ v2.2
lên **v2.3** khi thêm metric blocking `pass_hat_5`. M7 chưa được cài.

## Ước lượng pass@k và pass^k

Với n trial, trong đó c trial PASS, chọn k trial không hoàn lại:

```text
pass@k = 1 - C(n-c, k) / C(n, k)    # ít nhất một trial PASS
pass^k = C(c, k) / C(n, k)          # tất cả k trial PASS
pass^k <= c/n <= pass@k
```

`stats.pass_at_k` và `stats.pass_hat_k` dùng tổ hợp số nguyên. Hiệu của các tổ hợp
được tính trước khi chia, tránh mất xác suất nhỏ do phép trừ hai số float gần 1.
Test `n=10^18, c=1, k=1` vẫn cho 1e-18. Điều kiện hợp lệ: n, c, k là số nguyên,
không phải bool; n ≥ 1, 0 ≤ c ≤ n, 1 ≤ k ≤ n. Tham số sai trả `ValueError`.

Ví dụ n=5, c=4: pass@3 = 1, nhưng pass^3 = 0.4; pass@5 = 1, pass^5 = 0.
“Tìm được một lần đúng” khác với việc agent đúng ổn định trong cả k lần.
Không thay ước lượng tổ hợp bằng `(c/n)^k`.

`eval.aggregate` tính từng ước lượng trên mỗi item rồi lấy trung bình các item.
Đây là metric tổng hợp từ các dòng `pass_rate`, không phải grader bool của một
case đơn lẻ. Vì vậy `pass_hat_5` không được giả lập thành field trên từng row và
không bật `no_significant_drop` của gate theo row cho metric này. Nếu số trial
của item ít hơn k thì ước lượng không xác định và vẫn là `null`.

## A/A trước khi đặt sàn

Cùng agent `swarm`, cùng 28 item và nhãn, chạy hai bộ seed:

- Bộ chuẩn: **11, 22, 33, 44, 55**.
- Bộ đối chiếu: **66, 77, 88, 99, 110**.

Lệnh `lab9.mutation --aa` đã chạy khi estimator được cài và spec còn v2.2, trước
khi thêm sàn blocking. [Output thật](evidence/m6_aa.txt) và
[số liệu A/A](evidence/m6_aa.json) ghi đủ các metric; mọi Δ quan sát đều bằng **0**.

| Metric | Bộ chuẩn | Bộ đối chiếu | Δ |
|---|---|---|---|
| pass_rate / pass@1 / pass^1 | 0.9786 | 0.9786 | 0.0000 |
| pass@3 | 1.0000 | 1.0000 | 0.0000 |
| pass^3 | 0.9357 | 0.9357 | 0.0000 |
| pass@5 | 1.0000 | 1.0000 | 0.0000 |
| pass^5 | 0.8929 | 0.8929 | 0.0000 |

Chọn **sàn pass_hat_5 = 0.80**, blocking, đạt mức tối thiểu của rubric. Hai lần A/A
cùng cho 0.8929, nên sàn thấp hơn mức chuẩn 0.0929, lớn hơn biến động metric quan
sát bằng 0. Không đặt sàn sát mức chuẩn khi chỉ có hai bộ seed.

Đây là khoảng biến động quan sát trên **hai phép đo MockLLM**, không phải một CI
nhiễu đã được ước lượng trên nhiều lần chạy độc lập. Với LLM thật, output/judge
có thể thay đổi giữa các lần gọi và seed; cần thêm A/A lặp lại, nhãn mới và tập
held-out để chọn biên sàn ngoài dải nhiễu thực tế. A/A hiện tại không chứng minh
nhiễu bằng 0 trên model thật hoặc trên mọi bộ seed.

## Report mới và gate

Baseline và năm variant được chạy lại bằng script với spec v2.3. Tất cả report có
đủ **140 cặp item/seed**, không evaluator failure, không còn `null` ở các metric
pass@k/pass^k với k=1,3,5. Report v1 được giữ nguyên.

| Shape | pass_rate | pass@5 | pass^3 | pass^5 | Gate |
|---|---|---|---|---|---|
| swarm | 0.9786 | 1.0000 | 0.9357 | 0.8929 | 0 khi tự so baseline |
| fixed | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 |
| honest_refactor | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 |
| seeded_regression | 0.6429 | 0.6429 | 0.6429 | 0.6429 | 1 |
| slice_regression | 0.9357 | 1.0000 | 0.8929 | 0.8929 | 1, slice tiền |
| flaky_regression | 0.9143 | 1.0000 | 0.7429 | **0.5714** | **1, có pass_hat_5** |

Trên `flaky_regression`, 12 item chỉ PASS 4/5 trial và 16 item PASS đủ 5/5;
12 trial lỗi đều ở seed 33 trong bộ seed chuẩn. Mean 0.9143 vẫn trên sàn 0.85,
pass@5 bằng 1.0, nhưng chỉ 16/28 item đúng ổn định cả năm lần.

Trên dataset này, **pass_rate paired CI và slice tiền cũng chặn flaky**:
Δ pass_rate = −0.064, CI [−0.114, −0.014]. Không tuyên bố chỉ có metric mới bắt
được variant công khai. Một test độc lập dùng 3 item với số PASS `[4,4,5]` chứng
minh trường hợp khác: mean 0.8667 qua sàn 0.85, paired CI chạm 0, nhưng pass^5
bằng 0.3333 và chỉ `pass_hat_5` chặn. Đây là vai trò bổ sung của kiểm tra độ ổn định.

Mutation chạy lại qua entry point gốc đã đạt **3/3 regression bị chặn, 0 báo nhầm**.
[Mutation log](evidence/m6_mutation.txt), [gate log](evidence/m6_gate.txt) và
[report/hash đầy đủ](evidence/m6_validation.json) ghi kết quả thật. Không sửa
variant, trap, Lab 8, nhãn, bộ seed hay ngưỡng cũ để đạt phép kiểm tra.

Các report hiện hành: [baseline_v2](../src/reports/baseline_v2.json),
[fixed](../src/reports/eval_fixed_v2.json),
[honest_refactor](../src/reports/eval_honest_refactor_v2.json),
[seeded_regression](../src/reports/eval_seeded_regression_v2.json),
[slice_regression](../src/reports/eval_slice_regression.json),
[flaky_regression](../src/reports/eval_flaky_regression_v2.json).
Run ID vẫn theo shape/ngày/eval-set SHA nên có thể giống snapshot M5; dùng
`metric_spec_version=2.3` và hash report để phân biệt hai mốc. Báo cáo M5 đã liên
kết tới commit M5 cố định, không dùng report đang được M6 sinh lại để xác minh hash cũ.

## Kiểm tra và phần còn lại

- **131 test Core + M5 + M6 PASS** trên Python 3.12.10 và 3.13.18.
- Test mới so estimator với phép liệt kê mọi tổ hợp ở n nhỏ, kiểm miền tham số,
  xác suất nhỏ, NumPy integer, aggregation theo item và metric gate tổng hợp.
- Chạy đúng toàn bộ `-k advanced`: **48 passed, 2 failed**. Hai lỗi còn lại chính
  là `test_integrity_flags_nan_and_dropped_rows` và `test_integrity_flags_loosened_spec`,
  thuộc M7. [Log đầy đủ](evidence/m6_tests.txt), [kết quả](evidence/m6_test_results.json).
- Mutation 3/3 trên report trung thực chưa chứng minh chặn report bị làm đẹp.
  `integrity_check`/ratchet và trap thuộc M7 chưa được cài, nên CI v2 vẫn chưa xanh.

Không hạ sàn để cố bắt một bug hiếm 1/3 seed. Năm seed cố định chưa đủ để tuyên bố
phát hiện ổn định mọi lỗi hiếm hoặc ước lượng đúng tần suất lỗi trong production.

## Tái lập

Từ `src`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -m student -o addopts= -k "lab9 and not integrity"
.\.venv\Scripts\python.exe -m lab9.mutation --spec config/metric_spec_v2.yaml --aa 66,77,88,99,110
.\.venv\Scripts\python.exe -m lab9.eval --shape swarm --spec config/metric_spec_v2.yaml --out reports/baseline_v2.json
.\.venv\Scripts\python.exe -m lab9.eval --shape flaky_regression --spec config/metric_spec_v2.yaml --out reports/eval_flaky_regression_v2.json
.\.venv\Scripts\python.exe -m lab9.gate --pr reports/eval_flaky_regression_v2.json --baseline reports/baseline_v2.json --spec config/metric_spec_v2.yaml
# Gate phải exit 1 và nêu pass_hat_5 trong danh sách chặn
.\.venv\Scripts\python.exe -m lab9.mutation --spec config/metric_spec_v2.yaml --baseline reports/baseline_v2.json
# mutation score 3/3, false alarms 0; chưa phải phép kiểm trap M7
```
