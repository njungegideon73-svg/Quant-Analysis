"""Convert YouTube auto-caption .vtt files to deduplicated plain text with ~minute markers.
Usage: python3 vtt2txt.py subs/ transcripts/
"""
import re, sys, pathlib

def convert(vtt: str) -> str:
    out, last, next_mark = [], "", 0
    for block in vtt.split("\n\n"):
        m = re.search(r"(\d+):(\d+):(\d+)\.\d+ -->", block)
        if not m:
            continue
        t = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
        for line in block.split("\n")[1:]:
            line = re.sub(r"<[^>]+>", "", line).strip()
            if not line or line == last:  # auto-subs repeat the previous cue's line
                continue
            if t >= next_mark:
                out.append(f"\n[{t // 60:02d}:{t % 60:02d}]")
                next_mark = t + 60
            out.append(line)
            last = line
    return " ".join(out).strip()

if __name__ == "__main__":
    src, dst = map(pathlib.Path, sys.argv[1:3])
    dst.mkdir(exist_ok=True)
    for f in sorted(src.glob("*.vtt")):
        (dst / f"{f.name.split('.')[0]}.txt").write_text(convert(f.read_text(errors="ignore")))
