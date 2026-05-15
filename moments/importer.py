# -*- coding: utf-8 -*-
import json
import pandas as pd


def _is_arkmejson(data):
    """判断 JSON 数据是否为 arkmejson 格式"""
    if not isinstance(data, dict):
        return False
    if data.get("format") == "arkmejson":
        return True
    posts = data.get("posts", [])
    if isinstance(posts, list) and len(posts) > 0:
        first = posts[0]
        if isinstance(first, dict) and "author" in first and "contentDesc" in first:
            return True
    return False


def _convert_arkmejson_posts(raw_posts):
    """将 arkmejson 格式的 posts 数组转为内部统一格式

    arkmejson 字段映射:
      author.displayName / nickname -> 发布者
      contentDesc                   -> 内容
      createTimeStr                 -> 时间
      likes (str 数组)              -> 点赞 (逗号分隔 str)
      comments ({nickname,content}) -> 评论 (["昵称: 内容"] str 数组)
    """
    result = []
    for i, post in enumerate(raw_posts):
        author_info = post.get("author", {})
        publisher = (author_info.get("displayName")
                     or author_info.get("remark")
                     or author_info.get("nickName")
                     or post.get("nickname", ""))

        content = post.get("contentDesc", "")

        time_str = post.get("createTimeStr", "")

        # likes: str 数组 -> 逗号分隔字符串
        raw_likes = post.get("likes", [])
        if isinstance(raw_likes, list):
            likes = "，".join(raw_likes)
        else:
            likes = str(raw_likes) if raw_likes else ""

        # comments: 对象数组 -> ["昵称: 内容"] 格式
        raw_comments = post.get("comments", [])
        comments = []
        if isinstance(raw_comments, list):
            for c in raw_comments:
                if isinstance(c, dict):
                    nickname = c.get("nickname", "")
                    content_text = c.get("content", "")
                    if nickname and content_text:
                        comments.append(f"{nickname}: {content_text}")
                    elif nickname:
                        comments.append(nickname)
                elif isinstance(c, str):
                    comments.append(c)

        # 保留扩展字段用于高级分析
        loc = post.get("location", {}) or {}
        media = post.get("media", []) or []

        result.append({
            "编号": i + 1,
            "发布者": publisher,
            "内容": content,
            "时间": time_str,
            "点赞": likes,
            "评论": comments,
            "timestamp": post.get("createTime", 0),
            "latitude": loc.get("latitude", 0),
            "longitude": loc.get("longitude", 0),
            "media_count": len(media),
        })
    return result


def import_json(path):
    """导入 JSON 文件，自动识别格式并返回标准化 posts 列表"""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # arkmejson 格式
    if _is_arkmejson(data):
        raw_posts = data.get("posts", [])
        if not isinstance(raw_posts, list):
            raw_posts = []
        return _convert_arkmejson_posts(raw_posts), "arkmejson"

    # 原有格式：顶层 dict 带 posts 键
    if isinstance(data, dict) and 'posts' in data:
        data = data['posts']

    # 原有格式：顶层 list
    if isinstance(data, list):
        return data, "native"

    return [], "unknown"


def import_excel(path):
    """导入 Excel 文件，返回标准化 posts 列表"""
    df = pd.read_excel(path)
    posts = []
    for i, (_, row) in enumerate(df.iterrows()):
        comments_val = row.get("评论", "")
        if isinstance(comments_val, str):
            try:
                import ast
                parsed = ast.literal_eval(comments_val)
                if isinstance(parsed, list):
                    comments_val = parsed
            except Exception:
                pass
        posts.append({
            "编号": row.get("编号", i + 1),
            "发布者": row.get("发布者", ""),
            "内容": row.get("内容", ""),
            "时间": row.get("时间", ""),
            "点赞": row.get("点赞", "") if "点赞" in row else "",
            "评论": comments_val if isinstance(comments_val, list) else [],
        })
    return posts


def import_file(path):
    """统一导入入口，根据文件扩展名分发"""
    if path.lower().endswith('.json'):
        posts, fmt = import_json(path)
        return posts
    elif path.lower().endswith(('.xlsx', '.xls')):
        return import_excel(path)
    else:
        raise ValueError(f"不支持的文件格式: {path}")
