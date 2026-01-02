# Batdongsan Scraper Project

Tool tự động thu thập dữ liệu bất động sản (Batdongsan.com.vn), hỗ trợ đa luồng, tự động xử lý lỗi và lọc trùng.

## 1. Cài đặt môi trường

Mở Terminal tại thư mục dự án và chạy lần lượt các lệnh sau:

```bash
# 1. Tạo môi trường ảo (Khuyên dùng)
python -m venv venv

# 2. Kích hoạt môi trường (Windows)
.\venv\Scripts\activate

# 3. Cài đặt thư viện
pip install -r requirements.txt
```
## 2. Hướng dẫn chạy
Bước 1: Lấy danh sách Link
```bash
python get_links.py
Bước 2: Lọc trùng link
```
```bash
python dedupe.py
```
Bước 3: Cào dữ liệu chi tiết
```bash
python get_details.py
```

## 3. Cấu hình & Tùy chỉnh
### Trong file `get_links.py` (Cấu hình khu vực quét)
- **`BASE_URL_TEMPLATE`**: Link gốc của khu vực cần cào.
  - *Lưu ý:* Phải giữ nguyên ký tự `{}` trong link (ví dụ: `.../p{}...`) để code tự điền số trang.
- **`START_PAGE`**: Số trang bắt đầu cào (Ví dụ: `10`).
- **`END_PAGE`**: Số trang kết thúc (Ví dụ: `1010` để cào đến trang 1010 rồi dừng).

### Trong file `get_details.py` (Cấu hình tốc độ)
- **`NUM_DRIVERS`**: Số lượng trình duyệt mở cùng lúc (Nên để 3-4 nếu RAM 8GB; 5-8 nếu RAM 16GB)
- **`BATCH_SIZE`**: Số lượng link lấy ra để xử lý trong một đợt (ví dụ: 1000 link)

