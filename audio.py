"""Synth a 40s ambient/corporate-tech soundtrack via ffmpeg's lavfi.

Layers:
- Sub bass drone (sine, 55Hz with subtle vibrato)
- Mid pad (two detuned saws at 220/277 Hz, low-passed)
- High shimmer (sine 880Hz with tremolo)
- Soft kick at 1Hz (every beat) via aevalsrc envelope
- Sweep risers at scene boundaries (whoosh)
- Final chord swell

Duration matches 5 scenes x 8s = 40s.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

OUT = Path("audio.wav")
DUR = 40.0


def build_filter() -> str:
    # Sources
    parts = []
    # Sub bass drone (slow swell)
    parts.append(
        f"sine=frequency=55:duration={DUR}[sub_a];"
        f"[sub_a]volume='0.18+0.05*sin(2*PI*0.07*t)':eval=frame[sub];"
    )
    # Mid pad: detuned saws — but lavfi 'sine' only; emulate pad with multiple sines
    parts.append(
        f"sine=frequency=220:duration={DUR}[m1a];"
        f"sine=frequency=277:duration={DUR}[m2a];"
        f"sine=frequency=329:duration={DUR}[m3a];"
        f"[m1a]volume=0.10[m1];"
        f"[m2a]volume=0.08[m2];"
        f"[m3a]volume=0.07[m3];"
        f"[m1][m2]amix=inputs=2:normalize=0[m12];"
        f"[m12][m3]amix=inputs=2:normalize=0[mid_raw];"
        f"[mid_raw]lowpass=f=1200,volume='0.55+0.25*sin(2*PI*0.05*t)':eval=frame[mid];"
    )
    # Shimmer
    parts.append(
        f"sine=frequency=880:duration={DUR}[sh_a];"
        f"sine=frequency=1320:duration={DUR}[sh_b];"
        f"[sh_a]volume=0.04[sha];"
        f"[sh_b]volume=0.03[shb];"
        f"[sha][shb]amix=inputs=2:normalize=0[shr];"
        f"[shr]volume='0.4+0.4*sin(2*PI*0.3*t)':eval=frame[shim];"
    )
    # Click pulse — 'kick' every 2s (slow, ambient pulse) using aevalsrc
    # Envelope: fast attack, exp decay each beat
    parts.append(
        f"aevalsrc='0.6*sin(2*PI*60*t)*exp(-8*mod(t\\,2))':d={DUR}[kick];"
    )
    # Whoosh sweep — broadband noise filtered, modulated, only triggered at scene starts
    # Using anoisesrc + bandpass with time-varying frequency.
    parts.append(
        f"anoisesrc=color=white:duration={DUR}:amplitude=0.6[nz];"
        f"[nz]bandpass=f=1500:width_type=h:w=1500,"
        f"volume='if(lt(mod(t\\,8)\\,0.6)*gt(t\\,1)\\,0.35*(1-mod(t\\,8)/0.6)\\,0)':eval=frame[whoosh];"
    )

    # Mix everything
    parts.append(
        f"[sub][mid]amix=inputs=2:normalize=0[bus1];"
        f"[bus1][shim]amix=inputs=2:normalize=0[bus2];"
        f"[bus2][kick]amix=inputs=2:normalize=0[bus3];"
        f"[bus3][whoosh]amix=inputs=2:normalize=0[mixed];"
        f"[mixed]highpass=f=40,lowpass=f=14000,"
        f"acompressor=threshold=0.4:ratio=4:attack=20:release=250,"
        # Master fade-in/out
        f"afade=t=in:st=0:d=1.5,afade=t=out:st={DUR-2.0}:d=2.0,"
        f"volume=2.0[out]"
    )
    return "".join(parts)


def main():
    fc = build_filter()
    cmd = [
        "ffmpeg", "-y",
        "-filter_complex", fc,
        "-map", "[out]",
        "-ar", "44100", "-ac", "2",
        str(OUT),
    ]
    print(" ".join(cmd[:6]) + " ...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("STDERR:", r.stderr[-2000:])
        raise SystemExit(1)
    print("Wrote", OUT, OUT.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
