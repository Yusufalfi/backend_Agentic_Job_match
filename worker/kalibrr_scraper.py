import httpx
import logging
from bs4 import BeautifulSoup
from datetime import datetime

class KalibrrScraper:
    def __init__(self, target_limit: int = 10):
        self.target_limit = target_limit
        # Build ID Next.js Kalibrr saat ini
        self.build_id = "MxsQ6kfNqrKsqzy4Vn9An"

    def clean_html_to_text(self, html_content: str) -> str:
        """Membersihkan tag HTML dari deskripsi dan kualifikasi Kalibrr."""
        if not html_content:
            return "N/A"
        soup = BeautifulSoup(html_content, "html.parser")
        return soup.get_text(separator=" ", strip=True)

    async def run(self, target_roles: list) -> list:
        """
        Menjalankan penarikan lowongan dari Kalibrr secara sekuensial (satu role disikat sampai habis, 
        baru lanjut ke role berikutnya) menggunakan Next.js JSON endpoint.
        """
        extracted_jobs = []
        limit_per_role = self.target_limit  # Target kuota maksimal per masing-masing role
        
        logging.info(f"=== MEMULAI SCRAPING KALBRR SECARA SEKUENSIAL UNTUK ROLE: {target_roles} ===")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }

        # Menggunakan verify=False untuk bypass masalah SSL di lingkungan lokal
        async with httpx.AsyncClient(headers=headers, timeout=30.0, verify=False) as client:
            for role in target_roles:
                role_slug = role.strip().lower().replace(" ", "-")
                api_url = f"https://www.kalibrr.id/_next/data/{self.build_id}/id-ID/home/te/{role_slug}.json"
                
                offset = 0
                limit_per_request = 15
                role_collected = 0
                
                logging.info(f"\n--- [KALBRR] MULAI MENARIK ROLE: '{role}' (Target: {limit_per_role} lowongan) ---")

                while role_collected < limit_per_role:
                    params = {
                        "param": ["te", role_slug],
                        "limit": limit_per_request,
                        "offset": offset
                    }
                    
                    try:
                        response = await client.get(api_url, params=params)
                        
                        if response.status_code != 200:
                            logging.warning(f"Gagal mengambil Kalibrr untuk role '{role}', status: {response.status_code}")
                            break
                            
                        data = response.json()
                        page_props = data.get("pageProps", {})
                        jobs = page_props.get("jobs", [])
                        
                        if not jobs:
                            logging.info(f"Lowongan untuk role '{role}' sudah habis di offset {offset}.")
                            break
                            
                        batch_added = 0
                        for job in jobs:
                            if role_collected >= limit_per_role:
                                break
                            
                            # 1. Parsing Lokasi
                            loc = job.get("googleLocation", {}).get("addressComponents", {})
                            city = loc.get("city", "")
                            region = loc.get("region", "")
                            location_str = f"{city}, {region}".strip(", ") or "Indonesia"
                            
                            # 2. Parsing Gaji
                            base_sal = job.get("baseSalary")
                            max_sal = job.get("maximumSalary")
                            currency = job.get("salaryCurrency", "IDR")
                            if base_sal and max_sal:
                                salary_str = f"{base_sal} - {max_sal} {currency}"
                            elif base_sal:
                                salary_str = f"Min {base_sal} {currency}"
                            else:
                                salary_str = "Tidak disebutkan"

                            # 3. URL Lowongan
                            job_id = str(job.get("id"))
                            slug = job.get("slug")
                            comp_code = job.get("company", {}).get("code")
                            job_url = f"https://www.kalibrr.id/c/{comp_code}/jobs/{job_id}/{slug}" if (slug and comp_code) else f"https://www.kalibrr.com/jobs/{job_id}"

                            # 4. Cleaning HTML Deskripsi
                            raw_desc = job.get("description", "")
                            raw_qual = job.get("qualifications", "")
                            combined_text = f"{raw_desc}\n{raw_qual}"
                            cleaned_description = self.clean_html_to_text(combined_text)

                            job_data = {
                                "job_id": f"kalibrr_{job_id}",
                                "search_role": role,
                                "title": job.get("name", "Unknown").strip(),
                                "company": job.get("companyName", "Unknown").strip(),
                                "salary_text": salary_str,
                                "location": location_str,
                                "url": job_url,
                                "description": cleaned_description,
                                "work_type": job.get("tenure", "Full time"),
                                "date_posted": datetime.now().strftime("%Y-%m-%d"),
                                "evaluation_status": "NEW",
                                # "notification_status": "NOT_REQUIRED"
                            }
                            
                            # Cek duplikat global agar tidak ada lowongan kembar
                            if not any(j["job_id"] == job_data["job_id"] for j in extracted_jobs):
                                extracted_jobs.append(job_data)
                                role_collected += 1
                                batch_added += 1
                        
                        logging.info(f"Role '{role}': Berhasil mengambil {role_collected}/{limit_per_role} lowongan (Offset: {offset})")
                        
                        if batch_added == 0 or len(jobs) < limit_per_request:
                            break
                            
                        offset += limit_per_request
                            
                    except httpx.ReadTimeout:
                        logging.warning("Request Kalibrr timeout, mencoba ulang...")
                        continue
                    except Exception as e:
                        logging.error(f"Error pada Kalibrr scraper untuk role '{role}': {e}")
                        break

        logging.info(f"\n=== SCRAPING KALBRR SELESAI. Total keseluruhan terkumpul: {len(extracted_jobs)} ===")
        return extracted_jobs