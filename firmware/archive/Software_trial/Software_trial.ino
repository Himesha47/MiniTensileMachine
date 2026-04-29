#include "HX711.h"

//======================================================
// 1) PINS
//======================================================

// HX711
const int HX_DOUT = 8;
const int HX_SCK  = 9;
HX711 loadCell;

// A4988
const int PIN_EN   = 5;   // ACTIVE LOW (LOW = enabled, HIGH = disabled)
const int PIN_STEP = 6;
const int PIN_DIR  = 7;

//======================================================
// 2) SETTINGS (EDIT LATER)
//======================================================

// Speed control (microseconds)
int stepDelayMicros = 600;    // smaller = faster

// Mechanics (EDIT when finalized)
const int motorStepsPerRev = 200;      // full steps per revolution
const int microstepFactor  =16;        
const float leadScrewPitch_mmPerRev = 1.5;  // mm per revolution

float mmPerStep() {
  return leadScrewPitch_mmPerRev / (motorStepsPerRev * microstepFactor);
}

// Force calibration (EDIT after calibration)
float countsPerNewton = 12000.0;  // placeholder: raw_counts per 1 N

//======================================================
// 3) STATE
//======================================================
bool runningTest = false;
bool stopRequested = false;

long stepCount = 0;  // displacement steps from ZERO_LEN

//======================================================
// 4) HELPERS
//======================================================
void enableDriver()  { digitalWrite(PIN_EN, LOW); }
void disableDriver() { digitalWrite(PIN_EN, HIGH); }

bool topTriggered()    { return digitalRead(LIM_TOP) == HIGH; }     // NC opens => HIGH
bool bottomTriggered() { return digitalRead(LIM_BOTTOM) == HIGH; }

// One step pulse
void doStepOnce() {
  digitalWrite(PIN_STEP, HIGH);
  delayMicroseconds(stepDelayMicros);
  digitalWrite(PIN_STEP, LOW);
  delayMicroseconds(stepDelayMicros);
}

// Safe wait for HX711 ready (timeout prevents infinite lock)
bool waitForReady(unsigned long timeoutMs = 500) {
  unsigned long t0 = millis();
  while (!loadCell.is_ready()) {
    if (millis() - t0 > timeoutMs) return false;
  }
  return true;
}

float rawToNewton(long raw) {
  return raw / countsPerNewton;
}

//======================================================
// 5) COMMAND HANDLER (PC -> Arduino)
//======================================================
void handleSerialCommands() {
  
  if (!Serial.available()) return;

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  cmd.toUpperCase();

  if (cmd == "START") {
    stopRequested = false;
    runningTest = true;
    enableDriver();
    Serial.println("OK");
  }
  else if (cmd == "STOP") {
    stopRequested = true;
    runningTest = false;
    disableDriver();
    Serial.println("OK");
  }
  else if (cmd == "ZERO_LEN") {
    stepCount = 0;
    Serial.println("OK");
  }
  else if (cmd == "TARE") {
    // Only tare when no load
    // IMPORTANT: if HX711 is not ready, tare can fail
    if (waitForReady(1000)) {
      loadCell.tare();
      Serial.println("OK");
    } else {
      Serial.println("ERR");
    }
  }
  else if (cmd.startsWith("SPD")) {
    int spaceIndex = cmd.indexOf(' ');
    if (spaceIndex > 0) {
      int newDelay = cmd.substring(spaceIndex + 1).toInt();
      if (newDelay >= 50 && newDelay <= 5000) {
        stepDelayMicros = newDelay;
        Serial.println("OK");
      } else {
        Serial.println("ERR");
      }
    } else {
      Serial.println("ERR");
    }
  }
  else if (cmd == "DIR UP") {
  digitalWrite(PIN_DIR, HIGH);
  Serial.println("OK");
}
else if (cmd == "DIR DOWN") {
  digitalWrite(PIN_DIR, LOW);
  Serial.println("OK");
}

  else {
    Serial.println("ERR");
  }
}

//======================================================
// 6) SETUP
//======================================================
void setup() {
  Serial.begin(9600);
  delay(1200);

  // Stepper pins
  pinMode(PIN_EN, OUTPUT);
  pinMode(PIN_STEP, OUTPUT);
  pinMode(PIN_DIR, OUTPUT);
  disableDriver();

  // Limit switches
  pinMode(LIM_TOP, INPUT_PULLUP);
  pinMode(LIM_BOTTOM, INPUT_PULLUP);

  // HX711
  loadCell.begin(HX_DOUT, HX_SCK);

  // Set direction for tensile motion (change if reversed)
  digitalWrite(PIN_DIR, HIGH);

  // Small startup message + CSV header
  Serial.println("BOOT OK");
  Serial.println("t_ms,force_N,disp_mm");
}

//======================================================
// 7) LOOP
//======================================================
void loop() {
  handleSerialCommands();

  // Safety stop on limits (always active)
  if (topTriggered() || bottomTriggered()) {
    runningTest = false;
    disableDriver();
    stopRequested = true;
    delay(20);
    return;
  }

  if (!runningTest || stopRequested) {
    delay(20);
    return;
  }

  // -------- 7A) Read force --------
  if (!waitForReady(500)) {
    // HX711 not ready -> stop safely
    runningTest = false;
    disableDriver();
    stopRequested = true;
    return;
  }

  long raw = loadCell.read();
  float forceN = rawToNewton(raw);

  // -------- 7B) Move one step --------
  doStepOnce();
  stepCount++;

  float disp_mm = stepCount * mmPerStep();

  // -------- 7C) Send ONE clean CSV line --------
  Serial.print(millis());
  Serial.print(",");
  Serial.print(forceN, 3);
  Serial.print(",");
  Serial.println(disp_mm, 3);
}
