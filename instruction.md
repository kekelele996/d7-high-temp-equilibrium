# 高温转化气模型标定

中试反应器的出口气分析仪刚完成检修。工艺组要根据最近几轮运行记录，标定反应器的三个有效模型系数，再用标定后的模型预测下一班的三组工况。

## 要交付的内容

修好 `/app/main.py`。用法是 `python3 /app/main.py <输入文件>`。输入文件是一个 JSON 对象，含 `calibration_runs` 和 `targets` 两部分。

`calibration_runs` 是一个非空数组。每个元素按 `kind` 分三类：

三类运行都用同一套物种顺序。字段如下：

```text
pressure: pressure_bar, temperature_k, feed_mol, gas_mol, solid_carbon_mol
energy: inlet_temperature_k, feed_mol, outlet_temperature_k, outlet_gas_mol
carbon: pressure_bar, temperature_k, feed_mol, gas_mol, solid_carbon_mol
```

各 `feed_mol`、`gas_mol`、`outlet_gas_mol` 都只含 `CH4`、`H2O`、`CO`、`CO2`、`H2`、`N2` 六个键，单位都是 mol。运行记录来自现场，不能删除或改写原始条目。

`targets` 是一个对象，固定含 `pressure`、`energy`、`carbon` 三个键。每个目标沿用原反应器计算请求的字段：`mode`、`pressure_bar`、`feed_mol`，等温工况带 `temperature_k`，绝热工况带 `inlet_temperature_k`。

输出对象只含 `calibration` 和 `predictions` 两个字段。

`calibration` 只含四个字段：

```text
pressure_exponent: 1000 K 的有效压力指数，无量纲
pressure_exponent_slope_per_k: 压力指数随温度的变化率，单位 K^-1
heat_capacity_scale: 产物气相显焓的乘性系数，无量纲
carbon_entropy_shift_j_mol_k: 固碳标准熵的加性修正，单位 J mol^-1 K^-1
```

`predictions` 下按 `pressure`、`energy`、`carbon` 三个目标分别给出结果，键名与 `targets` 一致。每个目标结果只放 `temperature_k`、`gas_mol`、`gas_mole_fractions`、`solid_carbon_mol` 四项。`gas_mol` 和 `gas_mole_fractions` 的键与 `feed_mol` 相同，摩尔分数六项之和为 1。

## 计算口径

高压那组数据里的组成偏差，要先由压力系数来校正；系数不对，后面的预测会一起偏。不同温度下的压力记录会给出不同指数，变化率要从整批记录一起算。绝热出口温度主要受产物热容系数影响。固碳项必须与实测固碳量和气相组成同时一致。

热力学基础数据固定使用 `/app/data/thermo.json`，不要改写。以 1 bar 为标准压力，所有气相按理想气体处理，固碳按活度为 1 的纯固相处理。反应器是封闭系统，碳、氢、氧、氮的元素总量在反应前后保持不变。

绝热工况的出口温度必须使产物总焓等于进料总焓。富碳进料析出固碳后，气相组成仍须满足平衡条件，不能只把超出元素衡算的气体删掉。绝热出口温度在 500 K 到 1500 K 这个区间里寻找。

参数个数不对时退出码为 2，不输出 JSON。输入文件打不开、JSON 结构不对、运行记录不合规、不足以确定三个系数或数值不合法时，也以退出码 2 结束，不向标准输出写内容。同一份标定单重跑，输出必须一致。

## 约束

只使用容器内已有的 Python 标准库和上述热力学数据，报告生成不依赖网络。

## 交接要求

现场记录什么样就交什么样，我们不替算法挑样本。读数一跳，先跟同一批的其它运行对一遍，看看是仪表的问题还是模型偏了。系数落定后，三个目标共用它。最后把元素守恒、相平衡和能量衡算都过一遍，哪条过不去就把单子退回。


```text
交班前复核：
1. 三类运行都能反演出对应系数。
2. 三个目标共用同一套系数。
3. 元素守恒、相平衡和能量衡算同时成立。
4. 任一项对不上，拒绝出单。
```
