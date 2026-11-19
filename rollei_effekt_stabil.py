#!/usr/bin/env python3

import time


class EffektStabil:
    def __init__(self, sekunden=5):
        self.sekunden = sekunden
        self.letzter_wert = None
        self.seit = None
        self.bestaetigt = None

    def pruefen(self, effekt, parameter, helligkeit):
        jetzt = time.monotonic()
        wert = (effekt, parameter, helligkeit)

        if wert != self.letzter_wert:
            self.letzter_wert = wert
            self.seit = jetzt
            return False

        if (
            jetzt - self.seit >= self.sekunden
            and wert != self.bestaetigt
        ):
            self.bestaetigt = wert
            return True

        return False

    def zuruecksetzen(self):
        self.letzter_wert = None
        self.seit = None
