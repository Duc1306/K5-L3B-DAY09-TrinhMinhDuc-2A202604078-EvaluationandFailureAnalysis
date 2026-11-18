# M7 — Tính toàn vẹn của bằng chứng và ratchet

Hoàn thành local ngày 2026-11-18 trên `advanced/m5`, tiếp nối commit M6
`0f7d7aa6a9ffb21552644bf7fa732882463a3b23`. Eval set v2 vẫn là
`5fa347e61392`, 28 item × 5 seed; metric spec giữ nguyên **v2.3** và các ngưỡng M6.
Thay đổi nằm ở gate, kiểm tra regression và bằng chứng chạy lại.

## Gate kiểm tra gì

`integrity_check` chạy trước khi gate xét ngưỡng, áp dụng cho cả PR và baseline:

- Manifest phải có số item hợp lệ, seed nguyên không trùng, đủ mọi cặp item/seed.
  Kiểm tra riêng dòng trùng để bắt trường hợp thay một dòng lỗi bằng dòng tốt
  nhưng giữ nguyên tổng số dòng. Tập cặp PR phải trùng baseline.
- `evaluator_failures` phải rỗng; mọi grader cần thiết phải có kết quả hữu hạn
  ở từng dòng. Grader nhị phân không nhận giá trị ngoài 0/1. Không bỏ `None`
  khỏi mẫu rồi dùng điểm trung bình còn lại để cho qua.
- Metric tổng hợp không được là NaN/Infinity hoặc chuỗi. Gate dùng lại hàm
  `aggregate` của harness để đối chiếu điểm từ các dòng, gồm số vi phạm safety,
  pass@k/pass^k và cost/success. Vì vậy sửa riêng điểm tổng hợp hữu hạn cũng bị chặn.
- `pass_hat_5` là metric tổng hợp, không bắt buộc có trường này trong từng dòng.
  `null` chỉ hợp lệ khi phép tính thực sự không xác định, ví dụ cost/success
  khi không có trial PASS; metric blocking thiếu giá trị vẫn không được qua gate.
- Tag slice phải nhất quán giữa các seed và khớp baseline. Đổi thứ tự dòng,
  seed hoặc tag không làm thay đổi quyết định.

Khi cung cấp `--base-spec`, ratchet so sánh các rule theo ID metric và cặp
`(name, metric)` của slice trên cùng `eval_set_version`: không hạ/bỏ `min`,
không tăng/bỏ `max` hoặc `max_increase`, không tắt blocking, bỏ metric/slice,
bỏ paired CI hoặc thay nghĩa grader/kind/level. Rule trùng và ngưỡng NaN cũng
bị từ chối rõ ràng. Ngưỡng chặt hơn và thứ tự rule khác vẫn hợp lệ.

## Bằng chứng kiểm tra

- **194 test Lab 9 PASS** trên Python **3.12.10** và **3.13.18**.
  Lệnh advanced đúng theo workflow có **111 passed** trên Python 3.13.18.
  Trong đó 61 test M7 bổ sung kiểm dòng trùng, evaluator failure trên run xanh,
  summary giả, seed/item/slice bị đổi và từng cách nới/bỏ rule.
- Test bootstrap bổ sung từ M4 được điền đủ metadata manifest/evaluator để
  fixture tuân theo schema report; giữ nguyên dữ liệu và quyết định CI cần kiểm.
- Smoke và kiểm eval set v1/v2 đều exit 0. Đã chạy fresh Core swarm/fixed/seeded,
  gate và `ci_check` theo luồng workflow. Fresh swarm v2 khớp metric baseline M6.
- Không sửa Lab 8, variant, trap hoặc test công khai để đạt kết quả.

[Log test](evidence/m7_tests.txt), [kết quả test](evidence/m7_test_results.json),
[smoke/eval/ci_check](evidence/m7_checks.txt), [gate](evidence/m7_gate.txt) và
[hash source/report cùng từng lệnh](evidence/m7_validation.json).

| Candidate v2 | Gate exit | Lý do chặn chính |
|---|---|---|
| baseline so với chính nó; fresh swarm | 0 | đủ bằng chứng, đạt ngưỡng |
| fixed | 0 | đủ bằng chứng, đạt ngưỡng |
| honest_refactor | 0 | thêm tool call chỉ tạo cảnh báo cost không blocking |
| seeded_regression | 1 | pass_rate, tiền, reply, reliability và slice |
| slice_regression | 1 | chỉ `slice:money_movement/pass_rate` |
| flaky_regression | 1 | `pass_rate`, `pass_hat_5`, slice tiền |

Mutation chạy fresh qua entry point gốc:

```text
fixed                expect merge got merge ok
honest_refactor      expect merge got merge ok
seeded_regression    expect block got block ok
slice_regression     expect block got block ok
flaky_regression     expect block got block ok
mutation score 3/3 · false alarms 0
```

[Log mutation đầy đủ](evidence/m7_mutation.txt) có cả các metric chặn từng variant.

## Bốn trap và nội dung dùng trong PR

Đã sinh lại `eval_slice_regression.json` bằng Python 3.13.18, sau đó chạy
`lab9.traps` nguyên bản. Report mới chỉ khác snapshot M6 ở metadata phiên bản
Python; các dòng và metric không đổi. Bốn report lỗi và spec nới ngưỡng trong
`src/reports/traps/` đều do script tạo.

| Trap | Gate exit | Lý do |
|---|---|---|
| evaluator_errors_as_nan | 1 | grader ở dòng bị thiếu/None |
| dropped_failing_rows | 1 | thiếu dòng/cặp item-seed |
| cherry_picked_seeds | 1 | tập cặp item-seed khác baseline |
| loosened_spec | 1 | ratchet phát hiện hạ sàn, bỏ CI và slice |

Đã gọi CLI gate riêng trên từng trap, xác nhận không có traceback. Bốn dòng
kết luận thực tế dưới đây được giữ trong [log trap](evidence/m7_traps.txt),
kèm lệnh và toàn bộ lý do INTEGRITY:

```text
# evaluator_errors_as_nan.json
exit 1 — blocked: integrity
# dropped_failing_rows.json
exit 1 — blocked: integrity
# cherry_picked_seeds.json
exit 1 — blocked: integrity
# loosened_spec.json (có --base-spec)
exit 1 — blocked: integrity
```

Lệnh tổng `lab9.traps` trả **exit 0** vì cả bốn trap bị chặn; mỗi lần gọi gate
trên report lỗi trả **exit 1**. Có thể đưa bảng mutation, bốn dòng này và output
[A/A M6](evidence/m6_aa.txt) vào mô tả PR. A/A M6 có mọi Δ = 0, pass_hat_5 hai
bộ seed đều 0.8929, sàn blocking 0.80; M7 không sửa estimator, eval hoặc spec.

## Tái lập từ src

```powershell
.\.venv\Scripts\python.exe -m pytest -q -m student -o addopts= -k lab9
.\.venv\Scripts\python.exe -m pytest -q -m student -o addopts= -k advanced
.\.venv\Scripts\python.exe -m lab9.evalset --v2
.\.venv\Scripts\python.exe -m lab9.mutation --spec config/metric_spec_v2.yaml --baseline reports/baseline_v2.json --base-spec config/metric_spec_v2.yaml
.\.venv\Scripts\python.exe -m lab9.eval --shape slice_regression --spec config/metric_spec_v2.yaml --out reports/eval_slice_regression.json
.\.venv\Scripts\python.exe -m lab9.traps --pr reports/eval_slice_regression.json --baseline reports/baseline_v2.json --spec config/metric_spec_v2.yaml
```

Để chạy riêng trap nới ngưỡng:

```powershell
.\.venv\Scripts\python.exe -m lab9.gate --pr reports/traps/loosened_spec.json --baseline reports/baseline_v2.json --spec reports/traps/loosened_spec.spec.yaml --base-spec config/metric_spec_v2.yaml
# Mong đợi exit 1, các dòng INTEGRITY ratchet
```

## Phạm vi bảo đảm và bước nộp

Ratchet cần **spec tham chiếu đáng tin** qua `--base-spec`. Trong bài kiểm trap,
đó là spec gốc trước khi bị nới. Workflow bài lab hiện không tự lấy spec đã
review từ `main`; cần bảo vệ baseline, spec, dataset và code gate khi vận hành.
Kiểm tra nhất quán không xác thực được trường hợp mọi bằng chứng bị làm giả
đồng bộ, gồm cả baseline. Không tuyên bố đã chạy bộ chấm ẩn của giảng viên.

Giới hạn MockLLM, judge replay, số item nhỏ và lỗi hiếm 1/3 seed với 5 seed ở
eval card vẫn áp dụng. Không nới sàn để cố bắt một mẫu lỗi hiếm.

**M5–M7 đã hoàn tất kiểm tra local.** Chưa quan sát GitHub Actions của commit
M7. Commit code, tài liệu và report/trap đã stage, push `advanced/m5`, mở PR
vào `main` trong fork `Duc1306`, đợi cả `eval-gate` và `eval-gate-v2` xanh rồi
merge để người chấm thấy bài hoàn chỉnh trên `main`.
