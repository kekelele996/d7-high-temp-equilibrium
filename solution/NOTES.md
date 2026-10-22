# 参考解说明

## 三个难点

| 编号 | 错误认知 | 正确知识 | 可观察行为 | 对应测试 |
|---|---|---|---|---|
| difficulty_1 | 把由标准 Gibbs 能得到的平衡常数直接当作摩尔分数商，忽略总压和反应净摩尔数变化 | 每个独立反应都要使用以 1 bar 为标准态的无量纲分压商；甲烷重整的净气相摩尔数变化为 2 | 高压下 CH4、H2O、CO、H2 的平衡摩尔分数偏离独立解 | `test_high_pressure_case_a_*`、`test_high_pressure_case_b_*`、`test_high_pressure_case_c_*` |
| difficulty_2 | 绝热温升用进料混合物的平均热容统一代表产物显焓 | 产物总焓要逐物种使用各自的定压热容，并与随温度变化的平衡组成联立 | 绝热出口温度偏差超过最终容差 | `test_adiabatic_case_a_*`、`test_adiabatic_case_b_*`、`test_adiabatic_case_c_*` |
| difficulty_3 | 先求无固碳气相，再单独沿 Boudouard 反应估算固碳量 | 固碳量是第三个未知量，要与两组均相反应同时求解；有固碳时固相活度为 1，无固碳时饱和度不得超过 1 | 富碳工况的固碳量和气相摩尔分数均偏离独立解 | `test_carbon_case_a_*`、`test_carbon_case_b_*`、`test_carbon_case_c_*` |

## 数学模型

气相物种为 CH4、H2O、CO、CO2、H2、N2。独立均相反应取：

1. CH4 + H2O = CO + 3 H2
2. CO + H2O = CO2 + H2

固相出现时增加：

3. C(s) + CO2 = 2 CO

平衡常数由 `/app/data/thermo.json` 的 `h_f`、`s` 和 `cp` 计算。因为数据表采用定压热容，反应焓和反应熵按
`dH(T)=dH(Tref)+dCp(T-Tref)`、`dS(T)=dS(Tref)+dCp ln(T/Tref)` 修正。以总摩尔数为基准，把分压商化为摩尔数之比、总摩尔数和 1 bar 标准压力项。

无固碳时，两个反应进度 `x1`、`x2` 由两个质量作用方程确定。固碳出现时，第三个未知量 `x3` 同时进入碳、氢、氧元素衡算和 Boudouard 平衡。参考实现先检查无固碳解，再在可行域内寻找饱和度变号区间并二分。这个路径保证 `x3 >= 0`，且没有固碳时不会把亚饱和气相误判成析碳。

绝热温度按产物总焓等于进料总焓求解：

`sum_i n_i [h_f,i + cp_i(T-Tref)] + n_C cp_C(T-Tref) = sum_j n_feed,j [h_f,j + cp_j(Tin-Tref)]`

每个候选温度都重新求一次平衡组成，再用 500–1500 K 内的二分法定位能量残差零点。

## 独立复算

- 解析与高精度复算：`research/derivations.md` 和 `research/verify_equilibrium.py`。
- 测试期望值在 `tests/test_outputs.py` 中固定为十进制常数，不从参考解读取。
- 最终还会用另一套 Gibbs 最小化路径核对质量作用方程结果。

## 容差依据

- 组成容差 `2e-5`：参考实现的摩尔分数在不同起始区间下稳定到约 `1e-10`，典型错误口径造成 `1e-3` 到 `1e-1` 的偏差。
- 温度容差 `0.5 K`：平衡和能量二分均收敛到远小于该值；进料平均热容近似在三个隐藏工况造成 `0.68–3.47 K` 偏差。
- 固碳容差 `5e-4 mol`：数值二分稳定到约 `1e-10 mol`；另一条近似路径造成 `0.02–0.24 mol` 偏差。

## 权重依据

- gate 不计分：只检查输出结构和参数错误，不检查化学结果。
- difficulty_1 合计 `0.40`：高压组成是主交付结果，三种不同压力与进料共同覆盖。
- difficulty_2 合计 `0.30`：绝热温度是独立能量衡算结果，三种产物热容组成防止只对一个样例调参。
- difficulty_3 合计 `0.30`：固碳量与气相组成由同一相平衡闭合，三个温度覆盖不同析碳强度。

## 数据来源

- `/app/data/thermo.json` 采用 NIST/JANAF 298.15 K 标准生成焓、标准熵和定压热容的工程舍入值，用于题目内部自洽计算。
- 详细引用、表号和适用条件见 `research/sources.md`、`research/claims.json`。
- 不使用生产数据。全部验收工况由研究脚本生成，生成规则见 `research/data-notes.md`。

## 答案隔离

- [x] 镜像内没有 `tests/`、`solution/`、`.git/`、缓存和备份
- [x] 题面只给输入输出契约和化学守恒要求，不给修法
- [x] Dockerfile 没有先复制正确版本再改坏
