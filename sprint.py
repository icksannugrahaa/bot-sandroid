from datetime import date, timedelta

# Sprint 18 dimulai pada 2026-01-26 (hari kerja)
SPRINT_18_START = date(2026, 1, 26)
SPRINT_LENGTH = 10  # hari kerja

def get_current_sprint(today: date) -> int:
    sprint = 18
    start = SPRINT_18_START

    while True:
        work_days = 0
        d = start
        while work_days < SPRINT_LENGTH:
            if d.weekday() < 5:
                work_days += 1
            d += timedelta(days=1)

        if start <= today < d:
            return sprint

        sprint += 1
        start = d

