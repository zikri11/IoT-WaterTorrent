/*
====================================================
SMART WATER TANK MONITORING IOT DEVICE
FINAL VERSION (EVENT + ANTI SPAM)
====================================================

Fitur sistem:

1. Kirim laporan lengkap saat ESP32 start
2. Membaca sensor setiap 5 detik
3. Mengirim ALERT jika air tidak layak
4. Anti spam alert (cooldown 5 menit)
5. Mendukung tombol refresh Telegram
====================================================
*/

#include <WiFi.h>
#include <HTTPClient.h>

#include <OneWire.h>
#include <DallasTemperature.h>

//////////////////////////////////////////////////
// WIFI CONFIG
//////////////////////////////////////////////////

const char* ssid = "Wokwi-GUEST";
const char* password = "";

String serverUrl = "https://apiiot.informatika23e.my.id/analyze-water";
String commandUrl = "https://apiiot.informatika23e.my.id/device-command";

//////////////////////////////////////////////////
// SENSOR PIN
//////////////////////////////////////////////////

#define PH_PIN 34
#define TURBIDITY_PIN 35
#define TDS_PIN 32

#define TRIG_PIN 5
#define ECHO_PIN 18

#define ONE_WIRE_BUS 4

//////////////////////////////////////////////////
// RELAY / POMPA AIR
//////////////////////////////////////////////////

// Asumsi modul relay aktif-LOW (LOW = ON, HIGH = OFF)
#define RELAY_PIN 23

// Ambang kontrol otomatis toren (dalam % isi toren)
const float TANK_LOW_THRESHOLD  = 30.0;  // di bawah ini pompa ON
const float TANK_HIGH_THRESHOLD = 80.0;  // di atas ini pompa OFF

bool pumpIsOn = false;

//////////////////////////////////////////////////
// TEMPERATURE SENSOR
//////////////////////////////////////////////////

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

//////////////////////////////////////////////////
// TANK CONFIG
//////////////////////////////////////////////////

float tankHeight = 400.0;

//////////////////////////////////////////////////
// ANTI SPAM ALERT SYSTEM
//////////////////////////////////////////////////

unsigned long lastAlertTime = 0;
const long alertCooldown = 300000; // 5 menit

//////////////////////////////////////////////////
// WIFI CONNECTION
//////////////////////////////////////////////////

void connectWiFi() {

  Serial.print("Connecting to WiFi");

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {

    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WiFi Connected!");
}

//////////////////////////////////////////////////
// READ WATER SENSORS
//////////////////////////////////////////////////

void readWaterSensors(float &ph, float &turbidity, float &tds) {

  int phRaw = analogRead(PH_PIN);
  int turbRaw = analogRead(TURBIDITY_PIN);
  int tdsRaw = analogRead(TDS_PIN);

  ph = phRaw * 14.0 / 4095.0;
  turbidity = turbRaw * 30.0 / 4095.0;
  tds = tdsRaw * 1200.0 / 4095.0;
}

//////////////////////////////////////////////////
// READ TEMPERATURE
//////////////////////////////////////////////////

float readTemperature() {

  sensors.requestTemperatures();

  return sensors.getTempCByIndex(0);
}

//////////////////////////////////////////////////
// READ ULTRASONIC SENSOR
//////////////////////////////////////////////////

float readDistance() {

  long duration;

  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);

  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);

  digitalWrite(TRIG_PIN, LOW);

  duration = pulseIn(ECHO_PIN, HIGH);

  float distance = duration * 0.034 / 2;

  return distance;
}

//////////////////////////////////////////////////
// CEK AIR TIDAK LAYAK
//////////////////////////////////////////////////

bool isWaterUnsafe(float ph, float turbidity, float tds, float temperature) {

  if (ph < 6.5 || ph > 8.5) return true;

  // PERMENKES RI No. 2 Tahun 2023 (Higiene & Sanitasi):
  // Turbidity < 3 NTU dianggap aman
  if (turbidity >= 3) return true;

  // TDS < 300 ppm dianggap aman
  if (tds >= 300) return true;

  return false;
}

bool isTemperatureAbnormal(float temperature) {
  // Suhu hanya indikator "tidak normal", tidak mempengaruhi kualitas air
  return (temperature > 35 || temperature < 10);
}

//////////////////////////////////////////////////
// SEND DATA TO SERVER
//////////////////////////////////////////////////

void sendDataToServer(float ph,
                      float turbidity,
                      float tds,
                      float temperature,
                      float waterLevel,
                      float tankPercent,
                      const String &pumpStatus,
                      const String &trigger) {

  if (WiFi.status() == WL_CONNECTED) {

    HTTPClient http;

    http.begin(serverUrl);

    http.addHeader("Content-Type", "application/json");

    String json = "{";

    json += "\"ph\":" + String(ph) + ",";
    json += "\"turbidity\":" + String(turbidity) + ",";
    json += "\"tds\":" + String(tds) + ",";
    json += "\"temperature\":" + String(temperature) + ",";
    json += "\"water_level\":" + String(waterLevel) + ",";
    json += "\"tank_percent\":" + String(tankPercent) + ",";
    json += "\"pump_status\":\"" + pumpStatus + "\",";
    json += "\"trigger\":\"" + trigger + "\"";

    json += "}";

    Serial.println("Sending data to server...");
    Serial.println(json);

    int httpResponseCode = http.POST(json);

    Serial.print("Server Response: ");
    Serial.println(httpResponseCode);

    http.end();
  }
}

//////////////////////////////////////////////////
// PROCESS SENSOR DATA
//////////////////////////////////////////////////

void controlPump(float tankPercent, bool unsafe) {

  // Jika kualitas air tidak layak, paksa pompa OFF
  if (unsafe) {
    digitalWrite(RELAY_PIN, HIGH); // OFF (aktif-LOW)
    pumpIsOn = false;
    Serial.println("PUMP OFF: water unsafe");
    return;
  }

  // Kontrol level toren
  if (tankPercent < TANK_LOW_THRESHOLD) {
    digitalWrite(RELAY_PIN, LOW); // ON
    pumpIsOn = true;
    Serial.println("PUMP ON: tank below low threshold");
  } else if (tankPercent > TANK_HIGH_THRESHOLD) {
    digitalWrite(RELAY_PIN, HIGH); // OFF
    pumpIsOn = false;
    Serial.println("PUMP OFF: tank above high threshold");
  }
}

void processSensorData(bool forceSend = false, const String &trigger = "auto") {

  float ph;
  float turbidity;
  float tds;

  readWaterSensors(ph, turbidity, tds);

  float temperature = readTemperature();

  float distance = readDistance();

  float waterLevel = tankHeight - distance;

  if (waterLevel < 0) waterLevel = 0;

  float tankPercent = (waterLevel / tankHeight) * 100;

  Serial.println("===== WATER TANK MONITORING =====");

  Serial.print("pH: ");
  Serial.println(ph);

  Serial.print("Turbidity: ");
  Serial.println(turbidity);

  Serial.print("TDS: ");
  Serial.println(tds);

  Serial.print("Temperature: ");
  Serial.println(temperature);
  if (isTemperatureAbnormal(temperature)) {
    Serial.println("NOTE: Temperature abnormal (does not affect water quality status)");
  }

  Serial.print("Water Level: ");
  Serial.println(waterLevel);

  Serial.print("Tank Percent: ");
  Serial.println(tankPercent);

  Serial.println("==============================");

  bool unsafe = isWaterUnsafe(ph, turbidity, tds, temperature);

  unsigned long currentMillis = millis();

  // Kontrol pompa lebih dulu agar status pompa yang dikirim adalah status terbaru
  controlPump(tankPercent, unsafe);
  String pumpStatus = pumpIsOn ? "ON" : "OFF";

  if (forceSend) {

    // digunakan untuk laporan start / info

    sendDataToServer(
      ph,
      turbidity,
      tds,
      temperature,
      waterLevel,
      tankPercent,
      pumpStatus,
      trigger
    );

    return;
  }

  if (unsafe) {

    // Kirim alert langsung saat pertama kali terdeteksi tidak layak,
    // lalu aktifkan cooldown 5 menit untuk menghindari spam.
    if (lastAlertTime == 0 || (currentMillis - lastAlertTime >= alertCooldown)) {

      Serial.println("⚠ WATER QUALITY ALERT");

      sendDataToServer(
        ph,
        turbidity,
        tds,
        temperature,
        waterLevel,
        tankPercent,
        pumpStatus,
        "auto"
      );

      lastAlertTime = currentMillis;
    }

  } else {

    // Jika sudah kembali normal, reset agar jika nanti tidak layak lagi
    // alert bisa terkirim langsung.
    lastAlertTime = 0;
  }
}

//////////////////////////////////////////////////
// CEK COMMAND SERVER
//////////////////////////////////////////////////

void checkServerCommand() {

  if (WiFi.status() == WL_CONNECTED) {

    HTTPClient http;

    http.begin(commandUrl);

    int httpCode = http.GET();

    if (httpCode == 200) {

      String payload = http.getString();

      Serial.println("Command Response:");
      Serial.println(payload);

      if (payload.indexOf("info_button") >= 0) {

        Serial.println("INFO BUTTON COMMAND RECEIVED");

        processSensorData(true, "info_button"); // kirim laporan lengkap terbaru
      }
    }

    http.end();
  }
}

//////////////////////////////////////////////////
// SETUP
//////////////////////////////////////////////////

void setup() {

  Serial.begin(115200);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(RELAY_PIN, OUTPUT);

  // Pastikan pompa OFF saat start
  digitalWrite(RELAY_PIN, HIGH);
  pumpIsOn = false;

  sensors.begin();

  connectWiFi();

  // kirim laporan pertama saat start
  processSensorData(true, "startup");
}

//////////////////////////////////////////////////
// LOOP
//////////////////////////////////////////////////

void loop() {

  processSensorData();

  checkServerCommand();

  delay(5000);
}