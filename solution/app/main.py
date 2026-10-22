"""High-temperature conversion-gas equilibrium report.

Usage: python3 /app/main.py <request.json>
"""

import json
import math
import sys
from pathlib import Path

R = 8.31446261815324
NAMES = ["CH4", "H2O", "CO", "CO2", "H2", "N2"]
THERMO_PATH = Path(__file__).with_name("data") / "thermo.json"
REACTIONS = [
    {"nu": [-1.0, -1.0, 1.0, 0.0, 3.0, 0.0]},
    {"nu": [0.0, -1.0, -1.0, 1.0, 1.0, 0.0]},
    {"nu": [0.0, 0.0, 2.0, -1.0, 0.0, 0.0], "solid": -1.0},
]


def load_thermo():
    data = json.loads(THERMO_PATH.read_text(encoding="utf-8"))
    species = data["species"]
    tref = float(data["reference_temperature_k"])
    for reaction in REACTIONS:
        nu = reaction["nu"]
        dh = sum(nu[i] * species[NAMES[i]]["h_f_kj_mol"] for i in range(5)) * 1000.0
        ds = sum(nu[i] * species[NAMES[i]]["s_j_mol_k"] for i in range(5))
        dcp = sum(nu[i] * species[NAMES[i]]["cp_j_mol_k"] for i in range(5))
        if "solid" in reaction:
            solid = reaction["solid"]
            dh += solid * species["C"]["h_f_kj_mol"] * 1000.0
            ds += solid * species["C"]["s_j_mol_k"]
            dcp += solid * species["C"]["cp_j_mol_k"]
        reaction["dh"] = dh
        reaction["ds"] = ds
        reaction["dcp"] = dcp
    return data, species, tref


THERMO, SPECIES, TREF = load_thermo()


def reaction_ln_k(index, temperature):
    reaction = REACTIONS[index]
    dh = reaction["dh"] + reaction["dcp"] * (temperature - TREF)
    ds = reaction["ds"] + reaction["dcp"] * math.log(temperature / TREF)
    return -dh / (R * temperature) + ds / R


def gas_moles(feed, extent_1, extent_2, solid):
    methane = feed["CH4"] - extent_1
    steam = feed["H2O"] - extent_1 - extent_2
    carbon_monoxide = feed["CO"] + extent_1 - extent_2 - 2.0 * solid
    carbon_dioxide = feed["CO2"] + extent_2 + solid
    hydrogen = feed["H2"] + 3.0 * extent_1 + extent_2
    return [
        methane,
        steam,
        carbon_monoxide,
        carbon_dioxide,
        hydrogen,
        feed["N2"],
    ]


def homogeneous_residuals(feed, temperature, pressure_bar, x1, x2, solid):
    moles = gas_moles(feed, x1, x2, solid)
    total = sum(moles)
    if min(moles) <= 0.0:
        return None
    y = [value / total for value in moles]
    pressure_log = 2.0 * math.log(pressure_bar)
    reforming = (
        math.log(y[2] * y[4] ** 3 / (y[0] * y[1]))
        + pressure_log
        - reaction_ln_k(0, temperature)
    )
    water_gas_shift = (
        math.log(y[3] * y[4] / (y[2] * y[1]))
        - reaction_ln_k(1, temperature)
    )
    return reforming, water_gas_shift


def solve_shift_extent(feed, temperature, pressure_bar, x1, solid):
    span = max(feed.values())
    lower = max(-feed["CO2"] - solid, -feed["H2"] - 3.0 * x1)
    upper = min(feed["H2O"] - x1, feed["CO"] + x1 - 2.0 * solid)
    eps = span * 1.0e-12
    lower += eps
    upper -= eps
    if lower >= upper:
        return None
    left = homogeneous_residuals(feed, temperature, pressure_bar, x1, lower, solid)
    right = homogeneous_residuals(feed, temperature, pressure_bar, x1, upper, solid)
    if left is None or right is None or left[1] * right[1] > 0.0:
        return None
    for _ in range(90):
        middle = 0.5 * (lower + upper)
        value = homogeneous_residuals(feed, temperature, pressure_bar, x1, middle, solid)
        if value is None:
            return None
        if value[1] < 0.0:
            lower = middle
        else:
            upper = middle
    x2 = 0.5 * (lower + upper)
    result = homogeneous_residuals(feed, temperature, pressure_bar, x1, x2, solid)
    if result is None:
        return None
    return x2, result[0]


def solve_extents(feed, temperature, pressure_bar, solid):
    span = max(feed.values())
    upper = feed["CH4"] - span * 1.0e-10
    lower = -span
    previous = None
    bracket = None
    for index in range(601):
        x1 = lower + (upper - lower) * index / 600.0
        value = solve_shift_extent(feed, temperature, pressure_bar, x1, solid)
        if value is None:
            previous = None
            continue
        current = (x1, value[1])
        if previous is not None and current[1] * previous[1] <= 0.0:
            bracket = (previous[0], current[0])
            break
        previous = current
    if bracket is None:
        raise ValueError("equilibrium extents are not bounded")
    left, right = bracket
    for _ in range(90):
        middle = 0.5 * (left + right)
        value = solve_shift_extent(feed, temperature, pressure_bar, middle, solid)
        if value is None:
            raise ValueError("equilibrium search left the valid region")
        if value[1] < 0.0:
            left = middle
        else:
            right = middle
    x1 = 0.5 * (left + right)
    value = solve_shift_extent(feed, temperature, pressure_bar, x1, solid)
    if value is None:
        raise ValueError("equilibrium search did not converge")
    return x1, value[0]


def carbon_drive(feed, temperature, pressure_bar, x1, x2, solid):
    moles = gas_moles(feed, x1, x2, solid)
    total = sum(moles)
    if min(moles) <= 0.0:
        return None
    drive = (
        math.log(moles[2] ** 2 / (moles[3] * total))
        + math.log(pressure_bar)
        - reaction_ln_k(2, temperature)
    )
    return drive


def settle_solid_carbon(feed, temperature, pressure_bar):
    base_extents = solve_extents(feed, temperature, pressure_bar, 0.0)
    base_drive = carbon_drive(feed, temperature, pressure_bar, *base_extents, 0.0)
    if base_drive is None or base_drive <= 0.0:
        return base_extents[0], base_extents[1], 0.0

    carbon_total = feed["CH4"] + feed["CO"] + feed["CO2"]
    upper_limit = carbon_total * 0.8
    previous = (0.0, base_drive)
    bracket = None
    for index in range(1, 241):
        solid = upper_limit * index / 240.0
        try:
            extents = solve_extents(feed, temperature, pressure_bar, solid)
        except ValueError:
            previous = None
            continue
        drive = carbon_drive(feed, temperature, pressure_bar, *extents, solid)
        if drive is None:
            previous = None
            continue
        if drive <= 0.0:
            if previous is not None:
                bracket = (previous[0], solid)
                break
            raise ValueError("solid-carbon boundary is not bracketed")
        previous = (solid, drive)
    if bracket is None:
        raise ValueError("solid-carbon boundary is not bounded")

    lower, upper = bracket
    for _ in range(80):
        middle = 0.5 * (lower + upper)
        extents = solve_extents(feed, temperature, pressure_bar, middle)
        drive = carbon_drive(feed, temperature, pressure_bar, *extents, middle)
        if drive is None:
            raise ValueError("solid-carbon search left the valid region")
        if drive > 0.0:
            lower = middle
        else:
            upper = middle
    solid = 0.5 * (lower + upper)
    extents = solve_extents(feed, temperature, pressure_bar, solid)
    return extents[0], extents[1], solid


def solve_equilibrium(feed, temperature, pressure_bar):
    return settle_solid_carbon(feed, temperature, pressure_bar)


def feed_enthalpy(feed, temperature):
    return sum(
        feed[name] * (SPECIES[name]["h_f_kj_mol"] * 1000.0
                      + SPECIES[name]["cp_j_mol_k"] * (temperature - TREF))
        for name in NAMES
    )


def product_enthalpy(feed, temperature, moles, solid):
    formation = sum(moles[i] * SPECIES[NAMES[i]]["h_f_kj_mol"] * 1000.0 for i in range(6))
    sensible = sum(
        moles[i] * SPECIES[NAMES[i]]["cp_j_mol_k"] * (temperature - TREF)
        for i in range(6)
    )
    solid_sensible = solid * SPECIES["C"]["cp_j_mol_k"] * (temperature - TREF)
    return formation + sensible + solid_sensible


def adiabatic_temperature(feed, inlet_temperature, pressure_bar):
    inlet_h = feed_enthalpy(feed, inlet_temperature)

    def energy_residual(temperature):
        x1, x2, solid = solve_equilibrium(feed, temperature, pressure_bar)
        moles = gas_moles(feed, x1, x2, solid)
        return product_enthalpy(feed, temperature, moles, solid) - inlet_h

    lower, upper = 500.0, 1500.0
    left = energy_residual(lower)
    right = energy_residual(upper)
    if left * right > 0.0:
        raise ValueError("adiabatic temperature is not bounded")
    for _ in range(70):
        middle = 0.5 * (lower + upper)
        if energy_residual(middle) < 0.0:
            lower = middle
        else:
            upper = middle
    return 0.5 * (lower + upper)


def validate(request):
    if request.get("mode") not in {"isothermal", "adiabatic"}:
        raise ValueError("unsupported mode")
    pressure = request.get("pressure_bar")
    if not isinstance(pressure, (int, float)) or pressure <= 0.0:
        raise ValueError("pressure must be positive")
    feed = request.get("feed_mol")
    if not isinstance(feed, dict) or set(feed) != set(NAMES):
        raise ValueError("feed_mol has the wrong species")
    values = {}
    for name in NAMES:
        value = feed[name]
        if not isinstance(value, (int, float)) or value < 0.0:
            raise ValueError("feed amounts must be non-negative")
        values[name] = float(value)
    if sum(values.values()) <= 0.0:
        raise ValueError("feed is empty")
    return request["mode"], float(pressure), values


def build_report(request):
    mode, pressure, feed = validate(request)
    if mode == "isothermal":
        temperature = request.get("temperature_k")
        if not isinstance(temperature, (int, float)) or temperature <= 0.0:
            raise ValueError("temperature must be positive")
        temperature = float(temperature)
    else:
        inlet = request.get("inlet_temperature_k")
        if not isinstance(inlet, (int, float)) or inlet <= 0.0:
            raise ValueError("inlet temperature must be positive")
        temperature = adiabatic_temperature(feed, float(inlet), pressure)
    x1, x2, solid = solve_equilibrium(feed, temperature, pressure)
    moles = gas_moles(feed, x1, x2, solid)
    total = sum(moles)
    fractions = {NAMES[i]: moles[i] / total for i in range(6)}
    return {
        "temperature_k": temperature,
        "gas_mol": {NAMES[i]: moles[i] for i in range(6)},
        "gas_mole_fractions": fractions,
        "solid_carbon_mol": solid,
    }


def main(argv):
    if len(argv) != 2:
        print("usage: python3 /app/main.py <request.json>", file=sys.stderr)
        return 2
    try:
        request = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        report = build_report(request)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
