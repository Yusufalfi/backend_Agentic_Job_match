from fastapi import FastAPI, UploadFile, File, Form, HTTPException,Request
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import httpx
import uuid
from supabase import create_client
from dotenv import load_dotenv
from backend.parser import register_user_from_cv 

app = FastAPI(
    title="Agentic AI Job Match API",
    description="Backend API for automated CV parsing, Supabase storage, and Telegram pairing.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Atau tentukan spesifik seperti ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],  # Mengizinkan semua method (POST, GET, dll)
    allow_headers=["*"],  # Mengizinkan semua header
)
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Inisialisasi klien Supabase & URL API Telegram
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Batas maksimal ukuran file: 5 MB
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5,242,880 bytes

@app.get("/")
def read_root():
    return {"status": "AI Job Match Backend is running smoothly 🚀"}

# @app.post("/api/register-cv")
# async def register_cv(
#     file: UploadFile = File(...),
#     target_role: str = Form(...)  # Menerima input string dari Postman
# ):
#     # 1. Validasi format file harus PDF
#     if not file.filename.endswith(".pdf"):
#         raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
    
#     # 2. Validasi ukuran file (Maksimal 5 MB)
#     file_content = await file.read()
#     file_size = len(file_content)
    
#     if file_size > MAX_FILE_SIZE:
#         raise HTTPException(
#             status_code=400, 
#             detail=f"File size exceeds the maximum limit of 5 MB. Current file size: {file_size / (1024 * 1024):.2f} MB"
#         )
    
#     # 3. Ubah string target_role jadi List (Array) supaya cocok sama tipe data text[] di Supabase
#     # Contoh: "RPA Developer, Python Developer" -> ['RPA Developer', 'Python Developer']
#     if target_role:
#         role_list = [role.strip() for role in target_role.split(",") if role.strip()]
#     else:
#         role_list = []

#     temp_dir = "temp_uploads"
#     os.makedirs(temp_dir, exist_ok=True)
#     temp_file_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{file.filename}")
    
#     try:
#         with open(temp_file_path, "wb") as buffer:
#             buffer.write(file_content)
        
#         # Kirim role_list (yang sudah berbentuk array/list) ke fungsi parser lo
#         unique_code, error = register_user_from_cv(temp_file_path, role_list)
        
#         if error:
#             raise HTTPException(status_code=500, detail=f"Parsing error: {error}")
            
#         return {
#             "success": True,
#             "message": "CV successfully parsed and stored!",
#             "target_roles": role_list,
#             "unique_code": unique_code,
#             "telegram_link": f"https://t.me/AGENT_JOB_V1_BOT?start={unique_code}"
#         }
        
#     except HTTPException as he:
#         raise he
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
        
#     finally:
#         if os.path.exists(temp_file_path):
#             os.remove(temp_file_path)




@app.post("/api/register-cv")
async def register_cv(
    file: UploadFile = File(...),
    target_role: str = Form(...)  # Menerima input string dari Postman
):
    # 1. Validasi format file harus PDF
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
    
    # 2. Validasi ukuran file (Maksimal 5 MB)
    file_content = await file.read()
    file_size = len(file_content)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400, 
            detail=f"File size exceeds the maximum limit of 5 MB. Current file size: {file_size / (1024 * 1024):.2f} MB"
        )
    
    # 3. Ubah string target_role jadi List (Array) supaya cocok sama tipe data text[] di Supabase
    if target_role:
        role_list = [role.strip() for role in target_role.split(",") if role.strip()]
    else:
        role_list = []

    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{file.filename}")
    
    try:
        with open(temp_file_path, "wb") as buffer:
            buffer.write(file_content)
        
        # PENTING: Di dalam fungsi register_user_from_cv() ini, 
        # pastikan saat melakukan insert ke Supabase, kolom "status" diisi "pending_telegram".
        unique_code, error = register_user_from_cv(temp_file_path, role_list)
        
        if error:
            raise HTTPException(status_code=500, detail=f"Parsing error: {error}")
            
        return {
            "success": True,
            "message": "CV successfully parsed and stored!",
            "target_roles": role_list,
            "unique_code": unique_code,
            # <--- DIUBAH DISINI: Ubah jadi link polos tanpa ?start={unique_code}
            "telegram_link": "https://t.me/AGENT_JOB_V1_BOT" 
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# ==========================================
# TELEGRAM WEBHOOK ENDPOINT
# ==========================================
@app.post("/api/telegram-webhook")
async def telegram_webhook(request: Request):
    """
    Endpoint ini otomatis ditembak oleh server Telegram 
    ketika user ngeklik link dan nge-chat bot (/start <unique_code>).
    """
    try:
        data = await request.json()
        
        # Pastikan ada pesan teks masuk dari user
        if "message" in data and "text" in data["message"]:
            message = data["message"]
            chat_id = message["chat"]["id"]
            text = message.get("text", "")
            user_first_name = message["from"].get("first_name", "User")

            # Cek apakah perintahnya /start
            if text.startswith("/start"):
                parts = text.split(" ")
                
                # Cek apakah membawa unique_code dari web
                if len(parts) > 1:
                    unique_code = parts[1]
                    
                    # Update telegram_chat_id ke tabel users di Supabase berdasarkan unique_code
                    response = supabase.table("users").update({
                        "telegram_chat_id": str(chat_id)
                    }).eq("unique_code", unique_code).execute()

                    if response.data:
                        reply_text = (
                            f"🎉 Halo {user_first_name}! Akun Telegram lu berhasil **terhubung** dengan CV yang lu upload di web!\n\n"
                            f"🤖 Bot ini bakal otomatis ngabarin lu kalau ada lowongan kerja yang cocok sama target role lu. Ditunggu ya!"
                        )
                    else:
                        reply_text = (
                            "⚠️ Wah, kode unik (unique code) tidak ditemukan atau sudah kedaluwarsa di database. Coba upload ulang CV lu di web ya."
                        )
                else:
                    # Kalau user asal klik bot tanpa link web
                    reply_text = (
                        f"Halo {user_first_name}! Selamat datang di **Agentic AI Job Match Bot** 🚀\n\n"
                        "Silakan upload CV lu terlebih dahulu lewat web platform kita untuk mulai mencari lowongan kerja otomatis!"
                    )

                # Kirim balasan ke user lewat Telegram HTTP API
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{TELEGRAM_API_URL}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": reply_text,
                            "parse_mode": "Markdown"
                        }
                    )
        
        return {"status": "ok"}
    
    except Exception as e:
        print(f"Error in telegram_webhook: {str(e)}")
        return {"status": "error", "message": str(e)}