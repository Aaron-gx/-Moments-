# -*- coding: utf-8 -*-
"""时间维度分析：24h热力图、周/月周期、年际趋势"""
from datetime import datetime

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

from .config import FONT_NAME

matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False


def _parse_timestamp(post):
    """从 post 中提取 datetime 对象"""
    ts = post.get("timestamp", 0)
    if ts and isinstance(ts, (int, float)) and ts > 0:
        try:
            return datetime.fromtimestamp(ts)
        except (OSError, ValueError):
            pass

    time_str = str(post.get("时间", "")).strip()
    if not time_str:
        return None

    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y年%m月%d日", "%m月%d日"):
        try:
            dt = datetime.strptime(time_str, fmt)
            if dt.year == 1900:
                dt = dt.replace(year=datetime.now().year)
            return dt
        except ValueError:
            continue
    return None


def _collect_time_data(posts):
    """收集所有帖子的时间信息"""
    datetimes = []
    for post in posts:
        dt = _parse_timestamp(post)
        if dt:
            datetimes.append(dt)
    return datetimes


def plot_hourly_distribution(posts):
    """24小时发布分布图"""
    dts = _collect_time_data(posts)
    if not dts:
        return None

    hours = [dt.hour for dt in dts]
    counts = [0] * 24
    for h in hours:
        counts[h] += 1

    fig, ax = plt.subplots(figsize=(10, 5), dpi=100)
    colors = plt.cm.YlOrRd(np.linspace(0.2, 0.9, 24))
    bars = ax.bar(range(24), counts, color=colors, edgecolor='#666', linewidth=0.5)

    for bar, count in zip(bars, counts):
        if count > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                    str(count), ha='center', va='bottom', fontsize=8)

    ax.set_xlabel('小时', fontproperties={'family': FONT_NAME})
    ax.set_ylabel('发布条数', fontproperties={'family': FONT_NAME})
    ax.set_title('24小时发布分布（你是什么时段的"朋友圈达人"？）',
                fontproperties={'family': FONT_NAME, 'size': 13, 'weight': 'bold'})
    ax.set_xticks(range(24))
    ax.set_xticklabels([f'{h}:00' for h in range(24)], rotation=45, fontsize=7)
    fig.tight_layout()
    return fig


def plot_weekly_distribution(posts):
    """星期发布分布图"""
    dts = _collect_time_data(posts)
    if not dts:
        return None

    day_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    counts = [0] * 7
    for dt in dts:
        counts[dt.weekday()] += 1

    fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
    colors = ['#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f', '#edc948', '#b07aa1']
    bars = ax.bar(day_names, counts, color=colors, edgecolor='#333', linewidth=0.5)

    for bar, count in zip(bars, counts):
        if count > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                    str(count), ha='center', va='bottom', fontsize=10)

    ax.set_ylabel('发布条数', fontproperties={'family': FONT_NAME})
    ax.set_title('一周发布分布（工作日 vs 周末）',
                fontproperties={'family': FONT_NAME, 'size': 13, 'weight': 'bold'})
    fig.tight_layout()
    return fig


def plot_monthly_trend(posts):
    """月度发布趋势图"""
    dts = _collect_time_data(posts)
    if not dts:
        return None

    monthly = {}
    for dt in dts:
        key = f"{dt.year}-{dt.month:02d}"
        monthly[key] = monthly.get(key, 0) + 1

    keys = sorted(monthly.keys())
    values = [monthly[k] for k in keys]

    fig, ax = plt.subplots(figsize=(12, 5), dpi=100)
    ax.plot(keys, values, 'o-', color='#0066cc', linewidth=2, markersize=5)
    ax.fill_between(range(len(keys)), values, alpha=0.15, color='#0066cc')

    ax.set_xlabel('月份', fontproperties={'family': FONT_NAME})
    ax.set_ylabel('发布条数', fontproperties={'family': FONT_NAME})
    ax.set_title('月度发布趋势（你的朋友圈活跃度变化）',
                fontproperties={'family': FONT_NAME, 'size': 13, 'weight': 'bold'})
    plt.xticks(rotation=45, fontsize=7)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def plot_yearly_trend(posts):
    """年度发布趋势图"""
    dts = _collect_time_data(posts)
    if not dts:
        return None

    yearly = {}
    for dt in dts:
        yearly[dt.year] = yearly.get(dt.year, 0) + 1

    years = sorted(yearly.keys())
    values = [yearly[y] for y in years]

    fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
    ax.bar([str(y) for y in years], values, color='#59a14f', edgecolor='#333', linewidth=0.5)

    for i, (y, v) in enumerate(zip(years, values)):
        ax.text(i, v + 0.3, str(v), ha='center', va='bottom', fontsize=10)

    ax.set_xlabel('年份', fontproperties={'family': FONT_NAME})
    ax.set_ylabel('发布条数', fontproperties={'family': FONT_NAME})
    ax.set_title('年度发布趋势（你的"朋友圈进化史"）',
                fontproperties={'family': FONT_NAME, 'size': 13, 'weight': 'bold'})
    fig.tight_layout()
    return fig


def generate_time_report(posts):
    """生成时间分析的文本报告"""
    dts = _collect_time_data(posts)
    if not dts:
        return "无法解析时间数据。"

    hours = [dt.hour for dt in dts]
    from collections import Counter
    hour_counts = Counter(hours)
    peak_hour = hour_counts.most_common(1)[0]

    day_counts = Counter(dt.weekday() for dt in dts)
    day_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    peak_day = day_counts.most_common(1)[0]

    yearly = Counter(dt.year for dt in dts)

    lines = [
        f"共有 {len(dts)} 条带时间信息的朋友圈",
        f"",
        f"最爱发朋友圈的时段：{peak_hour[0]}:00-{peak_hour[0]+1}:00（{peak_hour[1]} 条）",
        f"最爱发朋友圈的星期：{day_names[peak_day[0]]}（{peak_day[1]} 条）",
        f"最早一条：{dts[-1].strftime('%Y-%m-%d %H:%M')}",
        f"最新一条：{dts[0].strftime('%Y-%m-%d %H:%M')}",
        f"覆盖年份：{', '.join(str(y) for y in sorted(yearly.keys()))}",
        f"",
        f"夜猫子指数（22:00-06:00发布比例）：{sum(1 for h in hours if h >= 22 or h < 6) / len(hours) * 100:.1f}%",
        f"早起鸟指数（06:00-09:00发布比例）：{sum(1 for h in hours if 6 <= h < 9) / len(hours) * 100:.1f}%",
    ]
    return "\n".join(lines)


def show_time_analysis_window(master, posts):
    """在独立窗口中展示时间分析"""
    import tkinter as tk
    from tkinter import ttk

    win = tk.Toplevel(master)
    win.title("时间维度分析")
    win.geometry("1100x750")

    btn_frame = ttk.Frame(win)
    btn_frame.pack(fill='x', padx=10, pady=8)

    fig_container = ttk.Frame(win)
    fig_container.pack(fill='both', expand=True, padx=10, pady=5)

    report_text = tk.Text(fig_container, wrap='word', font=(FONT_NAME, 11), height=6)
    report_text.pack(fill='x', pady=(0, 5))
    report_text.insert('1.0', generate_time_report(posts))
    report_text.configure(state='disabled')

    chart_frame = ttk.Frame(fig_container)
    chart_frame.pack(fill='both', expand=True)

    current_fig = [None]

    def show_chart(plot_func, title):
        for w in chart_frame.winfo_children():
            w.destroy()
        if current_fig[0]:
            plt.close(current_fig[0])
        fig = plot_func(posts)
        if fig is None:
            return
        current_fig[0] = fig
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

    charts = [
        ("24小时分布", lambda: show_chart(plot_hourly_distribution, "24h")),
        ("周分布", lambda: show_chart(plot_weekly_distribution, "周")),
        ("月度趋势", lambda: show_chart(plot_monthly_trend, "月")),
        ("年度趋势", lambda: show_chart(plot_yearly_trend, "年")),
    ]
    for text, cmd in charts:
        ttk.Button(btn_frame, text=text, command=cmd, width=12).pack(side='left', padx=3)

    show_chart(plot_hourly_distribution, "24h")
