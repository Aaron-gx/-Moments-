# -*- coding: utf-8 -*-
"""关系图谱可视化 — 聚焦视图，默认只展示核心网络"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import networkx as nx
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

from .config import FONT_NAME, strip_emoji

matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False


def _ego_subgraph(G, person, depth=1):
    """提取指定人物的 ego 网络"""
    nodes = {person}
    frontier = {person}
    for _ in range(depth):
        next_frontier = set()
        for n in frontier:
            for nb in G.neighbors(n):
                if nb not in nodes:
                    next_frontier.add(nb)
                    nodes.add(nb)
        frontier = next_frontier
    return G.subgraph(nodes)


def _core_subgraph(G, max_nodes=50):
    """提取核心网络：按度排序取 top 节点"""
    if G.number_of_nodes() <= max_nodes:
        return G
    sorted_nodes = sorted(G.nodes(), key=lambda n: G.degree(n), reverse=True)
    return G.subgraph(sorted_nodes[:max_nodes])


def _draw_network(G, analysis, ax, node_size=300, show_labels=True, show_edges=True):
    """绘制网络图 — 自动适应大小"""
    n = G.number_of_nodes()
    if n == 0:
        return

    # 布局：根据节点数自适应
    if n <= 20:
        pos = nx.spring_layout(G, k=1.5, iterations=100, seed=42)
    elif n <= 60:
        pos = nx.spring_layout(G, k=0.8, iterations=80, seed=42)
    else:
        pos = nx.kamada_kawai_layout(G)

    # 社区着色
    communities = analysis.get('communities', {})
    degree_cent = analysis.get('degree_centrality', {})
    palette = plt.cm.Set3(range(12))

    node_colors = []
    for node in G.nodes():
        cid = communities.get(node, 0) % 12
        node_colors.append(palette[cid])

    # 节点大小：按度中心性缩放
    node_sizes = [node_size * (0.5 + degree_cent.get(n, 0) * 3) for n in G.nodes()]

    # 绘制边（权重 → 粗细和透明度）
    if show_edges and n <= 200:
        edges = list(G.edges(data=True))
        weights = [d.get('weight', 1) for _, _, d in edges]
        max_w = max(weights) if weights else 1
        for (u, v, d), w in zip(edges, weights):
            alpha = min(0.6, 0.1 + w / max_w * 0.5)
            lw = 0.3 + w / max_w * 2
            ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                    color='#aaaaaa', linewidth=lw, alpha=alpha, zorder=1)

    # 绘制节点
    nodes_drawn = nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors,
                           node_size=node_sizes, alpha=0.9, edgecolors='white',
                           linewidths=1.5)
    nodes_drawn.set_zorder(3)

    # 标签：节点多时只显示前 N
    if show_labels:
        if n <= 40:
            labels = {n: strip_emoji(n) or n for n in G.nodes()}
        else:
            top = sorted(G.nodes(), key=lambda x: G.degree(x), reverse=True)[:25]
            labels = {n: strip_emoji(n) or n for n in top}
        lbl = nx.draw_networkx_labels(G, pos, ax=ax, labels=labels,
                                font_size=7 if n > 30 else 9,
                                font_family=FONT_NAME)
        for t in lbl.values():
            t.set_zorder(4)


def open_graph_window(master, graph, analysis, ui_logger):
    """打开关系图谱窗口"""
    graph_window = tk.Toplevel(master)
    graph_window.title("朋友圈互动关系图谱")
    graph_window.geometry("1200x800")

    all_people = sorted([p for p in graph.nodes() if '回复' not in p])

    # ── 控制栏 ──
    ctrl = ttk.Frame(graph_window)
    ctrl.pack(fill='x', padx=10, pady=8)

    # 视图模式
    ttk.Label(ctrl, text="视图：", font=(FONT_NAME, 10, "bold")).pack(side='left', padx=4)
    view_var = tk.StringVar(value="核心网络")

    n_total = graph.number_of_nodes()
    default_view = "核心网络" if n_total > 30 else "完整网络"
    view_var.set(default_view)

    view_options = ["完整网络", "核心网络", "个人网络"]
    ttk.Combobox(ctrl, textvariable=view_var, values=view_options,
                 state="readonly", width=10).pack(side='left', padx=2)

    # 个人网络选择
    ttk.Label(ctrl, text="选择人员：").pack(side='left', padx=4)
    person_frame = ttk.Frame(ctrl)
    person_frame.pack(side='left', padx=2)

    psb = ttk.Scrollbar(person_frame, orient='vertical')
    psb.pack(side='right', fill='y')
    person_lb = tk.Listbox(person_frame, yscrollcommand=psb.set,
                           selectmode='extended', width=18, height=6)
    person_lb.pack(side='left')
    psb.config(command=person_lb.yview)
    for p in all_people:
        person_lb.insert('end', p)

    ttk.Label(ctrl, text="关系深度：").pack(side='left', padx=4)
    depth_var = tk.IntVar(value=1)
    ttk.Combobox(ctrl, textvariable=depth_var, values=[1, 2, 3],
                 state="readonly", width=4).pack(side='left', padx=2)

    # 样式控制
    ttk.Separator(ctrl, orient='vertical').pack(side='left', fill='y', padx=8)
    node_size_var = tk.DoubleVar(value=300)
    ttk.Label(ctrl, text="节点大小：").pack(side='left', padx=4)
    ttk.Scale(ctrl, from_=50, to=800, variable=node_size_var,
              orient='horizontal', length=100).pack(side='left')

    show_labels_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(ctrl, text="标签", variable=show_labels_var).pack(side='left', padx=4)

    show_edges_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(ctrl, text="连线", variable=show_edges_var).pack(side='left', padx=4)

    # ── 图表区 + 信息表 ──
    main_pane = ttk.PanedWindow(graph_window, orient='vertical')
    main_pane.pack(fill='both', expand=True, padx=10, pady=4)

    chart_frame = ttk.Frame(main_pane)
    main_pane.add(chart_frame, weight=3)

    # 信息表
    info_frame = ttk.LabelFrame(main_pane, text="节点详情", padding=3)
    main_pane.add(info_frame, weight=1)

    cols = ("节点", "度中心性", "介数中心性", "社区", "连接数")
    info_tree = ttk.Treeview(info_frame, columns=cols, show='headings', height=8)
    cw = {"节点": 150, "度中心性": 100, "介数中心性": 100, "社区": 80, "连接数": 80}
    for c in cols:
        info_tree.heading(c, text=c)
        info_tree.column(c, width=cw[c], anchor='w')
    isb = ttk.Scrollbar(info_frame, orient='vertical', command=info_tree.yview)
    isb.pack(side='right', fill='y')
    info_tree.configure(yscrollcommand=isb.set)
    info_tree.pack(fill='both', expand=True)

    # 导出按钮
    export_frame = ttk.Frame(graph_window)
    export_frame.pack(fill='x', padx=10, pady=4)

    def _fill_info_table(G_sub):
        for r in info_tree.get_children():
            info_tree.delete(r)
        dc = analysis.get('degree_centrality', {})
        bc = analysis.get('betweenness', {})
        cm = analysis.get('communities', {})
        for node in sorted(G_sub.nodes(), key=lambda x: dc.get(x, 0), reverse=True):
            info_tree.insert('', 'end', values=(
                node,
                f"{dc.get(node, 0):.4f}",
                f"{bc.get(node, 0):.4f}",
                f"社区 {cm.get(node, -1) + 1}",
                f"{G_sub.degree(node)}"
            ))

    current_fig = [None]

    def update_graph():
        plt.close('all')

        view = view_var.get()
        G = graph

        if view == "个人网络":
            sel = person_lb.curselection()
            if not sel:
                messagebox.showinfo("提示", "请先选择人员", parent=graph_window)
                return
            people = [person_lb.get(i) for i in sel]
            nodes = set()
            for p in people:
                ego = _ego_subgraph(G, p, depth=depth_var.get())
                nodes.update(ego.nodes())
            G = G.subgraph(nodes)
            title_name = ', '.join(people[:3])
            if len(people) > 3:
                title_name += f" 等{len(people)}人"
            depth_text = {1: "直接关系", 2: "朋友的朋友", 3: "三级关系"}.get(depth_var.get(), "关系")
            title = f"{title_name} 的{depth_text}网络"
        elif view == "核心网络":
            G = _core_subgraph(G, max_nodes=50)
            title = f"核心互动网络（Top {G.number_of_nodes()} 人）"
        else:
            title = "完整互动网络"

        fig, ax = plt.subplots(figsize=(12, 7), dpi=100)
        fig.patch.set_facecolor('#fafafa')
        ax.set_facecolor('#fafafa')

        _draw_network(G, analysis, ax,
                      node_size=node_size_var.get(),
                      show_labels=show_labels_var.get(),
                      show_edges=show_edges_var.get())

        ax.set_title(title, fontproperties={'family': FONT_NAME, 'size': 13, 'weight': 'bold'})
        ax.axis('off')

        info_text = (f"节点: {G.number_of_nodes()}  |  "
                     f"关系: {G.number_of_edges()}  |  "
                     f"密度: {nx.density(G):.4f}")
        ax.text(0.02, 0.02, info_text, transform=ax.transAxes, fontsize=8,
                fontproperties={'family': FONT_NAME, 'size': 8},
                bbox=dict(boxstyle='round,pad=0.3', facecolor='wheat', alpha=0.7))

        fig.tight_layout()
        current_fig[0] = fig

        for w in chart_frame.winfo_children():
            w.destroy()
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

        _fill_info_table(G)

    ttk.Button(ctrl, text="生成图表", command=update_graph, width=10).pack(side='left', padx=8)

    def export_graph():
        p = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("PDF", "*.pdf"), ("SVG", "*.svg")])
        if p and current_fig[0]:
            try:
                current_fig[0].savefig(p, dpi=300, bbox_inches='tight')
                messagebox.showinfo("成功", f"已保存到：{p}")
            except Exception as e:
                messagebox.showerror("失败", str(e))

    def export_data():
        p = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")])
        if p:
            try:
                dc = analysis.get('degree_centrality', {})
                bc = analysis.get('betweenness', {})
                cm = analysis.get('communities', {})
                rows = [{'节点': n, '度': graph.degree(n),
                         '度中心性': dc.get(n, 0), '介数中心性': bc.get(n, 0),
                         '社区': cm.get(n, -1) + 1} for n in graph.nodes()]
                df = pd.DataFrame(rows)
                if p.endswith('.xlsx'):
                    df.to_excel(p, index=False)
                else:
                    df.to_csv(p, index=False, encoding='utf-8')
                messagebox.showinfo("成功", f"已保存到：{p}")
            except Exception as e:
                messagebox.showerror("失败", str(e))

    ttk.Button(export_frame, text="导出图表", command=export_graph, width=10).pack(side='left', padx=4)
    ttk.Button(export_frame, text="导出数据", command=export_data, width=10).pack(side='left', padx=4)

    # 初始生成
    update_graph()
    ui_logger.log_sys("关系图谱已生成。")
