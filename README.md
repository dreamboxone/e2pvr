# E2PVR

PVR subtitle translation for Enigma2, version 0.2.4.

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

Open E2PVR from the plugin menu. Red starts or stops translation immediately, as in E2Dub. Starting saves
preferences and returns to playback; stopping keeps the menu open;
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

At translation startup the recording plays a preview of four seconds by default.
The worker translates while that preview plays. The player then seeks back once
to the preview's initial position and continues with the prepared subtitles.
The menu's Startup delay setting selects 0-4 seconds. This preview is performed
only at initial startup, not after each seek. The plugin's own rewind preserves
the translation session and prepared cues. Playback must support seeking.
Network/service latency can still exceed this preparation window.

Translation runs in a separate worker through a persistent connection. Its audio
cursor remains at most four seconds ahead of the position currently being read.
During the initial preview this prepares audio beyond the preview's return point.

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

## Native builds

Universal DEB/IPK packages support Python 2.7 and Python 3. Native modules must
be compiled separately for the receiver architecture, Python ABI, Unicode
width and compatible C library. The Dreambox One build targets ARM64 and
Python 2.7 with the receiver's own configuration headers. It is not a Python 3
or universal OE-Alliance binary.

`tools/build_native.py` accepts an explicit Cython executable, cross compiler,
strip tool, receiver-matched include directory and a new output directory.
Generated C files remain outside the source tree. Only `__init__.py`, the platform profile, a small plugin discovery entry and
the worker entry script remain as Python in a native payload; application
modules are stripped shared libraries. Native builds make
source inspection less convenient, but do not prevent copying or reverse
engineering. Publicly distributed source remains available regardless of the
installed package format.

Package the staged `E2PVR` directory with `tools/build_packages.py --native-root
<staged-directory> --architecture arm64 --python-abi 2.7 --format deb`.
Keep the universal packages for other receivers until their native builds have
been tested on matching hardware.

Translation starts only after pressing red during local playback. A saved enabled
flag does not resume translation after an interface restart. The red label follows
the active recording worker; failed or stopped workers show Start, which retries
from the current playback position. UTF-8 recording names are passed explicitly
to the decoder on Python 2.7.

Local media is not filtered by filename extension. Names in any UTF-8 script,
spaces and punctuation are passed without shell parsing. Actual playback and
audio decoding still depend on the receiver player and FFmpeg codecs.

## Exit and restart

No translation worker, decoder or network connection is started on image or
interface startup. Start must be pressed explicitly. Graceful interface shutdown
kills the worker process group without waiting for network requests. On Linux,
parent-death signals also kill a worker if the interface crashes and a decoder if
its worker disappears. No startup download, worker recovery or blocking network
operation is required for boot.

## Subtitle shaping

As in E2Dub, when `/usr/bin/pango-view` is available, subtitle glyphs are shaped
by Pango and displayed as a transparent bitmap. The selected font's actual family
is read from its font metadata. This preserves Arabic mark placement, Persian
joining and digit coverage. Rendering runs asynchronously; changed or hidden
captions cancel obsolete work. A missing renderer or failed bitmap falls back to
the native two-label overlay. Renderer children also receive parent-death signals
and are terminated without blocking the interface on close.

If Start is pressed from the plugin browser while no local recording is playing,
the recording selector opens. Choosing a recording starts the native MoviePlayer
with translation enabled. Cancelling the selector returns to settings. E2PVR is
also available in the Extensions menu for access during playback.
