# -*- coding: utf-8 -*-
"""
运动世界校园 · 图形界面
"""
import sys, os, json, threading, queue, time, random

if getattr(sys, "frozen", False):
    HERE = os.path.dirname(os.path.abspath(sys.executable))
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
PROTO = os.path.join(HERE, "com.zjwh.android_wh_physicalfitness", "协议", "7.3.92")
sys.path.insert(0, PROTO)
STATE = os.path.join(PROTO, "_session.json")
SETTINGS = os.path.join(HERE, "settings.json")
LOG_FILE = os.path.join(HERE, "error.log")


def load_settings():
    try:
        with open(SETTINGS, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def get_accounts():
    return load_settings().get("accounts", []) or []


def _acc_key(a):
    """账号唯一键：学号 + 手机号，避免空值互相覆盖"""
    cid = str(a.get("campus_id") or "").strip()
    phone = str(a.get("phone") or "").strip()
    if cid and phone:
        return "cid:%s|phone:%s" % (cid, phone)
    if cid:
        return "cid:%s" % cid
    if phone:
        return "phone:%s" % phone
    return "name:%s" % str(a.get("name") or "").strip()


def upsert_account(info):
    st = load_settings()
    accs = st.get("accounts", []) or []
    key = _acc_key(info)
    # [FIX] 原来只用 campus_id 去重，字段为空时会互相覆盖，改用组合键
    out = [a for a in accs if _acc_key(a) != key]
    # 保留旧记录里的 token（同账号重新登录时以新值为准）
    out.append(info)
    st["accounts"] = out
    save_settings(st)


def switch_account(acc):
    """把指定账号写为当前登录态"""
    data = {k: acc.get(k) for k in ("phone", "name", "campus_id", "campus_name", "token", "uid", "unid")}
    with open(STATE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


APP_VERSION = "1.0.0"

STARTUP_DIR = os.path.join(os.environ.get("APPDATA", ""),
                           "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
STARTUP_LNK = os.path.join(STARTUP_DIR, "运动世界.lnk")


def is_autostart_on():
    return os.path.exists(STARTUP_LNK)


def set_autostart(enabled):
    """开启/关闭开机自启（写启动文件夹的快捷方式）"""
    try:
        if enabled:
            if getattr(sys, "frozen", False):
                target = sys.executable
                workdir = os.path.dirname(target)
            else:
                target = sys.executable
                workdir = HERE
            os.makedirs(STARTUP_DIR, exist_ok=True)
            ps = ("$ws = New-Object -ComObject WScript.Shell; "
                  "$s = $ws.CreateShortcut('%s'); "
                  "$s.TargetPath = '%s'; $s.WorkingDirectory = '%s'; $s.Save()") % (
                STARTUP_LNK.replace("'", "''"), target.replace("'", "''"), workdir.replace("'", "''"))
            import subprocess
            subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, timeout=20)
            return os.path.exists(STARTUP_LNK)
        else:
            if os.path.exists(STARTUP_LNK):
                os.remove(STARTUP_LNK)
            return True
    except Exception:
        return False


def save_settings(d):
    try:
        with open(SETTINGS, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass

if getattr(sys, "frozen", False):
    _tmp = os.path.join(HERE, ".tmp")
else:
    _tmp = os.path.join(HERE, ".tmp")
try:
    os.makedirs(_tmp, exist_ok=True)
    os.environ.setdefault("TMP", _tmp)
    os.environ.setdefault("TEMP", _tmp)
except Exception:
    pass

import tkinter as tk
from tkinter import ttk, messagebox

# ---------- 工具 ----------
FONT = ("Microsoft YaHei UI", 10)
FONT_BIG = ("Microsoft YaHei UI", 12, "bold")
FONT_TITLE = ("Microsoft YaHei UI", 14, "bold")
COLOR_BG = "#F7F8FA"
COLOR_PRIMARY = "#2D6CDF"


def load_session():
    if not os.path.exists(STATE):
        return None
    try:
        with open(STATE, "r", encoding="utf-8") as f:
            d = json.load(f)
        if d.get("token") and d.get("uid"):
            return d
    except Exception:
        pass
    return None


def parse_pace(text):
    text = str(text).strip().replace("：", ":")
    if ":" in text:
        m, s = text.split(":", 1)
        return float(m) + float(s) / 60.0
    return float(text)


def fmt_pace(p):
    m = int(p)
    s = int(round((p - m) * 60))
    if s == 60:
        m += 1
        s = 0
    return "%d:%02d" % (m, s)


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("运动世界校园")
        self.root.geometry("600x680")
        self.root.configure(bg=COLOR_BG)
        self.root.resizable(False, False)

        self.sess = load_session()
        self.client = None
        self.msgq = queue.Queue()
        self.busy = False
        self.daily_last = load_settings().get("daily_last", "")
        self.scheduler_started = False

        st = load_settings()
        self.distance = tk.StringVar(value=str(st.get("distance", "1010")))
        self.pace = tk.StringVar(value=str(st.get("pace", "6:40")))
        self.rand_dist = tk.BooleanVar(value=bool(st.get("rand_dist", True)))
        self.rand_pace = tk.BooleanVar(value=bool(st.get("rand_pace", True)))
        self.status = tk.StringVar(value="")
        self.progress = tk.DoubleVar(value=0.0)
        self.stat_text = tk.StringVar(value="")

        self.build_ui()
        self.root.after(100, self.poll)
        self.refresh_info()
        self.start_scheduler()

    # ---------- 界面 ----------
    def build_ui(self):
        # 顶部：账户信息
        top = tk.Frame(self.root, bg=COLOR_BG)
        top.pack(fill="x", padx=18, pady=(16, 6))

        self.lbl_user = tk.Label(top, text="", font=FONT_TITLE, bg=COLOR_BG, fg="#222")
        self.lbl_user.pack(anchor="w")

        self.lbl_school = tk.Label(top, text="", font=FONT, bg=COLOR_BG, fg="#666")
        self.lbl_school.pack(anchor="w", pady=(2, 0))

        # 账号切换行
        self.acc_row = tk.Frame(top, bg=COLOR_BG)
        self.acc_row.pack(fill="x", pady=(6, 0))
        self.combo = ttk.Combobox(self.acc_row, state="readonly", width=26, font=FONT)
        self.combo.pack(side="left")
        self.combo.bind("<<ComboboxSelected>>", self.on_switch_account)
        self.btn_add = tk.Button(self.acc_row, text="+ 添加账号", font=FONT, bg="white", fg="#333",
                                 relief="solid", bd=1, cursor="hand2", command=self.on_login)
        self.btn_add.pack(side="left", padx=(6, 0), ipady=1)

        # 学期进度
        card = tk.Frame(self.root, bg="white", highlightbackground="#E3E6EB", highlightthickness=1)
        card.pack(fill="x", padx=18, pady=10)

        self.lbl_stat = tk.Label(card, textvariable=self.stat_text, font=FONT, bg="white",
                                 fg="#333", justify="left", anchor="w")
        self.lbl_stat.pack(fill="x", padx=14, pady=(10, 4))

        self.bar = ttk.Progressbar(card, mode="determinate", maximum=100)
        self.bar.pack(fill="x", padx=14, pady=(0, 10))

        # 参数区
        form = tk.Frame(self.root, bg="white", highlightbackground="#E3E6EB", highlightthickness=1)
        form.pack(fill="x", padx=18, pady=(0, 10))

        row1 = tk.Frame(form, bg="white"); row1.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(row1, text="距离", font=FONT, bg="white", width=6, anchor="w").pack(side="left")
        tk.Entry(row1, textvariable=self.distance, font=FONT, width=8).pack(side="left")
        tk.Label(row1, text="米", font=FONT, bg="white").pack(side="left", padx=(4, 12))
        tk.Checkbutton(row1, text="每次随机", variable=self.rand_dist, font=FONT,
                       bg="white", activebackground="white").pack(side="left")

        row2 = tk.Frame(form, bg="white"); row2.pack(fill="x", padx=14, pady=(0, 6))
        tk.Label(row2, text="配速", font=FONT, bg="white", width=6, anchor="w").pack(side="left")
        tk.Entry(row2, textvariable=self.pace, font=FONT, width=8).pack(side="left")
        tk.Label(row2, text="分/公里", font=FONT, bg="white").pack(side="left", padx=(4, 12))
        tk.Checkbutton(row2, text="每次随机", variable=self.rand_pace, font=FONT,
                       bg="white", activebackground="white").pack(side="left")

        row3 = tk.Frame(form, bg="white"); row3.pack(fill="x", padx=14, pady=(0, 12))
        self.lbl_est = tk.Label(row3, text="", font=FONT, bg="white", fg="#888")
        self.lbl_est.pack(anchor="w")
        for v in (self.distance, self.pace):
            v.trace_add("write", lambda *a: self.update_estimate())

        # 主按钮
        btn_area = tk.Frame(self.root, bg=COLOR_BG)
        btn_area.pack(fill="x", padx=18, pady=(4, 6))

        self.btn_run = tk.Button(btn_area, text="开始跑步", font=FONT_BIG,
                                 bg=COLOR_PRIMARY, fg="white", relief="flat",
                                 activebackground="#1F57B8", activeforeground="white",
                                 cursor="hand2", command=self.on_run)
        self.btn_run.pack(fill="x", ipady=10)

        # 副按钮
        sub = tk.Frame(self.root, bg=COLOR_BG)
        sub.pack(fill="x", padx=18, pady=(0, 10))

        self.btn_login = tk.Button(sub, text="登录", font=FONT, bg="white", fg="#333",
                                   relief="solid", bd=1, cursor="hand2", command=self.on_login)
        self.btn_login.pack(side="left", expand=True, fill="x", padx=(0, 4), ipady=5)

        self.btn_refresh = tk.Button(sub, text="刷新记录", font=FONT, bg="white", fg="#333",
                                     relief="solid", bd=1, cursor="hand2", command=self.refresh_info)
        self.btn_refresh.pack(side="left", expand=True, fill="x", padx=4, ipady=5)

        self.btn_logout = tk.Button(sub, text="退出登录", font=FONT, bg="white", fg="#333",
                                    relief="solid", bd=1, cursor="hand2", command=self.on_logout)
        self.btn_logout.pack(side="left", expand=True, fill="x", padx=(4, 0), ipady=5)

        sub2 = tk.Frame(self.root, bg=COLOR_BG)
        sub2.pack(fill="x", padx=18, pady=(0, 6))
        self.btn_setting = tk.Button(sub2, text="⚙ 设置（开机自启 / 每日自动跑）", font=FONT,
                                     bg="white", fg="#555", relief="solid", bd=1,
                                     cursor="hand2", command=self.on_settings)
        self.btn_setting.pack(fill="x", ipady=4)

        # 状态区
        self.lbl_status = tk.Label(self.root, textvariable=self.status, font=FONT,
                                   bg=COLOR_BG, fg="#666", wraplength=440, justify="left")
        self.lbl_status.pack(fill="x", padx=18, pady=(4, 2))

        tk.Label(self.root, text="v%s" % APP_VERSION, font=("Microsoft YaHei UI", 8),
                 bg=COLOR_BG, fg="#BBB").pack(pady=(0, 8))

        self.update_estimate()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_settings(self):
        st = load_settings()
        win = tk.Toplevel(self.root)
        win.title("设置")
        win.geometry("380x430")
        win.configure(bg="white")
        win.transient(self.root)
        win.grab_set()

        v_auto = tk.BooleanVar(value=is_autostart_on())
        v_daily = tk.BooleanVar(value=bool(st.get("daily_enabled", False)))
        v_time = tk.StringVar(value=str(st.get("daily_time", "08:00")))
        v_dist = tk.StringVar(value=str(st.get("daily_distance", self.distance.get())))

        tk.Label(win, text="启动", font=("Microsoft YaHei UI", 11, "bold"),
                 bg="white", fg="#333").pack(anchor="w", padx=24, pady=(20, 6))
        tk.Checkbutton(win, text="开机时自动启动本程序", variable=v_auto, font=FONT,
                       bg="white", activebackground="white").pack(anchor="w", padx=24)

        tk.Label(win, text="每日自动跑步", font=("Microsoft YaHei UI", 11, "bold"),
                 bg="white", fg="#333").pack(anchor="w", padx=24, pady=(18, 6))

        row1 = tk.Frame(win, bg="white"); row1.pack(fill="x", padx=24)
        tk.Checkbutton(row1, text="每天自动跑一次", variable=v_daily, font=FONT,
                       bg="white", activebackground="white").pack(side="left")
        tk.Entry(row1, textvariable=v_time, font=FONT, width=7).pack(side="left", padx=(10, 0))

        row2 = tk.Frame(win, bg="white"); row2.pack(fill="x", padx=24, pady=(10, 0))
        tk.Label(row2, text="距离", font=FONT, bg="white").pack(side="left")
        tk.Entry(row2, textvariable=v_dist, font=FONT, width=8).pack(side="left", padx=(8, 4))
        tk.Label(row2, text="米", font=FONT, bg="white").pack(side="left")

        tk.Label(win, text="程序需要保持打开才会自动跑\n失败时会在下方状态栏红字提示",
                 font=FONT, bg="white", fg="#999", justify="left").pack(anchor="w", padx=24, pady=(16, 4))

        # 版本信息（只显示，不联网检查）
        tk.Label(win, text="版本 v%s" % APP_VERSION, font=FONT, bg="white", fg="#BBB").pack(
            anchor="w", padx=24, pady=(10, 0))

        def save():
            old_auto = is_autostart_on()
            ok_auto = set_autostart(v_auto.get())
            if v_auto.get() and not ok_auto:
                messagebox.showerror("失败", "开机自启设置失败（可能被安全软件拦截）")
                return
            d = load_settings()
            d.update({
                "daily_enabled": bool(v_daily.get()),
                "daily_time": v_time.get().strip(),
                "daily_distance": v_dist.get().strip(),
            })
            save_settings(d)
            self.daily_last = d.get("daily_last", "")
            self.set_status("设置已保存", "#1a7f37")
            win.destroy()

        btns = tk.Frame(win, bg="white"); btns.pack(side="bottom", fill="x", pady=18, padx=24)
        tk.Button(btns, text="保存", font=FONT_BIG, bg=COLOR_PRIMARY, fg="white",
                  relief="flat", command=save).pack(side="left", expand=True, fill="x", ipady=5, padx=(0, 6))
        tk.Button(btns, text="取消", font=FONT, bg="#EEE", fg="#333",
                  relief="flat", command=win.destroy).pack(side="left", expand=True, fill="x", ipady=5)

    def start_scheduler(self):
        """每分钟检查一次，到点自动跑"""
        if self.scheduler_started:
            return
        self.scheduler_started = True

        def tick():
            while True:
                time.sleep(30)
                try:
                    st = load_settings()
                    if not st.get("daily_enabled"):
                        continue
                    want = str(st.get("daily_time", "08:00"))
                    today = time.strftime("%Y-%m-%d")
                    last = st.get("daily_last", "")
                    now = time.strftime("%H:%M")
                    if last == today:
                        continue
                    if now >= want and self.sess and not self.busy:
                        # 记录今天已跑，避免重复
                        st["daily_last"] = today
                        save_settings(st)
                        try:
                            dist = int(float(st.get("daily_distance", 1010)))
                        except Exception:
                            dist = 1010
                        self.msgq.put(("status", ("⏰ 每日自动跑步开始（%d 米）" % dist, "#888")))
                        threading.Thread(target=self._auto_run, args=(dist,), daemon=True).start()
                except Exception:
                    pass

        threading.Thread(target=tick, daemon=True).start()

    def _auto_run(self, dist):
        try:
            c = self._get_client()
            if not c:
                self.msgq.put(("status", ("⏰ 自动跑步跳过：未登录", "#c0392b")))
                return
            pace = parse_pace(self.pace.get() or "6:40")
            pace = pace * random.uniform(0.97, 1.04)
            sec = int(round(dist / 1000.0 * pace * 60))
            def cb(msg):
                self.msgq.put(("status", ("⏰ " + str(msg), "#888")))
            r = c.execute_run(target_distance_m=dist, target_time_sec=sec,
                              sport_type=1, progress_callback=cb)
            if getattr(r, "success", False):
                self.msgq.put(("status", ("⏰ 今日自动跑步完成，记录号 %s" % getattr(r, "rrid", "?"), "#1a7f37")))
                self.msgq.put(("run_ok", {
                    "rrid": getattr(r, "rrid", None), "distance": dist, "time": sec,
                    "pace": fmt_pace(pace), "complete": getattr(r, "is_valid", None),
                    "reasons": [], "valid_dis": None,
                }))
            else:
                self.msgq.put(("status", ("⏰ 自动跑步失败：%s" % (getattr(r, "message", "") or "未知"), "#c0392b")))
        except Exception as e:
            self.msgq.put(("status", ("⏰ 自动跑步异常：%s" % e, "#c0392b")))

    def on_close(self):
        save_settings({
            "distance": self.distance.get(),
            "pace": self.pace.get(),
            "rand_dist": bool(self.rand_dist.get()),
            "rand_pace": bool(self.rand_pace.get()),
        })
        self.root.destroy()

    # ---------- 逻辑 ----------
    def set_status(self, text, color="#666"):
        self.status.set(text)
        self.lbl_status.configure(fg=color)

    def update_estimate(self):
        try:
            d = float(self.distance.get())
            p = parse_pace(self.pace.get())
            if d > 0 and p > 0:
                sec = int(round(d / 1000.0 * p * 60))
                self.lbl_est.configure(
                    text="预计用时 %d 分 %d 秒（配速 %s 分/公里）" % (sec // 60, sec % 60, fmt_pace(p)))
            else:
                self.lbl_est.configure(text="")
        except Exception:
            self.lbl_est.configure(text="")

    def on_switch_account(self, event=None):
        idx = self.combo.current()
        accs = get_accounts()
        if idx < 0 or idx >= len(accs):
            return
        acc = accs[idx]
        try:
            switch_account(acc)
        except Exception as e:
            messagebox.showerror("切换失败", str(e))
            return
        self.sess = None
        self.client = None
        self.refresh_info()

    def _reload_combo(self):
        accs = get_accounts()
        vals = ["%s (%s)" % (a.get("name", "?"), a.get("campus_id", "?")) for a in accs]
        self.combo["values"] = vals
        cur = None
        if self.sess:
            target = str(self.sess.get("campus_id") or "")
            for i, a in enumerate(accs):
                if str(a.get("campus_id") or "") == target:
                    cur = i
                    break
        if cur is not None:
            self.combo.current(cur)
        elif vals:
            self.combo.set("")

    def refresh_info(self):
        self.sess = load_session()
        # 当前登录的账号若不在列表里，自动补进去（兼容旧版本登录）
        if self.sess:
            try:
                accs = get_accounts()
                cid = str(self.sess.get("campus_id") or "")
                if cid and not any(str(a.get("campus_id") or "") == cid for a in accs):
                    upsert_account(self.sess)
            except Exception:
                pass
        self._reload_combo()
        if not self.sess:
            self.lbl_user.configure(text="未登录")
            self.lbl_school.configure(text="点击下方「登录」开始")
            self.stat_text.set("登录后可查看学期进度")
            self.bar["value"] = 0
            self.btn_login.configure(text="登录")
            return

        self.lbl_user.configure(text="%s · %s" % (self.sess.get("name", "?"), self.sess.get("campus_id", "?")))
        self.lbl_school.configure(text=self.sess.get("campus_name", ""))
        self.btn_login.configure(text="重新登录")
        self.stat_text.set("正在读取学期进度…")
        self.run_bg(self._fetch_stats)

    def run_bg(self, fn):
        """在后台线程执行 fn，fn 通过 self.msgq 回报"""
        self.busy = True
        def _wrap():
            try:
                fn()
            except Exception:
                import traceback
                _excepthook(*sys.exc_info())
        t = threading.Thread(target=_wrap, daemon=True)
        t.start()

    def send(self, kind, payload=None):
        self.msgq.put((kind, payload))

    def poll(self):
        try:
            while True:
                kind, payload = self.msgq.get_nowait()
                if kind == "status":
                    self.set_status(payload[0], payload[1] if len(payload) > 1 else "#666")
                elif kind == "stats":
                    self._apply_stats(payload)
                    self.busy = False   # [FIX] 读取完必须复位，否则按钮全部失效
                elif kind == "run_ok":
                    self.busy = False
                    self.btn_run.configure(state="normal", text="开始跑步")
                    self.show_result(payload)
                    self.refresh_info()
                elif kind == "run_err":
                    self.set_status(payload, "#c0392b")
                    self.busy = False
                    self.btn_run.configure(state="normal", text="开始跑步")
                elif kind == "login_ok":
                    self.busy = False
                    self.refresh_info()
                elif kind == "login_err":
                    self.busy = False
                    self.set_status(payload, "#c0392b")
                elif kind == "need_login":
                    self.busy = False
                    self.btn_run.configure(state="normal", text="开始跑步")
                    self.set_status(payload, "#c0392b")
                    if messagebox.askyesno("需要重新登录", "登录态已失效，现在去登录吗？"):
                        self.on_login()
        except queue.Empty:
            pass
        self.root.after(120, self.poll)

    def _get_client(self):
        if self.client is None and self.sess:
            from sport_client import SportClient792
            self.client = SportClient792(uid=self.sess["uid"], token=self.sess["token"],
                                         unid=self.sess.get("unid"))
        return self.client

    def _fetch_stats(self):
        try:
            c = self._get_client()
            if not c:
                self.send("stats", None)
                return
            sp = c.get_semester_progress(run_mode=1)
            done = float(getattr(sp, "total_completed_distance", 0) or 0) if sp else 0
            target = float(getattr(sp, "target_distance", 0) or 0) if sp else 0
            cnt = getattr(sp, "valid_count", 0) if sp else 0
            name = getattr(sp, "semester_name", "") if sp else ""

            # 7.3.93 的学期接口不返回总里程，只有有效次数。里程靠历史记录累加。
            if done <= 0:
                try:
                    h = c.get_history_records(page_num=1, page_size=60)
                    recs = []
                    def walk(o, d=0):
                        if d > 6:
                            return
                        if isinstance(o, dict):
                            if "rrid" in o and ("totalDis" in o or "totalDistance" in o):
                                recs.append(o)
                                return
                            for v in o.values():
                                walk(v, d + 1)
                        elif isinstance(o, list):
                            for v in o:
                                walk(v, d + 1)
                    walk(h)
                    seen, uniq = set(), []
                    for r in recs:
                        rid = r.get("rrid") or r.get("id")
                        if rid and rid not in seen:
                            seen.add(rid)
                            uniq.append(r)
                    if uniq:
                        done = sum(float(r.get("totalDis") or r.get("totalDistance") or 0) for r in uniq)
                except Exception:
                    pass

            self.send("stats", {"done": done, "target": target, "count": cnt, "name": name})
        except Exception as e:
            self.send("stats", {"error": str(e)})

    def _apply_stats(self, d):
        if not d:
            self.stat_text.set("暂无数据")
            self.bar["value"] = 0
            return
        if d.get("error"):
            self.stat_text.set("读取失败：%s" % d["error"][:40])
            return
        done, target, cnt = d["done"], d["target"], d["count"]
        if target > 0:
            pct = min(100.0, done / target * 100)
            self.stat_text.set("本学期完成 %.2f / %.2f 公里 · %.1f%%（有效 %d 次）"
                               % (done / 1000, target / 1000, pct, cnt))
            self.bar["value"] = pct
        else:
            self.stat_text.set("本学期完成 %.2f 公里 · 有效 %d 次（学校未设目标）"
                               % (done / 1000, cnt))
            self.bar["value"] = min(100.0, done / 30000.0 * 100) if done > 0 else 0

    # ---------- 动作 ----------
    def on_run(self):
        if self.busy:
            self.set_status("正在处理上一个操作，请稍等…", "#c0392b")
            return
        if not self.sess:
            messagebox.showwarning("还没登录", "请先点下方「登录」")
            return
        try:
            d = float(self.distance.get())
            p = parse_pace(self.pace.get())
        except Exception:
            messagebox.showerror("格式错误", "距离填数字，配速填 6:40 这种格式")
            return

        if self.rand_dist.get():
            d = random.randint(int(d * 0.97), int(d * 1.08))
        if self.rand_pace.get():
            p = p * random.uniform(0.96, 1.05)

        if d < 1000:
            messagebox.showerror("距离太短", "学校要求单次至少 1000 米")
            return
        if p < 2.35 or p > 10.0:
            messagebox.showerror("配速超范围", "学校允许 %s ~ %s 分/公里"
                                 % (fmt_pace(2.35), fmt_pace(10.0)))
            return

        sec = int(round(d / 1000.0 * p * 60))
        if not messagebox.askyesno("确认跑步",
                                   "距离：%d 米\n配速：%s 分/公里\n用时：%d 分 %d 秒\n\n开始吗？"
                                   % (d, fmt_pace(p), sec // 60, sec % 60)):
            return

        self.busy = True
        self.btn_run.configure(state="disabled", text="跑步中…")
        self.set_status("正在提交…", "#888")

        def job():
            try:
                c = self._get_client()
                def cb(msg):
                    self.send("status", (str(msg), "#888"))
                r = c.execute_run(target_distance_m=int(d), target_time_sec=sec,
                                  sport_type=1, progress_callback=cb)
                if not getattr(r, "success", False):
                    self.send("run_err", "提交失败：%s" % (getattr(r, "message", "") or "未知"))
                    return

                rrid = getattr(r, "rrid", None)
                info = {
                    "rrid": rrid,
                    "distance": int(d),
                    "time": sec,
                    "pace": fmt_pace(p),
                    "complete": None,
                    "reasons": [],
                    "valid_dis": None,
                }
                # 查服务端判定详情
                try:
                    detail = c.get_run_record_detail(rrid)
                    raw = getattr(detail, "raw", None) or {}
                    info["complete"] = raw.get("complete")
                    info["valid_dis"] = raw.get("validDis")
                    for item in (raw.get("reasonList") or []):
                        info["reasons"].append({
                            "ok": bool(item.get("complete")),
                            "text": item.get("reason", ""),
                        })
                except Exception as e:
                    info["error"] = str(e)[:60]

                self.send("run_ok", info)
            except Exception as e:
                msg = str(e)
                low = msg.lower()
                if ("401" in msg) or ("鉴权" in msg) or ("token" in low) or ("未授权" in msg):
                    self.send("need_login", "登录已过期，请点「重新登录」")
                else:
                    self.send("run_err", "出错了：%s" % msg)

        threading.Thread(target=job, daemon=True).start()

    def on_login(self):
        if self.busy:
            return
        win = tk.Toplevel(self.root)
        win.title("登录")
        win.geometry("340x220")
        win.configure(bg=COLOR_BG)
        win.transient(self.root)
        win.grab_set()

        def _on_close():
            self.busy = False   # [FIX] 中途关窗也要复位
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", _on_close)

        tk.Label(win, text="手机号", font=FONT, bg=COLOR_BG).pack(anchor="w", padx=20, pady=(18, 4))
        e_phone = tk.Entry(win, font=FONT, width=28)
        e_phone.pack(padx=20, anchor="w")
        if self.sess and self.sess.get("phone"):
            e_phone.insert(0, self.sess["phone"])

        tk.Label(win, text="密码", font=FONT, bg=COLOR_BG).pack(anchor="w", padx=20, pady=(12, 4))
        e_pwd = tk.Entry(win, font=FONT, width=28, show="*")
        e_pwd.pack(padx=20, anchor="w")

        lbl = tk.Label(win, text="", font=FONT, bg=COLOR_BG, fg="#c0392b")
        lbl.pack(pady=(8, 0))

        def do():
            phone = e_phone.get().strip()
            pwd = e_pwd.get()
            if not phone or not pwd:
                lbl.configure(text="请填写手机号和密码")
                return
            lbl.configure(text="登录中，请等 20~60 秒…", fg="#888")
            self.busy = True

            def job():
                try:
                    from login import LoginClient
                    c = LoginClient()
                    r = c.login(phone, pwd)
                    if getattr(r, "success", False):
                        u = r.user
                        info = {
                            "phone": phone,
                            "name": getattr(u, "name", ""),
                            "campus_id": getattr(u, "campus_id", ""),
                            "campus_name": getattr(u, "campus_name", ""),
                            "token": getattr(u, "token", ""),
                            "uid": getattr(u, "uid", ""),
                            "unid": getattr(u, "unid", ""),
                        }
                        with open(STATE, "w", encoding="utf-8") as f:
                            json.dump(info, f, ensure_ascii=False, indent=2)
                        upsert_account(info)   # 记入账号列表
                        self.client = None
                        self.send("login_ok")
                        win.after(0, win.destroy)
                    else:
                        self.send("login_err", "登录失败：%s" % (getattr(r, "message", "") or "未知"))
                        win.after(0, lambda: lbl.configure(text="登录失败，看下方提示", fg="#c0392b"))
                except Exception as e:
                    self.send("login_err", "异常：%s" % e)
                    win.after(0, lambda: lbl.configure(text="出错了，看下方提示", fg="#c0392b"))

            threading.Thread(target=job, daemon=True).start()

        tk.Button(win, text="登录", font=FONT_BIG, bg=COLOR_PRIMARY, fg="white",
                  relief="flat", command=do).pack(pady=14, ipadx=30, ipady=4)

    def show_result(self, info):
        """跑完弹结果窗，显示服务端判定"""
        win = tk.Toplevel(self.root)
        win.title("跑步结果")
        win.geometry("400x560")
        win.configure(bg="white")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        complete = info.get("complete")
        if complete is True:
            head, hcolor = "✓  达标", "#1a7f37"
        elif complete is False:
            head, hcolor = "✗  未达标", "#c0392b"
        else:
            head, hcolor = "已提交", "#666"

        tk.Label(win, text=head, font=("Microsoft YaHei UI", 20, "bold"),
                 bg="white", fg=hcolor).pack(pady=(24, 4))

        if info.get("error"):
            tk.Label(win, text="（无法读取判定详情：%s）" % info["error"],
                     font=FONT, bg="white", fg="#c0392b", wraplength=320).pack(pady=(0, 8))

        # 基本信息
        box = tk.Frame(win, bg="#F7F8FA")
        box.pack(fill="x", padx=26, pady=12)

        rows = [
            ("距离", "%d 米" % info.get("distance", 0)),
            ("配速", "%s 分/公里" % info.get("pace", "-")),
            ("用时", "%d 分 %d 秒" % (info.get("time", 0) // 60, info.get("time", 0) % 60)),
            ("记录号", str(info.get("rrid") or "-")),
        ]
        if info.get("valid_dis"):
            rows.append(("有效里程", "%.0f 米" % float(info["valid_dis"])))

        for label, value in rows:
            r = tk.Frame(box, bg="#F7F8FA")
            r.pack(fill="x", padx=14, pady=3)
            tk.Label(r, text=label, font=FONT, bg="#F7F8FA", fg="#888", width=8, anchor="w").pack(side="left")
            tk.Label(r, text=value, font=FONT, bg="#F7F8FA", fg="#222", anchor="w").pack(side="left")

        # 判定明细
        reasons = info.get("reasons") or []
        if reasons:
            tk.Label(win, text="判定明细", font=FONT, bg="white", fg="#888").pack(anchor="w", padx=26, pady=(6, 4))
            for it in reasons:
                mark = "✓" if it["ok"] else "✗"
                color = "#1a7f37" if it["ok"] else "#c0392b"
                row = tk.Frame(win, bg="white")
                row.pack(fill="x", padx=26, pady=1)
                tk.Label(row, text=mark, font=FONT, bg="white", fg=color, width=2).pack(side="left")
                tk.Label(row, text=it["text"], font=FONT, bg="white", fg="#333",
                         anchor="w", wraplength=280, justify="left").pack(side="left")

        tk.Button(win, text="好", font=FONT_BIG, bg=COLOR_PRIMARY, fg="white",
                  relief="flat", command=win.destroy).pack(side="bottom", pady=18, ipadx=36, ipady=5)

    def on_logout(self):
        if not self.sess:
            messagebox.showinfo("提示", "当前未登录")
            return
        if not messagebox.askyesno("退出登录", "确定要退出吗？\n退出后需要重新输入手机号密码。"):
            return
        # 清除本机保存的凭据：当前会话文件 + 账号列表里的明文 token
        try:
            cur = self.sess or {}
            cid = str(cur.get("campus_id") or "")
            phone = str(cur.get("phone") or "")
            os.remove(STATE)
            # [FIX] 原来只删 session，token 仍留在 settings.json 里，
            # 下拉框切回账号即可恢复登录 —— 现在一并清除
            st = load_settings()
            accs = st.get("accounts", []) or []
            for a in accs:
                same = ((cid and str(a.get("campus_id") or "") == cid) or
                        (phone and str(a.get("phone") or "") == phone))
                if same:
                    a["token"] = ""
                    a["uid"] = ""
                    a["unid"] = ""
            st["accounts"] = accs
            save_settings(st)
        except Exception as e:
            messagebox.showerror("失败", str(e))
            return
        self.sess = None
        self.client = None
        self.refresh_info()
        self.set_status("已退出登录，本机凭据已清除", "#1a7f37")


def _excepthook(tp, val, tb):
    """未捕获异常：写日志 + 弹窗，避免窗口无声消失"""
    import traceback
    text = "".join(traceback.format_exception(tp, val, tb))
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write("\n" + "=" * 60 + "\n")
            fh.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
            fh.write(text)
    except Exception:
        pass
    try:
        import tkinter.messagebox as mb
        mb.showerror("程序出错",
                     "发生了一个错误，详情已写入：\n%s\n\n%s" % (LOG_FILE, str(val)[:300]))
    except Exception:
        pass


def main():
    sys.excepthook = _excepthook
    root = tk.Tk()
    try:
        root.iconbitmap(default="")
    except Exception:
        pass
    App(root)
    # 启动时置顶一下，避免被其他窗口挡住
    try:
        root.attributes("-topmost", True)
        root.after(400, lambda: root.attributes("-topmost", False))
        root.lift()
        root.focus_force()
    except Exception:
        pass
    root.mainloop()


if __name__ == "__main__":
    main()