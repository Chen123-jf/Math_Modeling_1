import sys, pandas as pd, numpy as np
from scipy.optimize import linprog

sys.stdout.reconfigure(encoding="utf-8")

print("问题3: 多购A少购C + 损耗最小化")
print()

WEEKLY_PROD = 28200
CONSUME = {"A": 0.6, "B": 0.66, "C": 0.72}
PRICE = {"A": 1.2, "B": 1.1, "C": 1.0}
PLAN_WEEKS = 24
SAFETY = 2
TRANS_CAP = 6000
N_TRANS = 8

# 问题3目标: 减少转运仓储成本 -> 最小化原料总体积
# 选材优先级: A(0.6) > B(0.66) > C(0.72)
print("选材优先级: A > B > C (体积效率优先)")

MIN_RAW_NEED = WEEKLY_PROD * CONSUME["A"]
TARGET = MIN_RAW_NEED

fname = "附件1 近5年402家供应商的相关数据.xlsx"
order_df = pd.read_excel(fname, sheet_name=0, header=0)
supply_df = pd.read_excel(fname, sheet_name=1, header=0)
trans_df = pd.read_excel("附件2 近5年8家转运商的相关数据.xlsx", header=0)
ranking = pd.read_csv("supplier_ranking.csv")

week_cols = [c for c in supply_df.columns if c.startswith("W")]
sup_vals = supply_df[week_cols].values.astype(float)
trans_loss = trans_df[week_cols].values.astype(float)
supply_ids = supply_df["供应商ID"].values

avg_map = {sid: sup_vals[i].mean() for i, sid in enumerate(supply_ids)}
mat_map = {sid: supply_df.iloc[i]["材料分类"] for i, sid in enumerate(supply_ids)}
ranking["avg_supply"] = ranking["供应商ID"].map(avg_map)
ranking["材料分类"] = ranking["供应商ID"].map(mat_map)

# 按要求: A > B > C
ranking["mat_priority"] = ranking["材料分类"].map({"A": 0, "B": 1, "C": 2})
ranking_sorted = ranking.sort_values(["mat_priority", "最终得分"], ascending=[True, False])

# 选供应商
selected_sids = []
cum = 0
for _, row in ranking_sorted.iterrows():
    selected_sids.append(row["供应商ID"])
    cum += row["avg_supply"]
    if cum >= TARGET:
        break

sel = ranking[ranking["供应商ID"].isin(selected_sids)]
nA = sum(sel["材料分类"] == "A")
nB = sum(sel["材料分类"] == "B")
nC = sum(sel["材料分类"] == "C")
print("供应商: {}家 (A={} B={} C={})".format(len(selected_sids), nA, nB, nC))

# 计算每家订货量 = avg_supply
supplier_data = {}
for _, row in sel.iterrows():
    sid = row["供应商ID"]
    si = np.where(supply_ids == sid)[0][0]
    supplier_data[sid] = {"order": row["avg_supply"], "sup_idx": si, "mat": row["材料分类"]}

# 总订货
total_order = sum(s["order"] for s in supplier_data.values())
print("总订货: {:.0f} m3/周".format(total_order))

# 运输分配
ord_vals = order_df[week_cols].values.astype(float)
supply_ratio = np.where(ord_vals > 0, sup_vals / np.maximum(ord_vals, 1), np.nan)
median_ratio = np.nan_to_num(np.nanmedian(supply_ratio, axis=1), nan=1.0)
trans_avg_loss = [np.mean(trans_loss[t][trans_loss[t] > 0]) / 100 if len(trans_loss[t][trans_loss[t] > 0]) > 0 else 0 for t in range(N_TRANS)]
trans_sorted = sorted(range(N_TRANS), key=lambda t: trans_avg_loss[t])

# 用取整后的量分配(确保最终结果不超运力)
sup_list = [(sid, max(1, int(round(supplier_data[sid]["order"] * median_ratio[supplier_data[sid]["sup_idx"]])))) for sid in selected_sids]
sup_list.sort(key=lambda x: -x[1])
trans_used = np.zeros(N_TRANS)
trans_assign = {}
for sid, qty in sup_list:
    for t in trans_sorted:
        if trans_used[t] + qty <= TRANS_CAP:
            trans_used[t] += qty
            trans_assign[sid] = t
            break
    else:
        t = max(range(N_TRANS), key=lambda x: TRANS_CAP - trans_used[x])
        trans_used[t] += qty
        trans_assign[sid] = t

print("运输分配:")
for t in range(N_TRANS):
    cnt = sum(1 for v in trans_assign.values() if v == t)
    if trans_used[t] > 0:
        print("  T{}: {}家, {} m3".format(t + 1, cnt, int(trans_used[t])))
print("  合计: {}家".format(len(trans_assign)))

# 效果分析
cost_per_week = sum(
    supplier_data[sid]["order"] * PRICE[supplier_data[sid]["mat"]] for sid in selected_sids
)
avg_loss = np.mean(trans_avg_loss)
orders_by_cat = {}
for cat in ["A", "B", "C"]:
    sub = sel[sel["材料分类"] == cat]
    tot = sub["avg_supply"].sum()
    mids = sub["供应商ID"].values
    mask = np.isin(supply_ids, mids)
    r = median_ratio[mask]
    ar = r.mean() if len(r) > 0 else 1.0
    orders_by_cat[cat] = {"order": tot, "supply": tot * ar}
recv_total = sum(v["supply"] for v in orders_by_cat.values()) * (1 - avg_loss)
prod_achievable = sum(v["supply"] * (1 - avg_loss) / CONSUME[k] for k, v in orders_by_cat.items())

print()
print("效果分析:")
print("  周采购成本: {:.0f}".format(cost_per_week))
print("  周接收量: {:.0f} m3".format(recv_total))
print("  可实现产量: {:.0f} m3 (满足率 {:.1f}%)".format(prod_achievable, prod_achievable / WEEKLY_PROD * 100))
print("  平均损耗率: {:.3f}%".format(avg_loss * 100))
print("完成。")
