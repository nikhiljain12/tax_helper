#!/usr/bin/env python3
"""Generate a sample employee timesheet for weekends and US public holidays."""

import argparse
import random
import sys
from datetime import date, timedelta

import holidays


def parse_date(s: str) -> date:
    for fmt in ('%Y-%m-%d', '%m/%d/%Y'):
        try:
            if fmt == '%Y-%m-%d':
                return date.fromisoformat(s)
            parts = s.split('/')
            return date(int(parts[2]), int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            continue
    raise argparse.ArgumentTypeError(f'Invalid date: {s!r}. Use YYYY-MM-DD or MM/DD/YYYY.')


def sample_hours(max_h: float = 4.0) -> float:
    """Draw from a truncated normal (mean=2.5, std=1), rounded to 0.5."""
    for _ in range(200):
        v = random.gauss(2.5, 1.0)
        if 0.5 <= v <= max_h:
            return round(v * 2) / 2
    return 2.0


def make_blocks(days: list[date]) -> list[list[date]]:
    """Group consecutive eligible days into blocks."""
    if not days:
        return []
    blocks: list[list[date]] = [[days[0]]]
    for d in days[1:]:
        if (d - blocks[-1][-1]).days == 1:
            blocks[-1].append(d)
        else:
            blocks.append([d])
    return blocks


def generate(start: date, end: date, total_hours: float) -> list[tuple[date, float]]:
    us_hols = holidays.US(years=list(range(start.year, end.year + 1)))

    eligible: list[date] = []
    d = start
    while d <= end:
        if d.weekday() >= 4 or d in us_hols:  # Fri=4, Sat=5, Sun=6
            eligible.append(d)
        d += timedelta(days=1)

    if not eligible:
        print('Warning: no eligible days (Fri/Sat/Sun/holiday) in range.', file=sys.stderr)
        return []

    blocks = make_blocks(eligible)

    # Long weekends (4+ consecutive eligible days) allow 5h/day; otherwise 4h max.
    day_max: dict[date, float] = {}
    for b in blocks:
        h = 5.0 if len(b) >= 4 else 4.0
        for d in b:
            day_max[d] = h

    max_possible = sum(day_max.values())
    target = total_hours
    if total_hours > max_possible:
        print(
            f'Warning: {total_hours}h exceeds maximum possible {max_possible:.1f}h. Capping.',
            file=sys.stderr,
        )
        target = max_possible
    target = round(target * 2) / 2  # snap to nearest 0.5h

    # Select working days per block. Weights for [0, 1, 2, ...] days selected.
    work_days: set[date] = set()
    for block in blocks:
        n = len(block)
        if n == 1:
            k = random.choices([0, 1], weights=[15, 85])[0]
        elif n == 2:
            k = random.choices([0, 1, 2], weights=[15, 50, 35])[0]
        elif n == 3:
            k = random.choices([0, 1, 2, 3], weights=[15, 40, 35, 10])[0]
        else:  # long weekend
            k = min(random.choices([0, 1, 2, 3, 4], weights=[10, 25, 35, 20, 10])[0], n)
        if k:
            work_days.update(random.sample(block, k))

    if not work_days:
        work_days.add(random.choice(eligible))

    # Assign initial hours from truncated normal.
    assignments: dict[date, float] = {d: sample_hours(day_max[d]) for d in work_days}

    # If selected days can't cover target, pull in more eligible days.
    extra = [d for d in eligible if d not in assignments]
    random.shuffle(extra)
    for d in extra:
        if sum(day_max[x] for x in assignments) >= target:
            break
        assignments[d] = sample_hours(day_max[d])

    assignments = _adjust(assignments, day_max, target)
    return sorted(assignments.items())


def _adjust(
    assignments: dict[date, float],
    day_max: dict[date, float],
    target: float,
) -> dict[date, float]:
    """Scale then fine-tune assignments so they sum exactly to target."""
    if not assignments:
        return assignments

    # Proportional scaling to get close quickly.
    current = sum(assignments.values())
    if current > 0 and current != target:
        scale = target / current
        for d in assignments:
            h = round(assignments[d] * scale * 2) / 2
            assignments[d] = max(0.5, min(h, day_max[d]))

    # Fine-tune with ±0.5h steps.
    for _ in range(10_000):
        current = sum(assignments.values())
        diff = round((target - current) * 2)  # units of 0.5h
        if diff == 0:
            break

        days = list(assignments.keys())
        random.shuffle(days)

        if diff > 0:
            progress = False
            for d in days:
                if assignments[d] < day_max[d]:
                    assignments[d] += 0.5
                    diff -= 1
                    progress = True
                    if diff == 0:
                        break
            if not progress:
                break  # all days at max; target unachievable (already capped upstream)
        else:
            progress = False
            for d in days:
                if assignments[d] > 0.5:
                    assignments[d] -= 0.5
                    diff += 1
                    progress = True
                    if diff == 0:
                        break
            if not progress:
                # All days at minimum — drop the shortest to reduce total.
                if assignments:
                    d_min = min(assignments, key=lambda x: assignments[x])
                    del assignments[d_min]

    return assignments


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Generate a sample employee timesheet for weekends/US holidays.'
    )
    parser.add_argument(
        '--start', required=True, type=parse_date, metavar='DATE',
        help='Start date (YYYY-MM-DD or MM/DD/YYYY)',
    )
    parser.add_argument(
        '--end', required=True, type=parse_date, metavar='DATE',
        help='End date (YYYY-MM-DD or MM/DD/YYYY)',
    )
    parser.add_argument(
        '--hours', required=True, type=float, metavar='HOURS',
        help='Total hours to distribute',
    )
    parser.add_argument('--seed', type=int, help='Random seed for reproducibility')
    args = parser.parse_args()

    if args.start > args.end:
        parser.error('--start must be before or equal to --end')
    if args.hours <= 0:
        parser.error('--hours must be positive')
    if args.seed is not None:
        random.seed(args.seed)

    rows = generate(args.start, args.end, args.hours)
    if not rows:
        sys.exit(1)

    for d, h in rows:
        print(f'{d.strftime("%m/%d/%Y")},{h:g}')

    total = sum(h for _, h in rows)
    print(f'# Total: {total:g}h across {len(rows)} days', file=sys.stderr)


if __name__ == '__main__':
    main()
