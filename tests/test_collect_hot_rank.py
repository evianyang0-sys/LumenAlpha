import unittest
from unittest.mock import patch

import pandas as pd

from scripts import collect_a_share_hot_rank_boards as collector


def forbidden_result(row):
    return {
        **row,
        "rank": None,
        "rank_change": None,
        "his_rank_change": None,
        "his_rank_change_rank": None,
        "calc_time": None,
        "market_all_count": None,
        "rank_status": "forbidden: HTTP 403",
    }


class HotRankFallbackTest(unittest.TestCase):
    def test_fetch_returns_immediately_on_403(self):
        class ForbiddenResponse:
            status_code = 403

        class Session:
            def __init__(self):
                self.calls = 0

            def post(self, *_args, **_kwargs):
                self.calls += 1
                return ForbiddenResponse()

        session = Session()
        row = {"code": "000001", "market_symbol": "SZ000001", "name": "平安银行"}
        with patch.object(collector, "get_thread_session", return_value=session):
            result = collector.fetch_latest_rank(row, retries=3)

        self.assertEqual(session.calls, 1)
        self.assertEqual(result["rank_status"], "forbidden: HTTP 403")

    def test_three_failed_probes_stop_full_collection(self):
        stocks = pd.DataFrame(
            [
                {"code": f"{index:06d}", "market_symbol": f"SZ{index:06d}", "name": str(index)}
                for index in range(10)
            ]
        )
        calls = []

        def forbidden(row, retries=3):
            calls.append((row["code"], retries))
            return forbidden_result(row)

        with patch.object(collector, "fetch_latest_rank", side_effect=forbidden):
            with self.assertRaisesRegex(collector.HotRankUnavailable, "preflight failed"):
                collector.collect_ranks(stocks, workers=2)

        self.assertEqual(calls, [("000000", 1), ("000001", 1), ("000002", 1)])


if __name__ == "__main__":
    unittest.main()
