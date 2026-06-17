# All Saints Workflow Automation

This folder now contains a small automation scaffold for the All Saints sermon and YouTube workflows.

## What is automated now

- Environment checks for `whisper`, `ffmpeg`, disk space, and expected instruction videos.
- Discovery of recent public YouTube service videos and comparison against the public sermon page.
- Creation of a job JSON from the next likely unposted service.
- Whisper-based sermon start/end detection from service transcripts.
- A weekly sermon packet generator that turns sermon metadata into copy-ready website and YouTube cleanup notes.
- A transcript runner script that can transcribe the remaining instruction videos once `ffmpeg` is available.
- A secure configuration template that avoids hardcoding passwords in scripts.

## Quick start

Check the environment:

```powershell
python .\automation\check_environment.py
```

If `ffmpeg` is missing:

```powershell
python .\automation\setup_ffmpeg.py
```

Generate a sermon packet from the template:

```powershell
python .\automation\weekly_packet.py --input .\automation\sermon_template.json
```

The generated packet is written under `work\`.

Or parse a pasted/exported sermon form email:

```powershell
python .\automation\form_to_packet.py --input .\work\sermon-form.txt
```

Or fetch the latest sermon form email automatically after configuring `.env`:

```powershell
python .\automation\fetch_sermon_form.py
```

Process sermon audio from a downloaded video/audio file or YouTube URL:

```powershell
python .\automation\process_sermon_audio.py --job .\automation\sermon_job.example.json
```

You can also override those fields at the command line:

```powershell
python .\automation\process_sermon_audio.py --job .\work\sermon.json --youtube-url "https://youtube.com/watch?v=..." --start-time 00:34:10 --end-time 00:56:45
```

## Weekly Operator Flow

1. Run `python .\automation\discover_work.py` to create `work\sermon-discovery.md`.
2. Run `python .\automation\create_job_from_discovery.py --index 0` to create a job for the first likely unposted service.
3. Run `python .\automation\fetch_sermon_form.py`, or paste the sermon form email body into `work\sermon-form.txt` and run `python .\automation\form_to_packet.py --input .\work\sermon-form.txt`.
4. Copy sermon title, preacher, and scripture fields from the form JSON into the discovered job JSON if they are not already there.
5. Run `python .\automation\transcribe_service.py --job .\work\your-job.json --detect-bounds`.
6. Run `python .\automation\process_sermon_audio.py --job .\work\your-job.json`.
7. Upload the generated MP3 in Squarespace and copy the generated website body from the packet.
8. Use the packet checklist for the YouTube title/thumbnail cleanup.

The detector writes proposed `start_time` and `end_time` plus confidence into the job and final packet. Review low-confidence detections before publishing.

## Current blocker

`whisper` needs an executable named `ffmpeg`. If `python .\automation\check_environment.py` reports it missing, run:

```powershell
python .\automation\setup_ffmpeg.py
```

Then run:

```powershell
powershell -ExecutionPolicy Bypass -File .\automation\transcribe_instructions.ps1
```

That will create transcripts for the four sermon instruction videos.

## Credentials

Do not put real passwords in tracked scripts. Use `.env` or a password manager, and prefer API tokens/app passwords over account passwords.

Because raw passwords were shared in chat/email, rotate them before relying on this automation in production.
