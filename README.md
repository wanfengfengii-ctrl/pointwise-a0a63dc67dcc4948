# Minewater V1

Minewater 为模拟矿区排水巡检组制作固定的离线蓄水成果。测绘员登记格网修订，调度员选点并发布，现场人员持包输入实测水位，查询积水分区并导回核账明细。

## 运行

需要 Python 3.11，使用标准库和 SQLite。在项目目录运行完整回归和演示。

```sh
python3.11 -B -m unittest discover -s tests -t .
python3.11 -B -m demo
```

演示从 `samples/` 读取格网和点名，在独立临时库完成登记、冻结及发布。关闭源库后打开导出的包，打印水位 2 的点查和水位 2、5/2 的核账。

CLI 可以使用自己的数据库和输入文件。重复执行 `init` 会保留已有记录。

```sh
python3.11 -B -m minewater init survey.sqlite
python3.11 -B -m minewater terrain survey.sqlite section-r1 samples/saddles.json
python3.11 -B -m minewater freeze survey.sqlite shift-plan section-r1 samples/probes.json
python3.11 -B -m minewater publish survey.sqlite shift-edition shift-plan
python3.11 -B -m minewater bundle survey.sqlite shift-edition > shift.bundle
python3.11 -B -m minewater probe shift.bundle center 5/2
```

`minewater ledger shift.bundle requests.json` 读取形如 `[{"probe_id":"center","water":"5/2"}]` 的有序请求数组，在全部成功后向标准输出交付 JSON 明细。`bundle` 向标准输出交付固定包字节。错误写入标准错误，CLI 退出码为 2。

## 输入与计量

- 地形是非空矩形数组。`null` 表示无效格，其余格为 `{"height":值,"area":值}`。有效格面积必须为正。
- 行、列和格号均从零开始。格号为行号乘总列数加列号。点输入为 `{"probe_id":"center","row":0,"column":2}`，点名在计划内唯一。多个点名可以指向同一个有效格。
- 高程和水位以米计，面积以平方米计，体积以立方米计。输入支持整数、可解析为有理数的字符串、正分母整数对 `[分子,分母]`，Python 接口也接受 `Fraction`。二进制浮点值和布尔值不属于数值输入。包中使用约分后的正分母整数对。
- 高程严格低于水位的有效格才积水。同高格共同越过边界。分区按四邻域决定，编号取分区内最小格号，体积为分区内各格面积乘水深之和。示例在水位 2 时，`west`、`center`、`east` 的分区和体积分别为 `(0,2)`、`(2,2)`、`(4,6)`，两个鞍点为 `dry`。水位 5/2 时，这三个点均得到 `(0,14)`。

## Python API

在普通 `sqlite3.Connection` 上先调用 `minewater.initialize(connection)`。写入口各自管理事务，调用时连接须无外层事务。校验错误使用 `ValueError`，未知编号或点名使用 `registry.NotFoundError`，固定编号冲突使用 `registry.ConflictError`，无法读取离线包使用 `release.bundle.BundleError`。存储错误及提交前回调的异常向调用方传播。

| 入口 | 正常结果 |
| --- | --- |
| `terrain.revisions.put_terrain(connection, revision_id, rows)` | 登记固定修订并返回修订号。规范化后完全相同的同号输入可重放。 |
| `survey.plans.freeze_plan(connection, plan_id, revision_id, probes)` | 将已校验的点位固定到指定修订并返回计划号。 |
| `release.publish.publish(connection, release_id, plan_id, *, before_commit=None)` | 固定封套并原子发布，返回成果号。可选的无参回调在写入后、提交前执行，用于模拟提交前退出，回调不操作连接。 |
| `release.bundle.export_bundle(connection, release_id)` | 按成果号返回已提交的原封套字节。 |
| `field.query.query_probe(bundle_or_session, probe_id, water)` | 返回 `ProbeResult`。干点的 `status` 为 `dry`，分区和体积为 `None`。湿点的 `status` 为 `wet`，带格号和 `Fraction` 体积。 |
| `field.export.export_ledger(bundle_or_session, requests)` | 返回 `release_id` 和有序 `rows`。每行包括从零开始的 `position`、点名、精确水位和结果。 |

调度端可用 `terrain.revisions.get_revision`、`survey.catalog.get_plan` 按编号复核父链。地形更正以新修订登记。旧计划仍绑定原修订，旧成果仍能按原编号原样补发。现场可用 `field.session.open_session` 一次校验并打开包，再复用于多个查询。包载荷保存点名、分区事件和计量摘要，源格网留在测绘库。请求中重复出现的点按各自水位分别核账，空请求返回带成果号的零行明细。无效行使整份请求失败。
