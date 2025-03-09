FROM python:3.11-slim

# تثبيت libgl1 المطلوبة بواسطة OpenCV
RUN apt-get update && apt-get install -y libgl1

WORKDIR /app

# نسخ ملف المتطلبات وتثبيت المكتبات
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . .

# تشغيل البوت
CMD ["python", "bot.py"]
