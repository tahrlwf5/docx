# استخدام صورة أساسية من Python
FROM python:3.9-slim

# تعيين مجلد العمل
WORKDIR /app

# تحديث pip إلى أحدث إصدار
RUN pip3 install --upgrade pip

# نسخ الملفات المطلوبة
COPY requirements.txt .
COPY bot.py .
COPY .env .

# تثبيت المتطلبات
RUN pip3 install --no-cache-dir -r requirements.txt

# تشغيل البوت
CMD ["python3", "bot.py"]
