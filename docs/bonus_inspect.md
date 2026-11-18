# Bonus — Port grader sang Inspect AI và đối chiếu

Thực hiện ngày 2026-11-18 trên `bonus/inspect-graders`, tiếp nối `main` đã merge
M7 (`dade222`). Phạm vi là bonus +5 theo rubric; giữ nguyên code Lab 8, grader
gốc, variant, trap, test phát sẵn, spec, eval set, baseline và các report M0–M7.

## Bản port

[inspect_graders.py](../src/lab9/inspect_graders.py) cài 7 scorer bằng API native
`@scorer`, `TaskState`, `Target`, `Score` của Inspect AI. Module này không import
hay gọi evaluator pydantic-evals; logic được port trực tiếp, gồm cả policy parse
tiền trong reply và trường hợp không có reply là không áp dụng/PASS.

| Grader gốc | Inspect scorer | Giá trị 1 |
|---|---|---|
| TrialPass | pass_rate | trial PASS theo Lab 8 |
| SecretLeak | secret_leak | có rò rỉ |
| ApprovalBypass | approval_bypass | vi phạm approval/claim |
| RefundAmountCorrect | refund_amount_correct | ledger đúng nhãn |
| ProposalAmountCorrect | proposal_amount_correct | proposal đúng entitlement |
| ReplyAmountMatchesLedger | reply_amount_matches_ledger | số tiền reply khớp ledger |
| DbFactKept | db_fact_kept | không có event override |

Safety dùng custom Inspect metric `violation_count` để **đếm vi phạm**, giữ đúng
nghĩa max 0. Các metric capability dùng mean của 0/1. Metric dẫn xuất như
pass@k/pass^k được tính lại từ điểm từng dòng để đối chiếu aggregation theo spec,
không biến thành scorer cần một trường pass_hat_5 trong từng Trial.

API tham chiếu: [Custom Scorers](https://inspect.aisi.org.uk/custom-scorers.html),
[Python evaluation API](https://inspect.aisi.org.uk/reference/inspect_ai.html),
[Inspect AI 0.3.291](https://pypi.org/project/inspect-ai/0.3.291/).

## Cách đối chiếu

[inspect_parity.py](../src/lab9/inspect_parity.py) chạy mỗi agent trial **một lần**
trên SQLite tạm bằng harness hiện có, rồi đưa đúng Trial đã ghi lại cho cả hai
framework. Bên gốc chạy `pydantic_evals.Dataset` với đủ 7 Evaluator; bên port
chạy `inspect_ai.eval` với Task, 7 Scorer và replay Solver. Không so hai lần chạy
agent khác nhau, không lấy điểm framework gốc làm đáp án cho scorer Inspect.

Nhãn được truyền riêng qua `Case.expected_output` và Inspect `Sample.target`;
metadata của Inspect chỉ chứa Trial và tên shape. Oracle điểm của 20 ca biên
không được đưa cho scorer. Không thêm nhãn inline vào eval set.

Inspect dùng `mockllm/model`, solver không gọi `generate`; log ghi `model_usage={}`.
Lỗi evaluator/scorer, thiếu điểm/case hoặc sample ID trùng đều làm phép kiểm thất
bại. Test chủ động đổi một scorer đã chứng minh công cụ phát hiện bất đồng.

## Kết quả đã đo

- **840 trial thật**: 28 item × 5 seed × 6 shape (`swarm`, `fixed`, `honest_refactor`,
  `seeded_regression`, `slice_regression`, `flaky_regression`).
- **20 ca biên tổng hợp**: leak canary, chuyển tiền không có approval, dòng tiền
  giá trị 0, hoàn nhầm claim, proposal/ledger/reply sai, dấu âm, nhiều mệnh đề,
  format VND, reply cuối, không reply và DB override.
- **860 × 7 = 6.020/6.020 kết quả khớp**; không lệch explanation hoặc oracle.
  Mỗi grader đều có ít nhất một điểm 0 và một điểm 1.
- Các aggregate v2 của cả sáu shape khớp, gồm pass@k/pass^k và cost/success.
  Safety native Inspect ghi **1 leak, 3 bypass**, đều từ ca biên tổng hợp;
  không coi đó là số vi phạm quan sát trên sáu shape thật.
- Môi trường đo: Python 3.13.18, Inspect AI 0.3.291, pydantic-evals 2.68.0.
  Dependency bonus nằm riêng trong `requirements-bonus.txt`.
- **26 test bonus PASS**; toàn bộ Lab 9 khi cài bonus đạt **220 passed**.
  Môi trường Core Python 3.12 giữ **194 passed, 1 skipped** (module bonus chưa cài),
  không thay dependency hoặc kết quả kiểm tra M0–M7.

Bằng chứng do script sinh:

- [Report parity](../src/reports/bonus_inspect_parity.json): từng trial có hash và
  hai chuỗi bit theo `metric_order`, số so khớp từng metric, aggregate từng shape,
  source hashes chuẩn hóa LF và SHA của log native.
- [Log Inspect gốc](../src/reports/bonus_inspect/2026-11-18T07-07-31-00-00_lab9-bonus-parity_dxiMEHDXzw2uVZcMABkhwB.eval):
  đủ 860 sample, score, explanation và target/metadata; mở được bằng Inspect View.
- [Log chạy parity](evidence/bonus_inspect_run.txt),
  [log test](evidence/bonus_inspect_tests.txt), [kết quả test](evidence/bonus_inspect_tests.json).

## Tái lập

Từ `src`, tạo môi trường riêng để giữ môi trường Core đang dùng:

```powershell
python -m venv .venv-bonus
.\.venv-bonus\Scripts\python.exe -m pip install -r requirements-bonus.txt
.\.venv-bonus\Scripts\python.exe -m pytest -q -m student -o addopts= -k lab9
.\.venv-bonus\Scripts\python.exe -m lab9.inspect_parity
.\.venv-bonus\Scripts\inspect.exe view --log-dir reports/bonus_inspect
```

`inspect_parity` tự sinh report và log mới; **exit 0** chỉ khi mọi điểm, explanation,
oracle và aggregate khớp. File `.eval` mới có tên theo thời gian chạy, SHA và đường
dẫn thật được ghi trong report. Không sửa tay report để cập nhật kết quả.

Workflow riêng [bonus-inspect.yml](../.github/workflows/bonus-inspect.yml) cài bonus
trên Python 3.13, chạy test Lab 9 và toàn bộ parity khi mở PR/chạy tay. Workflow
M0–M7 giữ nguyên; môi trường không cài Inspect chỉ skip module test bonus tùy chọn.

## Giới hạn

Parity kiểm tra bản port giữ đúng nghĩa của grader gốc, không chứng minh hai
grader luôn đúng. TrialPass vẫn dùng verdict Lab 8 đã ghi lại; parser reply giữ
phạm vi và giới hạn M3. 20 oracle tổng hợp không thay thế dữ liệu held-out.
Chưa quan sát GitHub Actions của commit bonus; điểm thưởng do giảng viên chấm.
