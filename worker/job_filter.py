import logging

class JobFilter:
    def __init__(self):
        # Kata kunci yang ingin di-skip (bisa disesuaikan)
        self.excluded_keywords = [
            "intern", 
            "magang", 
            "unpaid", 
            "volunteer"
        ]

    def is_valid_job(self, job: dict) -> bool:
        """
        Menyaring lowongan berdasarkan kriteria deterministik.
        Mengembalikan True jika lolos, False jika dibuang.
        """
        title = job.get("title", "").lower()
        description = job.get("description", "").lower()
        
        # Cek apakah judul mengandung kata terlarang
        for keyword in self.excluded_keywords:
            if keyword in title:
                logging.info(f"Filtered out (Keyword '{keyword}' in title): {job.get('title')}")
                return False
                
        # Pastikan field wajib ada
        if not job.get("title") or not job.get("url") or not job.get("company"):
            return False
            
        return True

    def filter_jobs(self, jobs: list) -> list:
        """Menyaring sekumpulan list lowongan."""
        valid_jobs = []
        for job in jobs:
            if self.is_valid_job(job):
                valid_jobs.append(job)
        
        logging.info(f"Filtering selesai. Lolos: {len(valid_jobs)} dari {len(jobs)} total lowongan mentah.")
        return valid_jobs