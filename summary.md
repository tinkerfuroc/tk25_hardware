# Pan-Tilt Base v0.9 — Workspace Summary

## 1) What this project is
This is an ESP32 firmware for a mobile base that can run in multiple hardware modes:

- **UGV base only**
- **UGV + RoArm-M2 manipulator**
- **UGV + Pan/Tilt gimbal**

Core runtime is in [`loop`](pan_tilt_base_v0.9.ino) and command dispatch is in [`jsonCmdReceiveHandler`](uart_ctrl.h).

---

## 2) High-level architecture

### Main app
- [`pan_tilt_base_v0.9.ino`](pan_tilt_base_v0.9.ino)
  - Includes all modules
  - Initializes peripherals and subsystems in `setup()`
  - Runs periodic behavior in `loop()`

### Hardware control modules
- [`movtion_module.h`](movtion_module.h): motor PWM, encoder speed reading, PID speed control, heartbeat stop
- [`gimbal_module.h`](gimbal_module.h): pan/tilt servo control, feedback, steady mode helpers
- [`RoArm-M2_module.h`](RoArm-M2_module.h): arm kinematics, servo control, trajectory interpolation, torque/PID helpers
- [`IMU_ctrl.h`](IMU_ctrl.h), [`IMU.cpp`](IMU.cpp), [`QMI8658.cpp`](QMI8658.cpp), [`AK09918.cpp`](AK09918.cpp): IMU stack

### Communication & UI
- [`uart_ctrl.h`](uart_ctrl.h): JSON command parsing and switch-case dispatch
- [`json_cmd.h`](json_cmd.h): command IDs and protocol constants
- [`http_server.h`](http_server.h): web API endpoint `/js`
- [`web_page.h`](web_page.h): embedded HTML/CSS/JS control panel
- [`esp_now_ctrl.h`](esp_now_ctrl.h): ESP-NOW command/flow integration

### System services
- [`wifi_ctrl.h`](wifi_ctrl.h): AP/STA/AP+STA config and status
- [`files_ctrl.h`](files_ctrl.h): LittleFS file operations
- [`ugv_advance.h`](ugv_advance.h): missions, feedback packaging, runtime settings
- [`oled_ctrl.h`](oled_ctrl.h), [`battery_ctrl.h`](battery_ctrl.h), [`ugv_led_ctrl.h`](ugv_led_ctrl.h)

### Configuration/state
- [`ugv_config.h`](ugv_config.h): global runtime config and shared state
- [`data/wifiConfig.json`](data/wifiConfig.json), [`data/devConfig.json`](data/devConfig.json): persisted settings

---

## 3) Runtime flow

## setup()
From [`setup`](pan_tilt_base_v0.9.ino):
1. Serial + I2C init
2. Power/battery + OLED init
3. IMU init
4. LED + filesystem init
5. Motor pin/PWM init via [`movtionPinInit`](movtion_module.h)
6. Servo UART init + servo checks
7. Wi-Fi init + HTTP server + ESP-NOW
8. Encoder init + PID init
9. Creates/plays boot mission (`boot`)

## loop()
From [`loop`](pan_tilt_base_v0.9.ino):
1. Serial command input
2. Web server client handling
3. Module-specific update:
   - arm mode: constant control + arm feedback
   - gimbal mode: gimbal feedback + steady processing
4. ESP-NOW deferred command handling
5. Left/right speed read + PID compute (split compute)
6. OLED update
7. IMU update
8. Base feedback flow via [`baseInfoFeedback`](ugv_advance.h)
9. Heartbeat timeout stop via [`heartBeatCtrl`](movtion_module.h)

---

## 4) Control model

## Mode selection
- `mainType` (vehicle kinematics preset)
- `moduleType` (0 none, 1 arm, 2 gimbal)
Defined in [`ugv_config.h`](ugv_config.h), set by [`mm_settings`](movtion_module.h).

## Motion
- Speed API: [`setGoalSpeed`](movtion_module.h)
- PID API: [`pidControllerInit`](movtion_module.h), `Left/RightPidControllerCompute`
- Heartbeat safety: [`heartBeatCtrl`](movtion_module.h)

## Gimbal
- Direct commands: `gimbalCtrlSimple`, `gimbalCtrlMove`, `gimbalCtrlStop`
- User-shell mapping: [`gimbalUserCtrlShell`](gimbal_module.h) maps differential speeds to pan/tilt directional commands

## Arm
- Kinematics + path smoothing (`besselCtrl`, IK/FK helpers)
- Absolute/relative axis and joint control
- Mission integration through command queue/file steps

---

## 5) JSON command protocol

- Command IDs are centralized in [`json_cmd.h`](json_cmd.h)
- Parsing and dispatch in [`jsonCmdReceiveHandler`](uart_ctrl.h)
- Web panel examples are in [`web_page.h`](web_page.h)

Notable command groups:
- Mobility: `T=1,11,13,138..140`
- Gimbal: `T=133..137,141`
- Arm: `T=101..123,+`
- File/Mission: `T=200..231,241+`
- System: `T=600..605,900`

---

## 6) Important implementation notes (read before edits)

1. **Global shared state is heavy**  
   Most modules mutate globals from [`ugv_config.h`](ugv_config.h). Keep side effects explicit.

2. **Command contract stability matters**  
   Avoid changing existing `T` IDs in [`json_cmd.h`](json_cmd.h); UI and external tools depend on them.

3. **Safety behavior exists but is distributed**
   - Heartbeat timeout stop in motion module
   - Servo torque release controls in arm/gimbal paths
   - Mission abort on serial activity

4. **Web endpoint behavior**
   - HTTP endpoint implemented in [`webCtrlServer`](http_server.h)
   - Frontend sends `GET /js?json=...` in [`web_page.h`](web_page.h)

5. **Potential defects to verify**
   - Typo family: `movtion` naming is intentional in current codebase
   - In gimbal shell conditionals, comparisons like `abs(lSpd) == abs(lSpd)` look suspicious (likely intended right-side variable)
   - HTTP response content type uses `"text/plane"` (likely should be `"text/plain"`)

---

## 7) Fast orientation for a new contributor

1. Read:
   - [`pan_tilt_base_v0.9.ino`](pan_tilt_base_v0.9.ino)
   - [`ugv_config.h`](ugv_config.h)
   - [`uart_ctrl.h`](uart_ctrl.h)
   - [`json_cmd.h`](json_cmd.h)

2. Then follow your feature path:
   - Motion: [`movtion_module.h`](movtion_module.h)
   - Gimbal: [`gimbal_module.h`](gimbal_module.h)
   - Arm: [`RoArm-M2_module.h`](RoArm-M2_module.h)
   - Web/API: [`http_server.h`](http_server.h), [`web_page.h`](web_page.h)

3. Validate on hardware:
   - No-motion boot
   - Heartbeat stop
   - Base feedback JSON shape
   - Emergency stop path

---

## 8) Suggested next cleanup tasks

- Normalize typo naming (`movtion` -> `motion`) only behind compatibility wrappers
- Fix suspicious gimbal conditional comparisons
- Correct HTTP content-type typo
- Add lightweight command schema validation at dispatch
- Separate hardware abstraction from command parser for easier testing