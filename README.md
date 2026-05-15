# 微信朋友圈数据分析工具

基于 Python 的微信朋友圈数据多维度分析工具。导入朋友圈数据后，一键生成社交图谱、时间洞察、文本情感分析、互动排行和足迹地图。
数据导出推荐使用另一个开源项目WeFlow，地址：https://github.com/hicccc77/WeFlow

## 功能

- **数据导入** — 支持 JSON / Excel，自动识别 arkmejson 等第三方导出格式
- **Web 可视化** — 基于 Streamlit 的 Web 界面，数据表格可排序筛选，图谱可缩放拖拽
- **微信采集** — 通过 UI 自动化从微信桌面版采集朋友圈（需 3.9.10 版本）
- **社交图谱** — 交互式网络可视化、社区检测、桥梁人物识别（支持缩放/拖拽/悬停）
- **时间洞察** — 24h 发布热力图、周/月/年度趋势
- **文本分析** — 词云、高频词统计、情感曲线
- **互动排行** — "真爱粉"排行、互动流失分析
- **足迹地图** — 带地理定位的动态可视化地图
- **自动别名** — 智能合并同一人的不同昵称/备注名

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/Aaron-gx/WeChat-Moments-scraping-tool.git
cd WeChat-Moments-scraping-tool

# 2. 安装依赖
pip install -r requirements.txt

# 3a. 启动 Web 版（推荐）
streamlit run web_app.py

# 3b. 或启动桌面版（用于微信采集）
python main.py
```

## 使用方法

三步完成分析：

1. **导入文件** — 在侧边栏上传 JSON 或 Excel 数据文件
2. **一键分析** — 点击「一键分析」，自动完成所有计算
3. **查看结果** — 在「数据 / 图谱 / 时间 / 文本 / 互动 / 地图」标签页中浏览

### Web 版 vs 桌面版

| 功能 | Web 版 (`web_app.py`) | 桌面版 (`main.py`) |
|------|----------------------|-------------------|
| 数据分析 | ✅ | ✅ |
| 图表可视化 | ✅ | ✅ |
| 图谱缩放拖拽 | ✅ 交互式 | ❌ |
| 数据排序筛选 | ✅ | ❌ |
| 微信采集 | ❌ | ✅ |

## 支持的数据格式

| 格式 | 说明 |
|------|------|
| 原生 JSON | 工具采集后导出的 `[{"编号":1, "发布者":"...", ...}]` 格式 |
| arkmejson | 第三方导出工具生成的 `{"format":"arkmejson", "posts":[...]}` 格式 |
| Excel (.xlsx/.xls) | 包含 编号/发布者/内容/时间/点赞/评论 列的表格 |

## 项目结构

```
├── web_app.py              # Web 版入口（Streamlit）
├── main.py                 # 桌面版入口（tkinter，含微信采集）
├── requirements.txt        # 依赖
├── moments/
│   ├── app.py              # 桌面版主界面
│   ├── config.py           # 配置常量
│   ├── importer.py         # 数据导入（多格式兼容）
│   ├── scraper.py          # 微信采集
│   ├── analyzer.py         # 网络分析 + 自动别名
│   ├── visualizer.py       # 关系图谱可视化（桌面版）
│   ├── analysis_time.py    # 时间维度分析
│   ├── analysis_text.py    # 文本与情感分析
│   ├── analysis_social.py  # 互动排行分析
│   └── analysis_spatial.py # 足迹地图
```

## 依赖

| 库 | 用途 |
|----|------|
| streamlit | Web 界面框架 |
| pyvis | 交互式网络图可视化 |
| pandas, openpyxl | 数据处理与 Excel 支持 |
| networkx, python-louvain | 社交网络分析与社区检测 |
| matplotlib | 图表可视化 |
| jieba, wordcloud | 中文分词与词云 |
| snownlp | 中文情感分析 |
| rapidfuzz | 模糊名称匹配 |
| pywinauto, psutil | 微信 UI 自动化采集 |

## 系统要求

- Python 3.8+
- Windows（采集功能需要，Web 分析可跨平台）
- 微信桌面版 3.9.10（仅采集功能需要）

## 许可证

MIT License

## 声明

本工具仅供个人学习研究使用。请遵守相关法律法规和微信平台使用协议，不得用于未经授权的数据采集或传播他人隐私信息。
