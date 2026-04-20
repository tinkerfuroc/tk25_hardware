# AGENTS.md

## Purpose
This document is a practical guide for **vibe coding safely** on this hardware firmware project (ESP32 + UGV base + optional arm/gimbal), while still moving fast.

"Vibe coding" here means rapid iterative changes with high feedback frequency — but never at the expense of hardware safety, command compatibility, or recoverability.

---

## 1) Core mindset for hardware vibe coding

1. **Safety > speed > elegance**
   - A rough but safe implementation is better than a clean one that can damage hardware.
2. **Small diffs, fast loops**
   - Change one behavior at a time (one command path, one module function, one timing loop).
3. **Observe before optimize**
   - Add/verify telemetry first, then tune PID/filters/timing.
4. **Reversible by default**
   - Every behavior change should have a quick rollback path (flag, config toggle, or isolated function change).

---

## 2) Non-negotiable safety rules

- **Never bypass heartbeat stop logic** (`heartBeatCtrl`) during normal development.
- **Clamp all actuator outputs** (motor PWM, servo angles, speed goals) at module boundaries.
- **Default to no-motion boot** after flashing.
- **Treat serial/web/ESP-NOW as untrusted input**; validate ranges and required fields.
- **When uncertain, stop motion first** (`setGoalSpeed(0,0)` / gimbal stop / torque-safe state).

Recommended dev habit:
- Keep a physical kill method available (power switch/lifted wheels/emergency stop input) during every test.

---

## 3) Project-specific guardrails

- Keep command IDs in `json_cmd.h` stable. External UI/tools depend on them.
- Keep side effects explicit when touching globals in `ugv_config.h`.
- Avoid hidden coupling between parser (`uart_ctrl.h`) and hardware modules.
- Preserve existing naming contracts (including legacy names like `movtion_*`) unless adding compatibility wrappers.

---

## 4) Vibe coding loop (recommended)

Use this 7-step loop for each change:

1. **Intent**: state one concrete behavior change.
2. **Scope**: identify exact file/function(s) touched.
3. **Guard**: add clamps, null checks, timeout, and fallback before behavior code.
4. **Instrument**: add concise debug output or feedback fields.
5. **Test ladder**:
   - compile/static checks
   - no-load bench run
   - low-speed short run
   - normal run
6. **Observe**: verify expected JSON feedback and actuator behavior.
7. **Clean**: remove noisy logs, keep useful diagnostics.

If a test fails, revert to last known-safe behavior immediately.

---

## 5) Change patterns that work well

### A) Command handler changes (`uart_ctrl.h`, `http_server.h`, `web_page.h`)
- Keep parser strict: reject malformed or partial JSON.
- Use safe defaults for missing optional fields.
- Validate numeric range before calling motion/gimbal/arm APIs.
- Return explicit status/ack where possible.

### B) Motion changes (`movtion_module.h`)
- Keep control loop timing stable.
- Apply symmetric left/right handling unless asymmetry is intentional and documented.
- When tuning PID, change one coefficient at a time and record before/after behavior.
- Do not remove heartbeat or timeout-based stop behavior.

### C) Gimbal changes (`gimbal_module.h`)
- Normalize sign conventions (pan/tilt direction) and document once.
- Apply angle/speed limits before write.
- Verify shell mapping logic for left/right speed comparisons and absolute-value checks.

### D) Arm changes (`RoArm-M2_module.h`)
- Keep IK/FK and trajectory interpolation deterministic.
- Use bounded step sizes; avoid sudden jumps.
- Keep torque release / safe pose transitions intact.

---

## 6) Debugging and telemetry discipline

- Prefer short, structured logs over verbose free-form prints.
- Include command ID (`T`), key inputs, clamped outputs, and fault reason.
- Add timestamps or cycle counts for timing-sensitive issues.
- Keep one source of truth for feedback payload shape (`baseInfoFeedback` path).

Good debug pattern:
- `cmd=T133 in:{x,y} out:{pan,tilt} clamp:{...} state:{...}`

---

## 7) Configuration and persistence best practices

- Treat `data/devConfig.json` and `data/wifiConfig.json` as schema-controlled inputs.
- Validate persisted values on load; repair or reset invalid fields.
- Keep defaults conservative (safe speed/angle/timeout).
- Separate runtime state from persisted config when possible.

---

## 8) Testing ladder for hardware firmware

Before merging/keeping a change, run this ladder:

1. **Build sanity** (compiles, no new warnings of concern)
2. **Boot sanity** (no unintended movement on startup)
3. **Command sanity** (critical `T` commands still parse and execute)
4. **Safety sanity** (heartbeat timeout actually stops motion)
5. **Feedback sanity** (JSON shape stable, values plausible)
6. **Recovery sanity** (invalid command does not lock loop or crash)

---

## 9) Anti-patterns to avoid

- Giant refactors while also changing behavior.
- Silent command contract changes.
- Mixing feature work with broad renaming without wrappers.
- Disabling safety checks "temporarily" and forgetting to restore.
- Tuning PID from noisy or unrepeatable test conditions.

---

## 10) Definition of done (hardware vibe edition)

A change is "done" only if:
- Behavior works in intended mode(s) (base/arm/gimbal as applicable)
- Safety paths still work (heartbeat stop, safe defaults)
- Command compatibility is preserved
- Telemetry can explain what happened during test
- You can reproduce the result twice

---

## 11) Suggested workflow for this repo

1. Read/edit in this order: `ugv_config.h` -> module file -> parser/dispatch -> web/API.
2. Keep PR/patches focused to one subsystem.
3. Log risky assumptions in code review notes (timing, direction sign, limits).
4. If touching shared globals, include explicit rationale for each changed variable.

---

## 12) Minimal safety checklist (copy/paste before flashing)

- [ ] Wheels lifted / safe physical test setup
- [ ] Heartbeat stop enabled
- [ ] Output clamps present for touched actuators
- [ ] Boot path does not command motion
- [ ] Rollback plan ready (last known-good firmware/config)
- [ ] One short test script/sequence prepared

---

## 13) Note for AI coding agents

When assisting on this repo:
- Prefer minimal, surgical edits.
- Do not change command IDs unless explicitly requested.
- Preserve safety-critical behavior by default.
- Call out uncertain hardware assumptions clearly.
- Prioritize fixes that reduce risk and improve observability.
