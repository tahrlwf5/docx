import os
import pymongo
import logging
from datetime import datetime
from telegram import Bot

# إعداد تسجيل الأخطاء في ملف bot.log
logging.basicConfig(
    filename="bot.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# قراءة متغيرات البيئة
MONGO_URL = os.getenv("MONGO_URL")  # مثال: mongodb://localhost:27017
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))      # معرف المشرف (رقم)
CHANNEL_ID = os.getenv("CHANNEL_ID")            # معرف القناة (مثال: -1002424292607)
BOT_TOKEN = os.getenv("BOT_TOKEN")              # توكن البوت

# إنشاء الاتصال بقاعدة البيانات
try:
    client = pymongo.MongoClient(MONGO_URL)
    db = client["telegram_bot"]
    users_collection = db["users"]
    settings_collection = db["settings"]
except Exception as e:
    logging.error(f"❌ خطأ في الاتصال بقاعدة البيانات: {str(e)}")

# إنشاء كائن البوت لإرسال الإشعارات
bot = Bot(token=BOT_TOKEN)

def notify_admin(error_message: str):
    """إرسال إشعار بالخطأ إلى المشرف"""
    try:
        bot.send_message(chat_id=ADMIN_ID, text=f"🚨 خطأ في البوت:\n\n{error_message}")
    except Exception as e:
        logging.error(f"❌ فشل إرسال إشعار الخطأ للمشرف: {str(e)}")

def add_user(user_id: int, username: str, first_name: str, last_name: str) -> bool:
    """
    إضافة مستخدم جديد إلى قاعدة البيانات.
    إذا كان المستخدم جديدًا يتم إدخاله وإرسال إشعار إلى القناة.
    """
    try:
        if users_collection.find_one({"user_id": user_id}) is None:
            new_user = {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "joined_at": datetime.utcnow(),
                "file_count": 0
            }
            users_collection.insert_one(new_user)
            # إرسال إشعار للقناة باستخدام تنسيق HTML لتفادي مشاكل التحليل
            if CHANNEL_ID:
                message = (
                    f"<b>🆕 مستخدم جديد انضم إلى البوت!</b>\n"
                    f"👤 <b>الاسم:</b> {first_name} {last_name if last_name else ''}\n"
                    f"🔹 <b>المعرف:</b> @{username if username else 'لا يوجد'}\n"
                    f"🆔 <b>ID:</b> {user_id}\n"
                )
                bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode="HTML")
            return True
    except Exception as e:
        logging.error(f"❌ خطأ عند إضافة المستخدم {user_id}: {str(e)}")
        notify_admin(f"⚠️ حدث خطأ عند إضافة المستخدم `{user_id}`\n\n{str(e)}")
    return False

def update_file_count(user_id: int):
    """تحديث عدد الملفات التي رفعها المستخدم"""
    try:
        users_collection.update_one({"user_id": user_id}, {"$inc": {"file_count": 1}})
    except Exception as e:
        logging.error(f"❌ خطأ عند تحديث عدد الملفات للمستخدم {user_id}: {str(e)}")
        notify_admin(f"⚠️ خطأ عند تحديث عدد الملفات للمستخدم `{user_id}`\n\n{str(e)}")

def send_translated_file(user_id: int, file_path: str, original_file_name: str):
    """
    إرسال الملف المترجم إلى القناة مع معلومات المستخدم للمراقبة.
    يُستخدم تنسيق HTML لتفادي مشاكل تحليل الكيانات.
    """
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
            bot.send_document(chat_id=CHANNEL_ID, document=open(file_path, "rb"), caption=message, parse_mode="HTML")
    except Exception as e:
        logging.error(f"❌ خطأ عند إرسال الملف المترجم للمستخدم {user_id}: {str(e)}")
        notify_admin(f"⚠️ خطأ عند إرسال الملف المترجم للمستخدم `{user_id}`\n\n{str(e)}")

def get_user_count() -> int:
    """إرجاع عدد المستخدمين المسجلين في قاعدة البيانات."""
    try:
        return users_collection.count_documents({})
    except Exception as e:
        logging.error(f"❌ خطأ عند حساب عدد المستخدمين: {str(e)}")
        notify_admin(f"⚠️ خطأ عند حساب عدد المستخدمين\n\n{str(e)}")
        return 0
