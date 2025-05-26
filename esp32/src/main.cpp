#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <time.h>

const char* ssid = "SEU_WIFI_SSID_AQUI";
const char* password = "SUA_SENHA_WIFI_AQUI";
const char* serverURL = "http://IP_DO_SEU_SERVIDOR_FLASK:PORTA/data";

#define DHT_PIN 2 
#define DHT_TYPE DHT11
DHT dht(DHT_PIN, DHT_TYPE);

unsigned long lastReadingTime = 0;
const unsigned long readingInterval = 30000;

#define LED_BUILTIN_PIN 2
bool ledState = false;

const long gmtOffset_sec = -3 * 3600;
const int daylightOffset_sec = 0;   

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n=== ESP32 Sensor de Temperatura e Umidade ===");
  
  dht.begin();
  Serial.println("Sensor DHT11 inicializado.");

  pinMode(LED_BUILTIN_PIN, OUTPUT);
  digitalWrite(LED_BUILTIN_PIN, LOW);
  
  connectToWiFi();
  
  Serial.println("Configurando NTP...");
  configTime(gmtOffset_sec, daylightOffset_sec, "pool.ntp.org", "time.nist.gov");
  printLocalTime();

  Serial.println("Sistema pronto para iniciar leituras!");
  Serial.println("=====================================\n");
}

void loop() {
  unsigned long currentTime = millis();
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi desconectado! Tentando reconectar...");
    digitalWrite(LED_BUILTIN_PIN, LOW); 
    connectToWiFi();
  }
  
  if (currentTime - lastReadingTime >= readingInterval) {
    blinkLED(1, 50);
    readSensorAndSend();
    lastReadingTime = currentTime;
  }
  
  delay(1000);
}

void connectToWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(LED_BUILTIN_PIN, HIGH);
    return;
  }

  Serial.print("Conectando ao WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi conectado com sucesso!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    digitalWrite(LED_BUILTIN_PIN, HIGH);
  } else {
    Serial.println("\nFalha ao conectar ao WiFi após várias tentativas.");
    digitalWrite(LED_BUILTIN_PIN, LOW);
  }
}

void printLocalTime(){
  struct tm timeinfo;
  if(!getLocalTime(&timeinfo)){
    Serial.println("Falha ao obter hora local do NTP.");
    return;
  }
  Serial.print("Hora local atual: ");
  Serial.println(&timeinfo, "%A, %B %d %Y %H:%M:%S");
}

void readSensorAndSend() {
  Serial.println("--- Nova Leitura ---");
  
  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature();
  
  if (isnan(humidity) || isnan(temperature)) {
    Serial.println("Erro: Falha na leitura do sensor DHT11!");
    sendErrorData("erro_sensor", "Falha na leitura do DHT11");
    return;
  }
  
  Serial.printf("Temperatura: %.1f C\n", temperature);
  Serial.printf("Umidade: %.1f %%\n", humidity);
  
  String status = determineDeviceStatus(temperature, humidity);
  Serial.printf("Status (dispositivo): %s\n", status.c_str());
  
  if (WiFi.status() == WL_CONNECTED) {
    sendDataToServer(temperature, humidity, status);
  } else {
    Serial.println("WiFi não conectado! Dados não enviados.");
  }
  
  Serial.println("--- Fim da Leitura ---\n");
}

String determineDeviceStatus(float temp, float hum) {
  if (temp > 40.0 || temp < 0.0) return "critico_temperatura";
  if (hum > 95.0 || hum < 10.0) return "critico_umidade";  
  if (temp > 30.0 || temp < 5.0) return "alerta_temperatura"; 
  if (hum > 90.0 || hum < 20.0) return "alerta_umidade";  
  return "normal";
}

void sendDataToServer(float temperature, float humidity, String status) {
  HTTPClient http;
  
  Serial.print("[HTTP] Iniciando requisição para: ");
  Serial.println(serverURL);
  http.begin(serverURL);
  http.addHeader("Content-Type", "application/json");

  DynamicJsonDocument doc(512); 
  doc["temperatura"] = temperature;
  doc["umidade"] = humidity;
  doc["device_id"] = "ESP32_DHT11_Device_01";

  struct tm timeinfo;
  if(getLocalTime(&timeinfo)){
    char timeStr[30];
    strftime(timeStr, sizeof(timeStr), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
    doc["timestamp"] = timeStr;
  } else {
    Serial.println("Não foi possível obter hora NTP para o timestamp. O servidor usará a hora de recebimento.");
  }

  String jsonPayload;
  serializeJson(doc, jsonPayload);
  
  Serial.print("[HTTP] Enviando JSON: ");
  Serial.println(jsonPayload);
  
  int httpResponseCode = http.POST(jsonPayload);
  
  if (httpResponseCode > 0) {
    String responsePayload = http.getString();
    Serial.printf("[HTTP] Código de Resposta: %d\n", httpResponseCode);
    Serial.printf("[HTTP] Resposta do Servidor: %s\n", responsePayload.c_str());
    
    if (httpResponseCode == 200 || httpResponseCode == 201) {
      Serial.println("Dados enviados com sucesso!");
      blinkLED(3, 100);
    } else {
      Serial.println("Erro no envio, resposta do servidor não foi OK.");
      blinkLED(5, 200);
    }
  } else {
    Serial.printf("[HTTP] Falha na requisição POST, erro: %s\n", http.errorToString(httpResponseCode).c_str());
    blinkLED(10, 50);
  }
  
  http.end();
}

void sendErrorData(String errorType, String errorMessage) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi não conectado! Erro do sensor não reportado ao servidor.");
    return;
  }
  
  HTTPClient http;
  http.begin(serverURL);
  http.addHeader("Content-Type", "application/json");

  DynamicJsonDocument doc(300);
  doc["status"] = errorType;
  doc["message"] = errorMessage;
  doc["device_id"] = "ESP32_DHT11_Device_01";
  
  struct tm timeinfo;
  if(getLocalTime(&timeinfo)){
    char timeStr[30];
    strftime(timeStr, sizeof(timeStr), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
    doc["timestamp"] = timeStr;
  }

  String jsonPayload;
  serializeJson(doc, jsonPayload);
  
  Serial.println("Enviando dados de erro para o servidor...");
  Serial.print("JSON de Erro: ");
  Serial.println(jsonPayload);
  
  int httpResponseCode = http.POST(jsonPayload);
  
  if (httpResponseCode > 0) {
    Serial.printf("[HTTP] Código de Resposta (erro): %d\n", httpResponseCode);
    Serial.printf("[HTTP] Resposta do Servidor (erro): %s\n", http.getString().c_str());
  } else {
    Serial.printf("[HTTP] Falha na requisição POST (erro), erro: %s\n", http.errorToString(httpResponseCode).c_str());
  }
  
  http.end();
}

void blinkLED(int times, int blinkDelay) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_BUILTIN_PIN, !digitalRead(LED_BUILTIN_PIN));
    delay(blinkDelay);
    digitalWrite(LED_BUILTIN_PIN, !digitalRead(LED_BUILTIN_PIN)); 
    if (i < times - 1) delay(blinkDelay); 
  }
  if(WiFi.status() == WL_CONNECTED){
    digitalWrite(LED_BUILTIN_PIN, HIGH);
  } else {
    digitalWrite(LED_BUILTIN_PIN, LOW);
  }
}