import logging
import os
import pdfcrowd
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# إعداد السجل للتتبع
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# بيانات التوكن الخاص بالبوت
TELEGRAM_TOKEN = '5153049530:AAG4LS17jVZdseUnGkodRpHzZxGLOnzc1gs'

# بيانات حساب pdfcrowd
PDFCROWD_USERNAME = 'your_username'  # عدلها باسم المستخدم الخاص بك في pdfcrowd
PDFCROWD_API_KEY = '0419e795ea62ad1d4fcd5dcf7a5b8031'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحبًا، أرسل لي ملف PDF وسأقوم بتحويله إلى HTML.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    # التأكد من أن الملف من نوع PDF
    if document.mime_type != 'application/pdf':
        await update.message.reply_text("يرجى إرسال ملف PDF فقط.")
        return

    file_id = document.file_id
    new_file = await context.bot.get_file(file_id)
    
    # إنشاء مجلد للتنزيل إذا لم يكن موجوداً
    os.makedirs("downloads", exist_ok=True)
    file_path = os.path.join("downloads", document.file_name)
    await new_file.download_to_drive(custom_path=file_path)
    
    # تحويل PDF إلى HTML باستخدام pdfcrowd API
    try:
        # ننشئ عميل pdfcrowd (افترضنا توفر PdfToHtmlClient للتحويل)
        client = pdfcrowd.PdfToHtmlClient(PDFCROWD_USERNAME, PDFCROWD_API_KEY)
        # تحويل الملف إلى نص HTML
        html_content = client.convertFileToString(file_path)
        # تحديد مسار ملف HTML الناتج
        html_file_path = file_path.replace(".pdf", ".html")
        with open(html_file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
    except pdfcrowd.Error as e:
        await update.message.reply_text(f"حدث خطأ أثناء تحويل الملف: {str(e)}")
        return

    # إرسال ملف HTML إلى المستخدم
    with open(html_file_path, "rb") as html_file:
        await update.message.reply_document(document=html_file, filename=os.path.basename(html_file_path))
    
    # حذف الملفات المؤقتة (اختياري)
    os.remove(file_path)
    os.remove(html_file_path)

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    # التعامل مع الرسائل التي تحتوي على ملف PDF
    application.add_handler(MessageHandler(filters.Document.PDF, handle_document))

    application.run_polling()

if __name__ == '__main__':
    main()
