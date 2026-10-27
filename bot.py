import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_first_name = update.effective_user.first_name

    if context.args:
        unique_code = context.args[0]
        logger.info(f"Menerima unique_code: {unique_code} dari Chat ID: {chat_id}")

        try:
            response = supabase.table("users").update({
                "telegram_chat_id": str(chat_id)
            }).eq("unique_code", unique_code).execute()

            if response.data:
                await update.message.reply_text(
                    f"🎉 Halo {user_first_name}! Akun Telegram lu berhasil **terhubung** dengan CV lu di web!"
                )
            else:
                await update.message.reply_text(
                    "⚠️ Kode unik tidak ditemukan atau sudah kedaluwarsa. Coba upload ulang CV lu."
                )
        except Exception as e:
            logger.error(f"Error Supabase: {str(e)}")
            await update.message.reply_text("❌ Terjadi kesalahan sistem.")
    else:
        await update.message.reply_text(f"Halo {user_first_name}! Silakan upload CV lu lewat web dulu ya.")

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN belum diset!")
        return

    # Inisialisasi standar bersih tanpa custom request yang bikin error
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))

    logger.info("🤖 Bot Telegram berhasil berjalan!")
    application.run_polling()

if __name__ == "__main__":
    main()