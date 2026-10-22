"""高温转化气平衡报告的验收测试。

测试输入在临时目录中生成。期望值来自 research/ 中的独立复核记录，不从
solution/ 或候选输出生成。候选程序始终以 runner 身份运行。
"""

import json
import math
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
CALL_TIMEOUT_SEC = 120
NAMES = ["CH4", "H2O", "CO", "CO2", "H2", "N2"]
FRACTION_TOL = 2.0e-5
TEMPERATURE_TOL = 0.5
CARBON_TOL = 5.0e-4


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


def report(request):
    folder = Path(tempfile.mkdtemp(prefix="equilibrium-"))
    folder.chmod(0o755)
    case = folder / "request.json"
    case.write_text(json.dumps(request), encoding="utf-8")
    case.chmod(0o644)
    proc = run_candidate(case)
    assert proc.returncode == 0, f"exit={proc.returncode} stderr={proc.stderr[-500:]}"
    return json.loads(proc.stdout)


def request(mode, pressure, feed, temperature=None, inlet=None):
    payload = {"mode": mode, "pressure_bar": pressure, "feed_mol": feed}
    if temperature is not None:
        payload["temperature_k"] = temperature
    if inlet is not None:
        payload["inlet_temperature_k"] = inlet
    return payload


CASE_D1_A = request(
    "isothermal", 30.0,
    {"CH4": 0.18, "H2O": 0.24, "CO": 0.08, "CO2": 0.02, "H2": 0.03, "N2": 0.45},
    temperature=1100.0,
)
D1_A = {"CH4": 0.0584223050, "H2O": 0.0932638607, "CO": 0.1406611052,
        "CO2": 0.0308551860, "H2": 0.3072533707, "N2": 0.3695441724}

CASE_D1_B = request(
    "isothermal", 50.0,
    {"CH4": 0.20, "H2O": 0.30, "CO": 0.05, "CO2": 0.03, "H2": 0.02, "N2": 0.40},
    temperature=1000.0,
)
D1_B = {"CH4": 0.1312515852, "H2O": 0.1868862792, "CO": 0.0596513055,
        "CO2": 0.0615977433, "H2": 0.1998978952, "N2": 0.3607151916}

CASE_D1_C = request(
    "isothermal", 20.0,
    {"CH4": 0.25, "H2O": 0.35, "CO": 0.03, "CO2": 0.02, "H2": 0.02, "N2": 0.33},
    temperature=1000.0,
)
D1_C = {"CH4": 0.1184814176, "H2O": 0.1691038203, "CO": 0.0805765253,
        "CO2": 0.0483346241, "H2": 0.3113717888, "N2": 0.2721318238}

CASE_D2_A = request(
    "adiabatic", 1.0,
    {"CH4": 0.02, "H2O": 0.32, "CO": 0.22, "CO2": 0.04, "H2": 0.03, "N2": 0.37},
    inlet=700.0,
)
CASE_D2_B = request(
    "adiabatic", 1.0,
    {"CH4": 0.01, "H2O": 0.34, "CO": 0.30, "CO2": 0.02, "H2": 0.02, "N2": 0.31},
    inlet=700.0,
)
CASE_D2_C = request(
    "adiabatic", 1.0,
    {"CH4": 0.04, "H2O": 0.30, "CO": 0.25, "CO2": 0.03, "H2": 0.04, "N2": 0.34},
    inlet=800.0,
)

CARBON_FEED = {"CH4": 0.45, "H2O": 0.05, "CO": 0.04, "CO2": 0.01, "H2": 0.02, "N2": 0.43}
CASE_D3_A = request("isothermal", 1.0, CARBON_FEED, temperature=650.0)
CASE_D3_B = request("isothermal", 1.0, CARBON_FEED, temperature=700.0)
CASE_D3_C = request("isothermal", 1.0, CARBON_FEED, temperature=800.0)
D3_A_Y = {"CH4": 0.3606940340, "H2O": 0.0979221747, "CO": 0.0003546754,
          "CO2": 0.0041408039, "H2": 0.1203416131, "N2": 0.4165466989}
D3_B_Y = {"CH4": 0.3070535656, "H2O": 0.0911877004, "CO": 0.0012436567,
          "CO2": 0.0048918179, "H2": 0.1960555600, "N2": 0.3995676994}
D3_C_Y = {"CH4": 0.1758441628, "H2O": 0.0693473898, "CO": 0.0094652567,
          "CO2": 0.0061731871, "H2": 0.3828211041, "N2": 0.3563488994}


def test_prints_json_with_exact_fields():
    """「程序向标准输出写一个 JSON 对象，只含四个字段」"""
    got = report(request("isothermal", 1.0, CARBON_FEED, temperature=1100.0))
    assert set(got) == {"temperature_k", "gas_mol", "gas_mole_fractions", "solid_carbon_mol"}


def test_wrong_argument_count_exits_2():
    """「参数个数不对时退出码为 2，不输出 JSON」"""
    proc = run_candidate()
    assert proc.returncode == 2
    assert proc.stdout.strip() == ""


def test_high_pressure_case_a_keeps_reforming_products():
    """「反应器是封闭系统，碳、氢、氧、氮的元素总量在反应前后保持不变」"""
    got = report(CASE_D1_A)["gas_mole_fractions"]
    assert set(got) == set(NAMES)
    assert abs(got["CH4"] - D1_A["CH4"]) <= FRACTION_TOL
    assert abs(got["H2O"] - D1_A["H2O"]) <= FRACTION_TOL
    assert abs(got["CO"] - D1_A["CO"]) <= FRACTION_TOL
    assert abs(got["H2"] - D1_A["H2"]) <= FRACTION_TOL


def test_high_pressure_case_b_keeps_shift_products():
    """「以 1 bar 为标准压力，所有气相按理想气体处理」"""
    got = report(CASE_D1_B)["gas_mole_fractions"]
    assert abs(got["CH4"] - D1_B["CH4"]) <= FRACTION_TOL
    assert abs(got["H2O"] - D1_B["H2O"]) <= FRACTION_TOL
    assert abs(got["CO"] - D1_B["CO"]) <= FRACTION_TOL
    assert abs(got["H2"] - D1_B["H2"]) <= FRACTION_TOL


def test_high_pressure_case_c_keeps_mole_fractions_normalized():
    """「六项之和为 1」"""
    got = report(CASE_D1_C)["gas_mole_fractions"]
    assert abs(sum(got.values()) - 1.0) <= 1.0e-10
    assert abs(got["CH4"] - D1_C["CH4"]) <= FRACTION_TOL
    assert abs(got["H2O"] - D1_C["H2O"]) <= FRACTION_TOL
    assert abs(got["CO"] - D1_C["CO"]) <= FRACTION_TOL
    assert abs(got["H2"] - D1_C["H2"]) <= FRACTION_TOL


def test_adiabatic_case_a_matches_energy_balance():
    """「绝热工况的出口温度必须使产物总焓等于进料总焓」"""
    got = report(CASE_D2_A)
    assert abs(got["temperature_k"] - 841.6158237) <= TEMPERATURE_TOL


def test_adiabatic_case_b_matches_energy_balance():
    """「绝热工况的出口温度必须使产物总焓等于进料总焓」"""
    got = report(CASE_D2_B)
    assert abs(got["temperature_k"] - 888.4147162) <= TEMPERATURE_TOL


def test_adiabatic_case_c_matches_energy_balance():
    """「绝热工况的出口温度必须使产物总焓等于进料总焓」"""
    got = report(CASE_D2_C)
    assert abs(got["temperature_k"] - 858.3192376) <= TEMPERATURE_TOL


def test_carbon_case_a_releases_solid_carbon():
    """「富碳进料析出固碳后，气相组成仍须满足平衡条件」"""
    got = report(CASE_D3_A)
    assert abs(got["solid_carbon_mol"] - 0.1230158801) <= CARBON_TOL
    assert abs(got["gas_mole_fractions"]["CH4"] - D3_A_Y["CH4"]) <= FRACTION_TOL
    assert abs(got["gas_mole_fractions"]["H2O"] - D3_A_Y["H2O"]) <= FRACTION_TOL
    assert abs(got["gas_mole_fractions"]["H2"] - D3_A_Y["H2"]) <= FRACTION_TOL


def test_carbon_case_b_releases_solid_carbon():
    """「富碳进料析出固碳后，气相组成仍须满足平衡条件」"""
    got = report(CASE_D3_B)
    assert abs(got["solid_carbon_mol"] - 0.1629575226) <= CARBON_TOL


def test_carbon_case_c_releases_solid_carbon():
    """「富碳进料析出固碳后，气相组成仍须满足平衡条件」"""
    got = report(CASE_D3_C)
    assert abs(got["solid_carbon_mol"] - 0.2689412792) <= CARBON_TOL
    assert abs(got["gas_mole_fractions"]["CH4"] - D3_C_Y["CH4"]) <= FRACTION_TOL
    assert abs(got["gas_mole_fractions"]["H2"] - D3_C_Y["H2"]) <= FRACTION_TOL
    assert abs(got["gas_mole_fractions"]["N2"] - D3_C_Y["N2"]) <= FRACTION_TOL
