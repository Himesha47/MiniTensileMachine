#define STEP_PIN 3
#define DIR_PIN 4
#define ENABLE_PIN 8

void setup() {
  Serial.begin(9600);
  Serial.println("Type 'start' or 'stop'");

  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(ENABLE_PIN, OUTPUT);

  digitalWrite(DIR_PIN, HIGH);    // fixed direction
  digitalWrite(ENABLE_PIN, HIGH); // disable motor at power-up
}

void loop() {

  // Read command from serial
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');

    if (cmd == "start") {
      digitalWrite(ENABLE_PIN, LOW);  // enable driver
      Serial.println("Motor Started");
    }
    else if (cmd == "stop") {
      digitalWrite(ENABLE_PIN, HIGH); // disable driver
      Serial.println("Motor Stopped");
    }
  }

  // Run motor if enabled
  if (digitalRead(ENABLE_PIN) == LOW) {
    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(300);
    digitalWrite(STEP_PIN, LOW);
    delayMicroseconds(300);
  }
}
