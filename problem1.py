import sys
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

# 1. 数据加载与预处理

DATA_FILE = "附件1 近5年402家供应商的相关数据.xlsx"

def load_and_merge_data(filepath):
    # 读附件1的两个sheet，把订货量和供货量合并到一张表里。
    order_df = pd.read_excel(filepath, sheet_name=0, header=0)
    supply_df = pd.read_excel(filepath, sheet_name=1, header=0)

    week_cols = [c for c in supply_df.columns if c.startswith("W")]
    n_weeks = len(week_cols)
    print("历史数据覆盖 {} 周（约5年）".format(n_weeks))

    # 加前缀区分订货和供货的周数列
    sup_df = supply_df.copy()
    sup_df.columns = ["供应商ID", "材料分类"] + ["SUP_{}".format(c) for c in week_cols]

    ord_df = order_df.copy()
    ord_df.columns = ["供应商ID", "材料分类"] + ["ORD_{}".format(c) for c in week_cols]

    merged = ord_df.merge(
        sup_df[["供应商ID"] + ["SUP_{}".format(c) for c in week_cols]],
        on="供应商ID"
    )

    print("合并后维度: {}".format(merged.shape))
    cat_counts = merged["材料分类"].value_counts()
    print("材料分布: A={}, B={}, C={}".format(
        cat_counts.get("A", 0),
        cat_counts.get("B", 0),
        cat_counts.get("C", 0)
    ))

    return merged, n_weeks


# 2. 特征提取

def extract_supplier_features(df, week_cols, n_weeks):
    # 从原始数据中计算每个供应商的5个评价指标。
    ord_cols = ["ORD_{}".format(c) for c in week_cols]
    sup_cols = ["SUP_{}".format(c) for c in week_cols]
    ord_vals = df[ord_cols].values.astype(float)
    sup_vals = df[sup_cols].values.astype(float)

    n_suppliers = len(df)
    print("正在处理 {} 家供应商...".format(n_suppliers))

    # 指标1: 总供货量
    # 直接求和，是最直观的"重要"信号
    total_supply = sup_vals.sum(axis=1)

    # 指标2: 供货活跃度
    # 有供货的周数占比。连续5年每周都供应的供应商
    active_weeks = (sup_vals > 0).sum(axis=1)
    nw = float(n_weeks)
    activeness = active_weeks / nw

    # 指标3: 供货稳定性
    # 用变异系数的倒数。供货量忽大忽小的供应商，稳定性低
    mean_supply = sup_vals.mean(axis=1)
    std_supply = sup_vals.std(axis=1, ddof=0)
    cv_vals = np.where(mean_supply > 1, std_supply / mean_supply, 10.0)
    cv_vals = np.clip(cv_vals, 0, 10)
    stability = 1.0 / (cv_vals + 0.01)

    # 指标4: 供货可靠性
    # 统计当企业下了订单时，供应商能不能"交足货"的概率
    # >= 订货量就算满足
    ordered = ord_vals > 0
    sufficient = (sup_vals >= ord_vals) & ordered
    order_weeks = ordered.sum(axis=1)
    reliability = np.where(order_weeks > 0, sufficient.sum(axis=1) / order_weeks, 0)

    # 指标5: 供货充足率
    # 用中位数而不是均值，避免某次超量10倍拉高平均的情况
    ratios = np.where(ordered, sup_vals / np.maximum(ord_vals, 1), np.nan)
    fulfillment = np.nanmedian(ratios, axis=1)
    fulfillment = np.nan_to_num(fulfillment, nan=0)

    # 看一眼数值分布，确认没出异常
    print("\n指标范围检查:")
    print("  总供货量: {} ~ {}".format(total_supply.min(), total_supply.max()))
    print("  活跃度:   {:.3f} ~ {:.3f}".format(activeness.min(), activeness.max()))
    print("  稳定性:   {:.3f} ~ {:.3f}".format(stability.min(), stability.max()))
    print("  可靠性:   {:.3f} ~ {:.3f}".format(reliability.min(), reliability.max()))
    print("  充足率:   {:.3f} ~ {:.3f}".format(fulfillment.min(), fulfillment.max()))

    # 组装矩阵，后面熵权和TOPSIS直接操作这个矩阵
    feature_matrix = np.column_stack([
        total_supply,
        activeness,
        stability,
        reliability,
        fulfillment
    ])

    feature_names = ["总供货量", "供货活跃度", "供货稳定性", "供货可靠性", "供货充足率"]

    return feature_matrix, feature_names

# 3. 熵权法

def compute_entropy_weights(X):
    # 熵权法的核心逻辑: 某个指标上各供应商的差异越大，这个指标的信息量就越大，权重就应该越高。
    n_suppliers = X.shape[0]

    # 极差归一化，把不同量纲的指标拉到 [0,1] 区间
    X_min = X.min(axis=0)
    X_max = X.max(axis=0)
    X_norm = (X - X_min) / (X_max - X_min + 1e-10)

    # 算每个指标下各供应商占的比重（类似概率分布）
    P = X_norm / (X_norm.sum(axis=0) + 1e-10)

    # 信息熵公式: e_j = -k * sum(p_ij * ln(p_ij))
    # 其中 k = 1/ln(n)，保证熵值落在 [0,1]
    k = 1.0 / np.log(n_suppliers)
    eps = 1e-10
    entropy = -k * np.sum(P * np.log(P + eps), axis=0)

    # 差异系数 d_j = 1 - e_j，熵越大差异越小
    # 权重 = d_j / sum(d_j)
    diff_coef = 1 - entropy
    weights = diff_coef / diff_coef.sum()

    return weights, entropy

# 4. TOPSIS 综合排序

def rank_by_topsis(X, weights):
    """
    TOPSIS 的核心: 构造一个"理想供应商"和一个"最差供应商",然后看每个供应商离理想有多近、离最差有多远。
    得分 = 到最差距离 / (到理想距离 + 到最差距离)
    这个比值的好处是天然在 [0,1] 区间，且单调，排名直观。
    """
    # 归一化
    # 先用极差归一化消除量纲影响
    X_min = X.min(axis=0)
    X_max = X.max(axis=0)
    X_norm = (X - X_min) / (X_max - X_min + 1e-10)

    # 再用向量归一化（TOPSIS标准操作，保持相对距离）
    norm_vec = np.sqrt((X_norm ** 2).sum(axis=0))
    X_vec_norm = X_norm / (norm_vec + 1e-10)

    # 加权标准化矩阵V
    V = X_vec_norm * weights

    # 正理想解: 每个指标取最大值（因为全都是正向指标）
    # 负理想解: 每个指标取最小值
    V_plus = V.max(axis=0)
    V_minus = V.min(axis=0)

    # 欧氏距离
    D_plus = np.sqrt(((V - V_plus) ** 2).sum(axis=1))
    D_minus = np.sqrt(((V - V_minus) ** 2).sum(axis=1))

    # 相对贴近度
    C = D_minus / (D_plus + D_minus + 1e-10)

    return C

# 5. 输出结果

def build_result_table(topsis_scores, features, meta):
    """
    把TOPSIS得分和原始特征拼成一张结果表，排序输出。
    同时考虑材料类别对供应商的"战略重要性"差异——A类比C类采购单价高20%、单耗更低，问题3说要多买A少买C，所以给A一个较高的权重系数。
    """
    total_supply = features[:, 0]
    activeness = features[:, 1]
    stability = features[:, 2]
    reliability = features[:, 3]
    fulfillment = features[:, 4]

    # 材料类型权重: A > B > C
    # 按单价比例 + 单耗比例综合估算
    MATERIAL_WEIGHT = {"A": 1.6, "B": 1.2, "C": 1.0}
    material_w = meta["材料分类"].map(MATERIAL_WEIGHT).values

    final_scores = topsis_scores * material_w

    # 拼最终结果表
    result = meta.copy()
    result["总供货量"] = total_supply
    result["活跃度"] = activeness
    result["稳定性"] = stability
    result["可靠性"] = reliability
    result["充足率"] = fulfillment
    result["TOPSIS得分"] = topsis_scores
    result["材料权重"] = material_w
    result["最终得分"] = final_scores

    result = result.sort_values("最终得分", ascending=False).reset_index(drop=True)
    result["排名"] = range(1, len(result) + 1)

    return result


def print_top50(result):
    """
    打印Top50结果，格式对齐方便直接复制到论文表格。
    """
    top50 = result.head(50)
    print("\n")
    print("Top 50 最重要供应商")
    print("-" * 88)

    # 表头
    sep_line = "-" * 88
    hdr = "{:>4} {:>6} {:>4} {:>8} {:>10} {:>8} {:>8} {:>8} {:>8}".format(
        "排名", "供应商", "材料", "最终分", "总供货量",
        "活跃度", "稳定性", "可靠性", "充足率"
    )
    print(hdr)
    print(sep_line)

    for _, row in top50.iterrows():
        print("{:4d} {:>10} {:>5} {:>14.4f} {:>12.0f} {:>12.3f} {:>12.3f} {:>12.3f} {:>10.3f}".format(
            int(row["排名"]),
            row["供应商ID"],
            row["材料分类"],
            row["最终得分"],
            row["总供货量"],
            row["活跃度"],
            row["稳定性"],
            row["可靠性"],
            row["充足率"]
        ))

    print()
    nA = (top50["材料分类"] == "A").sum()
    nB = (top50["材料分类"] == "B").sum()
    nC = (top50["材料分类"] == "C").sum()
    print("Top 50 中材料分布: A={}, B={}, C={}".format(nA, nB, nC))

    print("\nTop 10 明细:")
    for _, row in top50.head(10).iterrows():
        print("  #{} {} ({}) TOPSIS={:.4f} x 材权{:.1f} = {:.4f}".format(
            int(row["排名"]),
            row["供应商ID"],
            row["材料分类"],
            row["TOPSIS得分"],
            row["材料权重"],
            row["最终得分"]
        ))

# 6. 主流程

def main():
    print("C题 问题1 — 供应商重要性评价")
    print("方法: 熵权法 + TOPSIS")

    # Step 1: 数据加载
    df, n_weeks = load_and_merge_data(DATA_FILE)

    week_cols = [c.replace("ORD_", "") for c in df.columns if c.startswith("ORD_W")]
    week_cols_clean = ["W{:03d}".format(i+1) for i in range(len(week_cols))]

    # Step 2: 特征提取
    X, feature_names = extract_supplier_features(df, week_cols_clean, n_weeks)

    # Step 3: 熵权法确定权重
    weights, entropies = compute_entropy_weights(X)
    print("\n熵权法确定的权重:")
    for name, w, e in zip(feature_names, weights, entropies):
        print("  {}: 熵值={:.4f}, 权重={:.4f}".format(name, e, w))

    # Step 4: TOPSIS打分
    scores = rank_by_topsis(X, weights)

    # Step 5: 排序输出
    meta = df[["供应商ID", "材料分类"]].copy()
    result = build_result_table(scores, X, meta)

    # Step 6: 打印和保存
    print_top50(result)

    result.to_csv("supplier_ranking.csv", index=False, encoding="utf-8-sig")
    result.head(50).to_csv("top50_suppliers.csv", index=False, encoding="utf-8-sig")
    print("\n所有结果已保存至 supplier_ranking.csv / top50_suppliers.csv")
    print("完成。")


if __name__ == "__main__":
    main()
