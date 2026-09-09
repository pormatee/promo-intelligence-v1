from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import subprocess
import sys
from typing import Callable


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class UpdatePolicy:
    scheduled_interval_seconds: int = 86400
    on_demand_min_age_seconds: int = 900
    on_demand_cooldown_seconds: int = 300
    lock_file: str = "data/state/promo_refresh.lock"
    state_file: str = "data/state/promo_update_state.json"


def load_policy(path: str | Path) -> UpdatePolicy:
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return UpdatePolicy(
        scheduled_interval_seconds=int(raw.get("scheduled_interval_seconds", 86400)),
        on_demand_min_age_seconds=int(raw.get("on_demand_min_age_seconds", 900)),
        on_demand_cooldown_seconds=int(raw.get("on_demand_cooldown_seconds", 300)),
        lock_file=str(raw.get("lock_file", "data/state/promo_refresh.lock")),
        state_file=str(raw.get("state_file", "data/state/promo_update_state.json")),
    )


def _state_path(root: Path, policy: UpdatePolicy) -> Path:
    return root / policy.state_file


def load_state(root: str | Path, policy: UpdatePolicy) -> dict:
    p = _state_path(Path(root), policy)
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(root: Path, policy: UpdatePolicy, state: dict) -> None:
    p = _state_path(root, policy)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(p)


def age_seconds(state: dict, now: datetime | None = None) -> float | None:
    now = now or _utcnow()
    last = _parse(state.get("last_success_at"))
    if not last:
        return None
    return max(0.0, (now - last).total_seconds())


def scheduled_due(state: dict, policy: UpdatePolicy, now: datetime | None = None) -> bool:
    age = age_seconds(state, now)
    return age is None or age >= policy.scheduled_interval_seconds


def on_demand_due(state: dict, policy: UpdatePolicy, now: datetime | None = None) -> bool:
    age = age_seconds(state, now)
    return age is None or age >= policy.on_demand_min_age_seconds


def default_refresh_runner(root: Path) -> int:
    return subprocess.call([sys.executable, "autonomous_promo.py", "--core-refresh"], cwd=root)


def request_refresh(project_root: str | Path, mode: str, requester: str = "external_consumer", reason: str = "",
                    now: datetime | None = None, runner: Callable[[Path], int] | None = None) -> dict:
    if mode not in {"scheduled", "on_demand", "manual"}:
        raise ValueError("mode must be scheduled, on_demand, or manual")
    root = Path(project_root)
    policy = load_policy(root / "config" / "update_policy.json")
    supplied_now = now
    now = now or _utcnow()
    state = load_state(root, policy)

    if mode == "scheduled" and not scheduled_due(state, policy, now):
        return {"decision": "use_published", "reason": "scheduled_not_due", "age_seconds": age_seconds(state, now)}
    if mode == "on_demand" and not on_demand_due(state, policy, now):
        return {"decision": "use_published", "reason": "published_fresh_enough", "age_seconds": age_seconds(state, now)}

    lock_path = root / policy.lock_file
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("a+")
    try:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"decision": "join_existing", "reason": "single_flight_active"}

        # Recheck after lock acquisition. A concurrent updater may have finished
        # between the first freshness check and acquiring the lock.
        state = load_state(root, policy)
        if mode == "scheduled" and not scheduled_due(state, policy, now):
            return {"decision": "use_published", "reason": "scheduled_completed_by_peer", "age_seconds": age_seconds(state, now)}
        if mode == "on_demand" and not on_demand_due(state, policy, now):
            return {"decision": "use_published", "reason": "refresh_completed_by_peer", "age_seconds": age_seconds(state, now)}

        last_request = _parse(state.get("last_request_at"))
        if mode == "on_demand" and last_request and (now - last_request).total_seconds() < policy.on_demand_cooldown_seconds and state.get("last_result") == "fail":
            return {"decision": "use_published", "reason": "failure_cooldown"}

        state.update({
            "last_request_at": _iso(now),
            "last_request_mode": mode,
            "last_requester": requester,
            "last_reason": reason,
            "running": True,
        })
        _write_state(root, policy, state)

        rc = (runner or default_refresh_runner)(root)
        finished = _utcnow() if supplied_now is None else now
        state = load_state(root, policy)
        state["running"] = False
        state["last_result"] = "pass" if rc == 0 else "fail"
        state["last_finished_at"] = _iso(finished)
        if rc == 0:
            state["last_success_at"] = _iso(finished)
        _write_state(root, policy, state)
        return {
            "decision": "refreshed" if rc == 0 else "refresh_failed",
            "reason": "completed",
            "return_code": rc,
            "mode": mode,
        }
    finally:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        lock_file.close()
