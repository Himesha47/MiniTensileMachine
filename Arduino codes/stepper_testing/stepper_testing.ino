// Pin Definitions
#define STEP_PIN 3     
#define DIR_PIN 4      
#define ENABLE_PIN 8   // connect EN pin to D8 (optional)

void setup() {
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(ENABLE_PIN, OUTPUT);

  digitalWrite(ENABLE_PIN, LOW);   // LOW = enable driver
  digitalWrite(DIR_PIN, HIGH);     // initial direction
}

void loop() {
  // Rotate 1 full revolution (about 1600 steps at 1/8 microstepping)
  for (int i = 0; i < 1600; i++) {
    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(600);    // speed: increase or decrease this value
    digitalWrite(STEP_PIN, LOW);
    delayMicroseconds(600);
  }

  delay(1000); // wait 1 sec

  // Reverse direction
  digitalWrite(DIR_PIN, !digitalRead(DIR_PIN));
  
  delay(1000); // wait 1 sec before moving again
}
