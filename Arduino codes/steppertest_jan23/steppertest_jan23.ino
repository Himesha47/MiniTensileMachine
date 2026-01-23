#define STEP_PIN 3
#define DIR_PIN  4
#define EN_PIN   5

void setup() {
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(EN_PIN, OUTPUT);

  digitalWrite(EN_PIN, LOW);   // enable
  digitalWrite(DIR_PIN, HIGH);
}

void loop() {
  for (int i = 0; i < 200; i++) {
    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(1000);
    digitalWrite(STEP_PIN, LOW);
    delayMicroseconds(1000);
  }

  delay(1000);

  digitalWrite(DIR_PIN, !digitalRead(DIR_PIN));
  delay(500);
}
