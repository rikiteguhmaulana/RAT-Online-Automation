"""
RAT Online Form Automation Script
=================================
Script untuk mengotomatisasi pengisian formulir RAT Online
menggunakan data user dari file PDF.

Dependencies:
    pip install pdfplumber selenium webdriver-manager

Author: Automated Script
"""

import time
import sys
import pdfplumber
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager


# ============================================
# KONFIGURASI
# ============================================
TARGET_URL = "https://komida.co.id/ratonline/"
WAIT_BETWEEN_USERS = 0  # Tanpa jeda antar user (Super Greget)

# Hardcoded values untuk Saran & Masukan
SARAN_MASUKAN = {
    "Pelayanan ke Anggota": "baik",
    "Produk Pinjaman": "banyak",
    "Jumlah Pinjaman": "banyak",
    "Simpanan": "banyak",
    "Margin": "sedikit",
    "Lain-lain": "cukup"
}


# ============================================
# FUNGSI PDF PARSING
# ============================================
def extract_users_from_pdf(pdf_path: str) -> list:
    """
    Ekstrak data Username dan Password dari file PDF.
    Mendukung tabel yang tersebar di beberapa halaman.
    
    Args:
        pdf_path: Path ke file PDF
        
    Returns:
        List of dicts berisi {'username': str, 'password': str}
    """
    users = []
    
    # Simpan indeks kolom untuk tabel yang berlanjut tanpa header
    last_username_idx = None
    last_password_idx = None
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"  [INFO] PDF memiliki {len(pdf.pages)} halaman")
            
            for page_num, page in enumerate(pdf.pages, 1):
                tables = page.extract_tables()
                page_users_count = 0
                
                print(f"  [INFO] Halaman {page_num}: ditemukan {len(tables)} tabel")
                
                for table_idx, table in enumerate(tables):
                    if not table or len(table) == 0:
                        continue
                    
                    # Cari indeks kolom Username dan Password
                    header_row = table[0] if table else []
                    username_idx = None
                    password_idx = None
                    start_row = 0  # Baris mulai ekstrak data
                    
                    # Cari header (case-insensitive)
                    for idx, cell in enumerate(header_row):
                        if cell:
                            cell_lower = str(cell).lower().strip()
                            if 'username' in cell_lower:
                                username_idx = idx
                            elif 'password' in cell_lower:
                                password_idx = idx
                    
                    # Jika header ditemukan di halaman ini
                    if username_idx is not None and password_idx is not None:
                        last_username_idx = username_idx
                        last_password_idx = password_idx
                        start_row = 1  # Skip header
                    # Jika tidak ada header tapi kita punya indeks dari halaman sebelumnya
                    elif last_username_idx is not None and last_password_idx is not None:
                        username_idx = last_username_idx
                        password_idx = last_password_idx
                        start_row = 0  # Tidak ada header, mulai dari baris pertama
                    else:
                        # Tidak bisa menentukan kolom, skip tabel ini
                        continue
                    
                    # Ekstrak data dari setiap baris
                    for row in table[start_row:]:
                        if len(row) > max(username_idx, password_idx):
                            username = row[username_idx]
                            password = row[password_idx]
                            
                            # Validasi data tidak kosong dan bukan header
                            if username and password:
                                username = str(username).strip()
                                password = str(password).strip()
                                
                                # Skip jika ini adalah header yang terulang
                                if 'username' in username.lower() or 'password' in password.lower():
                                    continue
                                
                                # Skip jika username kosong atau hanya angka baris
                                if username and password and len(username) > 2:
                                    users.append({
                                        'username': username,
                                        'password': password
                                    })
                                    page_users_count += 1
                                    print(f"    [USER] {username}")
                
                if page_users_count > 0:
                    print(f"  [INFO] Halaman {page_num}: {page_users_count} user diekstrak")
        
        print(f"\n[SUCCESS] Total {len(users)} user ditemukan dari PDF")
        return users
        
    except FileNotFoundError:
        print(f"[ERROR] File PDF tidak ditemukan: {pdf_path}")
        return []
    except Exception as e:
        print(f"[ERROR] Gagal membaca PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


# ============================================
# FUNGSI SELENIUM AUTOMATION
# ============================================
def setup_driver() -> webdriver.Chrome:
    """
    Setup Chrome WebDriver dengan konfigurasi optimal.
    """
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--headless=new")  # Mode headless untuk kecepatan maksimal
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # Disable Gambar untuk mempercepat loading
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(1)  # Minimal wait time (1s)
    
    return driver


def perform_login(driver: webdriver.Chrome, username: str, password: str) -> bool:
    """
    Melakukan proses login ke website.
    
    Returns:
        True jika login berhasil, False jika gagal
    """
    try:
        # Navigasi ke halaman login
        driver.get(TARGET_URL)
        # Menghapus time.sleep di sini, mengandalkan WebDriverWait
        
        wait = WebDriverWait(driver, 2)  # Minimal explicit wait (2s)
        
        # Cari dan isi field username
        # Mencoba berbagai kemungkinan selector
        username_selectors = [
            (By.NAME, "username"),
            (By.NAME, "Username"),
            (By.ID, "username"),
            (By.ID, "Username"),
            (By.CSS_SELECTOR, "input[type='text']"),
            (By.CSS_SELECTOR, "input[placeholder*='username' i]"),
            (By.CSS_SELECTOR, "input[placeholder*='Username' i]"),
        ]
        
        username_field = None
        for by, selector in username_selectors:
            try:
                username_field = wait.until(EC.presence_of_element_located((by, selector)))
                break
            except TimeoutException:
                continue
        
        if not username_field:
            print("    [ERROR] Field username tidak ditemukan")
            return False
        
        username_field.clear()
        username_field.send_keys(username)
        
        # Cari dan isi field password
        password_selectors = [
            (By.NAME, "password"),
            (By.NAME, "Password"),
            (By.ID, "password"),
            (By.ID, "Password"),
            (By.CSS_SELECTOR, "input[type='password']"),
        ]
        
        password_field = None
        for by, selector in password_selectors:
            try:
                password_field = driver.find_element(by, selector)
                break
            except NoSuchElementException:
                continue
        
        if not password_field:
            print("    [ERROR] Field password tidak ditemukan")
            return False
        
        password_field.clear()
        password_field.send_keys(password)
        
        # Klik tombol login
        login_button_selectors = [
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.CSS_SELECTOR, "input[type='submit']"),
            (By.XPATH, "//button[contains(text(), 'Login')]"),
            (By.XPATH, "//button[contains(text(), 'login')]"),
            (By.XPATH, "//button[contains(text(), 'Masuk')]"),
            (By.XPATH, "//input[@value='Login']"),
            (By.CSS_SELECTOR, ".btn-login"),
            (By.CSS_SELECTOR, ".login-btn"),
        ]
        
        login_button = None
        for by, selector in login_button_selectors:
            try:
                login_button = driver.find_element(by, selector)
                break
            except NoSuchElementException:
                continue
        
        if not login_button:
            print("    [ERROR] Tombol login tidak ditemukan")
            return False
        
        login_button.click()
        # time.sleep dikurangi minimal
        time.sleep(0.5)
        
        # Verifikasi login berhasil (cek apakah masih di halaman login atau tidak)
        current_url = driver.current_url
        if "login" not in current_url.lower() or current_url != TARGET_URL:
            print("    [SUCCESS] Login berhasil")
            return True
        else:
            print("    [WARNING] Kemungkinan login gagal, melanjutkan proses...")
            return True  # Tetap lanjutkan untuk mencoba
            
    except Exception as e:
        print(f"    [ERROR] Gagal login: {str(e)}")
        return False


def fill_pendapat_section(driver: webdriver.Chrome) -> bool:
    """
    Mengisi bagian Pendapat dengan memilih semua opsi "Setuju".
    
    Returns:
        True jika berhasil, False jika gagal
    """
    try:
        # Cari semua radio button "Setuju"
        setuju_selectors = [
            (By.XPATH, "//input[@type='radio'][following-sibling::text()[contains(., 'Setuju')] or @value='Setuju' or @value='setuju']"),
            (By.XPATH, "//input[@type='radio'][@value='Setuju']"),
            (By.XPATH, "//input[@type='radio'][@value='setuju']"),
            (By.XPATH, "//input[@type='radio'][@value='1']"),  # Kadang value 1 = Setuju
            (By.XPATH, "//label[contains(text(), 'Setuju')]/input[@type='radio']"),
            (By.XPATH, "//label[contains(text(), 'Setuju')]/preceding-sibling::input[@type='radio']"),
            (By.CSS_SELECTOR, "input[type='radio'][value='Setuju']"),
            (By.CSS_SELECTOR, "input[type='radio'][value='setuju']"),
        ]
        
        setuju_buttons = []
        
        # Coba berbagai selector
        for by, selector in setuju_selectors:
            try:
                buttons = driver.find_elements(by, selector)
                if buttons:
                    setuju_buttons = buttons
                    break
            except:
                continue
        
        # Jika tidak ditemukan dengan selector di atas, coba pendekatan lain
        if not setuju_buttons:
            # Cari semua radio button dan filter yang "Setuju"
            all_radios = driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")
            for radio in all_radios:
                try:
                    # Cek parent label atau sibling text
                    parent = radio.find_element(By.XPATH, "./..")
                    if parent and 'setuju' in parent.text.lower() and 'tidak' not in parent.text.lower():
                        setuju_buttons.append(radio)
                except:
                    pass
        
        if setuju_buttons:
            for button in setuju_buttons:
                try:
                    if not button.is_selected():
                        driver.execute_script("arguments[0].click();", button)
                        # time.sleep minimal antar klik radio
                        time.sleep(0.1)
                except:
                    pass
            
            print(f"    [SUCCESS] {len(setuju_buttons)} opsi 'Setuju' dipilih")
            return True
        else:
            print("    [WARNING] Radio button 'Setuju' tidak ditemukan")
            return True  # Lanjutkan proses meskipun tidak ada
            
    except Exception as e:
        print(f"    [ERROR] Gagal mengisi bagian Pendapat: {str(e)}")
        return False


def fill_saran_masukan_section(driver: webdriver.Chrome) -> bool:
    """
    Mengisi bagian Saran & Masukan dengan nilai hardcode.
    
    Returns:
        True jika berhasil, False jika gagal
    """
    try:
        filled_count = 0
        
        for field_name, value in SARAN_MASUKAN.items():
            # Cari input field berdasarkan label atau placeholder
            field_selectors = [
                (By.XPATH, f"//label[contains(text(), '{field_name}')]/following-sibling::input"),
                (By.XPATH, f"//label[contains(text(), '{field_name}')]/following-sibling::textarea"),
                (By.XPATH, f"//td[contains(text(), '{field_name}')]/following-sibling::td//input"),
                (By.XPATH, f"//td[contains(text(), '{field_name}')]/following-sibling::td//textarea"),
                (By.XPATH, f"//tr[contains(., '{field_name}')]//input"),
                (By.XPATH, f"//tr[contains(., '{field_name}')]//textarea"),
                (By.CSS_SELECTOR, f"input[placeholder*='{field_name}']"),
                (By.CSS_SELECTOR, f"textarea[placeholder*='{field_name}']"),
                (By.CSS_SELECTOR, f"input[name*='{field_name.lower().replace(' ', '_')}']"),
                (By.CSS_SELECTOR, f"textarea[name*='{field_name.lower().replace(' ', '_')}']"),
            ]
            
            field = None
            for by, selector in field_selectors:
                try:
                    field = driver.find_element(by, selector)
                    break
                except NoSuchElementException:
                    continue
            
            if field:
                field.clear()
                field.send_keys(value)
                filled_count += 1
                time.sleep(0.1)
        
        # Alternatif: isi semua input/textarea yang terlihat
        if filled_count == 0:
            # Cari semua input dan textarea dalam tabel Saran & Masukan
            all_inputs = driver.find_elements(By.CSS_SELECTOR, "table input[type='text'], table textarea")
            values_list = list(SARAN_MASUKAN.values())
            
            for idx, input_field in enumerate(all_inputs):
                if idx < len(values_list):
                    try:
                        input_field.clear()
                        input_field.send_keys(values_list[idx])
                        filled_count += 1
                        time.sleep(0.1)
                    except:
                        pass
        
        print(f"    [SUCCESS] {filled_count} field Saran & Masukan diisi")
        return True
        
    except Exception as e:
        print(f"    [ERROR] Gagal mengisi Saran & Masukan: {str(e)}")
        return False


def submit_form(driver: webdriver.Chrome) -> bool:
    """
    Klik tombol Kirim untuk submit formulir.
    
    Returns:
        True jika berhasil, False jika gagal
    """
    try:
        submit_selectors = [
            (By.XPATH, "//button[contains(text(), 'Kirim')]"),
            (By.XPATH, "//input[@value='Kirim']"),
            (By.XPATH, "//button[contains(text(), 'Submit')]"),
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.CSS_SELECTOR, "input[type='submit']"),
            (By.CSS_SELECTOR, ".btn-submit"),
            (By.CSS_SELECTOR, ".btn-kirim"),
        ]
        
        submit_button = None
        for by, selector in submit_selectors:
            try:
                submit_button = driver.find_element(by, selector)
                break
            except NoSuchElementException:
                continue
        
        if submit_button:
            driver.execute_script("arguments[0].click();", submit_button)
            time.sleep(1) # Sesuai kebutuhan website untuk sinkronisasi post-submit
            print("    [SUCCESS] Formulir berhasil dikirim")
            return True
        else:
            print("    [ERROR] Tombol Kirim tidak ditemukan")
            return False
            
    except Exception as e:
        print(f"    [ERROR] Gagal submit form: {str(e)}")
        return False


def check_already_filled(driver: webdriver.Chrome) -> bool:
    """
    Cek apakah user sudah pernah mengisi form sebelumnya.
    Mendeteksi keberadaan tombol 'Perbarui Tanggapan' atau halaman konfirmasi.
    
    Returns:
        True jika sudah pernah diisi, False jika belum
    """
    try:
        # Cari indikator bahwa form sudah diisi sebelumnya
        already_filled_selectors = [
            (By.XPATH, "//button[contains(text(), 'Perbarui Tanggapan')]"),
            (By.XPATH, "//a[contains(text(), 'Perbarui Tanggapan')]"),
            (By.XPATH, "//button[contains(text(), 'Perbarui')]"),
            (By.XPATH, "//*[contains(text(), 'Berikut tanggapan anda')]"),
            (By.XPATH, "//*[contains(text(), 'tanggapan anda')]"),
            (By.XPATH, "//table//td[contains(text(), 'Setuju') and not(contains(text(), 'Tidak'))]"),
        ]
        
        for by, selector in already_filled_selectors:
            try:
                elements = driver.find_elements(by, selector)
                if elements:
                    return True
            except:
                continue
        
        # Cek apakah tidak ada tombol Kirim (artinya sudah disubmit)
        try:
            kirim_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Kirim')]")
            return False  # Tombol Kirim ada, berarti belum diisi
        except NoSuchElementException:
            # Tidak ada tombol Kirim, cek apakah ada tombol Perbarui
            try:
                perbarui = driver.find_element(By.XPATH, "//*[contains(text(), 'Perbarui')]")
                return True
            except:
                pass
        
        return False
        
    except Exception as e:
        return False


def perform_logout(driver: webdriver.Chrome) -> bool:
    """
    Melakukan logout dari website.
    
    Returns:
        True jika berhasil, False jika gagal
    """
    try:
        logout_selectors = [
            (By.XPATH, "//a[contains(text(), 'Logout')]"),
            (By.XPATH, "//a[contains(text(), 'logout')]"),
            (By.XPATH, "//a[contains(text(), 'Keluar')]"),
            (By.XPATH, "//button[contains(text(), 'Logout')]"),
            (By.XPATH, "//button[contains(text(), 'Keluar')]"),
            (By.CSS_SELECTOR, "a[href*='logout']"),
            (By.CSS_SELECTOR, ".logout"),
            (By.CSS_SELECTOR, ".btn-logout"),
        ]
        
        logout_button = None
        for by, selector in logout_selectors:
            try:
                logout_button = driver.find_element(by, selector)
                break
            except NoSuchElementException:
                continue
        
        if logout_button:
            driver.execute_script("arguments[0].click();", logout_button)
            time.sleep(0.2)
            print("    [SUCCESS] Logout berhasil")
            return True
        else:
            # Jika tidak ada tombol logout, navigasi ke halaman utama
            driver.get(TARGET_URL)
            time.sleep(0.2)
            print("    [INFO] Tombol logout tidak ditemukan, kembali ke halaman utama")
            return True
            
    except Exception as e:
        print(f"    [ERROR] Gagal logout: {str(e)}")
        return False


def process_user(driver: webdriver.Chrome, username: str, password: str) -> tuple:
    """
    Proses lengkap untuk satu user: login -> cek sudah diisi -> isi form -> submit -> logout.
    
    Returns:
        Tuple (status: str, success: bool)
        - status: 'success', 'already_filled', 'failed'
        - success: True jika proses berjalan tanpa error
    """
    try:
        # Step 1: Login
        if not perform_login(driver, username, password):
            return ('failed', False)
        
        time.sleep(0.3)  # Dipercepat dari 0.5s
        
        # Step 2: Cek apakah sudah pernah mengisi
        if check_already_filled(driver):
            print("    [INFO] User sudah pernah mengisi form sebelumnya")
            perform_logout(driver)
            return ('already_filled', True)
        
        # Step 3: Isi bagian Pendapat (Radio Button Setuju)
        fill_pendapat_section(driver)
        
        time.sleep(0.3)
        
        # Step 4: Isi bagian Saran & Masukan
        fill_saran_masukan_section(driver)
        
        time.sleep(0.3)
        
        # Step 5: Submit formulir
        if not submit_form(driver):
            perform_logout(driver)
            return ('failed', False)
        
        time.sleep(0.1)  # Minimal jeda post-submit
        
        # Step 6: Logout
        perform_logout(driver)
        
        return ('success', True)
        
    except Exception as e:
        print(f"    [ERROR] Error saat memproses user: {str(e)}")
        return ('failed', False)


# ============================================
# MAIN FUNCTION
# ============================================
def main():
    """
    Fungsi utama untuk menjalankan otomatisasi.
    """
    print("=" * 60)
    print("RAT ONLINE FORM AUTOMATION")
    print("=" * 60)
    
    # Minta path file PDF dari user
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = input("\nMasukkan path file PDF: ").strip()
        if pdf_path.startswith('"') and pdf_path.endswith('"'):
            pdf_path = pdf_path[1:-1]
    
    # Validasi file
    print(f"\n[INFO] Membaca file PDF: {pdf_path}")
    
    # Ekstrak data user dari PDF
    users = extract_users_from_pdf(pdf_path)
    
    if not users:
        print("\n[ERROR] Tidak ada data user yang ditemukan!")
        print("Pastikan PDF memiliki tabel dengan kolom 'Username' dan 'Password'")
        return
    
    print(f"\n[INFO] Memulai proses otomatisasi untuk {len(users)} user...")
    print("-" * 60)
    
    # Setup driver
    driver = None
    success_count = 0
    already_filled_count = 0
    fail_count = 0
    
    try:
        driver = setup_driver()
        
        for idx, user in enumerate(users, 1):
            username = user['username']
            password = user['password']
            
            print(f"\n[{idx}/{len(users)}] Memproses User: {username}")
            print("-" * 40)
            
            try:
                status, success = process_user(driver, username, password)
                
                if status == 'success':
                    print(f"\n✓ Proses User [{username}] Selesai")
                    success_count += 1
                elif status == 'already_filled':
                    print(f"\n⊘ User [{username}] SUDAH PERNAH DIISI - Dilewati")
                    already_filled_count += 1
                else:
                    print(f"\n✗ Gagal pada User [{username}]")
                    fail_count += 1
            except Exception as e:
                print(f"\n✗ Gagal pada User [{username}]: {str(e)}")
                fail_count += 1
            
            # Jeda antar user
            if idx < len(users):
                print(f"\n[INFO] Menunggu {WAIT_BETWEEN_USERS} detik sebelum user berikutnya...")
                time.sleep(WAIT_BETWEEN_USERS)
    
    except Exception as e:
        print(f"\n[FATAL ERROR] {str(e)}")
    
    finally:
        if driver:
            driver.quit()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total User       : {len(users)}")
    print(f"Berhasil Diisi   : {success_count}")
    print(f"Sudah Pernah Isi : {already_filled_count}")
    print(f"Gagal            : {fail_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
