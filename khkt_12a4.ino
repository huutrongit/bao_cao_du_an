#define BLYNK_TEMPLATE_ID "TMPL6zO9l5gzc"
#define BLYNK_TEMPLATE_NAME "Tronggia"
#define BLYNK_AUTH_TOKEN "UtiVCWiqcljxtzyhaGdRDcGJdbnRhXSt"
#define BLYNK_PRINT Serial

#include <WiFi.h>
#include <BlynkSimpleEsp32.h>

char auth[] = BLYNK_AUTH_TOKEN;
char ssid[] = "Bui Huu Trong";
char pass[] = "09022008";

// Chân điều khiển thiết bị
int b3 = 17; // phun sương
int b5 = 12; // đèn

BLYNK_CONNECTED() {
  Blynk.syncAll();
}

// Blynk điều khiển phun sương
BLYNK_WRITE(V3) {
  int value = param.asInt();
  digitalWrite(b3, value ? HIGH : LOW);
  Serial.println(value ? "Đã bật phun sương (Blynk)" : "Đã tắt phun sương (Blynk)");
}

// Blynk điều khiển đèn
BLYNK_WRITE(V2) {
  int value = param.asInt();
  digitalWrite(b5, value ? HIGH : LOW);
  Serial.println(value ? "Đã bật đèn (Blynk)" : "Đã tắt đèn (Blynk)");
}

void setup() {
  Serial.begin(115200);
  pinMode(b3, OUTPUT);
  pinMode(b5, OUTPUT);

  digitalWrite(b3, LOW);
  digitalWrite(b5, LOW);

  Blynk.begin(auth, ssid, pass);
}

void loop() {
  Blynk.run();
}
