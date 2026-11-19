#!/usr/bin/env python3

import json
import os
import tempfile
from pathlib import Path

DATEI = Path("/home/pi/rollei_effekte.json")


def speichern(effekt, parameter, helligkeit):
    if not 1 <= effekt <= 13:
        raise ValueError("Ungültiger Effekt")

    if not 1 <= helligkeit <= 100:
        raise ValueError("Ungültige Helligkeit")

    if effekt in (5, 9, 10, 11, 12, 13):
        maximum = 3
    else:
        maximum = 5

    if not 1 <= parameter <= maximum:
        raise ValueError("Ungültiger Parameter")

    daten = json.loads(DATEI.read_text())

    daten[str(effekt)] = {
        "parameter": parameter,
        "helligkeit": helligkeit
    }

    fd, tmp = tempfile.mkstemp(
        prefix=".rollei_effekte_",
        suffix=".tmp",
        dir=DATEI.parent
    )

    try:
        with os.fdopen(fd, "w") as f:
            json.dump(daten, f, indent=2, ensure_ascii=False)
            f.write("\n")

        os.replace(tmp, DATEI)

    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
