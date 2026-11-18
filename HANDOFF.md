# 同高鞍点事故交接说明

## 根因

两处缺陷叠加，与 `INCIDENT.md` 的表一致。

1. `history/basins.py`（成果加工）：生成分区历史时只按“同号 basin”记一个前驱。
   一个连通块合并两个已生效分区时，只有编号等于新块最小格号的那个分区被记为前驱，
   另一个被吸收的分区连同其事件被丢弃。更糟的是，被吸收分区上的巡检点被改绑到
   幸存分区的起始事件，于是水位刚到鞍点高度时，独立洼地就被报成同一个分区。
   越过鞍点后，被丢弃分区的面积与高程矩不在任何链条上，蓄水量因此少报。
2. `field/query.py`（现场结算）：沿前驱回溯时遇到多前驱事件即停止，只累加单链上的
   事件。即使历史记录完整，也无法把汇合进来的各支体积计入。

## 修复

- `history/basins.py`：以“每个湿格当前属于哪个事件”的归属表代替单头表。
  每个连通块事件记录**全部**仍生效的被吸收分区事件为前驱（集合去重后按事件序排序）；
  巡检点锚定在它自身首次生效的事件上，之后由查询沿前驱自然跟随归属变化。
- `field/query.py`：体积改为遍历所选事件的**全部前驱祖先**（带访问集，避免重复计数），
  对每条事件的引入面积与高程矩求和，再按 `水位 × 面积 − 高程矩` 结算。
  同高格在同一批次引入，故严格低于水位才生效、同高同时越过边界的语义不变。
- 固定包的摘要格式（`level/basin_id/area/height_moment/predecessors`）保持不变，
  旧版正常包仍可按原编号读取、补发与查询。发布仍是“读源库全量重算后写入”，
  重复编号 `ON CONFLICT DO NOTHING`，源修订更正不影响已发布成果。

## 回归

`tests/test_field.py` 新增：

- `test_successive_merges`：`INCIDENT.md` 的两次先后汇合场景，两份修订在高程互换后
  分别在水位 2、5/2、7/2 复核，尚未连通的洼地不入账。
- `test_seeded_exhaustive_oracle`：固定种子的随机稀疏格网，在每个高程及其 ±1/2 处
  与独立 `flood_oracle` 全点比对（含同高点、负高程、分数面积）。
- `test_legacy_summary_format_readable` / `test_new_merge_summary_readable`：
  旧版单前驱包与新版多前驱包都能离线解码、校验、查询，且解码后再编码字节一致。

原有断言未改动（含 `BASIN_HANDOFF_MISMATCH`）。

## 验证

```sh
python3.11 -B -m unittest discover -s tests -t .     # 28 项全通过
python3.11 -B -m unittest -v tests.test_field.FieldTests.test_equal_saddles
python3.11 -B -m demo
```

`demo` 在临时库发布后关闭源库，再打开导出包，鞍点前后结果如下（节选）：

| 水位 | west | center | east | west-saddle | east-saddle |
| --- | --- | --- | --- | --- | --- |
| 2 | (0, 2) | (2, 2) | (4, 6) | dry | dry |
| 5/2 | (0, 14) | (0, 14) | (0, 14) | (0, 14) | (0, 14) |

`minewater probe shift.bundle center 5/2` 与 `minewater ledger shift.bundle requests.json`
在源库删除后同样得到上述结果；未知点名退出码 2。
