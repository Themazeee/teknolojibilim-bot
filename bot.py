import os, time, hashlib, sqlite3, logging
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta
import feedparser
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode

# --- Ayarlar ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
INTERVAL_MINUTES = int(os.getenv("INTERVAL_MINUTES", "20"))

FEEDS = [
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://www.theverge.com/rss/index.xml",
    "https://www.wired.com/feed/rss",
    "https://www.sciencealert.com/feed",
    "https://www.nasa.gov/news-release/feed/",
    "https://www.popsci.com/arcio/rss/",
    "https://www.techradar.com/feeds/articletype/news",
    "https://feeds.feedburner.com/TechCrunch/",
    "https://www.space.com/feeds/all",
    "https://interestingengineering.com/rss",
    "https://www.livescience.com/feeds/all"
]


KEYWORDS_ANY = [
    "AI","yapay zeka","artificial intelligence","bilim","science","uzay","space",
    "roket","SpaceX","NASA","kuantum","quantum","oyun","game","Steam","PlayStation",
    "Nvidia","AMD","Intel","Android","iOS","robot","keşif","discovery","buluş","gelişme"
]

# --- Veritabanı (tekrarları önleme) ---
conn = sqlite3.connect("news.db")
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS sent (
    id TEXT PRIMARY KEY,
    link TEXT,
    published TEXT
)""")
conn.commit()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

def allowed(entry):
    title = entry.get("title", "").lower()
    summary = BeautifulSoup(entry.get("summary", "") or "", "html.parser").get_text().lower()
    return any(k.lower() in title or k.lower() in summary for k in KEYWORDS_ANY)

def already_sent(uid):
    c.execute("SELECT 1 FROM sent WHERE id=?", (uid,))
    return c.fetchone() is not None

def mark_sent(uid, link, published):
    c.execute("INSERT OR IGNORE INTO sent (id, link, published) VALUES (?, ?, ?)", (uid, link, published))
    conn.commit()

def uid_from(entry):
    base = entry.get("id") or entry.get("link") or entry.get("title", "")
    return hashlib.sha256(base.encode("utf-8")).hexdigest()

def fmt_message(title, link, source, published=None):
    msg = f"📰 <b>{title}</b>\n🌍 {source}"
    if published:
        msg += f" | 🕒 {published}"
    msg += f"\n🔗 {link}"
    return msg

async def send(bot, text):
    await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.HTML, disable_web_page_preview=False)

async def run_once(bot):
    total_sent = 0
    for f in FEEDS:
        try:
            feed = feedparser.parse(f)
            source = urlparse(f).netloc.replace("www.", "")
            for e in feed.entries[:10]:
                uid = uid_from(e)
                if already_sent(uid):
                    continue
                if not allowed(e):
                    continue
                title = e.get("title", "")
                link = e.get("link", "")
                published = None
                if e.get("published_parsed"):
                    dt = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
                    published = dt.astimezone(timezone(timedelta(hours=3))).strftime("%d.%m.%Y %H:%M")
                msg = fmt_message(title, link, source, published)
                await send(bot, msg)
                mark_sent(uid, link, published or "")
                total_sent += 1
        except Exception as ex:
            logging.error(f"Hata: {ex}")
    logging.info(f"Gönderilen haber sayısı: {total_sent}")

if __name__ == "__main__":
    import asyncio
    bot = Bot(BOT_TOKEN)
    print("🔧 Bot aktif. Haber taraması başlıyor…")
    async def main():
        while True:
            await run_once(bot)
            await asyncio.sleep(INTERVAL_MINUTES * 60)
    asyncio.run(main())
