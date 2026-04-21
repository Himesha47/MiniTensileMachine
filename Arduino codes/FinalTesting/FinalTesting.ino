#include "HX711.h"

// ---------- Pins ----------
#define STEP_PIN 3
#define DIR_PIN  4
#define EN_PIN   5          // LOW = enable (A4988)

#define HX_DOUT  8          // HX711 DT
#define HX_SCK   9          // HX711 SCK
HX711 loadCell;

// ---------- Mechanics ----------
const int   STEPS_PER_REV = 200;
const int   MICROSTEP     = 16;
const float PITCH_MM      = 1.5;

const float MM_PER_STEP = PITCH_MM / (STEPS_PER_REV * MICROSTEP);

// ---------- Force (placeholder) ----------
float countsPerNewton = 12000.0;
float forceN = 0.0;

// ---------- State ----------
bool running = false;
bool dirDown = true;

long stepCount = 0;
long stepZero  = 0;

// ---------- Timing ----------
int stepDelayUs = 800;
unsigned long lastStepUs   = 0;
unsigned long lastStreamMs = 0;
const unsigned long STREAM_PERIOD_MS = 50;

// ---------- Driver helpers ----------
void enableDriver()  { digitalWrite(EN_PIN, LOW);  }
void disableDriver() { digitalWrite(EN_PIN, HIGH); }

// DOWN/UP mapping (if reversed, swap HIGH/LOW here)
void setDirection(bool down) {
  dirDown = down;
  digitalWrite(DIR_PIN, down ? HIGH : LOW);
}

void stepPulse() {
  digitalWrite(STEP_PIN, HIGH);
  delayMicroseconds(3);
  digitalWrite(STEP_PIN, LOW);

  if (dirDown) stepCount++;
  else         stepCount--;
}

float getDispMM() {
  return (stepCount - stepZero) * MM_PER_STEP;
}

void updateForceNonBlocking() {
  if (loadCell.is_ready()) {
    long raw = loadCell.read();
    forceN = raw / countsPerNewton;
  }
}

// ---------- Serial commands ----------
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
    else { setDirection(true); Serial.println("OK DIR_DOWN"); }
  }
  else if (cmd == "DIR UP") {
    if (running) Serial.println("ERR STOP_FIRST");
    else { setDirection(false); Serial.println("OK DIR_UP"); }
  }
  else if (cmd == "TARE") {
    loadCell.tare();
    Serial.println("OK TARE");
  }
  else if (cmd == "ZERO_LEN") {
    stepZero = stepCount;
    Serial.println("OK ZERO_LEN");
  }
  else {
    Serial.println("ERR UNKNOWN_CMD");
  }
}

void readSerialCommands() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    handleCommand(cmd);
  }
}

void setup() {
  Serial.begin(9600);
  delay(500);

  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(EN_PIN, OUTPUT);

  disableDriver();
  setDirection(true);  // default DOWN

  loadCell.begin(HX_DOUT, HX_SCK);

  Serial.println("READY");
  Serial.println("t_ms,force_N,disp_mm");
}

void loop() {
  readSerialCommands();
  updateForceNonBlocking();

  if (running) {
    unsigned long nowUs = micros();
    unsigned long periodUs = (unsigned long)stepDelayUs * 2UL;

    if (nowUs - lastStepUs >= periodUs) {
      lastStepUs = nowUs;
      stepPulse();
    }
  }

  unsigned long nowMs = millis();
  if (nowMs - lastStreamMs >= STREAM_PERIOD_MS) {
    lastStreamMs = nowMs;

    Serial.print(nowMs);
    Serial.print(",");
    Serial.print(forceN, 3);
    Serial.print(",");
    Serial.println(getDispMM(), 4);
  }
}
