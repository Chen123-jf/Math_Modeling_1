# CUMCM 2021 Problem C 供应商重要性评价

根据附件1提供的402家供应商近5年的订货量与供货量数据，对供应商的供货特征进行量化分析，建立反映保障企业生产重要性的数学模型，确定50家最重要的供应商。

## 方法

熵权法 + TOPSIS 综合排序。

### 评价指标

| 指标 | 说明 |
|------|------|
| 总供货量 | 5年总供货量，反映规模保障能力 |
| 供货活跃度 | 有供货的周数占比，反映持续性 |
| 供货稳定性 | 变异系数的倒数，反映供货波动性 |
| 供货可靠性 | 订货时能满足的比例，反映履约质量 |
| 供货充足率 | 供货量/订货量的中位数，反映实际到货水平 |

## 环境要求

- Python 3.8+
- 依赖库见 requirements.txt

## 运行方式

`ash
# 1. 克隆仓库
git clone https://github.com/Chen123-jf/Math_Modeling_1.git
cd Math_Modeling_1

# 2. 创建虚拟环境（推荐）
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行
python problem1.py
`

运行后会在当前目录生成 supplier_ranking.csv 和 top50_suppliers.csv。

## 文件说明

| 文件 | 说明 |
|------|------|
| problem1.py | 问题1: 熵权法 + TOPSIS 供应商排序 |
| problem2.py | 问题2: 订购与转运方案优化 |
| supplier_ranking.csv | 全部供应商排序结果 |
| top50_suppliers.csv | Top 50 结果 |
| 附件A 订购方案数据结果.xlsx | 已填入问题2的订购方案 |
| 附件B 转运方案数据结果.xlsx | 已填入问题2的转运方案 |
| 附件1 近5年402家供应商的相关数据.xlsx | 原始数据（订货量 & 供货量） |
| 附件2 近5年8家转运商的相关数据.xlsx | 转运商损耗率数据 |
| requirements.txt | Python 依赖 |
| CUMCM2021-C.pdf | 题目原文件 |
