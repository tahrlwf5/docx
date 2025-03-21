import io, os, time
from datetime import datetime, timedelta
from docx import Document
from docx.shared import Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pptx import Presentation
from pptx.util import Pt as pptxPt
from googletrans import Translator
import arabic_reshaper
from bidi.algorithm import get_display
from telegram import Update, Message
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# أدخل توكن البوت الخاص بك هنا
TOKEN = '5284087690:AAGwKfPojQ3c-SjCHSIdeog-yN3-4Gpim1Y'

# تهيئة مترجم جوجل
translator = Translator()

# خيارات المعالجة
apply_arabic_processing = False  # لتشغيل arabic_reshaper وget_display إذا لزم الأمر
ARABIC_FONT = "Traditional Arabic"

# حدود:
MAX_FILE_SIZE = 3 * 1024 * 1024  # 3 ميجابايت
MAX_PAGES = 10                 # 10 صفحات (بالنسبة لـ PPTX: 10 شرائح، بالنسبة لـ DOCX: اعتماداً على فواصل الصفحات)
WAIT_TIME = timedelta(minutes=12)  # فترة الانتظار 12 دقيقة بين الترجمات لكل مستخدم
DAILY_LIMIT = 10               # 10 ملفات يومياً لكل مستخدم

# متغيرات لتتبع المستخدمين
user_last_translation = {}  # {user_id: datetime_of_last_translation}
user_daily_limits = {}      # {user_id: (date_str, count)}

# دوال مساعدة

def process_arabic(text: str) -> str:
    """إعادة تشكيل النص العربي إذا تم تفعيل الخيار."""
    if apply_arabic_processing:
        reshaped_text = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped_text)
        return bidi_text
    else:
        return text

def set_paragraph_rtl(paragraph):
    """ضبط اتجاه الكتابة من اليمين لليسار باستخدام خصائص XML."""
    pPr = paragraph._p.get_or_add_pPr()
    bidi = OxmlElement('w:bidi')
    bidi.set(qn('w:val'), "1")
    pPr.append(bidi)

def translate_paragraph(paragraph):
    """ترجمة النص داخل كل run من الفقرة دون إزالة العناصر غير النصية مثل الصور، وتعيين الخط وحجم الخط."""
    for run in paragraph.runs:
        if run.text.strip():
            translated_text = translator.translate(run.text, src='en', dest='ar').text
            translated_text = process_arabic(translated_text)
            run.text = translated_text
            run.font.name = ARABIC_FONT
            run.font.size = Pt(14)
    set_paragraph_rtl(paragraph)

def count_docx_pages(document: Document) -> int:
    """
    يحاول حساب عدد الصفحات في ملف DOCX عبر عد فواصل الصفحة في runs.
    إذا لم يُوجد فاصل صفحة، يُعتبر الملف صفحة واحدة.
    """
    pages = 1
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            xml = run._r.xml
            if "w:br" in xml and 'w:type="page"' in xml:
                pages += 1
    return pages

def get_all_docx_paragraphs(document: Document) -> list:
    """جمع جميع الفقرات في المستند بما فيها فقرات الجداول."""
    paras = document.paragraphs[:]
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                paras.extend(cell.paragraphs)
    return paras

def get_all_pptx_shapes(prs: Presentation) -> list:
    """جمع جميع الأشكال التي تحتوي على نص في العرض التقديمي."""
    shapes_list = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame or getattr(shape, "has_table", False):
                shapes_list.append(shape)
    return shapes_list

def add_header_docx(document: Document):
    """إضافة سطر في أعلى المستند يشير إلى أن الترجمة بواسطة البوت."""
    header_text = "تم ترجمة بواسطة البوت : @i2pdf2tbot\n\n"
    # إنشاء فقرة جديدة في البداية
    para = document.add_paragraph(header_text)
    para.runs[0].font.name = ARABIC_FONT
    para.runs[0].font.size = Pt(14)
    set_paragraph_rtl(para)
    # نقل الفقرة إلى أعلى الملف:
    document._body._element.insert(0, para._p)

def add_header_pptx(prs: Presentation):
    """إضافة شريحة في بداية العرض تحتوي على رسالة الترجمة."""
    slide_layout = prs.slide_layouts[5]  # اختيار تخطيط فارغ
    header_slide = prs.slides.add_slide(slide_layout)
    txBox = header_slide.shapes.add_textbox(left=0, top=0, width=prs.slide_width, height=pptxPt(50))
    tf = txBox.text_frame
    tf.text = "تم ترجمة بواسطة البوت : @i2pdf2tbot"
    for paragraph in tf.paragraphs:
        for run in paragraph.runs:
            run.font.name = ARABIC_FONT
            run.font.size = pptxPt(20)
    # نقل الشريحة لتكون أول شريحة
    xml_slides = prs.slides._sldIdLst  
    slides = list(xml_slides)
    xml_slides.remove(slides[-1])
    xml_slides.insert(0, slides[-1])

# دوال الترجمة مع دعم عرض النسبة المئوية

def translate_docx_with_progress(file_bytes: bytes, progress_callback) -> io.BytesIO:
    """ترجمة ملف DOCX مع تحديث نسبة التقدم عبر progress_callback."""
    document = Document(io.BytesIO(file_bytes))
    
    # التحقق من عدد الصفحات
    pages = count_docx_pages(document)
    if pages > MAX_PAGES:
        raise Exception(f"عدد صفحات الملف ({pages}) يتجاوز الحد المسموح ({MAX_PAGES}).")
    
    all_paras = get_all_docx_paragraphs(document)
    total = len(all_paras) if all_paras else 1
    for idx, paragraph in enumerate(all_paras):
        if paragraph.text.strip():
            translate_paragraph(paragraph)
        progress = int((idx+1) / total * 100)
        progress_callback(progress)
    
    add_header_docx(document)
    output = io.BytesIO()
    document.save(output)
    output.seek(0)
    return output

def translate_pptx_with_progress(file_bytes: bytes, progress_callback) -> io.BytesIO:
    """ترجمة ملف PPTX مع تحديث نسبة التقدم عبر progress_callback."""
    prs = Presentation(io.BytesIO(file_bytes))
    
    # التحقق من عدد الشرائح
    if len(prs.slides) > MAX_PAGES:
        raise Exception(f"عدد الشرائح ({len(prs.slides)}) يتجاوز الحد المسموح ({MAX_PAGES}).")
    
    shapes_list = get_all_pptx_shapes(prs)
    total = len(shapes_list) if shapes_list else 1
    for idx, shape in enumerate(shapes_list):
        # إذا كان الشكل يحتوي على مربع نص
        if hasattr(shape, "text") and shape.text.strip() and shape.has_text_frame:
            translated_text = translator.translate(shape.text, src='en', dest='ar').text
            translated_text = process_arabic(translated_text)
            shape.text = translated_text
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.name = ARABIC_FONT
                    run.font.size = pptxPt(24)
        # إذا كان الشكل يحتوي على جدول
        if getattr(shape, "has_table", False) and shape.has_table:
            table = shape.table
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        translated_text = translator.translate(cell.text, src='en', dest='ar').text
                        translated_text = process_arabic(translated_text)
                        cell.text = translated_text
                        if cell.text_frame:
                            for paragraph in cell.text_frame.paragraphs:
                                for run in paragraph.runs:
                                    run.font.name = ARABIC_FONT
                                    run.font.size = pptxPt(18)
        progress = int((idx+1) / total * 100)
        progress_callback(progress)
    
    add_header_pptx(prs)
    output = io.BytesIO()
    prs.save(output)
    output.seek(0)
    return output

# إدارة حدود المستخدم
def can_user_translate(user_id: int) -> (bool, str):
    now = datetime.now()
    # تحقق من فترة الانتظار (12 دقيقة)
    if user_id in user_last_translation:
        elapsed = now - user_last_translation[user_id]
        if elapsed < WAIT_TIME:
            remaining = WAIT_TIME - elapsed
            return False, f"انتظر {int(remaining.total_seconds()//60)} دقيقة و{int(remaining.total_seconds()%60)} ثانية قبل ترجمة ملف آخر."
    # تحقق من الحد اليومي
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

# الدوال الخاصة بالبوت

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("مرحباً! أرسل لي ملف DOCX أو PPTX للترجمة من الإنجليزية إلى العربية.")

def handle_file(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    
    # منع إرسال أكثر من ملف دفعة واحدة (إذا وُجد أكثر من ملف في الرسالة)
    if len(update.message.document.file_id.split()) > 1:
        update.message.reply_text("يرجى إرسال ملف واحد فقط في كل مرة.")
        return

    # التحقق من حدود المستخدم (فترة الانتظار والحد اليومي)
    can_translate, msg = can_user_translate(user_id)
    if not can_translate:
        update.message.reply_text(msg)
        return

    document_file = update.message.document
    file_name = document_file.file_name.lower()
    file = document_file.get_file()
    file_bytes = file.download_as_bytearray()
    
    # التحقق من حجم الملف
    if len(file_bytes) > MAX_FILE_SIZE:
        update.message.reply_text("حجم الملف أكبر من 3 ميجابايت. الرجاء إرسال ملف أصغر.")
        return

    chat_id = update.message.chat_id
    progress_msg: Message = update.message.reply_text("جارٍ الترجمة: 0%")
    
    # دالة لتحديث رسالة التقدم
    def progress_callback(percentage):
        try:
            context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_msg.message_id,
                text=f"جارٍ الترجمة: {percentage}%"
            )
        except Exception as e:
            pass

    try:
        if file_name.endswith('.docx'):
            output_file = translate_docx_with_progress(file_bytes, progress_callback)
            out_filename = "translated.docx"
        elif file_name.endswith('.pptx'):
            output_file = translate_pptx_with_progress(file_bytes, progress_callback)
            out_filename = "translated.pptx"
        else:
            update.message.reply_text("صيغة الملف غير مدعومة. الرجاء إرسال ملف DOCX أو PPTX.")
            return
    except Exception as e:
        update.message.reply_text(f"خطأ أثناء الترجمة: {str(e)}")
        return

    # حذف رسالة التقدم
    try:
        context.bot.delete_message(chat_id=chat_id, message_id=progress_msg.message_id)
    except Exception as e:
        pass

    # تحديث حدود المستخدم
    update_user_limit(user_id)
    
    update.message.reply_document(document=output_file, filename=out_filename)

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.document, handle_file))
    
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
