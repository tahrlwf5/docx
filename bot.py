import logging
import requests
import base64
import time
import os
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# إعداد المتغيرات الأساسية
API_KEY = '3c50e707584d2cbe0139d35033b99d7c'
CONVERTIO_API = 'https://api.convertio.co/convert'
TELEGRAM_TOKEN = '5146976580:AAH0ZpK52d6fKJY04v-9mRxb6Z1fTl0xNLw'  # استبدل هذا بالتوكن الخاص ببوتك

# إعداد تسجيل الأحداث (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('مرحبًا! أرسل لي ملف PDF وسأقوم بتحويله إلى HTML.')

def pdf_handler(update: Update, context: CallbackContext) -> None:
    document = update.message.document
    if document.mime_type != 'application/pdf':
        update.message.reply_text('يرجى إرسال ملف بصيغة PDF فقط.')
        return

    # تحميل الملف من تليجرام
    file = document.get_file()
    input_filename = 'input.pdf'
    file.download(input_filename)
    update.message.reply_text('تم استلام الملف، جارٍ التحويل. يرجى الانتظار...')

    # قراءة الملف وترميزه بصيغة Base64
    with open(input_filename, 'rb') as f:
        file_data = f.read()
    encoded_file = base64.b64encode(file_data).decode('utf-8')

    # تجهيز بيانات الطلب لإرسالها إلى API الخاص بـ convertio
    payload = {
        "apikey": API_KEY,
        "input": "base64",
        "file": encoded_file,
        "filename": document.file_name,
        "outputformat": "html"
    }

    try:
        response = requests.post(CONVERTIO_API, json=payload)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Error during conversion initiation: {e}")
        update.message.reply_text('حدث خطأ أثناء بدء عملية التحويل.')
        return

    result = response.json()
    if result.get('code') != 200:
        error_msg = result.get('error', 'خطأ غير معروف.')
        update.message.reply_text(f'خطأ في API التحويل: {error_msg}')
        return

    conversion_id = result['data']['id']

    # استعلام دوري لمعرفة حالة عملية التحويل
    status_url = f"{CONVERTIO_API}/{conversion_id}/status"
    while True:
        time.sleep(2)  # الانتظار لمدة ثانيتين قبل الاستعلام مرة أخرى
        status_resp = requests.get(status_url)
        status_data = status_resp.json()
        step = status_data.get('data', {}).get('step')
        if step == 'finish':
            break
        if step == 'error':
            update.message.reply_text('حدث خطأ أثناء التحويل.')
            return

    # الحصول على رابط تحميل الملف المحول
    download_url = status_data['data']['output']['url']
    try:
        download_resp = requests.get(download_url)
        download_resp.raise_for_status()
    except Exception as e:
        logger.error(f"Error downloading converted file: {e}")
        update.message.reply_text('حدث خطأ أثناء تحميل الملف المحول.')
        return

    output_filename = 'output.html'
    with open(output_filename, 'wb') as f:
        f.write(download_resp.content)

    # إرسال الملف المحول إلى المستخدم
    update.message.reply_document(document=open(output_filename, 'rb'))

    # حذف الملفات المؤقتة
    os.remove(input_filename)
    os.remove(output_filename)

def main() -> None:
    # تأكد من استخدام use_context=True لتفعيل سياق الاستخدام في النسخة 13.15
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.document, pdf_handler))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
