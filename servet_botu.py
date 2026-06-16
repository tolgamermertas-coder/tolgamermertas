import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import yfinance as yf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import os
from flask import Flask
from threading import Thread

# -------------------------------------------------------------------------
# # 7/24 PREMIUM PRO MULTI-CURRENCY DASHBOARD (V2.2 ALTIN DÜZELTMELİ)
# -------------------------------------------------------------------------

BOT_TOKEN = "8778250529:AAFu08dUsJNiV7YySGB7BFJzT93VmKtdeys"
YETKILI_USER_ID = 7796185729
bot = telebot.TeleBot(BOT_TOKEN)
DB_FILE = "wealth_management.db"

app = Flask('')
@app.route('/')
def home():
    return "Premium Pro Dashboard Kesintisiz Aktif"

# -------------------------------------------------------------------------
# SABİT MALİYETLER VE LOT SAYILARI (KODUN KALBİNE İŞLENEN GERÇEK VERİLER)
# -------------------------------------------------------------------------
FAVORI_VARLIKLAR = {
    "ASELS": {"tip": "HISSE", "ticker": "ASELS.IS", "lot": 756, "maliyet": 116.11},
    "TUPRS": {"tip": "HISSE", "ticker": "TUPRS.IS", "lot": 152, "maliyet": 168.10},
    "ENJSA": {"tip": "HISSE", "ticker": "ENJSA.IS", "lot": 260, "maliyet": 108.60},
    "EREGL": {"tip": "HISSE", "ticker": "EREGL.IS", "lot": 354, "maliyet": 24.64},
    "SISE":  {"tip": "HISSE", "ticker": "SISE.IS",  "lot": 338, "maliyet": 53.76},
    "ALTIN.S1": {"tip": "ALTIN", "ticker": "GC=F",   "lot": 338, "maliyet": 53.76}
}

def guvenlik_kontrolu(user_id):
    return user_id == YETKILI_USER_ID

def veri_tabani_kur():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sabit_varliklar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            varlik_adi TEXT UNIQUE,
            tl_degeri REAL
        )
    ''')
    cursor.execute("INSERT OR IGNORE INTO sabit_varliklar (varlik_adi, tl_degeri) VALUES ('BES', 0.0)")
    conn.commit()
    conn.close()

def canli_fiyat_cek(ticker, tip="HISSE"):
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="1d")
        if not df.empty:
            kapanis = df['Close'].iloc[-1]
            if tip == "ALTIN":
                # Altın S1 Sertifikası için Ons -> Gram -> 0.01 Gram Dönüşüm Formülü
                usd_try = yf.Ticker("TRY=X").history(period="1d")['Close'].iloc[-1]
                gram_altin = (kapanis / 31.1034768) * usd_try
                # Altın S1 darphane sertifikası 0.01 gram altına denk geldiği için 100'e bölüyoruz
                return round(gram_altin / 100, 2)
            return round(kapanis, 2)
    except:
        pass
    return None

def rapor_butonlari_olustur():
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("💵 USD Bazlı Rapor", callback_data="rapor_usd"),
        InlineKeyboardButton("💶 EUR Bazlı Rapor", callback_data="rapor_eur")
    )
    markup.row(InlineKeyboardButton("🎯 BES Değeri Güncelle", callback_data="sabit_guncelle"))
    markup.row(InlineKeyboardButton("🔄 Dashboard Yenile", callback_data="yenile_ana"))
    return markup

@bot.message_handler(commands=['start', 'menu'])
def ana_menu_gonder(message):
    if not guvenlik_kontrolu(message.from_user.id):
        return
    
    msg = bot.send_message(message.chat.id, "🔄 Canlı piyasa verileri çekiliyor ve Altın S1 formülü kalibre ediliyor...")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT tl_degeri FROM sabit_varliklar WHERE varlik_adi='BES'")
    bes_degeri = cursor.fetchone()[0]
    conn.close()
    
    try:
        usd_kur = yf.Ticker("TRY=X").history(period="1d")['Close'].iloc[-1]
        eur_kur = yf.Ticker("EURTRY=X").history(period="1d")['Close'].iloc[-1]
    except:
        usd_kur, eur_kur = 33.0, 36.0

    toplam_borsa_tl = 0
    toplam_maliyet_tl = 0
    rapor_metni = "📊 **PREMIUM PRO KONSOLİDE SERVET RAPORU (TL)**\n\n"
    
    isimler = []
    degerler = []

    for varlik, info in FAVORI_VARLIKLAR.items():
        guncel_fiyat = canli_fiyat_cek(info["ticker"], info["tip"])
        if not guncel_fiyat:
            guncel_fiyat = info["maliyet"]
        
        mevcut_deger = info["lot"] * guncel_fiyat
        toplam_maliyet = info["lot"] * info["maliyet"]
        
        toplam_borsa_tl += mevcut_deger
        toplam_maliyet_tl += toplam_maliyet
        
        kar_zarar_tl = mevcut_deger - toplam_maliyet
        kar_zarar_yuzde = (kar_zarar_tl / toplam_maliyet) * 100 if toplam_maliyet > 0 else 0
        emoji = "🟢" if kar_zarar_tl >= 0 else "🔴"
        isaret = "+" if kar_zarar_tl >= 0 else ""
        
        rapor_metni += f"🔹 **{varlik}**: {info['lot']} Lot\n"
        rapor_metni += f"   Maliyet: {info['maliyet']:.2f} TL | Güncel: {guncel_fiyat:.2f} TL\n"
        rapor_metni += f"   Değer: {mevcut_deger:,.2f} TL | K/Z: {emoji} {isaret}{kar_zarar_yuzde:.2f}%\n\n"
        
        if mevcut_deger > 0:
            isimler.append(varlik)
            degerler.append(mevcut_deger)

    if bes_degeri > 0:
        isimler.append("BES")
        degerler.append(bes_degeri)

    net_servet = toplam_borsa_tl + bes_degeri
    toplam_kar_zarar = toplam_borsa_tl - toplam_maliyet_tl
    toplam_kz_yuzde = (toplam_kar_zarar / toplam_maliyet_tl) * 100 if toplam_maliyet_tl > 0 else 0
    genel_emoji = "🚀" if toplam_kar_zarar >= 0 else "📉"
    genel_isaret = "+" if toplam_kar_zarar >= 0 else ""

    rapor_metni += "────────────────────\n"
    rapor_metni += f"🛡️ **BES Birikimi:** {bes_degeri:,.2f} TL\n"
    rapor_metni += f"💰 **Net Servet Değeri:** {net_servet:,.2f} TL\n"
    rapor_metni += f"{genel_emoji} **Toplam Borsa K/Z Oranı:** {genel_isaret}{toplam_kz_yuzde:.2f}% ({toplam_kar_zarar:,.2f} TL)\n"
    rapor_metni += f"ℹ️ *Dolar: {usd_kur:.2f} TL | Euro: {eur_kur:.2f} TL*"

    bot.delete_message(message.chat.id, msg.message_id)

    if degerler:
        plt.figure(figsize=(6,6))
        plt.pie(degerler, labels=isimler, autopct='%1.1f%%', startangle=140, colors=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b'])
        plt.title("Premium Pro Varlık Dağılımı", fontsize=14, fontweight='bold')
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        plt.close()
        
        bot.send_photo(message.chat.id, buf, caption=rapor_metni, parse_mode="Markdown", reply_markup=rapor_butonlari_olustur())
    else:
        bot.send_message(message.chat.id, rapor_metni, parse_mode="Markdown", reply_markup=rapor_butonlari_olustur())

@bot.callback_query_handler(func=lambda call: True)
def callback_izleyici(call):
    if not guvenlik_kontrolu(call.from_user.id):
        return
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT tl_degeri FROM sabit_varliklar WHERE varlik_adi='BES'")
    bes_degeri = cursor.fetchone()[0]
    conn.close()

    try:
        usd_kur = yf.Ticker("TRY=X").history(period="1d")['Close'].iloc[-1]
        eur_kur = yf.Ticker("EURTRY=X").history(period="1d")['Close'].iloc[-1]
    except:
        usd_kur, eur_kur = 33.0, 36.0

    toplam_borsa_tl = 0
    for varlik, info in FAVORI_VARLIKLAR.items():
        guncel_fiyat = canli_fiyat_cek(info["ticker"], info["tip"]) or info["maliyet"]
        toplam_borsa_tl += info["lot"] * guncel_fiyat
        
    net_servet_tl = toplam_borsa_tl + bes_degeri

    if call.data == "yenile_ana":
        bot.answer_callback_query(call.id, "🔄 Veriler güncelleniyor...")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        ana_menu_gonder(call.message)

    elif call.data == "rapor_usd":
        servet_usd = net_servet_tl / usd_kur
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"💵 **USD BAZLI GÜNCEL SERVETİNİZ**\n\n💰 Toplam Portföy Değeri: **${servet_usd:,.2f}**\n*(Anlık Dolar Kuru: {usd_kur:.2f} TL üzerinden hesaplanmıştır.)*")

    elif call.data == "rapor_eur":
        servet_eur = net_servet_tl / eur_kur
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"€  **EUR BAZLI GÜNCEL SERVETİNİZ**\n\n💰 Toplam Portföy Değeri: **€{servet_eur:,.2f}**\n*(Anlık Euro Kuru: {eur_kur:.2f} TL üzerinden hesaplanmıştır.)*")

    elif call.data == "sabit_guncelle":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "🎯 Lütfen güncel BES toplam TL değerinizi sadece rakam olarak yazıp gönderin:\n(Örn: 125000)")
        bot.register_next_step_handler(msg, sabit_varlik_kaydet)

def sabit_varlik_kaydet(message):
    if not guvenlik_kontrolu(message.from_user.id):
        return
    try:
        yeni_deger = float(message.text.replace(".", "").replace(",", ".").strip())
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE sabit_varliklar SET tl_degeri=? WHERE varlik_adi='BES'", (yeni_deger,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ BES değeriniz başarıyla **{yeni_deger:,.2f} TL** olarak güncellendi! Yeni raporu görmek için /menu yazabilirsiniz.")
    except:
        bot.send_message(message.chat.id, "❌ Hatalı giriş yaptınız. Lütfen sadece rakam yazarak tekrar deneyin.")

def sunucu_calistir():
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    veri_tabani_kur()
    Thread(target=sunucu_calistir).start()
    print("💎 Premium Pro v2.2 Sistemi Aktif, Altın Kalibrasyonu Kuruldu...")
    bot.infinity_polling()
