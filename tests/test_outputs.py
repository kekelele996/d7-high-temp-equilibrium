"""Pilot-reactor calibration and equilibrium prediction acceptance tests."""

import json
import os
import signal
import subprocess
import tempfile
from pathlib import Path

ENTRY = "/app/main.py"
PYTHON = "/usr/local/bin/python3"
CANDIDATE_USER = "runner"
CANDIDATE_ENV = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "HOME": "/home/runner",
    "LANG": "C.UTF-8",
    "TZ": "UTC",
}
CALL_TIMEOUT_SEC = 180
FIXTURES = Path(__file__).with_name("fixtures")
EXPECTED = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
PARAM_TOL = 1.0e-2
CP_TOL = 5.0e-3
ENTROPY_TOL = 0.2
FRACTION_TOL = 2.0e-5
TEMPERATURE_TOL = 0.5
CARBON_TOL = 2.0e-3


def run_candidate(*args, timeout=CALL_TIMEOUT_SEC):
    as_root = os.getuid() == 0
    proc = subprocess.Popen(
        [PYTHON, ENTRY, *[str(a) for a in args]],
        cwd="/app",
        env=CANDIDATE_ENV,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        user=CANDIDATE_USER if as_root else None,
        group=CANDIDATE_USER if as_root else None,
        extra_groups=[] if as_root else None,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise TimeoutError(f"{ENTRY} 超过 {timeout}s")
    return subprocess.CompletedProcess(proc.args, proc.returncode, out, err)


def run_bundle(name):
    source = FIXTURES / f"{name}.json"
    folder = Path(tempfile.mkdtemp(prefix="calibration-"))
    folder.chmod(0o755)
    case = folder / "request.json"
    case.write_bytes(source.read_bytes())
    case.chmod(0o644)
    proc = run_candidate(case)
    assert proc.returncode == 0, f"exit={proc.returncode} stderr={proc.stderr[-500:]}"
    return json.loads(proc.stdout)


def test_prints_exact_calibration_and_prediction_fields():
    """「输出对象只含 `calibration` 和 `predictions` 两个字段」「`calibration` 只含三个字段」「`predictions` 固定含 `pressure`、`energy`、`carbon` 三个字段」"""
    got = run_bundle("bundle-a")
    assert set(got) == {"calibration", "predictions"}
    assert set(got["calibration"]) == {
        "pressure_exponent", "heat_capacity_scale", "carbon_entropy_shift_j_mol_k"
    }
    assert set(got["predictions"]) == {"pressure", "energy", "carbon"}


def test_wrong_argument_count_exits_2():
    """「参数个数不对时退出码为 2，不输出 JSON」"""
    proc = run_candidate()
    assert proc.returncode == 2
    assert proc.stdout.strip() == ""


def test_bundle_a_recovers_pressure_behavior():
    """「压力系数用于还原高压运行中的气相平衡组成」「运行记录来自现场，不能删除或改写原始条目」"""
    got = run_bundle("bundle-a")
    assert abs(got["calibration"]["pressure_exponent"] - EXPECTED["bundle-a"]["pressure_exponent"]) <= PARAM_TOL
    fractions = got["predictions"]["pressure"]["gas_mole_fractions"]
    assert abs(fractions["CH4"] - EXPECTED["bundle-a"]["pressure_ch4_fraction"]) <= FRACTION_TOL
    assert abs(fractions["H2"] - EXPECTED["bundle-a"]["pressure_h2_fraction"]) <= FRACTION_TOL


def test_bundle_b_recovers_pressure_behavior():
    """「压力系数用于还原高压运行中的气相平衡组成」"""
    got = run_bundle("bundle-b")
    assert abs(got["calibration"]["pressure_exponent"] - EXPECTED["bundle-b"]["pressure_exponent"]) <= PARAM_TOL
    fractions = got["predictions"]["pressure"]["gas_mole_fractions"]
    assert abs(fractions["CH4"] - EXPECTED["bundle-b"]["pressure_ch4_fraction"]) <= FRACTION_TOL
    assert abs(fractions["H2"] - EXPECTED["bundle-b"]["pressure_h2_fraction"]) <= FRACTION_TOL


def test_bundle_c_recovers_pressure_behavior():
    """「压力系数用于还原高压运行中的气相平衡组成」"""
    got = run_bundle("bundle-c")
    assert abs(got["calibration"]["pressure_exponent"] - EXPECTED["bundle-c"]["pressure_exponent"]) <= PARAM_TOL
    fractions = got["predictions"]["pressure"]["gas_mole_fractions"]
    assert abs(fractions["CH4"] - EXPECTED["bundle-c"]["pressure_ch4_fraction"]) <= FRACTION_TOL
    assert abs(fractions["H2"] - EXPECTED["bundle-c"]["pressure_h2_fraction"]) <= FRACTION_TOL


def test_bundle_a_recovers_heat_capacity_scale():
    """「产物热容系数用于还原绝热出口温度」「绝热工况的出口温度必须使产物总焓等于进料总焓」"""
    got = run_bundle("bundle-a")
    assert abs(got["calibration"]["heat_capacity_scale"] - EXPECTED["bundle-a"]["heat_capacity_scale"]) <= CP_TOL
    assert abs(got["predictions"]["energy"]["temperature_k"] - EXPECTED["bundle-a"]["energy_temperature_k"]) <= TEMPERATURE_TOL


def test_bundle_b_recovers_heat_capacity_scale():
    """「产物热容系数用于还原绝热出口温度」「绝热工况的出口温度必须使产物总焓等于进料总焓」"""
    got = run_bundle("bundle-b")
    assert abs(got["calibration"]["heat_capacity_scale"] - EXPECTED["bundle-b"]["heat_capacity_scale"]) <= CP_TOL
    assert abs(got["predictions"]["energy"]["temperature_k"] - EXPECTED["bundle-b"]["energy_temperature_k"]) <= TEMPERATURE_TOL


def test_bundle_c_recovers_heat_capacity_scale():
    """「产物热容系数用于还原绝热出口温度」「绝热工况的出口温度必须使产物总焓等于进料总焓」"""
    got = run_bundle("bundle-c")
    assert abs(got["calibration"]["heat_capacity_scale"] - EXPECTED["bundle-c"]["heat_capacity_scale"]) <= CP_TOL
    assert abs(got["predictions"]["energy"]["temperature_k"] - EXPECTED["bundle-c"]["energy_temperature_k"]) <= TEMPERATURE_TOL


def test_bundle_a_recovers_carbon_boundary():
    """「固碳项必须与实测固碳量和气相组成同时一致」「固碳按活度为 1 的纯固相处理」"""
    got = run_bundle("bundle-a")
    assert abs(got["calibration"]["carbon_entropy_shift_j_mol_k"] - EXPECTED["bundle-a"]["carbon_entropy_shift_j_mol_k"]) <= ENTROPY_TOL
    assert abs(got["predictions"]["carbon"]["solid_carbon_mol"] - EXPECTED["bundle-a"]["carbon_solid_mol"]) <= CARBON_TOL


def test_bundle_b_recovers_carbon_boundary():
    """「固碳项必须与实测固碳量和气相组成同时一致」「固碳按活度为 1 的纯固相处理」"""
    got = run_bundle("bundle-b")
    assert abs(got["calibration"]["carbon_entropy_shift_j_mol_k"] - EXPECTED["bundle-b"]["carbon_entropy_shift_j_mol_k"]) <= ENTROPY_TOL
    assert abs(got["predictions"]["carbon"]["solid_carbon_mol"] - EXPECTED["bundle-b"]["carbon_solid_mol"]) <= CARBON_TOL


def test_bundle_c_recovers_carbon_boundary():
    """「固碳项必须与实测固碳量和气相组成同时一致」「固碳按活度为 1 的纯固相处理」"""
    got = run_bundle("bundle-c")
    assert abs(got["calibration"]["carbon_entropy_shift_j_mol_k"] - EXPECTED["bundle-c"]["carbon_entropy_shift_j_mol_k"]) <= ENTROPY_TOL
    assert abs(got["predictions"]["carbon"]["solid_carbon_mol"] - EXPECTED["bundle-c"]["carbon_solid_mol"]) <= CARBON_TOL
