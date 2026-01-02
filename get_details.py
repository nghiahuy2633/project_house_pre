# -*- coding: utf-8 -*-
"""
Created on Wed Dec 31 10:19:24 2025

@author: HuyTryhard
"""
import time
import random
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
# from selenium import webdriver
# from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import queue
import json
import threading
import undetected_chromedriver as uc
import pandas as pd
import re

INPUT_FILE_LINKS = 'list_links_dedupe.json'
OUTPUT_FILE_DATA = 'data_scraped.json'
OUTPUT_FILE_DEAD = 'dead_links.json'
BATCH_SIZE = 4000
NUM_DRIVERS = 7  # Số lượng trình duyệt muốn mở sẵn
JSON_LOCK = threading.Lock()
DRIVER_QUEUE = queue.Queue()


def get_product_id(url):
    try:
        match = re.search(r"pr(\d+)", url)
        if match:
            return match.group(1)
        return "Unknown_ID"
    except:
        return "Error_ID"
    
def count_file_lines(filepath):
    if not os.path.exists(filepath):
        return 0
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return sum(1 for _ in f)
    except:
        return 0   


def get_links_to_scrape():
    print("--- ĐANG KIỂM TRA TIẾN ĐỘ ---")
    
    try:
        df_source = pd.read_json(INPUT_FILE_LINKS, lines=True)
        all_links = set(df_source['URL'].tolist())
    except:
        print(f"❌ Lỗi: Không tìm thấy file nguồn {INPUT_FILE_LINKS}")
        return []
    
    done_links = set()
    if os.path.exists(OUTPUT_FILE_DATA):
        try:
            df_done = pd.read_json(OUTPUT_FILE_DATA, lines=True)
            if not df_done.empty and 'url' in df_done.columns:
                    done_links = set(df_done['url'].tolist())
        except:
            pass

    if os.path.exists(OUTPUT_FILE_DEAD):
        try:
            df_dead = pd.read_json(OUTPUT_FILE_DEAD, lines=True)
            if not df_dead.empty and 'url' in df_done.columns:
                dead_links = set(df_dead['url'].tolist())
                done_links.update(dead_links)
        except:
            pass

    remaining_links = list(all_links - done_links)
    
    total = len(all_links)
    done = len(done_links)
    remain = len(remaining_links)

    print(f"📊 Tổng số link: {total:,}")
    print(f"✅ Đã cào xong : {done:,}")
    print(f"🚀 Còn lại      : {remain:,}")

    if remain == 0:
        print("🎉 Chúc mừng! Bạn đã cào xong hết toàn bộ dữ liệu.")
        return []

    current_batch = remaining_links[:BATCH_SIZE]
    
    print(f"⚡ Đợt này sẽ chạy: {len(current_batch)} link")
    print("-" * 30)
    
    return current_batch



def save_result_json(data):
    with JSON_LOCK: # Khóa an toàn
        with open(OUTPUT_FILE_DATA, 'a', encoding='utf-8') as f:
            # ensure_ascii=False để hiển thị tiếng Việt không bị lỗi font (\u...)
            json.dump(data, f, ensure_ascii=False)
            f.write('\n')
            
def save_dead_link(url, reason):
    with JSON_LOCK:
        with open(OUTPUT_FILE_DEAD, 'a', encoding='utf-8') as f:
            json.dump({"url": url, "error": reason}, f, ensure_ascii=False)
            f.write('\n')

def create_driver():
    options = uc.ChromeOptions()
    
    # --- 1. CẤU HÌNH CƠ BẢN ---
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")

    # --- 2. CẤU HÌNH ỔN ĐỊNH ---
    options.add_argument("--disable-dev-shm-usage")   # Tránh lỗi thiếu bộ nhớ chia sẻ
    options.add_argument("--disable-popup-blocking")  # Tắt chặn popup
    options.add_argument("--disable-gpu")             # Giảm tải cho Card màn hình
    options.add_argument("--disable-notifications")   # Tắt thông báo trình duyệt làm phiền

    # --- 3. CẤU HÌNH TỐC ĐỘ ---
    options.page_load_strategy = 'eager' 
    
    # Chặn ảnh , các thứ
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
        
        # Nhét driver vào hàng đợi (Queue)
        DRIVER_QUEUE.put(driver)
        print(f"-> Đã mở xong Browser #{i+1}")
    print("--- Start! ---")
    
def worker_task(url):
    driver = None
    product_id = get_product_id(url)
    try:
        # B1: MƯỢN driver từ hàng đợi
        driver = DRIVER_QUEUE.get()
        driver.get(url)
        
        if "batdongsan.com.vn" in driver.current_url and url.split('?')[0] not in driver.current_url:
            print(f"❌ [DEAD] ID: {product_id} (Redirect)")
            save_dead_link(url, "Redirected")
            DRIVER_QUEUE.put(driver) 
            return
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".re__pr-specs-content-item-value"))
            )
        except TimeoutException:
            print(f"💀 [FAIL] ID: {product_id} (No Data)")
            save_dead_link(url, "Timeout/Not Found")
            DRIVER_QUEUE.put(driver)
            return
        
              
        soup = BeautifulSoup(driver.page_source, 'lxml')
        
        # 1. Title
        title_elem = soup.select_one(".re__pr-title.pr-title.js__pr-title")
        title = title_elem.get_text(strip=True) if title_elem else None
        
        # 2. Location
        loc_elem = soup.select_one("span.re__pr-short-description.js__pr-address")
        location = loc_elem.get_text(strip=True) if loc_elem else None
        
        # 3. Image
        img_elem = soup.select_one(".re__media-thumb-item img")
        url_img = None
        if img_elem:
            url_img = img_elem.get('src') or img_elem.get('data-src')

        # 4. House Type
        breadcrumbs = soup.select(".re__breadcrumb .re__link-se")
        house_type = breadcrumbs[-1].get_text(strip=True) if breadcrumbs else None

        # 5. Mô tả
        desc_elem = soup.select_one(".re__detail-content")
        description = desc_elem.get_text(strip=True) if desc_elem else None

        # 6. Ngày đăng
        published = None
        try:
            pub_label = soup.find("span", class_="title", string="Ngày đăng")
            if pub_label:
                published = pub_label.find_next_sibling("span", class_="value").get_text(strip=True)
        except:
            pass

        # 7. Thông số chi tiết (Specs)
        price = area = legal = bedrooms = toilets = furnishing = width = floors = features = None
        
        specs = soup.select(".re__pr-specs-content-item")
        
        for spec in specs:
            try:
                t = spec.select_one(".re__pr-specs-content-item-title").get_text(strip=True)
                v = spec.select_one(".re__pr-specs-content-item-value").get_text(strip=True)
                
                if "Khoảng giá" in t: price = v
                elif "Diện tích" in t: area = v
                elif "Pháp lý" in t: legal = v
                elif "Số phòng ngủ" in t: bedrooms = v
                elif "Số phòng tắm" in t: toilets = v
                elif "Nội thất" in t: furnishing = v
                elif "Mặt tiền" in t: width = v
                elif "Số tầng" in t: floors = v
                elif "Đường vào" in t: features = v
            except:
                continue

        crawled_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        data = { 
                "url": url,
                "title": title,
                "price": price,
                "area": area,
                "location": location,
                "house_type": house_type,
                "legal": legal,
                "bedrooms": bedrooms,
                "toilets": toilets,
                "furnishing": furnishing,
                "width": width,
                "floors": floors,
                "features": features,
                "description": description,
                "crawled_at": crawled_at,
                "published_date": published,
                "image_url": url_img
            }
        
        save_result_json(data)
        time.sleep(random.uniform(0.1, 1.0))
        DRIVER_QUEUE.put(driver)
    # except Exception as e:
    #    print(f"[LỖI] - {str(e)[:10]}...")
       
    # finally:
    #     # --- 3. TRẢ DRIVER VỀ HÀNG ĐỢI ---
    #     if driver:
    #         DRIVER_QUEUE.put(driver)
    
    except Exception as e:
        str_error = str(e).lower()
        if "invalid session" in str_error or "died" in str_error or "closed" in str_error:
            print(f"⚠️ [CRASH] ID: {product_id} - Driver sập, đang hồi sinh...")
            try: driver.quit()
            except: pass
            try: DRIVER_QUEUE.put(create_driver())
            except: pass
        else:
            print(f"🔥 [ERR] ID: {product_id} - {str(e)[:50]}")
            if driver: DRIVER_QUEUE.put(driver)
            
if __name__ == "__main__":

    list_links = get_links_to_scrape()
    
    if len(list_links) > 0:

        start_success_count = count_file_lines(OUTPUT_FILE_DATA)
        start_dead_count = count_file_lines(OUTPUT_FILE_DEAD)
        
        init_driver_pool(NUM_DRIVERS)
        
        print(f"\n🚀 BẮT ĐẦU CHẠY BATCH {len(list_links)} LINKS...")
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=NUM_DRIVERS) as executor:
            executor.map(worker_task, list_links)
        
        total_time = time.time() - start_time
        
        end_success_count = count_file_lines(OUTPUT_FILE_DATA)
        end_dead_count = count_file_lines(OUTPUT_FILE_DEAD)
        
        added_success = end_success_count - start_success_count
        added_dead = end_dead_count - start_dead_count
        
        print("\n" + "="*45)
        print("           📊 BÁO CÁO KẾT QUẢ (FILE)       ")
        print("="*45)
        print(f"⏱️  Thời gian chạy    : {total_time:.2f} giây")
        print(f"📁  Tổng Link đầu vào : {len(list_links)}")
        print("-" * 45)
        print(f"✅  Lưu thành công    : +{added_success} link")
        print(f"💀  Phát hiện chết    : +{added_dead} link")
        
        processed = added_success + added_dead
        missed = len(list_links) - processed
        
        if missed > 0:
            print(f"⚠️  Chưa chạy xong    : {missed} link (Do dừng hoặc lỗi)")
        
        print("="*45)

        print("Đang đóng trình duyệt...")
        while not DRIVER_QUEUE.empty():
            try: DRIVER_QUEUE.get().quit()
            except: pass
        print("Đã đóng xong!")