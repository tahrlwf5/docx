import io, os, time, json
from datetime import datetime, timedelta
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
from docx import Document
from docx.shared import Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pptx import Presentation
from pptx.util import Pt as pptxPt
from deep_translator import GoogleTranslator
import arabic_reshaper
from bidi.algorithm import get_display
from telegram import Update, Message, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
import convertapi

# الإعدادات الأساسية
TOKEN = '5153049530:AAG4LS17jVZdseUnGkodRpHzZxGLOnzc1gs'
CONVERT_API_KEY = "secret_ZJOY2tBFX1c3T3hA"
convertapi.api_secret = CONVERT_API_KEY
TEMP_FOLDER = "temp_files"
os.makedirs(TEMP_FOLDER, exist_ok=True)

# إعدادات الترجمة
apply_arabic_processing = True
ARABIC_FONT = "Arial"
MAX_FILE_SIZE = 3 * 1024 * 1024  # 3MB
MAX_PAGES = 10
WAIT_TIME = timedelta(minutes=12)
DAILY_LIMIT = 10

# تتبع الاستخدام
user_last_translation = {}
user_daily_limits = {}

# ===================== معالجة PDF مباشرة =====================
def translate_pdf_directly(input_pdf: str, output_pdf: str):
    doc = fitz.open(input_pdf)
    translator = GoogleTranslator(source='en', target='ar')
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text_blocks = page.get_text("blocks")
        
        # معالجة النصوص
        for block in sorted(text_blocks, key=lambda x: (-x[3], x[0])):
            x0, y0, x1, y1, text, block_no, block_type = block
            if block_type != 0 or not text.strip():
                continue
                
            # ترجمة ومعالجة النص
            translated_text = translator.translate(text)
            if not translated_text:
                continue
                
            reshaped_text = arabic_reshaper.reshape(translated_text)
            bidi_text = get_display(reshaped_text)
            
            # حذف النص الأصلي
            page.add_redact_annot(fitz.Rect(x0, y0, x1, y1))
            page.apply_redactions()
            
            # إضافة النص المترجم
            page.insert_textbox(
                fitz.Rect(x0, y0, x1, y1),
                bidi_text,
                fontsize=11,
                fontname=ARABIC_FONT,
                encoding=fitz.TEXT_ENCODING_UTF8,
                align=fitz.TEXT_ALIGN_RIGHT
            )
    
    doc.save(output_pdf)
    doc.close()

# ===================== معالجة OCR للصور =====================
def ocr_image(image_path):
    return pytesseract.image_to_string(Image.open(image_path), lang='eng')

def translate_image_text(image_path):
    text = ocr_image(image_path)
    return GoogleTranslator(source='en', target='ar').translate(text)

# ===================== دوال البوت =====================
def start(update: Update, context: CallbackContext):
    update.message.reply_text("مرحبا! أرسل ملف PDF/DOCX/PPTX للترجمة")

def handle_document(update: Update, context: CallbackContext):
    # ... (يبقى نفس منطق التحقق من الحجم والحدود)
    
    if file_name.endswith('.pdf'):
        # ترجمة PDF مباشرة
        translated_pdf = os.path.join(TEMP_FOLDER, f"translated_{file_name}")
        translate_pdf_directly(input_path, translated_pdf)
        # إرسال الملف المترجم
        update.message.reply_document(open(translated_pdf, 'rb'))
    else:
        # معالجة DOCX/PPTX كما كان
        # ... (كود الترجمة الحالي)
        
# ===================== بقية الدوال =====================
# ... (تحافظ على نفس المنطق لإدارة المستخدمين والحدود)

if __name__ == '__main__':
    updater = Updater(TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.document, handle_document))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
