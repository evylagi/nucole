import os
import sys
import time
import logging
import requests
import tempfile
import signal
from datetime import datetime
from flask import Flask, Response
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

# ========== FLASK APP FOR HEALTH CHECK ==========
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "Bot is running!", 200

@flask_app.route('/health')
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}, 200

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

# ========== EMOTION TAGS FOR FISH.AUDIO ==========
EMOTIONS = {
    "happy": "[happy]",
    "sad": "[sad]",
    "angry": "[angry]",
    "excited": "[excited]",
    "calm": "[calm]",
    "laughing": "[laughing]",
    "whispering": "[whispering]",
    "serious": "[serious]",
    "friendly": "[friendly]",
    "neutral": "[neutral]"
}

# ========== SETUP ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== VOICE SERVICE ==========
def generate_voice(text, reference_id):
    """Generate voice with emotion support"""
    try:
        # Check for emotion tags in text
        emotion_processed = False
        for emotion_name, emotion_tag in EMOTIONS.items():
            if emotion_tag in text.lower():
                # Fish.audio supports emotion tags in the text
                # The model will interpret [happy], [sad], etc.
                emotion_processed = True
                break
        
        response = requests.post(
            "https://api.fish.audio/v1/tts",
            headers={
                "Authorization": f"Bearer {FISH_API_KEY}",
                "Content-Type": "application/json",
                "model": "s2.1-pro-free",
            },
            json={
                "text": text,  # Keep emotion tags in text
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
        self.user_languages = {}  # Store user language preferences
        self.user_voices = {}  # Store user voice preferences
        self.start_time = datetime.now()
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_text = f"""
🎙️ *Welcome to {BOT_NAME}*

🌍 83 languages • 🎤 4 premium voices • 😊 Emotion support

*Voice Artists:*
🎙️ Studio Pro - Studio quality
👨 Dave - Clear, serious male
🧘 Deep Dave - Meditative calm
🌊 Calm Voice - Soft & soothing

*Emotion Tags (add to your text):*
• [happy] 😊 - Cheerful tone
• [sad] 😢 - Melancholic tone
• [angry] 😠 - Intense tone
• [excited] 🤩 - Energetic tone
• [calm] 😌 - Relaxed tone
• [laughing] 😂 - Laughing while speaking
• [whispering] 🤫 - Whispered voice
• [serious] 😐 - Professional tone
• [friendly] 🤗 - Warm, inviting tone
• [neutral] 😐 - Balanced tone

*Commands:*
/voice - Change voice artist
/language - Change language
/emotions - Show emotion tags
/sample - Hear a demo
/about - Bot info

*Example:* Send text like:
"[happy] Hello! This is a happy message."

---
✨ *Developer:* {DEV_NAME} a.k.a {DEV_ALIAS}
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    
    async def emotions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available emotion tags"""
        emotions_text = """
😊 *Emotion Tags Guide*

Add these tags to your text for emotional voice:

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

*How to use:*
Put the tag at the start of your message:
`[happy] Hello! This is a happy message.`

*Multiple tags:*
`[excited] [laughing] This is exciting!`

---
✨ *Developer:* {DEV_NAME}
        """
        await update.message.reply_text(emotions_text, parse_mode='Markdown')
    
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
        """Show language selection with pagination"""
        user_id = str(update.effective_user.id)
        current_lang = self.user_languages.get(user_id, "en")
        
        # Get current page from context or default to 0
        page = context.user_data.get('lang_page', 0)
        
        # Get all language codes sorted
        lang_codes = sorted(LANGUAGES.keys())
        items_per_page = 20
        total_pages = (len(lang_codes) + items_per_page - 1) // items_per_page
        
        # Ensure page is within bounds
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        # Calculate start and end indices
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, len(lang_codes))
        
        # Build keyboard
        keyboard = []
        for code in lang_codes[start_idx:end_idx]:
            if code in LANGUAGES:
                is_current = " ✅" if code == current_lang else ""
                keyboard.append([InlineKeyboardButton(
                    f"{LANGUAGES[code]}{is_current}",
                    callback_data=f"lang_{code}"
                )])
        
        # Add navigation buttons
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ Previous", callback_data="lang_page_prev"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("Next ▶️", callback_data="lang_page_next"))
        if nav_row:
            keyboard.append(nav_row)
        
        # Add view all button
        keyboard.append([InlineKeyboardButton("📚 View All Languages", callback_data="view_all_langs")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        current_display = LANGUAGES.get(current_lang, "English")
        
        await update.message.reply_text(
            f"🌍 *Select Language*\n\nCurrent: {current_display}\nPage {page + 1}/{total_pages}\n\nChoose from below:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def sample_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a sample with emotion in user's language"""
        user_id = str(update.effective_user.id)
        lang = self.user_languages.get(user_id, "en")
        voice_key = self.user_voices.get(user_id, "studio_pro")
        
        lang_name = LANGUAGES.get(lang, "English")
        voice = VOICE_ARTISTS[voice_key]
        
        await update.message.reply_text(f"🎵 Generating sample with {voice['emoji']} {voice['name']} in {lang_name}...")
        
        # Sample texts with emotions in different languages
        sample_texts = {
            "en": f"[excited] [laughing] Hello! Welcome to {BOT_NAME}! This is the {voice['name']} voice with emotions! [laughing] Thanks to J a.k.a Jews for creating this amazing bot!",
            "zh": f"[excited] [laughing] 你好！欢迎来到 {BOT_NAME}！这是{voice['name']}的声音，带有情感！[laughing] 感谢 J a.k.a Jews 创建了这个令人惊叹的机器人！",
            "ja": f"[excited] [laughing] こんにちは！{BOT_NAME}へようこそ！これは{voice['name']}の感情的な声です！[laughing] J a.k.a Jews がこの素晴らしいボットを作成してくれてありがとう！",
            "es": f"[excited] [laughing] ¡Hola! ¡Bienvenido a {BOT_NAME}! ¡Esta es la voz de {voice['name']} con emociones! [laughing] ¡Gracias a J a.k.a Jews por crear este increíble bot!",
            "ar": f"[excited] [laughing] مرحباً! مرحباً بك في {BOT_NAME}! هذا هو صوت {voice['name']} مع المشاعر! [laughing] شكراً لـ J a.k.a Jews على إنشاء هذا البوت المذهل!",
        }
        
        sample_text = sample_texts.get(lang, sample_texts["en"])
        audio_file = generate_voice(sample_text, voice['reference_id'])
        
        if audio_file and os.path.exists(audio_file):
            with open(audio_file, 'rb') as audio:
                await update.message.reply_voice(
                    voice=audio,
                    caption=f"🎧 *Sample with Emotions*\n{voice['emoji']} {voice['name']} · 🌍 {lang_name}\n😊 [excited] [laughing]\n✨ {DEV_NAME}",
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
*Emotions:* 10 emotion tags
*Max Characters:* {MAX_CHARS}
*Uptime:* {hours}h {minutes}m

*Voice Artists:*
🎙️ Studio Pro - Studio quality
👨 Dave - Clear, serious male
🧘 Deep Dave - Meditative calm
🌊 Calm Voice - Soft & soothing

*Emotion Tags:*
[happy] [sad] [angry] [excited] [calm]
[laughing] [whispering] [serious] [friendly] [neutral]

Made with ❤️ by {DEV_NAME}
        """
        await update.message.reply_text(about_text, parse_mode='Markdown')
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Convert text to voice with language and emotion support"""
        user_id = str(update.effective_user.id)
        text = update.message.text
        
        if len(text) > MAX_CHARS:
            await update.message.reply_text(f"⚠️ Text exceeds {MAX_CHARS} characters.")
            return
        
        # Get user preferences (language and voice)
        lang = self.user_languages.get(user_id, "en")
        voice_key = self.user_voices.get(user_id, "studio_pro")
        
        lang_name = LANGUAGES.get(lang, "English")
        voice = VOICE_ARTISTS[voice_key]
        
        # Detect emotion tags in text
        detected_emotions = []
        for emotion_name, emotion_tag in EMOTIONS.items():
            if emotion_tag in text.lower():
                detected_emotions.append(emotion_name)
        
        emotion_indicator = f"😊 {', '.join(detected_emotions)}" if detected_emotions else "😐 Neutral"
        
        processing = await update.message.reply_text(
            f"🎵 Converting to voice ({voice['emoji']} {voice['name']} in {lang_name})\n{emotion_indicator}"
        )
        
        # Generate voice with the text (emotion tags included)
        audio_file = generate_voice(text, voice['reference_id'])
        
        if audio_file and os.path.exists(audio_file):
            with open(audio_file, 'rb') as audio:
                # Build caption with language and emotion info
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
        """Handle button clicks with proper page management"""
        query = update.callback_query
        await query.answer()
        
        user_id = str(update.effective_user.id)
        data = query.data
        
        # Handle voice selection
        if data.startswith("voice_"):
            voice_key = data.replace("voice_", "")
            if voice_key in VOICE_ARTISTS:
                self.user_voices[user_id] = voice_key
                voice = VOICE_ARTISTS[voice_key]
                await query.edit_message_text(
                    f"✅ Voice changed to: {voice['emoji']} *{voice['name']}*\n{voice['description']}",
                    parse_mode='Markdown'
                )
        
        # Handle language selection
        elif data.startswith("lang_") and not data.startswith("lang_page_"):
            lang_code = data.replace("lang_", "")
            if lang_code in LANGUAGES:
                self.user_languages[user_id] = lang_code
                lang_name = LANGUAGES[lang_code]
                await query.edit_message_text(
                    f"✅ Language changed to: {lang_name}\n\n"
                    f"Your text will now be processed in {lang_name}.\n"
                    f"Use emotion tags like [happy] or [sad] for expressive voice!",
                    parse_mode='Markdown'
                )
        
        # Handle page navigation
        elif data == "lang_page_next":
            current_page = context.user_data.get('lang_page', 0)
            context.user_data['lang_page'] = current_page + 1
            await self.language_command(update, context)
        
        elif data == "lang_page_prev":
            current_page = context.user_data.get('lang_page', 0)
            context.user_data['lang_page'] = max(0, current_page - 1)
            await self.language_command(update, context)
        
        # Handle view all languages
        elif data == "view_all_langs":
            all_langs = "🌍 *All 83 Languages*\n\n"
            # Group by region for better readability
            regions = {
                "🇪🇺 European": ["en", "fr", "de", "es", "pt", "it", "nl", "pl", "ru", "uk", "ro", "hu", "cs", "sk", "sl", "hr", "sr", "bs", "mk", "sq", "lv", "lt", "et", "fi", "sv", "nb", "da", "is", "ga", "cy", "eu", "ca", "gl", "el", "bg", "be"],
                "🇦🇸 Asian": ["zh", "ja", "ko", "hi", "bn", "pa", "te", "ta", "mr", "gu", "kn", "ml", "or", "as", "mai", "sat", "ks", "sd", "kok", "mni", "bodo", "doi", "ne", "si", "my", "km", "lo", "mn", "hy", "ka", "az", "kk", "uz", "tk", "tg", "ps", "fa", "he", "ur"],
                "🌍 Other": ["ar", "id", "ms", "fil", "vi", "th", "am", "sw", "zu", "xh", "af", "tr"]
            }
            
            for region, codes in regions.items():
                region_langs = [LANGUAGES[code] for code in codes if code in LANGUAGES]
                if region_langs:
                    all_langs += f"*{region}*\n"
                    for i in range(0, len(region_langs), 8):
                        chunk = region_langs[i:i+8]
                        all_langs += " • ".join(chunk) + "\n"
                    all_langs += "\n"
            
            all_langs += "Use /language to select your preferred language."
            await query.edit_message_text(all_langs, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            f"📋 *Commands*\n\n"
            f"/start - Welcome message\n"
            f"/help - This guide\n"
            f"/voice - Change voice artist\n"
            f"/language - Change language (83 options)\n"
            f"/emotions - Show emotion tags\n"
            f"/sample - Hear a demo with emotions\n"
            f"/about - Bot info\n\n"
            f"*Emotion Tags:*\n"
            f"[happy] 😊 [sad] 😢 [angry] 😠 [excited] 🤩\n"
            f"[calm] 😌 [laughing] 😂 [whispering] 🤫\n"
            f"[serious] 😐 [friendly] 🤗 [neutral] 😐\n\n"
            f"Send text to convert to voice.\n"
            f"🌍 83 languages • 🎤 4 voices • 😊 Emotions\n"
            f"✨ *Developer:* {DEV_NAME}",
            parse_mode='Markdown'
        )
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Error: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text("⚠️ Service unavailable. Please try again.")

# ========== MAIN WITH FLASK ==========
def run_bot():
    """Run the Telegram bot"""
    bot = VoiceBot()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", bot.start_command))
    app.add_handler(CommandHandler("help", bot.help_command))
    app.add_handler(CommandHandler("voice", bot.voice_command))
    app.add_handler(CommandHandler("language", bot.language_command))
    app.add_handler(CommandHandler("emotions", bot.emotions_command))
    app.add_handler(CommandHandler("sample", bot.sample_command))
    app.add_handler(CommandHandler("about", bot.about_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))
    app.add_handler(CallbackQueryHandler(bot.button_callback))
    app.add_error_handler(bot.error_handler)
    
    webhook_url = os.environ.get("WEBHOOK_URL")
    
    logger.info(f"🎙️ {BOT_NAME} by {DEV_NAME} is running...")
    logger.info(f"🌍 {len(LANGUAGES)} languages • 🎤 {len(VOICE_ARTISTS)} voices • 😊 10 emotions")
    
    if webhook_url:
        logger.info(f"🌐 Starting webhook on port {PORT}")
        logger.info(f"🔗 Webhook URL: {webhook_url}")
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
