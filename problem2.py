import sys, pandas as pd, numpy as np
sys.stdout.reconfigure(encoding="utf-8")

print("问题2: 订购与转运方案优化")
print()

# 1. 参数
WEEKLY_PROD = 28200
CONSUME = {"A": 0.6, "B": 0.66, "C": 0.72}
PRICE = {"A": 1.2, "B": 1.1, "C": 1.0}
PLAN_WEEKS = 24
SAFETY = 2
TRANS_CAP = 6000
N_TRANS = 8

# 单位产品总成本 = 采购 + 运输 + 仓储, 运输仓储按体积比例相同
# A: 1.2*0.6 + s*0.6 = 0.72 + s*0.6
# B: 1.1*0.66 + s*0.66 = 0.726 + s*0.66
# C: 1.0*0.72 + s*0.72 = 0.72 + s*0.72
# 由于s相同, A比C总成本更低, 两者都优于B
# 所以选材顺序: A > C > B

# 每周最经济的最小原材料需求量 = 全用A
MIN_RAW_NEED = WEEKLY_PROD * CONSUME["A"]
print("每周最小原材料需求量(全用A):", MIN_RAW_NEED, "m3")
print("安全库存:", SAFETY, "周")
print()

# 2. 数据加载
fname = "附件1 近5年402家供应商的相关数据.xlsx"
order_df = pd.read_excel(fname, sheet_name=0, header=0)
supply_df = pd.read_excel(fname, sheet_name=1, header=0)
trans_df = pd.read_excel("附件2 近5年8家转运商的相关数据.xlsx", header=0)
ranking = pd.read_csv("supplier_ranking.csv")

week_cols = [c for c in supply_df.columns if c.startswith("W")]
ord_vals = order_df[week_cols].values.astype(float)
sup_vals = supply_df[week_cols].values.astype(float)
trans_loss = trans_df[week_cols].values.astype(float)

# 3. 最小供应商数
# 按重要性从高到低选, 直到总供货量 >= MIN_RAW_NEED
# 先算每家供应商的周均供货
supply_avg_df = pd.DataFrame({
    "供应商ID": supply_df["供应商ID"],
    "avg_supply": sup_vals.mean(axis=1),
    "材料分类": supply_df["材料分类"]
})
ranking = ranking.drop(columns=["avg_supply", "材料分类"], errors="ignore")
ranking = ranking.merge(supply_avg_df, on="供应商ID")

# 贪心选供应商: 每次选重要性最高且材料最优先的未选供应商
# 优先选A, 其次C, 最后B (按经济性)
MAT_PRIORITY = {"A": 0, "C": 1, "B": 2}
ranking["priority"] = ranking["材料分类"].map(MAT_PRIORITY)
ranking["mat_priority"] = ranking["priority"]

# 排序: 先按材料优先级, 再按最终得分
ranking_selected = ranking.sort_values(
    ["mat_priority", "最终得分"], ascending=[True, False]
).copy()

selected = []
total_supply = 0
target = MIN_RAW_NEED * 1.0  # 刚好达标

for _, row in ranking_selected.iterrows():
    selected.append(row)
    total_supply += row["avg_supply"]
    if total_supply >= target:
        break

selected_df = pd.DataFrame(selected).reset_index(drop=True)
n_selected = len(selected_df)

# 各类材料的总供货
mat_counts = selected_df["材料分类"].value_counts()

print("最小供应商数:", n_selected)
print("  材料分布: A={} B={} C={}".format(
    mat_counts.get("A", 0), mat_counts.get("B", 0), mat_counts.get("C", 0)))
print("  总周均供货: {:.0f} m3".format(total_supply))
print()

# 4. 24周订购方案
# 方案: 每周按最优材料配比订购, 保持安全库存
# 最优配比: 优先用A, 其次C, 最后B
# 库存约束: 库存 >= SAFETY * 周消耗量

mat_total_supply = {}
for cat in ["A", "B", "C"]:
    subset = selected_df[selected_df["材料分类"] == cat]
    mat_total_supply[cat] = subset["avg_supply"].sum()

# 供货/订货比(历史中位数): 用于估算实际接收量
supply_ratio = np.where(ord_vals > 0, sup_vals / np.maximum(ord_vals, 1), np.nan)
median_ratio = np.nan_to_num(np.nanmedian(supply_ratio, axis=1), nan=1.0)

ratio_by_cat = {}
for cat in ["A", "B", "C"]:
    sup_ids = selected_df[selected_df["材料分类"] == cat]["供应商ID"].values
    mask = supply_df["供应商ID"].isin(sup_ids).values
    r = median_ratio[mask]
    ratio_by_cat[cat] = r.mean() if len(r) > 0 else 1.0

# 转运商平均损耗率
trans_avg_loss = []
for t in range(N_TRANS):
    vals = trans_loss[t][trans_loss[t] > 0]
    avg = np.mean(vals) / 100 if len(vals) > 0 else 0
    trans_avg_loss.append(avg)
avg_loss = np.mean(trans_avg_loss)

# 每周订购逻辑:
# 优先从A供应商订, A不够再订C, 还不够再订B
# 接收量 = 订货量 * 供货比 * (1-损耗率)
# 库存 = 上期库存 + 到货 - 消耗(按到货材料配比换算)

print("最优订购配比: A > C > B")
print("  可用A: {:.0f} m3/周, C: {:.0f} m3/周, B: {:.0f} m3/周".format(
    mat_total_supply["A"], mat_total_supply["C"], mat_total_supply["B"]))
print()

# 算最少需要的原材料总体积
# 先用A, 不够用C, 还不够用B
def calc_raw_need(prod_target):
    """计算达到目标产量所需的最少原材料(优先A> C> B)"""
    need_a = prod_target * CONSUME["A"]
    need_c = max(0, prod_target - need_a / CONSUME["A"]) * CONSUME["C"]
    # 实际上需要按材料分别算: 先算用A能产多少, 不够的用C补
    prod_from_a = mat_total_supply["A"] / CONSUME["A"]
    if prod_from_a >= prod_target:
        return {"A": prod_target * CONSUME["A"], "C": 0, "B": 0}
    prod_from_c = mat_total_supply["C"] / CONSUME["C"]
    if prod_from_a + prod_from_c >= prod_target:
        rem = prod_target - prod_from_a
        return {"A": mat_total_supply["A"], "C": rem * CONSUME["C"], "B": 0}
    rem = prod_target - prod_from_a - prod_from_c
    return {"A": mat_total_supply["A"], "C": mat_total_supply["C"], "B": rem * CONSUME["B"]}

raw_need = calc_raw_need(WEEKLY_PROD)
order_a = raw_need["A"]
order_c = raw_need["C"]
order_b = raw_need["B"]

# 限制不能超过可用量
order_a = min(order_a, mat_total_supply["A"])
order_c = min(order_c, mat_total_supply["C"])
order_b = min(order_b, mat_total_supply["B"])

# 如果总订购量小于最小需求（全用A）, 尽可能多订
if order_a + order_c + order_b < MIN_RAW_NEED:
    deficit = MIN_RAW_NEED - (order_a + order_c + order_b)
    if order_a < mat_total_supply["A"]:
        add = min(deficit, mat_total_supply["A"] - order_a)
        order_a += add
        deficit -= add
    if deficit > 0 and order_b < mat_total_supply["B"]:
        add = min(deficit, mat_total_supply["B"] - order_b)
        order_b += add
        deficit -= add
    if deficit > 0 and order_c < mat_total_supply["C"]:
        add = min(deficit, mat_total_supply["C"] - order_c)
        order_c += add

total_order = order_a + order_b + order_c

# 各材料到货比
ratio_a = ratio_by_cat["A"]
ratio_c = ratio_by_cat["C"]
ratio_b = ratio_by_cat["B"]

print("最优周订购量:")
print("  A: {:.0f} m3, C: {:.0f} m3, B: {:.0f} m3".format(order_a, order_c, order_b))
print("  总订购: {:.0f} m3/周".format(total_order))
print()

# 生成24周订购计划
init_inv = SAFETY * MIN_RAW_NEED  # 初始库存 = 2周×最低消耗
print("初始库存: {:.0f} m3 (满足{}周生产)".format(init_inv, SAFETY))
print()
print("24周订购计划:")
sep = "-" * 80
print("{:>4} {:>8} {:>8} {:>8} {:>8} {:>9} {:>10}".format(
    "周次", "订A", "订C", "订B", "总订货", "接收量", "库存"))
print(sep)

weekly_orders = []
inventory = init_inv

for w in range(PLAN_WEEKS):
    # 接收量
    recv_a = order_a * ratio_a
    recv_c = order_c * ratio_c
    recv_b = order_b * ratio_b
    recv_total = (recv_a + recv_c + recv_b) * (1 - avg_loss)

    # 消耗(按到货材料配比)
    prod_a = recv_a * (1 - avg_loss) / CONSUME["A"]
    prod_c = recv_c * (1 - avg_loss) / CONSUME["C"]
    prod_b = recv_b * (1 - avg_loss) / CONSUME["B"]
    actual_prod = prod_a + prod_c + prod_b
    raw_consumed = recv_total  # 全部到货投入生产

    # 库存
    inventory = inventory + recv_total - raw_consumed
    if inventory < 0:
        inventory = 0

    weekly_orders.append({
        "周次": w+1, "订A": order_a, "订C": order_c, "订B": order_b,
        "总订货": total_order, "接收量": recv_total, "库存": inventory
    })

    print("{:4d} {:>12.0f} {:>9.0f} {:>9.0f} {:>10.0f} {:>11.0f} {:>12.0f}".format(
        w+1, order_a, order_c, order_b, total_order, recv_total, inventory))

print(sep)
tot_ord = sum(o["总订货"] for o in weekly_orders)
tot_recv = sum(o["接收量"] for o in weekly_orders)
avg_inv = np.mean([o["库存"] for o in weekly_orders])
print("{:>4} {:>10} {:>10} {:>10} {:>9.0f} {:>11.0f} 平均库存:{:.0f}".format(
    "合计", "", "", "", tot_ord, tot_recv, avg_inv))

# 检查库存是否满足安全要求
min_inv = min(o["库存"] for o in weekly_orders)
print()
print("  最低库存: {:.0f} m3 (安全库存要求: {:.0f})".format(min_inv, init_inv))
if min_inv >= init_inv:
    print("  库存满足安全要求")
else:
    print("  库存低于安全线, 但受限于供应能力")

# 5. 转运方案
print()
print("5. 转运方案")

trans_sorted = sorted(range(N_TRANS), key=lambda t: trans_avg_loss[t])
print("  转运商(损耗率升序):")
for rank, t in enumerate(trans_sorted):
    print("    {}. {}  {:.3f}%".format(rank+1, trans_df.iloc[t]["转运商ID"], trans_avg_loss[t]*100))

# 第1周分配
print()
print("  第1周供应商-转运商分配:")
print("  {:>8} {:>10} {:>8} {:>10}".format("转运商", "运量m3", "供应商数", "损耗率%"))
print("  " + "-" * 42)

# 收集各供应商供货量
supply_ids_list = supply_df["供应商ID"].values
sup_orders = {}
for cat, ord_qty in [("A", order_a), ("C", order_c), ("B", order_b)]:
    subset = selected_df[selected_df["材料分类"] == cat]
    for _, row in subset.iterrows():
        sid = row["供应商ID"]
        sup_idx = np.where(supply_ids_list == sid)[0][0]
        order_qty = ord_qty * (row["avg_supply"] / mat_total_supply[cat])
        supply_qty = order_qty * median_ratio[sup_idx]
        sup_orders[sid] = sup_orders.get(sid, 0) + supply_qty

sorted_sup = sorted(sup_orders.items(), key=lambda x: -x[1])
trans_used = np.zeros(N_TRANS)
trans_detail = {t: [] for t in range(N_TRANS)}

for sid, qty in sorted_sup:
    assigned = False
    for t in trans_sorted:
        if trans_used[t] + qty <= TRANS_CAP:
            trans_used[t] += qty
            trans_detail[t].append(sid)
            assigned = True
            break
    if not assigned:
        t = max(range(N_TRANS), key=lambda x: TRANS_CAP - trans_used[x])
        trans_used[t] += qty
        trans_detail[t].append(sid)

for t in range(N_TRANS):
    if len(trans_detail[t]) > 0:
        tq = trans_used[t]
        ns = len(trans_detail[t])
        print("  {:>8} {:>14.0f} {:>12d} {:>13.3f}".format(
            trans_df.iloc[t]["转运商ID"], tq, ns, trans_avg_loss[t]*100))
    else:
        print("  {:>8} {:>14.0f} {:>12} {:>13.3f}".format(
            trans_df.iloc[t]["转运商ID"], 0, 0, trans_avg_loss[t]*100))

# 6. 效果分析
print()
print("6. 效果分析")
print()

total_cost = sum(
    o["订A"]*PRICE["A"] + o["订C"]*PRICE["C"] + o["订B"]*PRICE["B"]
    for o in weekly_orders
)
avg_recv = np.mean([o["接收量"] for o in weekly_orders])
avg_weekly_cost = total_cost / PLAN_WEEKS

# 可实现的周产量
weekly_prod_from_a = order_a * ratio_a * (1 - avg_loss) / CONSUME["A"]
weekly_prod_from_c = order_c * ratio_c * (1 - avg_loss) / CONSUME["C"]
weekly_prod_from_b = order_b * ratio_b * (1 - avg_loss) / CONSUME["B"]
actual_weekly_prod = weekly_prod_from_a + weekly_prod_from_c + weekly_prod_from_b

print("24周总采购成本: {:.0f} (C单价=1)".format(total_cost))
print("周均采购成本: {:.0f}".format(avg_weekly_cost))
print("周均接收量: {:.0f} m3".format(avg_recv))
print("周均可实现产量: {:.0f} m3产品".format(actual_weekly_prod))
print("产量满足率: {:.1f}%".format(actual_weekly_prod / WEEKLY_PROD * 100))
print("运输损耗率: {:.3f}%".format(avg_loss * 100))
print("总运力使用: {:.0f} / {} m3/周".format(trans_used.sum(), N_TRANS * TRANS_CAP))
print("期末平均库存: {:.0f} m3".format(avg_inv))

pd.DataFrame(weekly_orders).to_csv("ordering_plan.csv", index=False, encoding="utf-8-sig")
print()
print("结果已保存: ordering_plan.csv")
print("完成。")
