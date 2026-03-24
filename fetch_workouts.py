#!/usr/bin/env python3
"""
Fetch and display recent Orangetheory workouts.

Usage:
    python fetch_workouts.py           # last 30 days
    python fetch_workouts.py --days 7  # last 7 days
"""

import argparse
from datetime import date, timedelta

from dotenv import load_dotenv
from otf_api import Otf

load_dotenv()


def display_workout(workout, i: int) -> None:
    cls = workout.otf_class
    hr = workout.heart_rate
    zones = workout.zone_time_minutes

    print(f"\n{'─' * 50}")
    print(f"Workout #{i}: {cls.name if cls else 'Unknown'}")
    print(f"  Date:         {cls.starts_at if cls else 'Unknown'}")
    print(f"  Coach:        {workout.coach or '—'}")
    print(f"  Duration:     {workout.active_time_seconds and f'{workout.active_time_seconds // 60} min' or '—'}")
    print(f"  Calories:     {workout.calories_burned or '—'}")
    print(f"  Splat points: {workout.splat_points or '—'}")

    if hr:
        print(f"  Heart rate:   avg {hr.avg_hr} bpm ({hr.avg_hr_percent}%)  |  max {hr.max_hr} bpm")

    if zones:
        print(
            f"  Zones (min):  "
            f"Gray {zones.gray} | Blue {zones.blue} | Green {zones.green} "
            f"| Orange {zones.orange} | Red {zones.red}"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30, help="Days to look back (default: 30)")
    args = parser.parse_args()

    start_date = date.today() - timedelta(days=args.days)
    print(f"Fetching OTF workouts since {start_date}...")

    otf = Otf()  # reads OTF_EMAIL and OTF_PASSWORD from env
    workouts = otf.workouts.get_workouts(start_date=start_date)

    print(f"Found {len(workouts)} workout(s)")

    for i, workout in enumerate(workouts, 1):
        display_workout(workout, i)

    print(f"\n{'─' * 50}")


if __name__ == "__main__":
    main()
