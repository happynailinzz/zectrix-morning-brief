# Zectrix Morning Brief

为 Zectrix NOTE4 生成每日晨报的本地插件。它抓取天气、日出日落、节假日、农历、干支、节气、五行穿衣和宜忌，渲染为原生 `400x300`、`1BPP` 黑白图片，并通过 Zectrix Cloud API 上传到设备页面。

项目不包含 API Key、设备 ID、个人位置配置或本机绝对路径。配置保存在用户目录，不会写入仓库。

## 功能

- 当前天气、今日最高/最低温度、体感温度、湿度、降水概率和风力
- 24 小时温度柱状图、日出和日落时间
- 农历、干支、节气、日柱、五行、值神、建日
- 五行穿衣颜色、宜忌和穿搭建议
- 原生 `400x300`、`1BPP` 输出，适配 Zectrix 单色墨水屏
- 项目内置 `assets/fonts/Zfull.ttf` 点阵字体，默认无需安装系统字体

## 安装

```bash
git clone https://github.com/happynailinzz/zectrix-morning-brief.git
cd zectrix-morning-brief
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## 初始化

首次运行需要自己的 Zectrix API Key、设备 ID/MAC 和城市。配置写入：

```text
~/.config/zectrix-morning-brief/config.json
```

初始化示例：

```bash
.venv/bin/python scripts/init.py \
  --api-key 'zt_你的APIKey' \
  --device 'AA:BB:CC:DD:EE:FF' \
  --place '你的城市' \
  --label '你的城市' \
  --page '1'
```

初始化会验证 API Key 和设备归属，并通过 Open-Meteo 地理编码城市坐标。API Key 不会写入项目目录，也不会输出到日志。

## 本地预览

只生成固定样例，不联网、不上传：

```bash
.venv/bin/python scripts/morning_brief.py \
  --offline-sample \
  --output /tmp/zectrix-morning-brief-sample.png
```

使用实时数据但不上传：

```bash
ZECTRIX_NO_PUSH=1 .venv/bin/python scripts/morning_brief.py
```

## 生成并上传

```bash
.venv/bin/python scripts/morning_brief.py
```

Cloud API 返回 `PUSH pageId=1 OK` 表示平台接受了请求。设备是拉取式刷新，实际屏幕更新可能发生在下一次设备轮询时。

## 墨水屏渲染约束

- 画布原生 `400x300`，不进行放大后缩小
- 默认字体为 `assets/fonts/Zfull.ttf` 点阵字体
- 二值化阈值固定为 `128`
- 上传参数使用 `dither=false`，避免云端重复抖动导致文字模糊
- 如需临时测试其他字体，可设置 `ZECTRIX_FONT=/path/to/font.ttf`

## 定时运行

项目提供三时段执行脚本，每天运行三次：

- `07:00`：实时抓取当天当前天气和当天黄历
- `16:00`：再次实时抓取当天当前天气和当天黄历
- `21:00`：抓取次日天气预报和次日黄历

```bash
./scripts/run_scheduled.sh
```

脚本默认使用项目内 `.venv/bin/python`，可通过环境变量覆盖解释器和输出路径：

```bash
ZECTRIX_PYTHON=/path/to/python ZECTRIX_OUTPUT=/tmp/morning.png ./scripts/run_scheduled.sh
```

Hermes 或 cron 可每小时调用一次，脚本只会在三个目标小时执行：

```text
0 * * * *
```

也可以使用 cron 只在目标时间调用：

```cron
0 7,16,21 * * * /path/to/zectrix-morning-brief/scripts/run_scheduled.sh
```

晚上模式手动测试：

```bash
ZECTRIX_NO_PUSH=1 .venv/bin/python scripts/morning_brief.py --tomorrow
```

不要把 `~/.config/zectrix-morning-brief/config.json` 写入任务参数、仓库或日志。

## 数据来源

- 天气、日出日落和逐小时温度：[Open-Meteo](https://open-meteo.com/)
- 中国节假日和工作日：[Timor Holiday API](https://timor.tech/api/holiday/)
- 农历、干支、节气、五行和宜忌：[全民万年历](https://www.qmrl888.com/)
- 天气图标：[和风天气图标](https://icons.qweather.com/)
- 点阵字体：随项目分发的 `assets/fonts/Zfull.ttf`

黄历和五行穿衣属于民俗信息，本项目只做展示，不构成日程、健康或决策建议。第三方数据源不可用时，画面会显示“数据暂不可用”，不会把旧数据伪装成当天数据。

## 开发测试

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## 安全说明

提交代码前请确认以下内容没有进入仓库：

- Zectrix API Key
- 设备 ID 或 MAC 地址
- `~/.config/zectrix-morning-brief/config.json`
- 本机绝对路径
- `.venv`、`__pycache__` 和运行日志
