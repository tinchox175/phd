/*
  ============================================================================
  PANI humidity chamber controller - Arduino Due - firmware FW0.3 (commented)
  ============================================================================

  WHAT THIS PROGRAM DOES
  ----------------------
  The Due is the chamber's "local brain". It does everything that must keep
  working even if the PC crashes, the USB cable comes out or a script has a bug:

    1. Reads the sensors once per second:
         - SHT30 inside the jar     -> jar temperature and relative humidity (RH)
         - DS18B20 in the box air   -> air temperature (the one we control)
    2. Runs a PID control loop that drives the Peltier (TEC) through the
       BTS7960 H-bridge, to hold the box air at a target temperature.
    3. Switches the small fan inside the jar.
    4. Protects the hardware:
         - air temperature outside 5-55 degC        -> TEC off
         - air sensor lost while control is on      -> TEC off
         - program frozen for 8 s                   -> hardware watchdog reboots the chip
       A fault "latches": it stays active until the host sends *CLS.
    5. Listens on the Native USB port for text commands (see chamber_commands.txt).
       Every command gets exactly one reply line, so the PC can always ask a
       question and wait for one answer.

  HOW AN ARDUINO PROGRAM RUNS
  ---------------------------
  There is no operating system. After power-up or reset the chip runs setup()
  once, then calls loop() over and over, forever, as fast as it can (hundreds of
  thousands of times per second here). Nothing else runs in between, so:
    - loop() must never wait for long (no long delay() calls), otherwise commands
      pile up unanswered and the watchdog would reboot the board;
    - "do X once per second" is done by checking the clock (millis()) on every
      pass and acting only when a second has elapsed.

  BUILD
  -----
  Board  : Arduino Due (Native USB Port)  -> FQBN arduino:sam:arduino_due_x
  Libs   : OneWire, DallasTemperature, Adafruit SHT31 Library (+ Adafruit BusIO)
  Flash  : arduino-cli compile -u -p <port> --fqbn arduino:sam:arduino_due_x chamber_controller
           If the new program doesn't start after flashing, press RESET once.

  !! The Due runs at 3.3 V. Its pins are NOT 5 V tolerant: power the SHT30
     board, the DS18B20 pull-up and the BTS7960 VCC pin from 3.3 V.
  !! Never open the Native port at 1200 baud from your own software: that is
     the signal that tells the Due to erase itself and enter the bootloader.

  WIRING
  ------
  SHT30 board   VIN->3.3V  GND->GND  SDA->pin 20  SCL->pin 21
  DS18B20       VDD->3.3V  GND->GND  DQ->pin 2, plus 4.7k resistor DQ->3.3V
  BTS7960       VCC->3.3V  GND->GND  RPWM->pin 6  LPWM->pin 7  R_EN+L_EN->pin 5
                B+/B- -> 12 V supply,  M+/M- -> TEC
  Jar fan       switch transistor/MOSFET controlled by pin 4
  Heartbeat     on-board "L" LED (pin 13) toggles once per second while running

  VERSION HISTORY
  ---------------
  FW0.1  first version (hung at boot: bad PWM clock request)
  FW0.2  PWM fix (still hung with nothing on the 1-Wire pin)
  FW0.3  1-Wire pull-up fix, heartbeat LED, 8 s watchdog; this file adds
         comments only, plus a safer number parser for the PID command
*/

// ---------------------------------------------------------------------------
// Libraries
// ---------------------------------------------------------------------------
// #include pulls in code written by others, so we don't reimplement low-level
// protocols ourselves.
#include <Wire.h>                // I2C bus (the 2-wire bus the SHT30 talks on)
#include <OneWire.h>             // 1-Wire bus (the 1-wire bus the DS18B20 talks on)
#include <DallasTemperature.h>   // DS18B20 commands on top of OneWire
#include <Adafruit_SHT31.h>      // SHT3x commands (works for SHT30, SHT31, SHT35)

// ---------------------------------------------------------------------------
// Pin assignments
// ---------------------------------------------------------------------------
// "const int" = a named number that never changes. Using names instead of raw
// numbers means a rewiring is a one-line change here.
const int PIN_ONEWIRE   = 2;    // DS18B20 data line
const int PIN_FAN       = 4;    // jar fan switch (HIGH = on)
const int PIN_BTS_EN    = 5;    // BTS7960 enable, R_EN and L_EN tied together
const int PIN_RPWM      = 6;    // BTS7960 "right" PWM input  (hardware PWM pin)
const int PIN_LPWM      = 7;    // BTS7960 "left"  PWM input  (hardware PWM pin)
const int PIN_HEARTBEAT = 13;   // on-board "L" LED
// (Not named PIN_LED: the Due core already uses that name internally.)

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------
// Which BTS7960 input makes the TEC heat the box. It depends on which way round
// the TEC wires go into M+/M-. If "heating" cools, flip this to false.
const bool HEAT_ON_RPWM = true;

// Fraction of full 12 V the TEC may ever receive. 0.60 -> about 7.2 V average,
// roughly 3.5 A in a TEC1-12706: efficient, and well below its 6 A maximum.
const float MAX_DUTY = 0.60f;

// Outputs smaller than 2 % are rounded to zero, so the TEC isn't constantly
// flickering between tiny heating and tiny cooling around the setpoint.
const float DEADBAND = 0.02f;

// Hard safety limits on the box-air temperature (degC). Outside these -> fault.
const float T_MAX = 55.0f;
const float T_MIN = 5.0f;

// Range of setpoints the host is allowed to request (degC).
const float SETP_MIN = 10.0f;
const float SETP_MAX = 50.0f;

// How often we measure and update the control loop, in milliseconds.
const uint32_t PERIOD_MS = 1000;

// PWM: the TEC voltage is switched fully on/off 20,000 times per second; the
// fraction of time it is "on" (the duty cycle) sets the average voltage.
// 20 kHz is above human hearing (no whine) and fast enough that the TEC sees a
// steady average instead of on/off thermal cycling.
const uint32_t PWM_FREQ = 20000;
// The PWM hardware counts at the CPU clock, 84 MHz (VARIANT_MCK). One PWM period
// = 84,000,000 / 20,000 = 4200 counts, so the duty cycle can be set in 4200 steps.
const uint32_t PWM_TOP  = VARIANT_MCK / PWM_FREQ;

// The Due has two USB ports. SerialUSB is the Native one (fast, and opening it
// does NOT reset the board). "HOST" is just a nickname used throughout the code.
#define HOST SerialUSB

// Identification string returned by *IDN?. The PC driver checks the version.
const char* IDN = "PANI-CHAMBER,DUE,FW0.3";

// ---------------------------------------------------------------------------
// Global state (variables that live for the whole program)
// ---------------------------------------------------------------------------
OneWire           ow(PIN_ONEWIRE);   // the 1-Wire bus on pin 2
DallasTemperature ds(&ow);           // DS18B20 helper using that bus
DeviceAddress     dsAddr;            // each DS18B20 has a unique 64-bit address
bool              dsFound = false;   // did we find one at boot?
Adafruit_SHT31    sht;               // SHT30 helper (on the default I2C bus)
bool              shtFound = false;  // did we find it at boot?

// Latest measurements. NAN ("not a number") means "no valid value".
float tAir  = NAN;    // box air, degC  (DS18B20)
float tJar  = NAN;    // jar,     degC  (SHT30)
float rhJar = NAN;    // jar,     %RH   (SHT30)

float setpoint = 25.0f;   // target box-air temperature, degC
float output   = 0.0f;    // current TEC drive: -1 full cooling ... +1 full heating
bool  ctrlOn   = false;   // is the PID loop in charge of the TEC?
bool  fanOn    = false;   // jar fan state

// PID gains (see pidStep below). Starting guesses, to be tuned on the real box.
float kp = 0.15f;    // proportional: drive per degC of error
float ki = 0.002f;   // integral: drive per (degC * second) of accumulated error
float kd = 0.0f;     // derivative: drive per (degC / second) of change; off for now
float integ    = 0.0f;   // the integral term's running total
float prevMeas = NAN;    // previous measurement, for the derivative term

// Possible faults. An "enum" is a list of named values.
enum Fault { F_NONE, F_SENSOR, F_OVERTEMP, F_UNDERTEMP };
Fault fault = F_NONE;

String   rxLine;          // characters received from the PC, until Enter arrives
uint32_t lastTick = 0;    // time (ms) of the last 1-second update

// ---------------------------------------------------------------------------
// Watchdog
// ---------------------------------------------------------------------------
// The watchdog is a hardware timer independent of our program. Once enabled,
// it reboots the chip unless the program "pets" it (watchdogReset()) at least
// every 8 s. We pet it at the top of every loop(), so it only fires if the
// program freezes - e.g. stuck waiting for a broken sensor. After the reboot the
// board comes up in its safe state (control off, TEC off).
// The Due core calls watchdogSetup() automatically at boot.
void watchdogSetup() { watchdogEnable(8000); }

// ---------------------------------------------------------------------------
// PWM (hardware, 20 kHz)
// ---------------------------------------------------------------------------
// Arduino's usual analogWrite() gives only 1 kHz on the Due, so we program the
// chip's PWM peripheral directly. Pins 6 and 7 are wired inside the chip to two
// PWM "channels"; g_APinDescription[] is the core's table that tells us which.
// Do NOT call analogWrite() on pins 6-9 anywhere: it would reconfigure the PWM
// hardware and break this setup.

// Prepare one pin as a 20 kHz PWM output, starting at 0 % duty.
void pwmPinInit(int pin) {
  const PinDescription &p = g_APinDescription[pin];
  // Hand the pin over from normal digital I/O to the PWM peripheral.
  PIO_Configure(p.pPort, p.ulPinType, p.ulPin, p.ulPinConfiguration);
  uint32_t ch = p.ulPWMChannel;
  // Channel counts at the full 84 MHz clock (MCK); left-aligned; normal polarity.
  PWMC_ConfigureChannel(PWM_INTERFACE, ch, PWM_CMR_CPRE_MCK, 0, 0);
  PWMC_SetPeriod(PWM_INTERFACE, ch, PWM_TOP);   // 4200 counts = one 20 kHz period
  PWMC_SetDutyCycle(PWM_INTERFACE, ch, 0);      // start fully off
  PWMC_EnableChannel(PWM_INTERFACE, ch);
}

void pwmInit() {
  pmc_enable_periph_clk(PWM_INTERFACE_ID);   // switch on the PWM peripheral's power/clock
  // (FW0.1 called PWMC_ConfigureClocks() here asking for 84 MHz; the library
  //  forbids that and froze the board. Using MCK directly avoids it.)
  pwmPinInit(PIN_RPWM);
  pwmPinInit(PIN_LPWM);
}

// Set a pin's duty cycle: 0 = always off ... PWM_TOP = always on.
void pwmSet(int pin, uint32_t duty) {
  PWMC_SetDutyCycle(PWM_INTERFACE, g_APinDescription[pin].ulPWMChannel, duty);
}

// ---------------------------------------------------------------------------
// TEC output through the BTS7960 H-bridge
// ---------------------------------------------------------------------------
// An H-bridge can push current through the TEC in either direction:
//   RPWM pulsing, LPWM low  -> current one way    (e.g. heats the inner side)
//   LPWM pulsing, RPWM low  -> current other way  (cools the inner side)
//   both low                -> no drive
// We never pulse both at once.

// Immediately stop driving the TEC and disable the bridge.
void driverOff() {
  pwmSet(PIN_RPWM, 0);
  pwmSet(PIN_LPWM, 0);
  digitalWrite(PIN_BTS_EN, LOW);
  output = 0.0f;
}

// Apply a drive level u: -1 (full cooling) ... 0 ... +1 (full heating).
void applyOutput(float u) {
  if (fault != F_NONE) { driverOff(); return; }   // faults always win
  u = constrain(u, -1.0f, 1.0f);                  // clip to the allowed range
  if (fabs(u) < DEADBAND) u = 0.0f;               // ignore tiny values
  output = u;

  // Convert |u| into PWM counts, applying the MAX_DUTY current cap.
  uint32_t duty = (uint32_t)(fabs(u) * MAX_DUTY * PWM_TOP);
  int heatPin = HEAT_ON_RPWM ? PIN_RPWM : PIN_LPWM;
  int coolPin = HEAT_ON_RPWM ? PIN_LPWM : PIN_RPWM;

  digitalWrite(PIN_BTS_EN, HIGH);
  // Always set the opposite side to 0 BEFORE driving one side.
  if (u > 0)      { pwmSet(coolPin, 0); pwmSet(heatPin, duty); }
  else if (u < 0) { pwmSet(heatPin, 0); pwmSet(coolPin, duty); }
  else            { pwmSet(heatPin, 0); pwmSet(coolPin, 0); }
}

// ---------------------------------------------------------------------------
// PID controller
// ---------------------------------------------------------------------------
// Every second we compute error = setpoint - measured temperature, and the
// output is the sum of three terms:
//   P = kp * error             push harder the further we are from the target
//   I = ki * sum(error * dt)   slowly builds up to remove any steady offset
//                              (e.g. heat constantly leaking out of the box)
//   D = -kd * d(temp)/dt       brakes when the temperature changes fast, to
//                              limit overshoot (computed on the measurement,
//                              not the error, so setpoint jumps don't cause a kick)
//
// Anti-windup: if the output is already maxed out (+1 or -1), integrating more
// error would only build up a huge I term that later causes overshoot. So we
// stop integrating while saturated in the direction of the error.

// Forget the integral and derivative history (used when control (re)starts or
// the gains change).
void pidReset() { integ = 0.0f; prevMeas = NAN; }

float pidStep(float sp, float meas, float dt) {
  float err   = sp - meas;
  float deriv = isnan(prevMeas) ? 0.0f : -(meas - prevMeas) / dt;
  prevMeas = meas;

  float uNoI      = kp * err + kd * deriv;    // P + D
  float integCand = integ + ki * err * dt;    // what I would become
  float u         = uNoI + integCand;

  if ((u > 1.0f && err > 0) || (u < -1.0f && err < 0)) {
    u = uNoI + integ;      // saturated: keep the old I, don't wind up
  } else {
    integ = integCand;     // normal: accept the new I
  }
  return constrain(u, -1.0f, 1.0f);
}

// ---------------------------------------------------------------------------
// Sensors
// ---------------------------------------------------------------------------
// A DS18B20 reading is valid only inside its physical range. -127 means "no
// answer" and exactly 85.0 is the value it reports right after power-up before
// its first real measurement, so both are rejected.
bool dsValid(float t) { return t > -55.0f && t < 125.0f && t != 85.0f; }

void readSensors() {
  // DS18B20: a 12-bit measurement takes up to 750 ms. Waiting for it would
  // freeze loop() for most of a second, so we work one step ahead:
  // collect the result of the conversion started last second, then start the
  // next one, which will be ready by the next call.
  if (dsFound) {
    float t = ds.getTempC(dsAddr);
    tAir = dsValid(t) ? t : NAN;
    ds.requestTemperatures();
  } else {
    tAir = NAN;
  }

  // SHT30: one measurement takes ~15 ms, short enough to just wait for it.
  if (shtFound) {
    float t, h;
    if (sht.readBoth(&t, &h)) { tJar = t; rhJar = h; }
    else                      { tJar = NAN; rhJar = NAN; }   // read failed this time
  }
}

// Decide whether something is wrong. Once a fault is set it stays set
// (latched) until the host clears it with *CLS, so a brief problem can't be
// missed by the PC.
void checkFaults() {
  if (fault != F_NONE) return;
  if (ctrlOn && isnan(tAir))              fault = F_SENSOR;     // controlling blind
  else if (!isnan(tAir) && tAir > T_MAX)  fault = F_OVERTEMP;
  else if (!isnan(tAir) && tAir < T_MIN)  fault = F_UNDERTEMP;
  if (fault != F_NONE) { ctrlOn = false; driverOff(); }
}

const char* faultName() {
  switch (fault) {
    case F_SENSOR:    return "FAULT:SENSOR";
    case F_OVERTEMP:  return "FAULT:OVERTEMP";
    case F_UNDERTEMP: return "FAULT:UNDERTEMP";
    default:          return "OK";
  }
}

// ---------------------------------------------------------------------------
// Host protocol (commands from the PC)
// ---------------------------------------------------------------------------
// Commands are plain text lines, e.g. "TEMP:SET 25". The full list with reply
// formats is in chamber_commands.txt.

// Send one reply line. We end lines with '\n' only.
void reply(const String &s) { HOST.print(s); HOST.print('\n'); }

// Format a number with d decimals, or "NAN" if there is no valid value.
String num(float v, int d) { return isnan(v) ? String("NAN") : String(v, d); }

// Accept ON/OFF or 1/0. Returns false if the argument is neither.
bool parseOnOff(const String &arg, bool &val) {
  if (arg == "ON"  || arg == "1") { val = true;  return true; }
  if (arg == "OFF" || arg == "0") { val = false; return true; }
  return false;
}

// Read up to n numbers separated by spaces from text. Returns how many were
// found. Returns -1 if something that is not a number is in the way.
int parseFloats(const String &text, float *out, int n) {
  const char *p = text.c_str();
  int count = 0;
  while (*p != '\0' && count < n) {
    while (*p == ' ') p++;              // skip spaces
    if (*p == '\0') break;
    char *end;
    float v = strtof(p, &end);          // convert text to a number
    if (end == p) return -1;            // not a number
    out[count++] = v;
    p = end;
  }
  return count;
}

// Execute one complete command line.
void handleCommand(String line) {
  line.trim();                          // drop spaces / stray \r at the ends
  if (line.length() == 0) return;       // ignore empty lines
  line.toUpperCase();                   // so "temp:set 25" also works

  // Split "COMMAND ARGUMENT" at the first space.
  int sp = line.indexOf(' ');
  String cmd = sp < 0 ? line : line.substring(0, sp);
  String arg = sp < 0 ? String("") : line.substring(sp + 1);
  arg.trim();

  // --- identification ---
  if (cmd == "*IDN?") { reply(IDN); }

  // --- measurements (cached from the last 1-second update; answering is instant) ---
  else if (cmd == "MEAS?") {
    // tAir, tJar, rhJar, output, setpoint, ctrl, fan, status
    reply(num(tAir, 4) + "," + num(tJar, 2) + "," + num(rhJar, 2) + "," +
          String(output, 3) + "," + String(setpoint, 2) + "," +
          String(ctrlOn ? 1 : 0) + "," + String(fanOn ? 1 : 0) + "," + faultName());
  }
  else if (cmd == "MEAS:TAIR?") { reply(num(tAir, 4)); }
  else if (cmd == "MEAS:TJAR?") { reply(num(tJar, 2)); }
  else if (cmd == "MEAS:RH?")   { reply(num(rhJar, 2)); }

  // --- temperature setpoint ---
  else if (cmd == "TEMP:SET?") { reply(String(setpoint, 2)); }
  else if (cmd == "TEMP:SET") {
    float v;
    if (parseFloats(arg, &v, 1) != 1 || v < SETP_MIN || v > SETP_MAX) reply("ERR:RANGE");
    else { setpoint = v; reply("OK"); }
  }

  // --- automatic control on/off ---
  else if (cmd == "CTRL?") { reply(ctrlOn ? "1" : "0"); }
  else if (cmd == "CTRL") {
    bool v;
    if (!parseOnOff(arg, v))  { reply("ERR:ARG"); return; }
    if (v && fault != F_NONE) { reply("ERR:FAULT_ACTIVE"); return; }   // clear it first
    if (v && !dsFound)        { reply("ERR:NO_AIR_SENSOR"); return; }  // can't control blind
    ctrlOn = v;
    pidReset();                         // start the PID fresh
    if (!v) applyOutput(0.0f);          // switching off -> TEC off
    reply("OK");
  }

  // --- manual TEC output (testing; only while automatic control is off) ---
  else if (cmd == "OUT?") { reply(String(output, 3)); }
  else if (cmd == "OUT:SET") {
    float v;
    if (ctrlOn)                          { reply("ERR:CTRL_ON"); return; }
    if (fault != F_NONE)                 { reply("ERR:FAULT_ACTIVE"); return; }
    if (parseFloats(arg, &v, 1) != 1)    { reply("ERR:ARG"); return; }
    applyOutput(v);                      // applyOutput clips to -1..+1
    reply("OK");
  }

  // --- jar fan ---
  else if (cmd == "FAN?") { reply(fanOn ? "1" : "0"); }
  else if (cmd == "FAN") {
    bool v;
    if (!parseOnOff(arg, v)) { reply("ERR:ARG"); return; }
    fanOn = v;
    digitalWrite(PIN_FAN, fanOn ? HIGH : LOW);
    reply("OK");
  }

  // --- PID gains ---
  else if (cmd == "PID?") { reply(String(kp, 5) + "," + String(ki, 5) + "," + String(kd, 5)); }
  else if (cmd == "PID") {
    float g[3];
    if (parseFloats(arg, g, 3) != 3 || g[0] < 0 || g[1] < 0 || g[2] < 0) {
      reply("ERR:ARG"); return;
    }
    kp = g[0]; ki = g[1]; kd = g[2];
    pidReset();
    reply("OK");
  }

  // --- SHT30 built-in heater (only for recovery after long high-RH exposure) ---
  else if (cmd == "SHT:HEAT") {
    bool v;
    if (!shtFound)           { reply("ERR:NO_SHT"); return; }
    if (!parseOnOff(arg, v)) { reply("ERR:ARG"); return; }
    sht.heater(v);
    reply("OK");
  }

  // --- status / clear fault ---
  else if (cmd == "STAT?") { reply(faultName()); }
  else if (cmd == "*CLS")  { fault = F_NONE; reply("OK"); }
  // (If the cause is still there, checkFaults() sets the fault again within a second.)

  else { reply("ERR:UNKNOWN"); }
}

// Collect incoming characters without ever waiting. When a line ending arrives,
// process the complete line. Lines longer than 80 characters are truncated
// (no valid command is that long).
void pollHost() {
  while (HOST.available()) {
    char c = (char)HOST.read();
    if (c == '\n' || c == '\r') {
      if (rxLine.length()) { handleCommand(rxLine); rxLine = ""; }
    } else if (rxLine.length() < 80) {
      rxLine += c;
    }
  }
}

// ---------------------------------------------------------------------------
// setup(): runs once at power-up / reset
// ---------------------------------------------------------------------------
void setup() {
  // Outputs first, in their safe state: bridge disabled, fan off, LED off.
  pinMode(PIN_BTS_EN, OUTPUT);    digitalWrite(PIN_BTS_EN, LOW);
  pinMode(PIN_FAN, OUTPUT);       digitalWrite(PIN_FAN, LOW);
  pinMode(PIN_HEARTBEAT, OUTPUT); digitalWrite(PIN_HEARTBEAT, LOW);
  pwmInit();
  driverOff();

  HOST.begin(115200);   // the number is ignored on the Native port, but required
  // We deliberately do NOT wait for the PC to connect: the chamber must work
  // with no PC attached.

  // DS18B20 search. The internal pull-up keeps pin 2 from floating when nothing
  // is attached; a floating pin can look like an endless chain of sensors and
  // hang the search (the FW0.2 bug). Harmless with the real 4.7k fitted.
  pinMode(PIN_ONEWIRE, INPUT_PULLUP);
  ds.begin();
  dsFound = ds.getAddress(dsAddr, 0);       // first sensor on the bus
  if (dsFound) ds.setResolution(dsAddr, 12);   // 12 bit = 0.0625 degC steps
  ds.setWaitForConversion(false);           // don't block (see readSensors)
  ds.requestTemperatures();                 // start the first measurement

  // SHT30 at its default I2C address 0x44 (0x45 if the board's ADDR pin is high).
  shtFound = sht.begin(0x44);

  lastTick = millis();
}

// ---------------------------------------------------------------------------
// loop(): runs forever
// ---------------------------------------------------------------------------
void loop() {
  watchdogReset();   // "still alive" - must happen at least every 8 s
  pollHost();        // answer any commands that arrived (instant, no waiting)

  // Once per second: measure, check safety, run the PID.
  // (Unsigned subtraction handles millis() wrapping around after ~49 days.)
  uint32_t now = millis();
  if (now - lastTick >= PERIOD_MS) {
    float dt = (now - lastTick) / 1000.0f;   // actual elapsed seconds
    lastTick = now;

    static bool led = false;                 // "static": keeps its value between calls
    led = !led;
    digitalWrite(PIN_HEARTBEAT, led ? HIGH : LOW);

    readSensors();
    checkFaults();

    if (ctrlOn && fault == F_NONE && !isnan(tAir)) {
      applyOutput(pidStep(setpoint, tAir, dt));
    }
  }
}
