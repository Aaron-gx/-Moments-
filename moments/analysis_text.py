# -*- coding: utf-8 -*-
"""文本与情感分析：词云、情感倾向、话题统计"""
import os
import re
from collections import Counter

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from .config import FONT_NAME, strip_emoji

matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False

try:
    import jieba
    HAVE_JIEBA = True
except ImportError:
    HAVE_JIEBA = False

try:
    from wordcloud import WordCloud
    HAVE_WORDCLOUD = True
except ImportError:
    HAVE_WORDCLOUD = False

try:
    from snownlp import SnowNLP
    HAVE_SNOWNLP = True
except ImportError:
    HAVE_SNOWNLP = False

STOP_WORDS = set(
    "的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己 "
    "这 他 她 它 们 那 里 后 来 还 把 被而 但 与 或 从 中 对 为 之 让 被 其 可以 这个 那个 "
    "什么 怎么 如何 为什么 没 嘛 呀 吧 啊 呢 哦 哈 嗯 啦 哦 哈哈 哈哈哈 嘿嘿 呵呵 "
    "嗯嗯 不是 可以 已经 可能 因为 所以 如果 虽然 但是 不过 而且 或者 以及".split()
)

FONT_PATH = None
for candidate in [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
]:
    if os.path.exists(candidate):
        FONT_PATH = candidate
        break


def _extract_all_text(posts):
    """提取所有帖子文本内容"""
    texts = []
    for post in posts:
        content = post.get("内容", "")
        if content and content.strip():
            texts.append(content.strip())
    return texts


def _segment_texts(texts):
    """中文分词"""
    if not HAVE_JIEBA:
        return None

    all_words = []
    for text in texts:
        words = jieba.lcut(text)
        for w in words:
            w = w.strip()
            if len(w) >= 2 and w not in STOP_WORDS and not re.match(r'^[\W\d]+$', w):
                all_words.append(w)
    return all_words


def plot_wordcloud(posts):
    """生成词云"""
    if not HAVE_WORDCLOUD or not HAVE_JIEBA:
        return None

    texts = _extract_all_text(posts)
    if not texts:
        return None

    words = _segment_texts(texts)
    if not words:
        return None

    word_freq = Counter(words)
    if not word_freq:
        return None

    wc = WordCloud(
        font_path=FONT_PATH or "msyh.ttc",
        width=1000, height=600,
        background_color='white',
        max_words=200,
        max_font_size=120,
        colormap='viridis',
    )
    wc.generate_from_frequencies(word_freq)

    fig, ax = plt.subplots(figsize=(12, 7), dpi=100)
    ax.imshow(wc, interpolation='bilinear')
    ax.axis('off')
    ax.set_title('朋友圈高频词云（你的"精神内核"）',
                fontproperties={'family': FONT_NAME, 'size': 14, 'weight': 'bold'})
    fig.tight_layout()
    return fig


def plot_word_frequency(posts, top_n=30):
    """词频柱状图"""
    if not HAVE_JIEBA:
        return None

    texts = _extract_all_text(posts)
    if not texts:
        return None

    words = _segment_texts(texts)
    if not words:
        return None

    counter = Counter(words).most_common(top_n)
    if not counter:
        return None

    labels, values = zip(*counter)

    fig, ax = plt.subplots(figsize=(12, 7), dpi=100)
    colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(labels)))
    bars = ax.barh(range(len(labels)), values, color=colors)
    ax.set_yticks(range(len(labels)))
    safe_labels = [strip_emoji(l) or l for l in labels]
    ax.set_yticklabels(safe_labels, fontproperties={'family': FONT_NAME, 'size': 10})
    ax.invert_yaxis()
    ax.set_xlabel('出现次数', fontproperties={'family': FONT_NAME})
    ax.set_title(f'Top {top_n} 高频词汇',
                fontproperties={'family': FONT_NAME, 'size': 13, 'weight': 'bold'})
    ax.grid(True, alpha=0.3, axis='x')
    fig.tight_layout()
    return fig


def _compute_sentiments(posts):
    """计算情感分值列表"""
    if not HAVE_SNOWNLP:
        return None, None

    from datetime import datetime
    results = []
    for post in posts:
        content = post.get("内容", "")
        if not content or not content.strip():
            continue

        try:
            s = SnowNLP(content)
            score = s.sentiments
        except Exception:
            continue

        ts = post.get("timestamp", 0)
        dt = None
        if ts and isinstance(ts, (int, float)) and ts > 0:
            try:
                dt = datetime.fromtimestamp(ts)
            except (OSError, ValueError):
                pass

        if dt is None:
            time_str = str(post.get("时间", "")).strip()
            for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(time_str, fmt)
                    break
                except ValueError:
                    continue

        results.append((dt, score, content[:50]))
    return results


def plot_sentiment_timeline(posts):
    """情感时间线图"""
    results = _compute_sentiments(posts)
    if results is None or not results:
        return None

    results = [(dt, s, c) for dt, s, c in results if dt is not None]
    if not results:
        return None

    results.sort(key=lambda x: x[0])
    dates = [r[0] for r in results]
    scores = [r[1] for r in results]

    fig, ax = plt.subplots(figsize=(12, 5), dpi=100)
    ax.scatter(dates, scores, c=scores, cmap='RdYlGn', s=20, alpha=0.6, edgecolors='none')

    from numpy.polynomial.polynomial import polyfit
    try:
        import matplotlib.dates as mdates
        x_num = mdates.date2num(dates)
        if len(x_num) > 5:
            z = np.polyfit(x_num, scores, 3)
            p = np.poly1d(z)
            x_smooth = np.linspace(x_num.min(), x_num.max(), 200)
            ax.plot(mdates.num2date(x_smooth), p(x_smooth), 'r-', linewidth=2, alpha=0.7, label='趋势线')
            ax.legend(prop={'family': FONT_NAME})
    except Exception:
        pass

    ax.set_ylim(-0.05, 1.05)
    ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5)
    ax.set_xlabel('时间', fontproperties={'family': FONT_NAME})
    ax.set_ylabel('情感分值 (0=消极, 1=积极)', fontproperties={'family': FONT_NAME})
    ax.set_title('"情绪晴雨表" — 你的朋友圈情感曲线',
                fontproperties={'family': FONT_NAME, 'size': 13, 'weight': 'bold'})
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def plot_sentiment_distribution(posts):
    """情感分布直方图"""
    results = _compute_sentiments(posts)
    if results is None or not results:
        return None

    scores = [s for _, s, _ in results]
    if not scores:
        return None

    fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
    ax.hist(scores, bins=20, color='#4e79a7', edgecolor='white', alpha=0.8)
    ax.axvline(x=np.mean(scores), color='red', linestyle='--', linewidth=2, label=f'均值: {np.mean(scores):.2f}')
    ax.set_xlabel('情感分值', fontproperties={'family': FONT_NAME})
    ax.set_ylabel('条数', fontproperties={'family': FONT_NAME})
    ax.set_title('情感分布（偏左=消极多，偏右=积极多）',
                fontproperties={'family': FONT_NAME, 'size': 13, 'weight': 'bold'})
    ax.legend(prop={'family': FONT_NAME})
    fig.tight_layout()
    return fig


def generate_text_report(posts):
    """文本分析文本报告"""
    lines = []
    texts = _extract_all_text(posts)
    lines.append(f"共有 {len(texts)} 条文字内容")
    lines.append("")

    if not HAVE_JIEBA:
        lines.append("需要安装 jieba 库才能进行文本分析：pip install jieba")
        return "\n".join(lines)

    words = _segment_texts(texts)
    if words:
        counter = Counter(words).most_common(20)
        lines.append("Top 20 高频词：")
        for i, (w, c) in enumerate(counter, 1):
            lines.append(f"  {i:2d}. {w:10s} {c} 次")
        lines.append("")

    if HAVE_SNOWNLP:
        results = _compute_sentiments(posts)
        if results:
            scores = [s for _, s, _ in results]
            avg = np.mean(scores)
            pos_ratio = sum(1 for s in scores if s > 0.6) / len(scores) * 100
            neg_ratio = sum(1 for s in scores if s < 0.4) / len(scores) * 100

            lines.append(f"情感分析（共分析 {len(scores)} 条）：")
            lines.append(f"  平均情感分值：{avg:.3f} ({'偏积极' if avg > 0.5 else '偏消极'})")
            lines.append(f"  积极内容占比：{pos_ratio:.1f}%")
            lines.append(f"  消极内容占比：{neg_ratio:.1f}%")
            lines.append("")

            most_positive = max(results, key=lambda x: x[1])
            most_negative = min(results, key=lambda x: x[1])
            lines.append(f"  最积极的一条：{most_positive[2]}... (分值: {most_positive[1]:.3f})")
            lines.append(f"  最消极的一条：{most_negative[2]}... (分值: {most_negative[1]:.3f})")

    return "\n".join(lines)


def show_text_analysis_window(master, posts):
    """在独立窗口中展示文本分析"""
    import tkinter as tk
    from tkinter import ttk

    win = tk.Toplevel(master)
    win.title("文本与情感分析")
    win.geometry("1100x750")

    btn_frame = ttk.Frame(win)
    btn_frame.pack(fill='x', padx=10, pady=8)

    fig_container = ttk.Frame(win)
    fig_container.pack(fill='both', expand=True, padx=10, pady=5)

    report_text = tk.Text(fig_container, wrap='word', font=(FONT_NAME, 11), height=8)
    report_text.pack(fill='x', pady=(0, 5))
    report_text.insert('1.0', generate_text_report(posts))
    report_text.configure(state='disabled')

    chart_frame = ttk.Frame(fig_container)
    chart_frame.pack(fill='both', expand=True)

    current_fig = [None]

    def show_chart(plot_func):
        for w in chart_frame.winfo_children():
            w.destroy()
        if current_fig[0]:
            plt.close(current_fig[0])
        fig = plot_func(posts)
        if fig is None:
            from tkinter import messagebox
            missing = []
            if not HAVE_JIEBA:
                missing.append("jieba")
            if not HAVE_WORDCLOUD:
                missing.append("wordcloud")
            if not HAVE_SNOWNLP:
                missing.append("snownlp")
            if missing:
                messagebox.showinfo("提示", f"需要安装：pip install {' '.join(missing)}")
            return
        current_fig[0] = fig
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

    charts = [
        ("词云", lambda: show_chart(plot_wordcloud)),
        ("高频词", lambda: show_chart(plot_word_frequency)),
        ("情感曲线", lambda: show_chart(plot_sentiment_timeline)),
        ("情感分布", lambda: show_chart(plot_sentiment_distribution)),
    ]
    for text, cmd in charts:
        ttk.Button(btn_frame, text=text, command=cmd, width=12).pack(side='left', padx=3)

    show_chart(plot_wordcloud)
