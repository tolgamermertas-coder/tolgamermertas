import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import yfinance as yf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import os
import time
import logging
import re
from flask import Flask
from threading import Thread

# -------------------------------------------------------------------------
# # 7/24 GRAND VAULT DASHBOARD (USTA İŞİ DENETLENMİŞ SÜRÜM)
# -------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("grand_vault.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("GrandVault")

# Kütüphanenin doğrudan okuyacağı zorunlu standart isim ve orijinal token
BOT_TOKEN = "8561394116:AAF9ygCDxUyxriEObsv_WhbOviTjiU2F1a4"
YETKILI_USER_ID = 7796185729
DB_FILE = "wealth_management.db"

bot = telebot.TeleBot(BOT_TOKEN)
USER_STATE = {}
app = Flask('')

@app.route('/')
def home():
    return "Grand Vault System Online"

V2_VARLIKLAR = {
    "ASELS": {"tip": "HISSE", "ticker": "ASELS.IS", "lot": 756, "maliyet": 116.11, "logo": "🛡️ 𝗔𝗦𝗘𝗟𝗦"},
    "TUPRS": {"tip": "HISSE", "ticker": "TUPRS.IS", "lot": 152, "maliyet": 168.10, "logo": "🛢️ 𝗧𝗨𝗣𝗥𝗦"},
    "ENJSA": {"tip": "HISSE", "ticker": "ENJSA.IS", "lot": 260, "maliyet": 108.60, "logo": "⚡ 𝗘𝗡𝗝𝗦𝗔"},
    "EREGL": {"tip": "HISSE", "ticker": "EREGL.IS", "lot": 354, "maliyet": 24.64,  "logo": "🏗️ 𝗘𝗥𝗘𝗚𝗟"},
    "SISE":  {"tip": "HISSE", "ticker": "SISE.IS",  "lot": 338, "maliyet": 53.76,  "logo": "🥛 𝗦𝗜𝗦𝗘"},
    "ALTIN.S1": {"tip": "ALTIN_BORSASI", "ticker": "GC=F", "lot": 338, "maliyet": 53.76, "logo": "📜 𝗔verify𝗟𝗧𝗜𝗡.𝗦𝟭"},
    "GRAM_ALTIN": {"tip": "FIZIKI_ALTIN", "ticker": "GC=F", "lot": 0, "maliyet": 0, "logo": "📀 Gram Altin"},
    "CEYREK_ALTIN": {"tip": "FIZIKI_ALTIN", "ticker": "GC=F", "lot": 0, "maliyet": 0, "logo": "🪙 Ceyrek Altin"},
    "YARIM_ALTIN": {"tip": "FIZIKI_ALTIN", "ticker": "GC=F", "lot": 0, "maliyet": 0, "logo": "🌗 Yarim Altin"},
    "ATA_ALTIN": {"tip": "FIZIKI_ALTIN", "ticker": "GC=F", "lot": 0, "maliyet": 0, "logo": "👑 Ata Altin"}
}

def guvenlik_kontrolu(user_id):
    return True

def get_db_connection():
    return sqlite3.connect(DB_FILE, timeout=15.0)

def veri_tabani_kur():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS sabit_varliklar (id INTEGER PRIMARY KEY AUTOINCREMENT, varlik_adi TEXT UNIQUE, tl_degeri REAL)')
        cursor.execute('CREATE TABLE IF NOT EXISTS portfoy_varliklari (varlik_adi TEXT PRIMARY KEY, tip TEXT, ticker TEXT, lot REAL, maliyet REAL)')
        cursor.execute('CREATE TABLE IF NOT EXISTS doviz_kasasi (doviz_turu TEXT PRIMARY KEY, miktar REAL)')
        cursor.execute('CREATE TABLE IF NOT EXISTS alarmlar (id INTEGER PRIMARY KEY AUTOINCREMENT, varlik_adi TEXT, hedef_fiyat REAL, yon TEXT, aktif INTEGER DEFAULT 1)')
        
        cursor.execute("INSERT OR IGNORE INTO sabit_varliklar (varlik_adi, tl_degeri) VALUES ('BES', 0.0)")
        for d in ["USD", "EUR"]:
            cursor.execute("INSERT OR IGNORE INTO doviz_kasasi (doviz_turu, miktar) VALUES (?, 0.0)", (d,))
        for k, v in V2_VARLIKLAR.items():
            cursor.execute('INSERT OR IGNORE INTO portfoy_varliklari (varlik_adi, tip, ticker, lot, maliyet) VALUES (?, ?, ?, ?, ?)', (k, v["tip"], v["ticker"], v["lot"], v["maliyet"]))
        conn.commit()
    except Exception as e:
        logger.error(f"DB Kurulum Hatası: {e}")
    finally: conn.close()

def varliklari_getir():
    veri_tabani_kur()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT varlik_adi, tip, ticker, lot, maliyet FROM portfoy_varliklari")
        rows = cursor.fetchall()
        return {row[0]: {"tip": row[1], "ticker": row[2], "lot": row[3], "maliyet": row[4]} for row in rows}
    except: return {}
    finally: conn.close()

def doviz_kasasini_getir():
    veri_tabani_kur()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT doviz_turu, miktar FROM doviz_kasasi")
        rows = cursor.fetchall()
        return {row[0]: row[1] for row in rows}
    except: return {"USD": 0.0, "EUR": 0.0}
    finally: conn.close()

def canli_fiyat_cek(ticker, tip="HISSE", varlik_adi=""):
    if varlik_adi == "ALTIN.S1":
        return 64.25
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="1d")
        if not df.empty:
            kapanis = df['Close'].iloc[-1]
            if tip in ["ALTIN", "ALTIN_BORSASI", "FIZIKI_ALTIN"]:
                usd_try = 34.30
                try:
                    usd_df = yf.Ticker("TRY=X").history(period="1d")
                    if not usd_df.empty: usd_try = usd_df['Close'].iloc[-1]
                except: pass
                gram_altin = (kapanis / 31.1034768) * usd_try
                if varlik_adi == "GRAM_ALTIN": return round(gram_altin, 2)
                elif varlik_adi == "CEYREK_ALTIN": return round(gram_altin * 1.605, 2)
                elif varlik_adi == "YARIM_ALTIN": return round(gram_altin * 3.21, 2)
                elif varlik_adi == "ATA_ALTIN": return round(gram_altin * 6.61, 2)
                return round(gram_altin, 2)
            return round(kapanis, 2)
    except: pass
    return None

def rapor_butonlari_olustur():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("💵 USD Rapor", callback_data="rapor_usd"), InlineKeyboardButton("💶 EUR Rapor", callback_data="rapor_eur"))
    markup.row(InlineKeyboardButton("🛒 Aylık Alım Ekle", callback_data="sihirbaz_basla"), InlineKeyboardButton("💵 Döviz Kasasını Düzenle", callback_data="doviz_kasasi_menu"))
    markup.row(InlineKeyboardButton("🚨 Fiyat Alarmı Kur", callback_data="alarm_kur_menu"), InlineKeyboardButton("🎯 Eylül Simülasyonu", callback_data="eylul_simule"))
    markup.row(InlineKeyboardButton("🔄 Portföy Sıfırla/Düzenle", callback_data="lot_duzenle_menu"), InlineKeyboardButton("🛡️ BES Güncelle", callback_data="sabit_guncelle"))
    markup.row(InlineKeyboardButton("📦 Veritabanı Yedeği", callback_data="veritabanı_yedekle"), InlineKeyboardButton("🔄 Dashboard Yenile", callback_data="yenile_ana"))
    return markup

@bot.message_handler(commands=['start', 'menu'])
def ana_menu_gonder(message):
    msg = bot.send_message(message.chat.id, "🏛️ Global Piyasalar Verisi Çekiliyor...")
    conn = get_db_connection()
    bes_degeri = 0.0
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT tl_degeri FROM sabit_varliklar WHERE varlik_adi='BES'")
        row = cursor.fetchone()
        if row: bes_degeri = row[0]
    except: pass
    finally: conn.close()
        
    usd_kur, eur_kur = 34.30, 36.80
    try:
        u_df = yf.Ticker("TRY=X").history(period="1d")
        if not u_df.empty: usd_kur = u_df['Close'].iloc[-1]
        e_df = yf.Ticker("EURTRY=X").history(period="1d")
        if not e_df.empty: eur_kur = e_df['Close'].iloc[-1]
    except: pass

    canli_gram_altin = canli_fiyat_cek("GC=F", "ALTIN", "GRAM_ALTIN") or 2520.0
    hisse_metni = "🏛️ **BORSA İSTANBUL (BIST) DASHBOARD**\n────────────────────\n"
    altin_metni = "\n✨ **DARPHANE & ALTIN SEPETİ DASHBOARD**\n────────────────────\n"
    toplam_hisse_tl, toplam_altin_tl, toplam_maliyet_tl = 0, 0, 0
    varliklar = varliklari_getir()
    isimler, degerler = [], []

    for varlik, info in varliklar.items():
        if info["lot"] <= 0: continue
        guncel_fiyat = canli_fiyat_cek(info["ticker"], info["tip"], varlik) or info["maliyet"]
        mevcut_deger = info["lot"] * guncel_fiyat
        toplam_maliyet = info["lot"] * info["maliyet"]
        kar_zarar_tl = mevcut_deger - toplam_maliyet
        kar_zarar_yuzde = (kar_zarar_tl / toplam_maliyet) * 100 if toplam_maliyet > 0 else 0
        emoji = "🟢" if kar_zarar_tl >= 0 else "🔴"
        isaret = "+" if kar_zarar_tl >= 0 else ""
        logo_adi = V2_VARLIKLAR[varlik]["logo"] if varlik in V2_VARLIKLAR else f"🔹 {varlik}"
        unit = "Adet" if info["tip"] == "FIZIKI_ALTIN" else "Lot"
        
        line = f"{logo_adi}\n   📊 {info['lot']:.2f} {unit} | Mlyt: {info['maliyet']:.2f} TL\n   💵 Güncel: {guncel_fiyat:.2f} TL | Değer: {mevcut_deger:,.2f} TL\n   📈 Getiri: {emoji} {isaret}{kar_zarar_yuzde:.2f}%\n\n"
        
        if info["tip"] == "HISSE":
            hisse_metni += line
            toplam_hisse_tl += mevcut_deger
            toplam_maliyet_tl += toplam_maliyet
        else:
            altin_metni += line
            toplam_altin_tl += mevcut_deger
            if varlik == "ALTIN.S1": toplam_maliyet_tl += toplam_maliyet
        isimler.append(varlik)
        degerler.append(mevcut_deger)

    hisse_metni += f"🏢 **HİSSE SENEDİ PORTFÖY TOPLAMI: {toplam_hisse_tl:,.2f} TL**\n"
    altin_metni += f"📀 **ALTIN SEPETİ TOPLAMI: {toplam_altin_tl:,.2f} TL**\n"

    kasa = doviz_kasasini_getir()
    toplam_doviz_tl = (kasa.get("USD", 0) * usd_kur) + (kasa.get("EUR", 0) * eur_kur)
    doviz_metni = "\n💵 **GLOBAL NAKİT VAULT (DÖVİZ KASASI)**\n────────────────────\n"
    if kasa.get("USD", 0) > 0:
        doviz_metni += f"   🇺🇸 Dolar Kasası: {kasa['USD']:,.2f} USD ➔ **{kasa['USD']*usd_kur:,.2f} TL**\n"
        isimler.append("Nakit USD")
        degerler.append(kasa["USD"] * usd_kur)
    if kasa.get("EUR", 0) > 0:
        doviz_metni += f"   🇪🇺 Euro Kasası: {kasa['EUR']:,.2f} EUR ➔ **{kasa['EUR']*eur_kur:,.2f} TL**\n"
        isimler.append("Nakit EUR")
        degerler.append(kasa["EUR"] * eur_kur)

    net_servet = toplam_hisse_tl + toplam_altin_tl + toplam_doviz_tl + bes_degeri
    toplam_borsa_kz = (toplam_hisse_tl + (varliklar.get("ALTIN.S1", {}).get("lot", 0) * (canli_fiyat_cek("GC=F", "ALTIN_BORSASI", "ALTIN.S1") or 64.25))) - toplam_maliyet_tl
    toplam_kz_yuzde = (toplam_borsa_kz / toplam_maliyet_tl) * 100 if toplam_maliyet_tl > 0 else 0
    genel_emoji = "🚀" if toplam_borsa_kz >= 0 else "📉"

    nihai_rapor = hisse_metni + altin_metni + doviz_metni
    nihai_rapor += "👑 ==============================\n"
    nihai_rapor += f"🛡️ **Bireysel Emeklilik (BES):** {bes_degeri:,.2f} TL\n"
    nihai_rapor += f"💎 **BÜTÜN SERVETİMİN TOPLAMI:** {net_servet:,.2f} TL\n"
    nihai_rapor += f"{genel_emoji} **BIST Net K/Z Oranı:** {toplam_kz_yuzde:+.2f}% ({toplam_borsa_kz:,.2f} TL)\n"
    nihai_rapor += f"ℹ️ *USD: {usd_kur:.2f} TL | EUR: {eur_kur:.2f} TL | Has Altın/Gr: {canli_gram_altin:.2f} TL*"

    try: bot.delete_message(message.chat.id, msg.message_id)
    except: pass

    if degerler:
        try:
            plt.figure(figsize=(6,6))
            temiz_isimler = [n.replace("🛡️ ", "").replace("🛢️ ", "").replace("⚡ ", "").replace("🏗️ ", "").replace("🥛 ", "").replace("📜 ", "").replace("𝗔𝗦𝗘𝗟𝗦","ASELS").replace("𝗧𝗨𝗣𝗥𝗦","TUPRS").replace("𝗘𝗡𝗝𝗦Ａ","ENJSA").replace("𝗘𝗥𝗘𝗚𝗟","EREGL").replace("𝗦𝗜𝗦𝗘","SISE") for n in isimler]
            plt.pie(degerler, labels=temiz_isimler, autopct='%1.1f%%', startangle=140)
            plt.title("GRAND VAULT GLOBAL VARLIK DAGILIMI", fontsize=11, fontweight='bold')
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            plt.close()
            bot.send_photo(message.chat.id, buf, caption=nihai_rapor, parse_mode="Markdown", reply_markup=rapor_butonlari_olustur())
        except:
            bot.send_message(message.chat.id, nihai_rapor, parse_mode="Markdown", reply_markup=rapor_butonlari_olustur())
    else:
        bot.send_message(message.chat.id, nihai_rapor, parse_mode="Markdown", reply_markup=rapor_butonlari_olustur())

@bot.message_handler(commands=['yedek', 'backup'])
def veritabanini_yedekle_komut(message):
    veritabanini_yedekle(message.chat.id)

def veritabanini_yedekle(chat_id):
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'rb') as f:
                bot.send_document(
