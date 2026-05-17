# Data Layer Fixes — What Went Wrong and Why

After the first real test of `check_breaker_sizing` against panels `EL1` and `HDP`,
four bugs surfaced in the data returned from the Revit add-in. None were logic errors
in the NEC analysis — they were all mistakes in *how we read Revit data*. This document
explains each one as a concept, not just as a fix.

---

## Lesson 1 — Revit internal units are not display units

### What we saw

Every circuit returned `"voltage": 2238.893...` regardless of panel. That number is
not a real distribution voltage (208 V, 480 V, etc.) and it was identical across panels
that are almost certainly on different services.

`apparent_load_va` had the same problem: circuits that should have had load returned 0,
and any non-zero values were implausible.

### Why it happens

Revit stores every quantity that has a physical unit — lengths, areas, loads, voltages —
in a fixed *internal unit system* that is independent of what the project displays.
For example:

- Length is stored in **decimal feet** internally, even if the project shows millimetres.
- Electrical voltage is stored in an internal electrical-potential unit (not the volt you'd expect).
- Apparent load is stored in an internal power unit (not VA).

The raw values from `sys.Voltage` and `sys.ApparentLoad` are in these internal units.
Reading them without conversion gives you a physically meaningless number.

### The fix

Revit provides `UnitUtils.ConvertFromInternalUnits(value, UnitTypeId.X)` for exactly this:

```csharp
double volts  = UnitUtils.ConvertFromInternalUnits(sys.Voltage,       UnitTypeId.Volts);
double loadVA = UnitUtils.ConvertFromInternalUnits(sys.ApparentLoad,  UnitTypeId.VoltAmperes);
```

`UnitTypeId` is an enum of every unit Revit knows about. You always pair the
internal value with the `UnitTypeId` that describes what you want back.

### The rule to remember

**Any `double` property on a Revit element that has a physical unit is in internal units.**
Always convert before returning it to a user or an LLM. The only safe exceptions are
dimensionless values (counts, booleans, indices).

---

## Lesson 2 — Revit parameters have a `StorageType`; not all of them are strings

### What we saw

`load_classification` returned `"Unknown"` on every single circuit across both panels.
No project has 100% of its circuits unclassified.

### Why it happens

Revit parameters are not all strings. Each parameter has a `StorageType` that controls
which `As*()` method you must use to read it:

| StorageType    | Read with      | Example values                     |
|----------------|----------------|------------------------------------|
| `String`       | `AsString()`   | Names, descriptions                |
| `Double`       | `AsDouble()`   | Loads, lengths (in internal units) |
| `Integer`      | `AsInteger()`  | Pole count, booleans               |
| `ElementId`    | `AsElementId()`| References to other elements       |

`RBS_ELEC_LOAD_CLASSIFICATION` has `StorageType.ElementId`. It stores a *reference*
to a `LoadClassification` element in the project — not the name itself. When you call
`AsString()` on an `ElementId`-typed parameter, Revit returns `null`. Our code then
fell through to the `?? "Unknown"` default every time.

### The fix

Check `StorageType` first, then call the matching `As*()` method:

```csharp
var lcParam   = sys.get_Parameter(BuiltInParameter.RBS_ELEC_LOAD_CLASSIFICATION);
string lcName = "Unknown";
if (lcParam?.StorageType == StorageType.ElementId)
    lcName = doc.GetElement(lcParam.AsElementId())?.Name ?? "Unknown";
else if (lcParam?.StorageType == StorageType.String)
    lcName = lcParam.AsString() ?? "Unknown";
```

`doc.GetElement(id)` resolves the reference to the actual `LoadClassification` element,
and `.Name` gives the human-readable string ("Lighting", "Power", "Motor", etc.).

### The rule to remember

**Before calling `AsString()` on an unfamiliar parameter, check its `StorageType`.**
`ElementId`-typed parameters store *references*, not text. The actual value is in another
element you have to look up.

---

## Lesson 3 — Zero load can mean two different things; you have to distinguish them

### What we saw

`EL1` returned both circuits with `apparent_load_va: 0`. Panel `HDP` had a 200 A
breaker circuit also at zero VA. It was impossible to tell whether these were
legitimate spare slots or active feeders with a model data problem.

### Why it matters

The NEC sizing formula breaks down at zero load: you can't calculate `load_amps =
VA / voltage` and then check if the breaker is appropriately sized. A spare slot
*should* be zero; an active feeder *should not* be. Treating them the same either
produces nonsense results or silently skips real problems.

### The fix

`ElectricalSystem` inherits from `MEPSystem`, which has an `Elements` property —
a collection of all Revit elements connected to that circuit. If `Elements.Size == 0`,
nothing is wired to it: it's a spare or space.

```csharp
is_spare = sys.Elements.Size == 0,
```

Adding this field to the JSON response lets the LLM (or any downstream logic)
skip spare circuits cleanly, and flag zero-load *non-spare* circuits as a potential
model data problem worth reviewing.

### The rule to remember

**Model validity and data validity are different.** A zero-VA circuit is structurally
valid in Revit (it just means nothing is connected). The question of whether that's
intentional (spare) or a mistake (disconnected feeder) requires reading a second piece
of data — `Elements.Size` — not just the load value.

---

## Lesson 4 — `OST_ElectricalEquipment` vs `OST_ElectricalFixtures`

### What we saw

There was no way to enumerate panels. `query_elements` returned 481 fixtures (receptacles,
luminaires, HRU connections, etc.) but no panels, so the user had to know panel names in
advance to call `check_breaker_sizing`.

### Why it happens (and why it's easy to miss)

Revit has two different categories that are both "electrical":

| Category | BuiltInCategory | Contains |
|---|---|---|
| Electrical Fixtures | `OST_ElectricalFixtures` | Devices wired *to* a circuit: receptacles, luminaires, HRU connections |
| Electrical Equipment | `OST_ElectricalEquipment` | Distribution equipment: panels, switchboards, MCCs, transformers |

`query_elements` uses `OST_ElectricalFixtures`, which is correct for listing connected
devices. But panels are `OST_ElectricalEquipment`. Neither category contains the other.

### The fix

A new `list_panels` tool using a `FilteredElementCollector` with `OST_ElectricalEquipment`:

```csharp
new FilteredElementCollector(doc)
    .OfCategory(BuiltInCategory.OST_ElectricalEquipment)
    .WhereElementIsNotElementType()
    .ToElements()
```

This returns the panels themselves, which have names like `"EL1"` and `"HDP"` — exactly
what `check_breaker_sizing` expects as its `panel` argument.

### The rule to remember

**In Revit, "electrical" splits into at least two categories.** Equipment = the sources
and distribution points. Fixtures = the loads connected to them. When a query returns
nothing or the wrong things, checking the `BuiltInCategory` is often the first thing to verify.

---

## Why these bugs all appeared together

All four bugs share a root cause: **we wrote code that compiled and ran without errors,
but produced wrong output**. Revit's API doesn't throw exceptions for unit-conversion
mistakes, `AsString()` on an ElementId parameter, or querying the wrong category. It
just quietly returns the wrong value. The only way to catch this class of bug is to
run the tool against a real model and check whether the output makes physical sense —
which is exactly what the first real test did.

This is a general pattern in Revit API development: the API is very permissive. Treat
every returned value with the question "does this number make sense for what I'm measuring?"
