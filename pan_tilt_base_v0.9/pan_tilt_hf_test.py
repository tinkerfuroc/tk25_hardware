#!/usr/bin/env python3
import argparse
import json
import math
import threading
import time
from collections import deque

import serial


class PanTiltHFTester:
    def __init__(
        self,
        port: str,
        baud: int,
        cmd_hz: float,
        duration_s: float,
        spd: float,
        acc: float,
        x_center: float,
        y_center: float,
        x_amp: float,
        y_amp: float,
        wave_hz: float,
        feedback_interval_ms: int,
        request_xy_hz: float,
    ):
        self.ser = serial.Serial(port, baudrate=baud, timeout=0.05)
        self.cmd_hz = cmd_hz
        self.duration_s = duration_s
        self.spd = spd
        self.acc = acc
        self.x_center = x_center
        self.y_center = y_center
        self.x_amp = x_amp
        self.y_amp = y_amp
        self.wave_hz = wave_hz
        self.feedback_interval_ms = feedback_interval_ms
        self.request_xy_hz = request_xy_hz

        self.stop_event = threading.Event()
        self.tx_count = 0
        self.rx_count = 0
        self.rx_parse_err = 0
        self.last_pose = {"pan": None, "tilt": None, "ts": None}
        self.pose_history = deque(maxlen=2000)

    def _send(self, obj: dict):
        line = json.dumps(obj, separators=(",", ":")) + "\n"
        self.ser.write(line.encode("utf-8"))

    def _init_device(self):
        self._send({"T": 4, "cmd": 2})
        time.sleep(0.05)

        self._send({"T": 131, "cmd": 1})
        time.sleep(0.02)

        self._send({"T": 142, "cmd": int(self.feedback_interval_ms)})
        time.sleep(0.02)

    def sender_loop(self):
        period = 1.0 / self.cmd_hz
        t0 = time.perf_counter()
        next_tick = t0

        while not self.stop_event.is_set():
            now = time.perf_counter()
            elapsed = now - t0
            if elapsed > self.duration_s:
                break

            phase = 2.0 * math.pi * self.wave_hz * elapsed
            x = self.x_center + self.x_amp * math.sin(phase)
            y = self.y_center + self.y_amp * math.sin(phase)

            x = max(-180.0, min(180.0, x))
            y = max(-30.0, min(90.0, y))

            self._send({"T": 133, "X": round(x, 3), "Y": round(y, 3), "SPD": self.spd, "ACC": self.acc})
            self.tx_count += 1

            next_tick += period
            sleep_s = next_tick - time.perf_counter()
            if sleep_s > 0:
                time.sleep(sleep_s)
            else:
                next_tick = time.perf_counter()

        self.stop_event.set()

    def requester_loop(self):
        if self.request_xy_hz <= 0:
            return

        period = 1.0 / self.request_xy_hz
        next_tick = time.perf_counter()

        while not self.stop_event.is_set():
            self._send({"T": 130})
            next_tick += period
            sleep_s = next_tick - time.perf_counter()
            if sleep_s > 0:
                time.sleep(sleep_s)
            else:
                next_tick = time.perf_counter()

    def reader_loop(self):
        while not self.stop_event.is_set():
            raw = self.ser.readline()
            if not raw:
                continue

            try:
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                msg = json.loads(line)
            except Exception:
                self.rx_parse_err += 1
                continue

            msg_type = msg.get("T")
            if msg_type == 1001:
                pan = msg.get("pan")
                tilt = msg.get("tilt")
                if pan is not None and tilt is not None:
                    ts = time.time()
                    self.last_pose = {"pan": pan, "tilt": tilt, "ts": ts}
                    self.pose_history.append((ts, pan, tilt))
                    self.rx_count += 1

    def monitor_loop(self):
        t0 = time.perf_counter()
        last_tx = 0
        last_rx = 0

        while not self.stop_event.is_set():
            time.sleep(1.0)
            elapsed = time.perf_counter() - t0
            tx = self.tx_count
            rx = self.rx_count

            tx_rate = tx - last_tx
            rx_rate = rx - last_rx
            last_tx = tx
            last_rx = rx

            pan = self.last_pose["pan"]
            tilt = self.last_pose["tilt"]
            if pan is None:
                pose_str = "pose=N/A"
            else:
                pose_str = f"pan={pan:.2f}, tilt={tilt:.2f}"

            print(
                f"[t={elapsed:5.1f}s] tx_total={tx:6d} tx_hz~{tx_rate:3d} | "
                f"rx_total={rx:6d} rx_hz~{rx_rate:3d} | {pose_str}"
            )

    def run(self):
        print("Opening serial and configuring device...")
        self._init_device()

        threads = [
            threading.Thread(target=self.sender_loop, daemon=True),
            threading.Thread(target=self.reader_loop, daemon=True),
            threading.Thread(target=self.monitor_loop, daemon=True),
        ]

        if self.request_xy_hz > 0:
            threads.append(threading.Thread(target=self.requester_loop, daemon=True))

        for thread in threads:
            thread.start()

        try:
            while not self.stop_event.is_set():
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.stop_event.set()

        time.sleep(0.2)

        print("\n=== Test Summary ===")
        print(f"commands sent: {self.tx_count}")
        print(f"feedback msgs  : {self.rx_count}")
        print(f"parse errors   : {self.rx_parse_err}")

        if self.last_pose["pan"] is not None:
            print(f"last pose      : pan={self.last_pose['pan']:.2f}, tilt={self.last_pose['tilt']:.2f}")

        self.ser.close()


def build_arg_parser():
    parser = argparse.ArgumentParser(description="High-frequency pan/tilt UART tester")
    parser.add_argument("--port", required=True, help="Serial port, e.g. /dev/tty.usbserial-0001")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--cmd-hz", type=float, default=200.0, help="T133 command send rate")
    parser.add_argument("--duration", type=float, default=20.0, help="Test duration in seconds")

    parser.add_argument("--spd", type=float, default=180.0, help="SPD field for T133")
    parser.add_argument("--acc", type=float, default=0.0, help="ACC field for T133")

    parser.add_argument("--x-center", type=float, default=0.0)
    parser.add_argument("--y-center", type=float, default=20.0)
    parser.add_argument("--x-amp", type=float, default=30.0)
    parser.add_argument("--y-amp", type=float, default=10.0)
    parser.add_argument("--wave-hz", type=float, default=0.5, help="Target trajectory oscillation frequency")

    parser.add_argument("--feedback-interval-ms", type=int, default=20, help="T142 cmd field")
    parser.add_argument(
        "--request-xy-hz",
        type=float,
        default=5.0,
        help="Extra explicit T130 request rate; set 0 to disable",
    )

    return parser


def main():
    args = build_arg_parser().parse_args()

    tester = PanTiltHFTester(
        port=args.port,
        baud=args.baud,
        cmd_hz=args.cmd_hz,
        duration_s=args.duration,
        spd=args.spd,
        acc=args.acc,
        x_center=args.x_center,
        y_center=args.y_center,
        x_amp=args.x_amp,
        y_amp=args.y_amp,
        wave_hz=args.wave_hz,
        feedback_interval_ms=args.feedback_interval_ms,
        request_xy_hz=args.request_xy_hz,
    )
    tester.run()


if __name__ == "__main__":
    main()
