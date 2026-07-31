# Test fixtures

## `tiny-1frame.mp4` (1,548 bytes)

A one-frame, 64x64 black MP4 - the smallest valid QuickTime container that exiftool will read
and write. Committed rather than generated, so the video tests run **everywhere** instead of
skipping wherever `ffmpeg` is absent, which was every CI runner on all three platforms.

Provenance - regenerate with exactly this, from any machine with ffmpeg:

```
ffmpeg -loglevel error -y -f lavfi -i color=c=black:s=64x64:d=1 -frames:v 1 tiny-1frame.mp4
```

It carries no metadata of interest on purpose: every test that needs tags writes its own with
exiftool, which **is** installed in CI (`.github/workflows/ci.yml`), so the fixture is a
container and nothing more. Do not hand-edit it; regenerate it.
