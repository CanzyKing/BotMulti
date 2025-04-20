import os
import sqlite3
import logging
from datetime import datetime
import yt_dlp as youtube_dl
import requests
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    BotCommand
)
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    CallbackContext,
    ConversationHandler
)
from openai import OpenAI

# Konfigurasi
TOKEN = "7634379925:AAGKt0UIPkdt0Sn7Te6delF6tW8O6zWUMrQ"
OPENAI_API_KEY = "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"
ADMIN_ID = 6086282402  # Ganti dengan ID admin Anda
DATABASE_NAME = "bot_users.db"
START_IMAGE_PATH = "start.jpg"

# Inisialisasi OpenAI
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States untuk ConversationHandler
REQUEST_CODE, DEBUG_FILE = range(2)

# Inisialisasi database
def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Tabel users
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        is_active INTEGER DEFAULT 1,
        join_date TEXT
    )
    ''')
    
    # Tabel admin_messages
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_messages (
        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message_text TEXT,
        timestamp TEXT
    )
    ''')
    
    conn.commit()
    conn.close()

# Fungsi untuk menambahkan user ke database
def add_user_to_db(user):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, join_date)
    VALUES (?, ?, ?, ?, ?)
    ''', (
        user.id,
        user.username,
        user.first_name,
        user.last_name,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    
    conn.commit()
    conn.close()

# Fungsi untuk mendapatkan semua user aktif
def get_active_users():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT user_id FROM users WHERE is_active = 1")
    active_users = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return active_users

# Fungsi untuk memeriksa apakah user adalah admin
def is_admin(user_id):
    return user_id == ADMIN_ID

# Handler command /start
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    add_user_to_db(user)
    
    # Kirim foto sambutan jika ada
    if os.path.exists(START_IMAGE_PATH):
        with open(START_IMAGE_PATH, 'rb') as photo:
            update.message.reply_photo(
                photo=photo,
                caption=f"*✨ Halo {user.first_name}! ✨*\n\n"
                        "*Selamat datang di Canzy-Xtr Downloader Bot!*\n\n"
                        "Saya bisa membantu Anda:\n"
                        "- 📥 Mengunduh video dari YouTube & TikTok\n"
                        "- 💻 Membuat file kode sederhana\n"
                        "- 🐞 Debugging kode Anda\n\n"
                        "Gunakan menu di bawah untuk memulai!",
                parse_mode='Markdown',
                reply_markup=main_menu_keyboard()
            )
    else:
        update.message.reply_text(
            f"*✨ Halo {user.first_name}! ✨*\n\n"
            "*Selamat datang di Canzy-Xtr Downloader Bot!*\n\n"
            "Saya bisa membantu Anda:\n"
            "- 📥 Mengunduh video dari YouTube & TikTok\n"
            "- 💻 Membuat file kode sederhana\n"
            "- 🐞 Debugging kode Anda\n\n"
            "Gunakan menu di bawah untuk memulai!",
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard()
        )

# Keyboard menu utama
def main_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("📥 Download Video", callback_data='download_menu'),
            InlineKeyboardButton("💻 Buat Kode", callback_data='create_code')
        ],
        [
            InlineKeyboardButton("🐞 Debug Kode", callback_data='debug_code'),
            InlineKeyboardButton("ℹ️ Tentang Bot", callback_data='about')
        ]
    ]
    
    if is_admin(ADMIN_ID):
        keyboard.append([
            InlineKeyboardButton("👑 Admin Menu", callback_data='admin_menu')
        ])
    
    return InlineKeyboardMarkup(keyboard)

# Handler callback query
def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    if query.data == 'download_menu':
        query.edit_message_text(
            text="*📥 Pilih Platform Download:*",
            parse_mode='Markdown',
            reply_markup=download_menu_keyboard()
        )
    elif query.data == 'create_code':
        query.edit_message_text(
            text="*💻 Buat Kode Sederhana*\n\n"
                 "Kirim permintaan Anda dengan format:\n"
                 "`buatkan aku file sederhana python $file`\n\n"
                 "Contoh:\n"
                 "`buatkan aku file sederhana python yang mengecek bilangan prima $file`",
            parse_mode='Markdown'
        )
        return REQUEST_CODE
    elif query.data == 'debug_code':
        query.edit_message_text(
            text="*🐞 Debug Kode*\n\n"
                 "Silakan kirim file yang ingin di-debug beserta pesan error yang Anda dapatkan.\n\n"
                 "Format:\n"
                 "1. Kirim file\n"
                 "2. Reply file tersebut dengan pesan error",
            parse_mode='Markdown'
        )
        return DEBUG_FILE
    elif query.data == 'about':
        query.edit_message_text(
            text="*ℹ️ Tentang Bot*\n\n"
                 "🔹 *Nama Bot:* Canzy-Xtr Downloader\n"
                 "🔹 *Developer:* @Canzy_Xtr\n"
                 "🔹 *Fitur:*\n"
                 "   - Download video YouTube/TikTok\n"
                 "   - Pembuatan kode sederhana\n"
                 "   - Debugging kode\n\n"
                 "⭐ Gunakan bot ini dengan bijak!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Kembali", callback_data='main_menu')]
            ])
        )
    elif query.data == 'admin_menu' and is_admin(query.from_user.id):
        query.edit_message_text(
            text="*👑 Menu Admin*\n\n"
                 "Pilih opsi admin yang tersedia:",
            parse_mode='Markdown',
            reply_markup=admin_menu_keyboard()
        )
    elif query.data == 'main_menu':
        query.edit_message_text(
            text="*✨ Menu Utama ✨*",
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard()
        )
    elif query.data == 'broadcast':
        query.edit_message_text(
            text="*📢 Broadcast Message*\n\n"
                 "Kirim pesan yang ingin disiarkan ke semua user:",
            parse_mode='Markdown'
        )
        return 'broadcast_message'
    elif query.data == 'stats':
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
        active_users = cursor.fetchone()[0]
        
        conn.close()
        
        query.edit_message_text(
            text=f"*📊 Statistik Bot*\n\n"
                 f"🔹 Total User: {total_users}\n"
                 f"🔹 User Aktif: {active_users}\n\n"
                 f"*Terakhir Diupdate:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Kembali", callback_data='admin_menu')]
            ])
        )
    elif query.data in ['youtube', 'tiktok']:
        context.user_data['download_platform'] = query.data
        query.edit_message_text(
            text=f"*📥 Download dari {'YouTube' if query.data == 'youtube' else 'TikTok'}*\n\n"
                 "Silakan kirim URL video yang ingin diunduh:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Kembali", callback_data='download_menu')]
            ])
        )
        return 'get_url'

# Keyboard menu download
def download_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("YouTube", callback_data='youtube'),
            InlineKeyboardButton("TikTok", callback_data='tiktok')
        ],
        [
            InlineKeyboardButton("🔙 Kembali", callback_data='main_menu')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# Keyboard menu admin
def admin_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("📢 Broadcast", callback_data='broadcast'),
            InlineKeyboardButton("📊 Statistik", callback_data='stats')
        ],
        [
            InlineKeyboardButton("🔙 Kembali", callback_data='main_menu')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# Handler untuk mendapatkan URL video
def get_url(update: Update, context: CallbackContext):
    url = update.message.text
    platform = context.user_data.get('download_platform')
    
    if not url:
        update.message.reply_text("URL tidak valid. Silakan coba lagi.")
        return 'get_url'
    
    update.message.reply_text(f"⏳ Memproses {platform} video...")
    
    try:
        if platform == 'youtube':
            download_youtube_video(update, context, url)
        else:
            download_tiktok_video(update, context, url)
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        update.message.reply_text("❌ Gagal mengunduh video. Silakan coba lagi.")
    
    return ConversationHandler.END

# Fungsi untuk mengunduh video YouTube
def download_youtube_video(update: Update, context: CallbackContext, url: str):
    chat_id = update.effective_chat.id
    
    # Opsi yt-dlp untuk YouTube
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': '%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
    }
    
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'video')
            formats = info.get('formats', [])
            
            # Filter format yang tersedia
            available_resolutions = set()
            for f in formats:
                if f.get('height'):
                    available_resolutions.add(f['height'])
            
            if not available_resolutions:
                # Jika tidak ada info resolusi, langsung unduh
                update.message.reply_text("⏳ Mengunduh video...")
                ydl.download([url])
                
                # Cari file yang baru diunduh
                for file in os.listdir():
                    if file.endswith('.mp4') and os.path.isfile(file):
                        with open(file, 'rb') as video_file:
                            context.bot.send_video(
                                chat_id=chat_id,
                                video=InputFile(video_file),
                                caption=f"*{video_title}*\n\n🔹 *Platform:* YouTube\n"
                                        f"🔹 *Unduhan oleh:* @{update.effective_user.username}\n"
                                        "🔹 *Credit:* @Canzy_Xtr",
                                parse_mode='Markdown'
                            )
                        os.remove(file)
                        break
                return
            
            # Jika ada pilihan resolusi, tampilkan menu
            resolutions = sorted(available_resolutions, reverse=True)
            keyboard = []
            
            # Buat tombol resolusi (2 tombol per baris)
            for i in range(0, len(resolutions), 2):
                row = []
                if i < len(resolutions):
                    row.append(InlineKeyboardButton(
                        f"{resolutions[i]}p", 
                        callback_data=f"res_{resolutions[i]}"
                    ))
                if i+1 < len(resolutions):
                    row.append(InlineKeyboardButton(
                        f"{resolutions[i+1]}p", 
                        callback_data=f"res_{resolutions[i+1]}"
                    ))
                if row:
                    keyboard.append(row)
            
            keyboard.append([
                InlineKeyboardButton("🔙 Kembali", callback_data='download_menu')
            ])
            
            context.user_data['youtube_info'] = {
                'url': url,
                'title': video_title
            }
            
            update.message.reply_text(
                f"*📹 {video_title}*\n\nPilih resolusi yang diinginkan:",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            logger.error(f"Error getting YouTube info: {e}")
            update.message.reply_text("❌ Gagal mendapatkan info video. Silakan coba lagi.")

# Handler untuk memilih resolusi YouTube
def choose_resolution(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    resolution = int(query.data.split('_')[1])
    youtube_info = context.user_data.get('youtube_info')
    
    if not youtube_info:
        query.edit_message_text("❌ Session expired. Silakan coba lagi.")
        return
    
    url = youtube_info['url']
    video_title = youtube_info['title']
    chat_id = query.message.chat_id
    
    query.edit_message_text(f"⏳ Mengunduh video {resolution}p...")
    
    try:
        # Opsi untuk resolusi spesifik
        ydl_opts = {
            'format': f'bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]',
            'outtmpl': f'{video_title}.mp4',
            'quiet': True,
            'no_warnings': True,
            'merge_output_format': 'mp4',
        }
        
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
            # Cari file yang baru diunduh
            for file in os.listdir():
                if file.endswith('.mp4') and os.path.isfile(file):
                    with open(file, 'rb') as video_file:
                        context.bot.send_video(
                            chat_id=chat_id,
                            video=InputFile(video_file),
                            caption=f"*{video_title}*\n\n🔹 *Platform:* YouTube\n"
                                    f"🔹 *Resolusi:* {resolution}p\n"
                                    f"🔹 *Unduhan oleh:* @{query.from_user.username}\n"
                                    "🔹 *Credit:* @Canzy_Xtr",
                            parse_mode='Markdown'
                        )
                    os.remove(file)
                    break
    
    except Exception as e:
        logger.error(f"Error downloading YouTube video: {e}")
        query.edit_message_text("❌ Gagal mengunduh video. Silakan coba lagi.")

# Fungsi untuk mengunduh video TikTok
def download_tiktok_video(update: Update, context: CallbackContext, url: str):
    chat_id = update.effective_chat.id
    
    # Opsi yt-dlp untuk TikTok (tanpa watermark)
    ydl_opts = {
        'format': 'download_addr',
        'outtmpl': '%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }
    
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'tiktok_video')
            
            # Unduh video tanpa watermark
            ydl_opts_download = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': f'{video_title}.mp4',
                'quiet': True,
                'no_warnings': True,
            }
            
            with youtube_dl.YoutubeDL(ydl_opts_download) as ydl_download:
                ydl_download.download([url])
                
                # Cari file yang baru diunduh
                for file in os.listdir():
                    if file.endswith('.mp4') and os.path.isfile(file):
                        with open(file, 'rb') as video_file:
                            context.bot.send_video(
                                chat_id=chat_id,
                                video=InputFile(video_file),
                                caption=f"*{video_title}*\n\n🔹 *Platform:* TikTok\n"
                                        f"🔹 *Unduhan oleh:* @{update.effective_user.username}\n"
                                        "🔹 *Credit:* @Canzy_Xtr",
                                parse_mode='Markdown'
                            )
                        os.remove(file)
                        break
        
        except Exception as e:
            logger.error(f"Error downloading TikTok video: {e}")
            update.message.reply_text("❌ Gagal mengunduh video TikTok. Silakan coba lagi.")

# Handler untuk membuat kode
def create_code(update: Update, context: CallbackContext):
    user_request = update.message.text
    
    if not user_request.endswith('$file'):
        update.message.reply_text(
            "Format tidak valid. Gunakan:\n"
            "`buatkan aku file sederhana python $file`\n\n"
            "Contoh:\n"
            "`buatkan aku file sederhana python yang mengecek bilangan prima $file`",
            parse_mode='Markdown'
        )
        return REQUEST_CODE
    
    # Hapus $file dari permintaan
    clean_request = user_request.replace('$file', '').strip()
    
    update.message.reply_text("⏳ Sedang membuat kode...")
    
    try:
        # Gunakan OpenAI untuk membuat kode
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Anda adalah asisten pemrograman yang ahli. Buatkan kode sederhana berdasarkan permintaan user. Hanya berikan kode tanpa penjelasan."},
                {"role": "user", "content": clean_request}
            ],
            max_tokens=1000
        )
        
        code = response.choices[0].message.content
        
        # Tentukan ekstensi file berdasarkan permintaan
        if 'python' in clean_request.lower():
            ext = 'py'
            language = 'Python'
        elif 'javascript' in clean_request.lower():
            ext = 'js'
            language = 'JavaScript'
        elif 'java' in clean_request.lower():
            ext = 'java'
            language = 'Java'
        elif 'html' in clean_request.lower():
            ext = 'html'
            language = 'HTML'
        elif 'css' in clean_request.lower():
            ext = 'css'
            language = 'CSS'
        else:
            ext = 'txt'
            language = 'Text'
        
        # Simpan ke file sementara
        filename = f"code_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
        with open(filename, 'w') as f:
            f.write(code)
        
        # Kirim file
        with open(filename, 'rb') as f:
            update.message.reply_document(
                document=InputFile(f),
                caption=f"*🔹 Bahasa:* {language}\n"
                       f"*🔹 Permintaan:* {clean_request}\n\n"
                       "🔹 *Credit:* @Canzy_Xtr",
                parse_mode='Markdown'
            )
        
        # Hapus file sementara
        os.remove(filename)
    
    except Exception as e:
        logger.error(f"Error creating code: {e}")
        update.message.reply_text("❌ Gagal membuat kode. Silakan coba lagi.")
    
    return ConversationHandler.END

# Handler untuk debugging kode
def debug_code(update: Update, context: CallbackContext):
    # Periksa apakah ini adalah file yang dikirim
    if update.message.document:
        context.user_data['debug_file'] = {
            'file_id': update.message.document.file_id,
            'file_name': update.message.document.file_name
        }
        update.message.reply_text(
            "✅ File diterima. Sekarang reply pesan ini dengan error yang Anda dapatkan.",
            reply_to_message_id=update.message.message_id
        )
        return DEBUG_FILE
    
    # Periksa apakah ini adalah reply ke file dengan pesan error
    elif update.message.reply_to_message and update.message.reply_to_message.document:
        debug_file = context.user_data.get('debug_file')
        if not debug_file:
            update.message.reply_text("❌ Session expired. Silakan mulai lagi.")
            return ConversationHandler.END
        
        error_message = update.message.text
        file_id = update.message.reply_to_message.document.file_id
        
        update.message.reply_text("⏳ Sedang menganalisis dan memperbaiki kode...")
        
        try:
            # Download file
            file = context.bot.get_file(file_id)
            file_path = f"debug_{debug_file['file_name']}"
            file.download(file_path)
            
            # Baca isi file
            with open(file_path, 'r') as f:
                file_content = f.read()
            
            # Kirim ke OpenAI untuk debugging
            prompt = (
                f"File ini memiliki error:\n\n"
                f"Error message: {error_message}\n\n"
                f"Perbaiki kode berikut dan berikan versi yang sudah diperbaiki:\n\n"
                f"{file_content}\n\n"
                "Hanya berikan kode yang sudah diperbaiki tanpa penjelasan."
            )
            
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Anda adalah asisten pemrograman yang ahli dalam debugging kode. Perbaiki kode berdasarkan error message yang diberikan."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000
            )
            
            fixed_code = response.choices[0].message.content
            
            # Simpan kode yang sudah diperbaiki
            fixed_filename = f"fixed_{debug_file['file_name']}"
            with open(fixed_filename, 'w') as f:
                f.write(fixed_code)
            
            # Kirim file yang sudah diperbaiki
            with open(fixed_filename, 'rb') as f:
                update.message.reply_document(
                    document=InputFile(f),
                    caption=f"*🔹 File Asli:* {debug_file['file_name']}\n"
                           f"*🔹 Error:* {error_message}\n\n"
                           "🔹 *Credit:* @Canzy_Xtr",
                    parse_mode='Markdown'
                )
            
            # Hapus file sementara
            os.remove(file_path)
            os.remove(fixed_filename)
            if 'debug_file' in context.user_data:
                del context.user_data['debug_file']
        
        except Exception as e:
            logger.error(f"Error debugging code: {e}")
            update.message.reply_text("❌ Gagal melakukan debugging. Silakan coba lagi.")
        
        return ConversationHandler.END
    
    else:
        update.message.reply_text(
            "Format tidak valid. Silakan:\n"
            "1. Kirim file yang ingin di-debug\n"
            "2. Reply file tersebut dengan pesan error"
        )
        return DEBUG_FILE

# Handler untuk broadcast message
def broadcast_message(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Anda tidak memiliki akses ke fitur ini.")
        return ConversationHandler.END
    
    message = update.message.text
    active_users = get_active_users()
    success = 0
    failed = 0
    
    update.message.reply_text(f"⏳ Mengirim broadcast ke {len(active_users)} user...")
    
    for user_id in active_users:
        try:
            context.bot.send_message(
                chat_id=user_id,
                text=f"*📢 Broadcast Message*\n\n{message}\n\n"
                     "_Pesan ini dikirim ke semua user aktif_",
                parse_mode='Markdown'
            )
            success += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to {user_id}: {e}")
            failed += 1
    
    update.message.reply_text(
        f"✅ Broadcast selesai!\n\n"
        f"🔹 Berhasil dikirim: {success}\n"
        f"🔹 Gagal dikirim: {failed}"
    )
    
    return ConversationHandler.END

# Handler untuk cancel
def cancel(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Aksi dibatalkan.",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

# Handler untuk error
def error(update: Update, context: CallbackContext):
    logger.warning(f'Update "{update}" caused error "{context.error}"')

# Fungsi utama
def main():
    # Inisialisasi database
    init_db()
    
    # Buat updater dan dispatcher
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Tambahkan handler command
    dp.add_handler(CommandHandler('start', start))
    
    # Conversation handler untuk download
    download_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button, pattern='^(youtube|tiktok)$')],
        states={
            'get_url': [MessageHandler(Filters.text & ~Filters.command, get_url)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Conversation handler untuk membuat kode
    code_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button, pattern='^create_code$')],
        states={
            REQUEST_CODE: [MessageHandler(Filters.text & ~Filters.command, create_code)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Conversation handler untuk debugging
    debug_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button, pattern='^debug_code$')],
        states={
            DEBUG_FILE: [
                MessageHandler(Filters.document, debug_code),
                MessageHandler(Filters.text & ~Filters.command, debug_code)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Conversation handler untuk broadcast
    broadcast_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button, pattern='^broadcast$')],
        states={
            'broadcast_message': [MessageHandler(Filters.text & ~Filters.command, broadcast_message)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Tambahkan semua handler
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(CallbackQueryHandler(choose_resolution, pattern='^res_'))
    dp.add_handler(download_conv_handler)
    dp.add_handler(code_conv_handler)
    dp.add_handler(debug_conv_handler)
    dp.add_handler(broadcast_conv_handler)
    
    # Tambahkan handler error
    dp.add_error_handler(error)
    
    # Set command list di menu bot
    bot_commands = [
        BotCommand('start', 'Mulai bot'),
        BotCommand('cancel', 'Batalkan aksi saat ini')
    ]
    updater.bot.set_my_commands(bot_commands)
    
    # Mulai bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()