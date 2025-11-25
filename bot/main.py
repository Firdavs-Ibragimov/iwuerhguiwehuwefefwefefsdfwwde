# bot.py — Academy Pro Network Sertifikat Bot (PDF + QR, faqat local)

import os
import asyncio
import base64
import json
import random
from datetime import datetime, timedelta
from io import BytesIO

from jinja2 import Template
from playwright.async_api import async_playwright
import qrcode

import telebot
from telebot import types

# ================== TOKEN ==================
TOKEN = "8274353710:AAE9ugiSUWtbJdRKja-BeDwxccRLJKPvwwg"
bot = telebot.TeleBot(TOKEN)

# ================== PATHS ==================
BASE_DIR = os.path.dirname(__file__)
TEMPLATE_PNG = os.path.join(BASE_DIR, "template.png")
TEMPLATE_HTML = os.path.join(BASE_DIR, "template.html")
OUTPUT_DIR = os.path.join(BASE_DIR, "../certificates/certs")
USED_IDS_FILE = os.path.join(BASE_DIR, "used_ids.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ================== BACKGROUND ==================
with open(TEMPLATE_PNG, "rb") as f:
    BG_BASE64 = "data:image/png;base64," + base64.b64encode(f.read()).decode()

with open(TEMPLATE_HTML, "r", encoding="utf-8") as f:
    HTML_TEMPLATE = f.read()

# ================== COURSES ==================
COURSES = {
    "web": "WEB DASTURLASH",
    "comp": "KOMPYUTER SAVODXONLIGI",
    "cyber": "KIBERXAVFSIZLIK",
    "design": "GRAFIK DIZAYN"
}

# ================== UNIQUE ID ==================
used_ids = {}
if os.path.exists(USED_IDS_FILE):
    try:
        with open(USED_IDS_FILE, "r", encoding="utf-8") as f:
            used_ids = json.load(f)
    except:
        pass

def save_used_ids():
    with open(USED_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(used_ids, f, ensure_ascii=False, indent=2)

def get_prefix(course):
    words = [w for w in course.strip().upper().split() if w.isalpha()]
    return "".join(word[0] for word in words[:2]) or "AP"

def generate_unique_id(prefix):
    prefix = prefix.upper()
    used = used_ids.get(prefix, [])
    while True:
        num = random.randint(1000, 9999)
        new_id = f"{prefix}{num}"
        if new_id not in used:
            used.append(new_id)
            used_ids[prefix] = used
            save_used_ids()
            return new_id

# ================== QR CODE ==================
def generate_pdf_qr(pdf_path):
    # file:// link har doim o‘z qurilmada ishlaydi
    file_url = f"file:///{os.path.abspath(pdf_path).replace(os.sep, '/')}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(file_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode()

# ================== CERTIFICATE CREATION ==================
async def create_certificate(name, course, date_str):
    cert_id = generate_unique_id(get_prefix(course))
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in name.strip())
    pdf_path = os.path.join(OUTPUT_DIR, f"{safe_name}.pdf")

    qr_code = generate_pdf_qr(pdf_path)

    html = Template(HTML_TEMPLATE).render(
        name=name.strip().upper(),
        course=course.strip().upper(),
        date=date_str,
        cert_id=cert_id,
        qr_code=qr_code,
        background=BG_BASE64
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_viewport_size({"width": 3508, "height": 2480})
        await page.set_content(html, wait_until="networkidle")
        await page.add_style_tag(content="""
            @page { size: 297mm 210mm; margin: 0 !important; }
            .page { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
        """)
        await page.pdf(
            path=pdf_path,
            width="297mm",
            height="210mm",
            print_background=True,
            margin={"top":"0mm","right":"0mm","bottom":"0mm","left":"0mm"},
            prefer_css_page_size=True
        )
        await browser.close()

    return pdf_path, cert_id

# ================== USER DATA ==================
user_data = {}

# ================== BOT HANDLERS ==================
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Assalomu alaykum! Sertifikat olish uchun ism-familiyangizni kiriting:")
    user_data[message.chat.id] = {"step": "name"}

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get("step") == "name")
def get_name(message):
    user_data[message.chat.id] = {"name": message.text.strip(), "step": "date_choice"}
    markup = types.InlineKeyboardMarkup()
    tz_now = datetime.utcnow() + timedelta(hours=5)  # Tashkent UTC+5
    today = tz_now.strftime("%d.%m.%Y")
    yesterday = (tz_now - timedelta(days=1)).strftime("%d.%m.%Y")
    tomorrow = (tz_now + timedelta(days=1)).strftime("%d.%m.%Y")

    markup.row(
        types.InlineKeyboardButton(f"Bugun ({today})", callback_data="date_today"),
        types.InlineKeyboardButton(f"Kecha ({yesterday})", callback_data="date_yesterday")
    )
    markup.row(types.InlineKeyboardButton(f"Ertaga ({tomorrow})", callback_data="date_tomorrow"))
    markup.row(types.InlineKeyboardButton("Boshqa sana", callback_data="date_custom"))

    bot.send_message(message.chat.id, "Sana kiriting yoki tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("date_"))
def handle_date(call):
    chat_id = call.message.chat.id
    if chat_id not in user_data: return

    tz_now = datetime.utcnow() + timedelta(hours=5)  # Tashkent UTC+5
    if call.data == "date_today":
        date = tz_now.strftime("%d.%m.%Y")
    elif call.data == "date_yesterday":
        date = (tz_now - timedelta(days=1)).strftime("%d.%m.%Y")
    elif call.data == "date_tomorrow":
        date = (tz_now + timedelta(days=1)).strftime("%d.%m.%Y")
    elif call.data == "date_custom":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "Sanani o‘zingiz kiriting (masalan: 25.11.2025):")
        user_data[chat_id]["step"] = "date_custom_input"
        return

    user_data[chat_id]["date"] = date
    user_data[chat_id]["step"] = "course"
    show_courses(chat_id)

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get("step") == "date_custom_input")
def get_custom_date(message):
    user_data[message.chat.id]["date"] = message.text.strip()
    user_data[message.chat.id]["step"] = "course"
    show_courses(message.chat.id)

def show_courses(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Web Dasturlash", callback_data="web"),
        types.InlineKeyboardButton("Kompyuter Savodxonligi", callback_data="comp"),
        types.InlineKeyboardButton("Kiberxavfsizlik", callback_data="cyber"),
        types.InlineKeyboardButton("Grafik Dizayn", callback_data="design")
    )
    bot.send_message(chat_id, "Kursni tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in COURSES)
def handle_course(call):
    chat_id = call.message.chat.id
    user = user_data.get(chat_id)
    if not user or "date" not in user: return

    course = COURSES[call.data]
    name = user["name"]
    date = user["date"]

    msg = bot.send_message(chat_id, "Sertifikat tayyorlanmoqda... Iltimos kuting (15-25 sekund)")

    try:
        pdf_path, cert_id = asyncio.run(create_certificate(name, course, date))

        # PDF jo‘natish
        with open(pdf_path, "rb") as doc:
            bot.send_document(chat_id, doc, caption=f"{name}.pdf")

        bot.delete_message(chat_id, msg.message_id)
        bot.send_message(chat_id, "Sertifikat muvaffaqiyatli yaratildi!\nYana yaratish uchun /start bosing.")
        user_data.pop(chat_id, None)

    except Exception as e:
        bot.send_message(chat_id, "Xatolik yuz berdi. Qayta urining.")
        print("XATO:", e)

# ================== BOT START ==================
print("Bot ishga tushdi — PDF + QR code ishlaydi (faqat o‘z qurilmada)!")
bot.infinity_polling()
