import os
import sys
import logging
import requests
import tempfile
import signal
import json
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from config import (
    TELEGRAM_TOKEN, FISH_API_KEY, BOT_NAME, DEV_NAME, DEV_ALIAS,
    MAX_CHARS, PORT, VOICES_FILE, MAX_VOICES, DEFAULT_VOICES, EMOTIONS, LANGUAGES
)

flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "Bot is running!", 200

@flask_app.route('/health')
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}, 200

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def load_voices_from_json():
    try:
        if os.path.exists(VOICES_FILE):
            with open(VOICES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                voices_data = data.get('voices', [])
                voice_artists = {}
                for i, voice in enumerate(voices_data[:MAX_VOICES]):
                    voice_id = voice.get('id', '')
                    title = voice.get('title', f'Voice {i+1}')
                    language = voice.get('language', 'Unknown')
                    gender = voice.get('gender', 'Unknown')
                    description = voice.get('description', f'{gender} voice in {language}')
                    emoji = "🎙️"
                    if gender.lower() in ['male', 'm']:
                        emoji = "👨"
                    elif gender.lower() in ['female', 'f']:
                        emoji = "👩"
                    key = f"voice_{i+1}"
                    voice_artists[key] = {
                        "name": title[:30],
                        "reference_id": voice_id,
                        "emoji": emoji,
                        "description": f"{gender} · {language} · {description[:50]}",
                        "full_data": voice
                    }
                logger.info(f"Loaded {len(voice_artists)} voices from {VOICES_FILE}")
                return voice_artists
        else:
            logger.warning(f"{VOICES_FILE} not found. Using default voices.")
            return DEFAULT_VOICES
    except Exception as e:
        logger.error(f"Error loading voices: {e}")
        return DEFAULT_VOICES

VOICE_ARTISTS = load_voices_from_json()

def generate_voice(text, reference_id):
    try:
        response = requests.post(
            "https://api.fish.audio/v1/tts",
            headers={
                "Authorization": f"Bearer {FISH_API_KEY}",
                "Content-Type": "application/json",
                "model": "s2.1-pro-free",
            },
            json={
                "text": text,
                "reference_id": reference_id,
                "format": "mp3",
            },
            timeout=60
        )
        if response.status_code == 200:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            temp_file.write(response.content)
            temp_file.close()
            return temp_file.name
        else:
            logger.error(f"API Error: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error: {e}")
        return None

class VoiceBot:
    def __init__(self):
        self.user_voices = {}
        self.user_languages = {}
        self.start_time = datetime.now()
        self.voice_pages = {}
        self.lang_pages = {}

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_text = f"""
🎙️ *Welcome to {BOT_NAME}*

🌍 Supports 83 languages!
🎤 {len(VOICE_ARTISTS)} premium voice artists
😊 10 emotion tags

*How to use:*
1. Set your language with /language
2. Choose your voice with /voice
3. Send text with emotion tags!

*Emotion Tags:*
[happy] 😊 [sad] 😢 [angry] 😠 [excited] 🤩
[calm] 😌 [laughing] 😂 [whispering] 🤫
[serious] 😐 [friendly] 🤗 [neutral] 😐

*Commands:*
/language - Set your language
/voice - Change voice artist
/emotions - Show emotion tags
/sample - Hear a demo
/voices - List all available voices

---
✨ *Developer:* {DEV_NAME}
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')

    async def voices_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        voices_text = f"🎤 *Available Voices ({len(VOICE_ARTISTS)} total)*\n\n"
        for key, voice in list(VOICE_ARTISTS.items())[:20]:
            voices_text += f"{voice['emoji']} *{voice['name']}*\n"
            voices_text += f"   {voice['description']}\n\n"
        if len(VOICE_ARTISTS) > 20:
            voices_text += f"... and {len(VOICE_ARTISTS) - 20} more voices\n"
        voices_text += f"\nUse /voice to change your voice."
        await update.message.reply_text(voices_text, parse_mode='Markdown')

    async def show_voice_page(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, page: int):
        voice_keys = list(VOICE_ARTISTS.keys())
        current_voice = self.user_voices.get(user_id, voice_keys[0] if voice_keys else "studio_pro")
        items_per_page = 10
        total_pages = (len(voice_keys) + items_per_page - 1) // items_per_page
        
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        self.voice_pages[user_id] = page
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, len(voice_keys))
        
        keyboard = []
        for key in voice_keys[start_idx:end_idx]:
            voice = VOICE_ARTISTS[key]
            is_current = " ✅" if key == current_voice else ""
            keyboard.append([InlineKeyboardButton(
                f"{voice['emoji']} {voice['name']}{is_current}",
                callback_data=f"voice_{key}"
            )])
        
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ Previous", callback_data="voice_page_prev"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("Next ▶️", callback_data="voice_page_next"))
        if nav_row:
            keyboard.append(nav_row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        current = VOICE_ARTISTS.get(current_voice, list(VOICE_ARTISTS.values())[0] if VOICE_ARTISTS else {"name": "Unknown", "description": ""})
        
        text = f"🎤 *Select Voice Artist*\n\nCurrent: {current['name']}\n{current['description']}\nPage {page + 1}/{total_pages}"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

    async def show_language_page(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, page: int):
        current_lang = self.user_languages.get(user_id, "en")
        lang_codes = sorted(LANGUAGES.keys())
        items_per_page = 20
        total_pages = (len(lang_codes) + items_per_page - 1) // items_per_page
        
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        self.lang_pages[user_id] = page
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, len(lang_codes))
        
        keyboard = []
        for code in lang_codes[start_idx:end_idx]:
            if code in LANGUAGES:
                is_current = " ✅" if code == current_lang else ""
                keyboard.append([InlineKeyboardButton(
                    f"{LANGUAGES[code]}{is_current}",
                    callback_data=f"lang_{code}"
                )])
        
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ Previous", callback_data="lang_page_prev"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("Next ▶️", callback_data="lang_page_next"))
        if nav_row:
            keyboard.append(nav_row)
        
        keyboard.append([InlineKeyboardButton("📚 View All Languages", callback_data="view_all_langs")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        current_display = LANGUAGES.get(current_lang, "English")
        
        text = f"🌍 *Select Your Language*\n\nCurrent: {current_display}\nPage {page + 1}/{total_pages}"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

    async def language_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        page = self.lang_pages.get(user_id, 0)
        await self.show_language_page(update, context, user_id, page)

    async def voice_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        page = self.voice_pages.get(user_id, 0)
        await self.show_voice_page(update, context, user_id, page)

    async def emotions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        emotions_text = """
😊 *Emotion Tags Guide*

Add these tags to your text:

• `[happy]` - Cheerful, joyful tone
• `[sad]` - Melancholic, emotional tone
• `[angry]` - Intense, firm tone
• `[excited]` - Energetic, enthusiastic
• `[calm]` - Relaxed, soothing tone
• `[laughing]` - Laughing while speaking
• `[whispering]` - Soft, whispered voice
• `[serious]` - Professional, serious tone
• `[friendly]` - Warm, inviting tone
• `[neutral]` - Balanced, natural tone

*Example:*
`[happy] Hello! This is a happy message.`

---
✨ *Developer:* {DEV_NAME}
        """
        await update.message.reply_text(emotions_text, parse_mode='Markdown')

    async def sample_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        voice_keys = list(VOICE_ARTISTS.keys())
        voice_key = self.user_voices.get(user_id, voice_keys[0] if voice_keys else "studio_pro")
        voice = VOICE_ARTISTS.get(voice_key, list(VOICE_ARTISTS.values())[0] if VOICE_ARTISTS else {"name": "Studio Pro", "reference_id": "95496a7632a14321891943545846c31c"})
        lang = self.user_languages.get(user_id, "en")
        lang_name = LANGUAGES.get(lang, "English")
        await update.message.reply_text(f"🎵 Generating sample in {lang_name} with {voice['emoji']} {voice['name']}...")
        sample_texts = {
            "en": f"[excited] [laughing] Hello! Welcome to {BOT_NAME}! This is the {voice['name']} voice with emotions! [laughing] Thanks to J for creating this amazing bot!",
            "zh": f"[excited] [laughing] 你好！欢迎来到 {BOT_NAME}！这是{voice['name']}的声音，带有情感！[laughing] 感谢J创建了这个令人惊叹的机器人！",
            "ja": f"[excited] [laughing] こんにちは！{BOT_NAME}へようこそ！これは{voice['name']}の感情的な声です！[laughing] Jがこの素晴らしいボットを作成してくれてありがとう！",
            "es": f"[excited] [laughing] ¡Hola! ¡Bienvenido a {BOT_NAME}! ¡Esta es la voz de {voice['name']} con emociones! [laughing] ¡Gracias a J por crear este increíble bot!",
        }
        sample_text = sample_texts.get(lang, sample_texts["en"])
        audio_file = generate_voice(sample_text, voice['reference_id'])
        if audio_file and os.path.exists(audio_file):
            with open(audio_file, 'rb') as audio:
                await update.message.reply_voice(
                    voice=audio,
                    caption=f"🎧 *Sample in {lang_name}*\n{voice['emoji']} {voice['name']}\n😊 [excited] [laughing]\n✨ {DEV_NAME}",
                    parse_mode='Markdown'
                )
            os.unlink(audio_file)
        else:
            await update.message.reply_text("❌ Failed. Please try again.")

    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uptime = datetime.now() - self.start_time
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds % 3600) // 60
        about_text = f"""
ℹ️ *About {BOT_NAME}*

*Version:* 3.0
*Developer:* {DEV_NAME}
*Languages:* 83 supported
*Emotions:* 10 emotion tags
*Voice Artists:* {len(VOICE_ARTISTS)} premium voices
*Max Characters:* {MAX_CHARS}
*Uptime:* {hours}h {minutes}m

*Features:*
• 83 languages with auto-detection
• {len(VOICE_ARTISTS)} premium voice artists
• 10 emotion expressions
• Studio quality audio

Made with ❤️ by {DEV_NAME}
        """
        await update.message.reply_text(about_text, parse_mode='Markdown')

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        text = update.message.text
        if len(text) > MAX_CHARS:
            await update.message.reply_text(f"⚠️ Text exceeds {MAX_CHARS} characters.")
            return
        voice_keys = list(VOICE_ARTISTS.keys())
        voice_key = self.user_voices.get(user_id, voice_keys[0] if voice_keys else "studio_pro")
        voice = VOICE_ARTISTS.get(voice_key, list(VOICE_ARTISTS.values())[0] if VOICE_ARTISTS else {"name": "Studio Pro", "reference_id": "95496a7632a14321891943545846c31c"})
        lang = self.user_languages.get(user_id, "en")
        lang_name = LANGUAGES.get(lang, "English")
        detected_emotions = []
        for emotion_name, emotion_tag in EMOTIONS.items():
            if emotion_tag in text.lower():
                detected_emotions.append(emotion_name)
        emotion_indicator = f"😊 {', '.join(detected_emotions)}" if detected_emotions else "😐 Neutral"
        processing = await update.message.reply_text(
            f"🎵 Converting to voice ({voice['emoji']} {voice['name']})\n🌍 Language: {lang_name}\n{emotion_indicator}"
        )
        audio_file = generate_voice(text, voice['reference_id'])
        if audio_file and os.path.exists(audio_file):
            with open(audio_file, 'rb') as audio:
                caption = f"🎧 *{voice['emoji']} {voice['name']}*\n🌍 {lang_name} · 📝 {len(text)} chars"
                if detected_emotions:
                    caption += f"\n😊 Emotion: {', '.join(detected_emotions)}"
                caption += f"\n✨ {DEV_NAME}"
                await update.message.reply_voice(
                    voice=audio,
                    caption=caption,
                    parse_mode='Markdown'
                )
            os.unlink(audio_file)
            await processing.delete()
        else:
            await processing.edit_text("❌ Failed to generate voice. Please try again.")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = str(update.effective_user.id)
        data = query.data

        # Handle voice selection - FIXED
        if data.startswith("voice_") and not data.startswith("voice_page_"):
            voice_key = data.replace("voice_", "")
            
            # Check if the key exists directly
            if voice_key in VOICE_ARTISTS:
                self.user_voices[user_id] = voice_key
                voice = VOICE_ARTISTS[voice_key]
                await query.edit_message_text(
                    f"✅ Voice changed to: {voice['emoji']} *{voice['name']}*\n{voice['description']}\n\nSend any text to hear this voice!",
                    parse_mode='Markdown'
                )
            else:
                # If not found directly, try to find a matching key
                found = False
                for key, v in VOICE_ARTISTS.items():
                    if voice_key in key or key in voice_key:
                        self.user_voices[user_id] = key
                        await query.edit_message_text(
                            f"✅ Voice changed to: {v['emoji']} *{v['name']}*\n{v['description']}\n\nSend any text to hear this voice!",
                            parse_mode='Markdown'
                        )
                        found = True
                        break
                
                if not found:
                    await query.edit_message_text(
                        "❌ Voice not found. Please try again.",
                        parse_mode='Markdown'
                    )

        # Handle voice page navigation
        elif data == "voice_page_next":
            current_page = self.voice_pages.get(user_id, 0)
            new_page = current_page + 1
            await self.show_voice_page(update, context, user_id, new_page)

        elif data == "voice_page_prev":
            current_page = self.voice_pages.get(user_id, 0)
            new_page = max(0, current_page - 1)
            await self.show_voice_page(update, context, user_id, new_page)

        # Handle language selection
        elif data.startswith("lang_") and not data.startswith("lang_page_"):
            lang_code = data.replace("lang_", "")
            if lang_code in LANGUAGES:
                self.user_languages[user_id] = lang_code
                lang_name = LANGUAGES[lang_code]
                await query.edit_message_text(
                    f"✅ Language set to: {lang_name}\n\nYour text will now be processed in {lang_name}.\nSend a message or try /sample to hear it!",
                    parse_mode='Markdown'
                )

        # Handle language page navigation
        elif data == "lang_page_next":
            current_page = self.lang_pages.get(user_id, 0)
            new_page = current_page + 1
            await self.show_language_page(update, context, user_id, new_page)

        elif data == "lang_page_prev":
            current_page = self.lang_pages.get(user_id, 0)
            new_page = max(0, current_page - 1)
            await self.show_language_page(update, context, user_id, new_page)

        elif data == "view_all_langs":
            all_langs = "🌍 *All 83 Languages*\n\n"
            for code, name in sorted(LANGUAGES.items()):
                all_langs += f"{name}\n"
            all_langs += "\nUse /language to select your preferred language."
            await query.edit_message_text(all_langs, parse_mode='Markdown')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            f"📋 *Commands*\n\n"
            f"/start - Welcome message\n"
            f"/help - This guide\n"
            f"/language - Set your language (83 options)\n"
            f"/voice - Change voice artist ({len(VOICE_ARTISTS)} options)\n"
            f"/voices - List all available voices\n"
            f"/emotions - Show emotion tags\n"
            f"/sample - Hear a demo in your language\n"
            f"/about - Bot info\n\n"
            f"*How to use:*\n"
            f"1. Set your language with /language\n"
            f"2. Choose your voice with /voice\n"
            f"3. Send text with emotion tags!\n\n"
            f"*Emotion Tags:*\n"
            f"[happy] 😊 [sad] 😢 [angry] 😠 [excited] 🤩\n"
            f"[calm] 😌 [laughing] 😂 [whispering] 🤫\n"
            f"[serious] 😐 [friendly] 🤗 [neutral] 😐\n\n"
            f"✨ *Developer:* {DEV_NAME}",
            parse_mode='Markdown'
        )

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Error: {context.error}")
        if update and update.effective_message:
            await update.message.reply_text("⚠️ Service unavailable. Please try again.")

def run_bot():
    bot = VoiceBot()
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", bot.start_command))
    app.add_handler(CommandHandler("help", bot.help_command))
    app.add_handler(CommandHandler("language", bot.language_command))
    app.add_handler(CommandHandler("voice", bot.voice_command))
    app.add_handler(CommandHandler("voices", bot.voices_command))
    app.add_handler(CommandHandler("emotions", bot.emotions_command))
    app.add_handler(CommandHandler("sample", bot.sample_command))
    app.add_handler(CommandHandler("about", bot.about_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))
    app.add_handler(CallbackQueryHandler(bot.button_callback))
    app.add_error_handler(bot.error_handler)

    webhook_url = os.environ.get("WEBHOOK_URL")

    logger.info(f"🎙️ {BOT_NAME} by {DEV_NAME} is running...")
    logger.info(f"🌍 {len(LANGUAGES)} languages supported")
    logger.info(f"🎤 {len(VOICE_ARTISTS)} voice artists available")
    logger.info(f"😊 {len(EMOTIONS)} emotion tags")

    if webhook_url:
        logger.info(f"🌐 Starting webhook on port {PORT}")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=webhook_url,
            drop_pending_updates=True
        )
    else:
        logger.info("📡 Starting in polling mode...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    from werkzeug.serving import run_simple

    def signal_handler(sig, frame):
        logger.info("🛑 Shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    import threading
    flask_thread = threading.Thread(target=lambda: run_simple(
        "0.0.0.0", PORT, flask_app, use_reloader=False, use_debugger=False
    ))
    flask_thread.daemon = True
    flask_thread.start()

    logger.info(f"🌐 Health check available at http://0.0.0.0:{PORT}/")
    logger.info(f"🌐 Health check available at http://0.0.0.0:{PORT}/health")

    run_bot()

if __name__ == "__main__":
    main()
