#include "HX711.h"

const int HX_DOUT = 3;
const int HX_SCK  = 2;

HX711 loadCell;

void waitForReady() {
  unsigned long t0 = millis();
  while (!loadCell.is_ready()) {
    if (millis() - t0 > 500) {
      Serial.println("Waiting for HX711...");
      t0 = millis();
    }
  }
}

void setup() {
  Serial.begin(9600);
  delay(1000);

  Serial.println("Starting...");
  loadCell.begin(HX_DOUT, HX_SCK);

  Serial.print("Initial ready state: ");
  Serial.println(loadCell.is_ready());

  Serial.println("Manual tare: averaging 20 samples");

  long sum = 0;
  const int samples = 20;

  for (int i = 0; i < samples; i++) {
    waitForReady();
    long v = loadCell.read();
    sum += v;

    Serial.print("Sample ");
    Serial.print(i);
    Serial.print(" = ");
    Serial.println(v);

    delay(50);
  }

  long offset = sum / samples;
  Serial.print("Calculated offset = ");
  Serial.println(offset);

  loadCell.set_offset(offset);
  Serial.println("Offset set.");
}

void loop() {
  waitForReady();
  long raw = loadCell.read();

  Serial.print("Raw (after tare) = ");
  Serial.println(raw);

  delay(500);
}
