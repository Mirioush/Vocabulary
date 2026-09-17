# -*- coding: utf-8 -*-
"""考研单词背诵 (Android/Kivy 版)。

复用 SM-2 间隔重复算法与 words.py 词库。
进度保存在 App.user_data_dir 下的 progress.json。
"""

import json
import os
import random
from datetime import date, timedelta

from kivy.app import App
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex as C

from words import WORDS

QUALITY = {"again": 1, "hard": 3, "good": 4, "easy": 5}

# 配色 (Apple 风格)
BG = "#f5f5f7"
CARD = "#ffffff"
TEXT_PRIMARY = "#1d1d1f"
TEXT_SECONDARY = "#86868b"
ACCENT = "#0071e3"
TRACK = "#e5e5ea"
RATE_STYLE = {
    "again": {"fill": "#ffe3e3", "text": "#c9302c"},
    "hard": {"fill": "#fff1d8", "text": "#b7791f"},
    "good": {"fill": "#dcf3e2", "text": "#1f8a4d"},
    "easy": {"fill": "#dcecff", "text": "#2563eb"},
}
RATE_LABELS = {"again": "忘记", "hard": "困难", "good": "记得", "easy": "简单"}


def today_iso():
    return date.today().isoformat()


def default_card():
    return {"ef": 2.5, "interval": 0, "repetitions": 0, "due": None}


def schedule(card, quality):
    today = date.today()
    if quality < 3:
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


class RoundedButton(Button):
    """圆角按钮。"""

    def __init__(self, bg=ACCENT, fg="#ffffff", radius=24, **kw):
        super().__init__(**kw)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = C(fg)
        self.disabled_color = C("#b5b5bd")
        self.radius = radius
        with self.canvas.before:
            self._bg = Color(*C(bg))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def set_bg(self, bg):
        self._bg.rgba = C(bg)


class Card(BoxLayout):
    """白色圆角卡片。"""

    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(*C(CARD))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[28])
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size


class ProgressBar(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.pct = 0.0
        with self.canvas:
            Color(*C(TRACK))
            self.track = RoundedRectangle(pos=self.pos, size=self.size, radius=[4])
            Color(*C(ACCENT))
            self.fill = RoundedRectangle(pos=self.pos, size=(0, self.height), radius=[4])
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *a):
        self.track.pos = self.pos
        self.track.size = self.size
        self._refresh()

    def set_pct(self, p):
        self.pct = max(0.0, min(1.0, p))
        self._refresh()

    def _refresh(self):
        self.fill.pos = self.pos
        self.fill.size = (max(0, self.width * self.pct), self.height)


class WordApp(App):
    title = "考研单词"

    def build(self):
        Window.clearcolor = C(BG)

        self.word_map = {w["word"]: w for w in WORDS}
        self.progress = self._load()
        self.queue = []
        self.current = None
        self.revealed = False
        self.done_today = 0
        self.learned_total = 0
        self._status_job = None

        self._build_ui()
        self._build_session()
        self._show_next()
        return self.root

    # ---------- 数据 ----------
    def _data_file(self):
        try:
            d = App.get_running_app().user_data_dir
        except Exception:
            d = os.path.dirname(os.path.abspath(__file__))
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "progress.json")

    def _load(self):
        p = self._data_file()
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {"cards": {}}

    def _save(self):
        p = self._data_file()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.progress, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)

    def on_pause(self):
        self._save()
        return True

    def on_stop(self):
        self._save()

    # ---------- 界面 ----------
    def _build_ui(self):
        root = BoxLayout(orientation="vertical", padding=[20, 20, 20, 20], spacing=14)
        self.root = root

        # 顶栏
        top = BoxLayout(orientation="horizontal", size_hint_y=None, height=44, spacing=10)
        self.stats_label = Label(text="", font_size="12sp", color=C(TEXT_SECONDARY),
                                 halign="left", valign="middle", size_hint_x=1)
        self.stats_label.bind(size=lambda *a: setattr(self.stats_label, "text_size", self.stats_label.size))
        top.add_widget(self.stats_label)

        self.reset_btn = RoundedButton(text="重置", bg="#eef0f4", fg="#6e6e73", radius=14,
                                       size_hint=(None, None), size=(64, 36), font_size="13sp")
        self.reset_btn.bind(on_release=lambda *a: self.reset_progress())
        self.save_btn = RoundedButton(text="保存", bg="#eef0f4", fg="#6e6e73", radius=14,
                                      size_hint=(None, None), size=(64, 36), font_size="13sp")
        self.save_btn.bind(on_release=lambda *a: self.save_now())
        top.add_widget(self.reset_btn)
        top.add_widget(self.save_btn)
        root.add_widget(top)

        # 进度条
        self.progress_bar = ProgressBar(size_hint_y=None, height=8)
        root.add_widget(self.progress_bar)
        self.progress_label = Label(text="", font_size="12sp", color=C(TEXT_SECONDARY),
                                    size_hint_y=None, height=18, halign="left", valign="middle")
        self.progress_label.bind(size=lambda *a: setattr(self.progress_label, "text_size", self.progress_label.size))
        root.add_widget(self.progress_label)

        # 卡片
        card = Card(orientation="vertical", padding=[28, 24, 28, 20], spacing=8)

        self.word_label = Label(text="", font_size="46sp", bold=True, color=C(TEXT_PRIMARY),
                                size_hint_y=0.35, halign="center", valign="middle")
        self.word_label.bind(size=lambda *a: setattr(self.word_label, "text_size", self.word_label.size))
        self.phonetic_label = Label(text="", font_size="16sp", color=C(TEXT_SECONDARY),
                                    size_hint_y=None, height=26, halign="center", valign="middle")
        self.phonetic_label.bind(size=lambda *a: setattr(self.phonetic_label, "text_size", self.phonetic_label.size))

        self.reveal_btn = RoundedButton(text="显示答案", bg=ACCENT, fg="#ffffff", radius=24,
                                        size_hint=(None, None), size=(220, 52), font_size="16sp",
                                        pos_hint={"center_x": 0.5})
        self.reveal_btn.bind(on_release=lambda *a: self.reveal())

        self.meaning_label = Label(text="", font_size="18sp", color=C(TEXT_PRIMARY),
                                   size_hint_y=None, height=60, halign="center", valign="middle")
        self.meaning_label.bind(size=lambda *a: setattr(self.meaning_label, "text_size", self.meaning_label.size))
        self.example_label = Label(text="", font_size="14sp", color=C(TEXT_SECONDARY),
                                   size_hint_y=None, height=70, halign="center", valign="top")
        self.example_label.bind(size=lambda *a: setattr(self.example_label, "text_size", self.example_label.size))

        card.add_widget(self.word_label)
        card.add_widget(self.phonetic_label)
        card.add_widget(self.reveal_btn)
        card.add_widget(self.meaning_label)
        card.add_widget(self.example_label)
        root.add_widget(card)

        # 评分按钮
        rate_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=56, spacing=12)
        self.rate_btns = {}
        for k in ("again", "hard", "good", "easy"):
            s = RATE_STYLE[k]
            b = RoundedButton(text=RATE_LABELS[k], bg=s["fill"], fg=s["text"], radius=24,
                              font_size="16sp", bold=True)
            b.bind(on_release=lambda *a, key=k: self.rate(key))
            self.rate_btns[k] = b
            rate_row.add_widget(b)
        root.add_widget(rate_row)

    def _set_rating_enabled(self, enabled):
        for k, b in self.rate_btns.items():
            b.disabled = not enabled
            s = RATE_STYLE[k]
            b.set_bg(s["fill"] if enabled else "#e9e9ee")
            b.color = C(s["text"] if enabled else "#b5b5bd")

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
        self.reveal_btn.disabled = False
        self.reveal_btn.set_bg(ACCENT)
        self._set_rating_enabled(False)
        if not self.queue:
            self._save()
            self.word_label.text = "全部完成"
            self.phonetic_label.text = ""
            self.meaning_label.text = ""
            self.example_label.text = ""
            self._flash("今天没有需要复习的单词了")
            self._update_stats()
            return
        word = self.queue.pop(0)
        self.current = self.word_map[word]
        self.word_label.text = self.current["word"]
        self.phonetic_label.text = self.current.get("phonetic", "")
        self.meaning_label.text = ""
        self.example_label.text = ""
        self._update_stats()

    def reveal(self):
        if not self.current or self.revealed:
            return
        self.revealed = True
        self.meaning_label.text = self.current["meaning"]
        self.example_label.text = self.current["example"]
        self.reveal_btn.disabled = True
        self.reveal_btn.set_bg("#e9e9ee")
        self._set_rating_enabled(True)

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
        self._flash("进度已自动保存")
        self._show_next()

    # ---------- 状态 ----------
    def _update_stats(self):
        total = len(WORDS)
        pct = self.learned_total / total if total else 0
        self.stats_label.text = "待复习 {} · 新词 {} · 剩余 {}".format(
            self.review_total, self.new_total, len(self.queue))
        self.progress_label.text = "已学 {} / {} · {:.1f}%".format(
            self.learned_total, total, pct * 100)
        self.progress_bar.set_pct(pct)

    def _flash(self, msg):
        self.stats_label.text = msg
        if self._status_job:
            self._status_job.cancel()
        from kivy.clock import Clock
        self._status_job = Clock.schedule_once(lambda *a: self._update_stats(), 2.5)

    # ---------- 保存 / 重置 ----------
    def save_now(self):
        self._save()
        self._flash("进度已保存")

    def reset_progress(self):
        if not getattr(self, "_reset_armed", False):
            self._reset_armed = True
            self.reset_btn.text = "确认?"
            from kivy.clock import Clock
            if self._status_job:
                self._status_job.cancel()
            self._status_job = Clock.schedule_once(self._disarm_reset, 3.0)
            return
        self._reset_armed = False
        self.reset_btn.text = "重置"
        self.progress = {"cards": {}}
        self._save()
        self.done_today = 0
        self._build_session()
        self._show_next()
        self._flash("进度已重置")

    def _disarm_reset(self, *a):
        self._reset_armed = False
        self.reset_btn.text = "重置"


if __name__ == "__main__":
    WordApp().run()
