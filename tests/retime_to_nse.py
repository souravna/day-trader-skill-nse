#!/usr/bin/env python3
"""Re-time the recorded US test fixtures onto the NSE clock. Run once; kept so it can be re-run.

The intraday fixtures were cut from real TSLA sessions (9:30 to 16:00 New York).
This moves every timestamp so that minute N after the New York open becomes
minute N after the NSE open (9:15 IST, 03:45 UTC) on the same date. Prices,
volumes and bar order do not change, so every hand-checked price in the tests
still holds; clock times in the tests move 15 minutes earlier (10:15 -> 10:00).
The NSE day is 15 minutes shorter (75 five-minute bars, not 78): the last three
US bars land after the 15:30 close and the tools treat them as after hours.

    python3 tests/retime_to_nse.py FILE [FILE ...]   # rewrites the files in place
"""
import datetime
import gzip
import json
import sys

EPOCH = datetime.datetime(1970, 1, 1)
TIME_KEYS = {"regularMarketTime", "start", "end"}  # meta clock fields (currentTradingPeriod, tradingPeriods)


def _nth_sunday(year, month, n):
    d = datetime.date(year, month, 1)
    d += datetime.timedelta(days=(6 - d.weekday()) % 7)
    return d + datetime.timedelta(weeks=n - 1)


def ny_offset(utc):
    start = datetime.datetime.combine(_nth_sunday(utc.year, 3, 2), datetime.time(7, 0))
    end = datetime.datetime.combine(_nth_sunday(utc.year, 11, 1), datetime.time(6, 0))
    return -4 if start <= utc < end else -5


def retime(ts):
    """Unix seconds of a New York session -> the same offset into that date's NSE session."""
    utc = EPOCH + datetime.timedelta(seconds=int(ts))
    ny = utc + datetime.timedelta(hours=ny_offset(utc))
    ny_open = datetime.datetime.combine(ny.date(), datetime.time(9, 30))
    nse_open_utc = datetime.datetime.combine(ny.date(), datetime.time(3, 45))  # 9:15 IST
    return int((nse_open_utc + (ny - ny_open) - EPOCH).total_seconds())


def walk(x):
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            if k == "timestamp" and isinstance(v, list):
                out[k] = [retime(t) if isinstance(t, (int, float)) else t for t in v]
            elif k in TIME_KEYS and isinstance(v, (int, float)) and v > 10 ** 9:
                out[k] = retime(v)
            elif k == "gmtoffset" and isinstance(v, (int, float)):
                out[k] = 19800
            elif k in ("timezone",) and isinstance(v, str):
                out[k] = "IST"
            elif k == "exchangeTimezoneName" and isinstance(v, str):
                out[k] = "Asia/Kolkata"
            else:
                out[k] = walk(v)
        return out
    if isinstance(x, list):
        return [walk(v) for v in x]
    return x


def main(paths):
    for p in paths:
        op = gzip.open if p.endswith(".gz") else open
        with op(p, "rt", encoding="utf-8") as fh:
            raw = fh.read()
        doc = walk(json.loads(raw))
        compact = "\n" not in raw.strip()
        with op(p, "wt", encoding="utf-8") as fh:
            fh.write(json.dumps(doc, separators=(",", ":")) if compact else json.dumps(doc, indent=1))
        print("re-timed", p)


if __name__ == "__main__":
    main(sys.argv[1:])
