import streamlit as st
import os
import tempfile
import time
from backend.parser import register_user_from_cv

# Konfigurasi Halaman (Wide mode)
st.set_page_config(
    page_title="Agentic AI Job Match",
    page_icon="🤖",
    layout="wide"
)

# --- CUSTOM CSS: NEO-BRUTALISM SIDE-BY-SIDE ---
st.markdown("""
<style>
    .stApp {
        background-color: #f4f4f0;
        font-family: 'Inter', sans-serif;
    }
    
    .neo-header {
        border: 4px solid #000000;
        background-color: #ffde59;
        box-shadow: 6px 6px 0px #000000;
        padding: 25px;
        margin-bottom: 30px;
    }
    
    .neo-box {
        border: 4px solid #000000;
        background-color: #ffffff;
        box-shadow: 6px 6px 0px #000000;
        padding: 25px;
        margin-bottom: 20px;
    }

    .neo-success-box {
        border: 4px solid #000000;
        background-color: #b9ff66;
        box-shadow: 6px 6px 0px #000000;
        padding: 20px;
        margin-top: 15px;
    }

    label {
        font-weight: 800 !important;
        color: #000000 !important;
    }

    div.stTextInput > div > div > input {
        border: 3px solid #000000 !important;
        border-radius: 0px !important;
        box-shadow: 4px 4px 0px #000000 !important;
        background-color: #ffffff !important;
        font-weight: 600;
        color: #000000;
    }
    
    div.stFileUploader > div {
        border: 3px solid #000000 !important;
        border-radius: 0px !important;
        box-shadow: 4px 4px 0px #000000 !important;
        background-color: #fff9db !important;
    }

    div.stButton > button {
        border: 4px solid #000000 !important;
        background-color: #ffde59 !important;
        color: #000000 !important;
        font-weight: 900 !important;
        font-size: 16px !important;
        box-shadow: 5px 5px 0px #000000 !important;
        border-radius: 0px !important;
        width: 100%;
        padding: 12px;
        transition: transform 0.1s ease, box-shadow 0.1s ease;
    }
    
    div.stButton > button:hover {
        background-color: #ffcc00 !important;
        color: #000000 !important;
    }
    
    div.stButton > button:active {
        transform: translate(2px, 2px);
        box-shadow: 2px 2px 0px #000000 !important;
    }
</style>
""", unsafe_allow_html=True)

# Header Utama
st.markdown("""
<div class="neo-header">
    <h1 style="margin:0; color: #000000; font-weight: 900; font-size: 2.2rem;">🤖 AGENTIC AI JOB MATCH</h1>
    <p style="margin:8px 0 0 0; font-weight: 700; color: #000000; font-size: 1.05rem;">Upload CV berformat PDF dan tentukan target pekerjaanmu untuk memulai sistem pencocokan berbasis AI!</p>
</div>
""", unsafe_allow_html=True)

# Session state untuk mereset widget form secara total menggunakan unique key counter
if "form_reset_counter" not in st.session_state:
    st.session_state.form_reset_counter = 0

if "success_payload" not in st.session_state:
    st.session_state.success_payload = None

# --- LAYOUT 2 KOLOM (KIRI: FORM, KANAN: LOG & HASIL) ---
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    # st.markdown('<div class="neo-box">', unsafe_allow_html=True)
    st.markdown("### 📝 Form Pendaftaran Kandidat")
    st.markdown("---")
    
    # Key yang dinamis berdasarkan counter akan memaksa Streamlit merender ulang widget dari kosong saat di-trigger
    f_key = st.session_state.form_reset_counter
    
    target_roles_input = st.text_input(
        "Target Roles / Posisi Impian (pisahkan dengan koma)",
        placeholder="Contoh: Python Developer, Automation Engineer, RPA Developer",
        key=f"target_roles_{f_key}"
    )
    
    uploaded_file = st.file_uploader(
        "Upload CV Anda (Format PDF)", 
        type=["pdf"],
        key=f"uploader_{f_key}"
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    submit_button = st.button("🚀 PROSES & DAFTARKAN CV")
    st.markdown('</div>', unsafe_allow_html=True)


with col_right:
    # st.markdown('<div class="neo-box">', unsafe_allow_html=True)
    st.markdown("### 📡 Terminal & Status Pipeline")
    st.markdown("---")
    
    # Jika ada data sukses tersimpan di session, tampilkan card sukses di kanan
    if st.session_state.success_payload:
        unique_code = st.session_state.success_payload
        st.markdown(f"""
        <div class="neo-success-box">
            <h3 style="margin:0; color:#000000; font-weight:900;">🎉 PENDAFTARAN SUKSES!</h3>
            <p style="margin:6px 0 2px 0; font-weight:bold; color:#000;">Unique Code Anda:</p>
            <div style="background:#000000; color:#ffffff; display:inline-block; padding:6px 12px; font-weight:900; font-size:1.3rem; letter-spacing: 2px; border: 2px solid #000;">
                {unique_code}
            </div>
            <p style="margin:8px 0 0 0; font-size:13px; font-weight:700; color:#000000;">
                simpan unique code anda .
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("👉 Silakan isi form di sebelah kiri lalu klik tombol **Proses & Daftarkan CV** untuk memulai sistem.")
        
    st.markdown('</div>', unsafe_allow_html=True)

# Logika ketika tombol submit diklik
if submit_button:
    if not uploaded_file:
        with col_right:
            st.error("⚠️ Mohon upload file CV berformat PDF terlebih dahulu di sebelah kiri!")
    elif not target_roles_input:
        with col_right:
            st.error("⚠️ Mohon masukkan minimal satu Target Role di sebelah kiri!")
    else:
        target_roles_list = [role.strip() for role in target_roles_input.split(",") if role.strip()]
        
        # Simulasi animasi scan di kolom kanan
        with col_right:
            with st.status("🔄 Menjalankan Pipeline AI...", expanded=True) as status:
                
                st.write("📁 Membaca file PDF yang di-upload...")
                time.sleep(0.8)
                
                # Simpan file sementara
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_path = tmp_file.name
                
                st.write("🔍 Mengekstrak teks dokumen secara mendalam...")
                time.sleep(1.0)
                
                st.write("🤖 Mengirim payload ke AI untuk parsing profil & skill...")
                time.sleep(0.8)
                
                try:
                    # Memanggil fungsi backend
                    unique_code, error = register_user_from_cv(tmp_path, target_roles_list)
                    
                    if error:
                        status.update(label="❌ Proses Gagal!", state="error", expanded=True)
                        st.error(f"Detail Error: {error}")
                    else:
                        status.update(label="✅ Berhasil Diproses!", state="complete", expanded=False)
                        
                        # Simpan unique code ke session, lalu increment counter agar form di kiri ter-reset bersih
                        st.session_state.success_payload = unique_code
                        st.session_state.form_reset_counter += 1
                        
                        # Rerun agar form langsung kosong dan kotak sukses muncul di kanan
                        st.rerun()
                
                except Exception as e:
                    status.update(label="❌ Terjadi Kesalahan Sistem", state="error", expanded=True)
                    st.error(f"Error: {e}")
                
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)