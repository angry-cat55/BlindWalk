#include "BluetoothSerial.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

BluetoothSerial SerialBT;

const int PIN_LEFT_RED = 27;    // 왼쪽 모터/LED (빨강)
const int PIN_RIGHT_GREEN = 25; // 오른쪽 모터/LED (초록)

unsigned long leftEndTime = 0;
unsigned long rightEndTime = 0;

void handleCommand(char cmd) {
  unsigned long now = millis();
  if (cmd == 'L') {
    digitalWrite(PIN_LEFT_RED, HIGH);
    leftEndTime = now + 300;
  } 
  else if (cmd == 'R') {
    digitalWrite(PIN_RIGHT_GREEN, HIGH);
    rightEndTime = now + 300;
  } 
  else if (cmd == 'C') {
    digitalWrite(PIN_LEFT_RED, HIGH);
    digitalWrite(PIN_RIGHT_GREEN, HIGH);
    leftEndTime = now + 400;
    rightEndTime = now + 400;
  }
}

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  pinMode(PIN_LEFT_RED, OUTPUT);
  pinMode(PIN_RIGHT_GREEN, OUTPUT);

  // 구분하기 쉽게: 이번 새 코드가 들어가면 빨간불만 3번 빠르게 깜빡입니다!
  for (int i = 0; i < 3; i++) {
    digitalWrite(PIN_LEFT_RED, HIGH);
    delay(100);
    digitalWrite(PIN_LEFT_RED, LOW);
    delay(100);
  }

  Serial.begin(115200);
  SerialBT.begin("BlindWalk_Haptic");

  // 블루투스 켜짐 완료 신호: 초록불 1초 점등
  digitalWrite(PIN_RIGHT_GREEN, HIGH);
  delay(1000);
  digitalWrite(PIN_RIGHT_GREEN, LOW);
}

void loop() {
  while (Serial.available() > 0) {
    handleCommand(Serial.read());
  }
  while (SerialBT.available() > 0) {
    handleCommand(SerialBT.read());
  }

  unsigned long now = millis();
  if (leftEndTime > 0 && now >= leftEndTime) {
    digitalWrite(PIN_LEFT_RED, LOW);
    leftEndTime = 0;
  }
  if (rightEndTime > 0 && now >= rightEndTime) {
    digitalWrite(PIN_RIGHT_GREEN, LOW);
    rightEndTime = 0;
  }
}
