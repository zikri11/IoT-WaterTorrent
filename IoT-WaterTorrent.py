"""
=========================================================
SMART WATER TANK MONITORING API
=========================================================

API ini memiliki fungsi:

1. Menerima data sensor dari ESP32
2. Mengklasifikasi kualitas air
3. Menggunakan AI untuk analisis kualitas air
4. Mengirim laporan ke Telegram
5. Mendukung tombol refresh Telegram
6. Mengirim command ke ESP32

Endpoint:

POST /analyze-water
GET  /device-command
POST /telegram-webhook
=========================================================
"""

# =====================================================
# IMPORT LIBRARY
# =====================================================

from fastapi import FastAPI, Request
from ai_service import generate_analysis
from telegram_service import send_full_report, send_alert_message, send_pump_status


# =====================================================
# FASTAPI INSTANCE
# =====================================================

app = FastAPI()


# =====================================================
# VARIABEL GLOBAL
# =====================================================

"""
Menyimpan data sensor terakhir.
Digunakan saat tombol refresh ditekan.
"""

latest_sensor_data = None
latest_kategori = None
latest_analisis = None


"""
Command untuk ESP32.
refresh → ESP32 membaca sensor sekarang
"""

device_command = None


# =====================================================
# KLASIFIKASI AIR
# =====================================================

def check_higiene_sanitasi(data):

    return (
        6.5 <= data["ph"] <= 8.5 and
        data["turbidity"] < 3 and
        data["tds"] < 300
    )


def is_temperature_abnormal(temp):
    """
    Suhu hanya indikator "tidak normal", tidak mempengaruhi status kelayakan air.
    """

    return temp is not None and (temp > 35 or temp < 10)


# =====================================================
# ENDPOINT ESP32
# =====================================================

@app.post("/analyze-water")
async def analyze_water(sensor_data: dict):

    global latest_sensor_data
    global latest_kategori
    global latest_analisis

    """
    Endpoint ini menerima data sensor dari ESP32
    """

    trigger = sensor_data.get("trigger", "auto")

    # ==============================================
    # MENENTUKAN STATUS AIR
    # ==============================================

    layak = check_higiene_sanitasi(sensor_data)
    temp_abnormal = is_temperature_abnormal(sensor_data.get("temperature"))

    if layak:
        kategori = "Air layak digunakan untuk higiene dan sanitasi (mandi dan konsumsi tidak langsung/masak)."
        if temp_abnormal:
            kategori += " Catatan: suhu terdeteksi tidak normal."
    else:
        kategori = "Air tidak layak digunakan untuk higiene dan sanitasi (mandi dan konsumsi tidak langsung/masak)."
        if temp_abnormal:
            kategori += " Catatan: suhu terdeteksi tidak normal."


    # ==============================================
    # ANALISIS AI
    # ==============================================

    analisis = generate_analysis(sensor_data, kategori)


    # ==============================================
    # MENYIMPAN DATA TERAKHIR
    # ==============================================

    latest_sensor_data = sensor_data
    latest_kategori = kategori
    latest_analisis = analisis


    # ==============================================
    # CEK APAKAH AIR TIDAK LAYAK
    # ==============================================

    if trigger in ("info_button", "startup"):

        """
        Jika dipicu oleh tombol Info / startup,
        selalu kirim laporan lengkap terbaru.
        """

        send_full_report(sensor_data, kategori, analisis)

    else:

        """
        Trigger auto (pembacaan rutin):
        - jika tidak layak → kirim alert
        - jika layak → tidak kirim notif
        """

        if "tidak layak" in kategori:
            send_alert_message(sensor_data, kategori, analisis)


    # ==============================================
    # RESPONSE KE ESP32
    # ==============================================

    return {
        "sensor_data": sensor_data,
        "kategori": kategori,
        "analisis_llm": analisis
    }


# =====================================================
# ENDPOINT ESP32 CEK COMMAND
# =====================================================

@app.get("/device-command")
async def device_command_check():

    """
    Endpoint ini dipanggil ESP32
    untuk mengecek apakah ada command dari server.
    """

    global device_command

    cmd = device_command

    # reset command setelah dibaca
    device_command = None

    return {
        "command": cmd
    }


# =====================================================
# TELEGRAM WEBHOOK
# =====================================================

@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):

    global device_command

    data = await request.json()

    """
    Endpoint ini menerima event dari Telegram
    """

    if "callback_query" in data:

        callback = data["callback_query"]
        action = callback["data"]

        if action == "info_status":

            """
            Jika tombol refresh ditekan:

            1. kirim command ke ESP32
            2. ESP32 membaca sensor sekarang
            """

            device_command = "info_button"

        if action == "pump_status":

            """
            Kirim status pompa berdasarkan data terakhir dari ESP32.
            """

            if latest_sensor_data is not None:
                send_pump_status(latest_sensor_data)


    return {"status": "ok"}