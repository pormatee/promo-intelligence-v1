from datetime import datetime, timedelta, timezone
import fcntl
import json
import tempfile
import unittest
from pathlib import Path

from promo_intelligence.update_strategy import UpdatePolicy, load_policy, load_state, on_demand_due, request_refresh, scheduled_due


class UpdateStrategyTest(unittest.TestCase):
    def _root(self, td):
        root = Path(td)
        (root / "config").mkdir(parents=True)
        (root / "config" / "update_policy.json").write_text(json.dumps({
            "scheduled_interval_seconds": 86400,
            "on_demand_min_age_seconds": 900,
            "on_demand_cooldown_seconds": 300,
            "lock_file": "data/state/promo_refresh.lock",
            "state_file": "data/state/promo_update_state.json"
        }), encoding="utf-8")
        return root

    def test_daily_and_on_demand_freshness_rules(self):
        p = UpdatePolicy()
        now = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
        state = {"last_success_at": (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")}
        self.assertFalse(scheduled_due(state, p, now))
        self.assertTrue(on_demand_due(state, p, now))
        fresh = {"last_success_at": (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")}
        self.assertFalse(on_demand_due(fresh, p, now))

    def test_on_demand_uses_fresh_published_without_refresh(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._root(td)
            policy = load_policy(root / "config" / "update_policy.json")
            now = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
            state_path = root / policy.state_file
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps({"last_success_at": (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")}), encoding="utf-8")
            called=[]
            result = request_refresh(root, "on_demand", now=now, runner=lambda r: called.append(1) or 0)
            self.assertEqual(result["decision"], "use_published")
            self.assertEqual(called, [])

    def test_single_flight_returns_join_existing(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._root(td)
            policy = load_policy(root / "config" / "update_policy.json")
            lock_path = root / policy.lock_file
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            f = lock_path.open("a+")
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                result = request_refresh(root, "on_demand", now=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc), runner=lambda r: 0)
                self.assertEqual(result["decision"], "join_existing")
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN); f.close()

    def test_successful_refresh_updates_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._root(td)
            now = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
            result = request_refresh(root, "scheduled", requester="scheduler", now=now, runner=lambda r: 0)
            self.assertEqual(result["decision"], "refreshed")
            policy = load_policy(root / "config" / "update_policy.json")
            state = load_state(root, policy)
            self.assertEqual(state["last_result"], "pass")
            self.assertEqual(state["last_request_mode"], "scheduled")


if __name__ == "__main__": unittest.main()
