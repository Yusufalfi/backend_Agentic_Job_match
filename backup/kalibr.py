import json
import time
import httpx

base_url = "https://www.kalibrr.id/_next/data/MxsQ6kfNqrKsqzy4Vn9An/id-ID/home/te/wherehouse.json"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

extracted_jobs = []
target_limit = 50
limit_per_request = 15
offset = 0

# Ubah bagian ini di dalam worker/kalibrr_scraper.py:
async with httpx.AsyncClient(headers=headers, timeout=30.0, verify=False) as client:
    while len(extracted_jobs) < target_limit:
        params = {
            "param": ["te", "wherehouse"],
            "limit": limit_per_request,
            "offset": offset
        }
        
        try:
            response = client.get(base_url, params=params)
            if response.status_code != 200:
                print(f"Gagal dengan status: {response.status_code}")
                break
                
            data = response.json()
            page_props = data.get("pageProps", {})
            jobs = page_props.get("jobs", [])
            
            if not jobs:
                break
                
            for job in jobs:
                if len(extracted_jobs) >= target_limit:
                    break
                
                # Lokasi
                loc = job.get("googleLocation", {}).get("addressComponents", {})
                city = loc.get("city", "")
                region = loc.get("region", "")
                location_str = f"{city}, {region}".strip(", ")
                
                # Gaji
                base_sal = job.get("baseSalary")
                max_sal = job.get("maximumSalary")
                currency = job.get("salaryCurrency", "IDR")
                if base_sal or max_sal:
                    salary_str = f"{base_sal} - {max_sal} {currency}"
                else:
                    salary_str = "Tidak disebutkan"

                # URL Lowongan
                job_id = job.get("id")
                slug = job.get("slug")
                comp_code = job.get("company", {}).get("code")
                job_url = f"https://www.kalibrr.id/c/{comp_code}/jobs/{job_id}/{slug}" if (slug and comp_code) else "-"

                job_data = {
                    "job_title": job.get("name"),
                    "company_name": job.get("companyName"),
                    "location": location_str,
                    "salary": salary_str,
                    "tenure": job.get("tenure"),
                    "description": job.get("description"),
                    "qualifications": job.get("qualifications"),
                    "skills": job.get("jobSdsSkills", []),
                    "url": job_url
                }
                
                extracted_jobs.append(job_data)
                    
            offset += len(jobs)
            print(f"Berhasil mengumpulkan {len(extracted_jobs)} data...")
            time.sleep(1.5)
            
        except httpx.ReadTimeout:
            print("Request timeout, mencoba ulang...")
            time.sleep(3)
            continue

# Simpan ke file JSON
output_filename = "kalibrr_jobs.json"
with open(output_filename, "w", encoding="utf-8") as f:
    json.dump(extracted_jobs, f, ensure_ascii=False, indent=4)

print(f"\nSelesai! {len(extracted_jobs)} data berhasil disimpan ke file '{output_filename}'.")