#!/usr/bin/env bash
# Encode the rendered PNG sequence to video.
#
#   ./encode.sh                 H.264 master, CRF 14 (4K, 24 fps, yuv420p)  -> renders/intersection_h264.mp4
#   ./encode.sh prores          ProRes 422 HQ (10-bit 4:2:2, for grading)    -> renders/intersection_prores.mov
#   ./encode.sh h265            H.265/HEVC 10-bit, CRF 16                     -> renders/intersection_h265.mp4
#   ./encode.sh preview         1080p H.264 from renders/preview              -> renders/preview.mp4
#
# Options via environment: FRAMES=dir  OUT=file  CRF=n  FPS=24
# Windows: run from Git Bash or WSL, or copy the ffmpeg line into PowerShell.
set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-h264}"
FPS="${FPS:-24}"
FRAMES="${FRAMES:-renders/frames}"
[ "$MODE" = "preview" ] && FRAMES="${FRAMES_PREVIEW:-renders/preview}"

if ! ls "$FRAMES"/frame_*.png >/dev/null 2>&1; then
  echo "No frames found in $FRAMES (expected frame_0001.png ...)" >&2; exit 1
fi
FIRST=$(ls "$FRAMES"/frame_*.png | head -1 | sed -E 's/.*frame_0*([0-9]+)\.png/\1/')
COUNT=$(ls "$FRAMES"/frame_*.png | wc -l)
echo "Encoding $COUNT frames from $FRAMES (start $FIRST) as $MODE"

IN=(-framerate "$FPS" -start_number "$FIRST" -i "$FRAMES/frame_%04d.png")
# Rec.709 tagging so players show the same tones as the sRGB PNGs
TAGS=(-color_primaries bt709 -color_trc bt709 -colorspace bt709)

case "$MODE" in
  h264)
    OUT="${OUT:-renders/intersection_h264.mp4}"
    ffmpeg -y "${IN[@]}" -c:v libx264 -preset slow -crf "${CRF:-14}" -tune film \
      -pix_fmt yuv420p "${TAGS[@]}" -movflags +faststart -r "$FPS" "$OUT" ;;
  h265)
    OUT="${OUT:-renders/intersection_h265.mp4}"
    ffmpeg -y "${IN[@]}" -c:v libx265 -preset slow -crf "${CRF:-16}" \
      -x265-params "aq-mode=3:no-sao=1" -pix_fmt yuv420p10le -tag:v hvc1 "${TAGS[@]}" \
      -movflags +faststart -r "$FPS" "$OUT" ;;
  prores)
    OUT="${OUT:-renders/intersection_prores.mov}"
    ffmpeg -y "${IN[@]}" -c:v prores_ks -profile:v 3 -vendor apl0 -pix_fmt yuv422p10le \
      "${TAGS[@]}" -r "$FPS" "$OUT" ;;
  preview)
    OUT="${OUT:-renders/preview.mp4}"
    ffmpeg -y "${IN[@]}" -vf "scale=1920:-2:flags=lanczos" -c:v libx264 -preset slow \
      -crf "${CRF:-16}" -pix_fmt yuv420p "${TAGS[@]}" -movflags +faststart -r "$FPS" "$OUT" ;;
  *) echo "unknown mode $MODE (h264|h265|prores|preview)" >&2; exit 2 ;;
esac
echo "Wrote $OUT"
