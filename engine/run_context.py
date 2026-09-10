"""
Central Runtime Context for Indian Stock Market Fundamental News Analysis (FNA).
Enforces Section 7-10:
One unified runtime context (RunContext) governing mode ('live' vs 'historical'),
target_date, cutoff_datetime, and Asia/Kolkata timezone.
Guarantees historical integrity: no module uses datetime.now() or unverified current data
when reconstructing past dates.
"""

from dataclasses import dataclass
from datetime import datetime
import zoneinfo
from typing import Optional

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


@dataclass
class RunContext:
    mode: str  # "live" | "historical"
    target_date: str  # "YYYY-MM-DD"
    cutoff_datetime: datetime
    timezone: str = "Asia/Kolkata"

    @property
    def is_historical(self) -> bool:
        return self.mode == "historical"

    def is_eligible(self, pub_dt: Optional[datetime]) -> bool:
        """
        Enforces Section 8:
        event publication time <= target-date cutoff
        For historical mode: event must be on target_date and <= cutoff_datetime.
        For live mode: event must be <= cutoff_datetime.
        """
        if pub_dt is None:
            return not self.is_historical
        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=IST)
        else:
            pub_dt = pub_dt.astimezone(IST)

        if pub_dt > self.cutoff_datetime:
            return False
        if self.is_historical:
            return pub_dt.strftime("%Y-%m-%d") == self.target_date
        return True


_GLOBAL_RUN_CONTEXT: Optional[RunContext] = None


def get_current_context() -> Optional[RunContext]:
    """Returns the active RunContext if set."""
    return _GLOBAL_RUN_CONTEXT


def set_current_context(ctx: RunContext) -> None:
    """Sets the active RunContext globally across all pipeline modules."""
    global _GLOBAL_RUN_CONTEXT
    _GLOBAL_RUN_CONTEXT = ctx
