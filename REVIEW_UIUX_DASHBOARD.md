# Review UI/UX & Data Visualization — Dashboard GHN (nhánh `claude/sleepy-fermat-xv4hek`, commit 785e615)

Cách review: chạy `streamlit run app.py` với dữ liệu thật từ Google Sheet, đăng nhập 3032156, chụp toàn bộ 9 trang và 31 tab ở 1440px (máy tính) và 390px (điện thoại).

Thứ tự ưu tiên: **P0** = số liệu/màu đang làm người xem hiểu SAI, **P1** = biểu đồ khó đọc, **P2** = làm cho đẹp và nhất quán hơn.

---

## P0 — Hiểu sai số liệu (sửa trước)

### 1. Màu viền ô số liệu đi theo hướng tăng/giảm, nhưng người xem hiểu là "đạt KPI hay không"
`metric_card()` (app.py ~1293): `cls = "ok" if good else "bad"` với `good = (delta > 0) == higher_is_better`. Vì vậy:
- Tổng quan: **Tỷ lệ trả hàng 6.60% (KPI tối đa 6%)** có viền **xanh**, trong khi ngay bên dưới, phần cảnh báo ghi "CẦN XỬ LÝ — trả hàng vượt KPI".
- Vận hành › TikTok: **OPR tuần 81.82% (KPI 80%, đạt)** có viền **đỏ**; **%GTC TTS tháng 72.67% (KPI 77%, không đạt)** có viền **xanh**.

**Sửa:** tách thành hai tín hiệu riêng:
- **Viền trái và màu con số chính** = trạng thái so với KPI (đạt = xanh, không đạt = đỏ, chưa có KPI = xanh dương trung tính). Thêm tham số `target` cho `metric_card` và `period_cards`.
- **Dòng delta** = hướng thay đổi so với kỳ trước (giữ ▲▼ và màu xanh/đỏ như hiện nay).
- Ô nào có KPI thì luôn hiện chip "KPI 77% · thiếu 4.33 điểm". Hiện ô %GTC TikTok trên trang Tổng quan và cả 3 ô period của Vận hành đều chưa hiện KPI.

### 2. Chênh lệch giữa hai tỷ lệ phải ghi là "điểm %", không phải "%"
"▲ 0.17%" giữa 74.49% và 74.66% là **0.17 điểm %**. Ghi "0.17%" dễ bị đọc thành tăng 0.17% tương đối.
**Sửa:** trong `metric_card`, khi `unit == "%"` thì hiển thị `▲ 0.17 đ%` (hoặc `+0.17 điểm`). Sửa luôn chữ "lệch 0.60%" trong khối cảnh báo của trang Tổng quan và các chuỗi gửi cho AI.

### 3. Sparkline giống hệt nhau ở cả 3 ô Ngày / Tuần / Tháng
`period_cards()` truyền cùng một `spark` (7 ngày gần nhất) cho cả 3 ô. Vì thế ô "Tháng" mang đường xu hướng 7 ngày, và màu của sparkline có lúc ngược với màu của delta (ví dụ Doanh thu tuần: delta ▲ xanh, sparkline đỏ).
**Sửa:** ô Ngày giữ 7 ngày gần nhất. Ô Tuần dùng 6–8 tuần gần nhất (giá trị mỗi tuần). Ô Tháng dùng 6 tháng gần nhất. Nếu không làm được thì chỉ để sparkline ở ô Ngày. Màu sparkline nên để trung tính (xám/xanh dương), chỉ chấm điểm cuối mới tô xanh/đỏ, để không cạnh tranh với màu KPI.

### 4. Kinh doanh › "Còn thiếu so với mục tiêu: 0 đ" trong khi dự kiến VƯỢT mục tiêu
Dự kiến 87.9 tr so với mục tiêu 74.7 tr, nhưng ô hiện "0 đ" (app.py ~4740, `max(target - forecast, 0)`).
**Sửa:** khi dự kiến ≥ mục tiêu, đổi tiêu đề ô thành "Dự kiến vượt mục tiêu", hiện "+13.2 tr đ (118%)", viền xanh. Ngược lại hiện "Còn thiếu X tr đ", viền đỏ. Ô "Lũy kế tháng" thêm **% hoàn thành (74.6%) so với % thời gian đã qua (19/30 = 63%)** và một thanh tiến độ có vạch đánh dấu thời gian. Đây là chỉ số quản lý cần nhất để biết có kịp về đích hay không.

### 5. Năng suất & Lương › biểu đồ "Tổng lương, đơn GTC và LTC theo ngày" bị vỡ khi chỉ có 1 ngày
Khi kỳ lương mới có 1 ngày dữ liệu: cột chỉ còn là một sợi chỉ (vì trục là kiểu ngày nên bề rộng cột tính bằng mili-giây), trục phải hiện "0 đ" ở giữa biểu đồ, còn điểm 13.9 tr nằm lơ lửng phía trên.
**Sửa:** dùng trục x kiểu `category` (chuỗi "dd/mm"), hoặc đặt `xaxis.type="category"` cho mọi combo chart theo ngày. Khi có < 3 ngày dữ liệu thì không vẽ biểu đồ, hiện các ô số liệu kèm note "Kỳ lương mới có N ngày dữ liệu".

### 6. Thi đua › Top 3 mà không ghi rõ tiêu chí xếp hạng
Hạng 1 có 84.24%, hạng 2 có 94.14%, kèm chú thích "hạng tổng 3/4". Người xem không hiểu vì sao người % thấp hơn lại đứng trên.
**Sửa:** ngay dưới tiêu đề, ghi một dòng tiêu chí (ví dụ "Xếp theo: … ; điều kiện ≥80% và ≥ N đơn"). Trong mỗi thẻ, hiện đúng **chỉ số dùng để xếp hạng** làm con số lớn, còn %GTC để làm số phụ.

---

## P1 — Biểu đồ khó đọc

### 7. Trục số luôn bắt đầu từ 0 (`rangemode="tozero"`) làm phẳng các chỉ số nằm sát 100%
ODR (98–100%) và GTC Sameday (74–81%) trở thành một đường thẳng nằm trên đỉnh, nên không thấy được ngày nào hụt KPI. Quy tắc "trục bắt đầu từ 0" chỉ bắt buộc với **biểu đồ cột**, không bắt buộc với **biểu đồ đường**.
**Sửa:** với line chart của tỷ lệ, đặt `range = [min(dữ liệu, KPI) − 3 điểm, max(...) + 2]` (giới hạn trong 0–100), có thể thêm dải nền nhạt "vùng đạt KPI". Biểu đồ cột giữ nguyên trục từ 0.

### 8. Combo chart hai trục (`band_axes`): trục phải 0/50/100% nằm lơ lửng giữa biểu đồ
Trục phải hiện "0%" ngang mức 4,000 đơn của trục trái, và các đường 65–95% bị ép vào một dải mỏng nên không thấy dao động. Lưới của hai trục lệch nhau.
**Sửa (khuyến nghị):** bỏ trục kép, tách thành **2 biểu đồ xếp dọc dùng chung trục x** (`make_subplots(rows=2, shared_xaxes=True, row_heights=[0.4, 0.6])`): hàng trên là đường %GTC + % gán + đường KPI (trục được zoom như mục 7), hàng dưới là cột sản lượng. Áp dụng cho các tab GTC tổng, TikTok, OPR và Lương.

### 9. "Diễn biến 30 ngày" (Tổng quan): 4 chuỗi × 30 nhãn số chồng chéo lên nhau
%GTC tổng (#0077B6) và %GTC TikTok (#00B4D8) là hai màu xanh rất gần nhau, nhãn số đè lên nhau và lên đường KPI. ODR (~99%) và trả hàng (~6%) dùng chung một trục nên hai đường GTC bị nén ở giữa.
**Sửa:** chuyển sang **small multiples** (lưới 2×2, mỗi chỉ số một ô nhỏ có đường KPI riêng và trục được zoom riêng). Bỏ nhãn trên từng điểm, chỉ ghi nhãn **điểm cuối**, điểm min/max và các điểm không đạt KPI. Đặt tên KPI ở cuối đường ("KPI 72%") thay vì để chữ "KPI GTC" đè lên dữ liệu ở đầu biểu đồ.

### 10. Quá nhiều nhãn số trên biểu đồ
Line chart của KPI tab, %FD và 30 ngày đều ghi nhãn trên mọi điểm (`point_labels max_labels=16`).
**Sửa:** mặc định chỉ ghi nhãn điểm cuối và các điểm vi phạm KPI. Phần còn lại để hover xem.

### 11. Bullet chart theo bưu cục (Tiến độ KPI, So sánh giữa bưu cục)
- Nhãn "KPI 85.50%" nằm đè lên vạch KPI và mép cột. Nên dời nhãn KPI vào hover hoặc ghi nhỏ bên phải cột ("81.39% / KPI 85.5%").
- Nhãn giá trị nằm ngoài cột ("73.79%") bị vạch KPI cắt ngang.
- Cột quá dày khi chỉ có 1–3 bưu cục, để lại nhiều khoảng trắng. Đặt `bargap=0.45` và chiều cao biểu đồ theo số bưu cục (khoảng 70px/bưu cục + 80).
- Sắp xếp bưu cục theo **khoảng cách tới KPI** (tệ nhất lên đầu) thay vì theo giá trị.

### 12. Doanh thu theo ngày: thiếu mốc tham chiếu
Nên thêm đường "mục tiêu/ngày" (74.7 tr ÷ 30 ≈ 2.49 tr) và tô màu các cột thấp hơn mốc này. Đồng thời định dạng trục y theo kiểu Việt Nam ("4 tr", không dùng "4,000,000").

### 13. Bảng dữ liệu bị cắt cột bên phải
Bảng lương theo nhân viên (cột "Tổng…") và Truy thu (cột "Mã đơn hàng", "Còn phải…") bị cắt, người xem không biết là có thể cuộn ngang.
**Sửa:** dùng `st.dataframe(..., column_config=...)` để ghim cột Nhân viên, rút gọn tên cột ("Đơn giao TL", "Đơn lấy TL"), đưa cột Tổng lương lên ngay sau Nhân viên, định dạng tiền bằng `NumberColumn(format="%,d đ")`, và thêm `ProgressColumn` cho cột %.

---

## P2 — Nhất quán và đánh bóng

14. **Định dạng số không thống nhất**: các ô dùng "55.691.458 đ" (kiểu VN), nhưng bảng và trục dùng "1,073,500", "1,643 đơn gán", và nhãn ghi "3.4 tr đ" (dấu thập phân kiểu Anh). Nên chọn một chuẩn VN: nghìn ngăn bằng `.`, thập phân bằng `,` ("3,4 tr đ"). Đặt `separators=",."` trong template Plotly và dùng chung một hàm `fmt_*` cho mọi bảng.
15. **Màu ngữ nghĩa bị trùng**: cam (ACCENT) vừa là màu nút bấm, vừa là màu "%GTC" trong combo chart, vừa là màu số "Sản lượng" / "Dự kiến", vừa là màu tag "THEO DÕI". Nên dành cam cho *hành động và cảnh báo nhẹ*. Bảng màu cho chuỗi dữ liệu: sản lượng = xanh dương nhạt/xám, %GTC = xanh dương đậm, %gán = tím hoặc xám, KPI = nét đứt màu xám đậm (không dùng đỏ, vì đỏ đã có nghĩa là "không đạt").
16. **Trang Tổng quan**: xếp 8 ô theo nhóm có tiêu đề nhỏ (Vận hành: Sản lượng, %GTC, trả hàng, GTB · TikTok: GTC, ODR, OPR · Kinh doanh: Doanh thu) thay vì một lưới phẳng. Các ô đang không đạt KPI nên đưa lên trước.
17. **Sidebar**: hai nút "LÀM MỚI DỮ LIỆU" và "ĐĂNG XUẤT" đều màu cam đặc, nổi bật hơn cả nội dung chính. Nên đổi thành nút phụ (viền, nền trắng), riêng Đăng xuất là nút dạng chữ.
18. **Sparkline**: tăng chiều cao lên ~36px, chấm điểm cuối, và thêm tooltip giá trị cho thiết bị cảm ứng (`<title>` không hiện khi chạm trên điện thoại).
19. **Điện thoại (390px)**: trang Tổng quan dài 2.660px vì mỗi ô chiếm cả một hàng. Nên xếp **2 ô mỗi hàng** ở ≤640px (bỏ sparkline, con số ~22px), và đưa khối "Cảnh báo" lên **trên** các ô số liệu, vì đó là thứ quản lý cần thấy đầu tiên. Thanh tab bị xuống dòng ("Nhận định AI" rơi xuống dòng 2), nên cho thanh tab cuộn ngang thay vì xuống dòng.
20. **Banner thứ hai "BẢNG XẾP HẠNG THI ĐUA…"** trên trang Thi đua lặp lại style banner chính và chiếm khoảng 70px. Nên thay bằng `section-title`.
21. **Trạng thái trống**: "Bưu cục diện đỏ — ỔN ĐỊNH" chỉ có một dòng chữ. Nên hiện thêm mini-bảng 3 bưu cục với số ngày dưới KPI hiện tại (0/3), để người xem thấy được bưu cục nào đang gần ngưỡng.

---

## Đề xuất thứ tự làm
1. Mục 1, 2, 3 (`metric_card` / `period_cards`): sửa một chỗ, có tác dụng trên toàn bộ app.
2. Mục 4, 5, 6.
3. Mục 7, 8, 9 (`_line_fig`, `_combo_fig`, `band_axes`, biểu đồ 30 ngày).
4. Mục 10–13, sau đó đến P2.

Mỗi bước: chạy app, chụp lại trang Tổng quan, Vận hành › TikTok, Kinh doanh, Năng suất › Lương ở 1440px và 390px để so trước/sau.
