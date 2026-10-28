import os
import json
import logging
import time

# Membantu Python menggunakan sertifikat tepercaya dari Windows
import truststore
truststore.inject_into_ssl()

from groq import Groq, RateLimitError


class JobEvaluator:
    def __init__(self, user_row: dict):
        # user_row adalah 1 baris (row) data dari tabel public.users Supabase lu
        self.user = user_row or {}
        
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY belum diatur. Periksa file .env."
            )

        self.client = Groq(
            api_key=api_key,
            max_retries=0,
            timeout=60.0,
        )

        # Menggunakan model Groq yang tersedia di akun lu
        self.model_name = "openai/gpt-oss-20b"

    def evaluate_job(self, job: dict) -> tuple[int, str]:
        # Ekstraksi data dari kolom Supabase secara aman
        candidate_name = self.user.get("full_name", "Kandidat")
        target_roles = self.user.get("target_roles", [])
        parsed_skills = self.user.get("parsed_skills", "Tidak disebutkan")
        
        # Amankan format target_roles jika berupa string JSON
        if isinstance(target_roles, str):
            try:
                target_roles = json.loads(target_roles)
            except:
                target_roles = [target_roles]

        # Membungkus profil kandidat dalam format JSON yang bersih untuk dibaca AI
        profile_dict = {
            "name": candidate_name,
            "target_roles": target_roles,
            "skills_and_experience": parsed_skills
        }
        profile_json = json.dumps(profile_dict, ensure_ascii=False, indent=2)

        # Membungkus data lowongan ke format JSON
        job_dict = {
            "title": job.get('title', 'Tidak diketahui'),
            "company": job.get('company', 'Tidak diketahui'),
            "location": job.get('location', 'Tidak diketahui'),
            "salary": job.get('salary_text', job.get('salary', 'Tidak diketahui')),
            "description": str(job.get('description', ''))[:8000]
        }
        job_json = json.dumps(job_dict, ensure_ascii=False, indent=2)

        # Menerapkan prompt canggih rancangan lu secara dinamis
        prompt = f"""
Kamu adalah AI job matching assistant yang membantu kandidat
mengevaluasi kecocokan lowongan pekerjaan dengan profil mereka.

TUGAS UTAMA
Nilai seberapa cocok lowongan pekerjaan dengan kandidat berdasarkan
bukti yang tersedia di profil kandidat dan deskripsi lowongan.

=== PROFIL KANDIDAT ===
{profile_json}

=== DATA LOWONGAN ===
{job_json}

=== ATURAN ANALISIS ===

1. IDENTIFIKASI PEKERJAAN
Pahami tanggung jawab, kemampuan, pengalaman, pendidikan, sertifikasi,
dan persyaratan penting yang diminta oleh lowongan.

2. SESUAIKAN DENGAN PROFIL KANDIDAT
Gunakan target_roles, skills_and_experience, dan informasi profil lain yang tersedia.

Sesuaikan penilaian dengan bidang pekerjaan yang sebenarnya.
Jangan mengasumsikan kandidat harus memiliki kemampuan programming,
Python, atau skill IT jika pekerjaan tersebut tidak membutuhkannya.

3. NILAI BERDASARKAN BUKTI
Bedakan antara:
- Persyaratan yang didukung oleh informasi profil.
- Persyaratan yang belum terbukti dari informasi yang tersedia.
- Persyaratan penting yang bertentangan dengan informasi profil.

Jangan mengarang pengalaman, skill, pendidikan, atau sertifikasi.
Informasi yang tidak dicantumkan tidak otomatis berarti kandidat
tidak memiliki kemampuan tersebut.

4. PERTIMBANGKAN TRANSFERABLE SKILLS
Pertimbangkan pengalaman dan kemampuan dari pekerjaan sebelumnya
yang relevan dengan tanggung jawab pekerjaan baru.

Jangan menganggap semua skill dapat dialihkan. Jelaskan relevansinya
berdasarkan kebutuhan lowongan.

5. HITUNG SKOR KECOCOKAN 0-100
Gunakan panduan berikut secara konsisten:

- 90-100: Kecocokan sangat kuat; sebagian besar kebutuhan penting didukung oleh bukti profil.
- 75-89: Kecocokan kuat; sebagian besar kebutuhan relevan terpenuhi.
- 60-74: Kecocokan cukup; terdapat beberapa kesenjangan penting.
- 40-59: Kecocokan terbatas; beberapa kebutuhan utama belum terpenuhi atau belum dapat dibuktikan.
- 0-39: Kecocokan rendah; terdapat ketidakcocokan substansial.

Nilai relevansi tanggung jawab, skill, pengalaman, serta persyaratan penting lainnya. Sesuaikan prioritas berdasarkan jenis pekerjaan.
Persyaratan wajib yang tidak terpenuhi dapat menurunkan skor secara signifikan.

Jangan memberikan skor tinggi hanya karena judul pekerjaan mirip dengan target kandidat. Jangan pula memberikan skor rendah hanya karena nama skill atau tools berbeda jika kemampuan yang relevan dapat dibuktikan.

6. TULIS ALASAN
Gunakan bahasa Indonesia yang natural dan langsung kepada kandidat dengan kata ganti "Kamu".

Jelaskan alasan skor berdasarkan kecocokan utama dan kesenjangan yang paling penting. Hindari alasan generik seperti "profil Kamu sesuai dengan kebutuhan perusahaan" tanpa penjelasan konkret.

=== FORMAT OUTPUT ===

Kembalikan JSON valid dengan struktur persis seperti ini tanpa teks tambahan di luar JSON:

{{
    "score": 75,
    "reason": "Kamu memiliki pengalaman yang relevan dengan ..."
}}
"""

        # Eksekusi request ke Groq dengan retry rate limit
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                    max_completion_tokens=1024,
                )

                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Respons AI kosong.")

                cleaned_content = content.strip()
                if cleaned_content.startswith("```json"):
                    cleaned_content = cleaned_content[7:]
                if cleaned_content.endswith("```"):
                    cleaned_content = cleaned_content[:-3]
                cleaned_content = cleaned_content.strip()

                result = json.loads(cleaned_content)
                score = int(result["score"])
                reason = str(result["reason"]).strip()

                if not 0 <= score <= 100:
                    raise ValueError(f"Skor tidak valid: {score}")
                if not reason:
                    raise ValueError("Alasan evaluasi kosong")

                logging.info(
                    f"Evaluasi berhasil [{candidate_name}]: {job.get('title')} | Skor: {score}"
                )
                return score, reason

            except RateLimitError as e:
                if attempt == 2:
                    logging.error(f"Groq rate limit: {e}")
                    return -1, "API Error: Groq rate limit tercapai"
                time.sleep(2 ** (attempt + 1))

            except Exception as e:
                logging.error(f"Gagal mengevaluasi lowongan: {e}")
                return -1, f"API Error: {str(e)}"

        return -1, "API Error: Percobaan ulang habis"