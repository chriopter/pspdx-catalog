#!/bin/sh
# The preview clip the console plays: half the screen, no sound, small
# enough that a PSP-1004 on 802.11b has it in about a second.
#
#   sh encode-video.sh <source> apps/<id>/video.mp4
#
# 256x144: sixteenths, which is what the PSP decoder's header can express,
# and 16:9 within a pixel of the 480x272 card it is scaled onto. H.264
# Constrained Baseline is what the hardware decodes; 30 frames a second is
# what the console paces at; ten seconds is the loop. The quality is lowered
# a step at a time until the file is under 200 KB, so a busy clip gets less
# detail and a calm one keeps more.
set -e
src="$1"
out="$2"
[ -n "$src" ] && [ -n "$out" ] || { echo "usage: sh encode-video.sh <source> <video.mp4>" >&2; exit 2; }
limit=204800
crf=26
while :; do
	ffmpeg -v error -y -i "$src" -t 10 -an \
		-vf "scale=256:144:flags=lanczos,fps=30,format=yuv420p" \
		-c:v libx264 -profile:v baseline -level 2.1 -preset veryslow -tune film \
		-crf "$crf" -maxrate 400k -bufsize 400k -g 30 -keyint_min 30 -sc_threshold 0 \
		-movflags +faststart "$out"
	size=$(stat -c %s "$out")
	echo "crf $crf: $size bytes"
	[ "$size" -le "$limit" ] && break
	crf=$((crf + 2))
	[ "$crf" -gt 40 ] && { echo "cannot get under 200 KB" >&2; exit 1; }
done
