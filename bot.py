import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pdf2docx import Converter

# إعدادات البوت
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('مرحبا! أرسل لي ملف PDF لتحويله إلى DOCX')

async def convert_pdf_to_docx(pdf_path, docx_path):
    try:
        cv = Converter(pdf_path)
        cv.convert(docx_path)
        cv.close()
        return True
    except Exception as e:
        print(f"Error converting file: {e}")
        return False

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    
    if document.mime_type == 'application/pdf':
        file = await context.bot.get_file(document.file_id)
        file_name = document.file_name or 'document.pdf'
        
        # تنزيل الملف
        await update.message.reply_text('جارٍ معالجة الملف...')
        await file.download_to_drive(file_name)
        
        # التحويل
        docx_file = os.path.splitext(file_name)[0] + '.docx'
        if await convert_pdf_to_docx(file_name, docx_file):
            await update.message.reply_document(document=open(docx_file, 'rb'))
            
            # تنظيف الملفات المؤقتة
            os.remove(file_name)
            os.remove(docx_file)
        else:
            await update.message.reply_text('فشل التحويل. يرجى التأكد من أن الملف صالح')
    else:
        await update.message.reply_text('الرجاء إرسال ملف PDF فقط')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('أرسل لي ملف PDF وسأقوم بتحويله إلى مستند Word')

def main():
    application = Application.builder().token(TOKEN).build()

    # handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    application.run_polling()

if __name__ == '__main__':
    main()
