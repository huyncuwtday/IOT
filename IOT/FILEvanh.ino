#include <WiFi.h>
#include <PubSubClient.h>

const char* ssid = "iPhone";
const char* password = "12345678";
const char* mqttServer = "172.20.10.2";
const int mqttPort = 1883;
const char* mqttUser = "admin";
const char* mqttPassword = "admin";
const char* mqttTopic = "IOT";

const int lightSensorPin = 5;    
const int relayPin = 18;         
const int lightPin = 2;          

bool autoMode = true;      
int prevLightStatus = -1;         
bool prevMode = true;            


WiFiClient espClient;
PubSubClient client(espClient);

void setup() {
  Serial.begin(115200);
  
  pinMode(lightSensorPin, INPUT);    
  pinMode(relayPin, OUTPUT);         
  pinMode(lightPin, OUTPUT);         
  digitalWrite(relayPin, HIGH);      
  digitalWrite(lightPin, LOW);       

  // Kết nối WiFi
  Serial.print("Đang kết nối WiFi");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    Serial.println(WiFi.status());  // In trạng thái kết nối WiFi
  }
  Serial.println("\nĐã kết nối WiFi");

  // Thiết lập MQTT
  client.setServer(mqttServer, mqttPort);
  client.setCallback(callback);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();
  
  if (autoMode) {
    int lightStatus = digitalRead(lightSensorPin);
    Serial.print("Trạng thái cảm biến ánh sáng: ");
    Serial.println(lightStatus);  
    
  
        
    if (lightStatus == HIGH) {
      digitalWrite(relayPin, HIGH);  
      digitalWrite(lightPin, LOW);    
      //Serial.println("Ánh sáng cao, tắt đèn.");
       client.publish(mqttTopic,  "{\"mode\": \"auto\", \"status\": \"ON\"}");
    } else {
      digitalWrite(relayPin, LOW);   
      digitalWrite(lightPin, HIGH);   
      //Serial.println("Ánh sáng thấp, bật đèn.");
       client.publish(mqttTopic,  "{\"mode\": \"auto\", \"status\": \"OFF\"}");
    }
  }
  
  delay(1000);
}

void callback(char* topic, byte* payload, unsigned int length) {
  char message[50];
  memcpy(message, payload, length);
  message[length] = '\0';
  
  Serial.print("Nhận lệnh: ");
  Serial.println(message);

  if (strcmp(message, "ON") == 0) {
    autoMode = false;  
    digitalWrite(relayPin, LOW);   
    digitalWrite(lightPin, LOW);
    Serial.println("Bật đèn (thủ công)");
    client.publish(mqttTopic,  "{\"mode\": \"manual\", \"status\": \"ON\"}");
  }
  else if (strcmp(message, "OFF") == 0) {
    autoMode = false;  
    digitalWrite(relayPin, HIGH);  
    digitalWrite(lightPin, HIGH);
    Serial.println("Tắt đèn (thủ công)");
  client.publish(mqttTopic,  "{\"mode\": \"manual\", \"status\": \"OFF\"}");
  }
  else if (strcmp(message, "AUTO") == 0) {
    autoMode = true;   
    Serial.println("Chuyển sang chế độ tự động");
  }
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Kết nối MQTT...");
    if (client.connect("ESP32Client", mqttUser, mqttPassword)) {
      Serial.println("đã kết nối");
      client.subscribe(mqttTopic);
    } else {
      Serial.print("lỗi, rc=");
      Serial.print(client.state());
      Serial.println(" Thử lại sau 5 giây");
      delay(5000);
    }
  }
}
