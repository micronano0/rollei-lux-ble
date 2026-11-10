#!/usr/bin/env python3

EFFECT_CODES = {
    1: 0x03,
    2: 0x09,
    3: 0x13,
    4: 0x04,
    5: 0x0C,
    6: 0x0A,
    7: 0x0B,
    8: 0x0E,
    9: 0x05,
    10: 0x0D,
    11: 0x06,
    12: 0x07,
    13: 0x0F,
}

CODE_TO_EFFECT = {
    code: effekt for effekt, code in EFFECT_CODES.items()
}


def decode_effect(mode_code, data1, data2):
    effekt = CODE_TO_EFFECT.get(mode_code)

    if effekt is None:
        return None

    if effekt in (4, 6, 7, 8, 9, 10, 11, 12):
        if data1 not in (1, 3, 5, 7, 9):
            return None

        if data2 != 130:
            return None

        parameter = (data1 + 1) // 2

    elif effekt == 5:
        if data1 not in (1, 2, 3) or data2 != data1:
            return None

        parameter = data1

    elif effekt == 13:
        # Farbvariante wird separat über HSI/Kelvin bestimmt.
        return None

    elif effekt in (1, 2, 3):
        if not 1 <= data1 <= 5 or data2 != 130:
            return None

        parameter = data1

    else:
        return None

    return effekt, parameter


def decode_sos(mode_code, data1, data2):
    """Erkennt SOS, ohne eine Farbvariante zu behaupten."""
    if (mode_code, data1, data2) == (15, 130, 130):
        return 13
    return None
