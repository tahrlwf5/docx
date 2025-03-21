import os
import logging
from pymongo import MongoClient
from telegram import Bot

# إعداد سجل الأخطاء
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# تحميل متغيرات البيئة
MONGO_URL = os.getenv("MONGO_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))  # معرف المشرف
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))  # معرف القناة

# إنشاء اتصال بقاعدة البيانات
client = MongoClient(MONGO_URL)
db = client["telegram_bot"]
users_collection = db["users"]

# إنشاء كائن البوت
bot = Bot(token=BOT_TOKEN)

def add_user(user_id: int, username: str, first_name: str, last_name: str):
    """إضافة مستخدم جديد إلى قاعدة البيانات"""
    try:
        if users_collection.find_one({"user_id": user_id}) is None:
            users_collection.insert_one({
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name
            })
            logging.info(f"✅ تمت إضافة مستخدم جديد: {user_id}")
            bot.send_message(ADMIN_ID, f"👤 مستخدم جديد: {first_name} (@{username}) \n🆔 ID: {user_id}")
    except Exception as e:
        logging.error(f"❌ خطأ عند إضافة المستخدم {user_id}: {str(e)}")

def get_user_count():
    """إرجاع عدد المستخدمين المسجلين في قاعدة البيانات"""
    return users_collection.count_documents({})

def send_translated_file(user_id: int, file_path: str, original_file_name: str):
    """إرسال الملف المترجم إلى القناة مع معلومات المستخدم"""
    try:
        user = users_collection.find_one({"user_id": user_id})
        if user:
            message = (
                f"<b>📢 تمت ترجمة ملف جديد!</b>\n\n"
                f"<b>👤 المستخدم:</b> <a href=\"tg://user?id={user_id}\">{user.get('first_name', '')} {user.get('last_name', '')}</a>\n"
                f"<b>🔹 المعرف:</b> @{user.get('username', 'مجهول')}\n"
                f"<b>🆔 ID:</b> {user_id}\n"
                f"<b>📄 اسم الملف:</b> {original_file_name}"
            )
            
            print(f"📡 محاولة الإرسال إلى القناة: {CHANNEL_ID}")  # تأكيد معرف القناة
            with open(file_path, "rb") as file:
                bot.send_document(chat_id=CHANNEL_ID, document=file, caption=message, parse_mode="HTML")

            logging.info("✅ تم إرسال الملف إلى القناة بنجاح!")
        else:
            logging.warning(f"❌ المستخدم {user_id} غير موجود في قاعدة البيانات!")
    except Exception as e:
        logging.error(f"❌ خطأ عند إرسال الملف: {str(e)}")
        print(f"❌ خطأ عند إرسال الملف للقناة: {str(e)}")
