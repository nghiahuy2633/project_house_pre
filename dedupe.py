import pandas as pd
import os

INPUT_FILE = 'list_links.json'
OUTPUT_FILE = 'list_links_dedupe.json'

def clean_duplicates():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Không tìm thấy file {INPUT_FILE}")
        return

    print("--- ĐANG XỬ LÝ DỮ LIỆU ---")
    
    try:

        df = pd.read_json(INPUT_FILE, lines=True)
        total_rows = len(df)
        print(f"📊 Tổng số link ban đầu: {total_rows:,}")

        df_clean = df.drop_duplicates(subset=['URL'], keep='first')
        

        clean_rows = len(df_clean)
        removed_rows = total_rows - clean_rows

        df_clean.to_json(OUTPUT_FILE, orient='records', lines=True, force_ascii=False)

        print("-" * 30)
        print(f"✅ Đã xóa: {removed_rows:,} link trùng.")
        print(f"💎 Còn lại: {clean_rows:,} link sạch (Unique).")
        print(f"💾 Đã lưu vào file: {OUTPUT_FILE}")
        print("-" * 30)

    except ValueError as e:
        print("❌ LỖI ĐỌC FILE: Có thể file bị lỗi cấu trúc (dính dòng '}{').")
        print("Cách sửa: Mở file json bằng VS Code, nhấn Ctrl+H, thay thế '}{' thành '}\\n{' rồi lưu lại và chạy lại code này.")
    except Exception as e:
        print(f"❌ Lỗi không xác định: {e}")

if __name__ == "__main__":
    clean_duplicates()