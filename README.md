# otf-to-strava

Automatically syncs your OrangeTheory Fitness workouts to Strava — with real heart rate graphs, treadmill distance, and rower data.

![Strava activity showing HR graph from OTF data](https://placeholder)

## What gets synced

- **Heart rate** — real per-second HR trace (shows as a graph on Strava)
- **Calories, splat points, zone minutes** — in the activity description
- **Treadmill distance** — makes pace show up natively on Strava for Tread workouts
- **Rower distance + avg wattage** — in the activity description
- **Activity type** — Tread → Run, Strength → WeightTraining, Hyrox → HIIT, everything else → Workout
- **Duplicate detection** — won't re-upload workouts already on Strava

## Setup

### 1. Clone and install

```bash
git clone https://github.com/chenwnicole/otf-to-strava
cd otf-to-strava
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. OTF credentials

On first run, the script will prompt for your OTF email and password and save them securely to your system keychain. No config needed.

### 3. Strava credentials

**Create a Strava app:**
1. Go to [strava.com/settings/api](https://www.strava.com/settings/api)
2. Fill in the form (name/description can be anything, set Website to `localhost`)
3. Note your **Client ID** and **Client Secret**

**Get a refresh token:**

Open this URL in your browser (replace `YOUR_CLIENT_ID`):
```
https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&response_type=code&redirect_uri=http://localhost&scope=activity:read_all,activity:write&approval_prompt=force
```

Click Authorize → the browser will redirect to localhost (shows an error, that's fine) → copy the `code=` value from the URL bar.

Then run:
```bash
curl -X POST https://www.strava.com/oauth/token \
  -d client_id=YOUR_CLIENT_ID \
  -d client_secret=YOUR_CLIENT_SECRET \
  -d code=PASTE_CODE_HERE \
  -d grant_type=authorization_code
```

Copy the `refresh_token` from the response.

**Create a `.env` file:**
```
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_REFRESH_TOKEN=your_refresh_token
```

### 4. Run it

```bash
python upload_to_strava.py
```

## Usage

```bash
python upload_to_strava.py                     # last 30 days
python upload_to_strava.py --days 7            # last N days
python upload_to_strava.py --since 2026-01-01  # since a specific date
python upload_to_strava.py --filter Tread      # only matching workouts
python upload_to_strava.py --dry-run           # preview without uploading
```

## Automate with GitHub Actions

To sync automatically after every class:

1. Push this repo to GitHub (private is fine)
2. Go to **Settings → Secrets and variables → Actions** and add:
   - `OTF_EMAIL`
   - `OTF_PASSWORD`
   - `STRAVA_CLIENT_ID`
   - `STRAVA_CLIENT_SECRET`
   - `STRAVA_REFRESH_TOKEN`
3. The included workflow (`.github/workflows/sync.yml`) runs every 15 minutes during typical OTF class hours

You can also trigger it manually from the Actions tab.

## Requirements

- Python 3.11+
- An OrangeTheory membership
- A Strava account
