// NEMA 17 + A4988 + 1 mm pitch + 1/8 microstepping

// Control pins from Arduino to A4988
const int STEP_PIN = 3;    // Each pulse on this pin = 1 microstep
const int DIR_PIN  = 4;    // Direction: HIGH = CW, LOW = CCW

// Microstepping selection pins
const int MS1_PIN  = 5;
const int MS2_PIN  = 6;
const int MS3_PIN  = 7;

// Enable pin (turns driver on/off)
const int EN_PIN   = 8;    // LOW = enabled, HIGH = disabled

// Motor: 200 full steps per revolution for NEMA17
const int STEPS_PER_REV_FULL = 200;

//  1/8 microstepping
const int MICROSTEP_MODE = 8;

// Total microsteps per revolution
const int MICROSTEPS_PER_REV = STEPS_PER_REV_FULL * MICROSTEP_MODE;

// Size of one microstep in mm
const float MICROSTEP_SIZE_MM = 1.0 / MICROSTEPS_PER_REV;  // 0.000625 mm

const int DEFAULT_DELAY_US = 800;  

void stepMotor(long steps, int delayUs) {
  for (long i = 0; i < steps; i++) {
    digitalWrite(STEP_PIN, HIGH);       // Rising edge = take one microstep
    delayMicroseconds(delayUs);         // Control speed
    digitalWrite(STEP_PIN, LOW);        // End of pulse
    delayMicroseconds(delayUs);         // Pause before next microstep
  }
}

void moveMM(float mm, bool moveDown, int delayUs) {

  if (moveDown) {
    // Set direction pin so motor rotates clockwise (cross arm moves DOWN)
    digitalWrite(DIR_PIN, HIGH);
  } else {
    // Set direction for anticlockwise (cross arm moves UP)
    digitalWrite(DIR_PIN, LOW);
  }

  // Calculate how many microsteps are needed for the requested distance
  // stepsNeeded = distance(mm) / step_size(mm per microstep)
  long stepsNeeded = mm / MICROSTEP_SIZE_MM;

  // Safety: avoid negative steps
  if (stepsNeeded < 0) {
    stepsNeeded = -stepsNeeded;
  }

  // Perform the movement
  stepMotor(stepsNeeded, delayUs);
}


// ---------- Arduino setup ----------
void setup() {
  // Set all relevant pins as outputs
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN,  OUTPUT);

  pinMode(MS1_PIN,  OUTPUT);
  pinMode(MS2_PIN,  OUTPUT);
  pinMode(MS3_PIN,  OUTPUT);
  pinMode(EN_PIN,   OUTPUT);

  // Enable the stepper driver
  // A4988: EN LOW = enabled, EN HIGH = disabled
  digitalWrite(EN_PIN, LOW);

  // Configure microstepping to 1/8:
  // MS1 = HIGH, MS2 = HIGH, MS3 = LOW  -> 1/8 microstepping
  digitalWrite(MS1_PIN, HIGH);
  digitalWrite(MS2_PIN, HIGH);
  digitalWrite(MS3_PIN, LOW);
}


// ---------- Main loop (test behaviour only) ----------
void loop() {
  // Example test sequence:
  // 1) Move DOWN 1 mm
  // 2) Wait 1 second
  // 3) Move UP 1 mm
  // 4) Wait 1 second
  //
  // This is just for testing. Later you will replace this with:
  //  - limit switch logic
  //  - buttons
  //  - PC commands
  //  - test procedure, etc.

  // Move cross arm DOWN by 1.0 mm
  moveMM(1.0, true, DEFAULT_DELAY_US);   // true  = moveDown

  delay(1000);  // wait 1 second

  // Move cross arm UP by 1.0 mm
  moveMM(1.0, false, DEFAULT_DELAY_US);  // false = moveUp

  delay(1000);  // wait 1 second
}
