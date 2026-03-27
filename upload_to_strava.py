#!/usr/bin/env python3
"""
Fetch recent Orangetheory workouts and upload them to Strava with real HR data.

Usage:
    python upload_to_strava.py           # last 30 days
    python upload_to_strava.py --days 7  # last 7 days
    python upload_to_strava.py --dry-run # preview without uploading
    python upload_to_strava.py --filter Hyrox  # only matching workouts

Required .env variables:
    OTF_EMAIL, OTF_PASSWORD
    STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN
"""

import argparse
import io
import os
import time
from datetime import date, datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from otf_api import Otf

load_dotenv()

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ATHLETE_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
STRAVA_UPLOADS_URL = "https://www.strava.com/api/v3/uploads"


def get_strava_access_token() -> str:
    resp = requests.post(STRAVA_TOKEN_URL, data={
        "client_id": os.environ["STRAVA_CLIENT_ID"],
        "client_secret": os.environ["STRAVA_CLIENT_SECRET"],
        "refresh_token": os.environ["STRAVA_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_existing_strava_start_times(access_token: str, after: date) -> set[str]:
    after_ts = int(datetime.combine(after, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    start_times = set()
    page = 1
    while True:
        resp = requests.get(
            STRAVA_ATHLETE_ACTIVITIES_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            params={"after": after_ts, "per_page": 100, "page": page},
        )
        resp.raise_for_status()
        activities = resp.json()
        if not activities:
            break
        for a in activities:
            dt = datetime.fromisoformat(a["start_date_local"].replace("Z", ""))
            start_times.add(dt.strftime("%Y-%m-%dT%H:%M"))
        page += 1
    return start_times


def get_sport_type(class_name: str) -> str:
    name = class_name.lower()
    if "tread" in name:
        return "Run"
    if "strength" in name:
        return "WeightTraining"
    return "HighIntensityIntervalTraining"


def build_description(workout) -> str:
    hr = workout.heart_rate
    zones = workout.zone_time_minutes
    parts = []

    tread = workout.treadmill_data
    if tread:
        tread_parts = []
        if tread.moving_time:
            tread_parts.append(f"{tread.moving_time.display_value} {tread.moving_time.display_unit}")
        if tread.total_distance:
            tread_parts.append(f"{tread.total_distance.display_value} {tread.total_distance.display_unit}")
        if tread.elevation_gained:
            tread_parts.append(f"elev {tread.elevation_gained.display_value} {tread.elevation_gained.display_unit}")
        if tread_parts:
            parts.append("Treadmill: " + " | ".join(tread_parts))

    rower = workout.rower_data
    if rower:
        rower_parts = []
        if rower.moving_time:
            rower_parts.append(f"{rower.moving_time.display_value} {rower.moving_time.display_unit}")
        if rower.total_distance:
            rower_parts.append(f"{rower.total_distance.display_value} {rower.total_distance.display_unit}")
        if rower.avg_power:
            rower_parts.append(f"avg {rower.avg_power.display_value} {rower.avg_power.display_unit}")
        if rower_parts:
            parts.append("Rower: " + " | ".join(rower_parts))

    if workout.splat_points:
        parts.append(f"Splat points: {workout.splat_points}")

    return "\n".join(parts)


def _fmt_time(dt: datetime) -> str:
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_meters(value, unit: str) -> float:
    """Convert a distance value to meters based on its unit."""
    value = float(value)
    unit = (unit or "").lower()
    if "mi" in unit:
        return value * 1609.344
    if "km" in unit:
        return value * 1000
    return value  # assume meters


def generate_tcx(workout, telemetry, sport_type: str) -> bytes:
    cls = workout.otf_class
    hr = workout.heart_rate
    start_dt = cls.starts_at
    elapsed = workout.active_time_seconds or 0
    calories = workout.calories_burned or 0

    is_tread = sport_type == "Run"
    tread_summary = workout.treadmill_data if is_tread else None
    trackpoints = []
    for item in telemetry.telemetry:
        if not item.timestamp:
            continue
        lines = [f"            <Time>{_fmt_time(item.timestamp)}</Time>"]
        if item.hr:
            lines.append(f"            <HeartRateBpm><Value>{item.hr}</Value></HeartRateBpm>")
        if is_tread and item.tread_data and item.tread_data.agg_tread_distance is not None:
            # agg_tread_distance is a raw int in meters
            lines.append(f"            <DistanceMeters>{item.tread_data.agg_tread_distance}</DistanceMeters>")
        trackpoints.append(
            "          <Trackpoint>\n" + "\n".join(lines) + "\n          </Trackpoint>"
        )

    avg_hr_xml = f"        <AverageHeartRateBpm><Value>{hr.avg_hr}</Value></AverageHeartRateBpm>\n" if hr else ""
    max_hr_xml = f"        <MaximumHeartRateBpm><Value>{hr.max_hr}</Value></MaximumHeartRateBpm>\n" if hr else ""

    dist_xml = ""
    if is_tread and tread_summary and tread_summary.total_distance:
        total_m = _to_meters(
            tread_summary.total_distance.display_value,
            tread_summary.total_distance.display_unit,
        )
        dist_xml = f"        <DistanceMeters>{total_m:.1f}</DistanceMeters>\n"

    tcx = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">\n'
        "  <Activities>\n"
        '    <Activity Sport="Other">\n'
        f"      <Id>{_fmt_time(start_dt)}</Id>\n"
        f'      <Lap StartTime="{_fmt_time(start_dt)}">\n'
        f"        <TotalTimeSeconds>{elapsed}</TotalTimeSeconds>\n"
        f"        <Calories>{calories}</Calories>\n"
        f"{dist_xml}"
        f"{avg_hr_xml}"
        f"{max_hr_xml}"
        "        <Intensity>Active</Intensity>\n"
        "        <TriggerMethod>Manual</TriggerMethod>\n"
        "        <Track>\n"
        + "\n".join(trackpoints) + "\n"
        "        </Track>\n"
        "      </Lap>\n"
        "    </Activity>\n"
        "  </Activities>\n"
        "</TrainingCenterDatabase>"
    )
    return tcx.encode("utf-8")


def upload_tcx_to_strava(tcx_data: bytes, name: str, sport_type: str, description: str, access_token: str) -> str:
    resp = requests.post(
        STRAVA_UPLOADS_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        data={"name": name, "sport_type": sport_type, "description": description, "data_type": "tcx"},
        files={"file": ("workout.tcx", io.BytesIO(tcx_data), "application/octet-stream")},
    )
    resp.raise_for_status()
    upload_id = resp.json()["id"]

    for _ in range(30):
        time.sleep(2)
        resp = requests.get(
            f"{STRAVA_UPLOADS_URL}/{upload_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            if "duplicate" in data["error"].lower():
                return None  # already uploaded, skip silently
            raise Exception(f"Strava upload error: {data['error']}")
        if data.get("activity_id"):
            return data["activity_id"]

    raise Exception("Timed out waiting for Strava to process upload")


def upload_workout(workout, otf: Otf, access_token: str, dry_run: bool, existing: set[str]) -> None:
    cls = workout.otf_class
    name = f"OTF: {cls.name}" if cls else "OTF Workout"
    start_dt = cls.starts_at if cls else None

    if not start_dt:
        print("  Skipping — no start time available")
        return

    start_key = start_dt.strftime("%Y-%m-%dT%H:%M")
    if start_key in existing:
        print("  Already on Strava — skipping")
        return

    sport_type = get_sport_type(name)
    description = build_description(workout)

    # Fetch telemetry for real HR trace
    telemetry = None
    try:
        telemetry = otf.workouts.get_telemetry(workout.performance_summary_id)
        hr_points = [t for t in (telemetry.telemetry or []) if t.hr]
        if not hr_points:
            telemetry = None
    except Exception as e:
        print(f"  Warning: could not fetch telemetry ({e}), falling back to summary upload")

    if dry_run:
        hr_points = len([t for t in (telemetry.telemetry or []) if t.hr]) if telemetry else 0
        print(f"  [dry-run] Would upload: {name} on {start_dt}")
        print(f"    Sport: {sport_type} | Duration: {(workout.active_time_seconds or 0) // 60} min | Calories: {workout.calories_burned}")
        print(f"    HR data points: {hr_points if telemetry else 'none (summary only)'}")
        print(f"    {description}")
        return

    tcx_data = generate_tcx(workout, telemetry, sport_type) if telemetry else None

    if tcx_data:
        activity_id = upload_tcx_to_strava(tcx_data, name, sport_type, description, access_token)
        if activity_id is None:
            print("  Already on Strava — skipping")
            return
        print(f"  Uploaded with HR trace -> strava.com/activities/{activity_id}")
    else:
        # Fallback: create manual activity without HR trace
        resp = requests.post(
            "https://www.strava.com/api/v3/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "name": name,
                "sport_type": sport_type,
                "start_date_local": start_dt.isoformat(),
                "elapsed_time": workout.active_time_seconds or 0,
                "description": description,
                "calories": workout.calories_burned,
            },
        )
        resp.raise_for_status()
        activity_id = resp.json()["id"]
        print(f"  Uploaded (summary only) -> strava.com/activities/{activity_id}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30, help="Days to look back (default: 30)")
    parser.add_argument("--since", metavar="YYYY-MM-DD", help="Start date (overrides --days)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without uploading to Strava")
    parser.add_argument("--filter", metavar="NAME", help="Only process workouts whose name contains this string (case-insensitive)")
    args = parser.parse_args()

    if args.since:
        start_date = date.fromisoformat(args.since)
    else:
        start_date = date.today() - timedelta(days=args.days)
    print(f"Fetching OTF workouts since {start_date}...")

    otf = Otf()
    workouts = otf.workouts.get_workouts(start_date=start_date)
    print(f"Found {len(workouts)} workout(s)")

    if args.filter:
        workouts = [w for w in workouts if args.filter.lower() in (w.otf_class.name or "").lower()]
        print(f"Filtered to {len(workouts)} workout(s) matching '{args.filter}'")

    if not args.dry_run:
        print("Getting Strava access token...")
        access_token = get_strava_access_token()
        print("Checking for existing Strava activities...")
        existing = get_existing_strava_start_times(access_token, start_date)
        print(f"Found {len(existing)} existing Strava activity/activities in this window")
    else:
        access_token = None
        existing = set()
        print("Dry-run mode — no uploads will be made\n")

    for i, workout in enumerate(workouts, 1):
        cls = workout.otf_class
        label = cls.name if cls else f"Workout #{i}"
        start = cls.starts_at if cls else "?"
        print(f"\n[{i}/{len(workouts)}] {label} ({start})")
        upload_workout(workout, otf, access_token, dry_run=args.dry_run, existing=existing)

    print("\nDone.")


if __name__ == "__main__":
    main()
