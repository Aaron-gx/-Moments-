# -*- coding: utf-8 -*-
"""Plotly 交互式图表 — 悬停显示数据（用于 Web 版）"""
import numpy as np
from collections import Counter
from datetime import datetime

import plotly.graph_objects as go
import plotly.express as px

from .config import strip_emoji
from .analysis_time import _collect_time_data
from .analysis_text import (_extract_all_text, _segment_texts, _compute_sentiments,
                            HAVE_JIEBA, HAVE_SNOWNLP)
from .analysis_social import compute_fan_ranking, compute_interaction_decay
from .analysis_spatial import _extract_geotagged_posts


# ─── 时间图表 ──────────────────────────────────────

def plot_hourly_distribution_plotly(posts):
    """24小时发布分布（交互式柱状图）"""
    dts = _collect_time_data(posts)
    if not dts:
        return None
    counts = [0] * 24
    for dt in dts:
        counts[dt.hour] += 1

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[f'{h}:00' for h in range(24)],
        y=counts,
        marker_color=counts,
        marker_colorscale='YlOrRd',
        text=counts,
        textposition='outside',
        hovertemplate='时段: %{x}<br>发布条数: %{y}<extra></extra>',
    ))
    fig.update_layout(
        title='24小时发布分布（你是什么时段的"朋友圈达人"？）',
        xaxis_title='小时',
        yaxis_title='发布条数',
        height=450,
    )
    return fig


def plot_weekly_distribution_plotly(posts):
    """星期发布分布（交互式柱状图）"""
    dts = _collect_time_data(posts)
    if not dts:
        return None
    day_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    counts = [0] * 7
    for dt in dts:
        counts[dt.weekday()] += 1

    colors = ['#4e79a7', '#f28e2b', '#e15759', '#76b7b2',
              '#59a14f', '#edc948', '#b07aa1']
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=day_names,
        y=counts,
        marker_color=colors,
        text=counts,
        textposition='outside',
        hovertemplate='星期: %{x}<br>发布条数: %{y}<extra></extra>',
    ))
    fig.update_layout(
        title='一周发布分布（工作日 vs 周末）',
        yaxis_title='发布条数',
        height=450,
    )
    return fig


def plot_monthly_trend_plotly(posts):
    """月度发布趋势（交互式折线图）"""
    dts = _collect_time_data(posts)
    if not dts:
        return None
    monthly = {}
    for dt in dts:
        key = f"{dt.year}-{dt.month:02d}"
        monthly[key] = monthly.get(key, 0) + 1
    keys = sorted(monthly.keys())
    values = [monthly[k] for k in keys]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=keys, y=values,
        mode='lines+markers',
        fill='tozeroy',
        line_color='#0066cc',
        marker_size=6,
        hovertemplate='月份: %{x}<br>发布条数: %{y}<extra></extra>',
    ))
    fig.update_layout(
        title='月度发布趋势（你的朋友圈活跃度变化）',
        xaxis_title='月份',
        yaxis_title='发布条数',
        height=450,
    )
    return fig


def plot_yearly_trend_plotly(posts):
    """年度发布趋势（交互式柱状图）"""
    dts = _collect_time_data(posts)
    if not dts:
        return None
    yearly = {}
    for dt in dts:
        yearly[dt.year] = yearly.get(dt.year, 0) + 1
    years = sorted(yearly.keys())
    values = [yearly[y] for y in years]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[str(y) for y in years],
        y=values,
        marker_color='#59a14f',
        text=values,
        textposition='outside',
        hovertemplate='年份: %{x}<br>发布条数: %{y}<extra></extra>',
    ))
    fig.update_layout(
        title='年度发布趋势（你的"朋友圈进化史"）',
        xaxis_title='年份',
        yaxis_title='发布条数',
        height=450,
    )
    return fig


# ─── 文本图表 ──────────────────────────────────────

def plot_word_frequency_plotly(posts, top_n=30):
    """高频词柱状图（交互式）"""
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
    safe_labels = [strip_emoji(l) or l for l in labels]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=safe_labels[::-1],
        x=list(values[::-1]),
        orientation='h',
        text=list(values[::-1]),
        textposition='outside',
        marker_color=list(values[::-1]),
        marker_colorscale='Viridis',
        hovertemplate='词汇: %{y}<br>出现次数: %{x}<extra></extra>',
    ))
    fig.update_layout(
        title=f'Top {top_n} 高频词汇',
        xaxis_title='出现次数',
        height=max(500, len(labels) * 22),
    )
    return fig


def plot_sentiment_timeline_plotly(posts):
    """情感时间线（交互式散点图）"""
    if not HAVE_SNOWNLP:
        return None
    results = _compute_sentiments(posts)
    if results is None or not results:
        return None

    results = [(dt, s, c) for dt, s, c in results if dt is not None]
    if not results:
        return None
    results.sort(key=lambda x: x[0])
    dates = [r[0] for r in results]
    scores = [r[1] for r in results]
    previews = [r[2] for r in results]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=scores,
        mode='markers',
        marker=dict(color=scores, colorscale='RdYlGn', size=8, opacity=0.6),
        text=previews,
        hovertemplate='时间: %{x}<br>情感分值: %{y:.3f}<br>内容: %{text}<extra></extra>',
    ))

    # 趋势线
    try:
        x_nums = [dt.toordinal() for dt in dates]
        if len(x_nums) > 5:
            z = np.polyfit(x_nums, scores, 3)
            p = np.poly1d(z)
            x_smooth = np.linspace(min(x_nums), max(x_nums), 200)
            x_smooth_dates = [datetime.fromordinal(int(round(x))) for x in x_smooth]
            fig.add_trace(go.Scatter(
                x=x_smooth_dates, y=p(x_smooth),
                mode='lines',
                line=dict(color='red', width=2),
                name='趋势线',
                hoverinfo='skip',
            ))
    except Exception:
        pass

    fig.update_layout(
        title='"情绪晴雨表" — 你的朋友圈情感曲线',
        xaxis_title='时间',
        yaxis_title='情感分值 (0=消极, 1=积极)',
        yaxis=dict(range=[-0.05, 1.05]),
        height=450,
        shapes=[dict(type='line', yref='y', y0=0.5, y1=0.5,
                     xref='paper', x0=0, x1=1,
                     line=dict(color='gray', dash='dash', width=1))],
    )
    return fig


def plot_sentiment_distribution_plotly(posts):
    """情感分布直方图（交互式）"""
    if not HAVE_SNOWNLP:
        return None
    results = _compute_sentiments(posts)
    if results is None or not results:
        return None
    scores = [s for _, s, _ in results]
    if not scores:
        return None

    mean_score = np.mean(scores)
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=scores,
        nbinsx=20,
        marker_color='#4e79a7',
        opacity=0.8,
        hovertemplate='情感区间: %{x:.2f}<br>条数: %{y}<extra></extra>',
    ))
    fig.add_vline(x=mean_score, line_dash='dash', line_color='red',
                  annotation_text=f'均值: {mean_score:.2f}')
    fig.update_layout(
        title='情感分布（偏左=消极多，偏右=积极多）',
        xaxis_title='情感分值',
        yaxis_title='条数',
        height=450,
    )
    return fig


# ─── 社交图表 ──────────────────────────────────────

def plot_fan_ranking_plotly(posts, publisher_name=None):
    """真爱粉排行榜（交互式分组柱状图）"""
    _, _, combined = compute_fan_ranking(posts, publisher_name)
    if not combined:
        return None

    top = combined[:20]
    names = [strip_emoji(t[0]) or t[0] for t in top]
    likes = [t[1] for t in top]
    comments = [t[2] for t in top]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=names[::-1],
        x=likes[::-1],
        orientation='h',
        name='点赞数',
        marker_color='#4e79a7',
        text=likes[::-1],
        textposition='outside',
        hovertemplate='姓名: %{y}<br>点赞数: %{x}<extra></extra>',
    ))
    fig.add_trace(go.Bar(
        y=names[::-1],
        x=comments[::-1],
        orientation='h',
        name='评论数',
        marker_color='#f28e2b',
        text=comments[::-1],
        textposition='outside',
        hovertemplate='姓名: %{y}<br>评论数: %{x}<extra></extra>',
    ))
    title = f'"真爱粉"排行 Top {min(20, len(top))}'
    if publisher_name:
        title += f'（{publisher_name} 的朋友圈）'
    fig.update_layout(
        title=title,
        xaxis_title='次数',
        barmode='group',
        height=max(500, len(names) * 28),
    )
    return fig


def plot_interaction_decay_plotly(posts, top_n=10, publisher_name=None):
    """互动流失趋势（交互式折线图）"""
    decay_data = compute_interaction_decay(posts, publisher_name)
    if not decay_data:
        return None

    totals = {p: sum(months.values()) for p, months in decay_data.items()}
    top_people = sorted(totals.keys(), key=lambda p: totals[p], reverse=True)[:top_n]
    if not top_people:
        return None

    all_months = set()
    for p in top_people:
        all_months.update(decay_data[p].keys())
    all_months = sorted(all_months)

    palette = px.colors.qualitative.Alphabet + px.colors.qualitative.Dark24
    fig = go.Figure()
    for i, person in enumerate(top_people):
        values = [decay_data[person].get(m, 0) for m in all_months]
        fig.add_trace(go.Scatter(
            x=all_months, y=values,
            mode='lines+markers',
            name=strip_emoji(person) or person,
            line=dict(color=palette[i % len(palette)]),
            hovertemplate=f'{strip_emoji(person) or person}<br>'
                          '月份: %{{x}}<br>互动强度: %{{y}}<extra></extra>',
        ))

    title = '"社交关系半衰期" — 互动流失趋势'
    if publisher_name:
        title += f'（{publisher_name} 的朋友圈）'
    fig.update_layout(
        title=title,
        xaxis_title='月份',
        yaxis_title='互动强度（点赞=1，评论=2）',
        height=500,
    )
    return fig


# ─── 空间图表 ──────────────────────────────────────

def plot_footprint_plotly(posts):
    """足迹地图（交互式散点图）"""
    geo_posts = _extract_geotagged_posts(posts)
    if not geo_posts:
        return None

    lats = [p["latitude"] for p in geo_posts]
    lons = [p["longitude"] for p in geo_posts]
    names = [strip_emoji(p["发布者"]) or p["发布者"] for p in geo_posts]
    contents = [strip_emoji(p["内容"][:50]) for p in geo_posts]
    times = [str(p["时间"]) for p in geo_posts]

    fig = go.Figure()
    fig.add_trace(go.Scattermapbox(
        lat=lats, lon=lons,
        mode='markers',
        marker=dict(size=12, color='#e74c3c', opacity=0.8),
        text=[f"{n}<br>{c}<br>{t}" for n, c, t in zip(names, contents, times)],
        hovertemplate='<b>%{text}</b><extra></extra>',
    ))
    fig.update_layout(
        title=f'个人足迹地图（{len(geo_posts)} 个打卡点）',
        mapbox=dict(
            style='open-street-map',
            center=dict(lat=np.mean(lats), lon=np.mean(lons)),
            zoom=8,
        ),
        height=600,
    )
    return fig
