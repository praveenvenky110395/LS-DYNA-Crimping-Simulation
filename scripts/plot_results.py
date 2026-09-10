#!/usr/bin/env python3
"""
Generate the three result figures for the wire-crimp forming model.

Reads the LS-DYNA ASCII output in results/ plus the punch-stroke curve from the
deck, and writes:

    results/figures/01_crimping_force_vs_stroke.png
    results/figures/02_global_energy_balance.png
    results/figures/03_solution_quality_ratios.png

    python3 scripts/plot_results.py

Every annotated value is computed from the data, not hard-coded.
No dependencies beyond matplotlib.
"""

import bisect
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
FIGURES = RESULTS / "figures"
DECK = ROOT / "model" / "crimp_forming.k"

# --- theme -----------------------------------------------------------------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
INK3 = "#8a8983"
GRID = "#e4e3df"
# categorical slots, assigned in fixed order and never cycled
S = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]


# --- readers ---------------------------------------------------------------
def read_glstat(path):
    text = path.read_text(errors="ignore")
    rows = []
    for block in re.split(r"\n\s*dt of cycle", text):
        def field(key):
            m = re.search(re.escape(key) + r"\.*\s*([-\d.E+]+)", block)
            return float(m.group(1)) if m else None

        t, ie = field("time..."), field("internal energy")
        if t is None or ie is None:
            continue
        rows.append(dict(
            t=t, ke=field("kinetic energy"), ie=ie,
            hg=field("hourglass energy "), sl=field("sliding interface energy"),
            tot=field("total energy..."), ex=field("external work"),
        ))
    return rows


def read_rcforc(path):
    pat = re.compile(
        r"\s*(SURFA|SURFB)\s+(\d+)\s+time\s+([-\dE.+]+)"
        r"\s+x\s+([-\dE.+]+)\s+y\s+([-\dE.+]+)"
    )
    out = {}
    for line in path.read_text(errors="ignore").splitlines():
        m = pat.match(line)
        if m:
            out.setdefault((int(m.group(2)), m.group(1)), []).append(
                (float(m.group(3)), float(m.group(5)))
            )
    return out


def read_stroke_curve(path, lcid=4):
    lines = path.read_text(errors="ignore").splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("*DEFINE_CURVE"):
            continue
        pts, j, seen = [], i + 1, False
        card = None
        while j < len(lines) and not lines[j].startswith("*"):
            s = lines[j]
            j += 1
            if s.startswith("$") or not s.strip():
                continue
            if card is None:
                if s[:10].strip().isdigit():
                    card = s
                    if int(s[:10]) != lcid:
                        break
                continue
            if not seen:                      # skip the "a1  o1" header row
                seen = True
            try:
                pts.append((float(s[:20]), float(s[20:40])))
            except ValueError:
                continue
        if card is not None and int(card[:10]) == lcid and pts:
            return [p[0] for p in pts], [p[1] for p in pts]
    raise SystemExit(f"load curve {lcid} not found in {path}")


# --- chart helpers ---------------------------------------------------------
def new_axes(figsize=(7.8, 4.5)):
    fig, ax = plt.subplots(figsize=figsize, dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=INK2, labelsize=8.5, length=3, width=0.8)
    return fig, ax


def titles(ax, title, subtitle):
    ax.text(0, 1.135, title, transform=ax.transAxes, color=INK,
            fontsize=12, fontweight="600", va="bottom")
    ax.text(0, 1.035, subtitle, transform=ax.transAxes, color=INK2,
            fontsize=8.8, va="bottom")


def label_end(ax, x, y, text, color, dy=0.0):
    """Direct label at the right end of a series - identity is never colour alone."""
    ax.annotate(text, xy=(x, y), xytext=(6, dy), textcoords="offset points",
                color=color, fontsize=8.6, fontweight="600", va="center", zorder=5)


def save(fig, name):
    FIGURES.mkdir(parents=True, exist_ok=True)
    out = FIGURES / f"{name}.png"
    fig.savefig(out, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print("wrote", out.relative_to(ROOT))


# --- figures ---------------------------------------------------------------
def fig_force(rc, stroke):
    fig, ax = new_axes()
    xs, ys = stroke

    def disp(tq):
        i = bisect.bisect_left(xs, tq)
        if i == 0:
            return 0.0
        if i >= len(xs):
            return abs(ys[-1])
        f = (tq - xs[i - 1]) / (xs[i] - xs[i - 1])
        return abs(ys[i - 1] + f * (ys[i] - ys[i - 1]))

    punch, anvil = rc[(2, "SURFA")], rc[(1, "SURFA")]
    dp = [disp(t) for t, _ in punch]
    fp = [abs(v) / 1000 for _, v in punch]          # kN
    da = [disp(t) for t, _ in anvil]
    fa = [abs(v) / 1000 for _, v in anvil]

    # The two reactions lie on top of each other - that agreement IS the result,
    # so the second series is a dashed overlay rather than a hidden line.
    ax.plot(dp, fp, color=S[0], linewidth=2.4, solid_capstyle="round", zorder=3)
    ax.plot(da, fa, color=S[1], linewidth=1.6, linestyle=(0, (5, 3)), zorder=4)
    label_end(ax, dp[-1], fp[-1], "Punch", S[0], dy=13)
    label_end(ax, da[-1], fa[-1], "Anvil  (dashed)", S[1], dy=-13)

    peak = max(fp)
    peak_d = dp[fp.index(peak)]
    peak_anvil = fa[fp.index(peak)]
    imb = abs(peak_anvil - peak) / peak * 100
    ax.scatter([peak_d], [peak], s=30, color=S[0],
               edgecolor=SURFACE, linewidth=2, zorder=5)
    ax.annotate(f"Peak = {peak:.2f} kN\nat {peak_d:.2f} mm stroke",
                xy=(peak_d, peak), xytext=(-11, 2), textcoords="offset points",
                color=INK, fontsize=8.8, fontweight="600", ha="right",
                linespacing=1.45)

    ax.set_xlim(0, 7.9)
    ax.set_ylim(0, peak * 1.16)
    ax.set_xlabel("Punch stroke  [mm]", color=INK2, fontsize=9.5)
    ax.set_ylabel("Reaction force  [kN]", color=INK2, fontsize=9.5)
    titles(ax, "Crimping Force vs. Punch Stroke",
           f"Punch and anvil reactions agree within {imb:.1f} % at peak load")
    save(fig, "01_crimping_force_vs_stroke")


def fig_energy(rows):
    fig, ax = new_axes()
    t = [r["t"] for r in rows]
    series = [
        ("Total", [r["tot"] for r in rows], S[0]),
        ("Internal", [r["ie"] for r in rows], S[1]),
        ("Sliding", [r["sl"] for r in rows], S[2]),
        ("Hourglass", [r["hg"] for r in rows], S[3]),
        ("Kinetic", [r["ke"] for r in rows], S[4]),
    ]
    for name, y, col in series:
        ax.plot(t, y, color=col, linewidth=2.0, solid_capstyle="round", zorder=3)
        label_end(ax, t[-1], y[-1], f"{name}  {y[-1]:,.0f}", col)

    closure = min(r["tot"] / r["ex"] for r in rows if r["ex"]) * 100
    ax.set_xlim(0, t[-1] * 1.22)
    ax.set_xlabel("Time  [s]", color=INK2, fontsize=9.5)
    ax.set_ylabel("Energy  [mJ]", color=INK2, fontsize=9.5)
    titles(ax, "Global Energy Balance",
           f"Energy balance closes at {closure:.2f} % throughout the simulation")
    save(fig, "02_global_energy_balance")


def fig_quality(rows):
    fig, ax = new_axes()
    live = [r for r in rows if r["ie"] and r["ie"] > 1.0]
    t = [r["t"] for r in live]
    hg = [100 * r["hg"] / r["ie"] for r in live]
    ke = [100 * r["ke"] / r["ie"] for r in live]

    ax.axhline(10, color=INK2, linewidth=1.0, linestyle=(0, (4, 3)), zorder=1)
    ax.annotate("10 % guideline", xy=(t[0], 10), xytext=(2, 5),
                textcoords="offset points", color=INK2, fontsize=8.2)

    ax.plot(t, hg, color=S[3], linewidth=2.0, solid_capstyle="round", zorder=3)
    ax.plot(t, ke, color=S[4], linewidth=2.0, solid_capstyle="round", zorder=3)
    label_end(ax, t[-1], hg[-1], f"Hourglass / internal   end {hg[-1]:.2f} %", S[3])
    label_end(ax, t[-1], ke[-1], f"Kinetic / internal   end {ke[-1]:.5f} %", S[4], dy=11)

    # the curve crosses the guideline - mark the peak rather than let a reader find it
    peak = max(hg)
    peak_t = t[hg.index(peak)]
    ax.scatter([peak_t], [peak], s=30, color=S[3],
               edgecolor=SURFACE, linewidth=2, zorder=5)
    ax.annotate(f"Peak = {peak:.1f} %", xy=(peak_t, peak), xytext=(0, 10),
                textcoords="offset points", color=INK, fontsize=8.8,
                fontweight="600", ha="center")

    ax.set_xlim(t[0], t[-1] * 1.42)
    ax.set_ylim(0, 15)
    ax.set_xlabel("Time  [s]", color=INK2, fontsize=9.5)
    ax.set_ylabel("Ratio to internal energy  [%]", color=INK2, fontsize=9.5)
    titles(ax, "Solution Quality Ratios",
           "Hourglass energy exceeds the 10 % guideline and is reported as a "
           "model limitation")
    save(fig, "03_solution_quality_ratios")


def main():
    rows = read_glstat(RESULTS / "glstat")
    rc = read_rcforc(RESULTS / "rcforc")
    stroke = read_stroke_curve(DECK, lcid=4)
    fig_force(rc, stroke)
    fig_energy(rows)
    fig_quality(rows)


if __name__ == "__main__":
    main()
