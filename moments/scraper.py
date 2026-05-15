# -*- coding: utf-8 -*-
import time
import psutil
from pywinauto.application import Application


def get_wechat_pid():
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = proc.info.get('name') or ''
            if name.lower() == 'wechat.exe':
                return proc.info['pid']
        except Exception:
            continue
    return None


def extract_likes_from_element(post_element):
    candidates = []

    def search(el, depth=0):
        if depth > 15:
            return
        try:
            for c in el.children():
                try:
                    ctrl_type = c.element_info.control_type
                    name = c.element_info.name or c.window_text()
                except Exception:
                    continue
                if (ctrl_type in ("Static", "Text")
                        and name and '，' in name
                        and ':' not in name and '：' not in name
                        and 4 < len(name) < 300
                        and not any(x in name for x in ['包含', '张图片', '个视频', '回复'])):
                    candidates.append((depth, name))
                search(c, depth + 1)
        except Exception:
            pass

    try:
        search(post_element)
        if not candidates:
            return ""
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    except Exception:
        return ""


def extract_comments_from_element(post_element):
    def search(el, depth=0):
        if depth > 12:
            return []
        try:
            for c in el.children():
                try:
                    ctrl_type = c.element_info.control_type
                    name = c.element_info.name
                except Exception:
                    continue
                if ctrl_type == "List" and (name == "评论" or name == "评论列表"):
                    items = c.children(control_type="ListItem")
                    return [i.window_text() for i in items if i.window_text()]
                res = search(c, depth + 1)
                if res:
                    return res
        except Exception:
            pass
        return []

    try:
        return search(post_element) or []
    except Exception:
        return []


def parse_moments_collect(target_count=100, timeout=5, progress_callback=None, log_sys=None, log_data=None):
    if log_sys: log_sys(f"开始采集（目标 {target_count} 条，超时 {timeout}s）")
    pid = get_wechat_pid()
    if not pid:
        raise RuntimeError("未检测到 WeChat.exe 进程，请启动微信桌面客户端。")
    app = Application(backend='uia').connect(process=pid)
    moments_window = None
    try:
        moments_window = app['朋友圈']
    except Exception:
        for w in app.windows():
            try:
                if '朋友圈' in (w.window_text() or ''):
                    moments_window = w
                    break
            except Exception:
                continue
    if not moments_window:
        raise RuntimeError("无法定位朋友圈窗口，请打开微信并进入朋友圈页面。")
    moments_list = None
    try:
        moments_list = moments_window.child_window(title="朋友圈", control_type="List")
    except Exception:
        try:
            lists = [c for c in moments_window.children() if c.element_info.control_type == 'List']
            moments_list = lists[0] if lists else None
        except Exception:
            moments_list = None
    if not moments_list:
        raise RuntimeError("朋友圈列表控件未找到，请确保页面处于朋友圈界面（中文）。")
    all_posts = []
    seen = set()
    scroll_delay = 0.45
    last_new = time.time()
    while len(all_posts) < target_count:
        try:
            posts = moments_list.children(control_type="ListItem")
        except Exception:
            posts = []
        new_found = False
        for p in posts:
            try:
                text = p.window_text()
            except Exception:
                continue
            if not text or text in seen:
                continue
            seen.add(text)
            new_found = True
            last_new = time.time()
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            if len(lines) < 2:
                continue
            publisher = lines[0].rstrip(':').strip()
            content = lines[1]
            time_str = lines[-1]
            if len(lines) >= 3 and "包含" in lines[-2] and "图片" in lines[-2]:
                content += " (" + lines[-2] + ")"
            likes = extract_likes_from_element(p) or ""
            comments = extract_comments_from_element(p) or []
            item = {"编号": len(all_posts) + 1, "发布者": publisher, "内容": content, "时间": time_str, "点赞": likes,
                    "评论": comments}
            all_posts.append(item)
            if progress_callback:
                try:
                    progress_callback(len(all_posts), target_count)
                except Exception:
                    pass
            if log_data: log_data(f"采集到第 {len(all_posts)} 条：{publisher}")
            if len(all_posts) >= target_count:
                break
        try:
            moments_list.type_keys("{DOWN}")
        except Exception:
            pass
        time.sleep(scroll_delay)
        if time.time() - last_new > timeout:
            if log_sys: log_sys(f"超时 {timeout}s 未发现新动态，停止采集。")
            break
    if log_sys: log_sys(f"采集结束，共 {len(all_posts)} 条。")
    return all_posts
