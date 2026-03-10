"""
=========================================================
TELEGRAM SERVICE
=========================================================

File ini bertanggung jawab untuk mengirim pesan ke Telegram.

Ada dua jenis pesan:

1. FULL REPORT
   - dikirim saat ESP32 start
   - dikirim saat tombol refresh ditekan

2. ALERT MESSAGE
   - dikirim saat air tidak layak
   - hanya berisi penjelasan AI
=========================================================
"""

import requests
from config import BOT_TOKEN, CHAT_ID, SYSTEM_NAME


# =====================================================
# HELPERS
# =====================================================

def _normalize_ai_result(analisis):

    """
    Mendukung format lama (string) dan format baru (dict JSON).
    """

    if isinstance(analisis, dict):
        return {
            "water_analysis": str(analisis.get("water_analysis", "")).strip(),
            "tank_cleanliness": str(analisis.get("tank_cleanliness", "")).strip(),
            "cleaning_advice": str(analisis.get("cleaning_advice", "")).strip(),
        }

    return {
        "water_analysis": str(analisis).strip(),
        "tank_cleanliness": "",
        "cleaning_advice": "",
    }

def _default_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "ℹ️ Info Kualitas Air", "callback_data": "info_status"},
                {"text": "🧯 Status Pompa", "callback_data": "pump_status"},
            ]
        ]
    }


def send_pump_status(sensor_data):

    pump_status = sensor_data.get("pump_status", "UNKNOWN")
    tank_percent = sensor_data.get("tank_percent", "-")

    message = f"""
<pre>
🧯 STATUS POMPA AIR
📡 {SYSTEM_NAME}

🔌 Status Pompa
--------------------------------
Pompa         : {pump_status}
Tank Percent  : {tank_percent} %

🤖 Sistem Otomatis Pompa
--------------------------------
- Pompa ON  jika toren &lt; 30%
- Pompa OFF jika toren &gt; 80%
- Jika air terdeteksi tidak layak,
  pompa akan dipaksa OFF

ℹ️ Untuk data terbaru, tekan
"Info Kualitas Air".

--------------------------------
⚙️ Sistem IoT Water Monitoring
</pre>
"""

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "reply_markup": _default_keyboard(),
    }

    requests.post(url, json=payload)


# =====================================================
# FULL REPORT (START + REFRESH)
# =====================================================

def send_full_report(sensor_data, kategori, analisis):

    """
    Mengirim laporan lengkap sensor.
    Digunakan saat:
    - perangkat start
    - tombol refresh ditekan
    """

    ai = _normalize_ai_result(analisis)

    message = f"""
<pre>
📡 {SYSTEM_NAME}

📊 DATA SENSOR
--------------------------------
pH            : {sensor_data["ph"]}
Turbidity     : {sensor_data["turbidity"]} NTU
TDS           : {sensor_data["tds"]} ppm
Temperature   : {sensor_data["temperature"]} °C

🚰 TANK STATUS
--------------------------------
Water Level   : {sensor_data["water_level"]} cm
Tank Percent  : {sensor_data["tank_percent"]} %

🧽 KEBERSIHAN TOREN (Prediksi)
--------------------------------
Kondisi       : {ai["tank_cleanliness"]}
Saran         : {ai["cleaning_advice"]}

🧠 AI ANALYSIS
--------------------------------
Status        : {kategori}

Analisis :
{ai["water_analysis"]}

--------------------------------
⚙️ Sistem IoT Water Monitoring
</pre>
"""

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",

        "reply_markup": _default_keyboard()
    }

    requests.post(url, json=payload)


# =====================================================
# ALERT MESSAGE (AIR TIDAK LAYAK)
# =====================================================

def send_alert_message(sensor_data, kategori, analisis):

    """
    Mengirim pesan alert sederhana.
    Tidak menampilkan angka sensor
    agar lebih mudah dipahami user.
    """

    ai = _normalize_ai_result(analisis)

    message = f"""
<pre>
⚠️ PERINGATAN KUALITAS AIR

📡 {SYSTEM_NAME}

🚨 STATUS AIR
--------------------------------
Status        : {kategori}

🧽 KEBERSIHAN TOREN (Prediksi)
--------------------------------
Kondisi       : {ai["tank_cleanliness"]}
Saran         : {ai["cleaning_advice"]}

🧠 AI ANALYSIS
--------------------------------
Penjelasan :
{ai["water_analysis"]}

🚰 TANK STATUS
--------------------------------
Tank Percent  : {sensor_data["tank_percent"]} %

⏱ SIKLUS ALERT
--------------------------------
Pesan ini dikirim otomatis setiap
±5 menit selama kualitas air masih
belum normal.

Jika kualitas air sudah normal,
alert akan berhenti otomatis.

ℹ️ INFO REALTIME
--------------------------------
Tekan tombol "Info Kualitas Air"
di bawah untuk melihat data sensor
terbaru dan analisis AI lengkap.

--------------------------------
⚙️ Sistem IoT Water Monitoring
</pre>
"""

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",

        "reply_markup": _default_keyboard()
    }

    requests.post(url, json=payload)