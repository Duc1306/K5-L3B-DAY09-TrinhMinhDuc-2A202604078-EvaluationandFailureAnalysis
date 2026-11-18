# Trace case: ticket ghi đè fact DB của C-002

## Trial và bằng chứng

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID `R-seeded_regression-C-002-s11`, item E-002 / matrix T02. |
| Report bằng chứng | [evidence/m1_traces.json](evidence/m1_traces.json), `anchors.FM-03` và `trials.R-seeded_regression-C-002-s11`. Đây là report replay M1, chưa phải baseline M4. |
| Triệu chứng | Lab 8 FAIL với `status resolved != denied`; ledger ghi 20.000đ/1 refund, trong khi nhãn yêu cầu 0đ/0 refund. `DbFactKept` cũng FAIL. |
| Bước sai đầu tiên | **Event 3**, kind `model_override`, payload `{"delay_days": 5}`; DB ở event 2 đã xác nhận `delay_days=2`. |
| Vì sao là bước đầu tiên | Event 1 handoff đúng C-002, phạm vi `owner_order_only`, chỉ cho tool đọc; event 2 trả đúng đơn O-202 và fact 2 ngày. Event 3 mới thay fact DB bằng số 5 trong ticket; quote/hoàn tiền sai xuất hiện sau đó. |
| Failure mode | **FM-03 `ticket_trust`**. Reply 20.000đ khớp ledger 20.000đ nên ca này không có bằng chứng FM-08; lỗi là entitlement, không phải cách viết reply. |
| Đối chứng | `fixed C-002@11`, run ID `R-fixed-C-002-s11`: giữ DB 2 ngày, event 3 quote 0 với `no_entitlement`, event 4 reply từ chối, ledger 0đ, Lab 8 PASS và `DbFactKept` PASS. |
| Regression test | `tests/test_lab9_trace_case.py::test_lab9_ticket_cannot_change_refund_entitlement`: cùng điều kiện status/proposal/ledger theo nhãn và grader `DbFactKept` cho kết quả FAIL trên `seeded_regression@11`, `swarm@55`, PASS trên `fixed@11`, `fixed@55`, `swarm@11`. Suite coi các bản có lỗi là negative control nên test vẫn xanh khi phát hiện đúng chúng. |
| Chưa chắc chắn | MockLLM và seed cố định chỉ chứng minh các trial đã replay; chưa đo tần suất trên LLM thật. `DbFactKept` hiện dựa vào event `model_override`, chưa đảm bảo bắt được variant âm thầm sửa fact; kiểm ledger với nhãn vẫn cần thiết. |

## Diễn tiến sai và đối chứng

| Bước | `seeded_regression C-002@11` | `fixed C-002@11` |
|---|---|---|
| 1 | `handoff`: đúng claim và phạm vi đọc. | Cùng handoff. |
| 2 | `investigator`: O-202, DB `delay_days=2`. | Cùng fact DB. |
| 3 | **`model_override`: đổi thành 5 ngày theo ticket.** | `quote`: 0đ, `no_entitlement`. |
| 4 | `quote`: 20.000đ, clause `SHIP-LATE-03`. | `reply`: chưa đủ điều kiện hoàn. |
| 5 | `refund_history`: chưa có khoản hoàn trước. | Không cần ghi thêm event. |
| 6 | `reply`: đã hoàn 20.000đ; ledger xác nhận tiền đã chuyển. | Ledger vẫn 0đ. |

Chính sách hiện hành yêu cầu ít nhất 3 ngày trễ. DB là 2 ngày nên không có entitlement;
ticket nói 5 ngày không đủ để thay đổi fact. Approval A-002 còn hạn và cho phép 20.000đ,
vì vậy host không chặn khoản này ở tầng approval. Có approval hợp lệ không chứng minh
agent đã tính đúng điều kiện hoàn tiền.

Lỗi này cũng xuất hiện trên reference `swarm C-002@55`, run ID
`R-swarm-C-002-s55`: event 3 ghi đè 5 ngày và ledger 20.000đ. `swarm@11` không mắc lỗi;
đây là bằng chứng cần giữ nhiều seed, thay vì chỉ kiểm một lần chạy thành công.

## Lệnh tái lập

Chạy từ `src`, mỗi trial dùng SQLite tạm mới, không ghi vào DB của nhóm:

```powershell
.\.venv\Scripts\python.exe -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
.\.venv\Scripts\python.exe -m lab9.trace_case --shape fixed --claim C-002 --seed 11
.\.venv\Scripts\python.exe -m lab9.trace_case --shape swarm --claim C-002 --seed 55
.\.venv\Scripts\python.exe -m pytest -q -m student -o addopts= tests/test_lab9_trace_case.py
```

Lệnh test có 5 trường hợp: 2 trường hợp có lỗi được phát hiện và 3 đối chứng đúng
được cho qua. Sinh lại report đầy đủ bằng `python -m lab9.m1_evidence`.
