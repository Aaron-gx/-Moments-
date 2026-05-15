# -*- coding: utf-8 -*-
"""空间足迹分析：用 matplotlib 替代 folium，无外部 CDN 依赖"""
from collections import Counter

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from .config import FONT_NAME, strip_emoji

matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False


def _extract_geotagged_posts(posts):
    """提取带有效地理定位的帖子"""
    results = []
    for post in posts:
        lat = post.get("latitude", 0)
        lon = post.get("longitude", 0)
        if not lat or not lon:
            continue
        if abs(lat) < 0.001 and abs(lon) < 0.001:
            continue
        results.append({
            "发布者": post.get("发布者", ""),
            "内容": post.get("内容", ""),
            "时间": post.get("时间", ""),
            "latitude": lat,
            "longitude": lon,
        })
    return results


def plot_footprint(posts):
    """生成足迹散点地图（纯 matplotlib，无 CDN 依赖）"""
    geo_posts = _extract_geotagged_posts(posts)
    if not geo_posts:
        return None

    lats = [p["latitude"] for p in geo_posts]
    lons = [p["longitude"] for p in geo_posts]

    fig, ax = plt.subplots(figsize=(10, 7), dpi=100)

    scatter = ax.scatter(lons, lats, c='#e74c3c', s=80, alpha=0.8,
                         edgecolors='#c0392b', linewidths=1.5, zorder=5)

    for p in geo_posts:
        label = strip_emoji(p["发布者"]) or p["发布者"]
        content_preview = strip_emoji(p["内容"][:15] + "...") if len(p["内容"]) > 15 else strip_emoji(p["内容"])
        ax.annotate(f"{label}\n{content_preview}",
                    xy=(p["longitude"], p["latitude"]),
                    fontsize=7, fontproperties={'family': FONT_NAME, 'size': 7},
                    xytext=(5, 5), textcoords='offset points',
                    alpha=0.8)

    # 添加网格和基本装饰
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_xlabel('经度', fontproperties={'family': FONT_NAME})
    ax.set_ylabel('纬度', fontproperties={'family': FONT_NAME})
    ax.set_title(f'个人足迹地图（{len(geo_posts)} 个打卡点）',
                fontproperties={'family': FONT_NAME, 'size': 13, 'weight': 'bold'})

    margin = 0.5
    ax.set_xlim(min(lons) - margin, max(lons) + margin)
    ax.set_ylim(min(lats) - margin, max(lats) + margin)

    fig.tight_layout()
    return fig


def generate_spatial_report(posts):
    """空间分析报告"""
    geo_posts = _extract_geotagged_posts(posts)

    lines = []
    lines.append(f"共 {len(posts)} 条朋友圈中，{len(geo_posts)} 条带有地理定位信息。")
    lines.append("")

    if not geo_posts:
        lines.append("当前数据中未发现有效的地理定位数据。")
        lines.append("")
        lines.append("提示：朋友圈数据中的 location 字段大多为 (0, 0)，")
        lines.append("只有发布时主动添加了位置信息的动态才会有有效坐标。")
        return "\n".join(lines)

    locations = Counter()
    for p in geo_posts:
        key = f"({p['latitude']:.2f}, {p['longitude']:.2f})"
        locations[key] += 1

    lines.append("打卡位置 Top 10：")
    for i, (loc, count) in enumerate(locations.most_common(10), 1):
        lines.append(f"  {i}. {loc}: {count} 次")

    return "\n".join(lines)
