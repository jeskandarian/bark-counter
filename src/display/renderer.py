import datetime
import os
import time
from typing import Optional

os.environ.setdefault("SDL_VIDEODRIVER", "fbcon")
os.environ.setdefault("SDL_FBDEV",       "/dev/fb1")
os.environ.setdefault("SDL_MOUSEDRV",    "TSLIB")

import pygame

import src.display.layout as L
from src.storage.db import get_connection
from src.storage.models import query_episodes, query_stats


class DisplayRenderer:
    def __init__(self, db_path: str, refresh_seconds: int):
        self._db      = db_path
        self._refresh = refresh_seconds
        self._zoom_i  = 2   # default index → 24h
        self._screen: Optional[pygame.Surface] = None
        self._fsm: Optional[pygame.font.Font]  = None
        self._fmd: Optional[pygame.font.Font]  = None
        self._conn = None

    def init(self) -> None:
        pygame.init()
        self._screen = pygame.display.set_mode((L.WIDTH, L.HEIGHT), pygame.NOFRAME)
        self._fsm    = pygame.font.SysFont("monospace", 13)
        self._fmd    = pygame.font.SysFont("monospace", 15)
        self._conn   = get_connection(self._db)

    def handle_tap(self, x: int, y: int) -> None:
        if y < L.ZOOM_Y:
            return
        idx = x // (L.WIDTH // len(L.ZOOM_LEVELS))
        if 0 <= idx < len(L.ZOOM_LEVELS):
            self._zoom_i = idx
            self.render()

    def render(self) -> None:
        s = self._screen
        s.fill(L.BG)
        self._header()
        self._chart()
        self._zoom_strip()
        pygame.display.flip()

    def _header(self) -> None:
        pygame.draw.rect(self._screen, L.HEADER_BG, (0, 0, L.WIDTH, L.HEADER_H))
        st    = query_stats(self._conn)
        now   = datetime.datetime.now().strftime("%H:%M %a %d %b")
        today = st["today"]
        hr    = st["last_hour"]
        txt   = (f"BARK COUNTER  {now}  "
                 f"Today:{today['episodes']}/{today['barks']}  "
                 f"LastHr:{hr['episodes']}/{hr['barks']}")
        surf  = self._fsm.render(txt, True, L.TEXT_COLOR)
        self._screen.blit(surf, (5, (L.HEADER_H - surf.get_height()) // 2))

    def _chart(self) -> None:
        _, hours = L.ZOOM_LEVELS[self._zoom_i]
        now      = time.time()
        rows     = query_episodes(self._conn, start=now - hours * 3600, end=now)
        n        = min(hours, 48)
        bsz      = (hours * 3600) / n
        base     = now - hours * 3600
        buckets  = [0] * n
        for r in rows:
            i = max(0, min(n - 1, int((r["started_at"] - base) / bsz)))
            buckets[i] += r["bark_count"]

        peak = max(buckets) if any(buckets) else 1
        bw   = max(1, L.CHART_W // n - 1)

        for gi in range(1, 5):
            y = L.CHART_Y + L.CHART_H - int(L.CHART_H * gi / 4)
            pygame.draw.line(self._screen, L.GRID_COLOR, (L.CHART_X, y), (L.WIDTH - 4, y))
            lbl = self._fsm.render(str(int(peak * gi / 4)), True, L.DIM_COLOR)
            self._screen.blit(lbl, (0, y - lbl.get_height() // 2))

        for i, cnt in enumerate(buckets):
            if cnt == 0:
                continue
            bh = int(L.CHART_H * cnt / peak)
            x  = L.CHART_X + i * (L.CHART_W // n)
            pygame.draw.rect(self._screen, L.BAR_COLOR,
                             (x, L.CHART_Y + L.CHART_H - bh, bw, bh))

    def _zoom_strip(self) -> None:
        bw = L.WIDTH // len(L.ZOOM_LEVELS)
        for i, (label, _) in enumerate(L.ZOOM_LEVELS):
            active = i == self._zoom_i
            bg = L.ZOOM_ON_BG if active else L.ZOOM_OFF_BG
            fg = L.ZOOM_ON_FG if active else L.ZOOM_OFF_FG
            pygame.draw.rect(self._screen, bg,
                             (i * bw + 2, L.ZOOM_Y + 2, bw - 4, L.ZOOM_H - 4))
            surf = self._fmd.render(label, True, fg)
            self._screen.blit(surf, (
                i * bw + (bw - surf.get_width())  // 2,
                L.ZOOM_Y  + (L.ZOOM_H - surf.get_height()) // 2,
            ))
