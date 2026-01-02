import time
import random
import json
import threading
import queue
import undetected_chromedriver as uc
from concurrent.futures import ThreadPoolExecutor
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd

OUTPUT_FILE = "list_links.json" 
JSON_LOCK = threading.Lock()
NUM_DRIVERS = 8 

# Cấu hình tạo Link
BASE_URL_TEMPLATE = "https://batdongsan.com.vn/ban-nha-rieng-tp-hcm/p{}?cIds=325,163"
START_PAGE = 42
END_PAGE = 1001  

list_pages = [BASE_URL_TEMPLATE.format(i) for i in range(START_PAGE, END_PAGE + 1)]
print(f"-> Đã tạo danh sách {len(list_pages)} trang cần quét.")

DRIVER_QUEUE = queue.Queue()


def save_link_to_json(data):
    with JSON_LOCK:
        with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
            f.write('\n')
            
def create_driver():
    options = uc.ChromeOptions()
    
    # --- 1. CẤU HÌNH CƠ BẢN
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")

    # --- 2. CẤU HÌNH ỔN ĐỊNH
    # options.add_argument("--no-sandbox")              # Chạy ổn định hơn trên mọi môi trường
    options.add_argument("--disable-dev-shm-usage")   # Tránh lỗi thiếu bộ nhớ chia sẻ
    options.add_argument("--disable-popup-blocking")  # Tắt chặn popup
    options.add_argument("--disable-gpu")             # Giảm tải cho Card màn hình
    options.add_argument("--disable-notifications")   # Tắt thông báo trình duyệt làm phiền

    # --- 3. CẤU HÌNH TỐC ĐỘ
    options.page_load_strategy = 'eager' 
    
    # Chặn ảnh , rườm rà
    prefs = {
        "profile.managed_default_content_settings.images": 2, # Block Image
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2 # Block Notifications
    }
    options.add_experimental_option("prefs", prefs)

    # Khởi tạo Driver
    try:
        driver = uc.Chrome(options=options, use_subprocess=True)
    except TypeError:
        driver = uc.Chrome(options=options)
        
    driver.set_page_load_timeout(20) 
    return driver

def init_driver_pool(n):
    print(f"--- Đang mở sẵn {n} trình duyệt, vui lòng đợi... ---")
    for i in range(n):
        driver = create_driver()
        driver.maximize_window()
        
        # Mở trang chủ trước để lấy Cookies tin cậy
        try:
            driver.get("https://batdongsan.com.vn")
            time.sleep(2) 
        except:
            pass
        
        # Nhét driver vào hàng đợi
        DRIVER_QUEUE.put(driver)
        print(f"-> Đã mở xong Browser #{i+1}")
    print("--- START! ---")
 
    


def scrape_listing_page(page_url):
    driver = None
    try:
        # Lấy driver từ hàng đợi
        driver = DRIVER_QUEUE.get()
        
        # ---
        driver.get(page_url)
        
        time.sleep(random.uniform(1.5, 2.5))
        
        # Scroll
        for _ in range(3):
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(0.5)

        # Đợi Data
        try:
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".js__card-full-web"))
            )
        except:
            pass

        soup = BeautifulSoup(driver.page_source, 'lxml')
        cards = soup.select(".js__card-full-web")
        
        count = 0
        valid_data_count = 0 
        
        for card in cards:
            try:
                link_elem = card.select_one("a.js__product-link-for-product-id")
                if not link_elem: continue 
                
                href = link_elem.get('href')
               
                if href and not href.startswith("http"):
                    href = "https://batdongsan.com.vn" + href
                
                price_elem = card.select_one(".re__card-config-price") 
                price = price_elem.get_text(strip=True) if price_elem else None
                
                
                date_elem = card.select_one("span.re__card-published-info-published-at")
                date_post = date_elem.get("aria-label") if date_elem else None
                
                if date_elem:

                    date_post = date_elem.get("aria-label")

                    if not date_post:
                        date_post = date_elem.get_text(strip=True)

                data = { 
                        "URL": href,
                        "price": price,
                        "published": date_post
                    }
                save_link_to_json(data)
                valid_data_count += 1
                count += 1
            except: continue
        
        if valid_data_count == 0:
            print(f"[MISS] Page {page_url} có 0/20 tin (Trang trống hoặc bị chặn)")
        else:
            print(f"[OK] Page {page_url} - Lấy {valid_data_count} tin.")

        # Trả driver
        DRIVER_QUEUE.put(driver)

    except Exception as e:
        str_error = str(e).lower()
        
        if "invalid session" in str_error or "died" in str_error or "closed" in str_error:
            print(f"[CRASH] Driver bị sập khi cào {page_url}. Đang tạo mới...")
            
            try: driver.quit()
            except: pass 
            
            try:
                new_driver = create_driver()
                DRIVER_QUEUE.put(new_driver)
                print("-> Đã hồi sinh Driver mới thành công.")
            except:
                print("-> Hồi sinh thất bại (Có thể do full RAM).")
        else:

            print(f"[LỖI] {page_url} - {str(e)[:100]}...")
            if driver:
                DRIVER_QUEUE.put(driver)    

if __name__ == "__main__":
    # 1. Khởi tạo Driver
    init_driver_pool(NUM_DRIVERS)
    
    # 2. Chạy
    print(f"Bắt đầu cào {len(list_pages)} trang danh sách...")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=NUM_DRIVERS) as executor:
        executor.map(scrape_listing_page, list_pages)
    
    print(f"Hoàn thành tất cả trong {time.time() - start_time:.2f}s")
    
    # 3. Dọn dẹp
    while not DRIVER_QUEUE.empty():
        d = DRIVER_QUEUE.get()
        d.quit()
    
    # mở file = df
    # df= pd.read_json('list_links.json', lines=True)
