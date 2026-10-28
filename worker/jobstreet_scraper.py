import asyncio
import re
import logging
import os
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

# ==========================================
# KONFIGURASI SISTEM LOGGING
# ==========================================
# Memastikan folder 'logs' ada sebelum membuat file log
os.makedirs("logs", exist_ok=True)

# Mengatur format log agar mencatat waktu, level (INFO/ERROR), dan pesan
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/scraper.log", encoding="utf-8"), # Catat ke file logs/scraper.log
        logging.StreamHandler()                                   # Tampilkan juga ke terminal/konsol
    ]
)

SELECTORS = {
    "job_card": "article",
    "title": "h3 a, [data-automation='jobTitle']",
    "company": "[data-automation='jobCompany']",
    "salary": "[data-automation='jobSalary']",
    "location": "[data-automation='jobLocation']",
    "teaser": "[data-automation='jobShortDescription']",
    # Perbaikan: Menggunakan beberapa alternatif selector untuk container deskripsi JobStreet
    "detail_container": "div[data-automation='jobAdDetails'], div[class*='job-details'], main div section",
    # "work_type": "[data-automation='job-work-type']",
    "work_type": "[data-automation='job-detail-work-type'], [data-automation='job-work-type']", #  selector yang benar sesuai inspect
    "next_button": "a[aria-label='Next']"
}

BASE_URL = "https://www.jobstreet.co.id"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

class JobStreetScraper:
    def __init__(self, date_code: str = "14", max_limit: int = 10, max_concurrent_tabs: int = 5):
        """
        Inisialisasi Scraper JobStreet.
        :param date_code: Filter rentang tanggal dalam hari (default '14' hari terakhir)
        :param max_limit: Batasan maksimal jumlah lowongan yang ingin ditarik per role
        :param max_concurrent_tabs: Batasan jumlah tab browser yang dibuka bersamaan (asinkron)
        """
        self.date_code = date_code
        self.max_limit = max_limit
        self.visited_urls = set()  # Set untuk melacak URL yang sudah dikunjungi agar tidak duplikat di sesi ini
        self.max_concurrent_tabs = max_concurrent_tabs

    def build_url(self, role: str) -> str:
        """
        Membangun URL target pencarian JobStreet secara dinamis 
        berdasarkan role/keyword dan filter rentang tanggal (daterange).
        """
        formatted_query = role.strip().replace(" ", "-")
        url_params = []

        if self.date_code:
            url_params.append(f"daterange={self.date_code}")

        query_string = "&".join(url_params)
        target_url = f"{BASE_URL}/id/{formatted_query}-jobs"
        if query_string:
            target_url += f"?{query_string}"

        return target_url

    def parse_posted_date(self, date_text: str) -> str:
        """
        Normalisasi Teks Tanggal (Sesuai BRD FR-03):
        Mengubah teks relatif seperti '3 hari lalu' atau 'baru saja' menjadi format tanggal standar (YYYY-MM-DD).
        """
        if not date_text or date_text == "N/A":
            return datetime.now().strftime("%Y-%m-%d")

        text_lower = date_text.lower().strip()
        now = datetime.now()

        # Mencari pola angka diikuti kata 'hari' atau 'day'
        days_match = re.search(r'(\d+)\s*(hari|d\b|day)', text_lower)
        if days_match:
            days_ago = int(days_match.group(1))
            target_date = now - timedelta(days=days_ago)
            return target_date.strftime("%Y-%m-%d")

        # Jika diposting dalam hitungan jam atau menit yang lalu
        if any(unit in text_lower for unit in ["jam", "j lalu", "menit", "m lalu", "hour", "min"]):
            return now.strftime("%Y-%m-%d")

        return now.strftime("%Y-%m-%d")

    async def scrape_detail_task(self, context, semaphore, job_item, index: int, total: int, progress_tracker: dict):
        """
        Worker Asinkron per Tab: 
        Membuka halaman detail lowongan secara paralel menggunakan Semaphore agar 
        proses penarikan deskripsi lengkap menjadi jauh lebih cepat dan aman dari crash.
        """
        async with semaphore:
            logging.info(f"[DETAIL] Membuka tab ({index}/{total}): {job_item['title'][:30]}...")
            
            page = None
            full_description, work_type, raw_posted_date = "N/A", "N/A", ""

            try:
                page = await context.new_page()
                # Membuka link detail lowongan dengan batas waktu maksimal 15 detik
                await page.goto(job_item["url"], wait_until="domcontentloaded", timeout=15000)

                # Mengambil teks deskripsi lengkap lowongan
                details_el = await page.query_selector(SELECTORS["detail_container"])
                if details_el:
                    full_description = await details_el.inner_text()

                # Mengambil jenis pekerjaan (Full-time, Kontrak, dll)
                work_type_el = await page.query_selector(SELECTORS["work_type"])
                if work_type_el:
                    work_type = await work_type_el.inner_text()

                # Mengambil informasi tanggal posting asli dari halaman detail
                date_el = await page.query_selector('span:has-text("Diposting"), span:has-text("Diiklankan")')
                if date_el:
                    raw_posted_date = await date_el.inner_text()

            except Exception as e:
                # Error handling per-tab: jika satu lowongan gagal, tab lain tetap berjalan aman
                logging.warning(f"[WARNING] Gagal memuat detail lowongan [{job_item['title'][:20]}]: {e}")
            finally:
                if page:
                    await page.close()  # Pastikan tab selalu ditutup untuk membebaskan memori

            # Memasukkan hasil ekstraksi ke dalam dictionary job_item
            job_item["date_posted"] = self.parse_posted_date(raw_posted_date)
            job_item["description"] = full_description.strip()
            job_item["work_type"] = work_type.strip()

            # Melacak progres pengerjaan tab
            progress_tracker["completed"] += 1
            logging.info(f"[PROGRES] Selesai {progress_tracker['completed']}/{total} | {job_item['title'][:25]}")

    async def _clean_modals(self, page):
        """
        Membersihkan pop-up login, dialog persetujuan, atau latar belakang gelap (backdrop)
        yang sering muncul secara tiba-tiba di JobStreet agar tidak menghalangi klik otomatis.
        """
        await page.evaluate("""
            () => {
                const modals = document.querySelectorAll('div[role="dialog"], [data-automation="auth-modal"]');
                modals.forEach(el => el.remove());
                const backdrops = document.querySelectorAll('div[class*="backdrop"], div[class*="overlay"]');
                backdrops.forEach(el => el.remove());
                document.body.style.overflow = 'unset';
            }
        """)

    async def run(self, target_roles: list) -> list:
        """
        Fungsi Utama Menjalankan Scraper:
        Menerima daftar 'target_roles' dari profile.json, lalu melakukan iterasi 
        pencarian, pembukaan browser, scrolling, ekstraksi kartu, hingga pagination.
        """
        all_scraped_jobs = []

        logging.info(f"=== MEMULAI SCRAPING UNTUK ROLE: {target_roles} ===")
        logging.info(f"Maksimal Limit Data per Role: {self.max_limit}")

        async with async_playwright() as p:
            # Menjalankan browser Chromium (headless=False agar jendela browser terlihat saat pengembangan/dev)
            browser = await p.chromium.launch(
                headless=False, # Set ke True jika nanti ingin jalan di background tanpa GUI (untuk Task Scheduler)
                ignore_default_args=["--enable-automation"],
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                    "--no-sandbox",
                    "--disable-setuid-sandbox"
                ]
            )

            context = await browser.new_context(user_agent=USER_AGENT, viewport=None)
            # Menyamarkan browser agar tidak terdeteksi sebagai bot otomatisasi
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            page = await context.new_page()

            try:
                # Melakukan perulangan (looping) untuk setiap role yang ada di profile.json
                for role in target_roles:
                    target_url = self.build_url(role)
                    logging.info(f"\n--- Memproses Role: '{role}' ---")
                    logging.info(f"Target URL: {target_url}")

                    try:
                        # Membuka halaman pencarian
                        await page.goto(target_url, wait_until="domcontentloaded")
                        await page.wait_for_timeout(1500)
                        await self._clean_modals(page)

                        await page.wait_for_selector(SELECTORS["job_card"], timeout=10000)
                        page_number = 1
                        role_jobs_count = 0

                        # Loop utama untuk menangani pagination (pindah halaman) per role
                        while True:
                            logging.info(f"--- Memindai Halaman {page_number} untuk role '{role}' ---")

                            # Melakukan scrolling otomatis ke bawah untuk memuat seluruh kartu lowongan (lazy loading)
                            previous_height = 0
                            while True:
                                await page.evaluate("window.scrollBy(0, 500);")
                                await page.wait_for_timeout(300)
                                new_height = await page.evaluate("document.body.scrollHeight")
                                if new_height == previous_height:
                                    break
                                previous_height = new_height

                            # Mengambil semua elemen kartu lowongan yang tampak di halaman
                            job_cards = await page.query_selector_all(SELECTORS["job_card"])
                            logging.info(f"Ditemukan {len(job_cards)} kartu lowongan pada halaman ini.")

                            page_jobs = []
                            for card in job_cards:
                                # Berhenti jika kuota target maksimal per role sudah tercapai
                                if role_jobs_count + len(page_jobs) >= self.max_limit:
                                    break

                                # Mengambil ID unik lowongan
                                job_id = await card.get_attribute("data-job-id")
                                if not job_id:
                                    link_el = await card.query_selector("a[href*='/job/']")
                                    if link_el:
                                        href = await link_el.get_attribute("href")
                                        job_id = href.split("/job/")[-1].split("?")[0] if "/job/" in href else None

                                if not job_id:
                                    continue

                                full_link = f"{BASE_URL}/id/job/{job_id}?type=standard&ref=search-standalone&origin=card"
                                
                                # Cek duplikat URL di sesi berjalan
                                if full_link in self.visited_urls:
                                    continue
                                self.visited_urls.add(full_link)

                                # Mengambil data dasar dari kartu lowongan
                                title_el = await card.query_selector(SELECTORS["title"])
                                title = await title_el.inner_text() if title_el else "Unknown"

                                company_el = await card.query_selector(SELECTORS["company"])
                                company = await company_el.inner_text() if company_el else "Unknown"

                                salary_el = await card.query_selector(SELECTORS["salary"])
                                salary = await salary_el.inner_text() if salary_el else "Unknown"

                                location_els = await card.query_selector_all(SELECTORS["location"])
                                locations = [await loc.inner_text() for loc in location_els]
                                location_str = ", ".join(locations).strip() if locations else "Unknown"

                                # Menyimpan data terstruktur sementara (Normalisasi Kolom sesuai BRD FR-03)
                                page_jobs.append({
                                    "job_id": job_id,
                                    "search_role": role,
                                    "title": title.strip(),
                                    "company": company.strip(),
                                    "salary_text": salary.strip() if salary else "Unknown",
                                    "location": location_str,
                                    "url": full_link,
                                    "evaluation_status": "NEW",
                                    # "notification_status": "NOT_REQUIRED"
                                })

                            # Menjalankan ekstraksi detail deskripsi secara paralel (Asinkron dengan Semaphore)
                            if page_jobs:
                                semaphore = asyncio.Semaphore(self.max_concurrent_tabs)
                                progress_tracker = {"completed": 0}
                                total_jobs_in_page = len(page_jobs)

                                tasks = [
                                    self.scrape_detail_task(context, semaphore, job, idx, total_jobs_in_page, progress_tracker)
                                    for idx, job in enumerate(page_jobs, 1)
                                ]
                                await asyncio.gather(*tasks)
                                all_scraped_jobs.extend(page_jobs)
                                role_jobs_count += len(page_jobs)

                            # Cek apakah target limit total untuk role ini sudah terpenuhi
                            if role_jobs_count >= self.max_limit:
                                logging.info(f"Target batas maksimal data untuk role '{role}' tercapai ({role_jobs_count} items).")
                                break

                            # Mengecek keberadaan tombol 'Next' untuk pindah ke halaman berikutnya
                            next_button = await page.query_selector(SELECTORS["next_button"])
                            if not next_button:
                                logging.info(f"Tombol 'Next' tidak ditemukan untuk role '{role}'. Berarti sudah di halaman terakhir.")
                                break

                            await next_button.click()
                            await page.wait_for_load_state("networkidle")
                            page_number += 1

                    except Exception as role_err:
                        logging.error(f"Gagal memproses role '{role}': {role_err}")
                        continue

            except Exception as e:
                logging.error(f"Terjadi kesalahan fatal saat proses scraping: {e}")
            finally:
                await browser.close()
                logging.info(f"=== SCRAPING SELESAI. Total keseluruhan data terkumpul: {len(all_scraped_jobs)} ===")

        return all_scraped_jobs