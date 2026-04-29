#include "HX711.h"

const int HX_DOUT = 8;
const int HX_SCK  = 9;

HX711 loadCell;

void setup() {
  Serial.begin(9600);
  loadCell.begin(HX_DOUT, HX_SCK);
}

void loop() {
  if (Serial.available()) {
    char cmd = Serial.read();

    Serial.print("Received: ");
    Serial.println(cmd);   // so you can see what you typed

    if (cmd == 'T' || cmd == 't') {
      delay(2000); // time to remove hand if touching
      loadCell.tare(10);
      Serial.println("Tare done");
    }

    if (cmd == 'R' || cmd == 'r') {
      if (loadCell.is_ready()) {
        long value = loadCell.get_value(5);
        Serial.println(value);
      } else {
        Serial.println("Not ready");
      }
    }
  }
}