#!/usr/bin/env python3

"""
Task Coordinator — centralized clock-based scheduler for background tasks.

Replaces the pattern:
    while True:
        await asyncio.sleep(interval * jitter)
        # ... work ...

With:
    coordinator.register("task_name", work_func, "interval:30m")
    # coordinator handles scheduling, concurrency, idle gating

Schedule expressions:
    "daily@HH:MM"              Every day at given time
    "interval:Xs"              Every X seconds on the clock (not relative to startup)
    "interval:Xm"              Every X minutes on the clock
    "interval:Xh"              Every X hours on the clock
    "interval:Xh,anchor=HH:MM" Every X hours starting from anchor time
    ",idle" suffix             Only runs when user is idle (10+ min inactivity)
    ",quiet" suffix            Only runs during quiet hours (midnight-6am CT)

Categories control concurrency:
    "db_light"  Can run freely alongside anything
    "db_heavy"  Per-database mutex (one writer per database at a time)
    "llm"       Global mutex (one LLM-heavy task at a time)
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Dict, Optional, Set
from zoneinfo import ZoneInfo

# Module-level global coordinator singleton for cross-file task registration
_global_coordinator: Optional['TaskCoordinator'] = None


def get_global_coordinator() -> 'TaskCoordinator':
    """Get or create the global TaskCoordinator singleton."""
    global _global_coordinator
    if _global_coordinator is None:
        _global_coordinator = TaskCoordinator()
    return _global_coordinator


logger = logging.getLogger(__name__)

DEFAULT_QUIET_START = 0
DEFAULT_QUIET_END = 6
IDLE_THRESHOLD_SECONDS = 600


class ScheduleExpr:
    """Parses and evaluates schedule expressions."""

    def __init__(self, expr: str):
        self.raw = expr
        self.type: str = "interval"
        self.value: int = 0
        self.hour: int = 0
        self.minute: int = 0
        self.anchor_hour: int = 0
        self.anchor_minute: int = 0
        self.requires_idle: bool = False
        self.requires_quiet: bool = False
        self._parse(expr)

    def _parse(self, expr: str):
        parts = expr.split(",")
        base = parts[0]
        for p in parts[1:]:
            if p == "idle":
                self.requires_idle = True
            elif p == "quiet":
                self.requires_quiet = True
            elif p.startswith("anchor="):
                anchor_time = p[7:]
                self.anchor_hour, self.anchor_minute = map(int, anchor_time.split(":"))

        if base.startswith("daily@"):
            self.type = "daily"
            time_part = base[6:]
            if ":" in time_part:
                self.hour, self.minute = map(int, time_part.split(":"))
            else:
                self.hour = int(time_part)
                self.minute = 0
        elif base.startswith("interval:"):
            self.type = "interval"
            rest = base[9:]
            if rest.endswith("s"):
                self.value = int(rest[:-1])
            elif rest.endswith("m"):
                self.value = int(rest[:-1]) * 60
            elif rest.endswith("h"):
                self.value = int(rest[:-1]) * 3600
            else:
                self.value = int(rest)

    def next_after(self, now: datetime) -> datetime:
        """Return the next scheduled datetime after `now`."""
        if self.type == "daily":
            candidate = now.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)
            if candidate <= now:
                candidate += timedelta(days=1)
            return candidate
        elif self.type == "interval":
            if self.value <= 0:
                return now + timedelta(seconds=60)
            anchor = now.replace(hour=self.anchor_hour, minute=self.anchor_minute, second=0, microsecond=0)
            if anchor > now:
                anchor -= timedelta(days=1)
            seconds_since = (now - anchor).total_seconds()
            intervals_passed = int(seconds_since // self.value)
            return anchor + timedelta(seconds=(intervals_passed + 1) * self.value)
        return now + timedelta(seconds=60)


class TaskDef:
    """Definition of a scheduled task."""

    def __init__(
        self,
        name: str,
        func: Callable[[], Awaitable[None]],
        schedule: ScheduleExpr,
        category: str = "db_light",
        db: Optional[str] = None,
        max_errors: int = 5,
        valve_enabled: Optional[Callable[[], bool]] = None,
    ):
        self.name = name
        self.func = func
        self.schedule = schedule
        self.category = category
        self.db = db
        self.max_errors = max_errors
        self.valve_enabled = valve_enabled
        self.consecutive_errors = 0
        self.disabled = False
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self.is_running = False

    def should_run(self, now: datetime) -> bool:
        if self.disabled:
            return False
        if self.is_running:
            return False
        if self.valve_enabled is not None and not self.valve_enabled():
            return False
        if self.next_run is None:
            self.next_run = self.schedule.next_after(now)
        return self.next_run <= now


class TaskCoordinator:
    """Centralized scheduler for background tasks."""

    def __init__(self, timezone_name: str = "America/Chicago"):
        self._tasks: Dict[str, TaskDef] = {}
        self._db_locks: Dict[str, str] = {}
        self._llm_lock: Optional[str] = None
        self._last_inlet_time: Optional[datetime] = None
        self._scheduler_task: Optional[asyncio.Task] = None
        self._timezone = ZoneInfo(timezone_name)
        self._stopped = False

    def record_activity(self):
        self._last_inlet_time = datetime.now(timezone.utc)

    def is_idle(self) -> bool:
        if self._last_inlet_time is None:
            return True
        now = datetime.now(timezone.utc)
        idle = (now - self._last_inlet_time).total_seconds()
        return idle >= IDLE_THRESHOLD_SECONDS

    def is_quiet_hours(self) -> bool:
        now = datetime.now(self._timezone)
        return DEFAULT_QUIET_START <= now.hour < DEFAULT_QUIET_END

    def register(
        self,
        name: str,
        func: Callable[[], Awaitable[None]],
        schedule_expr: str,
        category: str = "db_light",
        db: Optional[str] = None,
        max_errors: int = 5,
        valve_enabled: Optional[Callable[[], bool]] = None,
    ):
        schedule = ScheduleExpr(schedule_expr)
        task = TaskDef(name, func, schedule, category, db, max_errors, valve_enabled)
        task.next_run = schedule.next_after(datetime.now(self._timezone))
        self._tasks[name] = task
        logger.debug(f"Coordinator registered task '{name}' — next run: {task.next_run.isoformat()}")

    def unregister(self, name: str):
        self._tasks.pop(name, None)

    async def start(self):
        global _global_coordinator
        if self._scheduler_task:
            return
        self._stopped = False
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        _global_coordinator = self
        logger.info("Task coordinator started")

    async def stop(self):
        self._stopped = True
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
            self._scheduler_task = None
        logger.info("Task coordinator stopped")

    async def _scheduler_loop(self):
        """Main scheduler loop — checks due tasks every 30 seconds."""
        try:
            while not self._stopped:
                try:
                    now = datetime.now(self._timezone)
                    self._check_due_tasks(now)
                except Exception as e:
                    logger.error(f"Coordinator scheduler error: {e}")
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            logger.debug("Coordinator scheduler loop cancelled")

    def _check_due_tasks(self, now: datetime):
        for name, task in self._tasks.items():
            if not task.should_run(now):
                continue
            if task.schedule.requires_idle and not self.is_idle():
                continue
            if task.schedule.requires_quiet and not self.is_quiet_hours():
                task.next_run = task.schedule.next_after(now)
                continue
            if not self._can_acquire_resources(task):
                continue
            task.is_running = True
            task.next_run = task.schedule.next_after(now)
            asyncio.create_task(self._run_task(name))

    def _can_acquire_resources(self, task: TaskDef) -> bool:
        if task.category == "llm" and self._llm_lock is not None:
            return False
        if task.category == "db_heavy" and task.db and task.db in self._db_locks:
            return False
        return True

    def _acquire_resources(self, task: TaskDef):
        if task.category == "llm":
            self._llm_lock = task.name
        if task.category == "db_heavy" and task.db:
            self._db_locks[task.db] = task.name

    def _release_resources(self, task: TaskDef):
        if task.category == "llm" and self._llm_lock == task.name:
            self._llm_lock = None
        if task.category == "db_heavy" and task.db:
            if self._db_locks.get(task.db) == task.name:
                del self._db_locks[task.db]

    async def _run_task(self, name: str):
        task = self._tasks.get(name)
        if not task:
            return
        self._acquire_resources(task)
        try:
            await task.func()
            task.consecutive_errors = 0
            task.last_run = datetime.now(self._timezone)
            logger.debug(f"Coordinator: task '{name}' completed")
        except asyncio.CancelledError:
            logger.debug(f"Coordinator: task '{name}' cancelled")
        except Exception as e:
            task.consecutive_errors += 1
            logger.error(f"Coordinator: task '{name}' error ({task.consecutive_errors}/{task.max_errors}): {e}")
            if task.consecutive_errors >= task.max_errors:
                task.disabled = True
                logger.critical(f"Coordinator: task '{name}' disabled after {task.max_errors} consecutive errors")
        finally:
            task.is_running = False
            self._release_resources(task)
