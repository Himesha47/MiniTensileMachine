#include "HX711.h"

// -------------------- PINS (YOUR SETUP) --------------------
#define STEP_PIN 3
#define DIR_PIN  4
#define EN_PIN   5   // A4988 EN: LOW = enabled, HIGH = disabled

#define HX_DOUT  8   // HX711 DT -> D8
#define HX_SCK   9   // HX711 SCK -> D9

HX711 loadCell;

// -------------------- MECHANICS --------------------
// Adjust these to match your real hardware
const int   STEPS_PER_REV = 200;   // NEMA17 full steps per rev
const int   MICROSTEP     = 16;    // 1/16 microstepping
const float PITCH_MM      = 1.5;   // lead screw mm per revolution

const float MM_PER_STEP = PITCH_MM / (STEPS_PER_REV * MICROSTEP);

// -------------------- FORCE (placeholder for now) --------------------
float countsPerNewton = 12000.0;   // keep as placeholder for now

// -------------------- STATE --------------------
bool running = false;
bool dirDown = true;

long stepCount = 0;  // total microsteps
long stepZero  = 0;  // displacement zero reference (ZERO_LEN)

float forceN = 0.0;

// speed (smaller = faster)
int stepDelayUs = 800;

// timing
unsigned long lastStepUs   = 0;
unsigned long lastStreamMs = 0;
const unsigned long STREAM_PERIOD_MS = 50; // 20 Hz

// -------------------- DRIVER HELPERS --------------------
void enableDriver()  { digitalWrite(EN_PIN, LOW);  }
void disableDriver() { digitalWrite(EN_PIN, HIGH); }

// ✅ FIXED: Direction mapping (swap HIGH/LOW here if needed)
void setDirection(bool down) {
  dirDown = down;

  // You said: DOWN should be real down.
  // If your mechanics are reversed, swap the HIGH/LOW below.
  digitalWrite(DIR_PIN, down ? HIGH : LOW);   // <--- swapped mapping
}

void stepPulse() {
  digitalWrite(STEP_PIN, HIGH);
  delayMicroseconds(3);
  digitalWrite(STEP_PIN, LOW);

  if (dirDown) stepCount++;
  else         stepCount--;
}

// -------------------- MEASUREMENTS --------------------
float getDispMM() {
  return (stepCount - stepZero) * MM_PER_STEP;
}

void updateForceNonBlocking() {
  if (loadCell.is_ready()) {
    long raw = loadCell.read();
    forceN = raw / countsPerNewton;
  }
}

// -------------------- SERIAL COMMANDS --------------------
void printHeader() {
  Serial.println("t_ms,force_N,disp_mm");
}

void handleCommand(String cmd) {
  cmd.trim();
  cmd.toUpperCase();

  if (cmd == "START") {
    running = true;
    enableDriver();
    Serial.println("OK START");
  }
  else if (cmd == "STOP") {
    running = false;
    disableDriver();
    Serial.println("OK STOP");
  }
  else if (cmd == "DIR DOWN") {
    if (running) Serial.println("ERR STOP_FIRST");
    else { setDirection(true); Serial.println
