#!/usr/bin/env python3
"""Move wall-clock times in a test file 15 minutes earlier, to match retime_to_nse.py.

Only times from 09:16 to 16:59 move (the US session and just after); UTC stamps
(...Z) and offsets are left alone and fixed by hand. "9:45 AM" stays unpadded,
"10:05 bar" becomes "9:50 bar", anything else is HH:MM.

    python3 tests/shift_test_times.py tests/test_entry.py               # rewrites in place
    python3 tests/shift_test_times.py tests/test_scanner.py --literals  # DT(...) / datetime.time(...) too
"""
import re
import sys

PAT = re.compile(r"(?<![\d:T])(\d{1,2}):(\d{2})(:\d{2})?(?![\d:]|Z|[+-]\d\d:)")


def shift(m, text):
    h, mi, sec = int(m.group(1)), int(m.group(2)), m.group(3) or ""
    t = h * 60 + mi
    if not (9 * 60 + 16 <= t <= 16 * 60 + 59):
        return m.group(0)
    t -= 15
    nh, nm = divmod(t, 60)
    after = text[m.end():m.end() + 4]
    if after.startswith((" AM", " PM", " am", " pm", " bar")) or (len(m.group(1)) == 1):
        return "%d:%02d%s" % (nh, nm, sec)
    return "%02d:%02d%s" % (nh, nm, sec)


DT_PAT = re.compile(r"\b(DT|datetime\.datetime)\((\d{4}), (\d{1,2}), (\d{1,2}), (\d{1,2}), (\d{1,2})")
TIME_PAT = re.compile(r"\bdatetime\.time\((\d{1,2}), (\d{1,2})")


def _minus15(h, mi):
    t = h * 60 + mi
    if not (9 * 60 + 16 <= t <= 16 * 60 + 59):
        return None
    return divmod(t - 15, 60)


def shift_dt(m):
    r = _minus15(int(m.group(5)), int(m.group(6)))
    if r is None:
        return m.group(0)
    return "%s(%s, %s, %s, %d, %d" % (m.group(1), m.group(2), m.group(3), m.group(4), r[0], r[1])


def shift_time(m):
    r = _minus15(int(m.group(1)), int(m.group(2)))
    return m.group(0) if r is None else "datetime.time(%d, %d" % r


def main(path):
    with open(path) as fh:
        text = fh.read()
    out = PAT.sub(lambda m: shift(m, text), text)
    if "--literals" in sys.argv:     # also DT(y, m, d, h, mi) and datetime.time(h, mi): wall-clock IST literals
        out = TIME_PAT.sub(shift_time, DT_PAT.sub(shift_dt, out))
    with open(path, "w") as fh:
        fh.write(out)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        if not p.startswith("--"):
            main(p)
