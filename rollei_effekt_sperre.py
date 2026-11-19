#!/usr/bin/env python3

import time
from pathlib import Path

SPERRDATEI = Path("/home/pi/rollei_effekt_steuerung.lock")


def sperren():
    SPERRDATEI.write_text(str(time.time()))


def entsperren():
    SPERRDATEI.unlink(missing_ok=True)


def ist_gesperrt():
    if not SPERRDATEI.exists():
        return False

    try:
        zeitpunkt = float(SPERRDATEI.read_text())
        return time.time() - zeitpunkt < 120
    except (ValueError, OSError):
        return True
