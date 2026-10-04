# CareVoice

CareVoice is a Streamlit health assistant with medicine schedules, health tracking, voice queries, and daily diet guidance.

## Local setup

Use Python 3.11 or newer and install the project dependencies:

```powershell
python -m pip install -r requirements.txt
```

Keep a local `.env` in the project root. You can use `.env.example` as a template. Set `GROQ_API_KEY` to a newly generated key in `.env`; do not put credentials in source files or documentation. `.env` is excluded by `.gitignore`.

Start the app from this directory:

```powershell
python -m streamlit run main.py
```

## Voice features

The browser microphone uses the Web Speech API and requests microphone permission after the microphone button is pressed. Browser support varies; HTTPS or localhost is required by many browsers. Replies use browser speech synthesis, with generated audio as a fallback.

## Medicine reminders

The reminder worker reads saved schedules and medicine logs and runs while the CareVoice server process is running. To receive notifications while the page is inactive or closed, enable notifications in Settings. Push delivery additionally requires browser permission, a Web Push provider, and a persistent VAPID key.

Local defaults use `http://localhost:8501` and the action API at `http://127.0.0.1:8765/action`. For a deployment, set these variables in the server environment:

- `CAREVOICE_REMINDER_ACTION_URL`: public HTTPS URL for the reminder action API, reachable by the browser service worker.
- `CAREVOICE_ACTION_BIND` and `CAREVOICE_ACTION_PORT`: private listener address and port behind the deployment's HTTPS reverse proxy. Keep the action API behind that proxy.
- `CAREVOICE_ALLOWED_WEB_ORIGINS`: comma-separated exact HTTPS origins allowed to call the action API.
- `CAREVOICE_APP_URL`: public HTTPS CareVoice URL opened from a notification.
- `CAREVOICE_SERVICE_WORKER_URL`: same-origin service-worker script URL. The default is `/app/static/carevoice-sw.js`; adjust it if the reverse proxy mounts Streamlit under a path prefix.
- `CAREVOICE_VAPID_PRIVATE_KEY_FILE`: optional path to a persistent VAPID private key. If omitted, CareVoice creates one under the user's local application-data directory. Preserve the same key across restarts.
- `CAREVOICE_VAPID_SUBJECT`: optional VAPID contact URI, such as a mailto address.
- `CAREVOICE_ACTION_SECRET_FILE`: optional path to the persistent secret used to sign reminder actions. If omitted, CareVoice creates one under the user's local application-data directory. Preserve it across restarts.

Serve the app and service worker over HTTPS in production. Set the action URL, app URL, and allowed origin to the real deployed HTTPS endpoints; do not use loopback URLs from remote browsers. Run one reminder worker against the persistent CareVoice database.

## Tests

Run the full suite from the project root:

```powershell
$env:PYTHONPATH = "frontend"
pytest -q
```

Focused voice and reminder tests:

```powershell
pytest -q test_voice_assistant.py test_reminder_worker.py
```

## Render deployment

CareVoice is a Streamlit application, so deploy it as a Render Docker web service rather than as a Vercel serverless function. The repository includes a Render Blueprint (`render.yaml`), Docker image definition, and an Nginx proxy that exposes Streamlit and the reminder-action endpoint on one public port.

1. Push the source to a private GitHub repository. Do not include `.env`, database files, prescription images, or anything under `uploads/`; the ignore rules exclude these local data files.
2. In Render, create a Blueprint from that repository and deploy the `carevoice` service. The Blueprint uses Singapore and attaches a persistent disk at `/var/data`.
3. Set `GROQ_API_KEY` and `CAREVOICE_VAPID_SUBJECT` as secret environment variables in Render. Set the VAPID subject to a contact URI such as `mailto:admin@example.com`.
4. Confirm that the service URL, reminder-action route, HTTPS, and notification permissions work after deployment.

The persistent disk holds the SQLite database, uploaded files, and reminder signing keys. The deployed service starts with a new database; it does not copy local health records or uploads. Keep backups of the Render disk. Render's persistent disk is tied to a single service instance, so do not scale this service to multiple instances.