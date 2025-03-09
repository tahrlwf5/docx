import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext
from pdf2docx import Converter

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# دالة بدء البوت
def start(update: Update, context: CallbackContext):
    update.message.reply_text("أرسل لي ملف PDF وسأقوم بتحويله.")

# عند استقبال ملف PDF
def pdf_handler(update: Update, context: CallbackContext):
    document = update.message.document
    if document.mime_type != 'application/pdf':
        update.message.reply_text("الرجاء إرسال ملف PDF صالح.")
        return

    chat_id = update.effective_chat.id
    file_id = document.file_id
    new_file = context.bot.getFile(file_id)
    
    # تخزين الملف باسم فريد لكل دردشة
    pdf_path = f"input_{chat_id}.pdf"
    new_file.download(pdf_path)
    logger.info("تم تنزيل الملف بنجاح.")

    # حفظ مسار الملف في بيانات المستخدم للاستخدام في callbacks
    context.user_data['pdf_path'] = pdf_path

    # إنشاء لوحة مفاتيح لاختيار نوع التحويل
    keyboard = [
        [InlineKeyboardButton("تحويل الى ملف وورد", callback_data="word")],
        [InlineKeyboardButton("تحويل ملف الى بوربوينت", callback_data="ppt")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("اختر نوع التحويل:", reply_markup=reply_markup)

# دالة معالجة CallbackQuery
def callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    chat_id = update.effective_chat.id
    pdf_path = context.user_data.get('pdf_path')
    if not pdf_path or not os.path.exists(pdf_path):
        query.edit_message_text("لم يتم العثور على ملف PDF المحمل. الرجاء إرسال الملف مرة أخرى.")
        return

    data = query.data

    # إذا كانت القيمة "word" أو "ppt" نعرض خيارات الامتداد
    if data == "word":
        keyboard = [
            [InlineKeyboardButton("docx", callback_data="docx_word"),
             InlineKeyboardButton("doc", callback_data="doc_word")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text("اختر الامتداد لملف وورد:", reply_markup=reply_markup)
    elif data == "ppt":
        keyboard = [
            [InlineKeyboardButton("pptx", callback_data="pptx_ppt"),
             InlineKeyboardButton("ppt", callback_data="ppt_ppt")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text("اختر الامتداد لملف بوربوينت:", reply_markup=reply_markup)
    # الخيارات النهائية للتحويل
    elif data in ["docx_word", "doc_word", "pptx_ppt", "ppt_ppt"]:
        # تحديد الامتداد المطلوب
        if data in ["docx_word", "doc_word"]:
            # سنحول باستخدام pdf2docx ونخرج ملف بصيغة docx، وإذا كان المطلوب doc سنغير الاسم
            out_ext = "docx" if data == "docx_word" else "doc"
            output_file = f"output_{chat_id}.{out_ext}"
        else:
            # نفس الفكرة بالنسبة للبوربوينت (للأغراض التجريبية)
            out_ext = "pptx" if data == "pptx_ppt" else "ppt"
            output_file = f"output_{chat_id}.{out_ext}"

        try:
            # تحويل الملف باستخدام pdf2docx (يتم دائماً إنشاء ملف بصيغة docx)
            temp_output = f"temp_output_{chat_id}.docx"
            cv = Converter(pdf_path)
            cv.convert(temp_output, start=0, end=None)
            cv.close()
            logger.info("تم التحويل بنجاح.")
            
            # إذا كان الامتداد المطلوب ليس docx، نقوم بتغيير اسم الملف (هذه خطوة سطحية)
            if out_ext != "docx":
                os.rename(temp_output, output_file)
            else:
                output_file = temp_output

        except Exception as e:
            logger.error(f"خطأ أثناء التحويل: {e}")
            query.edit_message_text("حدث خطأ أثناء تحويل الملف.")
            # حذف الملف المؤقت إذا وُجد
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            return

        # إرسال الملف الناتج
        with open(output_file, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, filename=f"converted.{out_ext}")
        query.edit_message_text("تم التحويل بنجاح وتم إرسال الملف.")

        # تنظيف الملفات المؤقتة
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        if os.path.exists(output_file):
            os.remove(output_file)
    else:
        query.edit_message_text("خيار غير معروف.")

# دالة لمعالجة الأخطاء
def error_handler(update: Update, context: CallbackContext):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("يرجى تعيين متغير البيئة TELEGRAM_BOT_TOKEN")
        return

    updater = Updater(token, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.document.pdf, pdf_handler))
    dispatcher.add_handler(CallbackQueryHandler(callback_handler))
    dispatcher.add_error_handler(error_handler)

    updater.start_polling()
    logger.info("البوت يعمل الآن...")
    updater.idle()

if __name__ == '__main__':
    main()
