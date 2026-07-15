import logging
import math
from typing import Callable, Dict, List, Optional, Sequence

import pandas as pd

logger = logging.getLogger(__name__)


class RecordParseError(ValueError):
    pass


def extract_timestamp(record: Dict) -> Optional[object]:
    """Return the timestamp value from an OpenF1 record regardless of key name."""
    return record.get("date") or record.get("timestamp")


def frame_from_rows(
    rows: List[Dict],
    columns: Sequence[str],
    sort_by: str,
    dropna_subset: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """Build a DataFrame from parsed rows, sorting by ``sort_by``.

    Returns an empty DataFrame with the given ``columns`` when there are no rows.
    """
    if not rows:
        return pd.DataFrame(columns=list(columns))
    df = pd.DataFrame(rows)
    if dropna_subset:
        df = df.dropna(subset=list(dropna_subset))
    return df.sort_values(sort_by)


def parse_records(
    raw: List[Dict],
    row_builder: Callable[[Dict], Optional[Dict]],
    columns: Sequence[str],
    sort_by: str,
    dropna_subset: Optional[Sequence[str]] = None,
    record_name: str = "data",
) -> pd.DataFrame:
    """Apply ``row_builder`` to each raw record and assemble a sorted DataFrame.

    ``row_builder`` returns a row dict, or ``None`` to skip a record.
    """
    rows = []
    invalid_count = 0
    last_error = None
    for record in raw:
        try:
            built = row_builder(record)
        except (OverflowError, TypeError, ValueError) as exc:
            invalid_count += 1
            last_error = exc
            continue
        if built is None:
            invalid_count += 1
            continue
        rows.append(built)

    if invalid_count:
        logger.warning(
            "Ignored %d malformed records from %s",
            invalid_count,
            record_name,
        )
    if raw and not rows:
        error = RecordParseError(f"{record_name} contained no valid records")
        if last_error is not None:
            raise error from last_error
        raise error
    return frame_from_rows(rows, columns, sort_by, dropna_subset)


def camber_change_deg(roll_angle_deg: float, wishbone_length_mm: float) -> float:
    """Camber angle change (degrees) produced by a chassis roll on a wishbone."""
    wheel_center_shift = wishbone_length_mm * math.sin(math.radians(roll_angle_deg))
    return -math.degrees(math.atan2(wheel_center_shift, wishbone_length_mm))
