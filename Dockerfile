# استخدام صورة أساسية من Python
FROM python:3.9-slim

# تعيين مجلد العمل
WORKDIR /app

# تحديث pip إلى أحدث إصدار
RUN pip install --upgrade pip

# نسخ الملفات المطلوبة
COPY requirements.txt .

# تثبيت المتطلبات
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي الملفات
COPY . .

# تشغيل البوت
CMD ["python", "bot.py"]
