from flask import Flask, request, render_template_string
import threading
import time
import telebot
from telebot.types import *
from pymongo import MongoClient
import os

# === CONFIGURATION ===
API_TOKEN = '8014049142:AAEj1gO3tD-HFrzc5gXrrNaNbCmGhJ4Vfb8'
CHANNEL_USERNAME = '@gsjdndnejdn'
ADMIN_USER_ID = [7592464127, 5022283560]
WELCOME_IMAGE_URL = 'https://i.ibb.co/CK5D69LC/MMJABGQTIHLELKL.jpg'
MONGO_URI = 'mongodb+srv://DATEBOT:DATEBOT@cluster0.817ghth.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

# === DATABASE ===
client = MongoClient(MONGO_URI)
db = client.botdb
config = db.config.find_one() or {}

def save_data():
    try:
        db.config.update_one({}, {"$set": {
            "known_users": list(known_users),
            "waiting_users": list(waiting_users),
            "active_chats": active_chats,
            "user_states": user_states,
            "reports": reports,
            "last_message_time": last_message_time,
            # convert int keys to str for MongoDB compatibility
            "welcome_message_ids": {str(k): v for k, v in welcome_message_ids.items()},
            "maintenance_mode": maintenance_mode
        }}, upsert=True)
        print("✅ Data saved to MongoDB.")
    except Exception as e:
        print(f"❌ Error saving to MongoDB: {e}")

def load_data():
    global known_users, waiting_users, active_chats, user_states, reports, last_message_time, welcome_message_ids, maintenance_mode
    try:
        data = db.config.find_one() or {}
        known_users = set(data.get("known_users", []))
        waiting_users = set(data.get("waiting_users", []))
        active_chats = data.get("active_chats", {})
        user_states = data.get("user_states", {})
        reports = data.get("reports", [])
        last_message_time = data.get("last_message_time", {})
        # convert string keys back to int
        welcome_message_ids = {int(k): v for k, v in data.get("welcome_message_ids", {}).items()}
        maintenance_mode = data.get("maintenance_mode", False)
        print("✅ Bot state loaded from MongoDB.")
    except Exception as e:
        print(f"❌ Error loading from MongoDB: {e}")

load_data()

# === STATE VARIABLES ===
spam_cooldown = 3  # seconds

# === UTILITY FUNCTIONS ===
def get_main_markup():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton('🔎Find Match'))
    markup.add(KeyboardButton('📢 Report'), KeyboardButton('📊 Bot Stats'))
    return markup

def get_chat_markup():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton('Disconnect ❌'), KeyboardButton('📢 Report'))
    return markup

def check_user_in_channel(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def is_admin(user_id):
    return user_id in ADMIN_USER_ID

# === HANDLERS ===
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    known_users.add(user_id)
    save_data()

    if maintenance_mode and not is_admin(user_id):
        bot.send_message(user_id, "🚧 The bot is under maintenance. Please try again later.")
        return

    if not check_user_in_channel(user_id):
        join_markup = InlineKeyboardMarkup()
        join_markup.add(
            InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.strip('@')}"),
            InlineKeyboardButton("✅ I Joined", callback_data='check_join')
        )
        bot.send_message(user_id, "🔐 To use this bot, you must join our channel first.", reply_markup=join_markup)
        return

    send_welcome(user_id)

def send_welcome(user_id):
    caption = "👋 Welcome to the Date Bot!\n\nPlease use the buttons below to proceed."
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("ℹ️ About", callback_data='about'),
        InlineKeyboardButton("📜 Privacy", callback_data='privacy'),
        InlineKeyboardButton("📜 Terms", callback_data='terms')
    )
    msg = bot.send_photo(user_id, WELCOME_IMAGE_URL, caption=caption, reply_markup=markup)
    welcome_message_ids[user_id] = msg.message_id
    bot.send_message(user_id, "👇 Use the buttons below to get started.", reply_markup=get_main_markup())
    save_data()

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    msg_id = call.message.message_id

    if call.data == 'check_join':
        if check_user_in_channel(user_id):
            bot.send_message(user_id, "✅ Verified! You're now allowed to use the bot.")
            send_welcome(user_id)
        else:
            bot.answer_callback_query(call.id, "❌ You haven't joined the channel yet.")

    elif call.data in ['about', 'privacy', 'terms']:
        text = {
            'about': "<b>Developer:</b> <a href='https://t.me/EK4mpreetsingh'>EK4mpreetsingh</a>\nBot Name: Date bot🌹",
            'privacy': "📜 <b>Privacy Policy</b>\nWe do not store your messages.",
            'terms': "📜 <b>Terms of Service</b>\nDon't abuse or harass users."
        }
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data='back'))
        bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=text[call.data], reply_markup=markup, parse_mode='HTML')

    elif call.data == 'back':
    caption = "👋 Welcome to the Date Bot!\n\nPlease use the buttons below to proceed."
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("ℹ️ About", callback_data='about'),
        InlineKeyboardButton("📜 Privacy", callback_data='privacy'),
        InlineKeyboardButton("📜 Terms", callback_data='terms')
    )
    bot.edit_message_media(
        media=InputMediaPhoto(WELCOME_IMAGE_URL, caption=caption, parse_mode='HTML'),
        chat_id=chat_id,
        message_id=msg_id,
        reply_markup=markup
    )

@bot.message_handler(func=lambda msg: msg.text == '🔎Find Match')
def find_match(message):
    user_id = message.from_user.id
    known_users.add(user_id)
    save_data()

    if maintenance_mode and not is_admin(user_id):
        bot.send_message(user_id, "🚧 The bot is under maintenance.")
        return

    if user_id in active_chats:
        bot.send_message(user_id, "⚠️ You're already in a chat.")
        return

    if not check_user_in_channel(user_id):
        bot.send_message(user_id, f"🔐 Please join our channel {CHANNEL_USERNAME}.")
        return

    bot.send_message(user_id, "🔍 Searching for a match...")

    for other_user in list(waiting_users):
        if other_user != user_id:
            waiting_users.remove(other_user)
            active_chats[user_id] = other_user
            active_chats[other_user] = user_id
            bot.send_message(user_id, "✅ Match found!", reply_markup=get_chat_markup())
            bot.send_message(other_user, "✅ Match found!", reply_markup=get_chat_markup())
            save_data()
            return

    waiting_users.add(user_id)
    user_states[user_id] = 'waiting'
    bot.send_message(user_id, "⏳ Waiting for a partner...")
    save_data()

@bot.message_handler(func=lambda msg: msg.text == 'Disconnect ❌')
def handle_disconnect(message):
    user_id = message.from_user.id

    if user_id in active_chats:
        partner_id = active_chats.pop(user_id)
        active_chats.pop(partner_id, None)
        bot.send_message(user_id, "❌ Chat disconnected.", reply_markup=get_main_markup())
        bot.send_message(partner_id, "❌ Chat disconnected.", reply_markup=get_main_markup())
        save_data()
    else:
        bot.send_message(user_id, "⚠️ You're not in a chat.")

@bot.message_handler(func=lambda msg: msg.text == '📢 Report')
def report_user(message):
    user_id = message.from_user.id
    if user_id in active_chats:
        reports.append((user_id, active_chats[user_id]))
        bot.send_message(user_id, "📢 Report submitted.")
        save_data()
    else:
        bot.send_message(user_id, "⚠️ You're not in a chat to report.")

@bot.message_handler(func=lambda msg: msg.text == '📊 Bot Stats')
def bot_stats(message):
    bot.send_message(message.chat.id, f"📊 Stats:\n👥 Total users: {len(known_users)}\n📋 Reports: {len(reports)}")

@bot.message_handler(commands=['admin_panel'])
def handle_admin_panel(message):
    if not is_admin(message.from_user.id): return
    bot.send_message(message.chat.id,
        f"🛠 Admin Panel\nUsers: {len(known_users)}\nReports: {len(reports)}")

@bot.message_handler(commands=['maintenance_on'])
def enable_maintenance(message):
    global maintenance_mode
    if not is_admin(message.from_user.id): return
    maintenance_mode = True
    for uid in known_users:
        if not is_admin(uid):
            try: bot.send_message(uid, "🚧 Bot is under maintenance.")
            except: pass
    bot.send_message(message.chat.id, "✅ Maintenance mode ON.")
    save_data()

@bot.message_handler(commands=['maintenance_off'])
def disable_maintenance(message):
    global maintenance_mode
    if not is_admin(message.from_user.id): return
    maintenance_mode = False
    bot.send_message(message.chat.id, "✅ Maintenance mode OFF.")
    save_data()

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker'])
def forward_message(message):
    user_id = message.from_user.id
    known_users.add(user_id)

    now = time.time()
    if user_id in last_message_time and now - last_message_time[user_id] < spam_cooldown:
        bot.send_message(user_id, "⏱ Wait a few seconds before sending again.")
        return
    last_message_time[user_id] = now

    if maintenance_mode and not is_admin(user_id):
        bot.send_message(user_id, "🚧 The bot is under maintenance.")
        return

    if user_id in active_chats:
        partner_id = active_chats.get(user_id)
        if partner_id:
            try:
                if message.content_type == 'text':
                    bot.send_message(partner_id, message.text)
                elif message.content_type == 'photo':
                    bot.send_photo(partner_id, message.photo[-1].file_id, caption=message.caption)
                elif message.content_type == 'video':
                    bot.send_video(partner_id, message.video.file_id, caption=message.caption)
                elif message.content_type == 'document':
                    bot.send_document(partner_id, message.document.file_id, caption=message.caption)
                elif message.content_type == 'audio':
                    bot.send_audio(partner_id, message.audio.file_id, caption=message.caption)
                elif message.content_type == 'voice':
                    bot.send_voice(partner_id, message.voice.file_id)
                elif message.content_type == 'sticker':
                    bot.send_sticker(partner_id, message.sticker.file_id)
            except:
                bot.send_message(user_id, "❌ Your partner may have left.")
                handle_disconnect(message)
    else:
        bot.send_message(user_id, "❗ Click 'Find Match' to start.", reply_markup=get_main_markup())

# === ADMIN PANEL WEB ===
@app.route("/", methods=["GET", "POST"])
def web_panel():
    if request.method == "POST":
        msg = request.form.get("message", "")
        sent, failed = 0, 0
        for uid in known_users:
            try:
                bot.send_message(uid, f"📢 {msg}")
                sent += 1
            except:
                failed += 1
        return f"<h3>Sent: {sent} | Failed: {failed}</h3><a href='/'>Back</a>"
    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>📊 Bot Admin Panel</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #f2f2f2;
      margin: 0;
      padding: 0;
    }
    .container {
      width: 500px;
      margin: 50px auto;
      background: #fff;
      border-radius: 10px;
      box-shadow: 0 0 15px rgba(0,0,0,0.1);
      padding: 30px;
    }
    h1 {
      text-align: center;
      color: #333;
    }
    .stats {
      font-size: 18px;
      margin: 20px 0;
    }
    .stats span {
      font-weight: bold;
    }
    textarea {
      width: 100%;
      height: 100px;
      padding: 10px;
      border-radius: 5px;
      border: 1px solid #ccc;
      resize: none;
      font-size: 16px;
    }
    button {
      width: 100%;
      padding: 12px;
      background: #4CAF50;
      color: white;
      border: none;
      border-radius: 5px;
      font-size: 16px;
      margin-top: 10px;
      cursor: pointer;
    }
    button:hover {
      background: #45a049;
    }
    .footer {
      margin-top: 20px;
      text-align: center;
      font-size: 12px;
      color: #888;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>📊 Bot Admin Panel</h1>
    <div class="stats">
      👥 Total users: <span>{{total_users}}</span><br>
      🚨 Total reports: <span>{{total_reports}}</span>
    </div>
    <form method="post">
      <textarea name="message" placeholder="Enter broadcast message..." required></textarea>
      <button type="submit">📢 Broadcast to All</button>
    </form>
    <div class="footer">
      Developed by <a href="https://t.me/EK4mpreetsingh" target="_blank">@EK4mpreetsingh</a>
    </div>
  </div>
</body>
</html>
""", total_users=len(known_users), total_reports=len(reports))

# === START BOT ===
print("Bot started!")

def run_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=8080)
