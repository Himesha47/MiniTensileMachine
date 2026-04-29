#include "HX711.h"

const int HX_DOUT = 8;   // DT -> D8
const int HX_SCK  = 9;   // SCK -> D9
HX711 loadCell;

void setup() {
  Serial.begin(9600);
  delay(500);
  loadCell.begin(HX_DOUT, HX_SCK);
  Serial.println("HX711 BASIC TEST");
}

void loop() {
  if (loadCell.is_ready()) {
    long raw = loadCell.read();
    Serial.println(raw);
  } else {
    Serial.println("NOT READY");
  }
  delay(200);
}
