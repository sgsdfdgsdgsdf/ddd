"""Parallel frame renderer — uses multiprocessing.Pool over render.SCENES."""
from __future__ import annotations

import os
import shutil
import time
from multiprocessing import Pool
from pathlib import Path

import render
from render import FPS, OUT_DIR, SCENES


def _render_one(args):
    frame_idx, scene_name, t, dur = args
    fn = dict((n, f) for n, f, _ in SCENES)[scene_name]
    im = fn(t, dur)
    im.convert("RGB").save(OUT_DIR / f"f{frame_idx:05d}.jpg",
                           quality=92, optimize=False)
    return frame_idx


def main():
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    jobs = []
    frame_idx = 0
    for name, fn, dur in SCENES:
        nf = int(dur * FPS)
        for i in range(nf):
            t = i / FPS
            jobs.append((frame_idx, name, t, dur))
            frame_idx += 1
    total = len(jobs)
    print(f"Dispatching {total} frames across {os.cpu_count()} workers")

    start = time.time()
    done = 0
    with Pool(processes=4) as pool:
        for fi in pool.imap_unordered(_render_one, jobs, chunksize=4):
            done += 1
            if done % 60 == 0 or done == total:
                el = time.time() - start
                eta = el / done * (total - done)
                print(f"  {done}/{total}  ({done/total*100:.0f}%)  "
                      f"elapsed={el:.0f}s eta={eta:.0f}s")
    print(f"Done in {time.time() - start:.0f}s")


if __name__ == "__main__":
    main()
