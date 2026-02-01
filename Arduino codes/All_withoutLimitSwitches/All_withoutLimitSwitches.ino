#include "HX711.h"

//======================================================
// 1) Defining the pins
//======================================================

// HX711
const int HX_DOUT = 8;
const int HX_SCK  = 9;
HX711 loadCell;   // Creates an object inside the arduino. 

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
const int microstepFactor  = 8;
const float threadbarPitch_mmPerRev = 1.5;  // threadbar pitch

float mmPerStep() {
  return threadbarPitch_mmPerRev / (motorStepsPerRev * microstepFactor);
}

// Software travel limits
const float MAX_TRAVEL_MM = 450.0;
const float MIN_TRAVEL_MM = 0.0;

// Force calibration (placeholder)
float countsPerNewton = 12000.0;

//======================================================
// 3) STATE
//======================================================
bool runningTest = false;   // flag to stop the motor from running all the time

long stepCount = 0; // count the no of micrsteps
int dirSign = +1;   // +1 UP, -1 DOWN

long rawForce = 0; // raw no given by the HX711
float forceN = 0.0; // store the force converted to Newtons

// Streaming rate
const unsigned long STREAM_PERIOD_MS = 50; // every 50 ms send one line. 
unsigned long lastStreamMs = 0;

// Step timing
unsigned long lastStepUs = 0; // stores the previous step size
unsigned long stepPeriodUs = 2UL * stepDelayMicros; // wait time during steps

//======================================================
// 4) HELPERS
//======================================================
void enableDriver()  { digitalWrite(PIN_EN, LOW); }   // can use the function when needed
void disableDriver() { digitalWrite(PIN_EN, HIGH); }

float rawToNewton(long raw) {
  return raw / countsPerNewton;  // get the force in Newtons. 
}

bool waitForReady(unsigned long timeoutMs) {
  unsigned long t0 = millis();
  while (!loadCell.is_ready()) {
    if (millis() - t0 > timeoutMs) return false;  // timed out
  }
  return true;   // HX711 became ready in time
}
// for safety
bool travelLimitReached(float disp_mm) {
  if (disp_mm >= MAX_TRAVEL_MM) return true;
  if (disp_mm <= MIN_TRAVEL_MM && dirSign < 0) return true;
  return false;
}

void doStepPulse() {
  digitalWrite(PIN_STEP, HIGH);
  delayMicroseconds(5);
  digitalWrite(PIN_STEP, LOW);
}

//======================================================
// 5) COMMAND HANDLER
//======================================================
void handleSerialCommands() {  //commands of the Python
  if (!Serial.available()) return;  // if nothing arrived, exit 

  String cmd = Serial.readStringUntil('\n');  // read until newline (full command)
  cmd.trim();
  cmd.toUpperCase();

  if (cmd == "START") {
    runningTest = true; // this is made false at the begining
    enableDriver();
    Serial.println("OK START");
  }
  else if (cmd == "STOP") { // immediate stop from the GUI
    runningTest = false; // didn't diable the driver to continue having the holding torque
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
// Controling the A4988
  pinMode(PIN_STEP, OUTPUT);
  pinMode(PIN_DIR, OUTPUT);
  pinMode(PIN_EN, OUTPUT);

  disableDriver();                 // motor disabled at boot
  digitalWrite(PIN_DIR, HIGH);     // default direction = UP
  dirSign = +1;
// start HX711 communication
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
  if (loadCell.is_ready()) { // to avoid reading the old data
    rawForce = loadCell.read();
    forceN = rawToNewton(rawForce);
  }

  if (runningTest == false) {  // to avoid the code running until the motor moves
    delay(10);
    return;
  }

  float disp_mm = stepCount * mmPerStep(); //mmPerStep() = 0.0009375 mm

  if (travelLimitReached(disp_mm)) {   // stop the test if reached the max height
    runningTest = false;
    disableDriver();
    Serial.println("ERR LIMIT");
    return;
  }

// to control the motor speed
  unsigned long nowMicros = micros();
  if (nowMicros - lastStepUs >= stepPeriodUs) {
    lastStepUs = nowMicros;
    doStepPulse();
    stepCount += dirSign;
  }

  // CSV output
  unsigned long nowMs = millis();
  if (nowMs - lastStreamMs >= STREAM_PERIOD_MS) {
    lastStreamMs = nowMs; // Save the current time
    disp_mm = stepCount * mmPerStep(); // Update the position

    Serial.print(nowMs);
    Serial.print(",");
    Serial.print(forceN, 3);  // upto 3 decimael places
    Serial.print(",");
    Serial.println(disp_mm, 4);
  }
}

