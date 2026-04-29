const int LIM_TOP = 8;
const int LIM_BOTTOM = 9;

void setup() {
  Serial.begin(9600);
  pinMode(LIM_TOP, INPUT_PULLUP);
  pinMode(LIM_BOTTOM, INPUT_PULLUP);
}

void loop() {
  int topState = digitalRead(LIM_TOP);
  int bottomState = digitalRead(LIM_BOTTOM);

  Serial.print("TOP: ");
  Serial.print(topState == LOW ? "NOT pressed (NC closed)" : "PRESSED / OPEN (fault)");
  Serial.print("    |    ");

  Serial.print("BOTTOM: ");
  Serial.println(bottomState == LOW ? "NOT pressed (NC closed)" : "PRESSED / OPEN (fault)");

  delay(1000);
}
