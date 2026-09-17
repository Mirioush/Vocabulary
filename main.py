# -*- coding: utf-8 -*-
"""考研单词背诵程序 (类 Anki 间隔重复, 简约苹果风格界面)。

基于 SM-2 算法, 根据记忆程度自动安排下次复习时间。
- 新词学习后按 1 / 6 天逐级拉长间隔, 之后按 易度因子(Ease Factor) 递乘。
- 忘记的单词会在本次学习中重新出现, 巩固记忆。
- 学习进度保存在 progress.json。

运行:  python main.py
"""

import json
import os
import random
from datetime import date, timedelta

import tkinter as tk
from tkinter import messagebox

from words import WORDS

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "progress.json")

QUALITY = {"again": 1, "hard": 3, "good": 4, "easy": 5}

# ---------- 配色 (Apple 风格: 浅灰背景 + 白卡片 + 单一蓝色强调) ----------
BG_TOP = "#f7f8fa"
BG_BOT = "#f0f1f5"
CARD_FILL = "#ffffff"
CARD_SHADOW = "#e2e3e8"
TRACK = "#e5e5ea"

TEXT_PRIMARY = "#1d1d1f"
TEXT_SECONDARY = "#86868b"
ACCENT = "#0071e3"

DISABLED_BG = "#f2f2f7"
DISABLED_TEXT = "#c7c7cc"

# 评分按钮: 柔和底色 + 深色文字 (低饱和, 更高级)
RATE_STYLE = {
    "again": {"fill": "#ffe3e3", "text": "#c9302c"},
    "hard": {"fill": "#fff1d8", "text": "#b7791f"},
    "good": {"fill": "#dcf3e2", "text": "#1f8a4d"},
    "easy": {"fill": "#dcecff", "text": "#2563eb"},
}
RATE_LABELS = {"again": "忘记 (1)", "hard": "困难 (2)", "good": "记得 (3)", "easy": "简单 (4)"}

WORD_FONT = ("Segoe UI", 40, "bold")
PHONETIC_FONT = ("Segoe UI", 14)
MEANING_FONT = ("Microsoft YaHei", 16)
EXAMPLE_FONT = ("Microsoft YaHei", 12)
STATS_FONT = ("Microsoft YaHei", 10)
SMALL_FONT = ("Microsoft YaHei", 9)
TITLE_FONT = ("Microsoft YaHei", 15, "bold")
BTN_FONT = ("Microsoft YaHei", 12, "bold")
SMALL_BTN_FONT = ("Microsoft YaHei", 9, "bold")


def today_iso():
    return date.today().isoformat()


def default_card():
    return {"ef": 2.5, "interval": 0, "repetitions": 0, "due": None}


def load_progress():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"cards": {}}


def save_progress(progress):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)


def schedule(card, quality):
    """SM-2 调度: 根据评分更新卡片。"""
    today = date.today()
    if quality < 3:  # 忘记: 打回当天重新学
        card["repetitions"] = 0
        card["interval"] = 0
        card["due"] = today.isoformat()
    else:
        if card["repetitions"] == 0:
            card["interval"] = 1
        elif card["repetitions"] == 1:
            card["interval"] = 6
        else:
            card["interval"] = round(card["interval"] * card["ef"])
        card["repetitions"] += 1
        card["due"] = (today + timedelta(days=card["interval"])).isoformat()

    ef = card["ef"] + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    card["ef"] = max(1.3, round(ef, 2))
    return card


# ---------- 绘制工具 ----------
def lerp_color(c1, c2, t):
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return "#%02x%02x%02x" % (r, g, b)


def lighten(color, amt):
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    r = min(255, max(0, int(r + 255 * amt)))
    g = min(255, max(0, int(g + 255 * amt)))
    b = min(255, max(0, int(b + 255 * amt)))
    return "#%02x%02x%02x" % (r, g, b)


def rounded_rect(canvas, x1, y1, x2, y2, radius, **kwargs):
    radius = max(0, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
    pts = [x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
           x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
           x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1]
    return canvas.create_polygon(pts, smooth=True, splinesteps=24, **kwargs)


class GlassButton:
    """圆角按钮 (canvas 绘制, 带悬停效果)。"""

    def __init__(self, canvas, text, command, fill, text_color="#ffffff",
                 radius=14, font=BTN_FONT):
        self.canvas = canvas
        self.text = text
        self.command = command
        self.fill = fill
        self.text_color = text_color
        self.radius = radius
        self.font = font
        self.hover_fill = lighten(fill, -0.06)
        self.enabled = True
        self.tag = "btn_%d" % id(self)
        self._body = None
        self.x = self.y = self.w = self.h = 0

    def place(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
        self._draw()

    def set_text(self, text):
        self.text = text
        self._draw()

    def set_enabled(self, enabled):
        self.enabled = enabled
        self._draw()

    def _draw(self):
        c = self.canvas
        c.delete(self.tag)
        fill = self.fill if self.enabled else DISABLED_BG
        tc = self.text_color if self.enabled else DISABLED_TEXT
        body = rounded_rect(c, self.x, self.y, self.x + self.w, self.y + self.h,
                            self.radius, fill=fill, outline="")
        label = c.create_text(self.x + self.w / 2, self.y + self.h / 2,
                              text=self.text, fill=tc, font=self.font)
        self._body = body
        c.addtag_withtag(self.tag, body)
        c.addtag_withtag(self.tag, label)
        c.addtag_withtag("button", body)
        c.addtag_withtag("button", label)
        c.tag_bind(self.tag, "<Enter>", self._on_enter)
        c.tag_bind(self.tag, "<Leave>", self._on_leave)
        c.tag_bind(self.tag, "<Button-1>", self._on_click)

    def _on_enter(self, e):
        if self.enabled:
            self.canvas.itemconfigure(self._body, fill=self.hover_fill)

    def _on_leave(self, e):
        if self.enabled:
            self.canvas.itemconfigure(self._body, fill=self.fill)

    def _on_click(self, e):
        if self.enabled and self.command:
            self.command()


class WordApp:
    def __init__(self, root):
        self.root = root
        self.root.title("考研单词背诵")
        self.root.geometry("720x560")
        self.root.minsize(560, 480)
        self.root.configure(bg=BG_TOP)

        self.word_map = {w["word"]: w for w in WORDS}
        self.progress = load_progress()

        self.queue = []
        self.current = None
        self.revealed = False
        self.done_today = 0
        self.learned_total = 0
        self._flash_job = None

        self.pbar_x = self.pbar_y = self.pbar_w = self.pbar_h = 0

        self._build_ui()

        self.root.bind("<space>", lambda e: self.reveal())
        self.root.bind("1", lambda e: self.rate("again"))
        self.root.bind("2", lambda e: self.rate("hard"))
        self.root.bind("3", lambda e: self.rate("good"))
        self.root.bind("4", lambda e: self.rate("easy"))
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_session()
        self._show_next()
        self._layout()

    # ---------- 界面 ----------
    def _build_ui(self):
        self.canvas = tk.Canvas(self.root, highlightthickness=0, bd=0, bg=BG_TOP)
        self.canvas.pack(fill="both", expand=True)
        c = self.canvas

        self.title_text = c.create_text(0, 0, text="考研单词背诵", anchor="w",
                                        font=TITLE_FONT, fill=TEXT_PRIMARY, tags="content")
        self.stats_text = c.create_text(0, 0, text="", anchor="w", font=STATS_FONT,
                                        fill=TEXT_SECONDARY, tags="content")
        self.pbar_track = rounded_rect(c, 0, 0, 10, 6, 3, fill=TRACK, outline="", tags="content")
        self.pbar_text = c.create_text(0, 0, text="", anchor="w", font=SMALL_FONT,
                                       fill=TEXT_SECONDARY, tags="content")
        self.status_text = c.create_text(0, 0, text="", anchor="w", font=SMALL_FONT,
                                         fill=ACCENT, tags="content")

        self.word_text = c.create_text(0, 0, text="", font=WORD_FONT, fill=TEXT_PRIMARY, tags="content")
        self.phonetic_text = c.create_text(0, 0, text="", font=PHONETIC_FONT, fill=TEXT_SECONDARY, tags="content")
        self.meaning_text = c.create_text(0, 0, text="", font=MEANING_FONT, fill=TEXT_PRIMARY,
                                          width=520, justify="center", tags="content")
        self.example_text = c.create_text(0, 0, text="", font=EXAMPLE_FONT, fill=TEXT_SECONDARY,
                                          width=520, justify="center", tags="content")

        self.reveal_btn = GlassButton(c, "显示答案 (空格)", self.reveal, ACCENT,
                                      radius=24, font=BTN_FONT)
        self.rate_btns = {}
        for k in ("again", "hard", "good", "easy"):
            style = RATE_STYLE[k]
            self.rate_btns[k] = GlassButton(c, RATE_LABELS[k], lambda k=k: self.rate(k),
                                            style["fill"], text_color=style["text"],
                                            radius=22, font=BTN_FONT)
        self.save_btn = GlassButton(c, "保存进度", self.save_now, "#eef0f4",
                                    text_color="#6e6e73", radius=14, font=SMALL_BTN_FONT)
        self.reset_btn = GlassButton(c, "重置进度", self.reset_progress, "#eef0f4",
                                     text_color="#6e6e73", radius=14, font=SMALL_BTN_FONT)

        self.canvas.bind("<Configure>", self._layout)

    def _draw_bg(self, w, h):
        c = self.canvas
        c.delete("bg")
        steps = 60
        for i in range(steps):
            t = i / (steps - 1)
            col = lerp_color(BG_TOP, BG_BOT, t)
            y0 = int(i * h / steps)
            y1 = int((i + 1) * h / steps) + 1
            c.create_rectangle(0, y0, w, y1, fill=col, outline=col, tags="bg")

    def _draw_card(self, w, h):
        c = self.canvas
        c.delete("card")
        x1, y1, x2, y2 = 48, 96, w - 48, h - 28
        # 柔和投影 + 白色卡片
        rounded_rect(c, x1, y1 + 6, x2, y2 + 6, 28, fill=CARD_SHADOW, outline="", tags="card")
        rounded_rect(c, x1, y1, x2, y2, 28, fill=CARD_FILL, outline="", tags="card")

    def _apply_zorder(self):
        c = self.canvas
        c.tag_lower("bg")
        c.tag_raise("card")
        c.tag_raise("content")
        c.tag_raise("button")

    def _layout(self, event=None):
        c = self.canvas
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 10 or h < 10:
            return
        self._draw_bg(w, h)
        self._draw_card(w, h)

        # 顶栏
        c.coords(self.title_text, 24, 24)
        c.coords(self.stats_text, 24, 52)
        c.coords(self.status_text, 24, 74)

        # 进度条
        pbx, pby, pbh = 24, 74, 6
        pbw = min(260, w * 0.35)
        self.pbar_x, self.pbar_y, self.pbar_w, self.pbar_h = pbx, pby, pbw, pbh
        c.delete("ptrack")
        rounded_rect(c, pbx, pby - pbh / 2, pbx + pbw, pby + pbh / 2, pbh / 2,
                     fill=TRACK, outline="", tags=("content", "ptrack"))
        c.coords(self.pbar_text, pbx + pbw + 12, pby)
        self._refresh_progress()

        # 卡片内容
        cx = w / 2
        c.coords(self.word_text, cx, 172)
        c.coords(self.phonetic_text, cx, 214)
        wrap = max(300, w - 200)
        c.itemconfigure(self.meaning_text, width=wrap)
        c.itemconfigure(self.example_text, width=wrap)
        c.coords(self.meaning_text, cx, 322)
        c.coords(self.example_text, cx, 382)

        self.reveal_btn.place(cx - 120, 248, 240, 48)

        # 评分按钮
        bw = min(140, (w - 160) // 4)
        gap = 14
        bh = 52
        total_w = 4 * bw + 3 * gap
        x0 = cx - total_w / 2
        y0 = h - 88
        for i, k in enumerate(("again", "hard", "good", "easy")):
            self.rate_btns[k].place(x0 + i * (bw + gap), y0, bw, bh)

        # 右上角按钮
        tbw, tbh = 76, 30
        self.reset_btn.place(w - 16 - 2 * tbw - 8, 18, tbw, tbh)
        self.save_btn.place(w - 16 - tbw, 18, tbw, tbh)

        self._apply_zorder()

    def _set_text(self, item, text):
        self.canvas.itemconfigure(item, text=text)

    def _clear_answer(self):
        self._set_text(self.meaning_text, "")
        self._set_text(self.example_text, "")

    def _refresh_progress(self):
        total = len(WORDS)
        pct = self.learned_total / total if total else 0
        if self.pbar_w <= 0:
            return
        c = self.canvas
        c.delete("pfill")
        fillw = max(0, self.pbar_w * pct)
        r = self.pbar_h / 2
        if fillw > 2:
            rounded_rect(c, self.pbar_x, self.pbar_y - r, self.pbar_x + fillw,
                         self.pbar_y + r, r, fill=ACCENT, outline="", tags=("content", "pfill"))
        self._set_text(self.pbar_text,
                       "已学 {} / {} · {:.1f}%".format(self.learned_total, total, pct * 100))

    def _update_stats(self):
        self._set_text(self.stats_text,
                       "今日待复习 {}  ·  新词 {}  ·  剩余 {}  ·  今日已学 {}".format(
                           self.review_total, self.new_total, len(self.queue), self.done_today))
        self._refresh_progress()

    # ---------- 会话 ----------
    def _build_session(self):
        new_cards, review_cards = [], []
        today = today_iso()
        for w in WORDS:
            card = self.progress["cards"].get(w["word"])
            if not card or card.get("due") is None:
                new_cards.append(w["word"])
            elif card["due"] <= today:
                review_cards.append(w["word"])
        self.new_total = len(new_cards)
        self.review_total = len(review_cards)
        self.learned_total = len(self.progress["cards"])
        random.shuffle(new_cards)
        random.shuffle(review_cards)
        self.queue = new_cards + review_cards

    def _show_next(self):
        self.revealed = False
        self.reveal_btn.set_enabled(True)
        for b in self.rate_btns.values():
            b.set_enabled(False)
        if not self.queue:
            self._save()
            self._set_text(self.word_text, "全部完成")
            self._set_text(self.phonetic_text, "")
            self._clear_answer()
            self._set_text(self.status_text, "今天没有需要复习的单词了, 明天再来吧")
            self._update_stats()
            return
        word = self.queue.pop(0)
        self.current = self.word_map[word]
        self._set_text(self.word_text, self.current["word"])
        self._set_text(self.phonetic_text, self.current.get("phonetic", ""))
        self._clear_answer()
        self._update_stats()

    def reveal(self):
        if not self.current or self.revealed:
            return
        self.revealed = True
        self._set_text(self.meaning_text, self.current["meaning"])
        self._set_text(self.example_text, self.current["example"])
        self.reveal_btn.set_enabled(False)
        for b in self.rate_btns.values():
            b.set_enabled(True)

    # ---------- 评分 / 保存 / 重置 ----------
    def _save(self):
        save_progress(self.progress)

    def _flash_saved(self, msg="进度已保存"):
        self._set_text(self.status_text, msg)
        if self._flash_job:
            self.root.after_cancel(self._flash_job)
        self._flash_job = self.root.after(2500, lambda: self._set_text(self.status_text, ""))

    def save_now(self):
        self._save()
        self._flash_saved("进度已保存 ✓")

    def reset_progress(self):
        if not messagebox.askyesno(
                "确认重置",
                "确定要清空所有学习进度吗？\n所有单词将恢复为未学习状态。",
                parent=self.root):
            return
        self.progress = {"cards": {}}
        self._save()
        self.done_today = 0
        self._build_session()
        self._show_next()
        self._flash_saved("进度已重置 ✓")

    def _on_close(self):
        self._save()
        self.root.destroy()

    def rate(self, key):
        if not self.current or not self.revealed:
            return
        word = self.current["word"]
        card = self.progress["cards"].setdefault(word, default_card())
        schedule(card, QUALITY[key])
        if key == "again":
            self.queue.append(word)
        self.done_today += 1
        self.learned_total = len(self.progress["cards"])
        self._save()
        self._flash_saved("进度已自动保存 ✓")
        self._show_next()


def main():
    root = tk.Tk()
    WordApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
