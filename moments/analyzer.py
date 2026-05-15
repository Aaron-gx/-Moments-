# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime, date

import networkx as nx

try:
    import community as community_louvain
except Exception:
    community_louvain = None

try:
    from rapidfuzz import fuzz, process as rf_process
    HAVE_RAPIDFUZZ = True
except Exception:
    HAVE_RAPIDFUZZ = False

from .config import LIKE_WEIGHT, COMMENT_WEIGHT


def build_interaction_graph(publishers, all_posts=None, like_weight=LIKE_WEIGHT,
                            comment_weight=COMMENT_WEIGHT, alias_map=None, log_sys=None):
    """从所有数据列构建互动网络（发布者、点赞者、评论者）"""
    if log_sys: log_sys("构建互动网络（基于所有互动数据）...")
    G = nx.Graph()

    def norm(name):
        if not name: return ""
        name = str(name).strip()
        if alias_map and name in alias_map:
            return alias_map[name]
        return name

    for pub in publishers:
        pub = norm(pub)
        if pub and '回复' not in pub:
            G.add_node(pub)

    if all_posts:
        for post in all_posts:
            pub = norm(post.get('发布者', ''))
            if not pub:
                continue
            if pub not in G:
                G.add_node(pub)

            likes_raw = post.get('点赞', '')
            if isinstance(likes_raw, str) and likes_raw.strip():
                likers = [x.strip() for x in likes_raw.replace('、', '，').split('，') if x.strip()]
                for liker in likers:
                    liker = norm(liker)
                    if not liker or liker == pub or '回复' in liker:
                        continue
                    if liker not in G:
                        G.add_node(liker)
                    if G.has_edge(liker, pub):
                        G[liker][pub]['weight'] += like_weight
                        G[liker][pub]['likes'] = G[liker][pub].get('likes', 0) + 1
                    else:
                        G.add_edge(liker, pub, weight=like_weight, likes=1, comments=0)

            comments = post.get('评论', []) or []
            for comment in comments:
                if not comment:
                    continue
                commenter = None
                if ':' in comment:
                    commenter = comment.split(':', 1)[0].strip()
                elif '：' in comment:
                    commenter = comment.split('：', 1)[0].strip()
                else:
                    parts = comment.split(None, 1)
                    commenter = parts[0].strip() if parts else comment.strip()

                commenter_raw = commenter
                commenter = norm(commenter)
                if not commenter or commenter == pub:
                    continue

                # 处理回复关系：A回复B → 回复者→发布者 + 回复者→被回复者
                if '回复' in commenter_raw:
                    reply_parts = commenter_raw.split('回复', 1)
                    replier = norm(reply_parts[0].strip())
                    reply_target = norm(reply_parts[1].strip()) if len(reply_parts) > 1 else None

                    if not replier or replier == pub:
                        continue
                    if replier not in G:
                        G.add_node(replier)
                    if G.has_edge(replier, pub):
                        G[replier][pub]['weight'] += comment_weight
                        G[replier][pub]['comments'] = G[replier][pub].get('comments', 0) + 1
                    else:
                        G.add_edge(replier, pub, weight=comment_weight, likes=0, comments=1)

                    if reply_target and reply_target != pub and reply_target != replier:
                        if reply_target not in G:
                            G.add_node(reply_target)
                        if G.has_edge(replier, reply_target):
                            G[replier][reply_target]['weight'] += comment_weight
                            G[replier][reply_target]['comments'] = G[replier][reply_target].get('comments', 0) + 1
                        else:
                            G.add_edge(replier, reply_target, weight=comment_weight, likes=0, comments=1)
                else:
                    if commenter not in G:
                        G.add_node(commenter)
                    if G.has_edge(commenter, pub):
                        G[commenter][pub]['weight'] += comment_weight
                        G[commenter][pub]['comments'] = G[commenter][pub].get('comments', 0) + 1
                    else:
                        G.add_edge(commenter, pub, weight=comment_weight, likes=0, comments=1)

    all_participants = set(publishers)
    if all_posts:
        for post in all_posts:
            likes_raw = post.get('点赞', '')
            if isinstance(likes_raw, str) and likes_raw.strip():
                likers = [x.strip() for x in likes_raw.replace('、', '，').split('，') if x.strip()]
                all_participants.update(likers)

            comments = post.get('评论', []) or []
            for comment in comments:
                if ':' in comment:
                    commenter = comment.split(':', 1)[0].strip()
                elif '：' in comment:
                    commenter = comment.split('：', 1)[0].strip()
                else:
                    parts = comment.split(None, 1)
                    commenter = parts[0].strip() if parts else comment.strip()
                if commenter:
                    all_participants.add(commenter)

    pub_counts = defaultdict(int)
    for pub in publishers:
        pub = norm(pub)
        if pub:
            pub_counts[pub] += 1

    if log_sys: log_sys(f"网络构建完成：节点 {G.number_of_nodes()}，边 {G.number_of_edges()}")
    return G, pub_counts


def analyze_graph(G, pub_counts, all_posts, use_louvain=True, log_sys=None):
    """分析网络图"""
    if log_sys: log_sys("开始网络分析...")
    res = {}
    res['num_nodes'] = G.number_of_nodes()
    res['num_edges'] = G.number_of_edges()

    degree_dict = dict(G.degree())
    res['degree'] = degree_dict

    try:
        res['degree_centrality'] = nx.degree_centrality(G)
    except Exception as e:
        res['degree_centrality'] = {}
        if log_sys: log_sys(f"度中心性计算失败: {e}")

    res['betweenness'] = {}
    n = G.number_of_nodes()
    if n > 2:
        try:
            if n <= 400:
                if log_sys: log_sys("计算介数中心性（精确）...")
                res['betweenness'] = nx.betweenness_centrality(G, normalized=True)
            else:
                k = min(200, max(80, n // 10))
                if log_sys: log_sys(f"计算介数中心性（近似，采样 k={k}）...")
                res['betweenness'] = nx.betweenness_centrality(G, k=k, normalized=True, seed=42)
        except Exception as e:
            res['betweenness'] = {}
            if log_sys: log_sys(f"介数计算失败: {e}")

    res['communities'] = {}
    res['community_groups'] = {}

    if use_louvain and community_louvain:
        try:
            if log_sys: log_sys("开始社区检测（基于完整互动网络）...")
            if G.number_of_nodes() > 0:
                partition = community_louvain.best_partition(G)
                res['communities'] = partition
                cg = {}
                for node, cid in partition.items():
                    cg.setdefault(cid, []).append(node)
                res['community_groups'] = cg
                if log_sys: log_sys(f"社区检测完成：{len(cg)} 个社区")
        except Exception as e:
            if log_sys: log_sys(f"社区检测失败: {e}")
    else:
        if use_louvain:
            if log_sys: log_sys("未安装 python-louvain，跳过社区检测。")

    def topk(dct, k=10):
        if not dct:
            return []
        try:
            k = int(k)
        except:
            k = 10
        if k <= 0:
            k = 10
        items = sorted(dct.items(), key=lambda x: x[1], reverse=True)
        return items[:k]

    res['top_degree'] = topk(res.get('degree_centrality', {}), k=10)
    res['top_betweenness'] = topk(res.get('betweenness', {}), k=10)

    res['network_density'] = nx.density(G) if G.number_of_nodes() > 0 else 0

    weights = [G[u][v].get('weight', 1) for u, v in G.edges()]
    res['avg_weight'] = sum(weights) / len(weights) if weights else 0
    res['max_weight'] = max(weights) if weights else 0

    if log_sys: log_sys("网络分析完成。")
    return res


def analyze_publisher_activity(all_posts):
    """分析发布者的活跃度"""
    activity = defaultdict(lambda: {'posts': 0, 'total_interactions': 0})

    for post in all_posts:
        publisher = post.get('发布者', '')
        if publisher:
            activity[publisher]['posts'] += 1

            likes_raw = post.get('点赞', '')
            likes_count = 0
            if isinstance(likes_raw, str) and likes_raw.strip():
                likes_count = len([x.strip() for x in likes_raw.replace('、', '，').split('，') if x.strip()])

            comments = post.get('评论', []) or []
            comments_count = len(comments) if isinstance(comments, list) else 0

            activity[publisher]['total_interactions'] += likes_count + comments_count

    return dict(activity)


def format_time_display(time_str):
    """处理时间显示：将时间转换为相对时间显示"""
    try:
        time_str = str(time_str).strip()
        now = datetime.now()
        today = now.date()

        if any(k in time_str for k in ['前', '昨天', '刚刚']):
            return time_str

        if ':' in time_str and '月' not in time_str and '年' not in time_str:
            try:
                return f"今天 {time_str}"
            except Exception:
                pass

        if '月' in time_str and '日' in time_str and '年' not in time_str:
            try:
                parsed_dt = datetime.strptime(f"{now.year}-{time_str}", "%Y-%m月%d日")
                if parsed_dt.date() > today:
                    parsed_dt = datetime.strptime(f"{now.year - 1}-{time_str}", "%Y-%m月%d日")

                parsed_date = parsed_dt.date()
                delta = today - parsed_date
                if delta.days == 0:
                    return "今天"
                if delta.days == 1:
                    return "昨天"
                if delta.days < 30:
                    return f"{delta.days}天前"
                else:
                    return time_str
            except Exception:
                return time_str

        if '年' in time_str and '月' in time_str and '日' in time_str:
            try:
                parsed_date = datetime.strptime(time_str, "%Y年%m月%d日").date()
                delta = today - parsed_date
                if delta.days == 0:
                    return "今天"
                if delta.days == 1:
                    return "昨天"
                return f"{delta.days}天前"
            except Exception:
                return time_str

        return time_str
    except Exception:
        return str(time_str)


def suggest_aliases_from_publishers(all_posts, threshold=0.86, max_pairs=1000):
    """从所有数据列进行别名建议（发布者、点赞者、评论者）"""
    names = set()

    for post in all_posts:
        pub = post.get('发布者', '')
        if pub and pub.strip():
            names.add(pub.strip())

    for post in all_posts:
        likes_raw = post.get('点赞', '')
        if isinstance(likes_raw, str) and likes_raw.strip():
            likers = [x.strip() for x in likes_raw.replace('、', '，').split('，') if x.strip()]
            for liker in likers:
                names.add(liker)

    for post in all_posts:
        comments = post.get('评论', []) or []
        for comment in comments:
            if ':' in comment:
                commenter = comment.split(':', 1)[0].strip()
            elif '：' in comment:
                commenter = comment.split('：', 1)[0].strip()
            else:
                parts = comment.split(None, 1)
                commenter = parts[0].strip() if parts else comment.strip()
            if commenter:
                names.add(commenter)

    names = list(names)
    suggestions = []

    if HAVE_RAPIDFUZZ:
        for i, name in enumerate(names):
            matches = rf_process.extract(name, names, scorer=fuzz.ratio, limit=10)
            for m_name, score, _ in matches:
                if m_name == name: continue
                ratio = score / 100.0
                if ratio >= threshold:
                    suggestions.append((name, m_name, ratio))
            if len(suggestions) > max_pairs:
                break
    else:
        import difflib
        n = len(names)
        for i in range(n):
            for j in range(i + 1, n):
                a = names[i]
                b = names[j]
                ratio = difflib.SequenceMatcher(None, a, b).ratio()
                if ratio >= threshold:
                    suggestions.append((a, b, ratio))
                if len(suggestions) > max_pairs:
                    break
            if len(suggestions) > max_pairs:
                break
    suggestions.sort(key=lambda x: x[2], reverse=True)
    return suggestions


def build_alias_map_from_suggestions(suggestions, prefer_shorter=True):
    amap = {}
    for a, b, score in suggestions:
        if prefer_shorter:
            can = a if len(a) <= len(b) else b
            alt = b if can == a else a
        else:
            can, alt = a, b
        if alt in amap:
            continue
        if alt == can:
            continue
        amap[alt] = can
    return amap


def auto_alias(posts, threshold=0.86):
    """自动检测并应用别名，返回 (alias_map, merged_count)"""
    suggestions = suggest_aliases_from_publishers(posts, threshold=threshold)
    amap = build_alias_map_from_suggestions(suggestions)
    return amap, len(amap)
