---
name: zectrix-morning-brief
description: 为 Zectrix NOTE4 生成并推送每日晨报，包含天气、农历、节庆节假日、节气、五行穿衣和宜忌。触发词：晨报屏、城市天气屏、黄历屏、五行穿衣、Zectrix 晨报。
---

# Zectrix 晨报屏

运行 `scripts/morning_brief.py`，生成原生 `400x300` 黑白墨水屏画面，并通过 Zectrix Cloud API 推送到配置的 `pageId`。

首次使用先运行：

```bash
python3 scripts/init.py
```

需要用户提供自己的 Zectrix API Key、设备 MAC 和城市，不要猜测或使用示例凭据。

日常运行：

```bash
python3 scripts/morning_brief.py
```

只预览不推送：

```bash
ZECTRIX_NO_PUSH=1 python3 scripts/morning_brief.py
```

调试固定样例：

```bash
python3 scripts/morning_brief.py --offline-sample
```

页面内容：

- 顶部：城市、日期、星期。
- 天气：天气状况、当前温度、体感、湿度、最高/最低温度和降水提示。
- 日历：农历、节庆/节假日、工作日或休息日、节气。
- 五行穿衣：贵人色、合作色、进财色、消耗色、不利色。
- 黄历：宜、忌和日柱/值神摘要。

不要将 API Key 输出到日志。画面使用项目内点阵字体，原生 `400x300`、`1BPP` 输出，阈值为 `128`，推送接口使用 `dither=false`；云端返回成功只表示请求被平台接受，不代表设备已经完成物理刷新。
