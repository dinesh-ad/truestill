"""Canonical Truestill pillar-T SVG - ORIGINAL GEOMETRIC ARTWORK.

**Origin, and why it is stated here.** This T is DRAWN, not outlined. Every point comes from
the named constants below; no typeface was traced, outlined, or referenced. No font licence
attaches to it and no attribution is required.

That matters because this file sits beside marks whose origin is the opposite:
``brand/wordmark-*.svg``, ``brand/monogram-*.svg`` and the *existing*
``brand/pillar-t-*.svg`` are all outlined from **Libre Caslon Text**. A reader who assumes one
provenance covers the directory would be wrong about this one. See ``brand/PROVENANCE.md``.

Output is committed (``brand/pillar-t-geometric*.svg``) and pinned byte-for-byte by
``packages/truestill-app/tests/test_pillar_t_is_deterministic.py``. That test pins the
CURRENT constants; it does not forbid changing them. Change a constant, re-run this file,
commit both - the test then pins the new value.

Quick edit guide
----------------
* ``TOP_BAR_EXTRA`` -- lengthen the floating top slab on BOTH sides (arms stay put).
* Everything else -- see the named constants below; each has a comment.

Geometry notes (why it looks the way it does)
---------------------------------------------
* The slab underside and the crossbar top are PARALLEL curves: flat across the
  middle, then diving steeply in the outer fifth. That is what makes the white
  gap read as a thin crescent instead of a straight slot.
* The crossbar underside is a flat lintel. The arms hang off it as separate
  tapering wedges -- they do NOT sweep continuously into the stem.
* The flute is a hairline (~10% of the stem width), running the full height of
  the stem down into the base.
* Gradient: vertical ``#35558F`` → ``#121E3F`` in user space (one ramp for cap + body).
"""

from __future__ import annotations

from pathlib import Path

BRAND = Path(__file__).resolve().parents[1] / "brand"

# =============================================================================
# ONE KNOB -- floating top bar length (both sides)
# =============================================================================
# How far the top slab sticks out past the arms on left AND right.
# 0 = flush with the arms (reference look).  25 = noticeable overhang.
TOP_BAR_EXTRA = 0

# =============================================================================
# Colours & canvas
# =============================================================================
GRADIENT_TOP = "#35558F"  # mockup top stop (lighter blue)
GRADIENT_BOTTOM = "#121E3F"  # mockup bottom stop (navy)
SOLID_COLOR = "#2E4A85"  # flat export colour

VB_W = 1000  # SVG width (viewBox units)
VB_H = 1100  # SVG height (viewBox units)
CX = 500  # horizontal centre -- stem and flute are centred here

# =============================================================================
# TOP CAP  (floating slab above the white gap)
# =============================================================================
CAP_OUTER_L = 131  # outer left corner of top slab
CAP_OUTER_R = 869  # outer right corner of top slab
CAP_CORNER_R = 8  # corner radius of the top two corners

CAP_TOP_Y = 82  # y of flat top face
CAP_SIDE_Y = 96  # y where the top corner curve lands on the vertical side
CAP_END_BOT_Y = 177  # y of the underside AT THE ENDS (deepest point)
CAP_MID_BOT_Y = 140  # y of the underside AT THE CENTRE (shallowest point)

# Underside profile: flat across the middle, plunging in the outer fifth.
# Expressed as fractions of the half-width, so it survives TOP_BAR_EXTRA.
CAP_BOW_C1_F = 0.45  # first control point, along the half-width
CAP_BOW_C2_F = 0.82  # second control point, along the half-width
CAP_BOW_C2_DY = 4  # how far the second control drops below the centre y

# =============================================================================
# MAIN BODY  (crossbar + arms + stem + base -- does NOT use TOP_BAR_EXTRA)
# =============================================================================

# --- Outer silhouette ---
BODY_TIP_L = 124  # outer left edge of the arm
BODY_TIP_R = 876  # outer right edge of the arm
BODY_TIP_BULGE = 2  # how far the outer edge bows outward mid-fall
BODY_SHOULDER_Y = 217  # y where the crossbar top curve meets the outer edge

# --- Crossbar top (below the gap) -- same profile as the cap underside ---
BODY_TOP_CENTRE_Y = 171  # y at the centre of the crossbar crown
BODY_TOP_C1_F = 0.45  # first control point, along the half-width
BODY_TOP_C2_F = 0.82  # second control point, along the half-width
BODY_TOP_C2_DY = 4  # how far the second control drops below the crown

# --- Crossbar underside (the flat lintel) ---
BODY_UNDER_Y = 246  # y of the flat underside
BODY_UNDER_FILLET = 18  # radius where the underside turns into the stem

# --- Hanging arm serifs ---
ARM_INNER_TOP_L = 323  # x where the left arm's inner edge leaves the lintel
ARM_INNER_TOP_R = 677  # x where the right arm's inner edge leaves the lintel
ARM_TIP_Y = 383  # y where the outer edge finishes its inward hook
ARM_TIP_HOOK = 5  # how far the outer edge hooks back IN at the very tip
ARM_TIP_ROUND = 9  # how far the rounded tip bulges below ARM_TIP_Y
ARM_TIP_LIFT = 10  # how much higher the inner side of the tip sits
ARM_TIP_INNER_L = 157  # inner x of the left tip
ARM_TIP_INNER_R = 843  # inner x of the right tip
ARM_KNEE_Y = 314  # y of the control that fattens the concave sweep

# --- Stem (vertical pillar) ---
BODY_STEM_L = 424  # left outer edge of stem
BODY_STEM_R = 576  # right outer edge of stem
BODY_STEM_BOTTOM_Y = 902  # y where the stem ends and the base flare starts

# --- Base flare (classical foot) ---
BODY_BASE_OUT_L = 338  # left outer x of the foot
BODY_BASE_OUT_R = 662  # right outer x of the foot
BODY_BASE_C1_Y = 922  # y of the first flare control (still on the stem line)
BODY_BASE_C2_Y = 934  # y of the second flare control (already at foot width)
BODY_BASE_SHOULDER_Y = 948  # y where the foot goes vertical
BODY_BASE_BOTTOM_Y = 960  # y of the flat bottom edge

# --- Central flute (hairline cutout, evenodd) ---
FLUTE_TOP_Y = 265  # y where the flute starts
FLUTE_BOTTOM_Y = 918  # y where the flute ends
FLUTE_L = 491  # left edge of flute
FLUTE_R = 509  # right edge of flute
FLUTE_BOW_TOP_Y = 256  # y of the top cap control (rounds the end)
FLUTE_BOW_BOT_Y = 927  # y of the bottom cap control


def _svg(*, gradient: bool, title: str) -> str:
    """Build the SVG document string."""
    if gradient:
        paint = "url(#pillar-gradient)"
        defs = f"""
  <defs>
    <linearGradient id="pillar-gradient"
        x1="{CX}" y1="{CAP_TOP_Y}" x2="{CX}" y2="{BODY_BASE_BOTTOM_Y}"
        gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="{GRADIENT_TOP}"/>
      <stop offset="100%" stop-color="{GRADIENT_BOTTOM}"/>
    </linearGradient>
  </defs>
"""
    else:
        paint = SOLID_COLOR
        defs = ""

    e = TOP_BAR_EXTRA

    # ---- top cap -------------------------------------------------------
    cap_l = CAP_OUTER_L - e
    cap_r = CAP_OUTER_R + e
    half = cap_r - CX

    # underside controls, mirrored around CX
    ub_r1 = CX + CAP_BOW_C1_F * half
    ub_r2 = CX + CAP_BOW_C2_F * half
    ub_l1 = CX - CAP_BOW_C1_F * half
    ub_l2 = CX - CAP_BOW_C2_F * half
    ub_y2 = CAP_MID_BOT_Y + CAP_BOW_C2_DY

    top_cap = f"""
      M {cap_l} {CAP_SIDE_Y}
      Q {cap_l} {CAP_TOP_Y} {cap_l + CAP_CORNER_R} {CAP_TOP_Y}
      H {cap_r - CAP_CORNER_R}
      Q {cap_r} {CAP_TOP_Y} {cap_r} {CAP_SIDE_Y}
      V {CAP_END_BOT_Y}
      C {ub_r2} {ub_y2} {ub_r1} {CAP_MID_BOT_Y} {CX} {CAP_MID_BOT_Y}
      C {ub_l1} {CAP_MID_BOT_Y} {ub_l2} {ub_y2} {cap_l} {CAP_END_BOT_Y}
      Z
    """

    # ---- crossbar top --------------------------------------------------
    bhalf = BODY_TIP_R - CX
    ct_r1 = CX + BODY_TOP_C1_F * bhalf
    ct_r2 = CX + BODY_TOP_C2_F * bhalf
    ct_l1 = CX - BODY_TOP_C1_F * bhalf
    ct_l2 = CX - BODY_TOP_C2_F * bhalf
    ct_y2 = BODY_TOP_CENTRE_Y + BODY_TOP_C2_DY

    # ---- derived helpers ----------------------------------------------
    tip_bulge_l = BODY_TIP_L - BODY_TIP_BULGE
    tip_bulge_r = BODY_TIP_R + BODY_TIP_BULGE
    hook_l = BODY_TIP_L + ARM_TIP_HOOK
    hook_r = BODY_TIP_R - ARM_TIP_HOOK
    tip_mid_l = (hook_l + ARM_TIP_INNER_L) / 2
    tip_mid_r = (hook_r + ARM_TIP_INNER_R) / 2
    tip_bot = ARM_TIP_Y + ARM_TIP_ROUND
    tip_lift = ARM_TIP_Y - ARM_TIP_LIFT

    main_body = f"""
      M {BODY_TIP_L} {BODY_SHOULDER_Y}
      C {ct_l2} {ct_y2} {ct_l1} {BODY_TOP_CENTRE_Y} {CX} {BODY_TOP_CENTRE_Y}
      C {ct_r1} {BODY_TOP_CENTRE_Y} {ct_r2} {ct_y2} {BODY_TIP_R} {BODY_SHOULDER_Y}
      C {tip_bulge_r} 300 {tip_bulge_r} 345 {hook_r} {ARM_TIP_Y}
      Q {tip_mid_r} {tip_bot} {ARM_TIP_INNER_R} {tip_lift}
      C {ARM_TIP_INNER_R} {ARM_KNEE_Y} {ARM_TIP_INNER_R - 73} {BODY_UNDER_Y} {ARM_INNER_TOP_R} {BODY_UNDER_Y}
      L {BODY_STEM_R + BODY_UNDER_FILLET} {BODY_UNDER_Y}
      Q {BODY_STEM_R} {BODY_UNDER_Y} {BODY_STEM_R} {BODY_UNDER_Y + BODY_UNDER_FILLET}
      V {BODY_STEM_BOTTOM_Y}
      C {BODY_STEM_R} {BODY_BASE_C1_Y} {BODY_BASE_OUT_R} {BODY_BASE_C2_Y} {BODY_BASE_OUT_R} {BODY_BASE_SHOULDER_Y}
      V {BODY_BASE_BOTTOM_Y}
      H {BODY_BASE_OUT_L}
      V {BODY_BASE_SHOULDER_Y}
      C {BODY_BASE_OUT_L} {BODY_BASE_C2_Y} {BODY_STEM_L} {BODY_BASE_C1_Y} {BODY_STEM_L} {BODY_STEM_BOTTOM_Y}
      V {BODY_UNDER_Y + BODY_UNDER_FILLET}
      Q {BODY_STEM_L} {BODY_UNDER_Y} {BODY_STEM_L - BODY_UNDER_FILLET} {BODY_UNDER_Y}
      L {ARM_INNER_TOP_L} {BODY_UNDER_Y}
      C {ARM_TIP_INNER_L + 73} {BODY_UNDER_Y} {ARM_TIP_INNER_L} {ARM_KNEE_Y} {ARM_TIP_INNER_L} {tip_lift}
      Q {tip_mid_l} {tip_bot} {hook_l} {ARM_TIP_Y}
      C {tip_bulge_l} 345 {tip_bulge_l} 300 {BODY_TIP_L} {BODY_SHOULDER_Y}
      Z

      M {FLUTE_L} {FLUTE_TOP_Y}
      Q {CX} {FLUTE_BOW_TOP_Y} {FLUTE_R} {FLUTE_TOP_Y}
      V {FLUTE_BOTTOM_Y}
      Q {CX} {FLUTE_BOW_BOT_Y} {FLUTE_L} {FLUTE_BOTTOM_Y}
      Z
    """

    x0 = min(0, cap_l - 20)
    x1 = max(VB_W, cap_r + 20)
    width = x1 - x0

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="{x0} 0 {width} {VB_H}"
    width="{width}"
    height="{VB_H}"
    role="img"
    aria-labelledby="title desc"
>
  <title id="title">{title}</title>
  <desc id="desc">
    Truestill pillar T. TOP_BAR_EXTRA={e}.
  </desc>
{defs}
  <g id="truestill-pillar-t" fill="{paint}">
    <path id="top-cap" d="{top_cap}"/>
    <path
        id="main-body"
        fill-rule="evenodd"
        clip-rule="evenodd"
        d="{main_body}"
    />
  </g>
</svg>
"""


def write_pillar_t(*, gradient: bool = True, filename: str | None = None) -> Path:
    """Write the pillar-T SVG into ``assets/`` and return its path."""
    BRAND.mkdir(parents=True, exist_ok=True)
    if filename is None:
        filename = "pillar-t-geometric.svg" if gradient else "pillar-t-geometric-solid.svg"
    path = BRAND / filename
    title = "Truestill pillar T (gradient)" if gradient else "Truestill pillar T (solid)"
    path.write_text(_svg(gradient=gradient, title=title), encoding="utf-8")
    return path


if __name__ == "__main__":
    # Two files, not three. The scratch version also wrote a third copy under a neutral name
    # as the "active" one; with the outputs committed, a duplicate is just a second thing to
    # drift.
    print(f"TOP_BAR_EXTRA={TOP_BAR_EXTRA}")
    print(f"gradient: {write_pillar_t(gradient=True)}")
    print(f"solid:    {write_pillar_t(gradient=False)}")
