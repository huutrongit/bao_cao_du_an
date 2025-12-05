#define BLYNK_TEMPLATE_ID "TMPL6zO9l5gzc"
#define BLYNK_TEMPLATE_NAME "Tronggia"
#define BLYNK_AUTH_TOKEN "UtiVCWiqcljxtzyhaGdRDcGJdbnRhXSt"
#define BLYNK_PRINT Serial

#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <BlynkSimpleEsp32.h>
#include <DHT.h>
#include <ESP_Mail_Client.h>
#include <SimpleTimer.h>

#define DHTTYPE DHT22
#define dht_dpin 13
int b3 = 17; // phun sương
int b5 = 12; // đèn

DHT dht(dht_dpin, DHTTYPE);
SimpleTimer timer;

char auth[] = BLYNK_AUTH_TOKEN;
char ssid[] = "Bui Huu Trong";
char pass[] = "09022008";

// SMTP
#define AUTHOR_EMAIL "trong49buihuu@gmail.com"
#define AUTHOR_PASSWORD "rtld qkbd svsw rbgb"
#define RECIPIENT_EMAIL "vitdz99@gmail.com"

SMTPSession smtp;
WebServer server(8080);

// Biến toàn cục
bool manualMist = false;
bool manualLight = false;
bool systemBusy = false;
unsigned long lastDetectionTime = 0;
unsigned long lastPeriodicEmail = 0; // Thêm: thời gian gửi email định kỳ cuối
String currentStage = "PHOI";
bool hasSpoiledMushroom = false;
String spoiledLocation = "Không";

// Cấu hình
const unsigned long DETECTION_INTERVAL = 300000;    // 5 phút
const unsigned long BUSY_COOLDOWN = 30000;         // 30 giây
const unsigned long PERIODIC_EMAIL_INTERVAL = 180000; // 3 phút cho email định kỳ
String piServerIP = "http://172.20.10.5:2177";     // SỬA IP THẬT CỦA PI

// ========== HÀM TIỆN ÍCH ==========
String getCurrentTime() {
  unsigned long ms = millis();
  unsigned long seconds = ms / 1000;
  unsigned long minutes = seconds / 60;
  seconds %= 60;
  
  char timeStr[20];
  sprintf(timeStr, "%02lu:%02lu:%02lu", minutes / 60, minutes % 60, seconds % 60);
  return String(timeStr);
}

String readDHT() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();
  
  if (isnan(h) || isnan(t)) {
    return "LỖI: Không đọc được cảm biến DHT";
  }
  
  char result[50];
  sprintf(result, "Nhiệt độ: %.1f°C\nĐộ ẩm: %.1f%%", t, h);
  return String(result);
}

String createFullReport(String action = "", String details = "") {
  String report = "HỆ THỐNG TRỒNG NẤM THÔNG MINH\n";
  report += "══════════════════════════════\n\n";
  
  report += "Thời gian: " + getCurrentTime() + "\n\n";
  
  if (action != "") {
    report += "HÀNH ĐỘNG: " + action + "\n";
    if (details != "") report += "Chi tiết: " + details + "\n";
    report += "\n";
  }
  
  report += "📊 TRẠNG THÁI HỆ THỐNG\n\n";
  
  unsigned long uptime = millis() / 1000;
  report += "Uptime: " + String(uptime / 60) + " phút " + String(uptime % 60) + " giây\n\n";
  
  report += "🌡️ MÔI TRƯỜNG:\n" + readDHT() + "\n\n";
  
  report += "⚙️ THIẾT BỊ:\n";
  report += "• Phun sương: " + String(digitalRead(b3) ? "✅ BẬT" : "❌ TẮT") + "\n";
  report += "• Đèn: " + String(digitalRead(b5) ? "✅ BẬT" : "❌ TẮT") + "\n\n";
  
  report += "🎮 CHẾ ĐỘ:\n";
  report += "• Phun sương: " + String(manualMist ? "👤 USER" : "🤖 AUTO") + "\n";
  report += "• Đèn: " + String(manualLight ? "👤 USER" : "🤖 AUTO") + "\n";
  report += "• Hệ thống: " + String(systemBusy ? "⏳ BẬN" : "✅ RẢNH") + "\n\n";
  
  report += "🍄 THÔNG TIN NẤM:\n";
  report += "• Giai đoạn: " + currentStage + "\n";
  report += "• Nấm hư: " + String(hasSpoiledMushroom ? "🚨 CÓ" : "✅ KHÔNG") + "\n";
  if (hasSpoiledMushroom) {
    report += "• Vị trí: " + spoiledLocation + "\n";
  }
  
  report += "\n══════════════════════════════\n";
  return report;
}

// ========== EMAIL ==========
void sendEmail(String subject, String content = "") {
  Serial.println("[EMAIL] 📤 " + subject);
  
  if (content == "") content = createFullReport();
  
  ESP_Mail_Session session;
  session.server.host_name = "smtp.gmail.com";
  session.server.port = 465;
  session.login.email = AUTHOR_EMAIL;
  session.login.password = AUTHOR_PASSWORD;
  
  SMTP_Message message;
  message.sender.name = "Hệ thống trồng nấm";
  message.sender.email = AUTHOR_EMAIL;
  message.subject = subject;
  message.addRecipient("Admin", RECIPIENT_EMAIL);
  message.text.content = content.c_str();
  message.text.charSet = "utf-8";
  message.text.transfer_encoding = Content_Transfer_Encoding::enc_7bit;
  
  if (!smtp.connect(&session)) {
    Serial.println("[EMAIL] ❌ Kết nối thất bại");
    return;
  }
  
  if (!MailClient.sendMail(&smtp, &message)) {
    Serial.println("[EMAIL] ❌ Gửi thất bại");
  } else {
    Serial.println("[EMAIL] ✅ Đã gửi");
  }
  
  smtp.closeSession();
}

// ========== ĐIỀU KHIỂN THIẾT BỊ ==========
void setMist(bool state, String reason) {
  if (manualMist) {
    Serial.println("[AUTO] ⚠️ Không thể điều khiển phun - User đang giữ quyền");
    return;
  }
  
  digitalWrite(b3, state ? HIGH : LOW);
  Serial.println("[AUTO] 🤖 " + String(state ? "✅ BẬT" : "❌ TẮT") + " phun sương (" + reason + ")");
  
  String report = createFullReport(
    "Hệ thống " + String(state ? "BẬT" : "TẮT") + " phun sương",
    "Lý do: " + reason
  );
  sendEmail("ĐIỀU KHIỂN PHUN SƯƠNG", report);
}

void setLight(bool state, String reason) {
  if (manualLight) {
    Serial.println("[AUTO] ⚠️ Không thể điều khiển đèn - User đang giữ quyền");
    return;
  }
  
  digitalWrite(b5, state ? HIGH : LOW);
  Serial.println("[AUTO] 🤖 " + String(state ? "✅ BẬT" : "❌ TẮT") + " đèn (" + reason + ")");
  
  String report = createFullReport(
    "Hệ thống " + String(state ? "BẬT" : "TẮT") + " đèn",
    "Lý do: " + reason
  );
  sendEmail("ĐIỀU KHIỂN ĐÈN", report);
}

// ========== XỬ LÝ KẾT QUẢ NẤM ==========
void processMushroomStage(String stage, String region) {
  Serial.println("\n[PI] 📥 KẾT QUẢ TỪ RASPBERRY PI");
  Serial.println("Giai đoạn: " + stage);
  if (region != "" && region != "none") Serial.println("Vị trí: " + region);
  
  currentStage = stage;
  hasSpoiledMushroom = (stage == "HU");
  spoiledLocation = (stage == "HU" && region != "" && region != "none") ? region : "Không";
  
  if (manualMist || manualLight) {
    Serial.println("[HỆ THỐNG] 👤 User đang điều khiển, bỏ qua auto");
    return;
  }
  
  if (stage == "NON") {
    Serial.println("[HỆ THỐNG] 🍄 Phát hiện nấm NON");
    setLight(true, "Nấm NON cần chiếu sáng");
    setMist(true, "Nấm NON cần độ ẩm");
    
    timer.setTimeout(60000, []() { setMist(false, "Đủ độ ẩm cho NON"); });
    timer.setTimeout(120000, []() { setLight(false, "Đủ ánh sáng cho NON"); });
    
  } else if (stage == "TRUONG-THANH") {
    Serial.println("[HỆ THỐNG] 🍄 Phát hiện nấm TRƯỞNG THÀNH");
    setLight(true, "Nấm trưởng thành cần ánh sáng");
    setMist(true, "Nấm trưởng thành cần độ ẩm");
    
    timer.setTimeout(90000, []() { setMist(false, "Đủ độ ẩm cho trưởng thành"); });
    timer.setTimeout(180000, []() { setLight(false, "Đủ ánh sáng cho trưởng thành"); });
    
  } else if (stage == "HU") {
    Serial.println("[HỆ THỐNG] 🚨 PHÁT HIỆN NẤM HƯ!");
    
    if (region != "" && region != "none") {
      Serial.println("[CẢNH BÁO] 📍 Nấm hư ở: " + region);
    }
    
    String warning = createFullReport(
      "🚨 CẢNH BÁO: PHÁT HIỆN NẤM HƯ",
      "Vị trí: " + region + "\nHệ thống tự động xử lý"
    );
    sendEmail("🚨 CẢNH BÁO NẤM HƯ", warning);
    
    setMist(true, "Xử lý nấm hư");
    timer.setTimeout(120000, []() { setMist(false, "Hoàn tất xử lý nấm hư"); });
    
  } else { // PHOI hoặc unknown
    Serial.println("[HỆ THỐNG] 🍄 Giai đoạn PHÔI");
    setMist(true, "Nấm phôi cần độ ẩm");
    timer.setTimeout(60000, []() { setMist(false, "Đủ độ ẩm cho phôi"); });
  }
}

// ========== XỬ LÝ JSON ==========
String extractJSONValue(String json, String key) {
  int keyIndex = json.indexOf("\"" + key + "\":");
  if (keyIndex == -1) return "";
  
  int valueStart = json.indexOf("\"", keyIndex + key.length() + 2);
  if (valueStart == -1) return "";
  
  int valueEnd = json.indexOf("\"", valueStart + 1);
  if (valueEnd == -1) return "";
  
  return json.substring(valueStart + 1, valueEnd);
}

// ========== KIỂM TRA HỆ THỐNG ==========
bool isSystemReadyForDetection() {
  if (systemBusy) {
    Serial.println("[MASTER] ⏳ Hệ thống đang bận...");
    return false;
  }
  
  if (millis() - lastDetectionTime < DETECTION_INTERVAL) {
    unsigned long remaining = (DETECTION_INTERVAL - (millis() - lastDetectionTime)) / 1000;
    if (remaining > 60) {
      Serial.print("[MASTER] ⏰ Còn ");
      Serial.print(remaining / 60);
      Serial.println(" phút");
    }
    return false;
  }
  
  if (manualMist || manualLight) {
    Serial.println("[MASTER] 👤 User đang điều khiển");
    return false;
  }
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[MASTER] 📶 WiFi không ổn định");
    return false;
  }
  
  return true;
}

// ========== GỌI PI ==========
void callPiForDetection() {
  Serial.println("\n[MASTER] 📞 ĐANG GỌI PI...");
  systemBusy = true;
  
  HTTPClient http;
  String url = piServerIP + "/detect";
  http.begin(url);
  http.setTimeout(15000);
  
  int httpCode = http.GET();
  
  if (httpCode == 200) {
    String payload = http.getString();
    Serial.println("[MASTER] ✅ PI phản hồi:");
    Serial.println(payload);
    
    String classification = extractJSONValue(payload, "class");
    String region = extractJSONValue(payload, "region");
    
    if (classification == "") classification = "PHOI";
    if (region == "") region = "";
    
    processMushroomStage(classification, region);
    lastDetectionTime = millis();
    
  } else if (httpCode == -1) {
    Serial.println("[MASTER] ❌ Pi không phản hồi");
  } else {
    Serial.print("[MASTER] ❌ Lỗi HTTP: ");
    Serial.println(httpCode);
  }
  
  http.end();
  
  timer.setTimeout(BUSY_COOLDOWN, []() {
    systemBusy = false;
    Serial.println("[MASTER] 🆓 Hệ thống sẵn sàng");
  });
}

// ========== KIỂM TRA ĐỊNH KỲ ==========
void checkAndCallPi() {
  if (isSystemReadyForDetection()) {
    callPiForDetection();
  }
}

// ========== KIỂM TRA MÔI TRƯỜNG VÀ GỬI EMAIL ĐỊNH KỲ ==========
void checkEnvironment() {
  Serial.println("\n[ENV] 🔍 Kiểm tra môi trường");
  
  String dhtReading = readDHT();
  Serial.println("[ENV] " + dhtReading);
  
  // GỬI EMAIL ĐỊNH KỲ 3 PHÚT/LẦN
  if (millis() - lastPeriodicEmail >= PERIODIC_EMAIL_INTERVAL) {
    Serial.println("[EMAIL] 📧 Gửi email định kỳ 3 phút");
    sendEmail("📊 BÁO CÁO ĐỊNH KỲ 3 PHÚT", createFullReport("📊 BÁO CÁO ĐỊNH KỲ", "Hệ thống tự động gửi 3 phút/lần"));
    lastPeriodicEmail = millis();
  }
  
  if (!dhtReading.startsWith("LỖI")) {
    float t, h;
    if (sscanf(dhtReading.c_str(), "Nhiệt độ: %f°C\nĐộ ẩm: %f%%", &t, &h) == 2) {
      
      if (!manualMist && !manualLight) {
        if (t > 32.0 || h < 60.0) {
          setMist(true, "Nhiệt độ cao/độ ẩm thấp");
          timer.setTimeout(60000, []() { setMist(false, "Đủ thời gian làm mát"); });
        } else if (t < 24.0) {
          setLight(true, "Nhiệt độ thấp");
          timer.setTimeout(60000, []() { setLight(false, "Đủ thời gian sưởi ấm"); });
        }
      }
    }
  }
}

// ========== WEB SERVER HANDLERS ==========
void handleData() {
  String classification = server.arg("class");
  String region = server.arg("region");
  
  if (classification.length() == 0) classification = "PHOI";
  if (region.length() == 0) region = "";
  
  processMushroomStage(classification, region);
  server.send(200, "text/plain", "OK");
}

// ========== BLYNK CALLBACKS ==========
BLYNK_CONNECTED() {
  Blynk.syncAll();
  Serial.println("[BLYNK] ✅ Đã kết nối");
}

BLYNK_WRITE(V3) {
  int value = param.asInt();
  manualMist = true;
  digitalWrite(b3, value ? HIGH : LOW);
  Serial.println("[USER] 👤 " + String(value ? "✅ BẬT" : "❌ TẮT") + " phun sương");
}

BLYNK_WRITE(V2) {
  int value = param.asInt();
  manualLight = true;
  digitalWrite(b5, value ? HIGH : LOW);
  Serial.println("[USER] 👤 " + String(value ? "✅ BẬT" : "❌ TẮT") + " đèn");
}

BLYNK_WRITE(V4) {
  int value = param.asInt();
  if (value == 1) {
    manualMist = false;
    manualLight = false;
    Serial.println("[USER] 🔄 Trả quyền cho hệ thống tự động");
    sendEmail("🔄 RESET CHẾ ĐỘ ĐIỀU KHIỂN", createFullReport("USER RESET VỀ CHẾ ĐỘ TỰ ĐỘNG"));
    Blynk.virtualWrite(V4, 0);
  }
}

// ========== SETUP ==========
void setup() {
  Serial.begin(115200);
  Serial.println("\n══════════════════════════════");
  Serial.println("🚀 HỆ THỐNG TRỒNG NẤM THÔNG MINH");
  Serial.println("══════════════════════════════");
  
  pinMode(b3, OUTPUT);
  pinMode(b5, OUTPUT);
  digitalWrite(b3, LOW);
  digitalWrite(b5, LOW);
  
  Serial.print("[WIFI] 📶 Đang kết nối...");
  WiFi.begin(ssid, pass);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WIFI] ✅ Đã kết nối");
    Serial.print("[WIFI] 📡 IP: ");
    Serial.println(WiFi.localIP().toString());
    Serial.print("[WIFI] 📡 PI Server: ");
    Serial.println(piServerIP);
  } else {
    Serial.println("\n[WIFI] ❌ Thất bại");
  }
  
  Blynk.begin(auth, ssid, pass);
  dht.begin();
  
  server.on("/data", handleData);
  server.begin();
  Serial.println("[SERVER] 🌐 Web server port 8080");
  
  sendEmail("🚀 HỆ THỐNG KHỞI ĐỘNG");
  
  timer.setInterval(180000, checkEnvironment);    // 3 phút kiểm tra môi trường và gửi email
  timer.setInterval(10000, checkAndCallPi);       // 10 giây kiểm tra gọi Pi
  
  Serial.println("\n⏰ Timer đã thiết lập:");
  Serial.println("  - 3 phút: Kiểm tra môi trường & Gửi email định kỳ");
  Serial.println("  - 10 giây: Kiểm tra gọi Pi");
  Serial.println("  - 5 phút: Khoảng cách giữa các lần detect");
  
  Serial.println("\n✅ HỆ THỐNG SẴN SÀNG!");
  Serial.println("══════════════════════════════");
}

// ========== LOOP ==========
void loop() {
  Blynk.run();
  timer.run();
  server.handleClient();
  
  static unsigned long lastUpdate = 0;
  if (millis() - lastUpdate > 2000) {
    lastUpdate = millis();
    
    float h = dht.readHumidity();
    float t = dht.readTemperature();
    
    if (!isnan(h) && !isnan(t)) {
      Blynk.virtualWrite(V0, t);
      Blynk.virtualWrite(V1, h);
    }
  }
}