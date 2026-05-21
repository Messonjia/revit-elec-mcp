# NEC 210.20(A) and NEC 240.6(A) encoded as pure Python.
# No Revit, no MCP, no WebSocket — takes circuit dicts, returns compliance result dicts.
# All pass/fail determinations happen here so Claude's role is explanation, not computation.

# NEC 240.6(A) standard ampere ratings for fixed-trip breakers through 200A.
# Values above 200A exist in the code but are uncommon in the panel types this tool targets.
STANDARD_SIZES = [15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 125, 150, 175, 200]

# Load classifications that fall under NEC 430/440 — the 125% rule does NOT apply.
# Motor starting inrush current intentionally allows larger breakers (up to 250% of FLC).
MOTOR_LOAD_TYPES = {"Motor", "HVAC"}


def next_standard_size(amps: float) -> int:
    """Return the smallest standard breaker size >= amps per NEC 240.6(A).

    Edge cases:
    - Exactly on a standard size (e.g. 20.0) returns that size, not the next one.
    - Above 200A returns 200; caller should flag circuits needing sizes above this table.
    """
    for size in STANDARD_SIZES:
        if size >= amps:
            return size
    return STANDARD_SIZES[-1]


def check_circuit(circuit: dict) -> dict:
    """Apply NEC 210.20(A) to one circuit dict and return a structured compliance result.

    Input keys (matching the schema returned by CircuitQueryHandler):
        circuit_number, panel, apparent_load_va, voltage, poles,
        breaker_rating, load_classification, is_spare

    Status values in the returned dict:
        "spare"         — no connected elements; sizing not applicable
        "manual_review" — motor/HVAC load; NEC 430/440 governs instead
        "pass"          — breaker meets NEC 210.20(A)
        "fail"          — breaker is undersized; dangerous
    """
    circuit_number     = circuit["circuit_number"]
    panel              = circuit["panel"]
    load_classification = circuit["load_classification"]
    actual_rating      = circuit["breaker_rating"]
    is_spare           = circuit.get("is_spare", False)

    # Fields that go into every result regardless of path.
    base = {
        "circuit_number":    circuit_number,
        "panel":             panel,
        "load_classification": load_classification,
        "actual_rating":     actual_rating,
        # Breaker sizes not in 240.6(A) are a model data issue, not a NEC sizing failure —
        # flagging separately lets Claude distinguish data errors from safety failures.
        "is_non_standard":   actual_rating not in STANDARD_SIZES,
    }

    if is_spare:
        return {
            **base,
            "status":          "spare",
            "load_amps":       None,
            "required_amps":   None,
            "required_rating": None,
            "is_oversized":    False,
            "nec_ref":         None,
            "reason":          "Spare circuit — no connected elements; NEC sizing not applicable.",
        }

    if load_classification in MOTOR_LOAD_TYPES:
        return {
            **base,
            "status":          "manual_review",
            "load_amps":       None,
            "required_amps":   None,
            "required_rating": None,
            "is_oversized":    False,
            "nec_ref":         "NEC 430/440",
            "reason": (
                f"{load_classification} load — NEC 430/440 governs overcurrent protection "
                "for motor circuits; the 125% continuous-load rule does not apply. "
                "Manual review required."
            ),
        }

    # --- NEC 210.20(A): continuous load ---
    # A circuit supplying a continuous load must have an overcurrent device rated at
    # least 125% of the load current. "Continuous" means load expected to last >= 3 hours.
    # We treat all circuits from the Revit model as continuous — conservative but correct
    # for lighting and power circuits in commercial/institutional buildings.
    load_va  = circuit["apparent_load_va"]
    voltage  = circuit["voltage"]
    poles    = circuit["poles"]

    # Three-phase current formula: I = VA / (V * √3). For single-phase: I = VA / V.
    phase_factor  = 1.732 if poles == 3 else 1.0
    load_amps     = load_va / (voltage * phase_factor)
    required_amps = load_amps * 1.25                      # 210.20(A) 125% factor
    required_rating = next_standard_size(required_amps)   # 240.6(A) rounding

    is_fail      = actual_rating < required_rating
    is_oversized = actual_rating > required_rating        # protected, but larger than necessary

    if is_fail:
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
        "nec_ref":         "NEC 210.20(A)",
        "reason":          reason,
    }
