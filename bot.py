import os
from dotenv import load_dotenv

# تحميل المتغيرات من ملف .env (إذا وُجد)
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# التأكد من أنه تم تحميل القيم بشكل صحيح
if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise Exception("تعذر تحميل المتغيرات البيئية اللازمة. تأكد من ملف .env أو إعداد المتغيرات البيئية في النظام.")

# استخدام المتغيرات في إعداد البوت ومفتاح OpenAI
import logging
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import openai

# إعداد مفتاح OpenAI من المتغيرات البيئية
openai.api_key = OPENAI_API_KEY

# تهيئة تسجيل الأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

def translate_text(text: str) -> str:
    """
    ترسل الرسالة إلى OpenAI API لترجمتها من الإنجليزية إلى العربية مع الحفاظ على تنسيق النص.
    """
    prompt = (
        "ترجم النص التالي من الإنجليزية إلى العربية مع الحفاظ على التنسيق (مثل تنسيق Markdown، "
        "bold، italic، وغيرها):\n\n"
        f"{text}"
    )
    try:
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=1000,
            temperature=0.3,
            n=1,
            stop=None
        )
        translation = response.choices[0].text.strip()
        return translation
    except Exception as e:
        logger.error("خطأ أثناء الترجمة: %s", e)
        return "حدث خطأ أثناء الترجمة. يرجى المحاولة مرة أخرى لاحقاً."

def start(update: Update, context: CallbackContext) -> None:
    """تعامل مع أمر /start لبدء المحادثة."""
    welcome_message = (
        "مرحباً! أرسل لي رسالة باللغة الإنجليزية وسأترجمها إلى العربية مع الحفاظ على التنسيق قدر الإمكان."
    )
    update.message.reply_text(welcome_message)

def translate_message(update: Update, context: CallbackContext) -> None:
    """تعالج الرسائل النصية وتترجمها."""
    input_text = update.message.text
    translation = translate_text(input_text)
    update.message.reply_text(translation, parse_mode=ParseMode.MARKDOWN)

def main() -> None:
    """نقطة البداية لتشغيل البوت."""
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, translate_message))

    updater.start_polling()
    logger.info("البوت يعمل الآن. انتظر الرسائل...")
    updater.idle()

if __name__ == '__main__':
    main()
