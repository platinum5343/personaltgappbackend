from http.server import BaseHTTPRequestHandler
import os
import json
import asyncio
import requests
import datetime
from telebot.async_telebot import AsyncTeleBot
import firebase_admin
from firebase_admin import credentials, firestore, storage
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# Initialize the bot token
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = AsyncTeleBot(BOT_TOKEN)

# Initialize Firebase
firebase_config = json.loads(os.getenv('FIREBASE_SERVICE_ACCOUNT'))
cred = credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred, {
    'storageBucket': os.getenv('tgapp-8404d.appspot.com')  # Fixed typo here
})
db = firestore.client()
bucket = storage.bucket()

def generate_start_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("open_web_app", web_app=WebAppInfo(url="https://personaltgapp.vercel.app/"))
    )
    return keyboard

@bot.message_handler(commands=['start'])
async def start(message):
    user_id = str(message.from_user.id)
    user_first_name = str(message.from_user.first_name)
    user_last_name = message.from_user.last_name
    user_username = message.from_user.username
    user_language_code = str(message.from_user.language_code)
    is_premium = message.from_user.is_premium
    text = message.text.split()
    welcome_message = (
        f"Hello {user_first_name}!\n\n"
        f"Welcome to W3p\n\n"
        f"Here is your personal web app\n\n"
    )
    try:
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()
        if not user_doc.exists:
            photos = await bot.get_user_profile_photos(user_id, limit=1)
            if photos.total_count > 0:
                file_id = photos.photos[0][-1].file_id
                file_info = await bot.get_file(file_id)
                file_path = file_info.file_path
                file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                # Download the photo
                response = requests.get(file_url)
                if response.status_code == 200:
                    # Upload image to Firebase Storage
                    blob = bucket.blob(f"user_images/{user_id}.jpg")
                    blob.upload_from_string(response.content, content_type='image/jpeg')
                    # Generate the correct URL
                    user_image = blob.generate_signed_url(datetime.timedelta(days=365), method="GET")
                else:
                    user_image = None
            else:
                user_image = None
            user_data = {
                'first_name': user_first_name,
                'last_name': user_last_name,
                'username': user_username,
                'language_code': user_language_code,
                'is_premium': is_premium,
                'user_image': user_image,
                'referrals': {},
                'balance': 0,
                'mineRate': 0.001,
                'isMining': False,
                'miningStartedTime': None,
                'daily': {
                    'claimTime': None,
                    'claimedDay': 0,
                },
                'links': None,
            }
            if len(text) > 1 and text[1].startswith('ref='):
                referrer_id = text[1][4:]
                referrer_ref = db.collection('users').document(referrer_id)
                referrer_doc = referrer_ref.get()
                if referrer_doc.exists:
                    user_data['referredBy'] = referrer_id
                    referrer_data = referrer_doc.to_dict()
                    bonus_amount = 500 if is_premium else 100
                    current_balance = referrer_data.get('balance', 0)
                    new_balance = current_balance + bonus_amount
                    referrals = referrer_data.get('referrals', {})
                    if referrals is None:
                        referrals = {}
                    referrals[user_id] = {
                        'addedValue': bonus_amount,
                        'firstName': user_first_name,
                        'lastName': user_last_name,
                        'userImage': user_image,
                    }
                    referrer_ref.update({
                        'balance': new_balance,
                        'referrals': referrals
                    })
                else:
                    user_data['referredBy'] = None
            else:
                user_data['referredBy'] = None
            user_ref.set(user_data)
        keyboard = generate_start_keyboard()
        await bot.reply_to(message, welcome_message, reply_markup=keyboard)
    except Exception as e:
        error_message = (
            "An error occurred while processing your request. "
            "Please try again later or contact support."
        )
        await bot.reply_to(message, error_message)
        print(f"Error: {str(e)}")