#include "HX711.h"

//======================================================
// 1) PINS (YOUR WIRING)
//======================================================

// HX711
const int HX_DOUT = 8;
const int HX_SCK  = 9;
HX711 loadCell;

// A4988
const int PIN_STEP = 3;   // STEP -> D3
const int PIN_DIR  = 4;   // DIR  -> D4
const int PIN_EN   = 5;   // EN   -> D5 (ACTIVE LOW)

//======================================================
// 2) SETTINGS (FIXED SPEED)
//======================================================

// Fixed step pulse timing (microseconds)
const unsigned int stepDelayMicros = 800;

// Mechanics
const int motorStepsPerRev = 200;
const int microstepFactor  = 16;
const float leadScrewPitch_mmPerRev = 1.5;  // mm per revolution

float mmPerStep() {
  return leadScrewPitch_mmPerRev / (motorStepsPerRev * microstepFactor);
}

// Software travel limits
const float MAX_TRAVEL_MM = 300.0;
const float MIN_TRAVEL_MM = 0.0;

// Force calibration (placeholder)
float countsPerNewton = 12000.0;

//======================================================
// 3) STATE
//======================================================
bool runningTest = false;

long stepCount = 0;
int dirSign = +1;   // +1 UP, -1 DOWN

long rawForce = 0;
float forceN = 0.0;

// Streaming rate
const unsigned long STREAM_PERIOD_MS = 50; // 20 Hz
unsigned long lastStreamMs = 0;

// Step timing
unsigned long lastStepUs = 0;
unsigned long stepPeriodUs = 2UL * stepDelayMicros;

//======================================================
// 4) HELPERS
//======================================================
void enableDriver()  { digitalWrite(PIN_EN, LOW); }
void disableDriver() { digitalWrite(PIN_EN, HIGH); }

float rawToNewton(long raw) {
  return raw / countsPerNewton;
}

bool waitForReady(unsigned long timeoutMs) {
  unsigned long t0 = millis();
  while (!loadCell.is_ready()) {
    if (millis() - t0 > timeoutMs) return false;
  }
  return true;
}

bool travelLimitReached(float disp_mm) {
  if (disp_mm >= MAX_TRAVEL_MM) return true;
  if (disp_mm <= MIN_TRAVEL_MM && dirSign < 0) return true;
  return false;
}

void doStepPulse() {
  digitalWrite(PIN_STEP, HIGH);
  delayMicroseconds(3);
  digitalWrite(PIN_STEP, LOW);
}

//======================================================
// 5) COMMAND HANDLER
//======================================================
void handleSerialCommands() {
  if (!Serial.available()) return;

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  cmd.toUpperCase();

  if (cmd == "START") {
    runningTest = true;
    enableDriver();
    Serial.println("OK START");
  }
  else if (cmd == "STOP") {
    runningTest = false;
    disableDriver();
    Serial.println("OK STOP");
  }
  else if (cmd == "ZERO_LEN") {
    stepCount = 0;
    Serial.println("OK ZERO_LEN");
  }
  else if (cmd == "TARE") {
    if (waitForReady(1500)) {
      loadCell.tare();
      Serial.println("OK TARE");
    } else {
      Serial.println("ERR HX711_NOT_READY");
    }
  }
  else if (cmd == "DIR UP") {
    if (runningTest) {
      Serial.println("ERR STOP_FIRST");
    } else {
      digitalWrite(PIN_DIR, HIGH);
      dirSign = +1;
      Serial.println("OK DIR_UP");
    }
  }
  else if (cmd == "DIR DOWN") {
    if (runningTest) {
      Serial.println("ERR STOP_FIRST");
    } else {
      digitalWrite(PIN_DIR, LOW);
      dirSign = -1;
      Serial.println("OK DIR_DOWN");
    }
  }
  else {
    Serial.println("ERR UNKNOWN_CMD");
  }
}

//======================================================
// 6) SETUP
//======================================================
void setup() {
  Serial.begin(9600);
  delay(800);

  pinMode(PIN_STEP, OUTPUT);
  pinMode(PIN_DIR, OUTPUT);
  pinMode(PIN_EN, OUTPUT);

  disableDriver();                 // motor disabled at boot
  digitalWrite(PIN_DIR, HIGH);     // default direction = UP
  dirSign = +1;

  loadCell.begin(HX_DOUT, HX_SCK);

  Serial.println("BOOT OK");
  Serial.println("t_ms,force_N,disp_mm");
}

//======================================================
// 7) LOOP
//======================================================
void loop() {
  handleSerialCommands();

  // Update force (non-blocking)
  if (loadCell.is_ready()) {
    rawForce = loadCell.read();
    forceN = rawToNewton(rawForce);
  }

  if (!runningTest) {
    delay(10);
    return;
  }

  float disp_mm = stepCount * mmPerStep();

  if (travelLimitReached(disp_mm)) {
    runningTest = false;
    disableDriver();
    Serial.println("ERR LIMIT");
    return;
  }

  // Step motor
  unsigned long nowUs = micros();
  if (nowUs - lastStepUs >= stepPeriodUs) {
    lastStepUs = nowUs;
    doStepPulse();
    stepCount += dirSign;
  }

  // Stream data
  unsigned long nowMs = millis();
  if (nowMs - lastStreamMs >= STREAM_PERIOD_MS) {
    lastStreamMs = nowMs;
    disp_mm = stepCount * mmPerStep();

    Serial.print(nowMs);
    Serial.print(",");
    Serial.print(forceN, 3);
    Serial.print(",");
    Serial.println(disp_mm, 4);
  }
}
