#include "HX711.h"

//======================================================
// 1) PINS
//======================================================

// HX711
const int HX_DOUT = 8;
const int HX_SCK = 9;
HX711 loadCell;

// A4988 - step/dir/enable
const int PIN_STEP = 3;
const int PIN_DIR = 4;
const int PIN_EN = 5;   // ACTIVE LOW

// A4988 - microstepping pins
const int PIN_MS1 = 10;
const int PIN_MS2 = 11;
const int PIN_MS3 = 12;

//======================================================
// 2) SETTINGS
//======================================================

const int motorStepsPerRev = 200;
const float threadbarPitch_mmPerRev = 1.5;

// Current speed state — defaults to 50 mm/min
int microstepFactor = 16;
unsigned long stepPeriodUs = 5625UL * 2;

float mmPerStep() {
  return threadbarPitch_mmPerRev / (motorStepsPerRev * microstepFactor);
}

// Calibration factor
float countsPerNewton = 10698.0;

//======================================================
// 3) STATE
//======================================================

bool runningTest = false;

long stepCount = 0;
int  dirSign = +1;

long  rawForce = 0;
float forceN = 0.0;

const unsigned long STREAM_PERIOD_MS = 50;
unsigned long lastStreamMs = 0;

unsigned long lastStepUs = 0;

unsigned long lastForceReadMs = 0;
const unsigned long FORCE_READ_MS = 100;

//======================================================
// 4) HELPERS
//======================================================

void enableDriver(){ digitalWrite(PIN_EN, LOW);}
void disableDriver(){ digitalWrite(PIN_EN, HIGH);}

float rawToNewton(long raw){
  return raw / countsPerNewton;
}

bool waitForReady(unsigned long timeoutMs){
  unsigned long t0 = millis();
  while (!loadCell.is_ready()) {
    if (millis() - t0 > timeoutMs) return false;
  }
  return true;
}

void doStepPulse(){
  digitalWrite(PIN_STEP, HIGH);
  delayMicroseconds(5);
  digitalWrite(PIN_STEP, LOW);
}

// Set MS1, MS2, MS3 pins according to microstep factor
void setMicrostepPins(int factor) {
  switch (factor){
    case 1:// Full step - MS1=L MS2=L MS3=L
      digitalWrite(PIN_MS1,LOW);
      digitalWrite(PIN_MS2,LOW);
      digitalWrite(PIN_MS3,LOW);
      break;
    case 2:// Half step - MS1=H MS2=L MS3=L
      digitalWrite(PIN_MS1,HIGH);
      digitalWrite(PIN_MS2,LOW);
      digitalWrite(PIN_MS3,LOW);
      break;
    case 4:// Quarter step - MS1=L MS2=H MS3=L
      digitalWrite(PIN_MS1,LOW);
      digitalWrite(PIN_MS2,HIGH);
      digitalWrite(PIN_MS3,LOW);
      break;
    case 8:  // Eighth step- MS1=H MS2=H MS3=L
      digitalWrite(PIN_MS1,HIGH);
      digitalWrite(PIN_MS2,HIGH);
      digitalWrite(PIN_MS3,LOW);
      break;
    case 16: // Sixteenth step - MS1=H MS2=H MS3=H
      digitalWrite(PIN_MS1,HIGH);
      digitalWrite(PIN_MS2,HIGH);
      digitalWrite(PIN_MS3,HIGH);
      break;
    default:
      // Default to sixteenth step
      digitalWrite(PIN_MS1,HIGH);
      digitalWrite(PIN_MS2,HIGH);
      digitalWrite(PIN_MS3,HIGH);
      microstepFactor = 16;
      break;
  }
}

// Set speed - updates both microstep factor and step period
// Speed locked during test - enforced in command handler
void setSpeed(int speedMmPerMin) {
  switch (speedMmPerMin) {
    case 10:
      microstepFactor=16;
      stepPeriodUs=28125UL*2;// 35 steps/sec → ~10 mm/min
      break;
    case 20:
      microstepFactor=16;
      stepPeriodUs= 4063UL*2;// 71 steps/sec → ~20 mm/min
      break;
    case 50:
      microstepFactor=16;
      stepPeriodUs=5625UL*2; // 178 steps/sec → ~50 mm/min
      break;
    case 100:
      microstepFactor=8;
      stepPeriodUs=5625UL*2; // 356 steps/sec → ~100 mm/min
      break;
    case 200:
      microstepFactor=4;
      stepPeriodUs=5625UL*2; // 711 steps/sec → ~200 mm/min
      break;
    default:
      microstepFactor = 16;
      stepPeriodUs=5625UL*2;
      break;
  }
  setMicrostepPins(microstepFactor);
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
    } else {
      Serial.println("ERR STOP_FIRST");
    }
  }

  // Speed commands - only accepted when test is not running
  else if (cmd == "SPEED_10") {
    if (!runningTest) {
      setSpeed(10);
      Serial.print("OK SPEED_10 mmPerStep=");
      Serial.println(mmPerStep(), 7);
    } else {
      Serial.println("ERR STOP_FIRST");
    }
  }

  else if (cmd == "SPEED_20") {
    if (!runningTest) {
      setSpeed(20);
      Serial.print("OK SPEED_20 mmPerStep=");
      Serial.println(mmPerStep(), 7);
    } else {
      Serial.println("ERR STOP_FIRST");
    }
  }

  else if (cmd == "SPEED_50") {
    if (!runningTest) {
      setSpeed(50);
      Serial.print("OK SPEED_50 mmPerStep=");
      Serial.println(mmPerStep(), 7);
    } else {
      Serial.println("ERR STOP_FIRST");
    }
  }

  else if (cmd == "SPEED_100") {
    if (!runningTest) {
      setSpeed(100);
      Serial.print("OK SPEED_100 mmPerStep=");
      Serial.println(mmPerStep(), 7);
    } else {
      Serial.println("ERR STOP_FIRST");
    }
  }

  else if (cmd == "SPEED_200") {
    if (!runningTest) {
      setSpeed(200);
      Serial.print("OK SPEED_200 mmPerStep=");
      Serial.println(mmPerStep(), 7);
    } else {
      Serial.println("ERR STOP_FIRST");
    }
  }
}

//======================================================
// 6) SETUP
//======================================================

void setup() {
  Serial.begin(9600);
  delay(800);

  pinMode(PIN_STEP,OUTPUT);
  pinMode(PIN_DIR,OUTPUT);
  pinMode(PIN_EN,OUTPUT);
  pinMode(PIN_MS1,OUTPUT);
  pinMode(PIN_MS2,OUTPUT);
  pinMode(PIN_MS3,OUTPUT);

  disableDriver();
  digitalWrite(PIN_DIR,HIGH);
  dirSign = +1;

  // Default speed: 50 mm/min on startup
  setSpeed(50);

  loadCell.begin(HX_DOUT, HX_SCK);

  Serial.println("BOOT OK");
  Serial.println("t_ms,force_N,disp_mm");
}

//======================================================
// 7) LOOP
//======================================================

void loop() {
  handleSerialCommands();

  // Read load cell every 100 ms
  unsigned long nowForceMs = millis();
  if (loadCell.is_ready() && nowForceMs - lastForceReadMs >= FORCE_READ_MS) {
    lastForceReadMs = nowForceMs;
    rawForce = loadCell.read();
    forceN   = rawToNewton(rawForce);
  }

  float disp_mm = stepCount * mmPerStep();

  // Stream data every 50 ms
  unsigned long nowMs = millis();
  if (nowMs - lastStreamMs >= STREAM_PERIOD_MS) {
    lastStreamMs = nowMs;
    Serial.print(nowMs);
    Serial.print(",");
    Serial.print(forceN, 3);
    Serial.print(",");
    Serial.println(disp_mm, 4);
  }

  if (!runningTest) {
    delay(10);
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