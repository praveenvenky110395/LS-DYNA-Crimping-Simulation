"""
Rebuilds every figure and number in the README from the committed LS-DYNA output.

Inputs, all under results/ as the solver wrote them:
    glstat      global energies and the time step, every 0.5 ms
    rcforc      contact resultants per interface, every 0.2 ms
    matsum      per-part energies and added mass, every 1 ms
The punch stroke comes from load curve 4 (PUNCH_STROKE) in model/crimp_forming.k,
so the x axis of the force plot is the commanded tool travel, not a measured node.

Outputs:
    results/results.csv                     the scalars quoted in the README
    results/figures/01_force_stroke.png
    results/figures/02_energy_balance.png
    results/figures/03_quality_ratios.png
    results/figures/04_hourglass_by_part.png

Run from anywhere:  python3 scripts/postprocess.py
"""

import bisect
import csv
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
FIG = RES / "figures"
DECK = ROOT / "model" / "crimp_forming.k"

# dataviz categorical slots 1-4, validated for a light surface
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, MUTED, GRID = "#0b0b0b", "#6e6c66", "#e3e2dd"

# contact interfaces that press on each rigid tool (see the deck)
PUNCH_CIDS = (2, 6)      # FERRULE_TO_PUNCH, STRAND_TO_PUNCH
ANVIL_CIDS = (1, 7)      # FERRULE_TO_ANVIL, STRAND_TO_ANVIL

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
    "text.color": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "white", "axes.facecolor": "white",
})


# ----------------------------------------------------------------- readers

def read_glstat(path):
    """glstat is a block per output time, one 'label....value' per line."""
    want = {
        "time": "t", "time step": "dt", "kinetic energy": "ke",
        "internal energy": "ie", "hourglass energy": "hg",
        "sliding interface energy": "sl", "external work": "ew",
        "total energy": "te", "total energy / initial energy": "ratio",
        "added mass": "am", "percentage increase": "amp",
    }
    row = re.compile(r"^\s*([A-Za-z][A-Za-z ./]*?)\.{2,}\s*([-+]?[\d.]+(?:[Ee][-+]?\d+)?)\s*$")
    out, cur = [], {}
    for line in path.read_text(errors="replace").splitlines():
        m = row.match(line)
        if not m:
            continue
        key = want.get(m.group(1).strip().lower())
        if key is None:
            continue
        if key == "t" and "t" in cur:
            out.append(cur)
            cur = {}
        cur[key] = float(m.group(2))
    if "t" in cur:
        out.append(cur)
    return [r for r in out if "ie" in r]


def read_rcforc(path):
    """One line per interface side and output time.

    The solver writes
        SURFA  <cid> time <t>  x <fx>  y <fy>  z <fz>  mass ...
    SURFA is the tracked surface, SURFB the reference surface. For every
    interface here the tool is the reference surface, so the SURFB rows carry
    the force on the punch or the anvil.
    """
    pat = re.compile(
        r"^\s*(SURFA|SURFB|master|slave)\s+(\d+)\s+time\s+(\S+)"
        r"\s+x\s+(\S+)\s+y\s+(\S+)\s+z\s+(\S+)", re.I)
    got = {}
    for line in path.read_text(errors="replace").splitlines():
        m = pat.match(line)
        if not m:
            continue
        side = m.group(1).upper()
        key = (int(m.group(2)), "SURFB" if side in ("SURFB", "MASTER") else "SURFA")
        got.setdefault(key, []).append(
            (float(m.group(3)), float(m.group(4)), float(m.group(5)), float(m.group(6))))
    return got


def read_matsum(path):
    """Per-part internal, kinetic and hourglass energy, plus added mass."""
    legend = {}
    txt = path.read_text(errors="replace")
    lg = re.search(r"\{BEGIN LEGEND\}(.*?)\{END LEGEND\}", txt, re.S)
    for line in lg.group(1).splitlines():
        m = re.match(r"\s*(\d+)\s+(\S.*?)\s*$", line)
        if m and not m.group(2).startswith("Title"):
            legend[int(m.group(1))] = m.group(2)
    blocks = re.split(r"\n\s*time\s*=\s*([-+0-9.Ee]+)\s*\n", txt)
    series = []
    for i in range(1, len(blocks), 2):
        parts = {}
        for pm in re.finditer(
                r"mat\.#=\s*(\d+)\s+inten=\s*([-+0-9.Ee]+)\s+kinen=\s*([-+0-9.Ee]+)"
                r".*?hgeng=\s*([-+0-9.Ee]+)\s+\+mass=\s*([-+0-9.Ee]+)", blocks[i + 1], re.S):
            parts[int(pm.group(1))] = dict(
                ie=float(pm.group(2)), ke=float(pm.group(3)),
                hg=float(pm.group(4)), addmass=float(pm.group(5)))
        if parts:
            series.append((float(blocks[i]), parts))
    return legend, series


def read_sleout_friction(path):
    """Last summary block of sleout: the frictional part of the contact energy."""
    if not path.exists():
        return None
    hits = re.findall(r"friction energy\s*=\s*([-+0-9.Ee]+)",
                      path.read_text(errors="replace"))
    return float(hits[-1]) if hits else None


def read_stroke_curve(path):
    """Load curve 4, PUNCH_STROKE: prescribed displacement of the punch in mm."""
    lines = path.read_text(errors="replace").splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "PUNCH_STROKE":
            break
    else:
        raise RuntimeError("PUNCH_STROKE curve not found in the deck")
    pts = []
    for line in lines[i + 4:]:
        if line.startswith(("*", "$")):
            break
        f = line.split()
        if len(f) == 2:
            pts.append((float(f[0]), float(f[1])))
    return pts


# ----------------------------------------------------------------- helpers

def interp(pts, x):
    xs = [p[0] for p in pts]
    i = min(max(bisect.bisect_left(xs, x), 1), len(pts) - 1)
    (x0, y0), (x1, y1) = pts[i - 1], pts[i]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0) if x1 > x0 else y1


def tool_force(rc, cids):
    """Sum the y resultant over the interfaces that load one tool, per time."""
    per_t = {}
    for (cid, side), rows in rc.items():
        if cid not in cids or side != "SURFB":
            continue
        for t, _fx, fy, _fz in rows:
            per_t[round(t, 9)] = per_t.get(round(t, 9), 0.0) + fy
    return sorted((t, abs(v)) for t, v in per_t.items())


def fmt(ax, xlabel, ylabel, title=None, sub=None, pad=14):
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title, loc="left", fontsize=11.5, fontweight="bold", pad=pad)
    if sub:
        ax.annotate(sub, xy=(0, 1.012), xycoords="axes fraction",
                    fontsize=9, color=MUTED, va="bottom")


# ----------------------------------------------------------------- figures

def fig_force(force_p, force_a, stroke, t_full, peak):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.2, 4.3))

    # The two tools carry the same load to within a fraction of a percent, so
    # the anvil is drawn wide underneath and shows as a halo around the punch.
    ramp_p = [(abs(interp(stroke, t)), f) for t, f in force_p if t <= t_full]
    ramp_a = [(abs(interp(stroke, t)), f) for t, f in force_a if t <= t_full]
    ax1.plot(*zip(*ramp_a), lw=5, color=ORANGE, alpha=0.85,
             label="anvil reaction", zorder=2, solid_capstyle="round")
    ax1.plot(*zip(*ramp_p), lw=2, color=BLUE, label="punch force", zorder=3)
    ax1.plot([peak["stroke"]], [peak["f"]], "o", ms=9, mfc=BLUE, mec="white",
             mew=2, zorder=4)
    ax1.annotate(f"{peak['f'] / 1000:.3f} kN\nat {peak['stroke']:.2f} mm",
                 xy=(peak["stroke"], peak["f"]), xytext=(-26, -14),
                 textcoords="offset points", ha="right", va="top",
                 fontsize=9.5, fontweight="bold", color=INK,
                 arrowprops=dict(arrowstyle="-", color=MUTED, lw=1,
                                 shrinkA=2, shrinkB=6))
    ax1.annotate("barrel wings bend\nfreely, almost no load",
                 xy=(2.1, 260), fontsize=9, color=MUTED, ha="center")
    ax1.legend(frameon=False, loc="upper left", fontsize=9.5)
    fmt(ax1, "punch stroke  (mm)", "vertical contact force  (N)",
        "Crimping force over the stroke",
        "the closing ramp, up to full stroke")

    ax2.plot(*zip(*[(t * 1e3, f) for t, f in force_a]), lw=5, color=ORANGE,
             alpha=0.85, label="anvil reaction", zorder=2, solid_capstyle="round")
    ax2.plot(*zip(*[(t * 1e3, f) for t, f in force_p]), lw=2, color=BLUE,
             label="punch force", zorder=3)
    ax2.axvspan(t_full * 1e3, force_p[-1][0] * 1e3, color=GRID, alpha=0.9, lw=0,
                zorder=1)
    ax2.annotate("stroke held\nhere", xy=(t_full * 1e3 + 3.8, peak["f"] * 0.62),
                 ha="center", va="top", fontsize=9, color=MUTED)
    ax2.annotate(f"{force_p[-1][1] / 1000:.3f} kN",
                 xy=(force_p[-1][0] * 1e3, force_p[-1][1]), xytext=(5, 3),
                 textcoords="offset points", fontsize=9, fontweight="bold",
                 color=BLUE)
    ax2.set_xlim(0, force_p[-1][0] * 1e3 * 1.10)
    ax2.legend(frameon=False, loc="upper left", fontsize=9.5)
    fmt(ax2, "time  (ms)", "vertical contact force  (N)",
        "The same force against time",
        "the load relaxes while the stroke is held")

    fig.tight_layout()
    fig.savefig(FIG / "01_force_stroke.png", dpi=170)
    plt.close(fig)


def fig_energy(g):
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    t = [r["t"] * 1e3 for r in g]
    for key, col, lab in (("ew", INK, "external work"),
                          ("ie", BLUE, "internal energy"),
                          ("sl", AQUA, "sliding (friction) energy"),
                          ("hg", ORANGE, "hourglass energy")):
        ax.plot(t, [r[key] for r in g], lw=2,
                color=col, label=lab, zorder=3 if key != "ew" else 2,
                ls="-" if key != "ew" else (0, (1, 1.6)))
    for key, col in (("ew", INK), ("ie", BLUE), ("sl", AQUA), ("hg", ORANGE)):
        ax.annotate(f"{g[-1][key]:,.0f}", xy=(t[-1], g[-1][key]), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=9,
                    fontweight="bold", color=col if col != INK else INK)
    ax.set_xlim(0, t[-1] * 1.12)
    ax.legend(frameon=False, loc="upper left", fontsize=9.5)
    fmt(ax, "time  (ms)", "energy  (mJ)", "Where the work goes",
        "kinetic energy stays below 1 mJ and is plotted as a ratio in figure 3")
    fig.tight_layout()
    fig.savefig(FIG / "02_energy_balance.png", dpi=170)
    plt.close(fig)


def fig_ratios(g):
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    # A share of the internal energy means nothing while that energy is still
    # near zero, so the curves start once it passes 10 mJ.
    gg = [r for r in g if r["ie"] >= 10.0]
    t = [r["t"] * 1e3 for r in gg]
    hg = [100 * r["hg"] / r["ie"] for r in gg]
    ke = [100 * r["ke"] / r["ie"] for r in gg]
    dr = [100 * abs(1.0 - r["ratio"]) for r in gg]
    ax.axhline(10, color=MUTED, lw=1, zorder=1)
    ax.annotate("10 % — the usual limit quoted for hourglass energy",
                xy=(t[0], 10), xytext=(2, 5), textcoords="offset points",
                ha="left", fontsize=9, color=MUTED)
    for y, col, lab in ((hg, ORANGE, "hourglass / internal"),
                        (dr, YELLOW, "energy balance error  |1 − ratio|"),
                        (ke, BLUE, "kinetic / internal")):
        ax.plot(t, y, lw=2, color=col, label=lab, zorder=3)
        ax.annotate(f"{y[-1]:.2f} %", xy=(t[-1], y[-1]), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=9,
                    fontweight="bold", color=col)
    ax.set_xlim(t[0] - 2, t[-1] * 1.13)
    ax.set_ylim(0, 14)
    ax.legend(frameon=False, loc="upper left", fontsize=9.5)
    fmt(ax, "time  (ms)", "share of internal energy  (%)",
        "Three ratios that say whether the run is trustworthy",
        "shown from the point where the internal energy passes 10 mJ; "
        "before that the denominator is near zero")
    fig.tight_layout()
    fig.savefig(FIG / "03_quality_ratios.png", dpi=170)
    plt.close(fig)


def fig_hourglass(legend, series):
    _t, last = series[-1]
    rows = [(legend.get(p, str(p)), v["ie"], v["hg"]) for p, v in last.items()
            if v["ie"] > 1e-6]
    rows.sort(key=lambda r: r[2] / r[1])
    names = [r[0].replace("WIRE_STRAND_", "strand ").replace("FERRULE", "ferrule")
             for r in rows]
    share = [100 * r[2] / r[1] for r in rows]
    fig, ax = plt.subplots(figsize=(8.2, 6.6))
    cols = [ORANGE if "ferrule" in n else BLUE for n in names]
    ax.barh(names, share, color=cols, height=0.72, zorder=3)
    for y, (n, s, r) in enumerate(zip(names, share, rows)):
        ax.annotate(f"{s:.1f} %    {r[2]:.1f} of {r[1]:.0f} mJ",
                    xy=(s, y), xytext=(7, 0), textcoords="offset points",
                    va="center", fontsize=8.5,
                    fontweight="bold" if "ferrule" in n else "normal",
                    color=INK if "ferrule" in n else MUTED)
    ax.set_xlim(0, max(share) * 1.45)
    ax.tick_params(axis="y", length=0, labelsize=8.5)
    fmt(ax, "hourglass energy as a share of that part's internal energy  (%)", "",
        "Which part carries the hourglass energy",
        "at the end of the run; the ferrule is the part that is actually formed",
        pad=26)
    fig.tight_layout()
    fig.savefig(FIG / "04_hourglass_by_part.png", dpi=170)
    plt.close(fig)


# ----------------------------------------------------------------- main

def main():
    FIG.mkdir(parents=True, exist_ok=True)
    g = read_glstat(RES / "glstat")
    rc = read_rcforc(RES / "rcforc")
    legend, ms = read_matsum(RES / "matsum")
    fric = read_sleout_friction(RES / "sleout")
    stroke = read_stroke_curve(DECK)

    force_p = tool_force(rc, PUNCH_CIDS)
    force_a = tool_force(rc, ANVIL_CIDS)
    s_max = max(abs(v) for _t, v in stroke)
    t_full = next(t for t, v in stroke if abs(abs(v) - s_max) < 1e-9)

    t_pk, f_pk = max(force_p, key=lambda p: p[1])
    f_a_pk = min(force_a, key=lambda p: abs(p[0] - t_pk))[1]
    peak = dict(t=t_pk, f=f_pk, stroke=abs(interp(stroke, t_pk)))

    last = g[-1]
    # A ratio to the internal energy says nothing while the internal energy is
    # still near zero, so the maxima are taken over the forming window: from the
    # first time the internal energy passes 10 % of its final value.
    ie_gate = 0.10 * last["ie"]
    formed = [r for r in g if r["ie"] >= ie_gate]
    t_form = formed[0]["t"]
    t_hg, hg_max = max(((r["t"], 100 * r["hg"] / r["ie"]) for r in formed),
                       key=lambda p: p[1])
    t_ke, ke_max = max(((r["t"], 100 * r["ke"] / r["ie"]) for r in formed),
                       key=lambda p: p[1])
    ke_abs = max(g, key=lambda r: r["ke"])

    _t_ms, parts = ms[-1]
    strands = [p for p, n in legend.items() if n.startswith("WIRE_STRAND")]
    ferrule = [p for p, n in legend.items() if n == "FERRULE"]
    tot = lambda ids, k: sum(parts[i][k] for i in ids if i in parts)

    scal = [
        ("peak punch force", f"{f_pk:.1f}", "N"),
        ("peak punch force, time", f"{t_pk:.4f}", "s"),
        ("punch stroke at peak force", f"{peak['stroke']:.3f}", "mm"),
        ("total punch stroke", f"{s_max:.2f}", "mm"),
        ("anvil reaction at that instant", f"{f_a_pk:.1f}", "N"),
        ("punch vs anvil difference", f"{100 * abs(f_pk - f_a_pk) / f_pk:.2f}", "%"),
        ("punch force at termination", f"{force_p[-1][1]:.1f}", "N"),
        ("internal energy, final", f"{last['ie']:.2f}", "mJ"),
        ("external work, final", f"{last['ew']:.2f}", "mJ"),
        ("sliding interface energy, final", f"{last['sl']:.2f}", "mJ"),
        ("hourglass energy, final", f"{last['hg']:.2f}", "mJ"),
        ("kinetic energy, final", f"{last['ke']:.3f}", "mJ"),
        ("energy ratio, final", f"{last['ratio']:.6f}", "-"),
        ("energy balance error, final", f"{100 * abs(1 - last['ratio']):.2f}", "%"),
        ("forming window starts (IE = 10 % of final)", f"{t_form:.4f}", "s"),
        ("hourglass / internal, maximum in that window", f"{hg_max:.2f}", "%"),
        ("hourglass / internal, at maximum, time", f"{t_hg:.4f}", "s"),
        ("hourglass / internal, final", f"{100 * last['hg'] / last['ie']:.2f}", "%"),
        ("kinetic energy, maximum over whole run", f"{ke_abs['ke']:.3f}", "mJ"),
        ("kinetic energy, at maximum, time", f"{ke_abs['t']:.4f}", "s"),
        ("kinetic / internal, at that instant", f"{100 * ke_abs['ke'] / ke_abs['ie']:.3f}", "%"),
        ("kinetic / internal, maximum in forming window", f"{ke_max:.3f}", "%"),
        ("kinetic / internal, at maximum, time", f"{t_ke:.4f}", "s"),
        ("kinetic / internal, final", f"{100 * last['ke'] / last['ie']:.3f}", "%"),
        ("sliding / internal, final", f"{100 * last['sl'] / last['ie']:.1f}", "%"),
        ("hourglass, ferrule", f"{tot(ferrule, 'hg'):.2f}", "mJ"),
        ("hourglass / internal, ferrule", f"{100 * tot(ferrule, 'hg') / tot(ferrule, 'ie'):.2f}", "%"),
        ("hourglass, 19 strands", f"{tot(strands, 'hg'):.2f}", "mJ"),
        ("hourglass / internal, 19 strands", f"{100 * tot(strands, 'hg') / tot(strands, 'ie'):.2f}", "%"),
        ("internal energy, ferrule share", f"{100 * tot(ferrule, 'ie') / (tot(ferrule, 'ie') + tot(strands, 'ie')):.1f}", "%"),
        ("friction energy, final (sleout)", f"{fric:.2f}", "mJ") if fric else None,
        ("physical model mass", f"{last['am'] / (last['amp'] / 100):.4e}", "t"),
        ("added mass, final", f"{last['am']:.4e}", "t"),
        ("added mass, as a multiple of physical mass", f"{last['amp'] / 100:.0f}", "x"),
        ("time step", f"{last['dt']:.3e}", "s"),
    ]
    scal = [s for s in scal if s]
    with (RES / "results.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["quantity", "value", "unit"])
        w.writerows(scal)

    fig_force(force_p, force_a, stroke, t_full, peak)
    fig_energy(g)
    fig_ratios(g)
    fig_hourglass(legend, ms)

    print(f"glstat {len(g)} states, rcforc {len(force_p)} samples, "
          f"matsum {len(ms)} states, stroke curve {len(stroke)} points")
    for name, val, unit in scal:
        print(f"  {name:<44} {val:>12}  {unit}")
    print(f"\nwrote {RES / 'results.csv'} and 4 figures in {FIG}")


if __name__ == "__main__":
    main()
