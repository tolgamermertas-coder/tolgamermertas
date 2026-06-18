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
# # 7/24 PREMIUM GRAND VAULT DASHBOARD (V4.0 - NİHAİ KUSURSUZ GÖRSEL DEVRİM)
# -------------------------------------------------------------------------

BOT_TOKEN = "8778250529:AAFu08dUsJNiV7YySGB7BFJzT93VmKtdeys"
YETKILI_USER_ID = 7796185729
bot = telebot.TeleBot(BOT_TOKEN)
DB_FILE = "wealth_management.db"

USER_STATE = {}

app = Flask('')
@app.route('/')
def home():
    return "Grand Vault v4.0 Ultimate Aktif"

# Başlangıç Varlıkları Kalibrasyonu
V2_VARLIKLAR = {
    "ASELS": {"tip": "HISSE", "ticker": "ASELS.IS", "lot": 756, "maliyet": 116.11, "logo": "🛡️ 𝗔𝗦𝗘𝗟𝗦"},
    "TUPRS": {"tip": "HISSE", "ticker": "TUPRS.IS", "lot": 152, "maliyet": 168.10, "logo": "🛢️ 𝗧𝗨𝗣𝗥𝗦"},
    "ENJSA": {"tip": "HISSE", "ticker": "ENJSA.IS", "lot": 260, "maliyet": 108.60, "logo": "⚡ 𝗘𝗡𝗝𝗦𝗔"},
    "EREGL": {"tip": "HISSE", "ticker": "EREGL.IS", "lot": 354, "maliyet": 24.64,  "logo": "🏗️ 𝗘𝗥𝗘𝗚𝗟"},
    "SISE":  {"tip": "HISSE", "ticker": "SISE.IS",  "lot": 338, "maliyet": 53.76,  "logo": "🥛 𝗦𝗜𝗦𝗘"},
    "ALTIN.S1": {"tip": "ALTIN_BORSASI", "ticker": "GC=F", "lot": 338, "maliyet": 53.76, "logo": "📜 𝗔𝗟𝗧𝗜𝗡.𝗦𝟭"},
    "GRAM_ALTIN": {"tip": "FIZIKI_ALTIN", "ticker": "GC=F", "lot": 0, "maliyet": 0, "logo": "📀 𝗚𝗿𝗮𝗺 𝗔𝗹𝘁ı𝗻"},
    "CEYREK_ALTIN": {"tip": "FIZIKI_ALTIN", "ticker": "GC=F", "lot": 0, "maliyet": 0, "logo": "🪙 𝗖̧𝗲𝘆𝗿𝗲𝗸 𝗔𝗹𝘁ı𝗻"},
    "YARIM_ALTIN": {"tip": "FIZIKI_ALTIN", "ticker": "GC=F", "lot": 0, "maliyet": 0, "logo": "🌗 𝗬𝗮𝗿ı𝗺 𝗔𝗹𝘁ı𝗻"},
    "ATA_ALTIN": {"tip": "FIZIKI_ALTIN", "ticker": "GC=F", "lot": 0, "maliyet": 0, "logo": "👑 𝗔𝘁𝗮 𝗔𝗹𝘁ı𝗻"}
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

def doviz_kasasini_getir():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT doviz_turu, miktar FROM doviz_kasasi")
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

def canli_fiyat_cek(ticker, tip="HISSE", varlik_adi=""):
    if varlik_adi == "ALTIN.S1":
        return 64.00
        
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="1d")
        if not df.empty:
            kapanis = df['Close'].iloc[-1]
            if tip in ["ALTIN", "ALTIN_BORSASI", "FIZIKI_ALTIN"]:
                usd_try = yf.Ticker("TRY=X").history(period="1d")['Close'].iloc[-1]
                gram_altin = (kapanis / 31.1034768) * usd_try
                
                if varlik_adi == "GRAM_ALTIN": return round(gram_altin, 2)
                elif varlik_adi == "CEYREK_ALTIN": return round(gram_altin * 1.605, 2)
                elif varlik_adi == "YARIM_ALTIN": return round(gram_altin * 3.21, 2)
                elif varlik_adi == "ATA_ALTIN": return round(gram_altin * 6.61, 2)
                
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
        InlineKeyboardButton("🛒 Aylık Alım Ekle (Hisse/Altın)", callback_data="sihirbaz_basla"),
        InlineKeyboardButton("💵 Döviz Kasasını Güncelle", callback_data="doviz_kasasi_menu")
    )
    markup.row(
        InlineKeyboardButton("🚨 Fiyat Alarmı Kur", callback_data="alarm_kur_menu"),
        InlineKeyboardButton("🎯 Eylül Simülasyonu", callback_data="eylul_simule")
    )
    markup.row(
        InlineKeyboardButton("🔄 Portföy Sıfırla/Düzenle", callback_data="lot_duzenle_menu"),
        InlineKeyboardButton("🛡️ BES Güncelle", callback_data="sabit_guncelle")
    )
    markup.row(InlineKeyboardButton("🔄 Dashboard Ekranını Yenile", callback_data="yenile_ana"))
    return markup

@bot.message_handler(commands=['start', 'menu'])
def ana_menu_gonder(message):
    if not guvenlik_kontrolu(message.from_user.id):
        return
    
    msg = bot.send_message(message.chat.id, "🏢 Borsa İstanbul (BIST) ve Darphane verileri çekiliyor, Grand Vault v4.0 Konsolu hazırlanıyor...")
    
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
    
    hisse_metni = "🏛️ **BORSA İSTANBUL (BIST) DASHBOARD**\n"
    hisse_metni += "────────────────────\n"
    altin_metni = "✨ **DARPHANE & ALTIN SERVETİ DASHBOARD**\n"
    altin_metni += "────────────────────\n"
    
    toplam_hisse_tl = 0
    toplam_altin_tl = 0
    toplam_maliyet_tl = 0
    
    isimler = []
    degerler = []

    for varlik, info in varliklar.items():
        if info["lot"] <= 0:
            continue
            
        guncel_fiyat = canli_fiyat_cek(info["ticker"], info["tip"], varlik) or info["maliyet"]
        mevcut_deger = info["lot"] * guncel_fiyat
        toplam_maliyet = info["lot"] * info["maliyet"]
        
        kar_zarar_tl = mevcut_deger - toplam_maliyet
        kar_zarar_yuzde = (kar_zarar_tl / toplam_maliyet) * 100 if toplam_maliyet > 0 else 0
        emoji = "🟢" if kar_zarar_tl >= 0 else "🔴"
        isaret = "+" if kar_zarar_tl >= 0 else ""
        
        logo_adi = V2_VARLIKLAR[varlik]["logo"] if varlik in V2_VARLIKLAR else f"🔹 {varlik}"
        unit = "Adet" if info["tip"] == "FIZIKI_ALTIN" else "Lot"
        
        line = f"{logo_adi}\n"
        line += f"   📊 {info['lot']:.2f} {unit} | Mlyt: {info['maliyet']:.2f} TL\n"
        line += f"   💵 Güncel: {guncel_fiyat:.2f} TL | Değer: {mevcut_deger:,.2f} TL\n"
        line += f"   📈 Getiri: {emoji} {isaret}{kar_zarar_yuzde:.2f}%\n\n"
        
        if info["tip"] == "HISSE":
            hisse_metni += line
            toplam_hisse_tl += mevcut_deger
            toplam_maliyet_tl += toplam_maliyet
        else:
            altin_metni += line
            toplam_altin_tl += mevcut_deger
            if varlik == "ALTIN.S1":
                toplam_maliyet_tl += toplam_maliyet

        isimler.append(varlik)
        degerler.append(mevcut_deger)

    hisse_metni += f"🏛️ **HİSSE SENEDİ ALT TOPLAMI: {toplam_hisse_tl:,.2f} TL**\n\n"
    altin_metni += f"👑 **ALTIN VARLIKLARI ALT TOPLAMI: {toplam_altin_tl:,.2f} TL**\n\n"

    # Nakit Döviz Kasası Bölümü
    kasa = doviz_kasasini_getir()
    toplam_doviz_tl = 0
    doviz_metni = "💵 **GLOBAL NAKİT VAULT (DÖVİZ KASASI)**\n"
    doviz_metni += "────────────────────\n"
    
    if kasa["USD"] > 0:
        usd_tl = kasa["USD"] * usd_kur
        toplam_doviz_tl += usd_tl
        doviz_metni += f"   🇺🇸 Dolar Kasası: {kasa['USD']:,.2f} USD ➔ **{usd_tl:,.2f} TL**\n"
        isimler.append("Nakit USD")
        degerler.append(usd_tl)
    if kasa["EUR"] > 0:
        eur_tl = kasa["EUR"] * eur_kur
        toplam_doviz_tl += eur_tl
        doviz_metni += f"   🇪🇺 Euro Kasası: {kasa['EUR']:,.2f} EUR ➔ **{eur_tl:,.2f} TL**\n"
        isimler.append("Nakit EUR")
        degerler.append(eur_tl)
        
    if toplam_doviz_tl <= 0:
        doviz_metni += "   ⚠️ Nakit döviz kasası şu an boş.\n"
    doviz_metni += "\n"

    if bes_degeri > 0:
        isimler.append("BES")
        degerler.append(bes_degeri)

    # Büyük Konsolide Hesaplamalar
    net_servet = toplam_hisse_tl + toplam_altin_tl + toplam_doviz_tl + bes_degeri
    toplam_borsa_kz = (toplam_hisse_tl + (varliklar.get("ALTIN.S1", {}).get("lot", 0) * canli_fiyat_cek("GC=F", "ALTIN_BORSASI", "ALTIN.S1"))) - toplam_maliyet_tl
    toplam_kz_yuzde = (toplam_borsa_kz / toplam_maliyet_tl) * 100 if toplam_maliyet_tl > 0 else 0
    genel_emoji = "🚀" if toplam_borsa_kz >= 0 else "📉"
    genel_isaret = "+" if toplam_borsa_kz >= 0 else ""

    nihai_rapor = hisse_metni + altin_metni + doviz_metni
    nihai_rapor += "👑 ==============================\n"
    nihai_rapor += f"🛡️ **Bireysel Emeklilik (BES):** {bes_degeri:,.2f} TL\n"
    nihai_rapor += f"💎 **BÜTÜN SERVETİMİN TOPLAMI:** {net_servet:,.2f} TL\n"
    nihai_rapor += f"{genel_emoji} **BIST Net Portföy K/Z Oranı:** {genel_isaret}{toplam_kz_yuzde:.2f}% ({toplam_borsa_kz:,.2f} TL)\n"
    nihai_rapor += f"ℹ️ *USD: {usd_kur:.2f} TL | EUR: {eur_kur:.2f} TL | Ons Altın/Gr: {canli_gram_altin:.2f} TL*"

    bot.delete_message(message.chat.id, msg.message_id)

    if degerler:
        plt.figure(figsize=(6,6))
        # Kurumsal renk paleti ve şık dağılım
        plt.pie(degerler, labels=isimler, autopct='%1.1f%%', startangle=140, colors=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'])
        plt.title("GRAND VAULT v4.0 GLOBAL VARLIK DAĞILIMI", fontsize=12, fontweight='bold', color='#111111')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        plt.close()
        bot.send_photo(message.chat.id, buf, caption=nihai_rapor, parse_mode="Markdown", reply_markup=rapor_butonlari_olustur())
    else:
        bot.send_message(message.chat.id, nihai_rapor, parse_mode="Markdown", reply_markup=rapor_butonlari_olustur())

# ---- DİĞER TELEGRAM CALLBACK VE METOT ADIMLARI (v3.8 İLE AYNI STABİL YAPI) ----
@bot.callback_query_handler(func=lambda call: True)
def callback_izleyici(call):
    if not guvenlik_kontrolu(call.from_user.id): return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT tl_degeri FROM sabit_varliklar WHERE varlik_adi='BES'")
    bes_degeri = cursor.fetchone()[0]
    conn.close()

    try:
        usd_kur = yf.Ticker("TRY=X").history(period="1d")['Close'].iloc[-1]
        eur_kur = yf.Ticker("EURTRY=X").history(period="1d")['Close'].iloc[-1]
    except: usd_kur, eur_kur = 33.0, 36.0

    varliklar = varliklari_getir()
    toplam_portfoy_tl = 0
    for varlik, info in varliklar.items():
        guncel_fiyat = canli_fiyat_cek(info["ticker"], info["tip"], varlik) or info["maliyet"]
        toplam_portfoy_tl += info["lot"] * guncel_fiyat

    kasa = doviz_kasasini_getir()
    toplam_doviz_tl = (kasa["USD"] * usd_kur) + (kasa["EUR"] * eur_kur)
    net_servet_tl = toplam_portfoy_tl + toplam_doviz_tl + bes_degeri

    if call.data == "yenile_ana":
        bot.answer_callback_query(call.id, "🔄 Güncelleniyor...")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        ana_menu_gonder(call.message)
    elif call.data == "rapor_usd":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"💵 **USD BAZLI SERVETİNİZ:** ${net_servet_tl / usd_kur:,.2f}")
    elif call.data == "rapor_eur":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"💶 **EUR BAZLI SERVETİNİZ:** €{net_servet_tl / eur_kur:,.2f}")
    elif call.data == "sabit_guncelle":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "🎯 Güncel BES değerinizi rakam olarak yazın:")
        bot.register_next_step_handler(msg, sabit_varlik_kaydet)
    elif call.data == "lot_duzenle_menu":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "🔄 **PORTFÖYÜ SIFIRLAMA (LOT MALİYET)**\n\n`VARLIK_ADI LOT MALİYET` formatında gönderin:")
        bot.register_next_step_handler(msg, dinamik_lot_kaydet)
    elif call.data == "alarm_kur_menu":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "🚨 **FİYAT ALARMI KURMA**\n\n`HİSSE FİYAT`:")
        bot.register_next_step_handler(msg, alarm_kaydet)
    elif call.data == "eylul_simule":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"🎯 **EYLÜL SİMÜLASYONU**\n\n📉 Muhafazakar (+%15): {net_servet_tl*1.15:,.2f} TL\n🚀 İyimser (+%30): {net_servet_tl*1.30:,.2f} TL")
    elif call.data == "sihirbaz_basla":
        bot.answer_callback_query(call.id)
        markup = InlineKeyboardMarkup()
        for v_name in varliklar.keys():
            markup.add(InlineKeyboardButton(f"🔹 {v_name}", callback_data=f"sel_var_{v_name}"))
        markup.add(InlineKeyboardButton("➕ Yeni BIST Hissesi Ekle", callback_data="sel_var_NEW_STOCK"))
        bot.send_message(call.message.chat.id, "🛒 Hangi varlığa bu ay alım eklemesi yaptınız?", reply_markup=markup)
    elif call.data.startswith("sel_var_"):
        bot.answer_callback_query(call.id)
        secilen = call.data.replace("sel_var_", "")
        if secilen == "NEW_STOCK":
            msg = bot.send_message(call.message.chat.id, "📝 Yeni BIST kodunu yazın:")
            bot.register_next_step_handler(msg, yeni_stok_adi_al)
        else:
            USER_STATE[call.from_user.id] = {"hisse": secilen}
            msg = bot.send_message(call.message.chat.id, f"📦 **{secilen}** için kaç adet/lot aldınız?")
            bot.register_next_step_handler(msg, sihirbaz_lot_al)
    elif call.data == "doviz_kasasi_menu":
        bot.answer_callback_query(call.id)
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("💵 Dolar (USD)", callback_data="set_curr_USD"), InlineKeyboardButton("💶 Euro (EUR)", callback_data="set_curr_EUR"))
        bot.send_message(call.message.chat.id, "💵 Hangi nakit döviz kasanızı güncelleyeceksiniz?", reply_markup=markup)
    elif call.data.startswith("set_curr_"):
        bot.answer_callback_query(call.id)
        curr = call.data.replace("set_curr_", "")
        USER_STATE[call.from_user.id] = {"doviz_turu": curr}
        msg = bot.send_message(call.message.chat.id, f"📝 Güncel toplam **{curr}** nakit miktarınızı yazın:")
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
        bot.send_message(message.chat.id, f"✅ Kasa güncellendi! Toplam: **{miktar:,.2f} {doviz}**")
    except: bot.send_message(message.chat.id, "❌ Rakam girin.")

def yeni_stok_adi_al(message):
    hisse_adi = message.text.strip().upper()
    USER_STATE[message.from_user.id] = {"hisse": hisse_adi, "is_new": True}
    msg = bot.send_message(message.chat.id, f"📦 **{hisse_adi}** lot miktarı:")
    bot.register_next_step_handler(msg, sihirbaz_lot_al)

def sihirbaz_lot_al(message):
    try:
        lot = float(message.text.strip())
        uid = message.from_user.id
        USER_STATE[uid]["lot"] = lot
        msg = bot.send_message(message.chat.id, "💵 Birim alış fiyatı (TL):")
        bot.register_next_step_handler(msg, sihirbaz_fiyat_ve_kaydet)
    except: bot.send_message(message.chat.id, "❌ Rakam girin.")

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
            tip_str = "FIZIKI_ALTIN" if "ALTIN" in hisse and hisse != "ALTIN.S1" else ("ALTIN_BORSASI" if hisse == "ALTIN.S1" else "HISSE")
            ticker_str = "GC=F" if "ALTIN" in hisse else f"{hisse}.IS"
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO portfoy_varliklari (varlik_adi, tip, ticker, lot, maliyet) VALUES (?,?,?,?,?)', (hisse, tip_str, ticker_str, toplam_lot, yeni_maliyet))
        conn.commit()
        conn.close()
        USER_STATE.pop(uid, None)
        bot.send_message(message.chat.id, "✅ Alım Sihirbazı işlemi başarıyla veritabanına kaydetti!")
    except: bot.send_message(message.chat.id, "❌ Hata.")

def dinamik_lot_kaydet(message):
    try:
        parcalar = message.text.strip().split()
        v_adi = parcalar[0].upper()
        yeni_lot = float(parcalar[1])
        yeni_maliyet = float(parcalar[2])
        varliklar = varliklari_getir()
        tip_str = varliklar[v_adi]["tip"] if v_adi in varliklar else ("FIZIKI_ALTIN" if "ALTIN" in v_adi and v_adi != "ALTIN.S1" else "HISSE")
        ticker_str = varliklar[v_adi]["ticker"] if v_adi in varliklar else ("GC=F" if "ALTIN" in v_adi else f"{v_adi}.IS")
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO portfoy_varliklari (varlik_adi, tip, ticker, lot, maliyet) VALUES (?,?,?,?,?)', (v_adi, tip_str, ticker_str, yeni_lot, yeni_maliyet))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ {v_adi} sıfırlandı ve işlendi.")
    except: bot.send_message(message.chat.id, "❌ Hata.")

def alarm_kaydet(message):
    try:
        parcalar = message.text.strip().split()
        v_adi = parcalar[0].upper()
        hedef = float(parcalar[1])
        varliklar = varliklari_getir()
        if v_adi not in varliklar: return
        guncel = canli_fiyat_cek(varliklar[v_adi]["ticker"], varliklar[v_adi]["tip"], v_adi) or varliklar[v_adi]["maliyet"]
        yon = "YUKARI" if hedef > guncel else "ASAGI"
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO alarmlar (varlik_adi, hedef_fiyat, yon) VALUES (?, ?, ?)", (v_adi, hedef, yon))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "🚨 Alarm kuruldu.")
    except: pass

def sabit_varlik_kaydet(message):
    try:
        yeni_deger = float(message.text.replace(".", "").replace(",", ".").strip())
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE sabit_varliklar SET tl_degeri=? WHERE varlik_adi='BES'", (yeni_deger,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ BES Güncellendi.")
    except: pass

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
                        guncel = canli_fiyat_cek(varliklar[v_adi]["ticker"], varliklar[v_adi]["tip"], v_adi)
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
    print("👑 Grand Vault v4.0 Ultimate Yayında...")
    bot.infinity_polling()
