# -*- coding: utf-8 -*-
"""主界面 — 简约三步流程：导入 → 分析 → 查看"""
import json
import re
import threading
import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .config import (APP_TITLE, ACCENT_COLOR, FONT_NAME, FONT_SIZE_LOG,
                    FONT_SIZE_LABEL, LIKE_WEIGHT, COMMENT_WEIGHT, TEMP_DIR)
from .logger import UILogHandler
from .scraper import parse_moments_collect
from .importer import import_file as load_import_file
from .analyzer import (build_interaction_graph, analyze_graph, format_time_display,
                      auto_alias)
from .visualizer import open_graph_window
from .analysis_time import (plot_hourly_distribution, plot_weekly_distribution,
                           plot_monthly_trend, plot_yearly_trend, generate_time_report)
from .analysis_text import (plot_wordcloud, plot_word_frequency,
                           plot_sentiment_timeline, plot_sentiment_distribution,
                           generate_text_report)
from .analysis_social import (plot_fan_ranking, plot_interaction_decay,
                             generate_social_report)
from .analysis_spatial import generate_spatial_report, plot_footprint

matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False


class MomentsApp:
    def __init__(self, master):
        self.master = master
        master.title("微信朋友圈数据分析")
        master.geometry("1200x850")
        master.minsize(900, 600)

        self.all_posts = []
        self._filtered_posts = []  # 当前视角过滤后的数据
        self.graph = None
        self.analysis = None
        self.alias_map = {}
        self._owner_name = None

        self._build_ui()
        self.ui_logger = UILogHandler(self.log_text, self.log_text)
        self._destroyed = False
        self._log_after_id = None
        self.master.protocol("WM_DELETE_WINDOW", self._on_close)
        self._schedule_log_flush()

    # ──────────────────────────────
    # UI 构建
    # ──────────────────────────────
    def _build_ui(self):
        # 操作栏
        action_frame = ttk.Frame(self.master)
        action_frame.pack(fill='x', padx=16, pady=(10, 6))
        ttk.Button(action_frame, text="?", width=3, command=self._show_help).pack(side='right')

        self.import_btn = ttk.Button(action_frame, text="导入文件",
                                     command=self.import_file, width=14)
        self.import_btn.pack(side='left', padx=(0, 8))

        self.collect_btn = ttk.Button(action_frame, text="从微信采集",
                                      command=self._show_collect_dialog, width=14)
        self.collect_btn.pack(side='left', padx=(0, 8))

        self.analyze_btn = ttk.Button(action_frame, text="一键分析",
                                      command=self.start_analyze, width=14)
        self.analyze_btn.pack(side='left', padx=(0, 16))

        # 身份选择
        ttk.Label(action_frame, text="分析视角：",
                  font=(FONT_NAME, FONT_SIZE_LABEL)).pack(side='left')
        self.owner_var = tk.StringVar(value="全部")
        self.owner_combo = ttk.Combobox(action_frame, textvariable=self.owner_var,
                                        values=["全部"], width=18, state="readonly")
        self.owner_combo.pack(side='left', padx=(0, 16))
        self.owner_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_treeview())

        self.data_label = ttk.Label(action_frame, text="未加载数据",
                                    font=(FONT_NAME, FONT_SIZE_LABEL), foreground='#888')
        self.data_label.pack(side='left')

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(self.master, variable=self.progress_var, maximum=100)
        self.progress.pack(fill='x', padx=16, pady=(0, 8))

        # 主内容：Notebook
        self.notebook = ttk.Notebook(self.master)
        self.notebook.pack(fill='both', expand=True, padx=16, pady=(0, 4))

        self._build_data_tab()
        self._build_graph_tab()
        self._build_time_tab()
        self._build_text_tab()
        self._build_social_tab()
        self._build_map_tab()

        # 日志区（增大高度）
        log_frame = ttk.LabelFrame(self.master, text="运行日志", padding=3)
        log_frame.pack(fill='x', padx=16, pady=(0, 4))
        self.log_text = tk.Text(log_frame, height=8, state='disabled', wrap='word',
                                font=("Consolas", 10), bg="#fafafa")
        log_scroll = ttk.Scrollbar(log_frame, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side='right', fill='y')
        self.log_text.pack(fill='x')

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(self.master, textvariable=self.status_var,
                  font=(FONT_NAME, 10), foreground=ACCENT_COLOR).pack(padx=16, pady=(0, 8), anchor='w')

    def _build_data_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=" 数据 ")

        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill='both', expand=True, padx=4, pady=4)

        columns = ("编号", "发布者", "内容", "时间", "点赞", "评论")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)
        col_widths = {"编号": 50, "发布者": 120, "内容": 300, "时间": 160, "点赞": 200, "评论": 250}
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=col_widths[col], anchor='w')

        style = ttk.Style()
        style.configure('Treeview', rowheight=36, font=(FONT_NAME, 10))
        style.configure('Treeview.Heading', font=(FONT_NAME, 10, "bold"))

        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        vsb.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)

        # 悬停提示
        self._tooltip_win = None
        self._post_by_item = {}
        self.tree.bind('<Motion>', self._on_tree_motion)
        self.tree.bind('<Leave>', self._hide_tooltip)

    def _build_graph_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=" 图谱 ")

        tk.Label(frame, text="社交关系图谱：节点大小反映活跃程度，连线粗细表示互动频率，颜色区分不同社区",
                 font=(FONT_NAME, 9), fg='#888', anchor='w', justify='left').pack(fill='x', padx=8, pady=(4, 0))

        center = ttk.Frame(frame)
        center.place(relx=0.5, rely=0.5, anchor='center')

        self.graph_summary = tk.Label(center, text="分析完成后可查看关系图谱",
                                      font=(FONT_NAME, 12), fg='#999')
        self.graph_summary.pack(pady=20)

        self.graph_btn = ttk.Button(center, text="打开关系图谱",
                                    command=self._open_graph, width=20)
        self.graph_btn.pack(pady=10)
        self.graph_btn.state(['disabled'])

    def _build_chart_tab(self, tab_text, chart_funcs, description=""):
        """通用图表 tab 构建器 — 只建框架，不建按钮"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=tab_text)

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill='x', padx=4, pady=4)

        if description:
            desc_lbl = tk.Label(frame, text=description, font=(FONT_NAME, 9),
                                fg='#888', anchor='w', justify='left')
            desc_lbl.pack(fill='x', padx=8)

        chart_frame = ttk.Frame(frame)
        chart_frame.pack(fill='both', expand=True, padx=4, pady=4)

        placeholder = tk.Label(chart_frame, text="点击「一键分析」后可查看",
                               font=(FONT_NAME, 12), fg='#999')
        placeholder.pack(expand=True)

        return btn_row, chart_frame, placeholder, chart_funcs

    def _build_time_tab(self):
        self.time_btn_row, self.time_chart_frame, self.time_placeholder, self.time_funcs = \
            self._build_chart_tab(" 时间 ", [
                ("24h分布", plot_hourly_distribution),
                ("周分布", plot_weekly_distribution),
                ("月趋势", plot_monthly_trend),
                ("年趋势", plot_yearly_trend),
            ], description="查看发圈的时间规律：几点最活跃、周几发最多、哪个月是高峰期")

    def _build_text_tab(self):
        self.text_btn_row, self.text_chart_frame, self.text_placeholder, self.text_funcs = \
            self._build_chart_tab(" 文本 ", [
                ("词云", plot_wordcloud),
                ("高频词", plot_word_frequency),
                ("情感曲线", plot_sentiment_timeline),
                ("情感分布", plot_sentiment_distribution),
            ], description="分析文字内容：常用词汇、话题偏好、情感倾向（0=消极，1=积极）")

    def _build_social_tab(self):
        self.social_btn_row, self.social_chart_frame, self.social_placeholder, self.social_funcs = \
            self._build_chart_tab(" 互动 ", [
                ("真爱粉排行", plot_fan_ranking),
                ("互动流失", plot_interaction_decay),
            ], description="互动排行：谁最常点赞评论你（评论权重更高）；互动流失：哪些关系在变淡")

    def _build_map_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=" 地图 ")

        tk.Label(frame, text="足迹地图：展示发布时带有位置信息的动态（仅包含主动添加定位的朋友圈）",
                 font=(FONT_NAME, 9), fg='#888', anchor='w', justify='left').pack(fill='x', padx=8, pady=(4, 0))

        self.map_btn_row = ttk.Frame(frame)
        self.map_btn_row.pack(fill='x', padx=4, pady=4)

        self.map_chart_frame = ttk.Frame(frame)
        self.map_chart_frame.pack(fill='both', expand=True, padx=4, pady=4)

        self.map_placeholder = tk.Label(self.map_chart_frame,
                                        text="点击「一键分析」后可查看",
                                        font=(FONT_NAME, 12), fg='#999')
        self.map_placeholder.pack(expand=True)

    # ──────────────────────────────
    # 工具方法
    # ──────────────────────────────
    def _on_close(self):
        self._destroyed = True
        if self._log_after_id is not None:
            try:
                self.master.after_cancel(self._log_after_id)
            except Exception:
                pass
            self._log_after_id = None
        self.master.destroy()

    def _schedule_log_flush(self):
        if self._destroyed:
            return
        try:
            self.ui_logger.flush_to_widgets()
        except Exception:
            pass
        if not self._destroyed:
            self._log_after_id = self.master.after(200, self._schedule_log_flush)

    def _log(self, msg):
        self.ui_logger.log_sys(msg)

    def _set_buttons(self, enabled):
        state = 'normal' if enabled else 'disabled'
        for btn in (self.import_btn, self.collect_btn, self.analyze_btn):
            btn.configure(state=state)

    def _on_tree_motion(self, event):
        """鼠标悬停在 Treeview 行上时显示详情提示"""
        row_id = self.tree.identify_row(event.y)
        self._hide_tooltip()
        if not row_id:
            return
        post = self._post_by_item.get(row_id)
        if not post:
            return
        likes = post.get('点赞', '') or ''
        comments = post.get('评论', []) or []
        lines = []
        if likes:
            lines.append(f"点赞：{likes}")
        if comments:
            lines.append("评论：")
            for c in comments:
                lines.append(f"  {c}")
        if not lines:
            return
        self._show_tooltip(event, '\n'.join(lines))

    def _show_tooltip(self, event, text):
        self._hide_tooltip()
        tw = tk.Toplevel(self.master)
        tw.wm_overrideredirect(True)
        tw.wm_attributes("-topmost", True)
        x = event.x_root + 15
        y = event.y_root + 10
        tw.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(tw, text=text, justify='left', background="#ffffe0",
                       relief='solid', borderwidth=1, font=(FONT_NAME, 9),
                       padx=6, pady=4)
        lbl.pack()
        self._tooltip_win = tw

    def _hide_tooltip(self, event=None):
        if self._tooltip_win:
            try:
                self._tooltip_win.destroy()
            except tk.TclError:
                pass
            self._tooltip_win = None

    def _refresh_treeview(self):
        self._post_by_item = {}
        for r in self.tree.get_children():
            self.tree.delete(r)
        owner = self.owner_var.get()
        for row in self.all_posts:
            if owner != "全部" and row.get('发布者', '') != owner:
                continue
            comments = row.get('评论', [])
            if isinstance(comments, list):
                cs = " | ".join(str(x) for x in comments[:3])
                if len(comments) > 3:
                    cs += "..."
            else:
                cs = str(comments)
            likes = row.get('点赞', '') or ""
            item_id = self.tree.insert('', 'end', values=(
                row.get('编号', ''), row.get('发布者', ''),
                str(row.get('内容', ''))[:100],
                format_time_display(row.get('时间', '')),
                str(likes)[:100] if isinstance(likes, str) else "",
                cs,
            ))
            self._post_by_item[item_id] = row

    def _embed_chart(self, chart_frame, fig):
        for w in chart_frame.winfo_children():
            w.destroy()
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

    def _populate_chart_tab(self, btn_row, chart_frame, placeholder, chart_funcs):
        """为图表 tab 添加按钮（防重复）"""
        # 清除旧按钮
        for w in btn_row.winfo_children():
            w.destroy()
        # 销毁 placeholder（如果还在）
        try:
            placeholder.destroy()
        except tk.TclError:
            pass

        def make_cmd(plot_fn):
            def cmd():
                fig = plot_fn(self._filtered_posts)
                if fig:
                    self._embed_chart(chart_frame, fig)
            return cmd

        for text, fn in chart_funcs:
            ttk.Button(btn_row, text=text, command=make_cmd(fn), width=10).pack(side='left', padx=2)

    def _update_owner_combo(self):
        """更新身份选择下拉框"""
        publishers = sorted(set(p.get('发布者', '') for p in self.all_posts if p.get('发布者', '')))
        values = ["全部"] + publishers
        self.owner_combo.configure(values=values)
        if self._owner_name and self._owner_name in publishers:
            self.owner_var.set(self._owner_name)
        else:
            self.owner_var.set("全部")

    # ──────────────────────────────
    # 操作：导入
    # ──────────────────────────────
    def import_file(self):
        p = filedialog.askopenfilename(
            filetypes=[('数据文件', '*.json *.xlsx *.xls')], title="选择文件")
        if not p:
            return
        try:
            self.all_posts = load_import_file(p)
            self._detect_owner(p)
            self._update_owner_combo()
            self._refresh_treeview()
            self.data_label.configure(text=f"已加载 {len(self.all_posts)} 条数据")
            self.status_var.set(f"已加载 {len(self.all_posts)} 条数据")
            self._log(f"导入成功：{len(self.all_posts)} 条数据")
        except Exception as e:
            messagebox.showerror("导入失败", str(e))
            self._log(f"导入失败：{e}")

    def _detect_owner(self, path):
        """从 arkmejson 中检测数据主人"""
        if not path.lower().endswith('.json'):
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                import json as _json
                data = _json.load(f)
            if isinstance(data, dict) and data.get('recordOwner'):
                owner = data['recordOwner']
                self._owner_name = (owner.get('displayName')
                                    or owner.get('remark')
                                    or owner.get('nickName', None))
        except Exception:
            pass

    # ──────────────────────────────
    # 操作：从微信采集
    # ──────────────────────────────
    def _show_collect_dialog(self):
        dlg = tk.Toplevel(self.master)
        dlg.title("从微信采集")
        dlg.geometry("360x220")
        dlg.resizable(False, False)
        dlg.transient(self.master)
        dlg.grab_set()

        ttk.Label(dlg, text="采集数量", font=(FONT_NAME, FONT_SIZE_LABEL)).grid(row=0, column=0, padx=12, pady=8, sticky='e')
        count_entry = ttk.Entry(dlg, width=12)
        count_entry.insert(0, "200")
        count_entry.grid(row=0, column=1, padx=8, pady=8)

        ttk.Label(dlg, text="超时(秒)", font=(FONT_NAME, FONT_SIZE_LABEL)).grid(row=1, column=0, padx=12, pady=8, sticky='e')
        timeout_entry = ttk.Entry(dlg, width=12)
        timeout_entry.insert(0, "6")
        timeout_entry.grid(row=1, column=1, padx=8, pady=8)

        ttk.Label(dlg, text="保存格式", font=(FONT_NAME, FONT_SIZE_LABEL)).grid(row=2, column=0, padx=12, pady=8, sticky='e')
        fmt_var = tk.StringVar(value="json")
        ttk.Combobox(dlg, textvariable=fmt_var, values=["json", "xlsx"],
                     width=10, state="readonly").grid(row=2, column=1, padx=8, pady=8)

        def start():
            try:
                count = int(count_entry.get())
                timeout = int(timeout_entry.get())
            except ValueError:
                messagebox.showerror("错误", "请输入有效数字", parent=dlg)
                return
            dlg.destroy()
            self._do_collect(count, timeout, fmt_var.get())

        ttk.Button(dlg, text="开始采集", command=start, width=16).grid(row=3, column=0, columnspan=2, pady=16)

    def _do_collect(self, count, timeout, fmt):
        self._set_buttons(False)
        self.status_var.set("正在采集...")
        self.progress_var.set(0)

        def progress_cb(now, target):
            try:
                self.progress_var.set(min(100, int(now / target * 100)))
                self.master.update_idletasks()
            except Exception:
                pass

        def worker():
            try:
                posts = parse_moments_collect(target_count=count, timeout=timeout,
                                              progress_callback=progress_cb,
                                              log_sys=self._log, log_data=self._log)
                self.all_posts = posts
                save_path = f"moments_{datetime.date.today()}.{fmt}"
                if fmt == 'json':
                    with open(save_path, 'w', encoding='utf-8') as f:
                        json.dump(self.all_posts, f, ensure_ascii=False, indent=2)
                else:
                    pd.DataFrame(self.all_posts).to_excel(save_path, index=False)
                self._update_owner_combo()
                self._refresh_treeview()
                self.data_label.configure(text=f"已加载 {len(self.all_posts)} 条数据")
                self.status_var.set(f"采集完成：{len(self.all_posts)} 条")
                self._log(f"采集完成：{len(self.all_posts)} 条，已保存到 {save_path}")
            except Exception as e:
                messagebox.showerror("采集失败", str(e))
                self._log(f"采集失败：{e}")
                self.status_var.set("采集失败")
            finally:
                self._set_buttons(True)
                self.progress_var.set(0)

        threading.Thread(target=worker, daemon=True).start()

    # ──────────────────────────────
    # 操作：一键分析
    # ──────────────────────────────
    def start_analyze(self):
        if not self.all_posts:
            messagebox.showwarning("提示", "请先导入或采集数据。")
            return

        self._set_buttons(False)
        self.status_var.set("正在分析...")
        self.progress_var.set(10)
        owner = self.owner_var.get()
        self._log(f"开始分析...（视角：{owner}）")

        def worker():
            try:
                # 筛选数据
                if owner != "全部":
                    posts = [p for p in self.all_posts
                             if p.get('发布者', '') == owner or owner in p.get('点赞', '') or any(owner in c for c in p.get('评论', []) if isinstance(c, str))]
                else:
                    posts = self.all_posts

                # 保存过滤后数据，供图表按钮等使用
                self._filtered_posts = posts

                # 1. 自动别名
                self.progress_var.set(15)
                amap, merged = auto_alias(posts, threshold=0.86)
                self.alias_map = amap
                if merged > 0:
                    self._log(f"自动合并了 {merged} 组相似名称")

                # 2. 网络分析
                self.progress_var.set(30)
                publishers = [p.get('发布者', '') for p in posts if p.get('发布者', '')]
                if self.alias_map:
                    publishers = [self.alias_map.get(p, p) for p in publishers]

                G, pub_counts = build_interaction_graph(
                    publishers, all_posts=posts,
                    like_weight=LIKE_WEIGHT, comment_weight=COMMENT_WEIGHT,
                    alias_map=self.alias_map, log_sys=self._log)
                self.graph = G
                self.progress_var.set(50)

                analysis = analyze_graph(G, pub_counts, posts,
                                         use_louvain=True, log_sys=self._log)
                self.analysis = analysis
                self.progress_var.set(70)

                # 3. 填充各 tab
                self.master.after(0, lambda: self._populate_results(analysis, posts))
                self.progress_var.set(100)

                n_nodes = analysis.get('num_nodes', 0)
                n_edges = analysis.get('num_edges', 0)
                n_comm = len(analysis.get('community_groups', {}))
                self._log(f"分析完成：{n_nodes} 人、{n_edges} 条关系、{n_comm} 个社区")
                self.status_var.set(f"分析完成：{n_nodes} 人 / {n_edges} 条关系 / {n_comm} 个社区")

            except Exception as e:
                import traceback
                traceback.print_exc()
                self._log(f"分析失败：{e}")
                messagebox.showerror("分析失败", str(e))
                self.status_var.set("分析失败")
            finally:
                self._set_buttons(True)
                self.progress_var.set(0)

        threading.Thread(target=worker, daemon=True).start()

    def _populate_results(self, analysis, posts):
        """分析完成后填充各 tab（主线程执行）"""
        # 确保使用过滤后的数据
        data = self._filtered_posts or posts

        # 图谱 tab
        self.graph_summary.configure(text=(
            f"节点: {analysis.get('num_nodes', 0)} 人  |  "
            f"关系: {analysis.get('num_edges', 0)} 条  |  "
            f"社区: {len(analysis.get('community_groups', {}))} 个  |  "
            f"密度: {analysis.get('network_density', 0):.4f}"
        ))
        self.graph_btn.state(['!disabled'])

        # 时间 tab
        self._populate_chart_tab(self.time_btn_row, self.time_chart_frame,
                                 self.time_placeholder, self.time_funcs)
        fig = plot_hourly_distribution(data)
        if fig:
            self._embed_chart(self.time_chart_frame, fig)

        # 文本 tab
        self._populate_chart_tab(self.text_btn_row, self.text_chart_frame,
                                 self.text_placeholder, self.text_funcs)
        fig = plot_wordcloud(data)
        if fig:
            self._embed_chart(self.text_chart_frame, fig)

        # 互动 tab
        self._populate_chart_tab(self.social_btn_row, self.social_chart_frame,
                                 self.social_placeholder, self.social_funcs)
        fig = plot_fan_ranking(data)
        if fig:
            self._embed_chart(self.social_chart_frame, fig)

        # 地图 tab — 用 matplotlib 内嵌
        # 清除旧按钮
        for w in self.map_btn_row.winfo_children():
            w.destroy()
        try:
            self.map_placeholder.destroy()
        except tk.TclError:
            pass

        fig = plot_footprint(data)
        if fig:
            self._embed_chart(self.map_chart_frame, fig)
        else:
            report = generate_spatial_report(data)
            lbl = tk.Label(self.map_chart_frame, text=report,
                          font=(FONT_NAME, 11), fg='#666', justify='left')
            lbl.pack(expand=True)

    # ──────────────────────────────
    # 图谱
    # ──────────────────────────────
    def _open_graph(self):
        if not self.graph or not self.analysis:
            return
        try:
            open_graph_window(self.master, self.graph, self.analysis, self.ui_logger)
        except Exception as e:
            messagebox.showerror("错误", str(e))

    # ──────────────────────────────
    # 帮助
    # ──────────────────────────────
    def _show_help(self):
        dlg = tk.Toplevel(self.master)
        dlg.title("使用帮助")
        dlg.geometry("580x400")
        txt = tk.Text(dlg, wrap='word', font=(FONT_NAME, 11), padx=12, pady=12)
        txt.pack(fill='both', expand=True)
        txt.insert('1.0', """
使用步骤：

1. 导入文件
   点击「导入文件」，选择 JSON 或 Excel 数据文件。
   支持自动识别 arkmejson 格式。

2. 选择分析视角
   导入后，在「分析视角」下拉框中选择你要分析的人。
   默认「全部」表示分析所有人。

3. 一键分析
   点击「一键分析」，程序自动完成：
   - 相似名称合并
   - 社交网络构建
   - 社区检测
   - 各维度图表生成

4. 查看结果
   在标签页中切换查看：
   数据 | 图谱 | 时间 | 文本 | 互动 | 地图

提示：也可「从微信采集」直接采集（需微信 3.9.10）。
""")
        txt.configure(state='disabled')
