import os
import logging
from pymongo import MongoClient
from telegram import Bot
from dotenv import load_dotenv

# تحميل متغيرات البيئة
load_dotenv()

# متغيرات البيئة
MONGO_URL = os.getenv("MONGO_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # معرف المشرف
CHANNEL_ID = os.getenv("CHANNEL_ID")  # معرف القناة للنشر

# إعداد الاتصال بقاعدة البيانات
client = MongoClient(MONGO_URL)
db = client["telegram_bot"]
users_collection = db["users"]

# إعداد البوت
bot = Bot(token=BOT_TOKEN)

# إعداد التسجيل للأخطاء
logging.basicConfig(filename="log.txt", level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")

def add_user(user_id, username, first_name, last_name):
    """إضافة مستخدم جديد إلى قاعدة البيانات وإرسال إشعار للمشرف"""
    try:
        if users_collection.find_one({"user_id": user_id}) is None:
            users_collection.insert_one({
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name
            })
            message = f"👤 **مستخدم جديد دخل البوت**\n🆔 ID: {user_id}\n👤 الاسم: {first_name} (@{username})"
            bot.send_message(chat_id=ADMIN_ID, text=message, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"خطأ عند إضافة المستخدم `{user_id}`: {e}")

def get_user_count():
    """إرجاع عدد المستخدمين المسجلين في قاعدة البيانات"""
    try:
        return users_collection.count_documents({})
    except Exception as e:
        logging.error(f"خطأ عند حساب عدد المستخدمين: {e}")
        return 0

def send_translated_file_to_channel(file_path, user_id, username, first_name):
    """إرسال الملف المترجم إلى القناة مع معلومات المستخدم"""
    try:
        caption = f"📄 **ملف مترجم جديد**\n👤 المستخدم: {first_name} (@{username})\n🆔 ID: {user_id}\n📂 الملف: {os.path.basename(file_path)}"
        with open(file_path, "rb") as file:
            bot.send_document(chat_id=CHANNEL_ID, document=file, caption=caption, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"خطأ عند إرسال الملف `{file_path}` للقناة: {e}")

