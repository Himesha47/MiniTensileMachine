#include "HX711.h"

//======================================================
// 1) PINS
//======================================================

// HX711
const int HX_DOUT = 8;
const int HX_SCK  = 9;
HX711 loadCell;

// A4988
const int PIN_STEP = 3;
const int PIN_DIR  = 4;
const int PIN_EN   = 5;   // ACTIVE LOW

//======================================================
// 2) SETTINGS
//======================================================

const unsigned int stepDelayMicros = 500;

const int motorStepsPerRev = 200;
const int microstepFactor  = 8;
const float threadbarPitch_mmPerRev = 1.5;

float mmPerStep() {
  return threadbarPitch_mmPerRev / (motorStepsPerRev * microstepFactor);
}

const float MAX_TRAVEL_MM = 450.0;
const float MIN_TRAVEL_MM = 0.0;

// ✅ YOUR CALIBRATION VALUE
float countsPerNewton = 10698.0;

//======================================================
// 3) STATE
//======================================================

bool runningTest = false;

long stepCount = 0;
int dirSign = +1;

long rawForce = 0;
float forceN = 0.0;

const unsigned long STREAM_PERIOD_MS = 50;
unsigned long lastStreamMs = 0;

unsigned long lastStepUs = 0;
unsigned long stepPeriodUs = 2UL * stepDelayMicros;

unsigned long lastForceReadMs = 0;
const unsigned long FORCE_READ_MS = 100;

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
  if (disp_mm >= MAX_TRAVEL_MM && dirSign>0) return true;
  // no lower limit
  return false;
}

void doStepPulse() {
  digitalWrite(PIN_STEP, HIGH);
  delayMicroseconds(5);
  digitalWrite(PIN_STEP, LOW);
}

//======================================================
// 5) COMMANDS
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
      loadCell.tare(10);
      Serial.println("OK TARE");
    } else {
      Serial.println("ERR HX711_NOT_READY");
    }
  }

  else if (cmd == "DIR UP") {
    if (!runningTest) {
      digitalWrite(PIN_DIR, HIGH);
      dirSign = +1;
      Serial.println("OK DIR_UP");
    } else {
        Serial.println("ERR STOP_FIRST");
   }
  }

  else if (cmd == "DIR DOWN") {
    if (!runningTest) {
      digitalWrite(PIN_DIR, LOW);
      dirSign = -1;
      Serial.println("OK DIR_DOWN");
    }
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

  disableDriver();
  digitalWrite(PIN_DIR, HIGH);
  dirSign=+1;

  loadCell.begin(HX_DOUT, HX_SCK);

  Serial.println("BOOT OK");
  Serial.println("t_ms,force_N,disp_mm");
}

//======================================================
// 7) LOOP
//======================================================

void loop() {
  handleSerialCommands();

  // ✅ READ LOAD CELL ALWAYS
  unsigned long nowForceMs = millis();
  if (loadCell.is_ready() && nowForceMs - lastForceReadMs >= FORCE_READ_MS) {
      lastForceReadMs = nowForceMs;
      rawForce = loadCell.read();
      forceN = rawToNewton(rawForce);
  }

  float disp_mm = stepCount * mmPerStep();

  // ✅ ALWAYS STREAM DATA (VERY IMPORTANT)
  unsigned long nowMs = millis();
  if (nowMs - lastStreamMs >= STREAM_PERIOD_MS) {
    lastStreamMs = nowMs;

    Serial.print(nowMs);
    Serial.print(",");
    Serial.print(forceN, 3);
    Serial.print(",");
    Serial.println(disp_mm, 4);
  }

  // If not running → stop motor but KEEP streaming
  if (!runningTest) {
    delay(10);
    return;
  }

  // Safety limit
  if (travelLimitReached(disp_mm)) {
    runningTest = false;
    disableDriver();
    Serial.println("ERR LIMIT");
    return;
  }

  // Motor stepping
  unsigned long nowMicros = micros();
  if (nowMicros - lastStepUs >= stepPeriodUs) {
    lastStepUs = nowMicros;
    doStepPulse();
    stepCount += dirSign;
  }
}