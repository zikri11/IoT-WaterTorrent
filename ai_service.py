"""
=========================================================
AI SERVICE
=========================================================

File ini bertanggung jawab untuk:

- Mengirim data sensor ke LLM
- Menghasilkan analisis AI
=========================================================
"""

from groq import Groq
import json
from config import GROQ_API_KEY, AI_MODEL

# membuat client LLM
client = Groq(api_key=GROQ_API_KEY)

def _extract_json_object(text: str) -> dict:
    """
    Ekstrak JSON object pertama dari output model yang kadang menambahkan
    code fence atau teks tambahan.
    """

    if not isinstance(text, str):
        raise ValueError("LLM output is not a string")

    s = text.strip()

    # buang code fence paling umum
    if s.startswith("```"):
        # hapus baris pertama ``` atau ```json
        first_newline = s.find("\n")
        if first_newline != -1:
            s = s[first_newline + 1 :]
        # hapus fence penutup jika ada
        if s.rstrip().endswith("```"):
            s = s.rstrip()
            s = s[: -3].rstrip()

    # ambil substring dari { pertama sampai } terakhir
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM output")

    candidate = s[start : end + 1]
    return json.loads(candidate)


def _normalize_water_analysis(value) -> str:
    """
    water_analysis bisa berupa string (yang diinginkan) atau object/list.
    Kita paksa jadi string ringkas.
    """

    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    # jika model mengembalikan object, stringify ringkas
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value).strip()


def _infer_tank_cleanliness_from_turbidity(turbidity: float) -> dict:
    """
    Fallback prediksi kebersihan toren berbasis turbidity (NTU).
    Dipakai jika output LLM tidak bisa di-parse.
    """

    try:
        t = float(turbidity)
    except Exception:
        return {
            "tank_cleanliness": "Tidak diketahui",
            "cleaning_advice": (
                "Data turbidity tidak valid. Periksa sensor turbidity dan kalibrasi."
            )
        }

    if t <= 5:
        return {
            "tank_cleanliness": "Bersih",
            "cleaning_advice": (
                "Pertahankan kebersihan toren. Bersihkan berkala dan pastikan penutup rapat."
            )
        }

    if t <= 25:
        return {
            "tank_cleanliness": "Kurang bersih",
            "cleaning_advice": (
                "Pertimbangkan pembersihan ringan: kuras sebagian, sikat dinding, "
                "cek endapan dan lumut, serta periksa filter/masuknya kotoran."
            )
        }

    return {
        "tank_cleanliness": "Kotor",
        "cleaning_advice": (
            "Disarankan pembersihan menyeluruh: kuras toren, sikat dinding & dasar, "
            "bilas hingga jernih, cek sumber kekeruhan (filter, pipa, penutup), "
            "dan lakukan pengisian ulang dengan air yang lebih bersih."
        )
    }

def generate_analysis(sensor_data, kategori):
    """
    Menghasilkan analisis AI berdasarkan data sensor
    """

    prompt = f"""
Anda adalah asisten untuk sistem IoT monitoring air toren.
Target pembaca: USER AWAM (tidak paham pH, TDS, NTU, dll).
Gaya bahasa: profesional, ramah, jelas, tidak menakut-nakuti, dan mudah dipahami.

DATA SENSOR (JSON):
{json.dumps(sensor_data, indent=2)}

KATEGORI AIR:
{kategori}

TUGAS:
1) Buat ringkasan analisis kualitas air dalam Bahasa Indonesia yang mudah dimengerti (3–5 kalimat pendek).
   - Hindari jargon. Jika harus menyebut istilah, jelaskan singkat dalam kurung:
     pH (tingkat keasaman), turbidity (kekeruhan), TDS (jumlah zat terlarut).
   - Jelaskan dampak praktis untuk pemakaian harian (mis. mandi/masak) sesuai kategori.
   - Sertakan 1 kalimat saran tindakan yang aman dan praktis.
2) Prediksi status kebersihan toren berdasarkan nilai turbidity (kekeruhan) dan konteks sensor:
   - output label: "Bersih" atau "Kurang bersih" atau "Kotor"
3) Berikan saran singkat pembersihan/penanganan toren (1-3 kalimat), praktis dan aman.

FORMAT OUTPUT:
Kembalikan STRICT JSON saja (tanpa markdown/code fence, tanpa penjelasan tambahan) dengan keys:
{{
  "water_analysis": "string",
  "tank_cleanliness": "Bersih|Kurang bersih|Kotor",
  "cleaning_advice": "string"
}}
"""

    try:
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        content = response.choices[0].message.content.strip()

        parsed = _extract_json_object(content)

        water_analysis = _normalize_water_analysis(parsed.get("water_analysis", ""))
        tank_cleanliness = str(parsed.get("tank_cleanliness", "")).strip()
        cleaning_advice = str(parsed.get("cleaning_advice", "")).strip()

        if not water_analysis:
            water_analysis = "Analisis AI tidak tersedia."

        if tank_cleanliness not in ("Bersih", "Kurang bersih", "Kotor"):
            fallback = _infer_tank_cleanliness_from_turbidity(sensor_data.get("turbidity"))
            tank_cleanliness = fallback["tank_cleanliness"]
            if not cleaning_advice:
                cleaning_advice = fallback["cleaning_advice"]

        if not cleaning_advice:
            fallback = _infer_tank_cleanliness_from_turbidity(sensor_data.get("turbidity"))
            cleaning_advice = fallback["cleaning_advice"]

        return {
            "water_analysis": water_analysis,
            "tank_cleanliness": tank_cleanliness,
            "cleaning_advice": cleaning_advice,
        }

    except Exception:
        fallback = _infer_tank_cleanliness_from_turbidity(sensor_data.get("turbidity"))
        return {
            "water_analysis": "Analisis AI sementara tidak tersedia.",
            "tank_cleanliness": fallback["tank_cleanliness"],
            "cleaning_advice": fallback["cleaning_advice"],
        }