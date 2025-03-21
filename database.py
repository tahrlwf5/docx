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
MONGO_URL = os.getenv("MONGO_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # معرف المشرف
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))  # معرف القناة
BOT_TOKEN = os.getenv("BOT_TOKEN")

# إعداد الاتصال بقاعدة البيانات
try:
    client = pymongo.MongoClient(MONGO_URL)
    db = client["telegram_bot"]
    users_collection = db["users"]
except Exception as e:
    logging.error(f"❌ خطأ في الاتصال بقاعدة البيانات: {str(e)}")

# إعداد البوت لإرسال الإشعارات
bot = Bot(token=BOT_TOKEN)

def notify_admin(error_message):
    """إرسال خطأ للمشرف عبر التليجرام"""
    try:
        bot.send_message(chat_id=ADMIN_ID, text=f"🚨 خطأ في البوت:\n\n{error_message}")
    except Exception as e:
        logging.error(f"❌ فشل إرسال إشعار الخطأ للمشرف: {str(e)}")

def add_user(user_id, username, first_name, last_name):
    """إضافة مستخدم جديد إلى قاعدة البيانات"""
    try:
        user = users_collection.find_one({"user_id": user_id})
        if user is None:
            new_user = {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "joined_at": datetime.utcnow(),
                "file_count": 0  # عداد الملفات
            }
            users_collection.insert_one(new_user)

            # إشعار القناة بانضمام مستخدم جديد
            message = f"🚀 مستخدم جديد انضم إلى البوت!\n\n"
            message += f"👤 الاسم: {first_name} {last_name}\n"
            message += f"📌 المعرف: @{username}\n" if username else ""
            message += f"🆔 ID: `{user_id}`\n"
            bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"❌ خطأ عند إضافة مستخدم {user_id}: {str(e)}")
        notify_admin(f"⚠️ حدث خطأ عند إضافة المستخدم `{user_id}`\n\n{str(e)}")

def update_file_count(user_id):
    """تحديث عدد الملفات التي رفعها المستخدم"""
    try:
        users_collection.update_one({"user_id": user_id}, {"$inc": {"file_count": 1}})
    except Exception as e:
        logging.error(f"❌ خطأ عند تحديث عدد الملفات للمستخدم {user_id}: {str(e)}")
        notify_admin(f"⚠️ خطأ عند تحديث عدد الملفات للمستخدم `{user_id}`\n\n{str(e)}")

def send_translated_file(user_id, file_path, caption="ملف مترجم"):
    """إرسال الملف المترجم إلى القناة للمراقبة"""
    try:
        user = users_collection.find_one({"user_id": user_id})
        if user:
            message = f"📄 ملف جديد تمت ترجمته بواسطة المستخدم:\n\n"
            message += f"👤 الاسم: {user.get('first_name', '')} {user.get('last_name', '')}\n"
            message += f"📌 المعرف: @{user.get('username', 'مجهول')}\n"
            message += f"🆔 ID: `{user_id}`\n"
            bot.send_document(chat_id=CHANNEL_ID, document=open(file_path, "rb"), caption=message, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"❌ خطأ عند إرسال الملف المترجم للمستخدم {user_id}: {str(e)}")
        notify_admin(f"⚠️ خطأ عند إرسال الملف المترجم للمستخدم `{user_id}`\n\n{str(e)}")

def get_user_count():
    """إرجاع عدد المستخدمين"""
    try:
        return users_collection.count_documents({})
    except Exception as e:
        logging.error(f"❌ خطأ عند حساب عدد المستخدمين: {str(e)}")
        notify_admin(f"⚠️ خطأ عند حساب عدد المستخدمين\n\n{str(e)}")
        return 0
