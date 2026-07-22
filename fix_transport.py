import sys
sys.stdout.reconfigure(encoding="utf-8")
with open("problem2_planning.py", "r", encoding="utf-8") as f:
    content = f.read()

# The old transport section collects 订货量, should collect 供货量
old = '# \u6536\u96c6\u5404\u4f9b\u5e94\u5546\u8ba2\u8d27\u91cf\nsup_orders = {}\nfor cat, ord_qty in [("A", order_a), ("C", order_c), ("B", order_b)]:\n    subset = selected_df[selected_df["\u6750\u6599\u5206\u7c7b"] == cat]\n    for _, row in subset.iterrows():\n        sid = row["\u4f9b\u5e94\u5546ID"]\n        prop = row["avg_supply"] / mat_total_supply[cat]\n        sup_orders[sid] = sup_orders.get(sid, 0) + ord_qty * prop'

new = '# \u6536\u96c6\u5404\u4f9b\u5e94\u5546\u4f9b\u8d27\u91cf\nsupply_ids_list = supply_df["\u4f9b\u5e94\u5546ID"].values\nsup_orders = {}\nfor cat, ord_qty in [("A", order_a), ("C", order_c), ("B", order_b)]:\n    subset = selected_df[selected_df["\u6750\u6599\u5206\u7c7b"] == cat]\n    for _, row in subset.iterrows():\n        sid = row["\u4f9b\u5e94\u5546ID"]\n        sup_idx = np.where(supply_ids_list == sid)[0][0]\n        order_qty = ord_qty * (row["avg_supply"] / mat_total_supply[cat])\n        supply_qty = order_qty * median_ratio[sup_idx]\n        sup_orders[sid] = sup_orders.get(sid, 0) + supply_qty'

content = content.replace(old, new)

with open("problem2_planning.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed")
