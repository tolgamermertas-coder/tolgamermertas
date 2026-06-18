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
# # 7/24 PREMIUM ELITE INTERACTIVE DASHBOARD (V3.6 GOLD EDITION)
# -------------------------------------------------------------------------

BOT_TOKEN = "8778250529:AAFu08dUsJNiV7YySGB7BFJzT93VmKtdeys"
YETKILI_USER_ID = 7796185729
bot = telebot.TeleBot(BOT_TOKEN)
DB_FILE = "wealth_management.db"

USER_STATE = {}

app = Flask('')
@app.route('/')
def home():
    return "Premium Elite v3.6 Gold Edition Aktif"

V2_VARLIKLAR = {
    "ASELS": {"tip": "HISSE", "ticker": "ASELS.IS", "lot": 756, "maliyet": 116.11},
    "TUPRS": {"tip": "HISSE", "ticker": "TUPRS.IS", "lot": 152, "maliyet": 168.10},
    "ENJSA": {"tip": "HISSE", "ticker": "ENJSA.IS", "lot": 260, "maliyet": 108.60},
    "EREGL": {"tip": "HISSE", "ticker": "EREGL.IS", "lot": 354, "maliyet": 24.64},
    "SISE":  {"tip": "HISSE", "ticker": "SISE.IS",  "lot": 338, "maliyet": 53.76},
    "ALTIN.S1": {"tip": "ALTIN_BORSASI", "ticker": "GC=F", "lot": 338, "maliyet": 53.76}
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfoy_varliklari (
            varlik_adi TEXT PRIMARY KEY,
            tip TEXT,
            ticker TEXT,
            lot REAL,
            maliyet REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fiziki_altinlar (
            altin_turu TEXT PRIMARY KEY,
            adet REAL
        )
    ''')
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
    
    # Fiziki altın türlerini sıfır adetle ilklendir
    for tur in ["GRAM", "CEYREK", "YARIM", "ATA"]:
        cursor.execute("INSERT OR IGNORE INTO fiziki_altinlar (altin_turu, adet) VALUES (?, 0.0)", (tur,))
    
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

def fiziki_altinlari_getir():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT altin_turu, adet FROM fiziki_altinlar")
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

def canli_fiyat_cek(ticker, tip="HISSE"):
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="1d")
        if not df.empty:
            kapanis = df['Close'].iloc[-1]
            if tip in ["ALTIN", "ALTIN_BORSASI"]:
                usd_try = yf.Ticker("TRY=X").history(period="1d")['Close'].iloc[-1]
                gram_altin = (kapanis / 31.1034768) * usd_try
                if tip == "ALTIN_BORSASI":
                    return round(gram_altin / 100, 2) # ALTIN.S1 borsa kalibrasyonu
                return round(gram_altin, 2) # Saf Gram Altın fiyatı
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
        InlineKeyboardButton("🛒 Aylık Düzenli Alım Ekle", callback_data="sihirbaz_basla"),
        InlineKeyboardButton("🏅 Fiziki Altın Sepetim", callback_data="fiziki_altin_menu")
    )
    markup.row(
        InlineKeyboardButton("🚨 Fiyat Alarmı Kur", callback_data="alarm_kur_menu"),
        InlineKeyboardButton("🎯 Eylül Simülasyonu", callback_data="eylul_simule")
    )
    markup.row(
        InlineKeyboardButton("🔄 Portföy Sıfırla", callback_data="lot_duzenle_menu"),
        InlineKeyboardButton("🛡️ BES Güncelle", callback_data="sabit_guncelle")
    )
    markup.row(
        InlineKeyboardButton("🔄 Dashboard Yenile", callback_data="yenile_ana")
    )
    return markup

@bot.message_handler(commands=['start', 'menu'])
def ana_menu_gonder(message):
    if not guvenlik_kontrolu(message.from_user.id):
        return
    
    msg = bot.send_message(message.chat.id, "🔄 Canlı piyasa ve altın verileri çekiliyor, Dashboard hazırlanıyor...")
    
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

    # Canlı Has Altın Fiyatını Çek (Ons altından hesaplama)
    canli_gram_altin = canli_fiyat_cek("GC=F", "ALTIN") or 2500.0

    toplam_borsa_tl = 0
    toplam_maliyet_tl = 0
    rapor_metni = "👑 **PREMIUM ELITE KONSOLİDE SERVET RAPORU (v3.6)**\n\n"
    
    varliklar = varliklari_getir()
    isimler = []
    degerler = []

    # 1. Borsa ve Altın Sertifikası Hesaplama
    for varlik, info in varliklar.items():
        if info["lot"] <= 0:
            continue
        guncel_fiyat = canli_fiyat_cek(info["ticker"], info["tip"]) or info["maliyet"]
        mevcut_deger = info["lot"] * guncel_fiyat
        
        toplam_borsa_tl += mevcut_deger
        if info["tip"] == "HISSE" or varlik == "ALTIN.S1":
            toplam_maliyet_tl += (info["lot"] * info["maliyet"])
        
        kar_zarar_tl = mevcut_deger - (info["lot"] * info["maliyet"])
        kar_zarar_yuzde = (kar_zarar_tl / (info["lot"] * info["maliyet"])) * 100 if info["maliyet"] > 0 else 0
        emoji = "🟢" if kar_zarar_tl >= 0 else "🔴"
        isaret = "+" if kar_zarar_tl >= 0 else ""
        
        rapor_metni += f"🔹 **{varlik}**: {info['lot']:.2f} Lot\n"
        rapor_metni += f"   Maliyet: {info['maliyet']:.2f} TL | Güncel: {guncel_fiyat:.2f} TL\n"
        rapor_metni += f"   Değer: {mevcut_deger:,.2f} TL | K/Z: {emoji} {isaret}{kar_zarar_yuzde:.2f}%\n\n"
        
        isimler.append(varlik)
        degerler.append(mevcut_deger)

    # 2. Fiziki Altın Sepeti Hesaplama
    f_altinlar = fiziki_altinlari_getir()
    toplam_fiziki_altin_tl = 0
    fiziki_detay = ""
    
    carpanlar = {"GRAM": 1.0, "CEYREK": 1.605, "YARIM": 3.21, "ATA": 6.61}
    tur_isimleri = {"GRAM": "Gram Altın", "CEYREK": "Çeyrek Altın", "YARIM": "Yarım Altın", "ATA": "Ata Altın"}
    
    for tur, adet in f_altinlar.items():
        if adet > 0:
            tl_degeri = adet * carpanlar[tur] * canli_gram_altin
            toplam_fiziki_altin_tl += tl_degeri
            fiziki_detay += f"   • {adet:.0f} Adet {tur_isimleri[tur]}: {tl_degeri:,.2f} TL\n"
            
    if toplam_fiziki_altin_tl > 0:
        rapor_metni += f"🏅 **Fiziki Altın Varlığı:** {toplam_fiziki_altin_tl:,.2f} TL\n{fiziki_detay}\n"
        isimler.append("Fiziki Altın")
        degerler.append(toplam_fiziki_altin_tl)

    if bes_degeri > 0:
        isimler.append("BES")
        degerler.append(bes_degeri)

    net_servet = toplam_borsa_tl + toplam_fiziki_altin_tl + bes_degeri
    toplam_kar_zarar = toplam_borsa_tl - toplam_maliyet_tl
    toplam_kz_yuzde = (toplam_kar_zarar / toplam_maliyet_tl) * 100 if toplam_maliyet_tl > 0 else 0
    genel_emoji = "🚀" if toplam_kar_zarar >= 0 else "📉"
    genel_isaret = "+" if toplam_kar_zarar >= 0 else ""

    rapor_metni += "────────────────────\n"
    rapor_metni += f"🛡️ **BES Birikimi:** {bes_degeri:,.2f} TL\n"
    rapor_metni += f"💰 **Net Servet Değeri:** {net_servet:,.2f} TL\n"
    rapor_metni += f"{genel_emoji} **Toplam Borsa K/Z Oranı:** {genel_isaret}{toplam_kz_yuzde:.2f}% ({toplam_kar_zarar:,.2f} TL)\n"
    rapor_metni += f"ℹ️ *Has Altın/Gr: {canli_gram_altin:.2f} TL | Dolar: {usd_kur:.2f} TL*"

    bot.delete_message(message.chat.id, msg.message_id)

    if degerler:
        plt.figure(figsize=(6,6))
        plt.pie(degerler, labels=isimler, autopct='%1.1f%%', startangle=140)
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

    canli_gram_altin = canli_fiyat_cek("GC=F", "ALTIN") or 2500.0

    varliklar = varliklari_getir()
    toplam_borsa_tl = 0
    for varlik, info in varliklar.items():
        guncel_fiyat = canli_fiyat_cek(info["ticker"], info["tip"]) or info["maliyet"]
        toplam_borsa_tl += info["lot"] * guncel_fiyat

    f_altinlar = fiziki_altinlari_getir()
    toplam_fiziki_altin_tl = 0
    carpanlar = {"GRAM": 1.0, "CEYREK": 1.605, "YARIM": 3.21, "ATA": 6.61}
    for tur, adet in f_altinlar.items():
        toplam_fiziki_altin_tl += adet * carpanlar[tur] * canli_gram_altin

    net_servet_tl = toplam_borsa_tl + toplam_fiziki_altin_tl + bes_degeri

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
        msg = bot.send_message(call.message.chat.id, "🔄 **PORTFÖYÜ SIFIRLAMA / YENİDEN YAZMA**\n\n`HİSSE LOT MALİYET`\n*(Örn: ASELS 756 116.11)*")
        bot.register_next_step_handler(msg, dinamik_lot_kaydet)

    elif call.data == "alarm_kur_menu":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "🚨 **FİYAT ALARMI KURMA**\n\n`HİSSE FİYAT`\n*(Örn: TUPRS 185)*")
        bot.register_next_step_handler(msg, alarm_kaydet)

    elif call.data == "eylul_simule":
        bot.answer_callback_query(call.id)
        sim_muhafazakar = net_servet_tl * 1.15
        sim_iyimser = net_servet_tl * 1.30
        sim_metni = "🎯 **EYLÜL SONU PORTFÖY DURUMU TAHMİN SİMÜLASYONU**\n\n"
        sim_metni += f"💼 Mevcut Net Servetiniz: **{net_servet_tl:,.2f} TL**\n\n"
        sim_metni += f"📉 **Muhafazakar Senaryo (+%15):**\n   Tahmini Değer: `{sim_muhafazakar:,.2f} TL`\n\n"
        sim_metni += f"🚀 **İyimser / Boğa Senaryosu (+%30):**\n   Tahmini Değer: `{sim_iyimser:,.2f} TL`\n\n"
        bot.send_message(call.message.chat.id, sim_metni, parse_mode="Markdown")

    # ---- INTERAKTIF BORSA ALIM SİHİRBAZI ----
    elif call.data == "sihirbaz_basla":
        bot.answer_callback_query(call.id)
        markup = InlineKeyboardMarkup()
        for v_name in varliklar.keys():
            markup.add(InlineKeyboardButton(f"🔹 {v_name}", callback_data=f"sel_var_{v_name}"))
        markup.add(InlineKeyboardButton("➕ Yeni BIST Hissesi Ekle", callback_data="sel_var_NEW_STOCK"))
        bot.send_message(call.message.chat.id, "🛒 **Premium Alım Sihirbazı**\n\nHangi varlığa alım eklemesi yaptınız?", reply_markup=markup)

    elif call.data.startswith("sel_var_"):
        bot.answer_callback_query(call.id)
        secilen = call.data.replace("sel_var_", "")
        if secilen == "NEW_STOCK":
            msg = bot.send_message(call.message.chat.id, "📝 Lütfen eklemek istediğiniz yeni hissenin kodunu yazın (Örn: THYAO):")
            bot.register_next_step_handler(msg, yeni_stok_adi_al)
        else:
            USER_STATE[call.from_user.id] = {"hisse": secilen}
            msg = bot.send_message(call.message.chat.id, f"📦 **{secilen}** için kaç lot aldınız? Sadece rakam girin:")
            bot.register_next_step_handler(msg, sihirbaz_lot_al)

    # ---- INTERAKTIF FIZIKI ALTIN MENÜSÜ ----
    elif call.data == "fiziki_altin_menu":
        bot.answer_callback_query(call.id)
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("🏅 Gram Altın", callback_data="set_gold_GRAM"), InlineKeyboardButton("🪙 Çeyrek Altın", callback_data="set_gold_CEYREK"))
        markup.row(InlineKeyboardButton("🌗 Yarım Altın", callback_data="set_gold_YARIM"), InlineKeyboardButton("👑 Ata Altın", callback_data="set_gold_ATA"))
        bot.send_message(call.message.chat.id, "🏅 **Fiziki Altın Güncelleme Paneli**\n\nHangi altın türünün toplam adetini düzenlemek istiyorsunuz? Lütfen seçin:", reply_markup=markup)

    elif call.data.startswith("set_gold_"):
        bot.answer_callback_query(call.id)
        tur = call.data.replace("set_gold_", "")
        USER_STATE[call.from_user.id] = {"altin_turu": tur}
        tur_isimler = {"GRAM": "Gram Altın (Toplam Gram)", "CEYREK": "Çeyrek Altın (Toplam Adet)", "YARIM": "Yarım Altın (Toplam Adet)", "ATA": "Ata Altın (Toplam Adet)"}
        msg = bot.send_message(call.message.chat.id, f"📝 Elinizdeki güncel toplam **{tur_isimler[tur]}** miktarını yazın:\n*(Not: Eski adet silinecek ve yazdığınız yeni adet kaydedilecektir)*")
        bot.register_next_step_handler(msg, fiziki_altin_kaydet)

def fiziki_altin_kaydet(message):
    try:
        uid = message.from_user.id
        yeni_adet = float(message.text.strip())
        tur = USER_STATE[uid]["altin_turu"]
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE fiziki_altinlar SET adet=? WHERE altin_turu=?", (yeni_adet, tur))
        conn.commit()
        conn.close()
        
        USER_STATE.pop(uid, None)
        tur_isimler = {"GRAM": "Gram Altın", "CEYREK": "Çeyrek Altın", "YARIM": "Yarım Altın", "ATA": "Ata Altın"}
        bot.send_message(message.chat.id, f"✅ **Altın Sepeti Güncellendi!**\n\n🏅 Tür: {tur_isimler[tur]}\n📊 Yeni Toplam Miktar: **{yeni_adet:.2f}**\n\nDashboard'u görmek için /menu yazabilirsiniz.")
    except:
        bot.send_message(message.chat.id, "❌ Hatalı adet girişi. Lütfen sadece rakam girin.")

def yeni_stok_adi_al(message):
    hisse_adi = message.text.strip().upper()
    USER_STATE[message.from_user.id] = {"hisse": hisse_adi, "is_new": True}
    msg = bot.send_message(message.chat.id, f"📦 Yeni eklenen **{hisse_adi}** için kaç lot aldınız?")
    bot.register_next_step_handler(msg, sihirbaz_lot_al)

def sihirbaz_lot_al(message):
    try:
        lot = float(message.text.strip())
        uid = message.from_user.id
        USER_STATE[uid]["lot"] = lot
        h_adi = USER_STATE[uid]["hisse"]
        msg = bot.send_message(message.chat.id, f"💵 **{h_adi}** için lot başına alım fiyatınız (TL):")
        bot.register_next_step_handler(msg, sihirbaz_fiyat_ve_kaydet)
    except:
        bot.send_message(message.chat.id, "❌ Hatalı giriş. Lütfen sadece rakam yazın.")

def sihirbaz_fiyat_ve_kaydet(message):
    try:
        uid = message.from_user.id
        fiyat = float(message.text.strip())
        hisse = USER_STATE[uid]["hisse"]
        eklenen_lot = USER_STATE[uid]["lot"]
        
        varliklar = varliklari_getir()
        
        if hisse in varliklar and "is_new" not in USER_STATE[uid]:
            eski_lot = varliklar[hisse]["lot"]
            eski_maliyet = varliklar[hisse]["maliyet"]
            toplam_lot = eski_lot + eklenen_lot
            yeni_maliyet = ((eski_lot * eski_maliyet) + (eklenen_lot * fiyat)) / toplam_lot
            ticker_str = varliklar[hisse]["ticker"]
            tip_str = varliklar[hisse]["tip"]
        else:
            toplam_lot = eklenen_lot
            yeni_maliyet = fiyat
            tip_str = "ALTIN_BORSASI" if "ALTIN" in hisse else "HISSE"
            ticker_str = "GC=F" if tip_str == "ALTIN_BORSASI" else f"{hisse}.IS"

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO portfoy_varliklari (varlik_adi, tip, ticker, lot, maliyet)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(varlik_adi) DO UPDATE SET lot=excluded.lot, maliyet=excluded.maliyet
        ''', (hisse, tip_str, ticker_str, toplam_lot, yeni_maliyet))
        conn.commit()
        conn.close()
        
        USER_STATE.pop(uid, None)
        bot.send_message(message.chat.id, f"✅ **Alım Kaydedildi!**\n\n🔹 Varlık: {hisse}\n📦 Yeni Toplam: **{toplam_lot:.2f} Lot**\n🧮 Yeni Maliyet: **{yeni_maliyet:.2f} TL**")
    except:
        bot.send_message(message.chat.id, "❌ Giriş hatası oluştu.")

def dinamik_lot_kaydet(message):
    try:
        parcalar = message.text.strip().split()
        v_adi = parcalar[0].upper()
        yeni_lot = float(parcalar[1])
        yeni_maliyet = float(parcalar[2])
        
        varliklar = varliklari_getir()
        tip_str = varliklar[v_adi]["tip"] if v_adi in varliklar else "HISSE"
        ticker_str = varliklar[v_adi]["ticker"] if v_adi in varliklar else f"{v_adi}.IS"

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO portfoy_varliklari (varlik_adi, tip, ticker, lot, maliyet)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(varlik_adi) DO UPDATE SET lot=excluded.lot, maliyet=excluded.maliyet
        ''', (v_adi, tip_str, ticker_str, yeni_lot, yeni_maliyet))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ **{v_adi}** güncellendi!")
    except:
        bot.send_message(message.chat.id, "❌ Hatalı biçim.")

def alarm_kaydet(message):
    try:
        parcalar = message.text.strip().split()
        v_adi = parcalar[0].upper()
        hedef = float(parcalar[1])
        
        varliklar = varliklari_getir()
        if v_adi not in varliklar:
            bot.send_message(message.chat.id, "❌ Varlık bulunamadı.")
            return
            
        guncel = canli_fiyat_cek(varliklar[v_adi]["ticker"], varliklar[v_adi]["tip"]) or varliklar[v_adi]["maliyet"]
        yon = "YUKARI" if hedef > guncel else "ASAGI"
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO alarmlar (varlik_adi, hedef_fiyat, yon) VALUES (?, ?, ?)", (v_adi, hedef, yon))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"🚨 Alarm kuruldu!")
    except:
        bot.send_message(message.chat.id, "❌ Hatalı biçim.")

def sabit_varlik_kaydet(message):
    try:
        yeni_deger = float(message.text.replace(".", "").replace(",", ".").strip())
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE sabit_varliklar SET tl_degeri=? WHERE varlik_adi='BES'", (yeni_deger,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ BES güncellendi.")
    except:
        bot.send_message(message.chat.id, "❌ Geçersiz rakam.")

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
                            if yon == "YUKARI" and guncel >= target:
                                tetiklendi = True
                            elif yon == "ASAGI" and guncel <= target:
                                tetiklendi = True
                                
                            if tetiklendi:
                                bot.send_message(YETKILI_USER_ID, f"🚨🔔 **{v_adi}** hedefiniz ({hedef:.2f} TL) kırıldı!")
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
    print("👑 Premium Elite v3.6 Gold Edition Yayında...")
    bot.infinity_polling()
