# otf-to-strava

Automatically syncs your OrangeTheory Fitness workouts to Strava — with real heart rate graphs, treadmill distance, and rower data.

![Strava activity showing HR graph from OTF data](assets/strava-screenshot.png)

## Why I built this

I go to OrangeTheory consistently and track all my workouts on Strava. The problem: OTF has no native Strava integration, so my OTF classes were just a gap in my activity feed. I got frustrated enough to build this.

It pulls real per-second heart rate telemetry from the OTF API — not just a summary — so your HR graph on Strava looks exactly like it does in the OTF app.

## What gets synced

- **Heart rate** — real per-second HR trace (shows as a graph on Strava)
- **Calories, splat points** — in the activity description
- **Treadmill distance** — makes pace show up natively on Strava for Tread workouts
- **Rower distance + avg wattage** — in the activity description
- **Activity type** — Tread → Run, Strength → WeightTraining, everything else → HIIT
- **Duplicate detection** — won't re-upload workouts already on Strava

## Setup

### Prerequisites: Get your Strava credentials

You'll need these before choosing how to run it (GitHub Actions or locally).

**Create a Strava app:**
1. Go to [strava.com/settings/api](https://www.strava.com/settings/api) to create an app
2. Fill in the form (set Website to `strava.testapp.com` and Authorization Callback Domain to `developers.strava.com`)
3. Note your **Client ID** and **Client Secret**

**Get a refresh token:**

Open this URL in your browser (replace `YOUR_CLIENT_ID`):
```
https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&response_type=code&redirect_uri=http://localhost&scope=activity:read_all,activity:write&approval_prompt=force
```

Click Authorize → the browser redirects to localhost (shows an error, that's fine) → copy the `code=` value from the URL bar.

Then run this in your terminal:
```bash
curl -X POST https://www.strava.com/oauth/token \
  -d client_id=YOUR_CLIENT_ID \
  -d client_secret=YOUR_CLIENT_SECRET \
  -d code=PASTE_CODE_HERE \
  -d grant_type=authorization_code
```

Copy the `refresh_token` from the response. You now have all three Strava credentials — proceed to one of the options below.

---

## Option A: Automate with GitHub Actions (recommended, no local install needed)

1. Fork this repo
2. Go to your fork's **Settings → Secrets and variables → Actions** and add:
   - `OTF_EMAIL`
   - `OTF_PASSWORD`
   - `STRAVA_CLIENT_ID`
   - `STRAVA_CLIENT_SECRET`
   - `STRAVA_REFRESH_TOKEN`
3. The included workflow runs every 15 minutes during typical OTF class hours and syncs automatically

You can also trigger it manually from the Actions tab at any time.

---

## Option B: Run locally

```bash
git clone https://github.com/chenwnicole/otf-to-strava
cd otf-to-strava

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:
```
OTF_EMAIL=your_otf_email
OTF_PASSWORD=your_otf_password

STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_REFRESH_TOKEN=your_refresh_token
```

**CLI options:**
```bash
python upload_to_strava.py                     # last 30 days
python upload_to_strava.py --days 7            # last N days
python upload_to_strava.py --since 2026-01-01  # since a specific date
python upload_to_strava.py --filter Tread      # only matching workouts
python upload_to_strava.py --dry-run           # preview without uploading
```

## Requirements

- Python 3.11+
- An OrangeTheory membership
- A Strava account

## Credits

OTF data powered by [otf-api](https://github.com/NodeJSmith/otf-api) by NodeJSmith.
