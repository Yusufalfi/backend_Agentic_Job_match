import os
import json
import uuid
import logging
import requests as r
from pypdf import PdfReader
from dotenv import load_dotenv

# Konfigurasi Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CVParser")

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def extract_text_from_pdf(pdf_path: str) -> str:
    """Fungsi untuk membaca teks dari file PDF CV"""
    try:
        logger.info(f"Mulai membaca file PDF: {pdf_path}")
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        logger.info(f"Berhasil membaca {len(reader.pages)} halaman dari PDF.")
        return text
    except Exception as e:
        logger.error(f"Gagal saat membaca PDF '{pdf_path}': {e}")
        return ""

def parse_cv_with_ai(cv_text: str) -> dict:
    """Fungsi mengekstrak CV menggunakan Groq REST API via requests (Bypass SSL)"""
    logger.info("Mengirim teks CV ke Groq AI via REST API...")
    
    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY tidak ditemukan di environment variables!")
        return {}

    prompt = f"""
    Analisis teks CV berikut dan ekstrak informasinya ke dalam format JSON murni dengan keys persis seperti ini:
    - "full_name": (Nama lengkap kandidat)
    - "email": (Email kandidat)
    - "phone_number": (Nomor telepon/WhatsApp)
    - "address": (Alamat atau domisili)
    - "parsed_skills": (Gabungan skill utama, teknikal, dan tools dalam bentuk teks koma atau deskripsi singkat)

    Teks CV:
    {cv_text}
    
    Keluarkan HANYA format JSON murni tanpa markdown tambahan (tanpa ```json ... ``` dan tanpa teks pengantar).
    """
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
        "max_completion_tokens": 1024
    }
    
    try:
        # verify=False mengabaikan sertifikat SSL VPN
        response = r.post(url, headers=headers, json=payload, verify=False, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Groq API Error [{response.status_code}]: {response.text}")
            return {}
            
        res_json = response.json()
        raw_response = res_json["choices"][0]["message"]["content"].strip()
        clean_response = raw_response.replace("```json", "").replace("```", "").strip()
        
        parsed_data = json.loads(clean_response)
        logger.info("Berhasil mengekstrak data CV menggunakan Groq API.")
        return parsed_data
        
    except Exception as e:
        logger.error(f"Gagal saat parsing AI Groq via requests: {e}")
        return {}

def register_user_from_cv(pdf_path: str, target_roles_list: list):
    """Fungsi utama untuk parsing PDF dan menyimpan data ke Supabase REST API (Bypass SSL)"""
    logger.info(f"Memproses registrasi user baru dari file: {pdf_path}")
    
    cv_text = extract_text_from_pdf(pdf_path)
    if not cv_text:
        return None, "Gagal membaca teks dari PDF."
    
    profile_data = parse_cv_with_ai(cv_text)
    if not profile_data:
        return None, "Gagal mengekstrak data dengan AI."
    
    unique_code = str(uuid.uuid4())[:8]
    
    data_to_insert = {
        "unique_code": unique_code,
        "full_name": profile_data.get("full_name"),
        "email": profile_data.get("email"),
        "phone_number": profile_data.get("phone_number"),
        "address": profile_data.get("address"),
        "target_roles": target_roles_list,
        "parsed_skills": profile_data.get("parsed_skills")
    }
    
    logger.info(f"Menyimpan data user {profile_data.get('full_name')} ke Supabase via REST API...")
    
    # Supabase REST API endpoint
    supabase_rest_url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/users"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    try:
        # verify=False untuk membypass error sertifikat SSL VPN pada Supabase
        response = r.post(
            supabase_rest_url,
            headers=headers,
            json=data_to_insert,
            verify=False,
            timeout=30
            )
        
        if response.status_code not in [200, 201]:
            error_msg = f"Supabase REST API Error [{response.status_code}]: {response.text}"
            logger.error(error_msg)
            return None, error_msg
            
        logger.info(f"Sukses! User terdaftar dengan Unique Code: {unique_code}")
        return unique_code, None
        
    except Exception as e:
        error_msg = f"Gagal menyimpan ke database Supabase via requests: {e}"
        logger.error(error_msg)
        return None, error_msg

# --- SCRIPT TESTING MANUAL ---
# if __name__ == "__main__":
#     test_pdf = "Yusuf Alfi.pdf" 
#     sample_roles = ["Automation Engineer", "Python Developer", "RPA Developer"]
    
#     print(f"🚀 Memulai uji coba parser untuk file: {test_pdf}")
#     code, err = register_user_from_cv(test_pdf, sample_roles)
    
#     if err:
#         print(f"❌ Uji Coba GAGAL: {err}")
#     else:
#         print(f"🎉 Uji Coba BERHASIL! Unique Code: {code}")