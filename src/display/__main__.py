import signal
import sys
import time

import pygame

from src.config import load_config
from src.display.renderer import DisplayRenderer
from src.display.touch import TouchInput


def main():
    cfg      = load_config()
    renderer = DisplayRenderer(cfg.storage.db_path, cfg.display.refresh_seconds)
    renderer.init()

    touch = TouchInput(
        device_path="/dev/input/event0",
        calibration_file=cfg.display.calibration_file,
        on_tap=renderer.handle_tap,
    )
    touch.start()

    def _quit(sig, frame):
        touch.stop()
        pygame.quit()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _quit)
    signal.signal(signal.SIGINT,  _quit)

    last = 0.0
    while True:
        now = time.monotonic()
        if now - last >= cfg.display.refresh_seconds:
            renderer.render()
            last = now
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                _quit(None, None)
        time.sleep(0.1)


if __name__ == "__main__":
    main()
