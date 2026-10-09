# Login scene media: provenance and processing

Assets in `frontend/public/media/login/` (ADR 0008). Nobody shown in the footage endorses
Infra Control or Smart Choice; the clips are stock footage used under their licence.

## Source

| | |
|---|---|
| Page | https://www.pexels.com/video/classical-orchestra-performance-on-stage-37600731/ |
| Title | Classical Orchestra Performance on Stage |
| Creator | Sandin Redzo, https://www.pexels.com/@sandin-redzo-1780184288/ |
| Licence | Pexels License, https://www.pexels.com/license/ (free to use and modify, no attribution required; no implied endorsement) |
| Retrieved | 2026-10-09, through the official download link `https://www.pexels.com/download/video/37600731/?w=1920&h=1080` |
| Master | `15937391_1920_1080_24fps.mp4`, H.264, 1920×1080, 24 fps, 30.29 s (kept outside the repository) |

Also inspected and not used: Pexels 37767499 (same session; the push-in segment introduces a
soloist, so continuity with the loop would break), Pexels 7568877 / 7567503 / 7567505
(cottonbro studio; front-facing close-ups in a church, no space for the form), Pixabay 339748
and 339749 (labelled AI generated), Pexels 39912799/39912800 (portrait or outdoor).

## Why this shot

A single, static shot: the conductor in black, from behind, left of centre, the orchestra and
an ornate hall ahead, warm practical light. The right third holds musicians, so the form sits
over a quiet gradient instead of empty space. No cuts, no camera motion, so idle and success
come from the same continuous take.

## Selected timestamps

| Clip | Source range | Notes |
|---|---|---|
| `conductor-idle` | 8.500 s – 15.500 s (7.0 s) | Chosen by frame-difference search for the least visible seam; the last 15 frames (15.500 – 16.125 s) are dissolved into the first 15 frames so the loop closes without a cut. |
| `conductor-success` | 20.000 s – 22.500 s (2.5 s) | Preparatory raise, downbeat, calm settle. Same take as the loop; the cut from an arbitrary loop position is softened by the 300 ms crossfade in the page. No forward camera move exists in this footage, so none is faked. |
| posters | first frame of the idle loop | WebP q80 |
| `*-mobile` | portrait crop `608×1080` at x=120 of the 1080p frame, scaled to 540×960 | Keeps the conductor and the hall; the form sits below. |

Inspection was done on extracted frames (contact sheets at 1 fps and 4 fps, seam and
continuity pairs). Full-motion review happened only in the browser after encoding.

## Commands (FFmpeg 7.0.2 static build)

```sh
X="-c:v libx264 -preset slow -crf 23 -pix_fmt yuv420p -profile:v high -level 4.1 -g 48 -keyint_min 48 -movflags +faststart -an"
# idle loop with a 15-frame overlap dissolve
ffmpeg -ss 15.5 -t 0.625 -i master.mp4 -ss 8.5 -t 0.625 -i master.mp4 -ss 9.125 -t 6.375 -i master.mp4 \
  -filter_complex "[0:v]setpts=PTS-STARTPTS[a];[1:v]setpts=PTS-STARTPTS[b];[a][b]blend=all_expr='A*(1-T/0.625)+B*(T/0.625)'[x];[2:v]setpts=PTS-STARTPTS[c];[x][c]concat=n=2:v=1:a=0[v]" \
  -map "[v]" -r 24 $X conductor-idle.mp4
ffmpeg -ss 20.0 -t 2.5 -i master.mp4 -r 24 $X conductor-success.mp4
ffmpeg -i conductor-idle.mp4    -vf "crop=608:1080:120:0,scale=540:960" -r 24 $X -crf 25 conductor-idle-mobile.mp4
ffmpeg -i conductor-success.mp4 -vf "crop=608:1080:120:0,scale=540:960" -r 24 $X -crf 25 conductor-success-mobile.mp4
ffmpeg -i conductor-idle.mp4        -frames:v 1 -c:v libwebp -quality 80 conductor-poster.webp
ffmpeg -i conductor-idle-mobile.mp4 -frames:v 1 -c:v libwebp -quality 80 conductor-poster-mobile.webp
for n in conductor-idle conductor-success conductor-idle-mobile conductor-success-mobile; do
  ffmpeg -i $n.mp4 -c:v libvpx-vp9 -crf 33 -b:v 0 -row-mt 1 -deadline good -cpu-used 2 -pix_fmt yuv420p -an $n.webm
done
```

## Outputs

| File | Size | Dimensions | Duration |
|---|---|---|---|
| conductor-idle.mp4 | 2.7 MB | 1920×1080 | 7.0 s |
| conductor-idle.webm | ≈1.9 MB | 1920×1080 | 7.0 s |
| conductor-success.mp4 | 1.0 MB | 1920×1080 | 2.5 s |
| conductor-success.webm | 0.7 MB | 1920×1080 | 2.5 s |
| conductor-idle-mobile.mp4 / .webm | 0.4 / 0.3 MB | 540×960 | 7.0 s |
| conductor-success-mobile.mp4 / .webm | 0.15 / 0.13 MB | 540×960 | 2.5 s |
| conductor-poster.webp / -mobile.webp | 115 / 21 KB | 1920×1080 / 540×960 | |
| smart-choice-logo.png | 27 KB | | interface asset, kept separate from the footage |

All outputs were decoded end to end with `ffmpeg -f null` after encoding. Audio was dropped.
