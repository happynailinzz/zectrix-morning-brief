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

## 部署到 Hermes Agent VPS

插件运行在 VPS 上，NOTE4 不需要安装 Python。VPS 需要满足：

- 能访问 Zectrix Cloud、Open-Meteo、Timor API 和全民万年历
- 服务器持续运行，不能在计划时间休眠
- 使用与设备所在地区一致的时区；脚本默认使用 `Asia/Shanghai`
- 已安装 Python 3、`venv` 和 Git

### 1. 下载并安装

以普通用户登录 VPS，建议不要使用 root 运行：

```bash
mkdir -p ~/services
cd ~/services
git clone https://github.com/happynailinzz/zectrix-morning-brief.git
cd zectrix-morning-brief
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
chmod +x scripts/run_scheduled.sh
```

### 2. 初始化设备配置

在 VPS 上执行一次初始化。API Key 不要写入 shell 历史，推荐省略命令行参数，让程序安全读取输入：

```bash
.venv/bin/python scripts/init.py
```

按提示输入 API Key、设备 ID/MAC、城市和页面号。配置会写入：

```text
~/.config/zectrix-morning-brief/config.json
```

检查权限：

```bash
chmod 700 ~/.config/zectrix-morning-brief
chmod 600 ~/.config/zectrix-morning-brief/config.json
```

不要把配置放到 Git 仓库、Hermes 任务参数、公开环境变量或日志中。

### 3. Hermes Agent 配置

在 Hermes 中创建本地 `no_agent` 任务，让 Hermes 只负责调度，脚本负责取数、渲染和上传。任务命令使用 VPS 上的绝对路径：

```bash
/home/你的用户名/services/zectrix-morning-brief/scripts/run_scheduled.sh
```

调度表达式使用每小时整点：

```text
0 * * * *
```

脚本只会在 `07:00`、`16:00` 和 `21:00` 执行，其余整点直接退出，不会访问数据源。`21:00` 自动使用 `--tomorrow`，推送次日天气预报和次日黄历。

不同 Hermes 版本的 cron 创建命令可能不同，先在 VPS 上查看：

```bash
hermes cron --help
```

### 4. 不使用 Hermes 时的 cron

VPS 也可以直接使用系统 cron。编辑当前用户的 crontab：

```bash
crontab -e
```

添加：

```cron
CRON_TZ=Asia/Shanghai
0 * * * * /home/你的用户名/services/zectrix-morning-brief/scripts/run_scheduled.sh >> /tmp/zectrix-morning-brief.log 2>&1
```

或者只在三个时段调用：

```cron
CRON_TZ=Asia/Shanghai
0 7,16,21 * * * /home/你的用户名/services/zectrix-morning-brief/scripts/run_scheduled.sh >> /tmp/zectrix-morning-brief.log 2>&1
```

日志只应记录运行状态和数据源错误，不应记录 `config.json` 或 API Key。检查最近日志：

```bash
tail -n 100 /tmp/zectrix-morning-brief.log
```

### 5. VPS 上线前测试

先做离线渲染，再做真实数据但不推送，最后确认上传：

```bash
cd ~/services/zectrix-morning-brief

# 不联网、不上传
.venv/bin/python scripts/morning_brief.py --offline-sample --output /tmp/morning-sample.png

# 抓取当天数据，但不上传
ZECTRIX_NO_PUSH=1 .venv/bin/python scripts/morning_brief.py --output /tmp/morning-today.png

# 抓取次日天气和黄历，但不上传
ZECTRIX_NO_PUSH=1 .venv/bin/python scripts/morning_brief.py --tomorrow --output /tmp/morning-tomorrow.png

# 确认无误后才执行真实上传
.venv/bin/python scripts/morning_brief.py
```

检查 VPS 当前时区和脚本计划小时：

```bash
ZECTRIX_TIMEZONE=Asia/Shanghai scripts/run_scheduled.sh
```

最后一条命令在非计划时段只会输出“跳过”，不会抓取或上传。

## 数据来源

- 天气、日出日落和逐小时温度：[Open-Meteo](https://open-meteo.com/)
- 中国节假日和工作日：[Timor Holiday API](https://timor.tech/api/holiday/)
- 农历、干支、节气、五行和宜忌：[全民万年历](https://www.qmrl888.com/)
- 天气图标：[和风天气图标](https://icons.qweather.com/)
- 点阵字体：随项目分发的 `assets/fonts/Zfull.ttf`

黄历和五行穿衣属于民俗信息，本项目只做展示，不构成日程、健康或决策建议。第三方数据源不可用时，画面会显示“数据暂不可用”，不会把旧数据伪装成当天数据。

如果 VPS 网络短暂抖动，天气、节假日和黄历请求各自会自动重试一次。重试仍失败时，日志会标明具体数据源，例如 `[Open-Meteo天气]`、`[Timor节假日]` 或 `[全民万年历黄历]`，便于排查；程序仍会生成带“数据暂不可用”提示的图片。

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
