import os
import sys
import time
import logging
import requests
import tempfile
import signal
import threading
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ========== CONFIGURATION ==========
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8107617495:AAEjCpxJ0qVmG1m7C5rzAU_maM2t9IlnUJs")
FISH_API_KEY = os.environ.get("FISH_API_KEY", "sk-fish-2IfHrnq1IG3lhnGoCFVbiNwRrdoR_yM4OXZEb7KfO_g")

# ========== BOT SETTINGS ==========
BOT_NAME = "VoiceStudio Pro"
DEV_NAME = "J 🧃"
DEV_ALIAS = "Jews"
MAX_CHARS = 5000
PORT = int(os.environ.get("PORT", 8080))

# ========== STEALTH DEPLOYMENT SETTINGS ==========
DEPLOYMENT_TIMEOUT = 30  # Seconds to wait for deployment to complete
IS_RENDER = os.environ.get("RENDER", False)
IS_DEPLOYING = True  # Flag to prevent premature webhook startup

# ========== VOICE ARTISTS ==========
VOICE_ARTISTS = {
    "studio_pro": {
        "name": "Studio Pro",
        "reference_id": "95496a7632a14321891943545846c31c",
        "emoji": "🎙️",
        "description": "Professional studio quality voice"
    },
    "dave": {
        "name": "Dave",
        "reference_id": "08bc8442f20945b4a7bce5bde11f2505",
        "emoji": "👨",
        "description": "Clear, serious, informative male voice"
    },
    "deep_dave": {
        "name": "Deep Dave",
        "reference_id": "5d992f2f63074d31a99413fdb157a565",
        "emoji": "🧘",
        "description": "Deep, meditative, calm male voice"
    },
    "calm": {
        "name": "Calm Voice",
        "reference_id": "b347db033a6549378b48d00acb0d06cd",
        "emoji": "🌊",
        "description": "Soft, gentle, soothing voice"
    }
}

# ========== 83 SUPPORTED LANGUAGES ==========
LANGUAGES = {
    "af": "🇿🇦 Afrikaans", "am": "🇪🇹 Amharic", "ar": "🇸🇦 Arabic",
    "as": "🇮🇳 Assamese", "az": "🇦🇿 Azerbaijani", "be": "🇧🇾 Belarusian",
    "bg": "🇧🇬 Bulgarian", "bn": "🇧🇩 Bengali", "bodo": "🇮🇳 Bodo",
    "bs": "🇧🇦 Bosnian", "ca": "🇪🇸 Catalan", "cs": "🇨🇿 Czech",
    "cy": "🇬🇧 Welsh", "da": "🇩🇰 Danish", "de": "🇩🇪 German",
    "doi": "🇮🇳 Dogri", "el": "🇬🇷 Greek", "en": "🇬🇧 English",
    "es": "🇪🇸 Spanish", "et": "🇪🇪 Estonian", "eu": "🇪🇸 Basque",
    "fa": "🇮🇷 Persian", "fi": "🇫🇮 Finnish", "fil": "🇵🇭 Filipino",
    "fr": "🇫🇷 French", "ga": "🇮🇪 Irish", "gl": "🇪🇸 Galician",
    "gu": "🇮🇳 Gujarati", "he": "🇮🇱 Hebrew", "hi": "🇮🇳 Hindi",
    "hr": "🇭🇷 Croatian", "hu": "🇭🇺 Hungarian", "hy": "🇦🇲 Armenian",
    "id": "🇮🇩 Indonesian", "is": "🇮🇸 Icelandic", "it": "🇮🇹 Italian",
    "ja": "🇯🇵 Japanese", "ka": "🇬🇪 Georgian", "kk": "🇰🇿 Kazakh",
    "km": "🇰🇭 Khmer", "kn": "🇮🇳 Kannada", "ko": "🇰🇷 Korean",
    "kok": "🇮🇳 Konkani", "ks": "🇮🇳 Kashmiri", "lo": "🇱🇦 Lao",
    "lt": "🇱🇹 Lithuanian", "lv": "🇱🇻 Latvian", "mai": "🇮🇳 Maithili",
    "mk": "🇲🇰 Macedonian", "ml": "🇮🇳 Malayalam", "mn": "🇲🇳 Mongolian",
    "mni": "🇮🇳 Manipuri", "mr": "🇮🇳 Marathi", "ms": "🇲🇾 Malay",
    "my": "🇲🇲 Burmese", "nb": "🇳🇴 Norwegian", "ne": "🇳🇵 Nepali",
    "nl": "🇳🇱 Dutch", "or": "🇮🇳 Odia", "pa": "🇮🇳 Punjabi",
    "pl": "🇵🇱 Polish", "ps": "🇦🇫 Pashto", "pt": "🇵🇹 Portuguese",
    "ro": "🇷🇴 Romanian", "ru": "🇷🇺 Russian", "sat": "🇮🇳 Santali",
    "sd": "🇵🇰 Sindhi", "si": "🇱🇰 Sinhala", "sk": "🇸🇰 Slovak",
    "sl": "🇸🇮 Slovenian", "sq": "🇦🇱 Albanian", "sr": "🇷🇸 Serbian",
    "sv": "🇸🇪 Swedish", "sw": "🇹🇿 Swahili", "ta": "🇮🇳 Tamil",
    "te": "🇮🇳 Telugu", "tg": "🇹🇯 Tajik", "th": "🇹🇭 Thai",
    "tk": "🇹🇲 Turkmen", "tr": "🇹🇷 Turkish", "uk": "🇺🇦 Ukrainian",
    "ur": "🇵🇰 Urdu", "uz": "🇺🇿 Uzbek", "vi": "🇻🇳 Vietnamese",
    "xh": "🇿🇦 Xhosa", "zh": "🇨🇳 Chinese", "zu": "🇿🇦 Zulu"
}

# ========== SETUP ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== STEALTH DEPLOYMENT HANDLER ==========
def stealth_deployment():
    """Handle Render deployment without getting stuck"""
    global IS_DEPLOYING
    
    logger.info("🔒 Stealth deployment mode activated")
    logger.info(f"📦 Render environment: {IS_RENDER}")
    logger.info(f"⏱️ Deployment timeout: {DEPLOYMENT_TIMEOUT}s")
    
    # Wait for deployment to settle
    if IS_RENDER:
        logger.info("⏳ Waiting for deployment to complete...")
        time.sleep(3)  # Brief pause for Render to finish setup
        
        # Check if we're in a healthy state
        health_check = os.environ.get("HEALTH_CHECK", "true")
        if health_check.lower() == "true":
            logger.info("✅ Health check passed")
            IS_DEPLOYING = False
            return True
    
    IS_DEPLOYING = False
    return True

# ========== VOICE SERVICE ==========
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

# ========== BOT HANDLERS ==========
class VoiceBot:
    def __init__(self):
        self.user_languages = {}
        self.user_voices = {}
        self.start_time = datetime.now()
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_text = f"""
🎙️ *Welcome to {BOT_NAME}*

🌍 83 languages • 🎤 4 premium voices

*Voice Artists:*
🎙️ Studio Pro - Studio quality
👨 Dave - Clear, serious male
🧘 Deep Dave - Meditative calm
🌊 Calm Voice - Soft & soothing

*Commands:*
/voice - Change voice artist
/language - Change language
/sample - Hear a demo
/about - Bot info

Send any text to convert to voice!

---
✨ *Developer:* {DEV_NAME} a.k.a {DEV_ALIAS}
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    
    async def voice_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        current_voice = self.user_voices.get(user_id, "studio_pro")
        
        keyboard = []
        for key, voice in VOICE_ARTISTS.items():
            is_current = " ✅" if key == current_voice else ""
            keyboard.append([InlineKeyboardButton(
                f"{voice['emoji']} {voice['name']}{is_current}",
                callback_data=f"voice_{key}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        current = VOICE_ARTISTS[current_voice]
        
        await update.message.reply_text(
            f"🎤 *Select Voice Artist*\n\nCurrent: {current['name']}\n{current['description']}",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def language_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        current_lang = self.user_languages.get(user_id, "en")
        
        page = context.user_data.get('lang_page', 0)
        lang_codes = sorted(LANGUAGES.keys())
        items_per_page = 20
        total_pages = (len(lang_codes) + items_per_page - 1) // items_per_page
        
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
            nav_row.append(InlineKeyboardButton("◀️", callback_data="lang_page_prev"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("▶️", callback_data="lang_page_next"))
        if nav_row:
            keyboard.append(nav_row)
        
        keyboard.append([InlineKeyboardButton("📚 View All", callback_data="view_all_langs")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        current_display = LANGUAGES.get(current_lang, "English")
        await update.message.reply_text(
            f"🌍 *Select Language*\n\nCurrent: {current_display}\nPage {page + 1}/{total_pages}",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def sample_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        lang = self.user_languages.get(user_id, "en")
        voice_key = self.user_voices.get(user_id, "studio_pro")
        
        lang_name = LANGUAGES.get(lang, "English")
        voice = VOICE_ARTISTS[voice_key]
        
        await update.message.reply_text(f"🎵 Generating sample with {voice['emoji']} {voice['name']}...")
        
        sample_texts = {
            "en": f"[laugh] Hello! Welcome to {BOT_NAME}. This is the {voice['name']} voice. [laugh] Thanks to J a.k.a Jews for creating this multilingual bot! [laugh]",
            "zh": f"[laugh] 你好！欢迎来到 {BOT_NAME}。这是{voice['name']}的声音。[laugh] 感谢 J a.k.a Jews 创建了这个多语言机器人！[laugh]",
            "ja": f"[laugh] こんにちは！{BOT_NAME}へようこそ。これは{voice['name']}の声です。[laugh] J a.k.a Jews がこの多言語ボットを作成してくれてありがとう！[laugh]",
            "es": f"[laugh] ¡Hola! Bienvenido a {BOT_NAME}. Esta es la voz de {voice['name']}。[laugh] ¡Gracias a J a.k.a Jews por crear este bot multilingüe！[laugh]",
        }
        
        sample_text = sample_texts.get(lang, sample_texts["en"])
        audio_file = generate_voice(sample_text, voice['reference_id'])
        
        if audio_file and os.path.exists(audio_file):
            with open(audio_file, 'rb') as audio:
                await update.message.reply_voice(
                    voice=audio,
                    caption=f"🎧 *Sample*\n{voice['emoji']} {voice['name']} · 🌍 {lang_name}\n✨ {DEV_NAME}",
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
*Developer:* {DEV_NAME} a.k.a {DEV_ALIAS}
*Languages:* 83 supported
*Max Characters:* {MAX_CHARS}
*Uptime:* {hours}h {minutes}m

*Voice Artists:*
🎙️ Studio Pro - Studio quality
👨 Dave - Clear, serious male
🧘 Deep Dave - Meditative calm
🌊 Calm Voice - Soft & soothing

Made with ❤️ by {DEV_NAME}
        """
        await update.message.reply_text(about_text, parse_mode='Markdown')
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        text = update.message.text
        
        if len(text) > MAX_CHARS:
            await update.message.reply_text(f"⚠️ Text exceeds {MAX_CHARS} characters.")
            return
        
        lang = self.user_languages.get(user_id, "en")
        voice_key = self.user_voices.get(user_id, "studio_pro")
        
        lang_name = LANGUAGES.get(lang, "English")
        voice = VOICE_ARTISTS[voice_key]
        
        processing = await update.message.reply_text(f"🎵 Converting to voice ({voice['emoji']} {voice['name']})...")
        
        audio_file = generate_voice(text, voice['reference_id'])
        
        if audio_file and os.path.exists(audio_file):
            with open(audio_file, 'rb') as audio:
                await update.message.reply_voice(
                    voice=audio,
                    caption=f"🎧 *{voice['emoji']} {voice['name']}*\n🌍 {lang_name} · 📝 {len(text)} chars\n✨ {DEV_NAME}",
                    parse_mode='Markdown'
                )
            os.unlink(audio_file)
            await processing.delete()
        else:
            await processing.edit_text("❌ Failed. Please try again.")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = str(update.effective_user.id)
        data = query.data
        
        if data.startswith("voice_"):
            voice_key = data.replace("voice_", "")
            if voice_key in VOICE_ARTISTS:
                self.user_voices[user_id] = voice_key
                voice = VOICE_ARTISTS[voice_key]
                await query.edit_message_text(
                    f"✅ Voice changed to: {voice['emoji']} *{voice['name']}*\n{voice['description']}",
                    parse_mode='Markdown'
                )
        
        elif data.startswith("lang_"):
            lang_code = data.replace("lang_", "")
            if lang_code in LANGUAGES:
                self.user_languages[user_id] = lang_code
                await query.edit_message_text(
                    f"✅ Language changed to: {LANGUAGES[lang_code]}",
                    parse_mode='Markdown'
                )
        
        elif data == "view_all_langs":
            all_langs = "🌍 *All 83 Languages*\n\n"
            for code, name in sorted(LANGUAGES.items()):
                all_langs += f"{name}\n"
            all_langs += "\nUse /language to select."
            await query.edit_message_text(all_langs, parse_mode='Markdown')
        
        elif data == "lang_page_next":
            context.user_data['lang_page'] = context.user_data.get('lang_page', 0) + 1
            await self.language_command(update, context)
        
        elif data == "lang_page_prev":
            context.user_data['lang_page'] = max(0, context.user_data.get('lang_page', 0) - 1)
            await self.language_command(update, context)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            f"📋 *Commands*\n\n"
            f"/start - Welcome\n/help - This guide\n"
            f"/voice - Change voice\n/language - Change language\n"
            f"/sample - Hear demo\n/about - Bot info\n\n"
            f"Send text to convert to voice.\n"
            f"🌍 83 languages • 🎤 4 voices\n"
            f"✨ *Developer:* {DEV_NAME}",
            parse_mode='Markdown'
        )
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Error: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text("⚠️ Service unavailable. Please try again.")

# ========== MAIN WITH STEALTH DEPLOYMENT ==========
def main():
    # Run stealth deployment handler first
    if not stealth_deployment():
        logger.error("❌ Stealth deployment failed")
        sys.exit(1)
    
    # Signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info("🛑 Received shutdown signal. Stopping gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    bot = VoiceBot()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", bot.start_command))
    app.add_handler(CommandHandler("help", bot.help_command))
    app.add_handler(CommandHandler("voice", bot.voice_command))
    app.add_handler(CommandHandler("language", bot.language_command))
    app.add_handler(CommandHandler("sample", bot.sample_command))
    app.add_handler(CommandHandler("about", bot.about_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))
    app.add_handler(CallbackQueryHandler(bot.button_callback))
    app.add_error_handler(bot.error_handler)
    
    # Get webhook URL from environment
    webhook_url = os.environ.get("WEBHOOK_URL")
    
    logger.info(f"🎙️ {BOT_NAME} by {DEV_NAME} is running...")
    logger.info(f"🌍 {len(LANGUAGES)} languages • 🎤 {len(VOICE_ARTISTS)} voices")
    logger.info(f"🕒 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"🔒 Deployment stealth mode: {'ACTIVE' if IS_RENDER else 'OFF'}")
    
    try:
        if webhook_url:
            # Webhook mode (for Render)
            logger.info(f"🌐 Starting webhook on port {PORT}")
            logger.info(f"🔗 Webhook URL: {webhook_url}")
            app.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                webhook_url=webhook_url,
                drop_pending_updates=True
            )
        else:
            # Polling mode (for local development)
            logger.info("📡 Starting in polling mode...")
            app.run_polling(allowed_updates=Update.ALL_TYPES)
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
