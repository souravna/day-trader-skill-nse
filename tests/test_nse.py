"""The Indian market across the pack: .NS symbols pass through untouched, the IST clock, the NSE
session and holidays, and every day trade out by 15:15."""

import datetime
import unittest

from _load import load

alerts = load("trader-alerts", "alerts")
broker = load("trader-broker", "ticket")
budget = load("trader-budget", "size")
entry = load("trader-entry", "entry")
exitp = load("trader-exit", "exit")
news = load("trader-news", "news")
risk = load("trader-risk", "check")
scan = load("trader-scanner", "scan")
tm = load("trader-timemachine", "timemachine")

CLOCKS = (alerts, broker, budget, entry, exitp, risk, scan, tm)
CALENDARS = (alerts, entry, exitp, risk, scan)
NSE = ["RELIANCE.NS", "BAJAJ-AUTO.NS", "M&M.NS", "20MICRONS.NS", "TCS.BO"]


class Symbols(unittest.TestCase):
    def test_yahoo_gets_the_symbol_as_it_is(self):
        for sym in NSE:
            self.assertEqual(alerts.yahoo_symbol(sym.lower()), sym)
            self.assertEqual(entry.yahoo_symbol(sym), sym)
            self.assertEqual(exitp.yahoo_symbol(sym), sym)
            self.assertEqual(tm.yahoo_symbol(sym), sym)
            self.assertEqual(scan.to_yahoo(sym), sym)
            self.assertEqual(scan.from_yahoo(sym), sym)
            self.assertEqual(news.yahoo_symbol(sym), sym)
        # US class shares keep their old mapping
        self.assertEqual(entry.yahoo_symbol("BRK.B"), "BRK-B")
        self.assertEqual(scan.from_yahoo("BRK-B"), "BRK.B")

    def test_urls(self):
        self.assertEqual(alerts.yahoo_url("reliance.ns"),
                         "https://query2.finance.yahoo.com/v8/finance/chart/RELIANCE.NS?range=1d&interval=1d")
        self.assertEqual(entry.chart_path("BAJAJ-AUTO.NS", "1d", "5m"),
                         "/v8/finance/chart/BAJAJ-AUTO.NS?range=1d&interval=5m")
        self.assertEqual(scan.chart_path("M&M.NS", "1d", "5m"), "/v8/finance/chart/M%26M.NS?range=1d&interval=5m")

    def test_risk_accepts_nse_tickers(self):
        for sym in NSE:
            self.assertTrue(risk.TICKER.match(sym), sym)
        for sym in ("TSLA", "BRK.B"):
            self.assertTrue(risk.TICKER.match(sym), sym)
        for bad in ("RELIANCE.XX", "BTC/USD", ".NS", "RELIANCE NS"):
            self.assertFalse(risk.TICKER.match(bad), bad)

    def test_the_time_machine_takes_an_nse_plan(self):
        p = tm.normalize_plan({"symbol": "reliance.ns", "date": "2026-11-19", "entry": 1500.0, "stop": 1490.0,
                               "target": 1520.0, "entry_time": "10:00 AM"})
        self.assertEqual((p["symbol"], p["entry_bar"]), ("RELIANCE.NS", 8))
        self.assertEqual(tm.normalize_plan(dict(p, symbol="M&M.NS"))["symbol"], "M&M.NS")

    def test_a_yes_that_names_another_nse_order_is_refused(self):
        order = {"symbol": "INFY.NS", "side": "buy", "qty": "5", "type": "market"}
        ok, why = broker.parse_yes("yes, buy RELIANCE.NS", order, batch_symbols=["INFY.NS", "RELIANCE.NS"])
        self.assertFalse(ok)
        self.assertIn("RELIANCE.NS", why)


class News(unittest.TestCase):
    def test_headlines_that_name_the_exchange(self):
        pats = news.mention_patterns({"RELIANCE.NS": None, "TSLA": None})
        self.assertTrue(pats["RELIANCE.NS"].search("Shares of NSE: RELIANCE jumped"))
        self.assertTrue(pats["RELIANCE.NS"].search("Reliance Industries (RELIANCE.NS) rose"))
        self.assertTrue(pats["TSLA"].search("NYSE: TSLA") or pats["TSLA"].search("NASDAQ: TSLA"))


class Clock(unittest.TestCase):
    def test_ist_everywhere(self):
        for mod in CLOCKS:
            for d in (datetime.datetime(2026, 1, 10, 3, 45), datetime.datetime(2026, 7, 10, 3, 45)):
                self.assertEqual(mod.to_ist(d), d + datetime.timedelta(hours=5, minutes=30), mod.__name__)
                self.assertEqual(mod.ist_to_utc(mod.to_ist(d)), d, mod.__name__)
            self.assertEqual(mod.parse_now("2026-11-19 09:15"), datetime.datetime(2026, 11, 19, 3, 45), mod.__name__)
        self.assertEqual(broker.ist_iso(datetime.datetime(2026, 11, 19, 4, 30)), "2026-11-19T10:00:00+05:30")

    def test_the_session_is_9_15_to_3_30(self):
        for mod in CALENDARS:
            self.assertEqual((mod.OPEN, mod.CLOSE), (datetime.time(9, 15), datetime.time(15, 30)), mod.__name__)
            self.assertEqual(mod.NSE_EARLY_CLOSE, {}, mod.__name__)
        self.assertEqual((tm.OPEN_MIN, tm.CLOSE_MIN, tm.SESSION_BARS), (555, 930, 75))

    def test_the_same_nse_holidays_everywhere(self):
        first = alerts.NSE_HOLIDAYS
        self.assertEqual(len(first), 16)
        for mod in CALENDARS:
            self.assertEqual(mod.NSE_HOLIDAYS, first, mod.__name__)
        for day in ("2026-01-26", "2026-03-03", "2026-10-02", "2026-10-20", "2026-11-10", "2026-11-24", "2026-12-25"):
            self.assertIn(day, first)
        self.assertEqual(first["2026-01-15"], "Municipal Corporation Election in Maharashtra")   # added Jan 12 2026


class FlatBy(unittest.TestCase):
    def test_every_day_trade_is_out_by_15_15(self):
        self.assertEqual(budget.DEFAULTS["flat_by"], "15:15")
        self.assertEqual(exitp.DEFAULTS["flat_by"], "15:15")
        self.assertEqual(risk.DEFAULTS["flat_by"], "15:15")
        rules = alerts.rules_from_plan({"symbol": "RELIANCE.NS", "date": "2026-11-19", "stop": 1490, "target": 1520})
        self.assertEqual(rules[2]["at"], "15:15")
        self.assertEqual(rules[0]["symbol"], "RELIANCE.NS")

    def test_entries_stop_before_the_flat_by(self):
        for d in (budget.DEFAULTS, entry.DEFAULTS, risk.DEFAULTS):
            self.assertEqual((d["no_entries_before"], d["no_entries_after"]), ("09:30", "14:50"))
        self.assertLess(datetime.time(14, 50), datetime.time(15, 15))

    def test_the_exit_plan_defaults_to_15_15(self):
        self.assertEqual(exitp.resolve_flat_by(datetime.date(2026, 11, 19), None, {}, datetime.time(10, 0)),
                         ("15:15", ""))
        with self.assertRaises(exitp.PlanError):           # a config flat-by past the close is refused
            exitp.resolve_flat_by(datetime.date(2026, 11, 19), None, {"flat_by": "15:40"}, datetime.time(10, 0))


if __name__ == "__main__":
    unittest.main()
