# GL eliminateRaid 分析记录

本文档记录当前对 GL `eliminateRaid` payload 的分析结论、已确认事实和后续导出方案。

## 1. 范围

当前讨论对象为 GL `Table/` 中命名包含 `eliminateRaid` 的 zip，例如：

- `6012301_eliminateRaid_binah_outdoor_unarmed_normal.zip`
- `6012301_eliminateRaid_binah_outdoor_unarmed_normal_start2phase.zip`
- `6012301_eliminateRaid_binah_outdoor_unarmed_normal_start3phase.zip`
- `6062106_eliminateRaid_perorozilla_outdoor_light_insane_start2phase.zip`

这些 zip 当前已经可以被稳定提取，但只会导出 raw `.bytes`，不会输出最终语义 JSON。

## 2. 当前提取行为

当前 `extract -r gl -rt table` 会对 `*eliminateRaid*.zip` 走独立路由：

- 正常打开 zip
- 提取内层 `.bytes`
- 直接落盘 raw payload
- 输出一条 `INFO`，提示 semantic parser is not implemented yet

这属于预期行为，不是错误。

## 3. 已确认事实

### 3.1 它不是当前 FlatBufferData 表

这批 payload 不是当前 `FlatBufferData` schema，也不是 `GroundGridFlat` / `GroundNodeLayerFlat` 这类地图网格表。

继续按文件名猜 `FlatBufferData` schema，会得到错误的：

```text
generated FlatBufferData schema is missing
```

### 3.2 头部有稳定结构

以样本：

- `GL_Extracted/Table/6012301_eliminateRaid_binah_outdoor_unarmed_normal_start2phase/6012301_eliminateraid_binah_outdoor_unarmed_normal_start2phase.bytes`

为例，其头部可以观察到：

- 前导 signed marker：`-1274`
- 一个短长度值：`4`
- 版本字符串：`"1.82"`

样本开头片段如下：

```text
06 fb ff ff ff 04 00 00 00 31 2e 38 32 ...
```

同组样本 `normal / start2phase / start3phase` 具有相同格式，仅内容数量不同。

### 3.3 payload 内有显式长度前缀字符串

同一条样本中可以稳定读到：

- `SpawnPlayer`
- `SetImmuneOff_2 (1)`
- `EndBattle`
- `SpawnBinah`
- `1-bPhaseChanged`
- `SpawnPointParent`
- `Binah_Outdoor_Unarmed_Normal`

其中 `SpawnPlayer` 不是偶然扫出来的 ASCII，而是带有显式长度字段的字符串值。

例如这段记录：

```text
04 f4 ff ff ff 0b 00 00 00 53 70 61 77 6e 50 6c 61 79 65 72
```

可以稳定拆成：

- `0x04`：1-byte tag
- `0xfffffff4`：signed value `-12`
- `0x0000000b`：长度 `11`
- `"SpawnPlayer"`

### 3.4 这批内容更像 battle / raid command script

对多条样本扫描 ASCII 后，可以看到大量高价值名称：

- `SpawnPlayer`
- `EndBattle`
- `SpawnBinah`
- `CommandSpawnBinah`
- `SetImmuneOff`
- `SetImmuneOff_2`
- `0->1PhaseChanged`
- `0->2PhaseChanged`
- `Moveto4Section`
- `Common_Sandbag`
- `Common_Barrel`
- `Common_Baricade`
- `Desert_Truck_Low`

这说明 payload 同时包含：

- 指令名
- 条件或状态名
- 场景对象名
- 阶段切换信息

### 3.5 dump.cs 中存在高度相关的 runtime 类型

在 `GL_Extracted/Dumps/dump.cs` 中可以确认存在大量同一生态的类型，并且很多是 `MemoryPack.IMemoryPackable`：

- `GroundCommandSpawnPlayer`
- `GroundCommandEndBattle`
- `GroundCommandDestroyObstacle`
- `GroundCommandSetStatusImmune`
- `GroundCommandSpawnEntity`
- `GroundCommandStartSection`
- `GroundConditionCharacterPhaseChanged`
- `GroundConditionObstacleDestroyed`

同时还能看到对应的 visual 类：

- `GroundCommandSpawnPlayerVisual`
- `GroundCommandEndBattleVisual`
- `GroundCommandDestroyObstacleVisual`
- `GroundCommandForceUpdateRaidBossIndexVisual`

这说明 GL 运行时确实存在一整套 `GroundCommand* / GroundCondition*` 体系。

## 4. 当前可以确认的结论

高置信度结论：

- `eliminateRaid` 是结构化二进制，不是随机垃圾数据。
- `eliminateRaid` 不是当前 `FlatBufferData` 表。
- `SpawnPlayer`、`EndBattle` 等更像 runtime command 名，而不是插件名。
- 这批内容与 `MX.Logic.Battles.GroundCommand* / GroundCondition*` 体系强相关。

当前不能过度声称的内容：

- 不能直接断言整个外层容器就是“标准 MemoryPack 文件”。
- 不能断言所有负数 tag 的精确语义已经完全明确。
- 不能保证每一条字符串都直接一一映射到 `dump.cs` 中的具体类型。

## 5. 推荐导出方案

不要直接尝试一步到位生成最终语义 JSON。更稳的方案是分两层推进。

### 5.1 第一阶段：Inspect JSON

目标是保留 raw payload，同时导出一个半结构化的可读分析文件。

推荐输出格式：

```json
{
  "format": "gl-eliminate-raid-inspect-v1",
  "header": {
    "sentinel": -1274,
    "version": "1.82",
    "record_count_hint": 3
  },
  "tokens": [
    {
      "offset": 30,
      "tag": 4,
      "signed_value": -12,
      "string": "SpawnPlayer"
    },
    {
      "offset": 170,
      "tag": 4,
      "signed_value": -19,
      "string": "SetImmuneOff_2 (1)"
    },
    {
      "offset": 292,
      "tag": 4,
      "signed_value": -10,
      "string": "EndBattle"
    }
  ],
  "ascii_strings": [
    "SpawnBinah",
    "Binah_Outdoor_Unarmed_Normal",
    "SpawnPointParent",
    "Common_Sandbag"
  ]
}
```

这个阶段的目标不是“最终正确语义”，而是：

- 可读
- 可 diff
- 可对齐不同 phase 的差异
- 不因为局部未知字段而丢失整条记录

### 5.2 第二阶段：Typed JSON

在 Inspect JSON 稳定后，再引入命令名到类型名的映射，例如：

- `SpawnPlayer -> GroundCommandSpawnPlayer`
- `EndBattle -> GroundCommandEndBattle`
- `DestroyObstacle -> GroundCommandDestroyObstacle`
- `SetImmuneOff* -> GroundCommandSetStatusImmune`
- `*PhaseChanged -> GroundConditionCharacterPhaseChanged` 或相关 condition

Typed JSON 阶段建议保留以下兜底字段：

- `raw_hex`
- `raw_size`
- `unknown_fields`
- `unresolved_type`

这样即使某些命令尚未完全逆出，也不会导致整条脚本导出失败。

## 6. 当前不建议做的事情

- 不要把 `eliminateRaid` 强行塞进 `GroundGridFlat`。
- 不要继续按 zip 文件名去猜 `FlatBufferData` schema。
- 不要在证据不足时直接宣称“这就是标准 MemoryPack 文件”。

## 7. 建议的下一步

如果后续要继续推进，建议按这个顺序：

1. 先做 `Inspect JSON` 导出，不改 raw 导出。
2. 选一组同 boss、不同 phase 的样本对齐：
   - `normal`
   - `start2phase`
   - `start3phase`
3. 先建立 token / string / offset 层面的稳定规则。
4. 再尝试把已知命令映射到 `GroundCommand* / GroundCondition*` 类型。

当前最适合做第一组建模样本的是：

- `6012301_eliminateRaid_binah_outdoor_unarmed_normal`
- `6012301_eliminateRaid_binah_outdoor_unarmed_normal_start2phase`
- `6012301_eliminateRaid_binah_outdoor_unarmed_normal_start3phase`

因为它们：

- 结构一致
- 内容差异清晰
- 字符串可读性较高
