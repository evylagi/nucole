import os
import sys
import json
import signal
import logging
import tempfile
import threading
from datetime import datetime

import requests
from flask import Flask
from werkzeug.serving import run_simple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

from config import (
    TELEGRAM_TOKEN,
    FISH_API_KEY,
    BOT_NAME,
    DEV_NAME,
    MAX_CHARS,
    PORT,
    VOICES_FILE,
    DEFAULT_VOICES,
    EMOTIONS,
    LANGUAGES,
)

flask_app = Flask(__name__)


@flask_app.route("/")
def health_check():
    return "Bot is running!", 200


@flask_app.route("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}, 200


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def load_voices_from_json():
    voice_artists = {}

    if os.path.exists(VOICES_FILE):
        try:
            logger.info(f"📂 Loading voices from {VOICES_FILE} in file order...")
            with open(VOICES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "models" in data:
                voices_data = data.get("models", [])
            elif "voices" in data:
                voices_data = data.get("voices", [])
            else:
                voices_data = data.get("items", [])

            if not voices_data:
                logger.warning(f"⚠️ No voices found in {VOICES_FILE}")
            else:
                logger.info(f"📊 Found {len(voices_data)} voices in JSON file")

                seen_ids = set()
                json_count = 0

                for i, voice in enumerate(voices_data):
                    voice_id = (
                        voice.get("_id")
                        or voice.get("id")
                        or voice.get("reference_id")
                    )
                    if not voice_id or voice_id in seen_ids:
                        continue
                    seen_ids.add(voice_id)

                    title = voice.get("title") or voice.get("name") or f"Voice {i+1}"
                    language = voice.get("language", "Unknown")
                    gender = voice.get("gender", "Unknown")
                    description = voice.get(
                        "description", f"{gender} voice in {language}"
                    )

                    emoji = "🎙️"
                    gl = gender.lower()
                    if gl in ("male", "m"):
                        emoji = "👨"
                    elif gl in ("female", "f"):
                        emoji = "👩"

                    key = f"json_voice_{json_count + 1}"
                    voice_artists[key] = {
                        "name": title[:30],
                        "reference_id": voice_id,
                        "emoji": emoji,
                        "description": f"{gender} · {language} · {description[:50]}",
                        "full_data": voice,
                        "is_default": False,
                    }
                    json_count += 1

                logger.info(
                    f"✅ Added {json_count} voices from JSON (file order preserved)"
                )
        except Exception as e:
            logger.error(f"❌ Error loading voices from JSON: {e}")
    else:
        logger.warning(f"⚠️ {VOICES_FILE} not found. Using default voices only.")

    existing_ref_ids = {v["reference_id"] for v in voice_artists.values()}
    defaults_added = 0
    for key, voice in DEFAULT_VOICES.items():
        if voice["reference_id"] in existing_ref_ids:
            continue
        entry = dict(voice)
        entry["is_default"] = True
        voice_artists[key] = entry
        defaults_added += 1

    logger.info(f"✅ Appended {defaults_added} default voices at the end")
    logger.info(f"🎤 Total voices loaded: {len(voice_artists)}")
    return voice_artists


VOICE_ARTISTS = load_voices_from_json()

DEFAULT_FALLBACK_VOICE = "studio_pro"


def generate_voice(text: str, reference_id: str):
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
            timeout=60,
        )
        if response.status_code == 200:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            tmp.write(response.content)
            tmp.close()
            return tmp.name
        logger.error(f"API Error: {response.status_code} - {response.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"generate_voice error: {e}")
        return None


class VoiceBot:
    def __init__(self):
        self.user_voices = {}
        self.user_languages = {}
        self.start_time = datetime.now()
        self.voice_pages = {}
        self.lang_pages = {}
        self.search_pages = {}
        self.search_results = {}

    def _resolve_current_voice(self, user_id: str):
        if not VOICE_ARTISTS:
            return None, None

        key = self.user_voices.get(user_id)
        if key and key in VOICE_ARTISTS:
            return key, VOICE_ARTISTS[key]

        if DEFAULT_FALLBACK_VOICE in VOICE_ARTISTS:
            return DEFAULT_FALLBACK_VOICE, VOICE_ARTISTS[DEFAULT_FALLBACK_VOICE]

        for dkey in DEFAULT_VOICES:
            if dkey in VOICE_ARTISTS:
                return dkey, VOICE_ARTISTS[dkey]

        first_key = next(iter(VOICE_ARTISTS))
        return first_key, VOICE_ARTISTS[first_key]

    def _is_default_voice(self, key: str) -> bool:
        if key in DEFAULT_VOICES:
            return True
        return bool(VOICE_ARTISTS.get(key, {}).get("is_default"))

    def _set_voice_confirmation(self, voice_key: str) -> str:
        voice = VOICE_ARTISTS[voice_key]
        badge = "⭐ Default Voice! " if self._is_default_voice(voice_key) else ""
        return (
            f"✅ Voice changed to: {voice['emoji']} *{voice['name']}*\n"
            f"{badge}{voice['description']}\n\n"
            f"Send any text to hear this voice!"
        )

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = f"""
🎙️ *Welcome to {BOT_NAME}*

🌍 Supports {len(LANGUAGES)} languages!
🎤 {len(VOICE_ARTISTS)} premium voice artists
😊 {len(EMOTIONS)} emotion tags

*How to use:*
1. Set your language with /language
2. Choose your voice with /voice or /search
3. Send text with emotion tags!

*Commands:*
/language - Set your language
/voice - Browse all voices
/search [name] - Search for voices
/emotions - Show emotion tags
/sample - Hear a demo
/voices - List all available voices
/about - Bot info
/help - Full guide

---
✨ *Developer:* {DEV_NAME}
"""
        await update.message.reply_text(text, parse_mode="Markdown")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            f"📋 *Commands*\n\n"
            f"/start - Welcome message\n"
            f"/help - This guide\n"
            f"/language - Set your language ({len(LANGUAGES)} options)\n"
            f"/voice - Browse all voices ({len(VOICE_ARTISTS)} total)\n"
            f"/search [name] - Search for voices\n"
            f"/voices - List all available voices\n"
            f"/emotions - Show emotion tags\n"
            f"/sample - Hear a demo in your language\n"
            f"/about - Bot info\n\n"
            f"*How to use:*\n"
            f"1. Set your language with /language\n"
            f"2. Choose your voice with /voice or /search\n"
            f"3. Send text with emotion tags!\n\n"
            f"⭐ = Default Voice ({len(DEFAULT_VOICES)} always available)\n\n"
            f"*Emotion Tags:*\n"
            f"[happy] 😊 [sad] 😢 [angry] 😠 [excited] 🤩\n"
            f"[calm] 😌 [laughing] 😂 [whispering] 🤫\n"
            f"[serious] 😐 [friendly] 🤗 [neutral] 😐\n\n"
            f"✨ *Developer:* {DEV_NAME}"
        )
        await update.message.reply_text(text, parse_mode="Markdown")

    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uptime = datetime.now() - self.start_time
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds % 3600) // 60
        text = f"""
ℹ️ *About {BOT_NAME}*

*Version:* 3.2
*Developer:* {DEV_NAME}
*Languages:* {len(LANGUAGES)} supported
*Emotions:* {len(EMOTIONS)} emotion tags
*Voice Artists:* {len(VOICE_ARTISTS)} total
*Default Voices:* {len(DEFAULT_VOICES)} always available
*Max Characters:* {MAX_CHARS}
*Uptime:* {hours}h {minutes}m

*Features:*
• {len(LANGUAGES)} languages with auto-detection
• {len(VOICE_ARTISTS)} premium voice artists
• {len(EMOTIONS)} emotion expressions
• Studio quality audio

Made with ❤️ by {DEV_NAME}
"""
        await update.message.reply_text(text, parse_mode="Markdown")

    async def emotions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        lines = ["😊 *Emotion Tags Guide*\n", "Add these tags to your text:\n"]
        for name, tag in EMOTIONS.items():
            lines.append(f"• `{tag}` - {name.capitalize()} tone")
        lines.append("\n*Example:*")
        lines.append("`[happy] Hello! This is a happy message.`")
        lines.append(f"\n---\n✨ *Developer:* {DEV_NAME}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def voices_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        total = len(VOICE_ARTISTS)
        defaults = len(DEFAULT_VOICES)
        text = (
            f"🎤 *Available Voices ({total} total)*\n\n"
            f"⭐ Default Voices ({defaults}) — always available:\n"
        )
        for key, v in DEFAULT_VOICES.items():
            text += f"   {v['emoji']} *{v['name']}*\n"
        text += (
            f"\n📌 Use /voice to browse every voice with pagination\n"
            f"🔍 Or use /search [keyword] to find a specific voice"
        )
        await update.message.reply_text(text, parse_mode="Markdown")

    async def voice_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        self.voice_pages[user_id] = 0
        await self.show_voice_page(update, context, user_id, 0)

    async def show_voice_page(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: str,
        page: int,
    ):
        voice_keys = list(VOICE_ARTISTS.keys())
        if not voice_keys:
            await update.message.reply_text("❌ No voices available.")
            return

        current_key, current = self._resolve_current_voice(user_id)
        items_per_page = 10
        total_pages = (len(voice_keys) + items_per_page - 1) // items_per_page
        page = max(0, min(page, total_pages - 1))
        self.voice_pages[user_id] = page

        start = page * items_per_page
        end = min(start + items_per_page, len(voice_keys))

        keyboard = []
        for key in voice_keys[start:end]:
            voice = VOICE_ARTISTS[key]
            marker = ""
            if self._is_default_voice(key):
                marker += " ⭐"
            if key == current_key:
                marker += " ✅"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{voice['emoji']} {voice['name']}{marker}",
                        callback_data=f"voice_{key}",
                    )
                ]
            )

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("◀️ Previous", callback_data="voice_page_prev"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("Next ▶️", callback_data="voice_page_next"))
        if nav:
            keyboard.append(nav)

        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            f"🎤 *Select Voice Artist*\n\n"
            f"Current: {current['name']}\n"
            f"{current['description']}\n"
            f"⭐ = Default Voice ({len(DEFAULT_VOICES)} available)\n"
            f"Page {page + 1}/{total_pages} · {len(voice_keys)} voices total"
        )

        if update.callback_query:
            await update.callback_query.edit_message_text(
                text, parse_mode="Markdown", reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                text, parse_mode="Markdown", reply_markup=reply_markup
            )

    async def language_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        page = self.lang_pages.get(user_id, 0)
        await self.show_language_page(update, context, user_id, page)

    async def show_language_page(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: str,
        page: int,
    ):
        current_lang = self.user_languages.get(user_id, "en")
        codes = sorted(LANGUAGES.keys())
        items_per_page = 20
        total_pages = (len(codes) + items_per_page - 1) // items_per_page
        page = max(0, min(page, total_pages - 1))
        self.lang_pages[user_id] = page

        start = page * items_per_page
        end = min(start + items_per_page, len(codes))

        keyboard = []
        for code in codes[start:end]:
            marker = " ✅" if code == current_lang else ""
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{LANGUAGES[code]}{marker}", callback_data=f"lang_{code}"
                    )
                ]
            )

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("◀️ Previous", callback_data="lang_page_prev"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("Next ▶️", callback_data="lang_page_next"))
        if nav:
            keyboard.append(nav)

        keyboard.append(
            [InlineKeyboardButton("📚 View All Languages", callback_data="view_all_langs")]
        )
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            f"🌍 *Select Your Language*\n\n"
            f"Current: {LANGUAGES.get(current_lang, 'English')}\n"
            f"Page {page + 1}/{total_pages}"
        )

        if update.callback_query:
            await update.callback_query.edit_message_text(
                text, parse_mode="Markdown", reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                text, parse_mode="Markdown", reply_markup=reply_markup
            )

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        query = " ".join(context.args) if context.args else ""

        if not query:
            await update.message.reply_text(
                "🔍 *How to search for voices:*\n\n"
                "Type: `/search narrator`\n"
                "Type: `/search female`\n"
                "Type: `/search spanish`\n"
                "Type: `/search dave`\n\n"
                "⭐ Default voices are shown first!\n"
                "Try searching for voice names, languages, or descriptions!\n"
                "You can also browse all voices with `/voice`",
                parse_mode="Markdown",
            )
            return

        self.search_results[user_id] = None
        await self.show_search_page(update, context, user_id, 0, query)

    async def show_search_page(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: str,
        page: int,
        query: str,
    ):
        cached = self.search_results.get(user_id)
        if cached and cached.get("query") == query:
            results = cached["results"]
        else:
            q = query.lower()
            results = []
            for key, voice in VOICE_ARTISTS.items():
                hay = f"{voice['name']} {voice['description']}".lower()
                if q in hay:
                    results.append((key, voice, self._is_default_voice(key)))
            results.sort(key=lambda x: (not x[2], x[1]["name"].lower()))
            self.search_results[user_id] = {"query": query, "results": results}

        if not results:
            msg = f"❌ No voices found for '{query}'\n\nTry different keywords!"
            if update.callback_query:
                await update.callback_query.edit_message_text(msg, parse_mode="Markdown")
            else:
                await update.message.reply_text(msg, parse_mode="Markdown")
            return

        items_per_page = 5
        total_pages = (len(results) + items_per_page - 1) // items_per_page
        page = max(0, min(page, total_pages - 1))
        self.search_pages[user_id] = page

        start = page * items_per_page
        end = min(start + items_per_page, len(results))

        keyboard = []
        for key, voice, is_default in results[start:end]:
            label = f"{'⭐ ' if is_default else ''}{voice['emoji']} {voice['name']}"
            keyboard.append(
                [InlineKeyboardButton(label, callback_data=f"search_select_{key}")]
            )

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("◀️ Previous", callback_data="search_page_prev"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("Next ▶️", callback_data="search_page_next"))
        if nav:
            keyboard.append(nav)
        keyboard.append(
            [InlineKeyboardButton("🎤 Back to All Voices", callback_data="search_back_to_voice")]
        )

        reply_markup = InlineKeyboardMarkup(keyboard)

        text = f"🔍 *Search Results for \"{query}\"*\n\n"
        text += f"Found {len(results)} voices:\n"
        text += f"Page {page + 1}/{total_pages}\n\n"
        for key, voice, is_default in results[start:end]:
            text += f"{'⭐ ' if is_default else ''}{voice['emoji']} *{voice['name']}*"
            if is_default:
                text += " *(Default)*"
            text += f"\n   {voice['description']}\n"
            text += f"   📌 Click to select\n\n"

        if update.callback_query:
            await update.callback_query.edit_message_text(
                text, parse_mode="Markdown", reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                text, parse_mode="Markdown", reply_markup=reply_markup
            )

    async def sample_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        _, voice = self._resolve_current_voice(user_id)
        if not voice:
            await update.message.reply_text("❌ No voices available.")
            return

        lang = self.user_languages.get(user_id, "en")
        lang_name = LANGUAGES.get(lang, "English")

        await update.message.reply_text(
            f"🎵 Generating sample in {lang_name} with {voice['emoji']} {voice['name']}..."
        )

        templates = {
            "en": f"[excited] [laughing] Hello! Welcome to {BOT_NAME}! This is the {voice['name']} voice with emotions! [laughing] Thanks to {DEV_NAME} for creating this amazing bot!",
            "zh": f"[excited] [laughing] 你好！欢迎来到 {BOT_NAME}！这是{voice['name']}的声音，带有情感！[laughing] 感谢 {DEV_NAME} 创建了这个令人惊叹的机器人！",
            "ja": f"[excited] [laughing] こんにちは！{BOT_NAME}へようこそ！これは{voice['name']}の感情的な声です！[laughing] {DEV_NAME}がこの素晴らしいボットを作成してくれてありがとう！",
            "es": f"[excited] [laughing] ¡Hola! ¡Bienvenido a {BOT_NAME}! ¡Esta es la voz de {voice['name']} con emociones! [laughing] ¡Gracias a {DEV_NAME} por crear este increíble bot!",
        }
        sample_text = templates.get(lang, templates["en"])

        audio_file = generate_voice(sample_text, voice["reference_id"])
        if audio_file and os.path.exists(audio_file):
            with open(audio_file, "rb") as audio:
                await update.message.reply_voice(
                    voice=audio,
                    caption=(
                        f"🎧 *Sample in {lang_name}*\n"
                        f"{voice['emoji']} {voice['name']}\n"
                        f"😊 [excited] [laughing]\n"
                        f"✨ {DEV_NAME}"
                    ),
                    parse_mode="Markdown",
                )
            os.unlink(audio_file)
        else:
            await update.message.reply_text("❌ Failed. Please try again.")

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        text = update.message.text

        if len(text) > MAX_CHARS:
            await update.message.reply_text(f"⚠️ Text exceeds {MAX_CHARS} characters.")
            return

        _, voice = self._resolve_current_voice(user_id)
        if not voice:
            await update.message.reply_text("❌ No voices available.")
            return

        lang = self.user_languages.get(user_id, "en")
        lang_name = LANGUAGES.get(lang, "English")

        detected = [name for name, tag in EMOTIONS.items() if tag in text.lower()]
        emotion_indicator = f"😊 {', '.join(detected)}" if detected else "😐 Neutral"

        processing = await update.message.reply_text(
            f"🎵 Converting to voice ({voice['emoji']} {voice['name']})\n"
            f"🌍 Language: {lang_name}\n{emotion_indicator}"
        )

        audio_file = generate_voice(text, voice["reference_id"])
        if audio_file and os.path.exists(audio_file):
            with open(audio_file, "rb") as audio:
                caption = (
                    f"🎧 *{voice['emoji']} {voice['name']}*\n"
                    f"🌍 {lang_name} · 📝 {len(text)} chars"
                )
                if detected:
                    caption += f"\n😊 Emotion: {', '.join(detected)}"
                caption += f"\n✨ {DEV_NAME}"
                await update.message.reply_voice(
                    voice=audio, caption=caption, parse_mode="Markdown"
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

        if data.startswith("voice_") and not data.startswith("voice_page_"):
            key = data[len("voice_"):]
            if key in VOICE_ARTISTS:
                self.user_voices[user_id] = key
                await query.edit_message_text(
                    self._set_voice_confirmation(key), parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    "❌ Voice not found. Please try again.", parse_mode="Markdown"
                )

        elif data == "voice_page_next":
            page = self.voice_pages.get(user_id, 0) + 1
            await self.show_voice_page(update, context, user_id, page)

        elif data == "voice_page_prev":
            page = max(0, self.voice_pages.get(user_id, 0) - 1)
            await self.show_voice_page(update, context, user_id, page)

        elif data.startswith("search_select_"):
            key = data[len("search_select_"):]
            if key in VOICE_ARTISTS:
                self.user_voices[user_id] = key
                await query.edit_message_text(
                    self._set_voice_confirmation(key), parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    "❌ Voice not found. Please try again.", parse_mode="Markdown"
                )

        elif data == "search_page_next":
            cached = self.search_results.get(user_id)
            if cached:
                page = self.search_pages.get(user_id, 0) + 1
                await self.show_search_page(
                    update, context, user_id, page, cached["query"]
                )
            else:
                await query.edit_message_text(
                    "❌ Search results expired. Please search again with /search",
                    parse_mode="Markdown",
                )

        elif data == "search_page_prev":
            cached = self.search_results.get(user_id)
            if cached:
                page = max(0, self.search_pages.get(user_id, 0) - 1)
                await self.show_search_page(
                    update, context, user_id, page, cached["query"]
                )
            else:
                await query.edit_message_text(
                    "❌ Search results expired. Please search again with /search",
                    parse_mode="Markdown",
                )

        elif data == "search_back_to_voice":
            page = self.voice_pages.get(user_id, 0)
            await self.show_voice_page(update, context, user_id, page)

        elif data.startswith("lang_") and not data.startswith("lang_page_"):
            code = data[len("lang_"):]
            if code in LANGUAGES:
                self.user_languages[user_id] = code
                await query.edit_message_text(
                    f"✅ Language set to: {LANGUAGES[code]}\n\n"
                    f"Your text will now be processed in {LANGUAGES[code]}.\n"
                    f"Send a message or try /sample to hear it!",
                    parse_mode="Markdown",
                )

        elif data == "lang_page_next":
            page = self.lang_pages.get(user_id, 0) + 1
            await self.show_language_page(update, context, user_id, page)

        elif data == "lang_page_prev":
            page = max(0, self.lang_pages.get(user_id, 0) - 1)
            await self.show_language_page(update, context, user_id, page)

        elif data == "view_all_langs":
            text = f"🌍 *All {len(LANGUAGES)} Languages*\n\n"
            text += "\n".join(name for _, name in sorted(LANGUAGES.items()))
            text += "\n\nUse /language to select your preferred language."
            await query.edit_message_text(text, parse_mode="Markdown")

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Error: {context.error}")
        if isinstance(update, Update):
            if update.effective_message:
                await update.effective_message.reply_text(
                    "⚠️ Service unavailable. Please try again."
                )
            elif update.callback_query:
                await update.callback_query.edit_message_text(
                    "⚠️ Service unavailable. Please try again."
                )


def run_bot():
    bot = VoiceBot()
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", bot.start_command))
    app.add_handler(CommandHandler("help", bot.help_command))
    app.add_handler(CommandHandler("language", bot.language_command))
    app.add_handler(CommandHandler("voice", bot.voice_command))
    app.add_handler(CommandHandler("search", bot.search_command))
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
    logger.info(f"🎤 {len(VOICE_ARTISTS)} voice artists available ({len(DEFAULT_VOICES)} defaults)")
    logger.info(f"😊 {len(EMOTIONS)} emotion tags")

    if webhook_url:
        logger.info(f"🌐 Starting webhook on port {PORT}")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=webhook_url,
            drop_pending_updates=True,
        )
    else:
        logger.info("📡 Starting in polling mode...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    def signal_handler(sig, frame):
        logger.info("🛑 Shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    flask_thread = threading.Thread(
        target=lambda: run_simple(
            "0.0.0.0", PORT, flask_app, use_reloader=False, use_debugger=False
        )
    )
    flask_thread.daemon = True
    flask_thread.start()

    logger.info(f"🌐 Health check available at http://0.0.0.0:{PORT}/")
    logger.info(f"🌐 Health check available at http://0.0.0.0:{PORT}/health")

    run_bot()


if __name__ == "__main__":
    main()
