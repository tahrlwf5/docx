import os
import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from convertapi import ConvertApi

ConvertApi.secret = 'secret_q4ijKpkWw17sLQx8'
TOKEN = "5146976580:AAE2yXc-JK6MIHVlLDy-O4YODucS_u7Zq-8"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def start(update, context):
    update.message.reply_text('مرحبا! أرسل لي ملف PDF وسأحوله إلى DOCX.')

def handle_pdf(update, context):
    file = update.message.document
    if file.mime_type == 'application/pdf':
        file_id = file.file_id
        new_file = context.bot.get_file(file_id)
        file_path = f"temp_{file_id}.pdf"
        new_file.download(file_path)
        
        try:
            result = ConvertApi().convert('docx', {'File': file_path})
            docx_path = f"converted_{file_id}.docx"
            result.save_files(docx_path)
            update.message.reply_document(document=open(docx_path, 'rb'))
            os.remove(file_path)
            os.remove(docx_path)
        except Exception as e:
            update.message.reply_text(f'حدث خطأ: {str(e)}')
    else:
        update.message.reply_text('الرجاء إرسال ملف PDF فقط.')

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.document, handle_pdf))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
