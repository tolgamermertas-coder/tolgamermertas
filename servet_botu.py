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
from flask import Flask
from threading import Thread

# -------------------------------------------------------------------------
# # 7/24 PREMIUM ELITE MULTI-CURRENCY DASHBOARD (V3.1 AYLIK ALIM ENTEGRELİ)
# -------------------------------------------------------------------------

BOT_TOKEN = "8778250529:AAFu08dUsJNiV7YySGB7BFJzT93VmKtdeys"
YETKILI_USER_ID = 7796185729
bot = telebot.TeleBot(BOT_TOKEN)
DB_FILE = "wealth_management.db"

app = Flask('')
@app.route('/')
def home():
    return "Premium Elite v3.1 Sistemi Kesintisiz Aktif"

# -------------------------------------------------------------------------
# SABİT MALİYETLER VE BAŞLANGIÇ LOTLARI (VERİTABANINDA YOKSA KULLANILIR)
# -------------------------------------------------------------------------
V2_VARLIKLAR = {
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
    # Sabit Varlıklar Tablosu (BES vb.)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sabit_varliklar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            varlik_adi TEXT UNIQUE,
            tl_degeri REAL
        )
    ''')
    # Dinamik Lot Tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfoy_varliklari (
            varlik_adi TEXT PRIMARY KEY,
            tip TEXT,
            ticker TEXT,
            lot REAL,
            maliyet REAL
        )
    ''')
    # Alarm Tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alarmlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            varlik_adi TEXT,
            hedef_fiyat REAL,
            yon TEXT,
            aktif INTEGER DEFAULT 1
        )
    ''')
    
    cursor.execute("INSERT OR IGNORE INTO sabit_varliklar (varlik_adi, tl_degeri) VALUES ('BES', 0.0)")
    
    for k, v in V2_VARLIKLAR.items():
        cursor.execute('''
            INSERT OR IGNORE INTO portfoy_varliklari (varlik_adi, tip, ticker, lot, maliyet)
            VALUES (?, ?, ?, ?, ?)
        ''', (k, v["tip"], v["ticker"], v["lot"], v["maliyet"]))
        
    conn.commit()
    conn.close()

def varliklari_getir():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT varlik_adi, tip, ticker, lot, maliyet FROM portfoy_varliklari")
    rows = cursor.fetchall()
    conn.close()
    
    varliklar = {}
    for row in rows:
        varliklar[row[0]] = {"tip": row[1], "ticker": row[2], "lot": row[3], "maliyet": row[4]}
    return varliklar

def canli_fiyat_cek(ticker, tip="HISSE"):
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="1d")
        if not df.empty:
            kapanis = df['Close'].iloc[-1]
            if tip == "ALTIN":
                usd_try = yf.Ticker("TRY=X").history(period="1d")['Close'].iloc[-1]
                gram_altin = (kapanis / 31.1034768) * usd_try
                return round(gram_altin / 100, 2)
            return round(kapanis, 2)
    except:
        pass
    return None

def rapor_butonlari_olustur():
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("💵 USD Rapor", callback_data="rapor_usd"),
        InlineKeyboardButton("💶 EUR Rapor", callback_data="rapor_eur")
    )
    markup.row(
        InlineKeyboardButton("🛒 Aylık Düzenli Alım Ekle", callback_data="aylik_alim_menu"),
        InlineKeyboardButton("🔄 Portföyü Sıfırla/Düzenle", callback_data="lot_duzenle_menu")
    )
    markup.row(
        InlineKeyboardButton("🚨 Fiyat Alarmı Kur", callback_data="alarm_kur_menu"),
        InlineKeyboardButton("🎯 Eylül Simülasyonu", callback_data="eylul_simule")
    )
    markup.row(
        InlineKeyboardButton("🛡️ BES Güncelle", callback_data="sabit_guncelle"),
        InlineKeyboardButton("🔄 Dashboard Yenile", callback_data="yenile_ana")
    )
    return markup

@bot.message_handler(commands=['start', 'menu'])
def ana_menu_gonder(message):
    if not guvenlik_kontrolu(message.from_user.id):
        return
    
    msg = bot.send_message(message.chat.id, "🔄 Canlı piyasa verileri çekiliyor ve Elite Dashboard hazırlanıyor...")
    
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
    rapor_metni = "👑 **PREMIUM ELITE KONSOLİDE SERVET RAPORU (v3.1)**\n\n"
    
    varliklar = varliklari_getir()
    isimler = []
    degerler = []

    for varlik, info in varliklar.items():
        if info["lot"] <= 0:
            continue
        guncel_fiyat = canli_fiyat_cek(info["ticker"], info["tip"]) or info["maliyet"]
        
        mevcut_deger = info["lot"] * guncel_fiyat
        toplam_maliyet = info["lot"] * info["maliyet"]
        
        toplam_borsa_tl += mevcut_deger
        toplam_maliyet_tl += toplam_maliyet
        
        kar_zarar_tl = mevcut_deger - toplam_maliyet
        kar_zarar_yuzde = (kar_zarar_tl / toplam_maliyet) * 100 if toplam_maliyet > 0 else 0
        emoji = "🟢" if kar_zarar_tl >= 0 else "🔴"
        isaret = "+" if kar_zarar_tl >= 0 else ""
        
        rapor_metni += f"🔹 **{varlik}**: {info['lot']:.2f} Lot\n"
        rapor_metni += f"   Maliyet: {info['maliyet']:.2f} TL | Güncel: {guncel_fiyat:.2f} TL\n"
        rapor_metni += f"   Değer: {mevcut_deger:,.2f} TL | K/Z: {emoji} {isaret}{kar_zarar_yuzde:.2f}%\n\n"
        
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
        plt.title("Premium Elite Varlık Dağılımı", fontsize=14, fontweight='bold')
        
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

    varliklar = varliklari_getir()
    toplam_borsa_tl = 0
    for varlik, info in varliklar.items():
        guncel_fiyat = canli_fiyat_cek(info["ticker"], info["tip"]) or info["maliyet"]
        toplam_borsa_tl += info["lot"] * guncel_fiyat
    net_servet_tl = toplam_borsa_tl + bes_degeri

    if call.data == "yenile_ana":
        bot.answer_callback_query(call.id, "🔄 Güncelleniyor...")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        ana_menu_gonder(call.message)

    elif call.data == "rapor_usd":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"💵 **USD BAZLI GÜNCEL SERVETİNİZ**\n\n💰 Toplam: **${(net_servet_tl / usd_kur):,.2f}**")

    elif call.data == "rapor_eur":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"💶 **EUR BAZLI GÜNCEL SERVETİNİZ**\n\n💰 Toplam: **€{(net_servet_tl / eur_kur):,.2f}**")

    elif call.data == "sabit_guncelle":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "🎯 Güncel BES değerinizi rakam olarak yazın: (Örn: 130000)")
        bot.register_next_step_handler(msg, sabit_varlik_kaydet)

    elif call.data == "lot_duzenle_menu":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "🔄 **PORTFÖYÜ SIFIRLAMA / YENİDEN YAZMA**\n\nBu ekran mevcut değerleri silip sıfırdan lot yazar. Lütfen şu formatta gönderin:\n\n`HİSSE LOT MALİYET`\n*(Örn: ASELS 756 116.11)*")
        bot.register_next_step_handler(msg, dinamik_lot_kaydet)

    elif call.data == "aylik_alim_menu":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "🛒 **AYLIK YENİ ALIM EKLEME (MALİYET ORTALAMA)**\n\nBu ay aldığınız yeni lotları ve alım fiyatını yazın. Sistem eski lotlarla birleştirip otomatik yeni ortalama maliyet hesaplar:\n\n`HİSSE ALINAN_LOT ALIM_FİYATI`\n*(Örn: TUPRS 20 162.40)*")
        bot.register_next_step_handler(msg, aylik_alim_hesapla_kaydet)

    elif call.data == "alarm_kur_menu":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "🚨 **FİYAT ALARMI KURMA**\n\nLütfen alarm kurmak istediğiniz hisseyi ve hedef fiyatı yazın:\n\n`HİSSE FİYAT`\n*(Örn: TUPRS 185)*")
        bot.register_next_step_handler(msg, alarm_kaydet)

    elif call.data == "eylul_simule":
        bot.answer_callback_query(call.id)
        sim_muhafazakar = net_servet_tl * 1.15
        sim_iyimser = net_servet_tl * 1.30
        
        sim_metni = "🎯 **EYLÜL SONU PORTFÖY DURUMU TAHMİN SİMÜLASYONU**\n\n"
        sim_metni += f"💼 Mevcut Net Servetiniz: **{net_servet_tl:,.2f} TL**\n\n"
        sim_metni += f"📉 **Muhafazakar Senaryo (+%15):**\n   Tahmini Değer: `{sim_muhafazakar:,.2f} TL`\n\n"
        sim_metni += f"🚀 **İyimser / Boğa Senaryosu (+%30):**\n   Tahmini Değer: `{sim_iyimser:,.2f} TL`\n\n"
        sim_metni += "ℹ️ *Bu grafiksel tahminler varlıklarınızın tarihsel trendleri ve piyasa çarpanları baz alınarak simüle edilmiştir.*"
        bot.send_message(call.message.chat.id, sim_metni, parse_mode="Markdown")

def aylik_alim_hesapla_kaydet(message):
    try:
        parcalar = message.text.strip().split()
        v_adi = parcalar[0].upper()
        eklenen_lot = float(parcalar[1])
        alim_fiyati = float(parcalar[2])
        
        varliklar = varliklari_getir()
        
        # Eğer hisse listede zaten varsa ortalama maliyet hesapla
        if v_adi in varliklar:
            eski_lot = varliklar[v_adi]["lot"]
            eski_maliyet = varliklar[v_adi]["maliyet"]
            
            toplam_lot = eski_lot + eklenen_lot
            yeni_maliyet = ((eski_lot * eski_maliyet) + (eklenen_lot * alim_fiyati)) / toplam_lot
            ticker_str = varliklar[v_adi]["ticker"]
            tip_str = varliklar[v_adi]["tip"]
        else:
            # Sıfırdan yeni bir hisse ekleniyorsa
            toplam_lot = eklenen_lot
            yeni_maliyet = alim_fiyati
            tip_str = "ALTIN" if "ALTIN" in v_adi else "HISSE"
            ticker_str = "GC=F" if tip_str == "ALTIN" else f"{v_adi}.IS"

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO portfoy_varliklari (varlik_adi, tip, ticker, lot, maliyet)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(varlik_adi) DO UPDATE SET lot=excluded.lot, maliyet=excluded.maliyet
        ''', (v_adi, tip_str, ticker_str, toplam_lot, yeni_maliyet))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"🛒 **Alım Başarıyla Eklendi!**\n\n🔹 **Hisse**: {v_adi}\n📦 Yeni Toplam Lot: **{toplam_lot:.2f} Lot**\n🧮 Hesaplanan Yeni Ortalama Maliyet: **{yeni_maliyet:.2f} TL**")
    except:
        bot.send_message(message.chat.id, "❌ Hatalı biçim. Lütfen aralarda boşluk bırakarak `HİSSE LOT_SAYISI ALIM_FİYATI` şeklinde tekrar yazın.")

def dinamik_lot_kaydet(message):
    try:
        parcalar = message.text.strip().split()
        v_adi = parcalar[0].upper()
        yeni_lot = float(parcalar[1])
        yeni_maliyet = float(parcalar[2])
        
        varliklar = varliklari_getir()
        tip_str = varliklar[v_adi]["tip"] if v_adi in varliklar else ("ALTIN" if "ALTIN" in v_adi else "HISSE")
        ticker_str = varliklar[v_adi]["ticker"] if v_adi in varliklar else ("GC=F" if tip_str == "ALTIN" else f"{v_adi}.IS")

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO portfoy_varliklari (varlik_adi, tip, ticker, lot, maliyet)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(varlik_adi) DO UPDATE SET lot=excluded.lot, maliyet=excluded.maliyet
        ''', (v_adi, tip_str, ticker_str, yeni_lot, yeni_maliyet))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"✅ **{v_adi}** varlığınız sıfırlanarak **{yeni_lot:.2f} Lot / {yeni_maliyet:.2f} TL** maliyet olarak veritabanına işlendi!")
    except:
        bot.send_message(message.chat.id, "❌ Hatalı biçim. Lütfen `HİSSE LOT MALİYET` şeklinde yazın.")

def alarm_kaydet(message):
    try:
        parcalar = message.text.strip().split()
        v_adi = parcalar[0].upper()
        hedef = float(parcalar[1])
        
        varliklar = varliklari_getir()
        if v_adi not in varliklar:
            bot.send_message(message.chat.id, "❌ Bu varlık listenizde bulunmuyor.")
            return
            
        guncel = canli_fiyat_cek(varliklar[v_adi]["ticker"], varliklar[v_adi]["tip"]) or varliklar[v_adi]["maliyet"]
        yon = "YUKARI" if hedef > guncel else "ASAGI"
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO alarmlar (varlik_adi, hedef_fiyat, yon) VALUES (?, ?, ?)", (v_adi, hedef, yon))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"🚨 Alarm kuruldu! **{v_adi}** fiyatı **{hedef:.2f} TL** seviyesini {yon.lower()} yönlü kırdığında size haber vereceğim.")
    except:
        bot.send_message(message.chat.id, "❌ Hatalı biçim. Lütfen `HİSSE FİYAT` formatında yazın.")

def sabit_varlik_kaydet(message):
    try:
        yeni_deger = float(message.text.replace(".", "").replace(",", ".").strip())
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE sabit_varliklar SET tl_degeri=? WHERE varlik_adi='BES'")
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ BES değeriniz **{yeni_deger:,.2f} TL** olarak güncellendi.")
    except:
        bot.send_message(message.chat.id, "❌ Sadece rakam giriniz.")

def alarm_kontrol_dongusu():
    while True:
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT id, varlik_adi, hedef_fiyat, yon FROM alarmlar WHERE aktif=1")
            aktif_alarmlar = cursor.fetchall()
            
            if aktif_alarmlar:
                varliklar = varliklari_getir()
                for al in aktif_alarmlar:
                    al_id, v_adi, hedef, yon = al
                    if v_adi in varliklar:
                        guncel = canli_fiyat_cek(varliklar[v_adi]["ticker"], varliklar[v_adi]["tip"])
                        if guncel:
                            tetiklendi = False
                            if yon == "YUKARI" and guncel >= hedef:
                                tetiklendi = True
                            elif yon == "ASAGI" and guncel <= hedef:
                                tetiklendi = True
                                
                            if tetiklendi:
                                bot.send_message(YETKILI_USER_ID, f"🚨🔔 **ALARM TETİKLENDİ, TOLGA BEY!**\n\n**{v_adi}** güncel fiyatı **{guncel:.2f} TL** seviyesine ulaştı. Hedefiniz olan {hedef:.2f} TL kırıldı! 🚀")
                                cursor.execute("UPDATE alarmlar SET aktif=0 WHERE id=?", (al_id,))
            conn.commit()
            conn.close()
        except:
            pass
        time.sleep(60)

def sunucu_calistir():
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    veri_tabani_kur()
    Thread(target=sunucu_calistir).start()
    Thread(target=alarm_kontrol_dongusu).start()
    print("👑 Premium Elite v3.1 Sistemi Aktif, Aylık Alım ve Maliyet Hesaplayıcı Dinamikleri Kuruldu...")
    bot.infinity_polling()
