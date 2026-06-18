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
# # 7/24 PREMIUM ELITE INTERACTIVE DASHBOARD (V3.7 GLOBAL VAULT EDITION)
# -------------------------------------------------------------------------

BOT_TOKEN = "8778250529:AAFu08dUsJNiV7YySGB7BFJzT93VmKtdeys"
YETKILI_USER_ID = 7796185729
bot = telebot.TeleBot(BOT_TOKEN)
DB_FILE = "wealth_management.db"

USER_STATE = {}

app = Flask('')
@app.route('/')
def home():
    return "Premium Elite v3.7 Global Vault Yayında"

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
        CREATE TABLE IF NOT EXISTS doviz_kasasi (
            doviz_turu TEXT PRIMARY KEY,
            miktar REAL
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
    
    for tur in ["GRAM", "CEYREK", "YARIM", "ATA"]:
        cursor.execute("INSERT OR IGNORE INTO fiziki_altinlar (altin_turu, adet) VALUES (?, 0.0)", (tur,))
        
    for doviz in ["USD", "EUR"]:
        cursor.execute("INSERT OR IGNORE INTO doviz_kasasi (doviz_turu, miktar) VALUES (?, 0.0)", (doviz,))
    
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
    return {row[0]: {"tip": row[1], "ticker": row[2], "lot": row[3], "maliyet": row[4]} for row in rows}

def fiziki_altinlari_getir():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT altin_turu, adet FROM fiziki_altinlar")
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

def doviz_kasasini_getir():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT doviz_turu, miktar FROM doviz_kasasi")
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

def canli_fiyat_cek(ticker, tip="HISSE"):
    if ticker == "GC=F" and tip == "ALTIN_BORSASI":
        return 64.00
        
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="1d")
        if not df.empty:
            kapanis = df['Close'].iloc[-1]
            if tip in ["ALTIN", "ALTIN_BORSASI"]:
                usd_try = yf.Ticker("TRY=X").history(period="1d")['Close'].iloc[-1]
                gram_altin = (kapanis / 31.1034768) * usd_try
                return round(gram_altin, 2)
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
        InlineKeyboardButton("🛒 Aylık Hisse Ekle", callback_data="sihirbaz_basla"),
        InlineKeyboardButton("🏅 Fiziki Altın Sepetim", callback_data="fiziki_altin_menu")
    )
    markup.row(
        InlineKeyboardButton("💵 Döviz Kasasını Güncelle", callback_data="doviz_kasasi_menu"),
        InlineKeyboardButton("🚨 Fiyat Alarmı Kur", callback_data="alarm_kur_menu")
    )
    markup.row(
        InlineKeyboardButton("🎯 Eylül Simülasyonu", callback_data="eylul_simule"),
        InlineKeyboardButton("🛡️ BES Güncelle", callback_data="sabit_guncelle")
    )
    markup.row(InlineKeyboardButton("🔄 Dashboard Yenile", callback_data="yenile_ana"))
    return markup

@bot.message_handler(commands=['start', 'menu'])
def ana_menu_gonder(message):
    if not guvenlik_kontrolu(message.from_user.id):
        return
    
    msg = bot.send_message(message.chat.id, "🔄 Canlı piyasa verileri, altın ve döviz kurları çekiliyor...")
    
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

    toplam_borsa_tl = 0
    toplam_maliyet_tl = 0
    rapor_metni = "👑 **PREMIUM ELITE GLOBAL DASHBOARD (v3.7)**\n\n"
    
    varliklar = varliklari_getir()
    isimler = []
    degerler = []

    # 1. Hisse ve Borsa Altını
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

    # 2. Fiziki Altın Sepeti
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

    # 3. Nakit Döviz Kasası
    kasa = doviz_kasasini_getir()
    toplam_doviz_tl = 0
    doviz_detay = ""
    
    if kasa["USD"] > 0:
        usd_tl_karislik = kasa["USD"] * usd_kur
        toplam_doviz_tl += usd_tl_karislik
        doviz_detay += f"   • {kasa['USD']:,.2f} USD: {usd_tl_karislik:,.2f} TL\n"
    if kasa["EUR"] > 0:
        eur_tl_karislik = kasa["EUR"] * eur_kur
        toplam_doviz_tl += eur_tl_karislik
        doviz_detay += f"   • {kasa['EUR']:,.2f} EUR: {eur_tl_karislik:,.2f} TL\n"
        
    if toplam_doviz_tl > 0:
        rapor_metni += f"💵 **Nakit Döviz Kasası:** {toplam_doviz_tl:,.2f} TL\n{doviz_detay}\n"
        if kasa["USD"] > 0:
            isimler.append("Nakit USD")
            degerler.append(kasa["USD"] * usd_kur)
        if kasa["EUR"] > 0:
            isimler.append("Nakit EUR")
            degerler.append(kasa["EUR"] * eur_kur)

    if bes_degeri > 0:
        isimler.append("BES")
        degerler.append(bes_degeri)

    net_servet = toplam_borsa_tl + toplam_fiziki_altin_tl + toplam_doviz_tl + bes_degeri
    toplam_kar_zarar = toplam_borsa_tl - toplam_maliyet_tl
    toplam_kz_yuzde = (toplam_kar_zarar / toplam_maliyet_tl) * 100 if toplam_maliyet_tl > 0 else 0
    genel_emoji = "🚀" if toplam_kar_zarar >= 0 else "📉"
    genel_isaret = "+" if toplam_kar_zarar >= 0 else ""

    rapor_metni += "────────────────────\n"
    rapor_metni += f"🛡️ **BES Birikimi:** {bes_degeri:,.2f} TL\n"
    rapor_metni += f"💰 **Net Servet Değeri:** {net_servet:,.2f} TL\n"
    rapor_metni += f"{genel_emoji} **Toplam Borsa K/Z Oranı:** {genel_isaret}{toplam_kz_yuzde:.2f}% ({toplam_kar_zarar:,.2f} TL)\n"
    rapor_metni += f"ℹ️ *Ounces Altın: {canli_gram_altin:.2f} TL | USD: {usd_kur:.2f} TL | EUR: {eur_kur:.2f} TL*"

    bot.delete_message(message.chat.id, msg.message_id)

    if degerler:
        plt.figure(figsize=(6,6))
        plt.pie(degerler, labels=isimler, autopct='%1.1f%%', startangle=140)
        plt.title("Premium Elite Küresel Varlık Dağılımı", fontsize=14, fontweight='bold')
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

    kasa = doviz_kasasini_getir()
    toplam_doviz_tl = (kasa["USD"] * usd_kur) + (kasa["EUR"] * eur_kur)

    net_servet_tl = toplam_borsa_tl + toplam_fiziki_altin_tl + toplam_doviz_tl + bes_degeri

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

    elif call.data == "fiziki_altin_menu":
        bot.answer_callback_query(call.id)
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("🏅 Gram Altın", callback_data="set_gold_GRAM"), InlineKeyboardButton("🪙 Çeyrek Altın", callback_data="set_gold_CEYREK"))
        markup.row(InlineKeyboardButton("🌗 Yarım Altın", callback_data="set_gold_YARIM"), InlineKeyboardButton("👑 Ata Altın", callback_data="set_gold_ATA"))
        bot.send_message(call.message.chat.id, "🏅 **Fiziki Altın Güncelleme Paneli**\n\nHangi altın türünün toplam adetini düzenlemek istiyorsunuz?", reply_markup=markup)

    elif call.data.startswith("set_gold_"):
        bot.answer_callback_query(call.id)
        tur = call.data.replace("set_gold_", "")
        USER_STATE[call.from_user.id] = {"altin_turu": tur}
        tur_isimler = {"GRAM": "Gram Altın", "CEYREK": "Çeyrek Altın", "YARIM": "Yarım Altın", "ATA": "Ata Altın"}
        msg = bot.send_message(call.message.chat.id, f"📝 Elinizdeki güncel toplam **{tur_isimler[tur]}** miktarını sadece rakam olarak yazın:")
        bot.register_next_step_handler(msg, fiziki_altin_kaydet)

    # ---- DÖVİZ KASASI ADIMLARI ----
    elif call.data == "doviz_kasasi_menu":
        bot.answer_callback_query(call.id)
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("💵 Nakit Dolar (USD)", callback_data="set_curr_USD"), InlineKeyboardButton("💶 Nakit Euro (EUR)", callback_data="set_curr_EUR"))
        bot.send_message(call.message.chat.id, "💵 **Küresel Nakit Kasası Yönetimi**\n\nHangi döviz kasanızı güncellemek istiyorsunuz?", reply_markup=markup)

    elif call.data.startswith("set_curr_"):
        bot.answer_callback_query(call.id)
        curr = call.data.replace("set_curr_", "")
        USER_STATE[call.from_user.id] = {"doviz_turu": curr}
        msg = bot.send_message(call.message.chat.id, f"📝 Kasada duran güncel toplam **{curr}** miktarınızı sadece rakam olarak yazıp gönderin:")
        bot.register_next_step_handler(msg, doviz_kasasi_kaydet)

def doviz_kasasi_kaydet(message):
    try:
        uid = message.from_user.id
        miktar = float(message.text.strip())
        doviz = USER_STATE[uid]["doviz_turu"]
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE doviz_kasasi SET miktar=? WHERE doviz_turu=?", (miktar, doviz))
        conn.commit()
        conn.close()
        
        USER_STATE.pop(uid, None)
        bot.send_message(message.chat.id, f"✅ **Kasa Güncellendi!**\n\n💵 Döviz: {doviz}\n📊 Yeni Toplam Nakit: **{miktar:,.2f} {doviz}**\n\nDashboard için /menu yazabilirsiniz.")
    except:
        bot.send_message(message.chat.id, "❌ Hatalı giriş. Lütfen sadece rakam yazın.")

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
        bot.send_message(message.chat.id, f"✅ Altın başarıyla güncellendi.")
    except:
        bot.send_message(message.chat.id, "❌ Sadece rakam girin.")

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
        bot.send_message(message.chat.id, "❌ Rakam giriniz.")

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
        bot.send_message(message.chat.id, f"✅ Alım Kaydedildi!")
    except:
        bot.send_message(message.chat.id, "❌ Hata oluştu.")

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
        bot.send_message(message.chat.id, f"✅ Güncelleniyor...")
    except:
        bot.send_message(message.chat.id, "❌ Hata.")

def alarm_kaydet(message):
    try:
        parcalar = message.text.strip().split()
        v_adi = parcalar[0].upper()
        hedef = float(parcalar[1])
        varliklar = varliklari_getir()
        if v_adi not in varliklar: return
        guncel = canli_fiyat_cek(varliklar[v_adi]["ticker"], varliklar[v_adi]["tip"]) or varliklar[v_adi]["maliyet"]
        yon = "YUKARI" if hedef > guncel else "ASAGI"
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO alarmlar (varlik_adi, hedef_fiyat, yon) VALUES (?, ?, ?)", (v_adi, hedef, yon))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"🚨 Alarm devrede.")
    except: pass

def sabit_varlik_kaydet(message):
    try:
        yeni_deger = float(message.text.replace(".", "").replace(",", ".").strip())
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE sabit_varliklar SET tl_degeri=? WHERE varlik_adi='BES'", (yeni_deger,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ BES Güncellendi.")
    except: pass

def alarm_kontrol_dongusu():
    while True:
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT id, varlik_adi, gateway_fiyat, yon FROM alarmlar WHERE aktif=1")
            # Değişken kalibrasyonu
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
                            if yon == "YUKARI" and guncel >= hedef: tetiklendi = True
                            elif yon == "ASAGI" and guncel <= hedef: tetiklendi = True
                            if tetiklendi:
                                bot.send_message(YETKILI_USER_ID, f"🚨🔔 **{v_adi}** hedefiniz ({hedef:.2f} TL) kırıldı!")
                                cursor.execute("UPDATE alarmlar SET aktif=0 WHERE id=?", (al_id,))
            conn.commit()
            conn.close()
        except: pass
        time.sleep(60)

def sunucu_calistir():
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    veri_tabani_kur()
    Thread(target=sunucu_calistir).start()
    Thread(target=alarm_kontrol_dongusu).start()
    print("👑 Premium Elite v3.7 Global Vault Yayında...")
    bot.infinity_polling()
