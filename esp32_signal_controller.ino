/*
 * FlowMirror miniature intersection controller.
 *
 * This board drives demonstration LEDs only. It must never be connected to
 * traffic-signal equipment, mains power, relays, or any public-road system.
 */
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

const char* WIFI_SSID = "REPLACE_WITH_WIFI_NAME";
const char* WIFI_PASSWORD = "REPLACE_WITH_WIFI_PASSWORD";

// Use the LAN IP address of the computer running uvicorn, not localhost.
const char* FLOWMIRROR_SIGNAL_URL =
  "http://192.168.1.50:8000/api/signals/signal-E/hardware";

const int RED_PIN = 25;
const int YELLOW_PIN = 26;
const int GREEN_PIN = 27;
const unsigned long POLL_INTERVAL_MS = 1500;

unsigned long lastPollAt = 0;

void setLights(bool red, bool yellow, bool green) {
  digitalWrite(RED_PIN, red ? HIGH : LOW);
  digitalWrite(YELLOW_PIN, yellow ? HIGH : LOW);
  digitalWrite(GREEN_PIN, green ? HIGH : LOW);
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
  }
}

void showSafeFallback() {
  // Flash yellow when FlowMirror or Wi-Fi is unreachable.
  bool on = (millis() / 500) % 2 == 0;
  setLights(false, on, false);
}

void updateSignal() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  HTTPClient http;
  http.begin(FLOWMIRROR_SIGNAL_URL);
  int status = http.GET();
  if (status != HTTP_CODE_OK) {
    http.end();
    showSafeFallback();
    return;
  }

  JsonDocument document;
  DeserializationError error = deserializeJson(document, http.getString());
  http.end();
  if (error) {
    showSafeFallback();
    return;
  }

  const char* phase = document["phase"] | "yellow";
  bool emergency = document["emergency_priority"] | false;
  if (emergency || strcmp(phase, "green") == 0) {
    setLights(false, false, true);
  } else if (strcmp(phase, "red") == 0) {
    setLights(true, false, false);
  } else {
    setLights(false, true, false);
  }
}

void setup() {
  pinMode(RED_PIN, OUTPUT);
  pinMode(YELLOW_PIN, OUTPUT);
  pinMode(GREEN_PIN, OUTPUT);
  setLights(false, true, false);
  connectWiFi();
}

void loop() {
  if (millis() - lastPollAt >= POLL_INTERVAL_MS) {
    lastPollAt = millis();
    updateSignal();
  }
}
