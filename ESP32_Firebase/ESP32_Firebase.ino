#include <WiFi.h>
#include <FirebaseESP32.h>
#include <HardwareSerial.h>
#include <ESP32Servo.h>
#include "time.h"

/* ----------------------------------------------------
   WIFI
---------------------------------------------------- */
const char* ssid = "temp";
const char* password = "temp123456";

/* ----------------------------------------------------
   FIREBASE
---------------------------------------------------- */
#define FIREBASE_HOST "binlevel-bd0a6-default-rtdb.firebaseio.com"
#define FIREBASE_AUTH "nWuCtVVLpiZz6ROFPspuAKLjNhNx12KHrNgAbEGr"

FirebaseData fbdo;
FirebaseAuth auth;
FirebaseConfig config;

/* ----------------------------------------------------
   ULTRASONIC
---------------------------------------------------- */
#define TRIG1 32
#define ECHO1 33

#define TRIG2 25
#define ECHO2 26

/* ----------------------------------------------------
   SERVO
---------------------------------------------------- */
Servo servo1;  // BIO
Servo servo2;  // NONBIO

/* ----------------------------------------------------
   GSM
---------------------------------------------------- */
HardwareSerial gsm(2);
#define GSM_RX 16
#define GSM_TX 17

/* ----------------------------------------------------
   BUZZER
---------------------------------------------------- */
#define BUZZER_PIN 2

/* ----------------------------------------------------
   NTP TIME (IST)
---------------------------------------------------- */
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 19800; 
const int daylightOffset_sec = 0;

/* Flags */
bool sms_bin_sent = false;
bool sms_bio_sent = false;
bool sms_nonbio_sent = false;

unsigned long lastSave = 0;
unsigned long saveInterval = 10000;  // 10 seconds

/* ----------------------------------------------------
   SEND SMS
---------------------------------------------------- */
void sendSMS(String msg) {
  Serial.println("Preparing to send SMS...");
  
  // 1. Clear any leftover data in the serial buffer
  while(gsm.available()) gsm.read();

  // 2. Wake up the module and synchronize baud rate
  gsm.println("AT");
  delay(500);

  // 3. Set SMS mode to Text Mode
  gsm.println("AT+CMGF=1");
  delay(500);

  // 4. Send the recipient phone number
  gsm.println("AT+CMGS=\"+917305587959\"");
  
  // CRITICAL: SIM900A needs time to process the number and reply with the '>' prompt
  delay(1000); 

  // 5. Send the actual message text
  gsm.print(msg);
  delay(100);
  
  // 6. Send Ctrl+Z (ASCII 26) to tell the module to send the message
  gsm.write(26);
  
  // 7. Network transmission takes time. Wait 5 seconds to ensure it sends completely.
  delay(5000); 

  // 8. Print any response from the module to help debugging
  Serial.print("Module Response: ");
  while(gsm.available()) {
    Serial.write(gsm.read());
  }

  Serial.println("\n📨 SMS ATTEMPT FINISHED: " + msg);
}

/* ----------------------------------------------------
   ULTRASONIC READ
---------------------------------------------------- */
long getDistance(int trig, int echo) {
  digitalWrite(trig, LOW);
  delayMicroseconds(3);

  digitalWrite(trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig, LOW);

  long duration = pulseIn(echo, HIGH, 30000);
  if (duration == 0) return 400;

  float distance = duration * 0.0343 / 2.0;
  return constrain(distance, 0, 400);
}

/* ----------------------------------------------------
   ONE-TIME SERVO ROTATION
---------------------------------------------------- */
void rotateServoOnce(Servo &servo, String name) {
  Serial.println("🔄 Rotating Servo : " + name);

  servo.write(90);
  delay(1200);
  servo.write(0);

  Serial.println("✔ Servo Returned to 0° (" + name + ")");
}

/* ----------------------------------------------------
   SETUP
---------------------------------------------------- */
void setup() {
  Serial.begin(115200);
  gsm.begin(9600, SERIAL_8N1, GSM_RX, GSM_TX);

  pinMode(TRIG1, OUTPUT);
  pinMode(ECHO1, INPUT);
  pinMode(TRIG2, OUTPUT);
  pinMode(ECHO2, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  servo1.attach(13);
  servo2.attach(12);

  servo1.write(0);
  servo2.write(0);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    Serial.println("Connecting WiFi...");
    delay(300);
  }
  Serial.println("✅ WiFi Connected!");

  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  delay(1500);

  config.database_url = FIREBASE_HOST;
  config.signer.tokens.legacy_token = FIREBASE_AUTH;
  Firebase.begin(&config, &auth);
  Firebase.reconnectWiFi(true);

  Serial.println("🚀 ESP32 READY");
}

/* ----------------------------------------------------
   LOOP
---------------------------------------------------- */
void loop() {

  /* READ DISTANCES */
  long d1 = getDistance(TRIG1, ECHO1);
  long d2 = getDistance(TRIG2, ECHO2);

  int bin1 = constrain(map(d1, 20, 0, 0, 100), 0, 100);
  int bin2 = constrain(map(d2, 20, 0, 0, 100), 0, 100);

  /* PRINT VALUES */
  Serial.println("----------------------------------------------------");
  Serial.print("Bin1 Distance: "); Serial.print(d1); Serial.print(" cm | Level: "); Serial.print(bin1); Serial.println("%");
  Serial.print("Bin2 Distance: "); Serial.print(d2); Serial.print(" cm | Level: "); Serial.print(bin2); Serial.println("%");
  Serial.println("----------------------------------------------------");

  /* UPDATE FIREBASE */
  Firebase.setInt(fbdo, "/SMARTBIN/LIVE/BIN1", bin1);
  Firebase.setInt(fbdo, "/SMARTBIN/LIVE/BIN2", bin2);

  /* ----------------------------------------------------
     PYTHON DETECTION SIGNAL
  ---------------------------------------------------- */
  if (Firebase.getString(fbdo, "/SMARTBIN/DETECTION")) {

    String cmd = fbdo.stringData();
    Serial.println("🔥 DETECTION CMD RECEIVED: " + cmd);

    if (cmd == "BIO") {
      rotateServoOnce(servo1, "BIO");
      if (!sms_bio_sent) {
        sendSMS("BIO waste detected.");
        sms_bio_sent = true;
      }
      Firebase.setString(fbdo, "/SMARTBIN/DETECTION", "NONE");
    }

    if (cmd == "NONBIO") {
      rotateServoOnce(servo2, "NONBIO");
      if (!sms_nonbio_sent) {
        sendSMS("NONBIO waste detected.");
        sms_nonbio_sent = true;
      }
      Firebase.setString(fbdo, "/SMARTBIN/DETECTION", "NONE");
    }
  }

  /* ----------------------------------------------------
     HIGH BIN ALERT
  ---------------------------------------------------- */
  if (bin1 >= 80 || bin2 >= 80) {
    digitalWrite(BUZZER_PIN, HIGH);

    if (!sms_bin_sent) {
      sendSMS("⚠ ALERT: Bin Level reached 80%!");
      sms_bin_sent = true;
    }
  } else {
    digitalWrite(BUZZER_PIN, LOW);
    sms_bin_sent = false;
    sms_bio_sent = false;
    sms_nonbio_sent = false;
  }

  /* ----------------------------------------------------
     SAVE HISTORICAL LOG
  ---------------------------------------------------- */
  static int prev1 = -1, prev2 = -1;

  if (millis() - lastSave >= saveInterval) {
    lastSave = millis();

    if (bin1 != prev1 || bin2 != prev2) {

      time_t now;
      time(&now);

      String base = "/SMARTBIN/DATABASE/" + String((long)now);

      Firebase.setInt(fbdo, base + "/BIN1", bin1);
      Firebase.setInt(fbdo, base + "/BIN2", bin2);

      prev1 = bin1;
      prev2 = bin2;

      Serial.println("📌 HISTORY SAVED to Firebase");
    }
  }

  delay(200);
}