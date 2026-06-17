# All Saints Workflow Automation Notes

## YouTube Live Cleanup

Source: `AllSaintsYouTube.txt`.

1. Find the latest Sunday service videos in YouTube Studio under Content > Live.
2. Confirm the correct service title/date in Planning Center.
3. Download the matching YouTube title slide from Planning Center Plan Files.
4. Update the YouTube livestream title if Streamlabs used the wrong one.
5. Upload the title slide as the YouTube thumbnail.
6. Save and verify on the public channel Live tab.

## Sermon Website Posting

Source: `AllSaintsSermons-1.txt` through `AllSaintsSermons-4.txt`.

The public sermon page at `https://www.allsaintswoodbridge.org/latest-sermons` and the instruction videos show the fields the automation packet prepares:

- sermon title
- preacher
- date
- scripture reference
- scripture text
- MP3 audio with title and artist metadata
- Squarespace markdown scripture block, when scripture is supplied

The manual Squarespace publishing flow is:

1. Go to the website config page.
2. Website > Pages > Listen > Sermons.
3. Remove older sermons when the prior year's month should roll off.
4. Add a sermon post.
5. Enter sermon title.
6. Add date text.
7. Add an audio block and upload the processed MP3.
8. Enable the audio block download link.
9. Add scripture in a markdown block if provided.
10. Set author to the preacher or guest speaker.
11. Save and publish.
12. Edit published date/time to the actual service date.
13. Test playback.

The current scripts automate steps 1-3 of the full backend process: form packet creation, YouTube/local audio processing, MP3 metadata, and copy-ready website fields. Squarespace publishing still needs either browser automation after login or confirmed CMS/API access.

## Added Automation

Discovery:

- `automation/discover_work.py` reads the public YouTube channel feed and public sermon page.
- It infers service dates from YouTube publish dates when services are uploaded the next day.
- It writes `work/sermon-discovery.md` with `needs_sermon_post`, `already_posted`, and `review` statuses.
- `automation/create_job_from_discovery.py` turns a discovery item into a job JSON with the YouTube URL already filled in.

Boundary detection:

- `automation/transcribe_service.py --job ... --detect-bounds` downloads/transcribes the service and updates the job with proposed sermon start/end times.
- `automation/detect_sermon_bounds.py` uses Episcopal/Anglican service cues such as Gospel response, "may be seated", "let us stand", and Creed language.
- The detector reports confidence. Low-confidence results should be reviewed before the MP3 is published.

## Recommended Automation Architecture

Use APIs where possible, then fall back to a monitored browser session for the CMS if no API is available.

- Gmail: read sermon form emails using Gmail API or IMAP with an app password.
- Planning Center: use a Planning Center personal access token to read service plans and download title-slide files.
- YouTube: use YouTube Data API OAuth to list livestreams, update titles, and upload thumbnails.
- Website CMS: use the CMS API if available; otherwise automate a logged-in browser session after the exact admin workflow is confirmed.

## Security Notes

The account passwords shared in the original email should be rotated. Automation should use app passwords, OAuth tokens, or API tokens with the narrowest available permissions.
