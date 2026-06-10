# NEC 210.20(A), NEC 240.6(A), and NEC 430.52 encoded as pure Python.
# No Revit, no MCP, no WebSocket — takes circuit dicts, returns compliance result dicts.
# All pass/fail determinations happen here so Claude's role is explanation, not computation.

# NEC 240.6(A) standard ampere ratings for fixed-trip breakers.
STANDARD_SIZES = [
    15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 125, 150, 175, 200,
    225, 250, 300, 350, 400, 450, 500, 600, 700, 800, 1000, 1200, 1600, 2000,
    2500, 3000, 4000, 5000, 6000,
]

# Load classifications that fall under NEC 430/440 motor rules.
MOTOR_LOAD_TYPES = {"Motor", "HVAC"}

# --- NEC Table 430.248: Single-phase AC motor FLC (amps), 60 Hz ---
# Outer key: HP. Inner key: nominal system voltage. Values: FLC in amps.
# Fractional HP expressed as decimals: 1/6 ≈ 0.1667, 1/4 = 0.25, 1/3 ≈ 0.3333.
_FLC_1PH = {
    0.1667: {115:   4.4, 200:  2.5, 208:  2.4, 230:  2.2},  # 1/6 HP
    0.25:   {115:   5.8, 200:  3.3, 208:  3.2, 230:  2.9},  # 1/4 HP
    0.3333: {115:   7.2, 200:  4.1, 208:  4.0, 230:  3.6},  # 1/3 HP
    0.5:    {115:   9.8, 200:  5.6, 208:  5.4, 230:  4.9},
    0.75:   {115:  13.8, 200:  7.9, 208:  7.6, 230:  6.9},
    1.0:    {115:  16.0, 200:  9.2, 208:  8.8, 230:  8.0},
    1.5:    {115:  20.0, 200: 11.5, 208: 11.0, 230: 10.0},
    2.0:    {115:  24.0, 200: 13.8, 208: 13.2, 230: 12.0},
    3.0:    {115:  34.0, 200: 19.6, 208: 18.7, 230: 17.0},
    5.0:    {115:  56.0, 200: 32.2, 208: 30.8, 230: 28.0},
    7.5:    {115:  80.0, 200: 46.0, 208: 44.0, 230: 40.0},
    10.0:   {115: 100.0, 200: 57.5, 208: 55.0, 230: 50.0},
}

# --- NEC Table 430.250: Three-phase AC motor FLC (amps), 60 Hz ---
_FLC_3PH = {
    0.5:   {200:   2.5, 208:   2.4, 230:   2.2, 460:   1.1, 575:  0.9},
    0.75:  {200:   3.7, 208:   3.5, 230:   3.2, 460:   1.6, 575:  1.3},
    1.0:   {200:   4.8, 208:   4.6, 230:   4.2, 460:   2.1, 575:  1.7},
    1.5:   {200:   6.9, 208:   6.6, 230:   6.0, 460:   3.0, 575:  2.4},
    2.0:   {200:   7.8, 208:   7.5, 230:   6.8, 460:   3.4, 575:  2.7},
    3.0:   {200:  11.0, 208:  10.6, 230:   9.6, 460:   4.8, 575:  3.9},
    5.0:   {200:  17.5, 208:  16.7, 230:  15.2, 460:   7.6, 575:  6.1},
    7.5:   {200:  25.3, 208:  24.2, 230:  22.0, 460:  11.0, 575:  9.0},
    10.0:  {200:  32.2, 208:  30.8, 230:  28.0, 460:  14.0, 575: 11.0},
    15.0:  {200:  48.3, 208:  46.2, 230:  42.0, 460:  21.0, 575: 17.0},
    20.0:  {200:  62.1, 208:  59.4, 230:  54.0, 460:  27.0, 575: 22.0},
    25.0:  {200:  78.2, 208:  74.8, 230:  68.0, 460:  34.0, 575: 27.0},
    30.0:  {200:  92.0, 208:  88.0, 230:  80.0, 460:  40.0, 575: 32.0},
    40.0:  {200: 119.6, 208: 114.4, 230: 104.0, 460:  52.0, 575: 41.0},
    50.0:  {200: 149.5, 208: 143.0, 230: 130.0, 460:  65.0, 575: 52.0},
    60.0:  {200: 177.1, 208: 169.4, 230: 154.0, 460:  77.0, 575: 62.0},
    75.0:  {200: 220.8, 208: 211.2, 230: 192.0, 460:  96.0, 575: 77.0},
    100.0: {200: 285.2, 208: 272.8, 230: 248.0, 460: 124.0, 575: 99.0},
    125.0: {200: 358.8, 208: 343.2, 230: 312.0, 460: 156.0, 575: 125.0},
    150.0: {200: 414.0, 208: 396.0, 230: 360.0, 460: 180.0, 575: 144.0},
    200.0: {200: 552.0, 208: 528.0, 230: 480.0, 460: 240.0, 575: 192.0},
}


def next_standard_size(amps: float) -> int:
    """Return the smallest standard breaker size >= amps per NEC 240.6(A).

    Exact matches are not rounded up (e.g. 20.0 → 20, not 25).
    Above 6000A returns 6000; circuits requiring more are outside this tool's scope.
    """
    for size in STANDARD_SIZES:
        if size >= amps:
            return size
    return STANDARD_SIZES[-1]


def _snap_voltage(circuit_v: float, table_voltages: list) -> int | None:
    """Return the largest table voltage <= circuit_v, or None if below all entries.

    A 480V system snaps to the 460V column — conservative and standard practice.
    A 120V system snaps to 115V. A 277V system has no snap in either table (returns None).
    """
    candidates = [v for v in table_voltages if v <= circuit_v]
    return candidates[-1] if candidates else None


def _snap_hp(hp: float, table: dict) -> float:
    """Return the closest HP key in table to hp.

    Motors ship in standard increments; an exact match is the normal case.
    Snapping handles minor rounding artifacts (e.g. 7.49 stored by Revit → 7.5).
    """
    return min(table.keys(), key=lambda k: abs(k - hp))


def _lookup_motor_flc(hp: float, voltage: float, poles: int):
    """Return (flc, snapped_hp, snapped_voltage) from NEC Table 430.248/430.250, or None.

    Returns None when circuit_v is below the lowest table voltage (e.g. a 100V system),
    which signals the caller to fall back to manual_review.
    """
    table = _FLC_1PH if poles == 1 else _FLC_3PH
    table_voltages = sorted(next(iter(table.values())).keys())

    snapped_hp = _snap_hp(hp, table)
    snapped_v  = _snap_voltage(voltage, table_voltages)

    if snapped_v is None:
        return None

    flc = table[snapped_hp][snapped_v]
    return flc, snapped_hp, snapped_v


def _check_motor_circuit(circuit: dict, base: dict, hp: float) -> dict:
    """Apply NEC 430.52 to a motor circuit that has a known HP value.

    NEC 430.52 maximum for an inverse-time circuit breaker: 250% of motor FLC,
    rounded up to the next standard size. A breaker larger than this cap provides
    inadequate short-circuit protection for the branch circuit conductors.

    We assume inverse-time (thermal-magnetic) breakers — the standard type in
    commercial distribution panels. Instantaneous-trip (magnetic-only) breakers
    allow up to 800% per Table 430.52 and are not handled here.
    """
    voltage       = circuit["voltage"]
    poles         = circuit["poles"]
    actual_rating = circuit["breaker_rating"]

    result = _lookup_motor_flc(hp, voltage, poles)
    if result is None:
        table_num = "430.248" if poles == 1 else "430.250"
        return {
            **base,
            "status":          "manual_review",
            "hp":              hp,
            "flc_amps":        None,
            "load_amps":       None,
            "required_amps":   None,
            "required_rating": None,
            "is_oversized":    False,
            "is_zero_load":    False,
            "nec_ref":         "NEC 430.52",
            "reason": (
                f"{hp} HP motor at {voltage:.0f}V — no matching entry in NEC Table {table_num}. "
                "Manual review required."
            ),
        }

    flc, snapped_hp, snapped_v = result
    max_amps   = flc * 2.5                     # NEC 430.52 Table: 250% of FLC for inverse-time CB
    max_rating = next_standard_size(max_amps)  # round up to next standard size

    is_fail = actual_rating > max_rating

    if is_fail:
        reason = (
            f"Breaker is {actual_rating}A; NEC 430.52 limits an inverse-time breaker to "
            f"{max_rating}A for a {snapped_hp} HP, {snapped_v}V motor "
            f"(FLC = {flc}A; 250% = {max_amps:.1f}A). "
            "Breaker exceeds the maximum — inadequate short-circuit protection."
        )
    else:
        reason = (
            f"Breaker is {actual_rating}A; NEC 430.52 maximum is {max_rating}A for a "
            f"{snapped_hp} HP, {snapped_v}V motor (FLC = {flc}A; 250% = {max_amps:.1f}A). "
            "Correctly sized."
        )

    return {
        **base,
        "status":          "fail" if is_fail else "pass",
        "hp":              snapped_hp,
        "flc_amps":        flc,
        "load_amps":       None,              # FLC (not VA/V) is the reference current for motors
        "required_amps":   round(max_amps, 2),
        "required_rating": max_rating,        # this is a MAXIMUM for motors, not a minimum
        "is_oversized":    False,             # "too large" is a fail for motors, not pass+flag
        "is_zero_load":    False,
        "nec_ref":         "NEC 430.52",
        "reason":          reason,
    }


def check_circuit(circuit: dict) -> dict:
    """Apply NEC rules to one circuit dict and return a structured compliance result.

    Input keys (matching the schema returned by CircuitQueryHandler):
        circuit_number, panel, apparent_load_va, voltage, poles,
        breaker_rating, load_classification, is_spare, hp (optional)

    Status values in the returned dict:
        "spare"         — no connected elements; sizing not applicable
        "manual_review" — motor/HVAC without HP data; NEC 430.52 requires HP to size
        "pass"          — breaker meets the applicable NEC rule
        "fail"          — breaker violates NEC (undersized for 210.20(A); oversized for 430.52)
    """
    circuit_number      = circuit["circuit_number"]
    panel               = circuit["panel"]
    load_classification = circuit["load_classification"]
    actual_rating       = circuit["breaker_rating"]
    is_spare            = circuit.get("is_spare", False)

    base = {
        "circuit_number":      circuit_number,
        "panel":               panel,
        "load_classification": load_classification,
        "actual_rating":       actual_rating,
        # Breaker sizes not in 240.6(A) are a model data issue, not a NEC sizing failure —
        # flagging separately lets Claude distinguish data errors from safety failures.
        "is_non_standard":     actual_rating not in STANDARD_SIZES,
    }

    if is_spare:
        return {
            **base,
            "status":          "spare",
            "load_amps":       None,
            "required_amps":   None,
            "required_rating": None,
            "is_oversized":    False,
            "is_zero_load":    False,
            "nec_ref":         None,
            "reason":          "Spare circuit — no connected elements; NEC sizing not applicable.",
        }

    if load_classification in MOTOR_LOAD_TYPES:
        hp = circuit.get("hp")
        if hp and hp > 0:
            return _check_motor_circuit(circuit, base, hp)
        # HP not found on connected equipment — can't apply NEC 430.52.
        return {
            **base,
            "status":          "manual_review",
            "load_amps":       None,
            "required_amps":   None,
            "required_rating": None,
            "is_oversized":    False,
            "is_zero_load":    False,
            "nec_ref":         "NEC 430.52",
            "reason": (
                f"{load_classification} load — no HP value found on connected equipment. "
                "NEC 430.52 sizing requires HP; manual review required."
            ),
        }

    # --- NEC 210.20(A): continuous load ---
    # A circuit supplying a continuous load must have an overcurrent device rated at
    # least 125% of the load current. "Continuous" means load expected to last >= 3 hours.
    # We treat all non-motor circuits as continuous — conservative but correct for
    # lighting and power circuits in commercial/institutional buildings.
    load_va  = circuit["apparent_load_va"]
    voltage  = circuit["voltage"]
    poles    = circuit["poles"]

    # Three-phase current formula: I = VA / (V * √3). For single-phase: I = VA / V.
    phase_factor    = 1.732 if poles == 3 else 1.0
    load_amps       = load_va / (voltage * phase_factor)
    required_amps   = load_amps * 1.25                     # 210.20(A) 125% factor
    required_rating = next_standard_size(required_amps)    # 240.6(A) rounding

    is_zero_load = (load_va == 0)
    is_fail      = actual_rating < required_rating
    is_oversized = actual_rating > required_rating         # protected, but larger than necessary

    if is_zero_load:
        # Circuit has connected elements (not spare) but zero modeled VA — likely missing
        # load data in Revit. The NEC math technically passes (0A → 15A min), but the
        # result is meaningless without real load data.
        reason = (
            f"Zero VA load — circuit has connected elements but no modeled load. "
            "Breaker sizing cannot be meaningfully verified; check model data."
        )
    elif is_fail:
        reason = (
            f"Breaker is {actual_rating}A; NEC 210.20(A) requires {required_rating}A "
            f"for a {load_va:.0f}VA {load_classification.lower()} load at "
            f"{voltage:.0f}V ({poles}-pole). "
            f"Load current is {load_amps:.1f}A; 125% threshold is {required_amps:.1f}A."
        )
    elif is_oversized:
        reason = (
            f"Breaker is {actual_rating}A; minimum per NEC 210.20(A) is {required_rating}A. "
            "Circuit is protected but breaker is larger than required."
        )
    else:
        reason = (
            f"Breaker is {actual_rating}A; NEC 210.20(A) requires {required_rating}A. "
            "Correctly sized."
        )

    return {
        **base,
        "status":          "fail" if is_fail else "pass",
        "load_amps":       round(load_amps, 2),
        "required_amps":   round(required_amps, 2),
        "required_rating": required_rating,
        "is_oversized":    is_oversized,
        "is_zero_load":    is_zero_load,
        "nec_ref":         "NEC 210.20(A)",
        "reason":          reason,
    }
