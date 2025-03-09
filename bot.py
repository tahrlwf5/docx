import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext
from pdf2docx import Converter
from pdf2image import convert_from_path
from pptx import Presentation
from pptx.util import Inches

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# دالة بدء البوت
def start(update: Update, context: CallbackContext):
    update.message.reply_text("أرسل لي ملف PDF وسأقوم بتحويله.")

# دالة استقبال ملف PDF
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

    # حفظ مسار الملف في بيانات المستخدم للاستخدام لاحقًا
    context.user_data['pdf_path'] = pdf_path

    # إنشاء لوحة مفاتيح لاختيار نوع التحويل
    keyboard = [
        [InlineKeyboardButton("تحويل الى ملف وورد", callback_data="word")],
        [InlineKeyboardButton("تحويل ملف الى بوربوينت", callback_data="ppt")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("اختر نوع التحويل:", reply_markup=reply_markup)

# دالة تحويل PDF إلى DOCX باستخدام pdf2docx
def convert_pdf_to_docx(pdf_path: str, output_path: str):
    cv = Converter(pdf_path)
    cv.convert(output_path, start=0, end=None)
    cv.close()

# دالة تحويل PDF إلى PPTX باستخدام pdf2image و python-pptx
def convert_pdf_to_pptx(pdf_path: str, output_path: str):
    # تحويل صفحات PDF إلى صور
    images = convert_from_path(pdf_path)
    if not images:
        raise Exception("لم يتم استخراج صور من ملف PDF.")
    
    # إنشاء عرض تقديمي جديد
    prs = Presentation()
    blank_slide_layout = prs.slide_layouts[6]  # تخطيط فارغ

    for image in images:
        # حفظ الصورة مؤقتًا
        temp_image = "temp_page.jpg"
        image.save(temp_image, "JPEG")
        # إنشاء شريحة جديدة
        slide = prs.slides.add_slide(blank_slide_layout)
        # إضافة الصورة للشريحة (يمكن ضبط الحجم حسب الحاجة)
        slide.shapes.add_picture(temp_image, Inches(0.5), Inches(0.5), width=prs.slide_width - Inches(1))
        os.remove(temp_image)
    
    prs.save(output_path)

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
        try:
            if data in ["docx_word", "doc_word"]:
                out_ext = "docx"  # سيتم إنشاء ملف بصيغة docx دائمًا
                temp_output = f"output_{chat_id}.docx"
                convert_pdf_to_docx(pdf_path, temp_output)
                # إذا كان المطلوب doc نقوم فقط بتغيير الاسم
                output_file = temp_output if data == "docx_word" else f"output_{chat_id}.doc"
            else:
                # تحويل PDF إلى PPTX
                out_ext = "pptx"
                temp_output = f"output_{chat_id}.pptx"
                convert_pdf_to_pptx(pdf_path, temp_output)
                # إذا كان المطلوب ppt نقوم بتغيير الاسم
                output_file = temp_output if data == "pptx_ppt" else f"output_{chat_id}.ppt"
            logger.info("تم التحويل بنجاح.")
        except Exception as e:
            logger.error(f"خطأ أثناء التحويل: {e}")
            query.edit_message_text("حدث خطأ أثناء تحويل الملف.")
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            return

        # إرسال الملف الناتج
        with open(temp_output, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, filename=f"converted.{out_ext}")
        query.edit_message_text("تم التحويل بنجاح وتم إرسال الملف.")

        # تنظيف الملفات المؤقتة
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        if os.path.exists(temp_output):
            os.remove(temp_output)
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
