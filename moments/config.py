# -*- coding: utf-8 -*-
import os
import re
import tempfile

APP_TITLE = "微信朋友圈关系分析 专业版"

# 匹配常见 emoji（精确范围，避免误删正常字符）
_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA00-\U0001FA6F"  # chess symbols
    "\U0001FA70-\U0001FAFF"  # symbols extended-A
    "\U00002702-\U000027BF"  # dingbats
    "\U00002600-\U000027BF"  # misc symbols + dingbats
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200D"             # zero width joiner
    "\U00002B50"             # star
    "]+", flags=re.UNICODE)


def strip_emoji(text):
    """去除字符串中的 emoji 字符，防止 matplotlib 字体警告"""
    return _EMOJI_RE.sub('', text).strip()
TEMP_DIR = os.path.join(tempfile.gettempdir(), "wmnt_pro_tmp")
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR, exist_ok=True)

LIKE_WEIGHT = 1
COMMENT_WEIGHT = 2
BG_COLOR = "#f5f5f5"
FG_COLOR = "#333333"
ACCENT_COLOR = "#0066cc"
BUTTON_COLOR = "#0066cc"
FONT_NAME = "Microsoft YaHei"
FONT_SIZE_LOG = 12
FONT_SIZE_LABEL = 11
