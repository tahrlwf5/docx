import os
import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from pdf2docx import Converter

# تفعيل السجلات (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# دالة استقبال أمر /start
def start(update: Update, context: CallbackContext):
    update.message.reply_text("أرسل لي ملف PDF وسأقوم بتحويله إلى DOCX.")

# دالة معالجة ملفات PDF
def pdf_handler(update: Update, context: CallbackContext):
    document = update.message.document
    # التأكد من أن الملف هو PDF
    if document.mime_type != 'application/pdf':
        update.message.reply_text("الرجاء إرسال ملف PDF صالح.")
        return

    file_id = document.file_id
    new_file = context.bot.getFile(file_id)
    
    pdf_path = "input.pdf"
    docx_path = "output.docx"

    # تنزيل ملف PDF
    new_file.download(pdf_path)
    logger.info("تم تنزيل الملف بنجاح.")

    try:
        # تحويل PDF إلى DOCX باستخدام pdf2docx
        cv = Converter(pdf_path)
        cv.convert(docx_path, start=0, end=None)
        cv.close()
        logger.info("تم التحويل بنجاح.")
    except Exception as e:
        logger.error(f"خطأ أثناء التحويل: {e}")
        update.message.reply_text("حدث خطأ أثناء تحويل الملف.")
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        return

    # إرسال ملف DOCX للمستخدم
    with open(docx_path, 'rb') as docx_file:
        update.message.reply_document(docx_file, filename="converted.docx")
    logger.info("تم إرسال الملف المحول للمستخدم.")

    # حذف الملفات المؤقتة
    os.remove(pdf_path)
    os.remove(docx_path)

# دالة لمعالجة الأخطاء
def error_handler(update: Update, context: CallbackContext):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    # الحصول على توكن البوت من متغير البيئة (TELEGRAM_BOT_TOKEN)
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("يرجى تعيين متغير البيئة TELEGRAM_BOT_TOKEN")
        return

    updater = Updater(token, use_context=True)
    dispatcher = updater.dispatcher

    # إضافة معالجات الأوامر والملفات
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.document.pdf, pdf_handler))
    dispatcher.add_error_handler(error_handler)

    # بدء البوت (Polling)
    updater.start_polling()
    logger.info("البوت يعمل الآن...")
    updater.idle()

if __name__ == '__main__':
    main()
