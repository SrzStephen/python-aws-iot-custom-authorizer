#include <Arduino.h>
#include <secrets.h>
#ifdef ESP32
#include <WiFi.h>
#elif defined(ESP8266)
#include <ESP8266WiFi.h>
#endif
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
WiFiClientSecure secure_client = WiFiClientSecure();
PubSubClient mqttClient = PubSubClient(secure_client);
const char *aws_protos[] = {"mqtt", NULL};
String testPublishString = String(mqtt_client_id) + String(" test message");

String mqtt_modified_username(const char * username)
{
  // AWS requires x-amz-customauthorizer-name along with username
  // note the mqtt_custom_authorizer name should probably be URL encoded.
  return String(username) + String("?x-amz-customauthorizer-name=") 
  + String(mqtt_custom_authorizer_name);
}

void setup_wifi()
{
  WiFi.begin(wifi_name, wifi_pass); 
  while (WiFi.status() !=WL_CONNECTED )
   {
     Serial.println("Failed to connect to WiFi");
     Serial.println(WiFi.status());
     sleep(5);
   }
   Serial.println("connected");
}

void setup_mqtt()
{
  secure_client.setCACert(CA_CERT);
  secure_client.setAlpnProtocols(aws_protos);
  mqttClient.setSocketTimeout(10);
  mqttClient.setServer(mqtt_ats_endpoint,443);
  mqttClient.setKeepAlive(60);
  while(!mqttClient.connected())
  {

    mqttClient.connect(mqtt_client_id,mqtt_modified_username(mqtt_username).c_str(),mqtt_password);
      Serial.println("Failed to connect to MQTT");
      sleep(5);
  }
  Serial.println("Connected to MQTT");
}

void setup() {
  Serial.begin(9600);
  setup_wifi();
  setup_mqtt();
}

void loop() {
  sleep(200);
  mqttClient.publish(mqtt_publish_topic,testPublishString.c_str());
}