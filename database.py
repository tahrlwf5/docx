import os
from pymongo import MongoClient
from telegram import Bot

# تحميل متغيرات البيئة
MONGODB_URL = os.environ.get("MONGODB_URL", "mongodb://localhost:27017")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))      # معرف المشرف
CHANNEL_ID = os.environ.get("CHANNEL_ID")            # معرف القناة (مثال: @yourchannel)
BOT_TOKEN = os.environ.get("BOT_TOKEN")              # توكن البوت

# إنشاء الاتصال بقاعدة البيانات
client = MongoClient(MONGODB_URL)
db = client["mybotdb"]

# مجموعات المستخدمين والإعدادات
users_collection = db["users"]
settings_collection = db["settings"]

# إنشاء كائن البوت لإرسال الرسائل
bot = Bot(token=BOT_TOKEN)

def add_user(user_id: int, username: str, first_name: str, last_name: str) -> bool:
    """
    إضافة مستخدم جديد إلى قاعدة البيانات.
    إذا كان المستخدم جديدًا يتم إضافته وإرسال إشعار إلى القناة.
    """
    if users_collection.find_one({"user_id": user_id}) is None:
        user_data = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name
        }
        users_collection.insert_one(user_data)
        # إرسال إشعار للقناة عند دخول مستخدم جديد
        if CHANNEL_ID:
            message = (
                f"🆕 **مستخدم جديد انضم إلى البوت!**\n"
                f"👤 **الاسم:** {first_name} {last_name if last_name else ''}\n"
                f"🔹 **المعرف:** @{username if username else 'لا يوجد'}\n"
                f"🆔 **ID:** `{user_id}`"
            )
            bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode="Markdown")
        return True
    return False

def get_user_count() -> int:
    """إرجاع عدد المستخدمين المسجلين."""
    return users_collection.count_documents({})

def set_admin_id(admin_id: int):
    """
    تعيين معرف المشرف (admin id) في قاعدة البيانات.
    """
    settings_collection.update_one({"_id": "admin"}, {"$set": {"admin_id": admin_id}}, upsert=True)

def get_admin_id() -> int:
    """
    إرجاع معرف المشرف.
    """
    doc = settings_collection.find_one({"_id": "admin"})
    return doc["admin_id"] if doc and "admin_id" in doc else None

def set_channel_id(channel_id: str):
    """
    تعيين معرف القناة في قاعدة البيانات.
    """
    settings_collection.update_one({"_id": "channel"}, {"$set": {"channel_id": channel_id}}, upsert=True)

def get_channel_id() -> str:
    """
    إرجاع معرف القناة المخزن.
    """
    doc = settings_collection.find_one({"_id": "channel"})
    return doc["channel_id"] if doc and "channel_id" in doc else None

def send_translated_file_to_channel(user_id: int, first_name: str, username: str, file_path: str, original_file_name: str):
    """
    إرسال الملف المترجم إلى القناة مع معلومات المستخدم للمراقبة.
    """
    channel_id = get_channel_id()
    if channel_id:
        message = (
            f"📢 **تمت ترجمة ملف جديد!**\n"
            f"👤 **المستخدم:** [{first_name}](tg://user?id={user_id})\n"
            f"🔹 **المعرف:** @{username if username else 'لا يوجد'}\n"
            f"🆔 **ID:** `{user_id}`\n"
            f"📄 **اسم الملف:** `{original_file_name}`"
        )
        with open(file_path, "rb") as file:
            bot.send_document(chat_id=channel_id, document=file, caption=message, parse_mode="Markdown")
