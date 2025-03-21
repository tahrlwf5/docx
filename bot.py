import io
from docx import Document
from pptx import Presentation
from googletrans import Translator
import arabic_reshaper
from bidi.algorithm import get_display
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# أدخل توكن البوت الخاص بك هنا
TOKEN = '5284087690:AAGwKfPojQ3c-SjCHSIdeog-yN3-4Gpim1Y'

# تهيئة مترجم جوجل
translator = Translator()

def process_arabic(text: str) -> str:
    """
    إعادة تشكيل الحروف العربية وترتيبها من اليمين لليسار.
    """
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

def translate_docx(file_bytes: bytes) -> io.BytesIO:
    """
    ترجمة ملف DOCX من الإنجليزية إلى العربية مع الحفاظ على التنسيق.
    """
    document = Document(io.BytesIO(file_bytes))
    
    for paragraph in document.paragraphs:
        original_text = paragraph.text
        if original_text.strip():
            # ترجمة النص
            translated = translator.translate(original_text, src='en', dest='ar').text
            # معالجة النص العربي
            translated = process_arabic(translated)
            paragraph.text = translated
            
            # ضبط اتجاه النص إلى RTL
            pPr = paragraph._p.get_or_add_pPr()
            bidi = OxmlElement('w:bidi')
            bidi.set(qn('w:val'), "1")
            pPr.append(bidi)
    
    output = io.BytesIO()
    document.save(output)
    output.seek(0)
    return output

def translate_pptx(file_bytes: bytes) -> io.BytesIO:
    """
    ترجمة ملف PPTX من الإنجليزية إلى العربية مع الحفاظ على التنسيق.
    """
    prs = Presentation(io.BytesIO(file_bytes))
    
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                original_text = shape.text
                translated = translator.translate(original_text, src='en', dest='ar').text
                translated = process_arabic(translated)
                # تعيين النص المترجم في مربع النص
                if shape.has_text_frame:
                    shape.text = translated
                    # لضمان عرض RTL، يمكن تعديل بعض خصائص text_frame إذا دعت الحاجة.
    
    output = io.BytesIO()
    prs.save(output)
    output.seek(0)
    return output

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("مرحباً! أرسل لي ملف DOCX أو PPTX للترجمة من الإنجليزية إلى العربية.")

def handle_file(update: Update, context: CallbackContext) -> None:
    document_file = update.message.document
    file_name = document_file.file_name.lower()
    
    # تحميل الملف كـ bytes
    file = document_file.get_file()
    file_bytes = file.download_as_bytearray()

    if file_name.endswith('.docx'):
        translated_file = translate_docx(file_bytes)
        update.message.reply_document(document=translated_file, filename="translated.docx")
    elif file_name.endswith('.pptx'):
        translated_file = translate_pptx(file_bytes)
        update.message.reply_document(document=translated_file, filename="translated.pptx")
    else:
        update.message.reply_text("صيغة الملف غير مدعومة. الرجاء إرسال ملف DOCX أو PPTX.")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.document, handle_file))
    
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
