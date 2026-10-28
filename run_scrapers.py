# import asyncio
# import logging
# from worker.jobstreet_scraper import JobStreetScraper
# from worker.kalibrr_scraper import KalibrrScraper
# from worker.job_filter import JobFilter
# from worker.supabase_handler import SupabaseHandler

# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s [%(levelname)s] %(message)s",
#     handlers=[logging.StreamHandler()]
# )

# async def main():
#     logging.info("=== MEMULAI ORKESTRASI MULTI-PORTAL SCRAPER & PIPELINE ===")
    
#     # Inisialisasi Handler & Scraper
#     db_handler = SupabaseHandler()
#     job_filter = JobFilter()
    
#     # AMBIL PROFIL USER SECARA DINAMIS (Dapat user_id & target_roles sekaligus)
#     # Pastikan SupabaseHandler punya method fetch_user_profile() atau fetch_target_roles yang mengembalikan user_id
#     user_profile = db_handler.fetch_user_profile()  # Mengembalikan dict misal: {"user_id": 1, "target_roles": [...]}
#     user_id = user_profile.get("user_id")
#     target_roles = user_profile.get("target_roles", ["python developer", "ai automation"])
    
#     logging.info(f"User ID aktif: {user_id}")
#     logging.info(f"Target roles aktif: {target_roles}")

#     target_limit_per_portal = 20
#     jobstreet = JobStreetScraper()
#     kalibrr = KalibrrScraper()

#     # Jalankan Scraping Paralel
#     js_jobs, kl_jobs = await asyncio.gather(
#         jobstreet.run(target_roles),
#         kalibrr.run(target_roles)
#     )

#     all_raw_jobs = js_jobs + kl_jobs
#     logging.info(f"Total keseluruhan data mentah terkumpul: {len(all_raw_jobs)}")

#     # Deterministic Filter
#     valid_jobs = job_filter.filter_jobs(all_raw_jobs)

#     # Simpan ke tabel 'job_opportunities' di Supabase dengan menyertakan user_id
#     db_handler.save_jobs(valid_jobs, user_id=user_id)
#     logging.info("=== ORKESTRASI & PIPELINE SELESAI ===")

# if __name__ == "__main__":
#     asyncio.run(main())




import asyncio
import logging
import time
from worker.jobstreet_scraper import JobStreetScraper
from worker.kalibrr_scraper import KalibrrScraper
from worker.job_filter import JobFilter
from worker.supabase_handler import SupabaseHandler
from backend.evaluator import JobEvaluator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

async def main():
    logging.info("=== MEMULAI ORKESTRASI MULTI-PORTAL SCRAPER & PIPELINE ===")
    
    db_handler = SupabaseHandler()
    job_filter = JobFilter()
    
    # 1. Ambil profil user secara dinamis
    user_profile = db_handler.fetch_user_profile() 
    user_id = user_profile.get("user_id")
    target_roles = user_profile.get("target_roles", ["python developer", "ai automation"])
    
    logging.info(f"User ID aktif: {user_id}")
    logging.info(f"Target roles aktif: {target_roles}")

    jobstreet = JobStreetScraper()
    kalibrr = KalibrrScraper()

    # 2. Scraping Paralel
    js_jobs, kl_jobs = await asyncio.gather(
        jobstreet.run(target_roles),
        kalibrr.run(target_roles)
    )

    all_raw_jobs = js_jobs + kl_jobs
    logging.info(f"Total keseluruhan data mentah terkumpul: {len(all_raw_jobs)}")

    # 3. Filter data
    valid_jobs = job_filter.filter_jobs(all_raw_jobs)

    # 4. Simpan ke Supabase dan tangkap ID-nya
    saved_jobs = db_handler.save_jobs(valid_jobs, user_id=user_id)
    logging.info("Penyimpanan lowongan ke Supabase selesai.")

    # ==========================================================
    # 5. PROSES EVALUASI AI (GROQ) & JEDA WAKTU (RATE LIMIT AMAN)
    # ==========================================================
    logging.info("=== MEMULAI PROSES EVALUASI AI (GROQ) ===")
    
    evaluator = JobEvaluator(user_row=user_profile)

    for job in saved_jobs:
        title = job.get('title', 'Tanpa Judul')
        job_id = job.get('id')  # ID unik dari database Supabase
        
        if not job_id:
            logging.warning(f"  ⚠️ Lewati evaluasi untuk [{title}], ID database tidak ditemukan.")
            continue

        # Jalankan evaluasi AI Groq
        score, reason = evaluator.evaluate_job(job=job)

        if score >= 75:  
            evaluation_status = "MATCHED"
            logging.info(f"  ✅ MATCHED ({score}) | {title}")
        else:
            evaluation_status = "REJECTED"
            logging.info(f"  ❌ REJECTED ({score}) | {title}")

        # Update ke Supabase menggunakan nama kolom asli (ai_score, ai_reason, evaluation_status)
        db_handler.update_job_evaluation(
            job_id=job_id,
            evaluation_status=evaluation_status,
            ai_score=score,
            ai_reason=reason
        )
        
        # Jeda 3 detik per lowongan agar tidak terkena Groq Rate Limit (Error 429)
        time.sleep(3)
        
        # TODO: Trigger kirim notifikasi Telegram ke user di sini jika evaluation_status == "MATCHED"

    logging.info("=== ORKESTRASI & PIPELINE SELESAI ===")

if __name__ == "__main__":
    asyncio.run(main())