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

# ---------------------------------------------------------
# 7/24 PREMIUM MULTI-CURRENCY DASHBOARD (KUSURSUZ BULUT)
# ---------------------------------------------------------

BOT_TOKEN = "8778250529:AAFu08dUsJNiV7YySGB7BFJzT93VmKtdeys"
YETKILI_USER_ID = 7796185729  
bot = telebot.TeleBot(BOT_TOKEN)
DB_FILE = "wealth_management.db"

app = Flask('')
@app.route('/')
def home(): return "Premium Dashboard Kesintisiz Aktif"

FAVORI_VARLIKLAR = {
    "ASELS": {"tip": "HISSE", "ticker": "ASELS.IS"},
    "TUPRS": {"tip": "HISSE", "ticker": "TUPRS.IS"},
    "ENJSA": {"tip": "HISSE", "ticker": "ENJSA.IS"},
    "ALTIN.S1": {"tip": "ALTIN", "ticker": "GC=F"},
    "EREGL": {"tip": "HISSE", "ticker": "EREGL.IS"},
    "SISE": {"tip": "HISSE", "ticker": "SISE.IS"},
    "USD": {"tip": "DOVIZ", "ticker": "USDTRY=X"},
    "EUR": {"tip": "DOVIZ", "ticker": "EURTRY=X"}
}

user_states = {}

def guvenlik_kontrolu(message):
    if message.from_user.id != YETKILI_USER_ID:
        bot.send_message(message.chat.id, "❌ **Yetkisiz Kullanıcı!**\nBu finansal panel sadece sahibine özeldir.")
        return False
    return True

def veri_tabani_kur():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS yatirimlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            varlik_tipi TEXT NOT NULL,
            varlik_adi TEXT NOT NULL,
            miktar REAL NOT NULL,
            maliyet REAL NOT NULL,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sabit_varliklar (
            varlik_adi TEXT PRIMARY KEY,
            guncel_deger REAL NOT NULL
        )
    ''')
    cursor.execute("INSERT OR IGNORE INTO sabit_varliklar (varlik_adi, guncel_deger) VALUES ('BES', 0.0)")
    cursor.execute("INSERT OR IGNORE INTO sabit_varliklar (varlik_adi, guncel_deger) VALUES ('SIGORTA', 0.0)")
    conn.commit()
    conn.close()

def canli_fiyat_cek(tip, ad):
    try:
        if tip == "ALTIN" or ad == "ALTIN.S1":
            gold = yf.Ticker("GC=F")
            usd = yf.Ticker("USDTRY=X")
            return ((gold.fast_info['last_price'] / 31.1035) * usd.fast_info['last_price']) / 100
        else:
            ticker = FAVORI_VARLIKLAR[ad]["ticker"]
            return yf.Ticker(ticker).fast_info['last_price']
    except Exception:
        if ad == "ALTIN.S1": return 25.50
        elif ad == "USD": return 32.50
        elif ad == "EUR": return 35.00
        return 50.0

def ana_dashboard_olustur():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(text="📊 Canlı Portföyü Raporla", callback_data="db_report_TL"),
        InlineKeyboardButton(text="➕ Varlık Alım Ekle", callback_data="db_menu_add"),
        InlineKeyboardButton(text="🎯 Sabit Varlık Güncelle (BES/Sigorta)", callback_data="db_menu_sabit"),
        InlineKeyboardButton(text="🧹 İşlem Geçmişi / Silme Paneli", callback_data="db_menu_delete")
    )
    return markup

def alim_menusu_olustur():
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(text=f"➕ {name}", callback_data=f"asset_{name}") for name in FAVORI_VARLIKLAR.keys() if name not in ["USD", "EUR"]]
    markup.add(*buttons)
    markup.add(InlineKeyboardButton(text="💵 USD Ekle", callback_data="asset_USD"), InlineKeyboardButton(text="💶 EUR Ekle", callback_data="asset_EUR"))
    markup.add(InlineKeyboardButton(text="↩️ Ana Menüye Dön", callback_data="db_main"))
    return markup

def sabit_menusu_olustur():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(text="🎯 BES Güncelle", callback_data="sabit_BES"),
        InlineKeyboardButton(text="🛡️ Sigorta Güncelle", callback_data="sabit_SIGORTA"),
        InlineKeyboardButton(text="↩️ Ana Menüye Dön", callback_data="db_main")
    )
    return markup

def rapor_butonlari_olustur(current_currency):
    markup = InlineKeyboardMarkup(row_width=3)
    buttons = []
    if current_currency != "TL":
        buttons.append(InlineKeyboardButton(text="🇹🇷 TL'ye Dön", callback_data="db_report_TL"))
    if current_currency != "USD":
        buttons.append(InlineKeyboardButton(text="🇺🇸 USD Bazlı", callback_data="db_report_USD"))
    if current_currency != "EUR":
        buttons.append(InlineKeyboardButton(text="🇪🇺 EUR Bazlı", callback_data="db_report_EUR"))
    markup.add(*buttons)
    markup.add(InlineKeyboardButton(text="↩️ Ana Menüye Dön", callback_data="db_main"))
    return markup

@bot.message_handler(commands=['start', 'menu', 'dashboard'])
def send_welcome(message):
    if not guvenlik_kontrolu(message): return
    user_states.pop(message.chat.id, None)
    bot.send_message(
        message.chat.id, 
        "👑 **Tolga Mermertaş | Kişisel Servet Yönetim Paneli**\n\nFinansal durumunuzu izlemek ve yönetmek için aşağıdaki interaktif paneli kullanabilirsiniz.", 
        reply_markup=ana_dashboard_olustur(),
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.message.chat.id != YETKILI_USER_ID: return
    chat_id = call.message.chat.id
    
    if call.data == "db_main":
        user_states.pop(chat_id, None)
        bot.edit_message_text("👑 **Kişisel Servet Yönetim Paneli**\n\nLütfen yapmak istediğiniz işlemi seçin:", chat_id, call.message.message_id, reply_markup=ana_dashboard_olustur())
    
    elif call.data == "db_menu_add":
        bot.edit_message_text("➕ **Ekleme Yapmak İstediğiniz Varlığı Seçin:**\n*(Fiyat otomatik doğrulanacaktır)*", chat_id, call.message.message_id, reply_markup=alim_menusu_olustur(), parse_mode="Markdown")
    
    elif call.data == "db_menu_sabit":
        bot.edit_message_text("🎯 **Güncellemek İstediğiniz Sabit Varlığı Seçin:**", chat_id, call.message.message_id, reply_markup=sabit_menusu_olustur(), parse_mode="Markdown")
    
    elif call.data == "db_menu_delete":
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT id, varlik_adi, miktar, tarih FROM yatirimlar ORDER BY id DESC LIMIT 5")
        son_islemler = cursor.fetchall()
        conn.close()
        
        if not son_islemler:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(text="↩️ Geri Dön", callback_data="db_main"))
            bot.edit_message_text("🧹 Silinecek herhangi bir işlem geçmişi bulunamadı.", chat_id, call.message.message_id, reply_markup=markup)
            return
            
        markup = InlineKeyboardMarkup(row_width=1)
        for idx, ad, miktar, tarih in son_islemler:
            tarih_kisa = tarih.split()[0] if tarih else ""
            markup.add(InlineKeyboardButton(text=f"❌ Sil: {ad} ({miktar:,.0f} Lot) - {tarih_kisa}", callback_data=f"del_{idx}"))
        markup.add(InlineKeyboardButton(text="↩️ Ana Menüye Dön", callback_data="db_main"))
        bot.edit_message_text("🧹 **Son Yaptığınız İşlemler:**\nSilmek istediğiniz işlemin üzerine tıklayın:", chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data.startswith("del_"):
        islem_id = call.data.split("_")[1]
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM yatirimlar WHERE id = ?", (islem_id,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "✅ İşlem başarıyla silindi!")
        handle_callbacks(telebot.types.CallbackQuery(call.id, call.from_user, call.message, call.inline_message_id, data="db_menu_delete"))

    elif call.data.startswith("asset_"):
        varlik_adi = call.data.split("_")[1]
        user_states[chat_id] = {"mod": "ALIM", "varlik": varlik_adi}
        bot.send_message(chat_id, f"📝 **{varlik_adi}** için yeni aldığınız lot/adet sayısını giriniz:")
        bot.answer_callback_query(call.id)

    elif call.data.startswith("sabit_"):
        sabit_adi = call.data.split("_")[1]
        user_states[chat_id] = {"mod": "SABIT", "varlik": sabit_adi}
        bot.send_message(chat_id, f"🎯 **{sabit_adi}** için yeni güncel toplam TL değerini giriniz:")
        bot.answer_callback_query(call.id)

    elif call.data.startswith("db_report_"):
        currency = call.data.split("_")[2]
        bot.answer_callback_query(call.id, f"🔄 {currency} bazlı rapor hazırlanıyor...")
        try: bot.delete_message(chat_id, call.message.message_id)
        except: pass
        portfoy_raporla_ve_gonder(call.message, currency)

def portfoy_raporla_ve_gonder(message, para_birimi="TL"):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT varlik_adi, guncel_dezer FROM sabit_varliklar" if 'guncel_dezer' in locals() else "SELECT varlik_adi, guncel_deger FROM sabit_varliklar")
    sabitler = dict(cursor.fetchall())
    cursor.execute("SELECT varlik_tipi, varlik_adi, SUM(miktar), SUM(miktar * maliyet) / SUM(miktar) FROM yatirimlar GROUP BY varlik_adi HAVING SUM(miktar) > 0")
    dinamikler = cursor.fetchall()
    conn.close()

    usd_kuru = canli_fiyat_cek("DOVIZ", "USD")
    eur_kuru = canli_fiyat_cek("DOVIZ", "EUR")
    
    bolen = 1.0
    sembol = "TL"
    if para_birimi == "USD":
        bolen = usd_kuru
        sembol = "$"
    elif para_birimi == "EUR":
        bolen = eur_kuru
        sembol = "€"

    toplam_portfoy_degeri = 0
    toplam_maliyet = 0
    rapor_metni = f"📊 **KONSOLİDE SERVET RAPORU ({para_birimi})**\n\n"
    grafik_etiketler = []
    grafik_degerler = []

    for tip, ad, miktar, ort_maliyet in dinamikler:
        guncel_fiyat_tl = canli_fiyat_cek(tip, ad)
        v_maliyet_tl = miktar * ort_maliyet
        v_deger_tl = miktar * guncel_fiyat_tl
        
        toplam_portfoy_degeri += v_deger_tl
        toplam_maliyet += v_maliyet_tl
        
        guncel_fiyat_out = guncel_fiyat_tl / bolen
        v_deger_out = v_deger_tl / bolen
        ort_maliyet_out = ort_maliyet / bolen
        
        v_pnl = v_deger_tl - v_maliyet_tl
        v_pnl_yuzde = (v_pnl / v_maliyet_tl) * 100 if v_maliyet_tl > 0 else 0
        pnl_emoji = "🟢" if v_pnl >= 0 else "🔴"
        
        rapor_metni += f"• **{ad}**: {miktar:,.2f} Lot\n  Maliyet: {ort_maliyet_out:,.2f} {sembol} | Güncel: {guncel_fiyat_out:,.2f} {sembol}\n  Değer: **{v_deger_out:,.2f} {sembol}** | K/Z: {pnl_emoji} %{v_pnl_yuzde:.2f}\n\n"
        if v_deger_tl > 0:
            grafik_etiketler.append(ad)
            grafik_degerler.append(v_deger_tl)

    for ad, deger_tl in sabitler.items():
        if deger_tl > 0:
            toplam_portfoy_degeri += deger_tl
            deger_out = deger_tl / bolen
            rapor_metni += f"• **{ad}**: Değer: **{deger_out:,.2f} {sembol}**\n\n"
            grafik_etiketler.append(ad)
            grafik_degerler.append(deger_tl)

    if toplam_portfoy_degeri == 0:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(text="↩️ Dashboard'a Dön", callback_data="db_main"))
        bot.send_message(message.chat.id, "📭 Portföyünüzde henüz kayıtlı bir varlık bulunmamaktadır.", reply_markup=markup)
        return

    net_pnl_tl = toplam_portfoy_degeri - toplam_maliyet
    net_pnl_yuzde = (net_pnl_tl / toplam_maliyet) * 100 if toplam_maliyet > 0 else 0
    net_emoji = "🚀" if net_pnl_tl >= 0 else "📉"
    
    toplam_portfoy_out = toplam_portfoy_degeri / bolen
    net_pnl_out = net_pnl_tl / bolen

    rapor_metni += "───────────────────\n" f"💰 **Net Varlık Değeri: {toplam_portfoy_out:,.2f} {sembol}**\n"
    if toplam_maliyet > 0:
        rapor_metni += f"{net_emoji} **Borsa K/Z Oranı: {net_pnl_out:,.2f} {sembol} (%{net_pnl_yuzde:.2f})**"

    plt.figure(figsize=(6, 6))
    colors = ['#0f4c81', '#1f77b4', '#5b92e5', '#a5c4f2', '#36454f', '#8a9a86']
    plt.pie(grafik_degerler, labels=grafik_etiketler, autopct='%1.1f%%', startangle=140, colors=colors, textprops={'fontsize': 10, 'weight': 'bold'})
    plt.title("Varlık Dağılım Matrisi", fontsize=14, weight='bold', pad=20)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=200)
    buf.seek(0)
    plt.close()

    bot.send_photo(message.chat.id, buf, caption=rapor_metni, parse_mode="Markdown", reply_markup=rapor_butonlari_olustur(para_birimi))

@bot.message_handler(func=lambda message: message.chat.id in user_states and not message.text.startswith('/'))
def handle_text_inputs(message):
    if not guvenlik_kontrolu(message): return
    chat_id = message.chat.id
    state = user_states[chat_id]
    
    try:
        deger = float(message.text.replace(',', '.'))
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        
        if state["mod"] == "ALIM":
            varlik_adi = state["varlik"]
            bot.send_message(chat_id, "⏳ Canlı borsa fiyatı doğrulanıyor...")
            tip = "DOVIZ" if varlik_adi in ["USD", "EUR"] else FAVORI_VARLIKLAR[varlik_adi]["tip"]
            fiyat = canli_fiyat_cek(tip, varlik_adi)
            cursor.execute("INSERT INTO yatirimlar (varlik_tipi, varlik_adi, miktar, maliyet) VALUES (?, ?, ?, ?)", (tip, varlik_adi, deger, fiyat))
            bot.send_message(chat_id, f"✅ **{varlik_adi}** portföye eklendi!\n+{deger:,.2f} Lot (Fiyat: {fiyat:,.2f} TL)", reply_markup=ana_dashboard_olustur())
            
        elif state["mod"] == "SABIT":
            sabit_adi = state["varlik"]
            cursor.execute("UPDATE sabit_varliklar SET guncel_deger = ? WHERE varlik_adi = ?", (deger, sabit_adi))
            bot.send_message(chat_id, f"✅ **{sabit_adi}** güncel değeri **{deger:,.2f} TL** olarak güncellendi.", reply_markup=ana_dashboard_olustur())
            
        conn.commit()
        conn.close()
    except ValueError:
        bot.send_message(chat_id, "❌ Hata! Lütfen sadece sayısal bir değer giriniz.")
    
    user_states.pop(chat_id, None)

def run_web_server():
    try:
        port = int(os.environ.get("PORT", 8080))
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Sunucu uyarısı: {e}")

if __name__ == '__main__':
    veri_tabani_kur()
    Thread(target=run_web_server, daemon=True).start()
    print("💎 Korumalı ve Çoklu Para Birimli Sistem Aktif...")
    bot.infinity_polling()
