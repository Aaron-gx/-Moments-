# -*- coding: utf-8 -*-
"""增强社交分析：真爱粉排行、互动流失分析"""
from collections import defaultdict, Counter
from datetime import datetime

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from .config import FONT_NAME, strip_emoji

matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False


def _parse_timestamp(post):
    ts = post.get("timestamp", 0)
    if ts and isinstance(ts, (int, float)) and ts > 0:
        try:
            return datetime.fromtimestamp(ts)
        except (OSError, ValueError):
            pass
    return None


def _parse_likes(post):
    """提取点赞者列表"""
    raw = post.get("点赞", "")
    if isinstance(raw, str) and raw.strip():
        return [x.strip() for x in raw.replace("、", "，").split("，") if x.strip()]
    elif isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return []


def _parse_comments(post):
    """提取评论者列表"""
    raw = post.get("评论", [])
    if not isinstance(raw, list):
        return []
    result = []
    for c in raw:
        if isinstance(c, dict):
            name = c.get("nickname", "")
            if name:
                result.append(name)
        elif isinstance(c, str):
            if ':' in c:
                name = c.split(':', 1)[0].strip()
            elif '：' in c:
                name = c.split('：', 1)[0].strip()
            else:
                name = c.strip()
            if name:
                result.append(name)
    return result


def compute_fan_ranking(posts, publisher_name=None):
    """计算粉丝互动排行

    Args:
        posts: 帖子列表
        publisher_name: 指定发布者（分析谁的"真爱粉"），None 表示所有人

    Returns:
        likes_ranking: [(name, count), ...] 点赞排行
        comments_ranking: [(name, count), ...] 评论排行
        combined_ranking: [(name, likes, comments, total), ...] 综合排行
    """
    likes_counter = Counter()
    comments_counter = Counter()

    for post in posts:
        if publisher_name and post.get("发布者", "") != publisher_name:
            continue

        for liker in _parse_likes(post):
            likes_counter[liker] += 1

        for commenter in _parse_comments(post):
            comments_counter[commenter] += 1

    likes_ranking = likes_counter.most_common(30)
    comments_ranking = comments_counter.most_common(30)

    all_people = set(likes_counter.keys()) | set(comments_counter.keys())
    combined = []
    for p in all_people:
        l = likes_counter.get(p, 0)
        c = comments_counter.get(p, 0)
        combined.append((p, l, c, l + c * 2))
    combined.sort(key=lambda x: x[3], reverse=True)

    return likes_ranking, comments_ranking, combined


def plot_fan_ranking(posts, publisher_name=None):
    """真爱粉排行榜（柱状图）"""
    likes_ranking, comments_ranking, combined = compute_fan_ranking(posts, publisher_name)

    if not combined:
        return None

    top = combined[:20]
    names = [strip_emoji(t[0]) or t[0] for t in top]
    likes = [t[1] for t in top]
    comments = [t[2] for t in top]

    fig, ax = plt.subplots(figsize=(12, 7), dpi=100)
    y_pos = np.arange(len(names))
    bar_h = 0.35

    ax.barh(y_pos + bar_h / 2, likes, bar_h, label='点赞数', color='#4e79a7')
    ax.barh(y_pos - bar_h / 2, comments, bar_h, label='评论数', color='#f28e2b')

    # 在柱状图末端标注数值
    for i, (l, c) in enumerate(zip(likes, comments)):
        if l > 0:
            ax.text(l + 0.3, i + bar_h / 2, str(l), va='center', fontsize=7, color='#4e79a7')
        if c > 0:
            ax.text(c + 0.3, i - bar_h / 2, str(c), va='center', fontsize=7, color='#f28e2b')

    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontproperties={'family': FONT_NAME, 'size': 9})
    ax.invert_yaxis()
    ax.set_xlabel('次数', fontproperties={'family': FONT_NAME})
    title = f'"真爱粉"排行 Top {min(20, len(top))}'
    if publisher_name:
        title += f'（{publisher_name} 的朋友圈）'
    ax.set_title(title, fontproperties={'family': FONT_NAME, 'size': 13, 'weight': 'bold'})
    ax.legend(prop={'family': FONT_NAME})
    ax.grid(True, alpha=0.3, axis='x')
    fig.tight_layout()
    return fig


def compute_interaction_decay(posts, publisher_name=None):
    """互动流失分析：跟踪每个人的互动随时间变化

    Returns:
        decay_data: {person: {year_month: interaction_count}}
    """
    person_timeline = defaultdict(lambda: defaultdict(int))

    for post in posts:
        if publisher_name and post.get("发布者", "") != publisher_name:
            continue

        dt = _parse_timestamp(post)
        if not dt:
            continue

        year_month = f"{dt.year}-{dt.month:02d}"

        for liker in _parse_likes(post):
            person_timeline[liker][year_month] += 1

        for commenter in _parse_comments(post):
            person_timeline[commenter][year_month] += 2

    return dict(person_timeline)


def plot_interaction_decay(posts, top_n=10, publisher_name=None):
    """互动流失趋势图"""
    decay_data = compute_interaction_decay(posts, publisher_name)

    if not decay_data:
        return None

    # 取互动总量最高的 top_n 个人
    totals = {p: sum(months.values()) for p, months in decay_data.items()}
    top_people = sorted(totals.keys(), key=lambda p: totals[p], reverse=True)[:top_n]

    if not top_people:
        return None

    # 收集所有月份并排序
    all_months = set()
    for p in top_people:
        all_months.update(decay_data[p].keys())
    all_months = sorted(all_months)

    fig, ax = plt.subplots(figsize=(14, 6), dpi=100)
    colors = plt.cm.tab20(np.linspace(0, 1, len(top_people)))

    for i, person in enumerate(top_people):
        values = [decay_data[person].get(m, 0) for m in all_months]
        ax.plot(all_months, values, 'o-', color=colors[i],
                label=strip_emoji(person) or person, linewidth=1.5, markersize=4)

    ax.set_xlabel('月份', fontproperties={'family': FONT_NAME})
    ax.set_ylabel('互动强度（点赞=1，评论=2）', fontproperties={'family': FONT_NAME})
    title = '"社交关系半衰期" — 互动流失趋势'
    if publisher_name:
        title += f'（{publisher_name} 的朋友圈）'
    ax.set_title(title, fontproperties={'family': FONT_NAME, 'size': 13, 'weight': 'bold'})
    ax.legend(prop={'family': FONT_NAME, 'size': 8}, ncol=2, loc='upper right')
    plt.xticks(rotation=45, fontsize=7)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def generate_social_report(posts, publisher_name=None):
    """社交分析文本报告"""
    lines = []
    likes_ranking, comments_ranking, combined = compute_fan_ranking(posts, publisher_name)

    total_likes = sum(c for _, c in likes_ranking)
    total_comments = sum(c for _, c in comments_ranking)

    lines.append(f"互动数据总览（点赞总计: {total_likes}，评论总计: {total_comments}）")
    lines.append("")

    if combined:
        lines.append(f'"真爱粉" Top 10（点赞+评论加权）：')
        for i, (name, l, c, score) in enumerate(combined[:10], 1):
            lines.append(f"  {i:2d}. {name:20s}  点赞: {l:3d}  评论: {c:3d}  综合分: {score}")
        lines.append("")

    if likes_ranking:
        lines.append(f"点赞王 Top 5：")
        for i, (name, count) in enumerate(likes_ranking[:5], 1):
            lines.append(f"  {i}. {name}: {count} 次")
        lines.append("")

    if comments_ranking:
        lines.append(f"评论王 Top 5：")
        for i, (name, count) in enumerate(comments_ranking[:5], 1):
            lines.append(f"  {i}. {name}: {count} 次")

    return "\n".join(lines)


def show_social_analysis_window(master, posts):
    """在独立窗口中展示社交分析"""
    import tkinter as tk
    from tkinter import ttk

    win = tk.Toplevel(master)
    win.title("增强社交分析")
    win.geometry("1100x750")

    btn_frame = ttk.Frame(win)
    btn_frame.pack(fill='x', padx=10, pady=8)

    fig_container = ttk.Frame(win)
    fig_container.pack(fill='both', expand=True, padx=10, pady=5)

    report_text = tk.Text(fig_container, wrap='word', font=(FONT_NAME, 11), height=10)
    report_text.pack(fill='x', pady=(0, 5))
    report_text.insert('1.0', generate_social_report(posts))
    report_text.configure(state='disabled')

    chart_frame = ttk.Frame(fig_container)
    chart_frame.pack(fill='both', expand=True)

    current_fig = [None]

    def show_chart(plot_func, **kwargs):
        for w in chart_frame.winfo_children():
            w.destroy()
        if current_fig[0]:
            plt.close(current_fig[0])
        fig = plot_func(posts, **kwargs)
        if fig is None:
            return
        current_fig[0] = fig
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

    charts = [
        ("真爱粉排行", lambda: show_chart(plot_fan_ranking)),
        ("互动流失趋势", lambda: show_chart(plot_interaction_decay)),
    ]
    for text, cmd in charts:
        ttk.Button(btn_frame, text=text, command=cmd, width=14).pack(side='left', padx=3)

    show_chart(plot_fan_ranking)
