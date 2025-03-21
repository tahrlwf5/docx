import os
import io
import time
from datetime import datetime, timedelta

# مكتبات تحويل الملفات والوثائق
from docx import Document
from docx.shared import Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pptx import Presentation
from pptx.util import Pt as pptxPt

# مكتبة الترجمة
from googletrans import Translator

# مكتبات معالجة النص العربي
import arabic_reshaper
from bidi.algorithm import get_display

# مكتبات التليجرام
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler

# مكتبة ConvertAPI لتحويل الملفات
import convertapi

# استيراد وظائف قاعدة البيانات
from database import add_user, get_user_count, send_translated_file_to_channel
from database import send_translated_file_to_channel
from database import CHANNEL_ID

# تحميل متغيرات البيئة المطلوبة
TOKEN = os.environ.get("BOT_TOKEN")
CONVERT_API_KEY = os.environ.get("CONVERT_API_KEY")
convertapi.api_secret = CONVERT_API_KEY

# مجلد التخزين المؤقت
TEMP_FOLDER = "temp_files"
os.makedirs(TEMP_FOLDER, exist_ok=True)

# تهيئة مترجم جوجل
translator = Translator()

# إعدادات المعالجة والخطوط
apply_arabic_processing = False  # قم بتعديلها حسب الحاجة
ARABIC_FONT = "Traditional Arabic"

# الحدود والإعدادات
MAX_FILE_SIZE = 3 * 1024 * 1024       # 3 ميجابايت
MAX_PAGES = 10                        # 10 صفحات (أو 10 شرائح في PPTX)
WAIT_TIME = timedelta(minutes=12)     # فترة انتظار 12 دقيقة لكل مستخدم
DAILY_LIMIT = 10                      # 10 ملفات يومياً لكل مستخدم

# إدارة حدود الاستخدام (مؤقتة في الذاكرة)
user_last_translation = {}  # {user_id: datetime}
user_daily_limits = {}      # {user_id: (date_str, count)}

# دوال معالجة الوثائق والترجمة

def process_arabic(text: str) -> str:
    if apply_arabic_processing:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    return text

def set_paragraph_rtl(paragraph):
    pPr = paragraph._p.get_or_add_pPr()
    bidi = OxmlElement('w:bidi')
    bidi.set(qn('w:val'), "1")
    pPr.append(bidi)

def translate_paragraph(paragraph):
    for run in paragraph.runs:
        if run.text.strip():
            translated = translator.translate(run.text, src='en', dest='ar').text
            run.text = process_arabic(translated)
            run.font.name = ARABIC_FONT
            run.font.size = Pt(14)
    set_paragraph_rtl(paragraph)

def count_docx_pages(document: Document) -> int:
    pages = 1
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            xml = run._r.xml
            if "w:br" in xml and 'w:type="page"' in xml:
                pages += 1
    return pages

def get_all_docx_paragraphs(document: Document) -> list:
    paras = document.paragraphs[:]
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                paras.extend(cell.paragraphs)
    return paras

def get_all_pptx_shapes(prs: Presentation) -> list:
    shapes = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame or getattr(shape, "has_table", False):
                shapes.append(shape)
    return shapes

def add_header_docx(document: Document):
    header = "تم ترجمة بواسطة البوت : @i2pdf2tbot\n\n"
    para = document.add_paragraph(header)
    para.runs[0].font.name = ARABIC_FONT
    para.runs[0].font.size = Pt(14)
    set_paragraph_rtl(para)
    document._body._element.insert(0, para._p)

def add_header_pptx(prs: Presentation):
    slide_layout = prs.slide_layouts[5]
    header_slide = prs.slides.add_slide(slide_layout)
    txBox = header_slide.shapes.add_textbox(0, 0, prs.slide_width, pptxPt(50))
    tf = txBox.text_frame
    tf.text = "تم ترجمة بواسطة البوت : @i2pdf2tbot"
    for para in tf.paragraphs:
        for run in para.runs:
            run.font.name = ARABIC_FONT
            run.font.size = pptxPt(20)
    xml_slides = prs.slides._sldIdLst
    slides = list(xml_slides)
    xml_slides.remove(slides[-1])
    xml_slides.insert(0, slides[-1])

def translate_docx_with_progress(file_bytes: bytes, progress_callback) -> io.BytesIO:
    document = Document(io.BytesIO(file_bytes))
    if count_docx_pages(document) > MAX_PAGES:
        raise Exception(f"عدد الصفحات يتجاوز الحد المسموح ({MAX_PAGES}).")
    paras = get_all_docx_paragraphs(document)
    total = len(paras) if paras else 1
    for idx, para in enumerate(paras):
        if para.text.strip():
            translate_paragraph(para)
        progress_callback(int((idx+1) / total * 100))
    add_header_docx(document)
    output = io.BytesIO()
    document.save(output)
    output.seek(0)
    return output

def translate_pptx_with_progress(file_bytes: bytes, progress_callback) -> io.BytesIO:
    prs = Presentation(io.BytesIO(file_bytes))
    if len(prs.slides) > MAX_PAGES:
        raise Exception(f"عدد الشرائح يتجاوز الحد المسموح ({MAX_PAGES}).")
    shapes = get_all_pptx_shapes(prs)
    total = len(shapes) if shapes else 1
    for idx, shape in enumerate(shapes):
        if hasattr(shape, "text") and shape.text.strip() and shape.has_text_frame:
            translated = translator.translate(shape.text, src='en', dest='ar').text
            shape.text = process_arabic(translated)
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    run.font.name = ARABIC_FONT
                    run.font.size = pptxPt(24)
        if getattr(shape, "has_table", False) and shape.has_table:
            table = shape.table
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        translated = translator.translate(cell.text, src='en', dest='ar').text
                        cell.text = process_arabic(translated)
                        if cell.text_frame:
                            for para in cell.text_frame.paragraphs:
                                for run in para.runs:
                                    run.font.name = ARABIC_FONT
                                    run.font.size = pptxPt(18)
        progress_callback(int((idx+1) / total * 100))
    add_header_pptx(prs)
    output = io.BytesIO()
    prs.save(output)
    output.seek(0)
    return output

# ===================== إدارة حدود الاستخدام =====================
def can_user_translate(user_id: int) -> (bool, str):
    now = datetime.now()
    if user_id in user_last_translation:
        elapsed = now - user_last_translation[user_id]
        if elapsed < WAIT_TIME:
            remaining = WAIT_TIME - elapsed
            return False, f"انتظر {int(remaining.total_seconds()//60)} دقيقة و{int(remaining.total_seconds()%60)} ثانية قبل ترجمة ملف آخر."
    date_str = now.strftime("%Y-%m-%d")
    if user_id in user_daily_limits:
        last_date, count = user_daily_limits[user_id]
        if last_date == date_str and count >= DAILY_LIMIT:
            return False, "لقد تجاوزت الحد اليومي المسموح (10 ملفات)."
    return True, ""

def update_user_limit(user_id: int):
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    user_last_translation[user_id] = now
    if user_id in user_daily_limits:
        last_date, count = user_daily_limits[user_id]
        if last_date == date_str:
            user_daily_limits[user_id] = (date_str, count + 1)
        else:
            user_daily_limits[user_id] = (date_str, 1)
    else:
        user_daily_limits[user_id] = (date_str, 1)

# ===================== دوال تحويل باستخدام ConvertAPI =====================
def convert_file(input_path: str, output_format: str, output_path: str):
    result = convertapi.convert(output_format, {'File': input_path})
    result.save_files(output_path)

# ===================== دوال البوت =====================
def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("قناة البوت", url="https://t.me/i2pdfbotchannel"),
         InlineKeyboardButton("المطور", url="https://t.me/ta_ja199")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("مرحباً! هل أنت مستعد؟\nأرسل لي ملف PDF أو DOCX أو PPTX.", reply_markup=reply_markup)

def handle_file(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    user_id = user.id
    add_user(user_id, user.username or "", user.first_name or "", user.last_name or "")
    
    if len(update.message.document.file_id.split()) > 1:
        update.message.reply_text("يرجى إرسال ملف واحد فقط في كل مرة.")
        return
    can_translate, msg = can_user_translate(user_id)
    if not can_translate:
        update.message.reply_text(msg)
        return

    document_file = update.message.document
    file_name = document_file.file_name.lower()
    file = document_file.get_file()
    file_bytes = file.download_as_bytearray()
    if len(file_bytes) > MAX_FILE_SIZE:
        update.message.reply_text("حجم الملف أكبر من 3 ميجابايت. الرجاء إرسال ملف أصغر.")
        return

    context.user_data['file_id'] = document_file.file_id
    context.user_data['file_name'] = file_name

    if document_file.mime_type == "application/pdf":
        keyboard = [
            [InlineKeyboardButton("تحويل إلى DOCX", callback_data="pdf2docx")],
            [InlineKeyboardButton("تحويل إلى PPTX", callback_data="pdf2pptx")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("اختر نوع التحويل:", reply_markup=reply_markup)
    elif document_file.mime_type in [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    ]:
        keyboard = [[InlineKeyboardButton("تحويل إلى PDF", callback_data="to_pdf")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("اختر نوع التحويل:", reply_markup=reply_markup)
    else:
        update.message.reply_text("صيغة الملف غير مدعومة.")

def update_progress(context: CallbackContext, chat_id: int, message_id: int, percentage: int):
    try:
        context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"جارٍ الترجمة: {percentage}%")
    except Exception:
        pass

def cleanup_files(files: list):
    for path in files:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    action = query.data
    file_id = context.user_data.get('file_id')
    file_name = context.user_data.get('file_name')
    if not file_id or not file_name:
        query.edit_message_text("حدث خطأ، يرجى إعادة إرسال الملف.")
        return

    if action in ["pdf2docx", "pdf2pptx"]:
        process_pdf_file(action, update, context)
    elif action == "to_pdf":
        process_office_file(update, context)
    else:
        query.edit_message_text("عملية غير معروفة.")

def process_pdf_file(action: str, update: Update, context: CallbackContext):
    query = update.callback_query
    file_id = context.user_data.get('file_id')
    file_name = context.user_data.get('file_name')
    ext = "docx" if action == "pdf2docx" else "pptx"
    base_name = os.path.splitext(file_name)[0]
    input_pdf_path = os.path.join(TEMP_FOLDER, file_name)
    converted_path = os.path.join(TEMP_FOLDER, base_name + f".{ext}")
    translated_path = os.path.join(TEMP_FOLDER, base_name + f"_translated.{ext}")
    final_pdf_path = os.path.join(TEMP_FOLDER, base_name + f"_translated.pdf")

    pdf_file = context.bot.getFile(file_id)
    pdf_file.download(input_pdf_path)

    query.edit_message_text(f"جارٍ تحويل الملف من PDF إلى {ext.upper()} ...")
    try:
        convert_file(input_pdf_path, ext, converted_path)
    except Exception as e:
        query.edit_message_text(f"حدث خطأ أثناء تحويل الملف: {str(e)}")
        cleanup_files([input_pdf_path])
        return

    query.edit_message_text("جارٍ ترجمة الملف المحوّل...")
    try:
        if ext == "docx":
            with open(converted_path, "rb") as f:
                file_bytes = f.read()
            progress_msg = query.message.reply_text("جارٍ الترجمة: 0%")
            translated_file_io = translate_docx_with_progress(file_bytes, lambda p: update_progress(context, query.message.chat_id, progress_msg.message_id, p))
            with open(translated_path, "wb") as f:
                f.write(translated_file_io.getbuffer())
        else:
            with open(converted_path, "rb") as f:
                file_bytes = f.read()
            progress_msg = query.message.reply_text("جارٍ الترجمة: 0%")
            translated_file_io = translate_pptx_with_progress(file_bytes, lambda p: update_progress(context, query.message.chat_id, progress_msg.message_id, p))
            with open(translated_path, "wb") as f:
                f.write(translated_file_io.getbuffer())
    except Exception as e:
        query.edit_message_text(f"حدث خطأ أثناء الترجمة: {str(e)}")
        cleanup_files([input_pdf_path, converted_path])
        return
    try:
        context.bot.delete_message(chat_id=query.message.chat_id, message_id=progress_msg.message_id)
    except Exception:
        pass

    query.edit_message_text("جارٍ تحويل الملف المترجم إلى PDF...")
    try:
        convert_file(translated_path, "pdf", final_pdf_path)
    except Exception as e:
        query.edit_message_text(f"حدث خطأ أثناء تحويل الملف إلى PDF: {str(e)}")
        cleanup_files([input_pdf_path, converted_path, translated_path])
        return

    query.edit_message_text("تمت العملية بنجاح!")
    context.bot.send_document(chat_id=query.message.chat_id, document=open(translated_path, "rb"), filename=os.path.basename(translated_path))
    keyboard = [[InlineKeyboardButton("تعديل pdf", url="https://t.me/i2pdfbot")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_document(chat_id=query.message.chat_id, document=open(final_pdf_path, "rb"), filename=os.path.basename(final_pdf_path), reply_markup=reply_markup)

    # إرسال الملف المترجم إلى القناة للمراقبة
    context.bot.send_document(chat_id=CHANNEL_ID, document=open(translated_path, "rb"), filename=os.path.basename(translated_path))
    caption_text = f"""
📂 **ملف مترجم جديد!**  
👤 **المستخدم:** [{user.first_name}](tg://user?id={user.id})  
🆔 **المعرف:** `{user.id}`  
📄 **اسم الملف:** `{os.path.basename(translated_path)}`
"""

context.bot.send_document(
    chat_id=CHANNEL_ID,
    document=open(translated_path, "rb"),
    filename=os.path.basename(translated_path),
    caption=caption_text,
    parse_mode="Markdown"
)

    
    update_user_limit(query.from_user.id)
    cleanup_files([input_pdf_path, converted_path, translated_path, final_pdf_path])

def process_office_file(update: Update, context: CallbackContext):
    query = update.callback_query
    file_id = context.user_data.get('file_id')
    file_name = context.user_data.get('file_name')
    ext = "docx" if file_name.endswith(".docx") else "pptx"
    base_name = os.path.splitext(file_name)[0]
    input_path = os.path.join(TEMP_FOLDER, file_name)
    translated_path = os.path.join(TEMP_FOLDER, base_name + f"_translated.{ext}")
    final_pdf_path = os.path.join(TEMP_FOLDER, base_name + f"_translated.pdf")

    office_file = context.bot.getFile(file_id)
    office_file.download(input_path)

    query.edit_message_text("جارٍ ترجمة الملف...")
    try:
        if ext == "docx":
            with open(input_path, "rb") as f:
                file_bytes = f.read()
            progress_msg = query.message.reply_text("جارٍ الترجمة: 0%")
            translated_file_io = translate_docx_with_progress(file_bytes, lambda p: update_progress(context, query.message.chat_id, progress_msg.message_id, p))
            with open(translated_path, "wb") as f:
                f.write(translated_file_io.getbuffer())
        else:
            with open(input_path, "rb") as f:
                file_bytes = f.read()
            progress_msg = query.message.reply_text("جارٍ الترجمة: 0%")
            translated_file_io = translate_pptx_with_progress(file_bytes, lambda p: update_progress(context, query.message.chat_id, progress_msg.message_id, p))
            with open(translated_path, "wb") as f:
                f.write(translated_file_io.getbuffer())
    except Exception as e:
        query.edit_message_text(f"حدث خطأ أثناء الترجمة: {str(e)}")
        cleanup_files([input_path])
        return
    try:
        context.bot.delete_message(chat_id=query.message.chat_id, message_id=progress_msg.message_id)
    except Exception:
        pass

    query.edit_message_text("جارٍ تحويل الملف المترجم إلى PDF...")
    try:
        convert_file(translated_path, "pdf", final_pdf_path)
    except Exception as e:
        query.edit_message_text(f"حدث خطأ أثناء تحويل الملف إلى PDF: {str(e)}")
        cleanup_files([input_path, translated_path])
        return

    query.edit_message_text("تمت العملية بنجاح!")
    context.bot.send_document(chat_id=query.message.chat_id, document=open(translated_path, "rb"), filename=os.path.basename(translated_path))
    keyboard = [[InlineKeyboardButton("تعديل pdf", url="https://t.me/i2pdfbot")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_document(chat_id=query.message.chat_id, document=open(final_pdf_path, "rb"), filename=os.path.basename(final_pdf_path), reply_markup=reply_markup)

    # إرسال الملف المترجم إلى القناة للمراقبة
    context.bot.send_document(chat_id=CHANNEL_ID, document=open(translated_path, "rb"), filename=os.path.basename(translated_path))
    # إرسال الملف المترجم إلى القناة
context.bot.send_document(
    chat_id=CHANNEL_ID,
    document=open(translated_path, "rb"),
    filename=os.path.basename(translated_path)
)

# 🔹 إضافة معلومات المستخدم مع الملف المترجم
caption_text = f"""
📂 **ملف مترجم جديد!**  
👤 **المستخدم:** [{first_name}](tg://user?id={user_id})  
🆔 **المعرف:** `{user_id}`  
📄 **اسم الملف:** `{os.path.basename(translated_path)}`
"""

with open(translated_path, "rb") as file:
    context.bot.send_document(
        chat_id=CHANNEL_ID,
        document=file,
        filename=os.path.basename(translated_path),
        caption=caption_text,
        parse_mode="Markdown"
    )

    
    update_user_limit(query.from_user.id)
    cleanup_files([input_path, translated_path, final_pdf_path])

def user_count(update: Update, context: CallbackContext) -> None:
    count = get_user_count()
    update.message.reply_text(f"عدد المستخدمين الحالي: {count}")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("user", user_count))
    dp.add_handler(MessageHandler(Filters.document, handle_file))
    dp.add_handler(CallbackQueryHandler(button_handler))
    
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
