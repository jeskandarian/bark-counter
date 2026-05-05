WIDTH  = 480
HEIGHT = 320

HEADER_H = 28
ZOOM_H   = 30
CHART_Y  = HEADER_H
CHART_H  = HEIGHT - HEADER_H - ZOOM_H
CHART_X  = 36   # left margin for y-axis tick labels
CHART_W  = WIDTH - CHART_X - 4
ZOOM_Y   = HEIGHT - ZOOM_H

# Colors (RGB)
BG             = (17,  17,  17)
HEADER_BG      = (30,  30,  30)
BAR_COLOR      = (255, 153,  0)
TEXT_COLOR     = (238, 238, 238)
DIM_COLOR      = (100, 100, 100)
GRID_COLOR     = (34,  34,  34)
ZOOM_ON_BG     = (255, 153,  0)
ZOOM_ON_FG     = (17,  17,  17)
ZOOM_OFF_BG    = (34,  34,  34)
ZOOM_OFF_FG    = (150, 150, 150)

ZOOM_LEVELS = [("1h", 1), ("6h", 6), ("24h", 24), ("7d", 168)]
