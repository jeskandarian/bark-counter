import threading
from typing import Callable, Optional

try:
    import evdev
    from evdev import ecodes
    _EVDEV = True
except ImportError:
    _EVDEV = False


class TouchInput:
    def __init__(
        self,
        device_path: str,
        calibration_file: str,
        on_tap: Callable[[int, int], None],
    ):
        self._path  = device_path
        self._cal   = self._read_cal(calibration_file)
        self._on_tap = on_tap
        self._t: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        if not _EVDEV:
            return
        self._running = True
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        try:
            dev = evdev.InputDevice(self._path)
            rx = ry = 0
            for ev in dev.read_loop():
                if not self._running:
                    break
                if ev.type == ecodes.EV_ABS:
                    if ev.code == ecodes.ABS_X:
                        rx = ev.value
                    elif ev.code == ecodes.ABS_Y:
                        ry = ev.value
                elif ev.type == ecodes.EV_KEY and ev.code == ecodes.BTN_TOUCH and ev.value == 1:
                    self._on_tap(*self._cal_pt(rx, ry))
        except Exception:
            pass

    def _cal_pt(self, rx: int, ry: int) -> tuple:
        from src.display.layout import WIDTH, HEIGHT
        if self._cal is None:
            return rx, ry
        x0, x1, y0, y1 = self._cal
        x = int((rx - x0) / (x1 - x0) * WIDTH)
        y = int((ry - y0) / (y1 - y0) * HEIGHT)
        return max(0, min(WIDTH - 1, x)), max(0, min(HEIGHT - 1, y))

    def _read_cal(self, path: str) -> Optional[tuple]:
        try:
            vals = [int(v) for v in open(path).read().split()]
            return tuple(vals)  # x_min x_max y_min y_max
        except Exception:
            return None
