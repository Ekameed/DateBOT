import time
import telebot
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto
)

API_TOKEN = '8014049142:AAFryAYqEx6sKsPBq9Rw3BUl9do5UtNUH9E'
CHANNEL_USERNAME = '@gsjdndnejdn'
ADMIN_USER_ID = [7592464127, 5022283560]
WELCOME_IMAGE_URL = 'https://i.ibb.co/CK5D69LC/MMJABGQTIHLELKL.jpg'

bot = telebot.TeleBot(API_TOKEN)

waiting_users = set()
active_chats = {}
user_states = {}
known_users = set()
maintenance_mode = False  # Default: OFF
reports = []
last_message_time = {}
spam_cooldown = 3  # seconds
welcome_message_ids = {}

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

@bot.message_handler(commands=['admin_panel'])
def handle_admin_panel(message):
    user_id = message.from_user.id
    if not is_admin(user_id): return

    admin_text = (
        "🛠️ *Admin Panel*\n"
        "Reply to any message with /broadcast to send it to all users.\n"
        "/maintenance_on - Enable maintenance mode\n"
        "/maintenance_off - Disable maintenance mode\n"
        f"👥 Total known users: {len(known_users)}\n"
        f"📌 Total reports: {len(reports)}"
    )
    bot.send_message(user_id, admin_text, parse_mode='Markdown')

@bot.message_handler(commands=['maintenance_on'])
def maintenance_on(message):
    global maintenance_mode
    user_id = message.from_user.id
    if not is_admin(user_id): return

    maintenance_mode = True
    for uid in known_users:
        if not is_admin(uid):
            try:
                bot.send_message(uid, "🚧 Bot is now under maintenance. Please try again later.")
            except:
                continue
    bot.send_message(user_id, "✅ Maintenance mode enabled.")

@bot.message_handler(commands=['maintenance_off'])
def maintenance_off(message):
    global maintenance_mode
    user_id = message.from_user.id
    if not is_admin(user_id): return

    maintenance_mode = False
    bot.send_message(user_id, "✅ Maintenance mode disabled.")

@bot.message_handler(commands=['broadcast'])
def handle_broadcast(message):
    user_id = message.from_user.id
    if not is_admin(user_id): return

    if not message.reply_to_message:
        bot.send_message(user_id, "❗ To broadcast, reply to the message with /broadcast")
        return

    sent_count = 0
    failed_count = 0

    for uid in list(known_users):
        try:
            bot.copy_message(uid, user_id, message.reply_to_message.message_id)
            sent_count += 1
        except:
            failed_count += 1

    bot.send_message(user_id, f"📢 Broadcast sent to {sent_count} users. Failed: {failed_count}")

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    known_users.add(user_id)

    if maintenance_mode and not is_admin(user_id):
        bot.send_message(user_id, "🚧 The bot is under maintenance. Please try again later.")
        return

    if not check_user_in_channel(user_id):
        join_markup = InlineKeyboardMarkup()
        join_markup.add(
            InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.strip('@')}"),
            InlineKeyboardButton("✅ I Joined", callback_data='check_join')
        )
        bot.send_message(
            user_id,
            "🔐 To use this bot, you must join our channel first.",
            reply_markup=join_markup
        )
        return

    send_welcome(user_id)

def send_welcome(user_id):
    welcome_caption = "👋 Welcome to the Date Bot!\n\nPlease use the buttons below to proceed."
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("ℹ️ About", callback_data='about'),
        InlineKeyboardButton("📜 Privacy", callback_data='privacy'),
        InlineKeyboardButton("📜 Terms", callback_data='terms')
    )
    msg = bot.send_photo(user_id, WELCOME_IMAGE_URL, caption=welcome_caption, reply_markup=markup)
    welcome_message_ids[user_id] = msg.message_id
    bot.send_message(user_id, "👇 Use the buttons below to get started.", reply_markup=get_main_markup())

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    if call.data == 'check_join':
        if check_user_in_channel(user_id):
            bot.send_message(user_id, "✅ Verified! You're now allowed to use the bot.")
            send_welcome(user_id)
        else:
            bot.answer_callback_query(call.id, "❌ You haven't joined the channel yet.")

    elif call.data in ['about', 'privacy', 'terms']:
        text_map = {
            'about': "<b>Developer:</b> <a href='https://t.me/EK4mpreetsingh'>EK4mpreetsingh</a>\nBot Name: Date bot🌹\nServer: Personal",
            'privacy': "📜 <b>Privacy Policy</b>\n\nWe do not store your messages. All chats are anonymous and temporary.",
            'terms': "📜 <b>Terms of Service</b>\n\nBy using this bot, you agree not to abuse or harass other users."
        }
        back_markup = InlineKeyboardMarkup()
        back_markup.add(InlineKeyboardButton("🔙 Back", callback_data='back'))
        bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=text_map[call.data],
            reply_markup=back_markup,
            parse_mode='HTML'
        )

    elif call.data == 'back':
        welcome_caption = "👋 Welcome to the Date Bot!\n\nPlease use the buttons below to proceed."
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("ℹ️ About", callback_data='about'),
            InlineKeyboardButton("📜 Privacy", callback_data='privacy'),
            InlineKeyboardButton("📜 Terms", callback_data='terms')
        )
        original_msg_id = welcome_message_ids.get(user_id)
        bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=welcome_caption,
            reply_markup=markup
        )

@bot.message_handler(func=lambda msg: msg.text == '🔎Find Match')
def find_match(message):
    user_id = message.from_user.id
    known_users.add(user_id)

    if maintenance_mode and not is_admin(user_id):
        bot.send_message(user_id, "🚧 The bot is under maintenance. Please try again later.")
        return

    if user_id in active_chats:
        bot.send_message(user_id, "⚠️ You are already in a chat.")
        return

    if not check_user_in_channel(user_id):
        bot.send_message(user_id, f"🔐 Please join our channel {CHANNEL_USERNAME} to use this feature.")
        return

    bot.send_message(user_id, "🔍 Searching for a match...")

    for other_user in list(waiting_users):
        if other_user != user_id:
            waiting_users.remove(other_user)
            active_chats[user_id] = other_user
            active_chats[other_user] = user_id
            bot.send_message(user_id, "✅ Match found! Say hi!", reply_markup=get_chat_markup())
            bot.send_message(other_user, "✅ Match found! Say hi!", reply_markup=get_chat_markup())
            return

    waiting_users.add(user_id)
    user_states[user_id] = 'waiting'
    bot.send_message(user_id, "⏳ Waiting for someone to match with you...")

@bot.message_handler(func=lambda msg: msg.text == 'Disconnect ❌')
def handle_disconnect(message):
    user_id = message.from_user.id
    known_users.add(user_id)

    if maintenance_mode and not is_admin(user_id):
        bot.send_message(user_id, "🚧 The bot is under maintenance. Please try again later.")
        return

    if user_id in active_chats:
        partner_id = active_chats.pop(user_id)
        active_chats.pop(partner_id, None)
        bot.send_message(user_id, "❌ Chat disconnected.", reply_markup=get_main_markup())
        bot.send_message(partner_id, "❌ Chat disconnected.", reply_markup=get_main_markup())
    else:
        bot.send_message(user_id, "⚠️ You are not in a chat currently.", reply_markup=get_main_markup())

@bot.message_handler(func=lambda msg: msg.text == '📢 Report')
def report_user(message):
    user_id = message.from_user.id
    if user_id in active_chats:
        partner_id = active_chats[user_id]
        reports.append((user_id, partner_id))
        bot.send_message(user_id, "📢 Report submitted. Thank you! We will review it.")
    else:
        bot.send_message(user_id, "⚠️ You are not in a chat to report anyone.")

@bot.message_handler(func=lambda msg: msg.text == '📊 Bot Stats')
def bot_stats(message):
    bot.send_message(message.chat.id, f"📊 Stats:\n👥 Total users: {len(known_users)}\n📋 Reports: {len(reports)}")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker'])
def handle_messages(message):
    user_id = message.from_user.id
    known_users.add(user_id)

    now = time.time()
    if user_id in last_message_time and now - last_message_time[user_id] < spam_cooldown:
        bot.send_message(user_id, "⏱ Please wait a few seconds before sending another message.")
        return
    last_message_time[user_id] = now

    if maintenance_mode and not is_admin(user_id):
        bot.send_message(user_id, "🚧 The bot is under maintenance. Please try again later.")
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
                bot.send_message(user_id, "❌ Failed to send message. Your partner may have left.")
                handle_disconnect(message)
    else:
        bot.send_message(user_id, "❗ Click 'Find Match' to start chatting.", reply_markup=get_main_markup())

print("Bot started!")
bot.polling()
