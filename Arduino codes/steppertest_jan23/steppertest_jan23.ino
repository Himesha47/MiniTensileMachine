// A4988 + NEMA17 Spin Test (NO MS pins in code)
// STEP->D3, DIR->D4, EN->D5 (or tie EN to GND)

#define STEP_PIN 3
#define DIR_PIN  4
#define EN_PIN   5

void stepPulse(int us) {
  digitalWrite(STEP_PIN, HIGH);
  delayMicroseconds(us);
  digitalWrite(STEP_PIN, LOW);
  delayMicroseconds(us);
}

void setup() {
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(EN_PIN, OUTPUT);

  digitalWrite(EN_PIN, LOW);     // enable driver
  digitalWrite(DIR_PIN, HIGH);   // initial direction
}

void loop() {
  for (int i = 0; i < 200; i++) {  // 200 full steps = ~1 rev
    stepPulse(1200);
  }

  delay(1000);

  digitalWrite(DIR_PIN, !digitalRead(DIR_PIN)); // reverse
  delay(500);
}
