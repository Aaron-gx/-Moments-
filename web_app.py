# -*- coding: utf-8 -*-
"""微信朋友圈数据分析 — Web 版 (Streamlit)"""
import os
import sys
import tempfile

import streamlit as st
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import networkx as nx

matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False

# 确保能 import moments 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from moments.importer import import_file as load_import_file
from moments.analyzer import (build_interaction_graph, analyze_graph,
                              auto_alias, format_time_display)
from moments.analysis_time import generate_time_report
from moments.analysis_text import plot_wordcloud, generate_text_report
from moments.analysis_social import generate_social_report
from moments.analysis_spatial import generate_spatial_report
from moments.plotly_charts import (
    plot_hourly_distribution_plotly, plot_weekly_distribution_plotly,
    plot_monthly_trend_plotly, plot_yearly_trend_plotly,
    plot_word_frequency_plotly, plot_sentiment_timeline_plotly,
    plot_sentiment_distribution_plotly,
    plot_fan_ranking_plotly, plot_interaction_decay_plotly,
    plot_footprint_plotly,
)
from moments.config import FONT_NAME, strip_emoji, LIKE_WEIGHT, COMMENT_WEIGHT

st.set_page_config(page_title="微信朋友圈数据分析", layout="wide",
                   page_icon="📊")

# ──────────────────────────────
# 状态管理
# ──────────────────────────────
def init_state():
    defaults = {
        'posts': [],
        'filtered_posts': [],
        'graph': None,
        'analysis': None,
        'alias_map': {},
        'owner_name': None,
        'analyzed': False,
        'logs': [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


def log(msg):
    st.session_state.logs.append(msg)


# ──────────────────────────────
# 分析逻辑
# ──────────────────────────────
def do_analysis(owner):
    posts = st.session_state.posts
    if not posts:
        return

    # 筛选
    if owner != "全部":
        filtered = [p for p in posts
                    if p.get('发布者', '') == owner
                    or owner in (p.get('点赞', '') or '')
                    or any(owner in c for c in p.get('评论', []) if isinstance(c, str))]
    else:
        filtered = posts
    st.session_state.filtered_posts = filtered

    # 自动别名
    amap, merged = auto_alias(filtered, threshold=0.86)
    st.session_state.alias_map = amap
    if merged > 0:
        log(f"自动合并了 {merged} 组相似名称")

    # 网络分析
    publishers = [p.get('发布者', '') for p in filtered if p.get('发布者', '')]
    if amap:
        publishers = [amap.get(p, p) for p in publishers]

    G, pub_counts = build_interaction_graph(
        publishers, all_posts=filtered,
        like_weight=LIKE_WEIGHT, comment_weight=COMMENT_WEIGHT,
        alias_map=amap, log_sys=log)
    st.session_state.graph = G

    analysis = analyze_graph(G, pub_counts, filtered, use_louvain=True, log_sys=log)
    st.session_state.analysis = analysis
    st.session_state.analyzed = True

    n_nodes = analysis.get('num_nodes', 0)
    n_edges = analysis.get('num_edges', 0)
    n_comm = len(analysis.get('community_groups', {}))
    log(f"分析完成：{n_nodes} 人 / {n_edges} 条关系 / {n_comm} 个社区")


# ──────────────────────────────
# 侧边栏：导入 + 视角 + 分析
# ──────────────────────────────
with st.sidebar:
    st.title("📊 微信朋友圈数据分析")
    st.divider()

    # 导入文件
    uploaded = st.file_uploader("导入文件", type=['json', 'xlsx', 'xls'],
                                help="支持 JSON / Excel，自动识别 arkmejson 格式")

    if uploaded:
        suffix = os.path.splitext(uploaded.name)[1]
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(uploaded.getvalue())
            tmp_path = tmp.name
        try:
            posts = load_import_file(tmp_path)
            if posts != st.session_state.posts:
                st.session_state.posts = posts
                st.session_state.analyzed = False
                st.session_state.logs = []
                log(f"导入成功：{len(posts)} 条数据")
                # 检测数据主人
                if suffix == '.json':
                    try:
                        import json
                        with open(tmp_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        if isinstance(data, dict) and data.get('recordOwner'):
                            owner = data['recordOwner']
                            st.session_state.owner_name = (
                                owner.get('displayName')
                                or owner.get('remark')
                                or owner.get('nickName'))
                    except Exception:
                        pass
        except Exception as e:
            st.error(f"导入失败：{e}")
        finally:
            os.unlink(tmp_path)

    # 数据概览
    posts = st.session_state.posts
    if posts:
        st.success(f"已加载 {len(posts)} 条数据")

        # 分析视角
        publishers = sorted(set(p.get('发布者', '') for p in posts if p.get('发布者', '')))
        options = ["全部"] + publishers
        default_idx = 0
        if st.session_state.owner_name and st.session_state.owner_name in publishers:
            default_idx = publishers.index(st.session_state.owner_name) + 1
        owner = st.selectbox("分析视角", options, index=default_idx)

        # 一键分析
        if st.button("🚀 一键分析", type="primary", use_container_width=True):
            with st.spinner("正在分析..."):
                do_analysis(owner)
    else:
        st.info("请先导入数据文件")

    # 日志
    st.divider()
    if st.session_state.logs:
        with st.expander("运行日志", expanded=True):
            for msg in st.session_state.logs:
                st.text(msg)


# ──────────────────────────────
# 主区域
# ──────────────────────────────
if not st.session_state.posts:
    st.markdown("### 👈 请先在侧边栏导入数据文件")
    st.markdown("支持 JSON / Excel 格式，自动识别 arkmejson 等第三方导出格式")
    st.stop()

tab_data, tab_graph, tab_time, tab_text, tab_social, tab_map = \
    st.tabs(["📋 数据", "🕸️ 图谱", "⏰ 时间", "📝 文本", "💬 互动", "🗺️ 地图"])

# ──────────────────────────────
# 数据 Tab
# ──────────────────────────────
with tab_data:
    if st.session_state.posts:
        rows = []
        for p in st.session_state.posts:
            comments = p.get('评论', []) or []
            cs = " | ".join(str(x) for x in comments[:3])
            if len(comments) > 3:
                cs += "..."
            rows.append({
                '编号': p.get('编号', ''),
                '发布者': p.get('发布者', ''),
                '内容': str(p.get('内容', '')),
                '时间': format_time_display(p.get('时间', '')),
                '点赞': p.get('点赞', '') or '',
                '评论': cs,
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, height=500,
                     column_config={
                         '编号': st.column_config.NumberColumn(width='small'),
                         '内容': st.column_config.TextColumn(width='large'),
                         '点赞': st.column_config.TextColumn(width='medium'),
                         '评论': st.column_config.TextColumn(width='large'),
                     })
    else:
        st.info("暂无数据")


# ──────────────────────────────
# 图谱 Tab
# ──────────────────────────────
with tab_graph:
    if not st.session_state.analyzed:
        st.info("点击「一键分析」后可查看关系图谱")
    else:
        G = st.session_state.graph
        analysis = st.session_state.analysis
        if G is None or G.number_of_nodes() == 0:
            st.warning("网络图为空")
        else:
            # 统计摘要
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("节点（人）", analysis.get('num_nodes', 0))
            col2.metric("关系（边）", analysis.get('num_edges', 0))
            col3.metric("社区数", len(analysis.get('community_groups', {})))
            col4.metric("网络密度", f"{analysis.get('network_density', 0):.4f}")

            # 图谱控制
            view_col, size_col, label_col = st.columns(3)
            view_mode = view_col.radio("视图模式", ["核心网络", "完整网络", "个人网络"],
                                       horizontal=True)
            node_scale = size_col.slider("节点大小", 5, 50, 20)
            show_labels = label_col.checkbox("显示标签", value=True)

            # 个人网络选择
            if view_mode == "个人网络":
                all_people = sorted([n for n in G.nodes() if '回复' not in n])
                selected = st.multiselect("选择人员", all_people)
                depth = st.selectbox("关系深度", [1, 2, 3], index=0)

            # 生成 pyvis 图
            G_display = G
            if view_mode == "核心网络" and G.number_of_nodes() > 50:
                sorted_nodes = sorted(G.nodes(), key=lambda n: G.degree(n), reverse=True)
                G_display = G.subgraph(sorted_nodes[:50])
            elif view_mode == "个人网络":
                if selected:
                    import community as community_louvain
                    nodes = set()
                    for p in selected:
                        frontier = {p}
                        visited = {p}
                        for _ in range(depth):
                            nf = set()
                            for n in frontier:
                                for nb in G.neighbors(n):
                                    if nb not in visited:
                                        nf.add(nb)
                                        visited.add(nb)
                            frontier = nf
                        nodes.update(visited)
                    G_display = G.subgraph(nodes)
                else:
                    st.warning("请先选择人员")
                    G_display = None

            if G_display and G_display.number_of_nodes() > 0:
                from pyvis.network import Network
                net = Network(height='650px', bgcolor='#fafafa',
                              font_color='#333', directed=False)

                communities = analysis.get('communities', {})
                degree_cent = analysis.get('degree_centrality', {})
                palette = ['#4e79a7', '#f28e2b', '#e15759', '#76b7b2',
                           '#59a14f', '#edc948', '#b07aa1', '#ff9da7',
                           '#9c755f', '#bab0ac', '#86bcb6', '#8cd17d']

                for node in G_display.nodes():
                    cid = communities.get(node, 0) % len(palette)
                    dc = degree_cent.get(node, 0)
                    size = node_scale * (1 + dc * 10)
                    label = strip_emoji(node) or node if show_labels else ""
                    net.add_node(node, label=label, color=palette[cid],
                                 size=size, title=f"{node}\n度中心性: {dc:.4f}")

                for u, v, d in G_display.edges(data=True):
                    w = d.get('weight', 1)
                    net.add_edge(u, v, value=w, title=f"权重: {w}")

                net.repulsion(node_distance=150, central_gravity=0.2,
                              spring_length=100, spring_strength=0.05)

                html_path = os.path.join(tempfile.gettempdir(), 'moments_graph.html')
                net.save_graph(html_path)
                with open(html_path, 'r', encoding='utf-8') as f:
                    html = f.read()
                st.components.v1.html(html, height=680)

                # 节点详情表
                st.subheader("节点详情")
                dc = analysis.get('degree_centrality', {})
                bc = analysis.get('betweenness', {})
                cm = analysis.get('communities', {})
                node_rows = []
                for n in sorted(G_display.nodes(), key=lambda x: dc.get(x, 0), reverse=True):
                    node_rows.append({
                        '节点': strip_emoji(n) or n,
                        '度中心性': f"{dc.get(n, 0):.4f}",
                        '介数中心性': f"{bc.get(n, 0):.4f}",
                        '社区': f"社区 {cm.get(n, -1) + 1}",
                        '连接数': G_display.degree(n),
                    })
                st.dataframe(pd.DataFrame(node_rows), use_container_width=True, height=300)

            # Top 桥梁人物
            top_bw = analysis.get('top_betweenness', [])
            if top_bw:
                st.subheader("🏆 桥梁人物（介数中心性 Top 10）")
                st.caption("连接不同社区的关键人物，删除他们会显著影响信息传播")
                bw_rows = [{'人物': strip_emoji(n) or n, '介数中心性': f"{v:.4f}"}
                           for n, v in top_bw[:10]]
                st.dataframe(pd.DataFrame(bw_rows), use_container_width=True, hide_index=True)


# ──────────────────────────────
# 时间 Tab
# ──────────────────────────────
with tab_time:
    if not st.session_state.analyzed:
        st.info("点击「一键分析」后可查看")
    else:
        data = st.session_state.filtered_posts
        st.caption("查看发圈的时间规律：几点最活跃、周几发最多、哪个月是高峰期")

        chart = st.radio("选择图表", ["24h 发布分布", "周分布", "月趋势", "年趋势"],
                         horizontal=True, key='time_chart')

        fig_map = {
            "24h 发布分布": plot_hourly_distribution_plotly,
            "周分布": plot_weekly_distribution_plotly,
            "月趋势": plot_monthly_trend_plotly,
            "年趋势": plot_yearly_trend_plotly,
        }
        fig = fig_map[chart](data)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("数据不足，无法生成图表")

        with st.expander("📋 时间分析报告"):
            st.text(generate_time_report(data))


# ──────────────────────────────
# 文本 Tab
# ──────────────────────────────
with tab_text:
    if not st.session_state.analyzed:
        st.info("点击「一键分析」后可查看")
    else:
        data = st.session_state.filtered_posts
        st.caption("分析文字内容：常用词汇、话题偏好、情感倾向（0=消极，1=积极）")

        chart = st.radio("选择图表", ["词云", "高频词", "情感曲线", "情感分布"],
                         horizontal=True, key='text_chart')

        fig_map = {
            "词云": plot_wordcloud,
            "高频词": plot_word_frequency_plotly,
            "情感曲线": plot_sentiment_timeline_plotly,
            "情感分布": plot_sentiment_distribution_plotly,
        }
        fig = fig_map[chart](data)
        if fig:
            if chart == "词云":
                st.pyplot(fig)
            else:
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("数据不足或缺少依赖库（jieba / wordcloud / snownlp）")

        with st.expander("📋 文本分析报告"):
            st.text(generate_text_report(data))


# ──────────────────────────────
# 互动 Tab
# ──────────────────────────────
with tab_social:
    if not st.session_state.analyzed:
        st.info("点击「一键分析」后可查看")
    else:
        data = st.session_state.filtered_posts
        st.caption("互动排行：谁最常点赞评论你（评论权重更高）；互动流失：哪些关系在变淡")

        chart = st.radio("选择图表", ["真爱粉排行", "互动流失趋势"],
                         horizontal=True, key='social_chart')

        if chart == "真爱粉排行":
            fig = plot_fan_ranking_plotly(data)
        else:
            fig = plot_interaction_decay_plotly(data)

        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("数据不足，无法生成图表")

        with st.expander("📋 互动分析报告"):
            st.text(generate_social_report(data))


# ──────────────────────────────
# 地图 Tab
# ──────────────────────────────
with tab_map:
    if not st.session_state.analyzed:
        st.info("点击「一键分析」后可查看")
    else:
        data = st.session_state.filtered_posts
        st.caption("展示发布时带有位置信息的动态（仅包含主动添加定位的朋友圈）")

        fig = plot_footprint_plotly(data)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("当前数据中未发现有效的地理定位数据。")

        with st.expander("📋 空间分析报告"):
            st.text(generate_spatial_report(data))
