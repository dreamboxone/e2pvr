# E2PVR

PVR subtitle translation for Enigma2, version 0.2.2.

The receiver streams the selected audio track of a local recording to Gemini
Live and displays translated subtitles. Source language is detected automatically.
Persian, Arabic and Russian are available as subtitle targets. Kurdish Kurmanji is unavailable in the current service: `ku` returned Sorani
in receiver testing, while `ku-Latn` and `kmr` sessions were closed by the service. The plugin does not play
translated audio and needs no local model.

## Installation

Install the DEB on DreamOS or the IPK on an OE-Alliance image. The installer
restarts the Enigma2 interface and creates a key file with mode `0600` only when
it does not exist. The same locations as E2Dub are used:

- DreamOS DEB: `/root/apikey.txt`.
- OE-Alliance IPK: `/home/root/apikey.txt`.

Put the API key alone in this file. Existing keys are
preserved on upgrades and package removal. Keys are never placed in package
contents, command arguments, request URLs or diagnostic logs.

After installation, package archives matching
`/tmp/enigma2-plugin-extensions-e2pvr_*.deb` or `.ipk` are removed automatically.
Use the generated package filename when uploading to `/tmp`. Other filenames
and files outside `/tmp` are not removed.

Open E2PVR from the plugin menu. Red starts or stops translation immediately;
green saves display preferences and closes the menu; Exit cancels unsaved display
changes. Yellow tests the actual subtitle connection with a 60-second display
deadline. Play a local recording with the image's player. Reopen E2PVR and press red
to stop. The status distinguishes a stopped session, waiting for a recording,
connecting, active translation, and connection errors.
Internet access and a working API key with quota are required. The default
service model is `gemini-3.5-live-translate-preview`.

## Display and playback

The menu supports English (default), Persian and Arabic. Subtitle color, installed
font, three font sizes, vertical position as a percentage of picture height, and
box transparency are configurable. Fonts are discovered in `/usr/share/fonts`.
Vazirmatn SemiBold is also supplied under the included SIL Open Font License.
Each subtitle line has a separate non-wrapping label to preserve RTL line order.

When translation is enabled and a recording starts, supported seekable playback
is held at its initial position for up to four seconds. Translation runs
in a separate worker through one persistent Live connection. The audio cursor
stays at most four seconds ahead of the current playback position. Playback
resumes when a complete subtitle becomes available or the preparation budget
expires. Network or service latency can still cause late or missing subtitles;
four seconds is a preparation limit, not a service response guarantee.

Only committed phrases are displayed. Two-second text stability, sentence and
turn boundaries, a six-cue ordered pending window, two-to-six-second reading
time and a four-second arrival lateness limit follow E2Dub's subtitle policies.
Manual timing correction ranges from -4 to +3.5 seconds in 250 ms steps.
Negative correction cannot display text before it arrives. Live transcription
does not supply exact file timestamps. As in E2Dub, committed text availability
controls display, with manual correction and reading-time protection. Estimated
source intervals are diagnostic metadata rather than an authoritative clock;
manual adjustment can be needed. Keep recordings' `.ap` and `.sc` timing indexes
alongside TS files for accurate native seeking.

Subtitles follow the actual playback position. Seeking starts a new processing
generation and rejects responses from the old location. Pausing retains the
current subtitle. Existing `movie.fa.srt` or `movie.ar.srt` files alongside
`movie.ts` take precedence over online processing for that recording.

## Diagnostics and compatibility

Runtime code supports Python 2.7 and Python 3. FFmpeg and TLS-enabled Python
with trusted CA certificates are required. AArch64, ARM and MIPS plugin packages
share the same Python code; this does not certify every image or hardware model.
Dreambox One with DreamOS 2.6 and Python 2.7 is the hardware test target.

Diagnostic logs rotate in `/tmp/e2pvr.log`. They contain status and timings,
not API keys or transcript contents. Temporary session control files are kept
under a private `/tmp/e2pvr-*` directory and removed when the worker stops.
Audio travels through pipes and is not written to disk. The client requests
TEXT output; any inline audio still returned by the service is discarded.
Original recordings are read without modification. The transport reused from
E2Dub retains its original copyright and license in `LICENSE-E2Dub.txt`.

## Development

Build tools require Python 3:

```
python -m unittest discover -s tests
python tools/build_packages.py
```

Both package formats are deterministic archives with SHA-256 sidecars in `dist`.
Do not infer successful live translation from parser tests or SRT display tests:
authenticated service and audio-language tests are separate validation steps.
