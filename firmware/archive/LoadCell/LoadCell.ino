#include "HX711.h"

const int HX_DOUT = 8;
const int HX_SCK  = 9;

HX711 scale;

void setup() {
  Serial.begin(9600);
  delay(1000);

  Serial.println("Starting HX711 test...");
  scale.begin(HX_DOUT, HX_SCK);

  Serial.println("Taring...");
  scale.tare();
  Serial.println("Tare done");
}

void loop() {
  if (scale.is_ready()) {
    long raw = scale.read();

    Serial.print("Raw value: ");
    Serial.println(raw);
  } else {
    Serial.println("HX711 not ready");
  }

  delay(500);
}