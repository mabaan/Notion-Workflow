from datetime import date

from research_automation.utils.dates import current_workweek
from research_automation.utils.edition_numbers import ordinal


def test_current_workweek_runs_monday_to_friday() -> None:
    workweek = current_workweek(date(2026, 7, 1))
    assert workweek.start == date(2026, 6, 29)
    assert workweek.end == date(2026, 7, 3)


def test_ordinal_formatting_handles_edge_cases() -> None:
    assert ordinal(1) == "1st"
    assert ordinal(2) == "2nd"
    assert ordinal(3) == "3rd"
    assert ordinal(4) == "4th"
    assert ordinal(11) == "11th"
    assert ordinal(12) == "12th"
    assert ordinal(13) == "13th"
    assert ordinal(21) == "21st"
