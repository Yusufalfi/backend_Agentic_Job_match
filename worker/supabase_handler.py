# import os
# import logging
# from dotenv import load_dotenv
# import requests
# import urllib3

# urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# load_dotenv()

# class SupabaseHandler:
#     def __init__(self):
#         self.supabase_url = os.getenv("SUPABASE_URL")
#         self.supabase_key = os.getenv("SUPABASE_KEY")
        
#         if not self.supabase_url or not self.supabase_key:
#             logging.warning("SUPABASE_URL atau SUPABASE_KEY tidak ditemukan di file .env!")
#             self.is_active = False
#         else:
#             self.is_active = True
#             base_url = self.supabase_url.rstrip("/")
#             self.jobs_endpoint = f"{base_url}/rest/v1/job_opportunities"
#             self.users_endpoint = f"{base_url}/rest/v1/users"
            
#             self.headers = {
#                 "apikey": self.supabase_key,
#                 "Authorization": f"Bearer {self.supabase_key}",
#                 "Content-Type": "application/json",
#                 "Prefer": "resolution=merge-duplicates"
#             }
#             logging.info("SupabaseHandler berhasil diinisialisasi.")

#     def save_jobs(self, jobs: list, user_id: int = None) -> int:
#         """Menyimpan list lowongan ke tabel 'job_opportunities'."""
#         if not self.is_active:
#             return 0

#         saved_count = 0
#         for job in jobs:
#             try:
#                 # Salin dictionary job agar aman dimodifikasi
#                 job_data = job.copy()
#                 # Masukkan user_id jika ada
#                 if user_id:
#                     job_data["user_id"] = user_id
                
#                 # Pemetaan: Ubah key 'salary_text' dari scraper ke kolom 'salary' milik database
#                 if "salary_text" in job_data:
#                     job_data["salary"] = job_data.pop("salary_text")

#                 response = requests.post(
#                     self.jobs_endpoint,
#                     json=job_data,
#                     headers=self.headers,
#                     verify=False,
#                     timeout=10
#                 )
#                 if response.status_code in [200, 201, 204]:
#                     saved_count += 1
#                 else:
#                     logging.error(f"Gagal simpan job_id {job_data.get('job_id')}: {response.text}")
#             except Exception as e:
#                 logging.error(f"Gagal menyimpan job_id {job.get('job_id')}: {e}")

#         logging.info(f"Berhasil menyinkronkan {saved_count} dari {len(jobs)} lowongan ke Supabase.")
#         return saved_count

#     def fetch_target_roles(self) -> list:
#         """Mengambil target_roles secara dinamis dari tabel 'users' di Supabase."""
#         if not self.is_active:
#             return ["python developer", "ai automation"] # Fallback default

#         try:
#             # Ambil data dari tabel users
#             response = requests.get(
#                 f"{self.users_endpoint}?select=target_roles",
#                 headers=self.headers,
#                 verify=False,
#                 timeout=10
#             )
#             if response.status_code == 200:
#                 users_data = response.json()
#                 if users_data and "target_roles" in users_data[0]:
#                     roles = users_data[0]["target_roles"]
#                     if roles:
#                         logging.info(f"Berhasil memuat target_roles dinamis dari database: {roles}")
#                         return roles
#             logging.warning("Gagal memuat target_roles dari DB, menggunakan default hardcoded.")
#         except Exception as e:
#             logging.error(f"Terjadi kesalahan saat fetch target_roles: {e}")
            
#         return ["python developer", "ai automation"]


import os
import logging
from dotenv import load_dotenv
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class SupabaseHandler:
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            logging.warning("SUPABASE_URL atau SUPABASE_KEY tidak ditemukan di file .env!")
            self.is_active = False
        else:
            self.is_active = True
            base_url = self.supabase_url.rstrip("/")
            self.jobs_endpoint = f"{base_url}/rest/v1/job_opportunities"
            self.users_endpoint = f"{base_url}/rest/v1/users"
            
            self.headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates"
            }
            logging.info("SupabaseHandler berhasil diinisialisasi.")

    def save_jobs(self, jobs: list, user_id: int = None) -> int:
        """Menyimpan list lowongan ke tabel 'job_opportunities' lengkap dengan user_id."""
        if not self.is_active:
            return 0

        saved_count = 0
        for job in jobs:
            try:
                job_data = job.copy()
                
                # Masukkan user_id jika ada
                if user_id:
                    job_data["user_id"] = user_id
                
                # Mapping salary_text ke salary jika diperlukan
                if "salary_text" in job_data:
                    job_data["salary"] = job_data.pop("salary_text")

                response = requests.post(
                    self.jobs_endpoint,
                    json=job_data,
                    headers=self.headers,
                    verify=False,
                    timeout=10
                )
                if response.status_code in [200, 201, 204]:
                    saved_count += 1
                else:
                    logging.error(f"Gagal simpan job_id {job_data.get('job_id')}: {response.text}")
            except Exception as e:
                logging.error(f"Gagal menyimpan job_id {job.get('job_id')}: {e}")

        logging.info(f"Berhasil menyinkronkan pencatatan {saved_count} dari {len(jobs)} lowongan ke Supabase.")
        return saved_count

    def fetch_user_profile(self) -> dict:
        """Mengambil data user (id dan target_roles) secara dinamis dari tabel 'users'."""
        default_profile = {
            "user_id": None,
            "target_roles": ["python developer", "ai automation"]
        }
        if not self.is_active:
            return default_profile

        try:
            response = requests.get(
                f"{self.users_endpoint}?select=id,target_roles",
                headers=self.headers,
                verify=False,
                timeout=10
            )
            if response.status_code == 200:
                users_data = response.json()
                if users_data and len(users_data) > 0:
                    user = users_data[0]
                    profile = {
                        "user_id": user.get("id"),
                        "target_roles": user.get("target_roles", default_profile["target_roles"])
                    }
                    logging.info(f"Berhasil memuat profil user dari DB -> User ID: {profile['user_id']}, Roles: {profile['target_roles']}")
                    return profile
            
            logging.warning("Gagal memuat profil user dari DB, menggunakan default fallback.")
        except Exception as e:
            logging.error(f"Terjadi kesalahan saat fetch user profile: {e}")
            
        return default_profile

    def fetch_target_roles(self) -> list:
        """Fungsi fallback untuk kompatibilitas jika terpanggil."""
        profile = self.fetch_user_profile()
        return profile["target_roles"]