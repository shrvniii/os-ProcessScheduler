"""
==============================================================================
  GUI-BASED OS PROCESS MANAGER SIMULATOR  —  Dashboard Edition v3.0
  Author  : Shravani
  Version : 3.0
  File    : gui_process_manager.py

  Description:
    A premium, dashboard-style Tkinter GUI that simulates CPU scheduling using
    six algorithms: FCFS, SJF, SRTF, Priority, MLQ, and Round Robin.
    Features tabbed interface with Process Table, multi-row Gantt Chart,
    Ready Queue visualiser, and matplotlib-powered Statistics dashboard.

    States: New → Ready → Running → Waiting → Terminated

  Run with:
    python gui_process_manager.py

  Dependencies:
    - Python 3.8+
    - matplotlib  (pip install matplotlib)
==============================================================================
"""

import tkinter as tk
from tkinter import ttk, messagebox
import copy
import random
from collections import deque
import threading
import time

# matplotlib for Statistics tab charts
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# ─────────────────────────────────────────────────────────────────────────────
#  THEME / COLOUR CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
BG_DARK       = "#0f1117"
BG_PANEL      = "#1a1d27"
BG_CARD       = "#252836"
BG_CARD_ALT   = "#1e2130"
ACCENT        = "#6366f1"
ACCENT_HOVER  = "#818cf8"
ACCENT_DIM    = "#4f46e5"
TEXT_PRIMARY  = "#e2e8f0"
TEXT_SECONDARY= "#94a3b8"
TEXT_MUTED    = "#64748b"
TEXT_WHITE    = "#ffffff"

COL_RUNNING   = "#22c55e"
COL_READY     = "#eab308"
COL_WAITING   = "#3b82f6"
COL_TERMINATED= "#475569"
COL_NEW       = "#ec4899"

SUCCESS       = "#22c55e"
WARNING       = "#f59e0b"
ERROR         = "#ef4444"
BORDER        = "#2d3147"

GANTT_COLORS = [
    "#6366f1", "#22c55e", "#f59e0b", "#3b82f6",
    "#ec4899", "#14b8a6", "#f97316", "#8b5cf6",
    "#06b6d4", "#ef4444", "#84cc16", "#a855f7",
]

ALGO_COLORS = {
    "FCFS":        "#3b82f6",
    "SJF":         "#f59e0b",
    "SRTF":        "#22c55e",
    "Priority":    "#ec4899",
    "MLQ":         "#8b5cf6",
    "Round Robin": "#6366f1",
}


# ─────────────────────────────────────────────────────────────────────────────
#  DATA MODEL – Process Control Block (PCB)
# ─────────────────────────────────────────────────────────────────────────────
def make_pcb(pid, name, arrival, burst, priority, queue_level=1):
    return {
        "pid":        int(pid),
        "name":       str(name),
        "arrival":    int(arrival),
        "burst":      int(burst),
        "priority":   int(priority),
        "queue_level": int(queue_level),
        "remaining":  int(burst),
        "status":     "New",
        "start_time": None,
        "completion": None,
        "turnaround": None,
        "waiting":    None,
        "response":   None,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  SCHEDULING ALGORITHMS
# ─────────────────────────────────────────────────────────────────────────────

def run_fcfs(processes):
    """First Come, First Served – Non-preemptive."""
    procs = sorted(copy.deepcopy(processes), key=lambda p: (p["arrival"], p["pid"]))
    gantt = []
    clock = 0
    for p in procs:
        if clock < p["arrival"]:
            gantt.append({"pid": -1, "name": "IDLE", "start": clock, "end": p["arrival"]})
            clock = p["arrival"]
        p["start_time"] = clock
        p["status"] = "Running"
        gantt.append({"pid": p["pid"], "name": f'P{p["pid"]}',
                      "start": clock, "end": clock + p["burst"]})
        clock += p["burst"]
        p["completion"] = clock
        p["status"] = "Terminated"
        p["turnaround"] = p["completion"] - p["arrival"]
        p["waiting"] = p["turnaround"] - p["burst"]
        p["response"] = p["start_time"] - p["arrival"]
    return procs, gantt


def run_sjf(processes):
    """Shortest Job First – Non-preemptive."""
    procs = copy.deepcopy(processes)
    remaining = list(procs)
    done = []
    gantt = []
    clock = 0
    while remaining:
        available = [p for p in remaining if p["arrival"] <= clock]
        if not available:
            nxt = min(p["arrival"] for p in remaining)
            gantt.append({"pid": -1, "name": "IDLE", "start": clock, "end": nxt})
            clock = nxt
            continue
        p = min(available, key=lambda x: (x["burst"], x["arrival"], x["pid"]))
        remaining.remove(p)
        p["start_time"] = clock
        p["status"] = "Running"
        gantt.append({"pid": p["pid"], "name": f'P{p["pid"]}',
                      "start": clock, "end": clock + p["burst"]})
        clock += p["burst"]
        p["completion"] = clock
        p["status"] = "Terminated"
        p["turnaround"] = p["completion"] - p["arrival"]
        p["waiting"] = p["turnaround"] - p["burst"]
        p["response"] = p["start_time"] - p["arrival"]
        done.append(p)
    done.sort(key=lambda p: p["pid"])
    return done, gantt


def run_srtf(processes):
    """Shortest Remaining Time First – Preemptive SJF."""
    procs = sorted(copy.deepcopy(processes), key=lambda p: (p["arrival"], p["pid"]))
    for p in procs:
        p["remaining"] = p["burst"]
    done = []
    gantt = []
    clock = 0
    total_time = sum(p["burst"] for p in procs)
    max_time = max(p["arrival"] for p in procs) + total_time + 1

    while len(done) < len(procs) and clock < max_time:
        available = [p for p in procs if p["arrival"] <= clock
                     and p["remaining"] > 0 and p["status"] != "Terminated"]
        if not available:
            nxt_arrivals = [p["arrival"] for p in procs
                            if p["arrival"] > clock and p["status"] != "Terminated"]
            if nxt_arrivals:
                nxt = min(nxt_arrivals)
                gantt.append({"pid": -1, "name": "IDLE", "start": clock, "end": nxt})
                clock = nxt
            else:
                break
            continue
        p = min(available, key=lambda x: (x["remaining"], x["arrival"], x["pid"]))
        if p["start_time"] is None:
            p["start_time"] = clock
        p["status"] = "Running"
        # Run for 1 unit (preemptive)
        gantt.append({"pid": p["pid"], "name": f'P{p["pid"]}',
                      "start": clock, "end": clock + 1})
        clock += 1
        p["remaining"] -= 1
        if p["remaining"] == 0:
            p["completion"] = clock
            p["status"] = "Terminated"
            p["turnaround"] = p["completion"] - p["arrival"]
            p["waiting"] = p["turnaround"] - p["burst"]
            p["response"] = p["start_time"] - p["arrival"]
            done.append(p)
        else:
            p["status"] = "Ready"

    # Merge consecutive same-pid gantt segments
    merged = []
    for seg in gantt:
        if merged and merged[-1]["pid"] == seg["pid"] and merged[-1]["end"] == seg["start"]:
            merged[-1]["end"] = seg["end"]
        else:
            merged.append(dict(seg))

    done.sort(key=lambda p: p["pid"])
    return done, merged


def run_priority(processes):
    """Priority Scheduling – Non-preemptive (lower number = higher priority)."""
    procs = copy.deepcopy(processes)
    remaining = list(procs)
    done = []
    gantt = []
    clock = 0
    while remaining:
        available = [p for p in remaining if p["arrival"] <= clock]
        if not available:
            nxt = min(p["arrival"] for p in remaining)
            gantt.append({"pid": -1, "name": "IDLE", "start": clock, "end": nxt})
            clock = nxt
            continue
        p = min(available, key=lambda x: (x["priority"], x["arrival"], x["pid"]))
        remaining.remove(p)
        p["start_time"] = clock
        p["status"] = "Running"
        gantt.append({"pid": p["pid"], "name": f'P{p["pid"]}',
                      "start": clock, "end": clock + p["burst"]})
        clock += p["burst"]
        p["completion"] = clock
        p["status"] = "Terminated"
        p["turnaround"] = p["completion"] - p["arrival"]
        p["waiting"] = p["turnaround"] - p["burst"]
        p["response"] = p["start_time"] - p["arrival"]
        done.append(p)
    done.sort(key=lambda p: p["pid"])
    return done, gantt


def run_mlq(processes):
    """
    Multi-Level Queue – 3 queues by priority level (queue_level field).
    Queue 1: highest priority (FCFS within queue)
    Queue 2: medium priority (Round Robin q=4)
    Queue 3: lowest priority (FCFS within queue)
    Higher queue level processes only run when all lower-level queues are empty.
    """
    procs = sorted(copy.deepcopy(processes), key=lambda p: (p["arrival"], p["pid"]))
    for p in procs:
        p["remaining"] = p["burst"]

    done = []
    gantt = []
    clock = 0
    not_arrived = list(procs)
    q1 = deque()  # priority 1 – FCFS
    q2 = deque()  # priority 2 – RR quantum=4
    q3 = deque()  # priority 3 – FCFS
    q2_quantum = 4

    def admit(t):
        for p in list(not_arrived):
            if p["arrival"] <= t:
                p["status"] = "Ready"
                ql = p.get("queue_level", 2)
                if ql == 1:
                    q1.append(p)
                elif ql == 3:
                    q3.append(p)
                else:
                    q2.append(p)
                not_arrived.remove(p)

    admit(clock)
    rr_remaining = {}  # pid -> remaining in current quantum

    while q1 or q2 or q3 or not_arrived:
        admit(clock)
        if not q1 and not q2 and not q3:
            if not_arrived:
                nxt = min(p["arrival"] for p in not_arrived)
                gantt.append({"pid": -1, "name": "IDLE", "start": clock, "end": nxt})
                clock = nxt
                admit(clock)
            continue

        if q1:
            p = q1.popleft()
        elif q2:
            p = q2.popleft()
            rr_remaining[p["pid"]] = min(q2_quantum, p["remaining"])
        else:
            p = q3.popleft()

        ql = p.get("queue_level", 2)

        if p["start_time"] is None:
            p["start_time"] = clock

        if ql == 2:
            # Round Robin in queue 2
            run_time = min(rr_remaining.get(p["pid"], q2_quantum), p["remaining"])
        else:
            run_time = p["remaining"]

        p["status"] = "Running"
        end_t = clock + run_time
        gantt.append({"pid": p["pid"], "name": f'P{p["pid"]}',
                      "start": clock, "end": end_t})
        for t in range(clock + 1, end_t + 1):
            admit(t)
        clock = end_t
        p["remaining"] -= run_time

        if p["remaining"] == 0:
            p["completion"] = clock
            p["status"] = "Terminated"
            p["turnaround"] = p["completion"] - p["arrival"]
            p["waiting"] = p["turnaround"] - p["burst"]
            p["response"] = p["start_time"] - p["arrival"]
            done.append(p)
        else:
            p["status"] = "Ready"
            if ql == 2:
                q2.append(p)
            elif ql == 1:
                q1.append(p)
            else:
                q3.append(p)

    done.sort(key=lambda p: p["pid"])
    return done, gantt


def run_rr(processes, quantum=2):
    """Round Robin – Preemptive (time-sliced)."""
    procs = sorted(copy.deepcopy(processes), key=lambda p: (p["arrival"], p["pid"]))
    for p in procs:
        p["remaining"] = p["burst"]

    not_arrived = list(procs)
    queue = deque()
    done = []
    gantt = []
    clock = 0

    def admit_arrivals(t):
        arrived = [p for p in not_arrived if p["arrival"] <= t]
        for p in arrived:
            p["status"] = "Ready"
            queue.append(p)
            not_arrived.remove(p)

    admit_arrivals(clock)

    while queue or not_arrived:
        if not queue:
            nxt = min(p["arrival"] for p in not_arrived)
            gantt.append({"pid": -1, "name": "IDLE", "start": clock, "end": nxt})
            clock = nxt
            admit_arrivals(clock)
            continue

        p = queue.popleft()
        p["status"] = "Running"
        if p["start_time"] is None:
            p["start_time"] = clock

        run_time = min(quantum, p["remaining"])
        end_time = clock + run_time
        gantt.append({"pid": p["pid"], "name": f'P{p["pid"]}',
                      "start": clock, "end": end_time})

        for t in range(clock + 1, end_time + 1):
            admit_arrivals(t)

        clock = end_time
        p["remaining"] -= run_time

        if p["remaining"] == 0:
            p["completion"] = clock
            p["status"] = "Terminated"
            p["turnaround"] = p["completion"] - p["arrival"]
            p["waiting"] = p["turnaround"] - p["burst"]
            p["response"] = p["start_time"] - p["arrival"]
            done.append(p)
        else:
            p["status"] = "Ready"
            queue.append(p)

    done.sort(key=lambda p: p["pid"])
    return done, gantt


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN APPLICATION CLASS
# ─────────────────────────────────────────────────────────────────────────────
class ProcessManagerApp(tk.Tk):

    PROCESS_NAMES = [
        "Chrome", "VSCode", "Terminal", "Spotify", "Firefox",
        "Slack", "Docker", "Discord", "Figma", "Git",
        "Node", "Python", "Nginx", "Redis", "MySQL",
    ]

    SAMPLE_PROCESSES = [
        make_pcb(pid=1, name="Chrome",   arrival=0, burst=8,  priority=2, queue_level=1),
        make_pcb(pid=2, name="VSCode",   arrival=1, burst=5,  priority=1, queue_level=2),
        make_pcb(pid=3, name="Terminal", arrival=2, burst=12, priority=3, queue_level=2),
        make_pcb(pid=4, name="Spotify",  arrival=3, burst=6,  priority=2, queue_level=3),
    ]

    def __init__(self):
        super().__init__()
        self.title("OS Process Manager Simulator  —  Shravani")
        self.geometry("1520x920")
        self.minsize(1300, 820)
        self.configure(bg=BG_DARK)
        self.resizable(True, True)

        # State
        self.processes     = []
        self.result_procs  = []
        self.result_gantt  = []
        self.algo_var      = tk.StringVar(value="FCFS")
        self.rr_quantum    = tk.IntVar(value=4)
        self.sim_running   = False
        self.sim_paused    = False
        self.current_algo  = "—"
        self.algo_history  = {}
        self.created_count = 0
        self._next_pid     = 5

        self._build_styles()
        self._build_ui()

        for pcb in self.SAMPLE_PROCESSES:
            self.processes.append(copy.deepcopy(pcb))
        self._refresh_all()

    # ──────────────────────────────────────────────────────────────────
    #  TTK STYLES
    # ──────────────────────────────────────────────────────────────────
    def _build_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")

        s.configure("Dashboard.TNotebook",
                    background=BG_DARK, borderwidth=0, tabmargins=[0, 0, 0, 0])
        s.configure("Dashboard.TNotebook.Tab",
                    background=BG_PANEL, foreground=TEXT_MUTED,
                    font=("Segoe UI", 10, "bold"),
                    padding=[18, 9], borderwidth=0)
        s.map("Dashboard.TNotebook.Tab",
              background=[("selected", BG_DARK)],
              foreground=[("selected", TEXT_WHITE)])

        for style in ("Proc.Treeview", "Metrics.Treeview"):
            s.configure(style,
                        background=BG_PANEL, foreground=TEXT_PRIMARY,
                        fieldbackground=BG_PANEL, rowheight=34,
                        font=("Consolas", 10), borderwidth=0)
            s.configure(f"{style}.Heading",
                        background=BG_CARD, foreground=TEXT_SECONDARY,
                        font=("Segoe UI", 9, "bold"), relief="flat")
            s.map(style,
                  background=[("selected", ACCENT_DIM)],
                  foreground=[("selected", TEXT_WHITE)])

        s.configure("Vertical.TScrollbar",
                    background=BG_PANEL, troughcolor=BG_DARK,
                    arrowcolor=TEXT_MUTED, borderwidth=0)
        s.configure("Horizontal.TScrollbar",
                    background=BG_PANEL, troughcolor=BG_DARK,
                    arrowcolor=TEXT_MUTED, borderwidth=0)

        s.configure("TCombobox",
                    fieldbackground=BG_CARD, background=BG_CARD,
                    foreground=TEXT_PRIMARY, selectbackground=ACCENT_DIM,
                    font=("Segoe UI", 9))

    # ──────────────────────────────────────────────────────────────────
    #  UI ASSEMBLY
    # ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_header()
        self._build_stats_row()
        self._build_main_area()

    # ── HEADER BAR ────────────────────────────────────────────────────
    def _build_header(self):
        bar = tk.Frame(self, bg=BG_PANEL, height=58)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # Left – Logo
        left = tk.Frame(bar, bg=BG_PANEL)
        left.pack(side="left", padx=20)

        badge = tk.Label(left, text=" OS ", bg=ACCENT, fg=TEXT_WHITE,
                         font=("Segoe UI", 11, "bold"), padx=8, pady=3)
        badge.pack(side="left", pady=12)

        tk.Label(left, text="  Process Manager Simulator",
                 bg=BG_PANEL, fg=TEXT_PRIMARY,
                 font=("Segoe UI", 15, "bold")).pack(side="left")

        # Right – status badges
        right = tk.Frame(bar, bg=BG_PANEL)
        right.pack(side="right", padx=20)

        self.lbl_status_badge = tk.Label(right, text=" Simulator Idle ",
                                          bg=BG_CARD, fg=TEXT_MUTED,
                                          font=("Segoe UI", 9, "bold"),
                                          padx=12, pady=5)
        self.lbl_status_badge.pack(side="left", padx=6, pady=14)

        self.lbl_algo_badge = tk.Label(right, text=" Algorithm: — ",
                                        bg=BG_CARD, fg=TEXT_MUTED,
                                        font=("Segoe UI", 9, "bold"),
                                        padx=12, pady=5)
        self.lbl_algo_badge.pack(side="left", padx=6, pady=14)

    # ── STATS CARDS ROW ───────────────────────────────────────────────
    def _build_stats_row(self):
        row = tk.Frame(self, bg=BG_DARK)
        row.pack(fill="x", padx=18, pady=(12, 6))

        cards_data = [
            ("TOTAL PROCESSES",  "0",  "",  "total"),
            ("CPU UTILIZATION",  "—",  "",  "cpu"),
            ("AVG TURNAROUND",   "—",  "",  "tat"),
            ("AVG WAITING TIME", "—",  "",  "wait"),
        ]

        for i, (title, value, sub, key) in enumerate(cards_data):
            card = tk.Frame(row, bg=BG_PANEL, padx=20, pady=14,
                            highlightbackground=BORDER, highlightthickness=1)
            card.pack(side="left", fill="both", expand=True,
                      padx=(0 if i == 0 else 6, 0 if i == 3 else 6))

            tk.Label(card, text=title, bg=BG_PANEL, fg=TEXT_MUTED,
                     font=("Segoe UI", 8, "bold")).pack(anchor="w")

            val_lbl = tk.Label(card, text=value, bg=BG_PANEL, fg=TEXT_PRIMARY,
                               font=("Segoe UI", 22, "bold"))
            val_lbl.pack(anchor="w", pady=(2, 0))

            sub_lbl = tk.Label(card, text=sub, bg=BG_PANEL, fg=TEXT_MUTED,
                               font=("Segoe UI", 8))
            sub_lbl.pack(anchor="w")

            setattr(self, f"stat_{key}_val", val_lbl)
            setattr(self, f"stat_{key}_sub", sub_lbl)

    # ── MAIN AREA ─────────────────────────────────────────────────────
    def _build_main_area(self):
        main = tk.Frame(self, bg=BG_DARK)
        main.pack(fill="both", expand=True, padx=18, pady=(6, 14))
        main.columnconfigure(0, weight=0, minsize=270)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        self._build_sidebar(main)
        self._build_tabbed_area(main)

    # ── SIDEBAR ───────────────────────────────────────────────────────
    def _build_sidebar(self, parent):
        sidebar = tk.Frame(parent, bg=BG_PANEL,
                           highlightbackground=BORDER, highlightthickness=1)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # Scroll frame for sidebar content
        scv = tk.Canvas(sidebar, bg=BG_PANEL, highlightthickness=0)
        sb_scroll = ttk.Scrollbar(sidebar, orient="vertical", command=scv.yview)
        sb_inner = tk.Frame(scv, bg=BG_PANEL)
        sb_inner.bind("<Configure>",
                      lambda e: scv.configure(scrollregion=scv.bbox("all")))
        scv.create_window((0, 0), window=sb_inner, anchor="nw")
        scv.configure(yscrollcommand=sb_scroll.set)
        scv.pack(side="left", fill="both", expand=True)
        sb_scroll.pack(side="right", fill="y")

        def _mw(event):
            scv.yview_scroll(int(-1 * (event.delta / 120)), "units")
        scv.bind_all("<MouseWheel>", _mw)

        # ── CREATE PROCESS ──────────────────────────────────────────
        self._section_label(sb_inner, "CREATE PROCESS")

        form = tk.Frame(sb_inner, bg=BG_PANEL)
        form.pack(fill="x", padx=14)

        self.ent_name     = self._sidebar_field(form, "Process name",          "e.g. P7")
        self.ent_burst    = self._sidebar_field(form, "Burst time (ms)",        "e.g. 8")
        self.ent_arrival  = self._sidebar_field(form, "Arrival time (ms)",      "e.g. 0")
        self.ent_priority = self._sidebar_field(form, "Priority (1 = highest)", "e.g. 2")

        # Queue Level
        ql_row = tk.Frame(form, bg=BG_PANEL)
        ql_row.pack(fill="x", pady=(6, 2))
        tk.Label(ql_row, text="Queue Level (MLQ)", bg=BG_PANEL,
                 fg=TEXT_SECONDARY, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 2))
        self.ql_var = tk.StringVar(value="2")
        ql_combo = ttk.Combobox(ql_row, textvariable=self.ql_var,
                                values=["1 (High)", "2 (Medium)", "3 (Low)"],
                                state="readonly", font=("Segoe UI", 9), width=14)
        ql_combo.pack(fill="x")

        btn_add = self._make_btn(sb_inner, "+ Add Process", BG_CARD,
                                 TEXT_PRIMARY, self._on_add_process)
        btn_add.pack(fill="x", padx=14, pady=(8, 4), ipady=8)

        self._divider(sb_inner)

        # ── SCHEDULING ALGORITHM ────────────────────────────────────
        self._section_label(sb_inner, "SCHEDULING ALGORITHM")

        algo_grid = tk.Frame(sb_inner, bg=BG_PANEL)
        algo_grid.pack(fill="x", padx=14)
        algo_grid.columnconfigure(0, weight=1)
        algo_grid.columnconfigure(1, weight=1)

        algos = [
            ("FCFS",        0, 0),
            ("Round Robin", 0, 1),
            ("SJF",         1, 0),
            ("Priority",    1, 1),
            ("SRTF",        2, 0),
            ("MLQ",         2, 1),
        ]

        self.algo_buttons = {}
        for name, r, c in algos:
            is_sel = (name == "FCFS")
            btn = tk.Button(algo_grid, text=name,
                            bg=ACCENT if is_sel else BG_CARD,
                            fg=TEXT_WHITE if is_sel else TEXT_MUTED,
                            font=("Segoe UI", 9, "bold"),
                            relief="flat", cursor="hand2", bd=0,
                            activebackground=ACCENT_HOVER,
                            activeforeground=TEXT_WHITE,
                            command=lambda n=name: self._select_algo(n))
            btn.grid(row=r, column=c, sticky="ew",
                     padx=(0 if c == 0 else 3, 3 if c == 0 else 0),
                     pady=3, ipady=7)
            self.algo_buttons[name] = btn

        # RR quantum frame
        self.rr_frame = tk.Frame(sb_inner, bg=BG_PANEL)
        rr_inner = tk.Frame(self.rr_frame, bg=BG_PANEL)
        rr_inner.pack(fill="x", padx=14, pady=(6, 0))
        tk.Label(rr_inner, text="ROUND ROBIN SETTINGS",
                 bg=BG_PANEL, fg=TEXT_MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 4))
        rr_row = tk.Frame(rr_inner, bg=BG_PANEL)
        rr_row.pack(fill="x")
        tk.Label(rr_row, text="Time Quantum",
                 bg=BG_PANEL, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 9)).pack(side="left")
        self.rr_entry = tk.Entry(rr_row, textvariable=self.rr_quantum,
                                  bg=BG_CARD, fg=TEXT_PRIMARY,
                                  insertbackground=TEXT_PRIMARY,
                                  font=("Consolas", 11), relief="flat",
                                  bd=3, width=5,
                                  highlightthickness=1,
                                  highlightcolor=ACCENT,
                                  highlightbackground=BORDER)
        self.rr_entry.pack(side="right")
        tk.Label(rr_row, text="ms", bg=BG_PANEL, fg=TEXT_MUTED,
                 font=("Segoe UI", 9)).pack(side="right", padx=(0, 4))

        self._divider(sb_inner)

        # ── SIMULATION CONTROLS ─────────────────────────────────────
        self._section_label(sb_inner, "SIMULATION CONTROLS")

        ctrl = tk.Frame(sb_inner, bg=BG_PANEL)
        ctrl.pack(fill="x", padx=14)

        self.btn_run = tk.Button(ctrl, text="▶  Run Simulation",
                                  bg=COL_RUNNING, fg=TEXT_WHITE,
                                  font=("Segoe UI", 11, "bold"),
                                  relief="flat", cursor="hand2", bd=0,
                                  activebackground="#16a34a",
                                  command=self._on_run_scheduler)
        self.btn_run.pack(fill="x", ipady=10, pady=(0, 4))

        self.btn_pause = tk.Button(ctrl, text="⏸  Pause",
                                    bg=BG_CARD, fg=TEXT_PRIMARY,
                                    font=("Segoe UI", 9, "bold"),
                                    relief="flat", cursor="hand2", bd=0,
                                    activebackground=BORDER,
                                    command=self._on_pause)
        self.btn_pause.pack(fill="x", ipady=6, pady=(0, 4))

        btn_row = tk.Frame(ctrl, bg=BG_PANEL)
        btn_row.pack(fill="x")
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)

        tk.Button(btn_row, text="↺  Reset",
                  bg=BG_CARD, fg=TEXT_PRIMARY,
                  font=("Segoe UI", 9), relief="flat",
                  cursor="hand2", bd=0,
                  activebackground=BORDER,
                  command=self._on_reset_all
                  ).grid(row=0, column=0, sticky="ew", padx=(0, 2), ipady=6)

        tk.Button(btn_row, text="■  Stop All",
                  bg=BG_CARD, fg=ERROR,
                  font=("Segoe UI", 9), relief="flat",
                  cursor="hand2", bd=0,
                  activebackground=BORDER,
                  command=self._on_stop_all
                  ).grid(row=0, column=1, sticky="ew", padx=(2, 0), ipady=6)

        self.lbl_sim_status = tk.Label(sb_inner, text="● Idle",
                                        bg=BG_PANEL, fg=TEXT_MUTED,
                                        font=("Segoe UI", 9))
        self.lbl_sim_status.pack(padx=14, pady=(8, 16), anchor="w")

    def _section_label(self, parent, text):
        tk.Label(parent, text=text, bg=BG_PANEL, fg=TEXT_MUTED,
                 font=("Segoe UI", 9, "bold")).pack(padx=14, pady=(14, 8), anchor="w")

    def _divider(self, parent):
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=14, pady=10)

    def _make_btn(self, parent, text, bg, fg, cmd):
        return tk.Button(parent, text=text, bg=bg, fg=fg,
                         font=("Segoe UI", 10, "bold"),
                         relief="flat", cursor="hand2", bd=0,
                         activebackground=BORDER, activeforeground=TEXT_WHITE,
                         command=cmd)

    def _sidebar_field(self, parent, label, placeholder):
        tk.Label(parent, text=label, bg=BG_PANEL, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(6, 2))
        entry = tk.Entry(parent,
                         bg=BG_CARD, fg=TEXT_MUTED,
                         insertbackground=TEXT_PRIMARY,
                         font=("Consolas", 10),
                         relief="flat", bd=4,
                         highlightthickness=1,
                         highlightcolor=ACCENT,
                         highlightbackground=BORDER)
        entry.pack(fill="x", ipady=5)
        entry.insert(0, placeholder)

        def _fin(e, ph=placeholder, ent=entry):
            if ent.get() == ph:
                ent.delete(0, "end")
                ent.config(fg=TEXT_PRIMARY)

        def _fout(e, ph=placeholder, ent=entry):
            if not ent.get().strip():
                ent.insert(0, ph)
                ent.config(fg=TEXT_MUTED)

        entry.bind("<FocusIn>", _fin)
        entry.bind("<FocusOut>", _fout)
        return entry

    # ── TABBED AREA ───────────────────────────────────────────────────
    def _build_tabbed_area(self, parent):
        self.notebook = ttk.Notebook(parent, style="Dashboard.TNotebook")
        self.notebook.grid(row=0, column=1, sticky="nsew")

        self.tab_procs = tk.Frame(self.notebook, bg=BG_DARK)
        self.notebook.add(self.tab_procs, text="  Process Table  ")
        self._build_process_table_tab()

        self.tab_gantt = tk.Frame(self.notebook, bg=BG_DARK)
        self.notebook.add(self.tab_gantt, text="  Gantt Chart  ")
        self._build_gantt_tab()

        self.tab_queue = tk.Frame(self.notebook, bg=BG_DARK)
        self.notebook.add(self.tab_queue, text="  Ready Queue  ")
        self._build_queue_tab()

        self.tab_stats = tk.Frame(self.notebook, bg=BG_DARK)
        self.notebook.add(self.tab_stats, text="  Statistics  ")
        self._build_stats_tab()

    # ── TAB 1: PROCESS TABLE ──────────────────────────────────────────
    def _build_process_table_tab(self):
        header = tk.Frame(self.tab_procs, bg=BG_DARK)
        header.pack(fill="x", padx=10, pady=(12, 6))

        tk.Label(header, text="All Processes",
                 bg=BG_DARK, fg=TEXT_PRIMARY,
                 font=("Segoe UI", 14, "bold")).pack(side="left")

        self.filter_var = tk.StringVar(value="All States")
        filter_cb = ttk.Combobox(
            header, textvariable=self.filter_var,
            values=["All States", "New", "Ready", "Running", "Waiting", "Terminated"],
            state="readonly", font=("Segoe UI", 9), width=14)
        filter_cb.pack(side="right")
        filter_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_process_table())

        # Main treeview
        tree_frame = tk.Frame(self.tab_procs, bg=BG_DARK)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        cols = ("PID", "Name", "State", "Burst", "Remaining", "Arrival", "Priority", "Queue")
        self.proc_tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                       style="Proc.Treeview", selectmode="browse")

        widths = {"PID": 55, "Name": 100, "State": 110, "Burst": 75,
                  "Remaining": 100, "Arrival": 75, "Priority": 72, "Queue": 65}
        for col in cols:
            self.proc_tree.heading(col, text=col.upper())
            self.proc_tree.column(col, width=widths[col], anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                             command=self.proc_tree.yview)
        self.proc_tree.configure(yscrollcommand=vsb.set)
        self.proc_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # State colour tags
        self.proc_tree.tag_configure("new",        background=BG_PANEL,     foreground=COL_NEW)
        self.proc_tree.tag_configure("ready",      background=BG_PANEL,     foreground=COL_READY)
        self.proc_tree.tag_configure("running",    background="#0d2318",     foreground=COL_RUNNING)
        self.proc_tree.tag_configure("waiting",    background="#0d1a2e",     foreground=COL_WAITING)
        self.proc_tree.tag_configure("terminated", background=BG_CARD_ALT,  foreground=COL_TERMINATED)

        # Performance metrics panel
        metrics_frame = tk.Frame(self.tab_procs, bg=BG_PANEL,
                                  highlightbackground=BORDER, highlightthickness=1)
        metrics_frame.pack(fill="x", padx=10, pady=(0, 10))

        tk.Label(metrics_frame, text="PERFORMANCE METRICS",
                 bg=BG_PANEL, fg=TEXT_MUTED,
                 font=("Segoe UI", 9, "bold")).pack(padx=12, pady=(8, 4), anchor="w")

        mf = tk.Frame(metrics_frame, bg=BG_PANEL)
        mf.pack(fill="x", padx=12, pady=(0, 4))

        met_cols = ("PID", "Name", "Arrival", "Burst", "Priority",
                    "Start", "Completion", "Turnaround", "Waiting", "Response")
        self.metrics_tree = ttk.Treeview(mf, columns=met_cols,
                                          show="headings", style="Metrics.Treeview",
                                          height=4, selectmode="none")
        met_widths = {"PID": 42, "Name": 85, "Arrival": 60, "Burst": 52,
                      "Priority": 62, "Start": 52, "Completion": 88,
                      "Turnaround": 88, "Waiting": 72, "Response": 78}
        for col in met_cols:
            self.metrics_tree.heading(col, text=col)
            self.metrics_tree.column(col, width=met_widths[col], anchor="center")

        self.metrics_tree.tag_configure("odd",  background=BG_CARD)
        self.metrics_tree.tag_configure("even", background=BG_PANEL)

        mvsb = ttk.Scrollbar(mf, orient="vertical",
                              command=self.metrics_tree.yview)
        self.metrics_tree.configure(yscrollcommand=mvsb.set)
        self.metrics_tree.pack(side="left", fill="x", expand=True)
        mvsb.pack(side="right", fill="y")

        self.lbl_avg = tk.Label(metrics_frame, text="",
                                 bg=BG_PANEL, fg=WARNING,
                                 font=("Segoe UI", 9, "bold"))
        self.lbl_avg.pack(padx=12, anchor="w", pady=(2, 8))

    # ── TAB 2: GANTT CHART ────────────────────────────────────────────
    def _build_gantt_tab(self):
        self.gantt_header_lbl = tk.Label(
            self.tab_gantt,
            text="GANTT CHART  —  Run a scheduler to visualise",
            bg=BG_DARK, fg=TEXT_MUTED,
            font=("Segoe UI", 13, "bold"))
        self.gantt_header_lbl.pack(padx=14, pady=(14, 8), anchor="w")

        gantt_wrap = tk.Frame(self.tab_gantt, bg=BG_PANEL,
                               highlightbackground=BORDER, highlightthickness=1)
        gantt_wrap.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        inner = tk.Frame(gantt_wrap, bg=BG_PANEL)
        inner.pack(fill="both", expand=True, padx=4, pady=4)

        self.gantt_canvas = tk.Canvas(inner, bg=BG_PANEL, highlightthickness=0)
        h_scroll = ttk.Scrollbar(inner, orient="horizontal",
                                  command=self.gantt_canvas.xview)
        v_scroll = ttk.Scrollbar(inner, orient="vertical",
                                  command=self.gantt_canvas.yview)
        self.gantt_canvas.configure(xscrollcommand=h_scroll.set,
                                     yscrollcommand=v_scroll.set)
        self.gantt_canvas.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")

        self.gantt_canvas.create_text(
            300, 100,
            text="Run a scheduling algorithm to see\nthe multi-row Gantt chart here",
            fill=TEXT_MUTED, font=("Segoe UI", 12), justify="center",
            tags="placeholder")

        # Ready Queue strip inside Gantt tab
        rq_sep = tk.Frame(self.tab_gantt, bg=BORDER, height=1)
        rq_sep.pack(fill="x", padx=14, pady=(0, 4))

        rq_header = tk.Frame(self.tab_gantt, bg=BG_DARK)
        rq_header.pack(fill="x", padx=14)
        tk.Label(rq_header, text="Ready Queue",
                 bg=BG_DARK, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 10, "bold")).pack(side="left")

        self.gantt_queue_frame = tk.Frame(self.tab_gantt, bg=BG_DARK)
        self.gantt_queue_frame.pack(fill="x", padx=14, pady=(4, 10))

    # ── TAB 3: READY QUEUE ────────────────────────────────────────────
    def _build_queue_tab(self):
        tk.Label(self.tab_queue, text="Ready Queue",
                 bg=BG_DARK, fg=TEXT_PRIMARY,
                 font=("Segoe UI", 14, "bold")).pack(padx=14, pady=(14, 8), anchor="w")

        self.queue_container = tk.Frame(self.tab_queue, bg=BG_DARK)
        self.queue_container.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self._draw_queue_pills()

    # ── TAB 4: STATISTICS ─────────────────────────────────────────────
    def _build_stats_tab(self):
        canvas = tk.Canvas(self.tab_stats, bg=BG_DARK, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.tab_stats, orient="vertical",
                                   command=canvas.yview)
        self.stats_inner = tk.Frame(canvas, bg=BG_DARK)

        self.stats_inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.stats_inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _mw(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<MouseWheel>", _mw)
        self.stats_canvas_widget = canvas

        self.stats_placeholder = tk.Label(
            self.stats_inner,
            text=("Run scheduling algorithms to see statistics.\n\n"
                  "Charts will include:\n"
                  "• CPU Utilization Over Time\n"
                  "• Process State Distribution\n"
                  "• Algorithm Comparison (Avg Waiting Time)\n"
                  "• Throughput per Algorithm\n"
                  "• Turnaround Time per Process\n"
                  "• Burst Time vs Waiting Time"),
            bg=BG_DARK, fg=TEXT_MUTED,
            font=("Segoe UI", 12), justify="left")
        self.stats_placeholder.pack(padx=30, pady=40)

    # ──────────────────────────────────────────────────────────────────
    #  EVENT HANDLERS
    # ──────────────────────────────────────────────────────────────────
    def _select_algo(self, name):
        self.algo_var.set(name)
        for n, btn in self.algo_buttons.items():
            btn.config(bg=ACCENT if n == name else BG_CARD,
                       fg=TEXT_WHITE if n == name else TEXT_MUTED)
        if name == "Round Robin":
            self.rr_frame.pack(fill="x", after=self.algo_buttons["MLQ"].master)
        else:
            self.rr_frame.pack_forget()

    def _on_add_process(self):
        PLACEHOLDERS = {"e.g. P7", "e.g. 8", "e.g. 0", "e.g. 2"}

        raw_name     = self.ent_name.get().strip()
        raw_burst    = self.ent_burst.get().strip()
        raw_arrival  = self.ent_arrival.get().strip()
        raw_priority = self.ent_priority.get().strip()

        for field, val in [("Name", raw_name), ("Burst", raw_burst),
                            ("Arrival", raw_arrival), ("Priority", raw_priority)]:
            if not val or val in PLACEHOLDERS:
                messagebox.showerror("Input Error",
                                     f"'{field}' is required.")
                return

        try:
            burst    = int(raw_burst)
            arrival  = int(raw_arrival)
            priority = int(raw_priority)
        except ValueError:
            messagebox.showerror("Input Error",
                                 "Burst, Arrival, and Priority must be integers.")
            return

        if arrival < 0:
            messagebox.showerror("Input Error", "Arrival Time cannot be negative.")
            return
        if burst < 1:
            messagebox.showerror("Input Error", "Burst Time must be ≥ 1.")
            return
        if priority < 1:
            messagebox.showerror("Input Error", "Priority must be ≥ 1.")
            return

        # Auto-assign PID
        pid = self._next_pid
        while any(p["pid"] == pid for p in self.processes):
            pid += 1
        self._next_pid = pid + 1

        ql_raw = self.ql_var.get()
        ql = int(ql_raw[0]) if ql_raw else 2

        pcb = make_pcb(pid, raw_name, arrival, burst, priority, ql)
        self.processes.append(pcb)
        self.created_count += 1

        self._refresh_all()
        self._clear_form()
        self.lbl_sim_status.config(text=f"● P{pid} ({raw_name}) added", fg=SUCCESS)

    def _on_run_scheduler(self):
        if not self.processes:
            messagebox.showwarning("No Processes",
                                   "Add at least one process before running.")
            return

        algo = self.algo_var.get()
        self.current_algo = algo
        self.sim_running = True
        self.sim_paused = False

        self.lbl_status_badge.config(text=" Simulator Running ", bg="#166534", fg=COL_RUNNING)
        self.lbl_algo_badge.config(text=f" Algorithm: {algo} ", bg=ACCENT, fg=TEXT_WHITE)
        self.lbl_sim_status.config(text=f"● Running {algo}…", fg=WARNING)
        self.update_idletasks()

        if algo == "FCFS":
            result_procs, gantt = run_fcfs(self.processes)
        elif algo == "SJF":
            result_procs, gantt = run_sjf(self.processes)
        elif algo == "SRTF":
            result_procs, gantt = run_srtf(self.processes)
        elif algo == "Priority":
            result_procs, gantt = run_priority(self.processes)
        elif algo == "MLQ":
            result_procs, gantt = run_mlq(self.processes)
        elif algo == "Round Robin":
            try:
                q = int(self.rr_quantum.get())
                if q < 1:
                    raise ValueError
            except (ValueError, tk.TclError):
                messagebox.showerror("Input Error",
                                     "Time Quantum must be a positive integer ≥ 1.")
                self.lbl_sim_status.config(text="● Error", fg=ERROR)
                return
            result_procs, gantt = run_rr(self.processes, quantum=q)
        else:
            return

        self.result_procs = result_procs
        self.result_gantt = gantt

        # Save for comparison
        self.algo_history[algo] = copy.deepcopy(result_procs)

        # Merge statuses
        pid_map = {p["pid"]: p for p in result_procs}
        for p in self.processes:
            if p["pid"] in pid_map:
                p["status"]    = pid_map[p["pid"]]["status"]
                p["remaining"] = pid_map[p["pid"]].get("remaining", 0)

        self._refresh_all()
        self._draw_gantt(gantt)
        self._populate_metrics(result_procs)
        self._draw_statistics()

        self.sim_running = False
        self.lbl_status_badge.config(text=" Simulation Complete ", bg="#166534", fg=COL_RUNNING)
        self.lbl_sim_status.config(text=f"● {algo} complete ✓", fg=SUCCESS)

    def _on_pause(self):
        if not self.sim_running:
            return
        self.sim_paused = not self.sim_paused
        if self.sim_paused:
            self.btn_pause.config(text="▶  Resume", bg=WARNING, fg=BG_DARK)
            self.lbl_sim_status.config(text="● Paused", fg=WARNING)
        else:
            self.btn_pause.config(text="⏸  Pause", bg=BG_CARD, fg=TEXT_PRIMARY)
            self.lbl_sim_status.config(text="● Running…", fg=WARNING)

    def _on_reset_all(self):
        if self.processes and not messagebox.askyesno(
                "Confirm Reset",
                "Remove all processes and clear results?"):
            return

        self.processes     = []
        self.result_procs  = []
        self.result_gantt  = []
        self.algo_history  = {}
        self.created_count = 0
        self.current_algo  = "—"
        self.sim_running   = False
        self._next_pid     = 5

        self.lbl_status_badge.config(text=" Simulator Idle ",  bg=BG_CARD,  fg=TEXT_MUTED)
        self.lbl_algo_badge.config(text=" Algorithm: — ",      bg=BG_CARD,  fg=TEXT_MUTED)
        self.lbl_sim_status.config(text="● Reset complete",    fg=TEXT_MUTED)

        self._refresh_all()

        self.gantt_canvas.delete("all")
        self.gantt_header_lbl.config(
            text="GANTT CHART  —  Run a scheduler to visualise")
        self.gantt_canvas.create_text(
            300, 100,
            text="Run a scheduling algorithm to see\nthe multi-row Gantt chart here",
            fill=TEXT_MUTED, font=("Segoe UI", 12), justify="center",
            tags="placeholder")

        for row in self.metrics_tree.get_children():
            self.metrics_tree.delete(row)
        self.lbl_avg.config(text="")

        for w in self.stats_inner.winfo_children():
            w.destroy()
        self.stats_placeholder = tk.Label(
            self.stats_inner,
            text="Run scheduling algorithms to see statistics.",
            bg=BG_DARK, fg=TEXT_MUTED, font=("Segoe UI", 12))
        self.stats_placeholder.pack(padx=30, pady=40)

        # Also reload sample processes
        for pcb in self.SAMPLE_PROCESSES:
            self.processes.append(copy.deepcopy(pcb))
        self._next_pid = 5
        self._refresh_all()

    def _on_stop_all(self):
        for p in self.processes:
            p["status"] = "Terminated"
            p["remaining"] = 0
        self.sim_running = False
        self.lbl_status_badge.config(text=" Simulator Stopped ", bg="#7f1d1d", fg=ERROR)
        self.lbl_sim_status.config(text="● All processes stopped", fg=ERROR)
        self._refresh_all()

    # ──────────────────────────────────────────────────────────────────
    #  REFRESH HELPERS
    # ──────────────────────────────────────────────────────────────────
    def _refresh_all(self):
        self._update_stats_cards()
        self._refresh_process_table()
        self._draw_queue_pills()
        self._draw_gantt_queue_strip()

    def _update_stats_cards(self):
        n = len(self.processes)
        active = sum(1 for p in self.processes if p["status"] != "Terminated")
        done   = sum(1 for p in self.processes if p["status"] == "Terminated")

        self.stat_total_val.config(text=str(n))
        self.stat_total_sub.config(
            text=f"{active} active · {done} done · {self.created_count} new")

        if self.result_procs:
            total_burst = sum(p["burst"] for p in self.result_procs)
            total_time  = max(
                (p["completion"] for p in self.result_procs
                 if p["completion"] is not None), default=1)
            if total_time > 0:
                util = (total_burst / total_time) * 100
                self.stat_cpu_val.config(text=f"{util:.0f}%")
                self.stat_cpu_sub.config(text=f"Avg over {total_time} cycles")

            tats = [p["turnaround"] for p in self.result_procs if p["turnaround"] is not None]
            wts  = [p["waiting"]    for p in self.result_procs if p["waiting"]    is not None]

            if tats:
                avg_tat = sum(tats) / len(tats)
                self.stat_tat_val.config(text=f"{avg_tat:.1f}ms")
                if "FCFS" in self.algo_history and self.current_algo != "FCFS":
                    fcfs_tats = [p["turnaround"] for p in self.algo_history["FCFS"]
                                 if p["turnaround"] is not None]
                    if fcfs_tats:
                        fcfs_avg = sum(fcfs_tats) / len(fcfs_tats)
                        diff = avg_tat - fcfs_avg
                        sign = "+" if diff >= 0 else ""
                        col = ERROR if diff > 0 else SUCCESS
                        self.stat_tat_sub.config(
                            text=f"{sign}{diff:.1f}ms vs FCFS", fg=col)
                    else:
                        self.stat_tat_sub.config(text=self.current_algo, fg=TEXT_MUTED)
                else:
                    self.stat_tat_sub.config(text=self.current_algo, fg=TEXT_MUTED)

            if wts:
                avg_wt = sum(wts) / len(wts)
                self.stat_wait_val.config(text=f"{avg_wt:.1f}ms")
                if "FCFS" in self.algo_history and self.current_algo != "FCFS":
                    fcfs_wts = [p["waiting"] for p in self.algo_history["FCFS"]
                                if p["waiting"] is not None]
                    if fcfs_wts:
                        fcfs_avg = sum(fcfs_wts) / len(fcfs_wts)
                        diff = avg_wt - fcfs_avg
                        sign = "+" if diff >= 0 else ""
                        col  = ERROR if diff > 0 else SUCCESS
                        self.stat_wait_sub.config(
                            text=f"{sign}{diff:.1f}ms vs FCFS", fg=col)
                    else:
                        self.stat_wait_sub.config(text=self.current_algo, fg=TEXT_MUTED)
                else:
                    self.stat_wait_sub.config(text=self.current_algo, fg=TEXT_MUTED)
        else:
            for key in ("cpu", "tat", "wait"):
                getattr(self, f"stat_{key}_val").config(text="—")
                getattr(self, f"stat_{key}_sub").config(text="", fg=TEXT_MUTED)

    def _refresh_process_table(self):
        for item in self.proc_tree.get_children():
            self.proc_tree.delete(item)

        flt = self.filter_var.get()
        for p in sorted(self.processes, key=lambda x: x["pid"]):
            state = p["status"]
            if flt != "All States" and state != flt:
                continue
            tag  = state.lower()
            rem  = p.get("remaining", p["burst"])
            self.proc_tree.insert(
                "", "end",
                values=(f'{p["pid"]:03d}', p["name"], state,
                        f'{p["burst"]}ms', f'{rem}ms',
                        f'{p["arrival"]}ms', p["priority"],
                        f'Q{p.get("queue_level", 1)}'),
                tags=(tag,))

    def _draw_queue_pills(self):
        """Draw pill-style cards for processes in Ready state in Ready Queue tab."""
        for w in self.queue_container.winfo_children():
            w.destroy()

        ready = [p for p in self.processes if p["status"] == "Ready"]

        if not ready:
            tk.Label(self.queue_container,
                     text="No processes in Ready Queue",
                     bg=BG_DARK, fg=TEXT_MUTED,
                     font=("Segoe UI", 12)).pack(pady=50)
            return

        tk.Label(self.queue_container,
                 text=f"{len(ready)} process{'es' if len(ready) != 1 else ''} waiting",
                 bg=BG_DARK, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 10))

        row_frame = tk.Frame(self.queue_container, bg=BG_DARK)
        row_frame.pack(fill="x", anchor="w")

        for p in sorted(ready, key=lambda x: x["pid"]):
            rem = p.get("remaining", p["burst"])
            pill = tk.Frame(row_frame, bg=ACCENT_DIM, padx=14, pady=8)
            pill.pack(side="left", padx=(0, 8), pady=4)
            tk.Label(pill, text=f"P{p['pid']} · {p['name']} · {rem}ms",
                     bg=ACCENT_DIM, fg=TEXT_WHITE,
                     font=("Segoe UI", 10, "bold")).pack()

    def _draw_gantt_queue_strip(self):
        """Draw ready queue pills at the bottom of the Gantt tab."""
        for w in self.gantt_queue_frame.winfo_children():
            w.destroy()

        ready = [p for p in self.processes if p["status"] == "Ready"]
        if not ready:
            tk.Label(self.gantt_queue_frame,
                     text="—  No processes waiting",
                     bg=BG_DARK, fg=TEXT_MUTED,
                     font=("Segoe UI", 9)).pack(side="left", pady=4)
            return

        for p in sorted(ready, key=lambda x: x["pid"]):
            rem = p.get("remaining", p["burst"])
            pill = tk.Frame(self.gantt_queue_frame, bg=ACCENT_DIM, padx=10, pady=5)
            pill.pack(side="left", padx=(0, 6), pady=4)
            tk.Label(pill, text=f"P{p['pid']} · {rem}ms",
                     bg=ACCENT_DIM, fg=TEXT_WHITE,
                     font=("Segoe UI", 9, "bold")).pack()

    def _draw_gantt(self, gantt):
        """Draw multi-row Gantt chart (one lane per process)."""
        self.gantt_canvas.delete("all")
        if not gantt:
            return

        algo = self.algo_var.get()
        q_text = ""
        if algo == "Round Robin":
            try:
                q_text = f" (quantum = {self.rr_quantum.get()}ms)"
            except Exception:
                pass
        self.gantt_header_lbl.config(
            text=f"GANTT CHART  —  {algo} Execution Timeline (ms){q_text}")

        # Unique PIDs (excluding IDLE)
        pids = sorted({seg["pid"] for seg in gantt if seg["pid"] != -1})
        if not pids:
            return

        total_time = gantt[-1]["end"]

        LANE_H   = 38
        LANE_GAP = 14
        LABEL_W  = 55
        PAD_L    = LABEL_W + 10
        PAD_T    = 20
        UNIT_W   = max(30, min(60, 900 // max(total_time, 1)))

        num_lanes = len(pids)
        canvas_h  = PAD_T + num_lanes * (LANE_H + LANE_GAP) + 55
        canvas_w  = PAD_L + total_time * UNIT_W + 80

        self.gantt_canvas.configure(scrollregion=(0, 0, canvas_w, canvas_h))

        color_map   = {pid: GANTT_COLORS[i % len(GANTT_COLORS)]
                       for i, pid in enumerate(pids)}
        pid_to_row  = {pid: i for i, pid in enumerate(pids)}

        # Draw background lane tracks
        for pid, row in pid_to_row.items():
            y1 = PAD_T + row * (LANE_H + LANE_GAP)
            y2 = y1 + LANE_H
            self.gantt_canvas.create_rectangle(
                PAD_L, y1, PAD_L + total_time * UNIT_W, y2,
                fill=BG_CARD, outline=BORDER, width=1)

        # Draw segments
        for seg in gantt:
            if seg["pid"] == -1:
                # IDLE stripe
                y_top = PAD_T
                y_bot = PAD_T + num_lanes * (LANE_H + LANE_GAP) - LANE_GAP
                x1 = PAD_L + seg["start"] * UNIT_W
                x2 = PAD_L + seg["end"] * UNIT_W
                self.gantt_canvas.create_rectangle(
                    x1, y_top, x2, y_bot,
                    fill=BG_CARD_ALT, outline="", stipple="gray25")
                if x2 - x1 > 20:
                    self.gantt_canvas.create_text(
                        (x1 + x2) / 2, (y_top + y_bot) / 2,
                        text="IDLE", fill=TEXT_MUTED,
                        font=("Segoe UI", 8), anchor="center")
                continue

            row = pid_to_row[seg["pid"]]
            y1  = PAD_T + row * (LANE_H + LANE_GAP)
            y2  = y1 + LANE_H
            x1  = PAD_L + seg["start"] * UNIT_W
            x2  = PAD_L + seg["end"] * UNIT_W
            fill = color_map[seg["pid"]]

            self.gantt_canvas.create_rectangle(
                x1 + 1, y1 + 1, x2 - 1, y2 - 1,
                fill=fill, outline="", width=0)

            bar_w = x2 - x1
            if bar_w > 30:
                label = f"{seg['start']}–{seg['end']}"
                self.gantt_canvas.create_text(
                    (x1 + x2) / 2, (y1 + y2) / 2,
                    text=label, fill=TEXT_WHITE,
                    font=("Segoe UI", 8, "bold"))

        # Process labels
        for pid, row in pid_to_row.items():
            y = PAD_T + row * (LANE_H + LANE_GAP) + LANE_H / 2
            proc = next((p for p in self.processes if p["pid"] == pid), None)
            label = f"P{pid}" if not proc else f"P{pid}"
            self.gantt_canvas.create_text(
                LABEL_W - 5, y,
                text=label,
                fill=color_map[pid],
                font=("Segoe UI", 10, "bold"), anchor="e")

        # Time axis
        axis_y = PAD_T + num_lanes * (LANE_H + LANE_GAP) + 8
        step = max(1, total_time // 14)
        for t in range(0, total_time + 1, step):
            x = PAD_L + t * UNIT_W
            self.gantt_canvas.create_line(x, PAD_T - 4, x, axis_y - 4,
                                           fill=BORDER, width=1)
            self.gantt_canvas.create_text(
                x, axis_y, text=str(t), fill=TEXT_MUTED,
                font=("Segoe UI", 8))

        # Final time label
        final_x = PAD_L + total_time * UNIT_W
        self.gantt_canvas.create_text(
            final_x, axis_y + 14,
            text=f"{total_time}ms", fill=TEXT_SECONDARY,
            font=("Segoe UI", 8, "bold"))

    def _populate_metrics(self, procs):
        for row in self.metrics_tree.get_children():
            self.metrics_tree.delete(row)

        def fmt(val):
            return val if val is not None else "—"

        n = len(procs)
        sum_tat = sum_wt = sum_rt = 0

        for i, p in enumerate(procs):
            tag = "odd" if i % 2 == 0 else "even"
            self.metrics_tree.insert(
                "", "end", tags=(tag,),
                values=(fmt(p["pid"]), p.get("name", "—"),
                        fmt(p["arrival"]), fmt(p["burst"]),
                        fmt(p["priority"]), fmt(p["start_time"]),
                        fmt(p["completion"]), fmt(p["turnaround"]),
                        fmt(p["waiting"]), fmt(p["response"])))
            if p["turnaround"] is not None: sum_tat += p["turnaround"]
            if p["waiting"]    is not None: sum_wt  += p["waiting"]
            if p["response"]   is not None: sum_rt  += p["response"]

        if n:
            self.lbl_avg.config(
                text=(f"Averages  →  "
                      f"Turnaround: {sum_tat/n:.2f}   "
                      f"Waiting: {sum_wt/n:.2f}   "
                      f"Response: {sum_rt/n:.2f}"))

    # ──────────────────────────────────────────────────────────────────
    #  STATISTICS CHARTS (matplotlib)
    # ──────────────────────────────────────────────────────────────────
    def _draw_statistics(self):
        for w in self.stats_inner.winfo_children():
            w.destroy()
        if not self.result_procs:
            return

        # Row 1: CPU utilization over time + State distribution
        row1 = tk.Frame(self.stats_inner, bg=BG_DARK)
        row1.pack(fill="x", padx=8, pady=(10, 4))
        row1.columnconfigure(0, weight=2)
        row1.columnconfigure(1, weight=1)
        self._chart_cpu_utilization(row1, 0)
        self._chart_state_distribution(row1, 1)

        # Row 2: Algo comparison + Throughput per algo
        row2 = tk.Frame(self.stats_inner, bg=BG_DARK)
        row2.pack(fill="x", padx=8, pady=(4, 4))
        row2.columnconfigure(0, weight=1)
        row2.columnconfigure(1, weight=1)
        self._chart_algo_comparison(row2, 0)
        self._chart_throughput(row2, 1)

        # Row 3: Turnaround per process + Burst vs Waiting
        row3 = tk.Frame(self.stats_inner, bg=BG_DARK)
        row3.pack(fill="x", padx=8, pady=(4, 10))
        row3.columnconfigure(0, weight=1)
        row3.columnconfigure(1, weight=1)
        self._chart_turnaround_per_process(row3, 0)
        self._chart_burst_vs_waiting(row3, 1)

    def _make_chart_card(self, parent, column, title, rowspan=1, figsize=(4.5, 3)):
        card = tk.Frame(parent, bg=BG_PANEL,
                         highlightbackground=BORDER, highlightthickness=1)
        card.grid(row=0, column=column, sticky="nsew",
                  padx=(0 if column == 0 else 4, 4 if column == 0 else 0),
                  rowspan=rowspan)

        tk.Label(card, text=title, bg=BG_PANEL, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 9, "bold")).pack(padx=12, pady=(10, 0), anchor="w")

        fig = Figure(figsize=figsize, dpi=96, facecolor=BG_PANEL)
        ax  = fig.add_subplot(111)
        ax.set_facecolor(BG_CARD)
        ax.tick_params(colors=TEXT_MUTED, labelsize=8)
        for sp in ['bottom', 'left']:
            ax.spines[sp].set_color(BORDER)
        for sp in ['top', 'right']:
            ax.spines[sp].set_visible(False)
        return card, fig, ax

    def _embed_chart(self, card, fig):
        cv = FigureCanvasTkAgg(fig, master=card)
        cv.draw()
        cv.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)

    def _chart_cpu_utilization(self, parent, column):
        """Line chart – CPU utilisation sampled over time from Gantt."""
        card, fig, ax = self._make_chart_card(
            parent, column, "CPU UTILIZATION OVER TIME", figsize=(6, 3))

        gantt = self.result_gantt
        if not gantt:
            self._embed_chart(card, fig)
            return

        total_time = gantt[-1]["end"]
        # Build busy[t] = True if any process runs at time t
        busy = [False] * (total_time + 1)
        for seg in gantt:
            if seg["pid"] != -1:
                for t in range(seg["start"], seg["end"]):
                    if t < len(busy):
                        busy[t] = True

        # Rolling window utilisation
        WIN = max(2, total_time // 10)
        times = list(range(total_time + 1))
        util  = []
        for t in times:
            lo = max(0, t - WIN)
            window = busy[lo:t + 1]
            util.append(sum(window) / max(len(window), 1) * 100)

        ax.fill_between(times, util, alpha=0.25, color=ACCENT)
        ax.plot(times, util, color=ACCENT, linewidth=2)
        ax.set_ylim(0, 110)
        ax.set_ylabel("CPU %", color=TEXT_MUTED, fontsize=8)
        ax.set_xlabel("Time (ms)", color=TEXT_MUTED, fontsize=8)
        ax.axhline(y=sum(busy) / max(total_time, 1) * 100,
                   color=COL_RUNNING, linestyle="--", linewidth=1, alpha=0.6)
        fig.tight_layout()
        self._embed_chart(card, fig)

    def _chart_state_distribution(self, parent, column):
        """Donut chart – process state distribution."""
        card, fig, ax = self._make_chart_card(
            parent, column, "PROCESS STATE DISTRIBUTION")

        states = {}
        for p in self.processes:
            states[p["status"]] = states.get(p["status"], 0) + 1

        state_colors = {
            "Running": COL_RUNNING, "Ready": COL_READY,
            "Waiting": COL_WAITING, "Terminated": COL_TERMINATED,
            "New": COL_NEW,
        }

        labels = list(states.keys())
        sizes  = list(states.values())
        colors = [state_colors.get(s, TEXT_MUTED) for s in labels]

        wedges, _, autotexts = ax.pie(
            sizes, labels=None, colors=colors,
            autopct='%1.0f%%', startangle=90, pctdistance=0.75,
            wedgeprops=dict(width=0.42, edgecolor=BG_PANEL))

        for t in autotexts:
            t.set_color(TEXT_WHITE)
            t.set_fontsize(8)

        leg_labels = [f"{s} — {states[s]}" for s in labels]
        legend = ax.legend(wedges, leg_labels, loc="center left",
                           bbox_to_anchor=(1, 0.5), fontsize=8, frameon=False)
        for t in legend.get_texts():
            t.set_color(TEXT_PRIMARY)

        fig.tight_layout()
        self._embed_chart(card, fig)

    def _chart_algo_comparison(self, parent, column):
        """Horizontal bar – avg waiting time per algorithm."""
        card, fig, ax = self._make_chart_card(
            parent, column, "ALGORITHM COMPARISON — AVG WAITING TIME (MS)")

        if not self.algo_history:
            ax.text(0.5, 0.5, "Run multiple algorithms\nto compare",
                    transform=ax.transAxes, ha='center', va='center',
                    color=TEXT_MUTED, fontsize=10)
            self._embed_chart(card, fig)
            return

        algo_names, avg_wts, colors = [], [], []
        for name, procs in self.algo_history.items():
            wts = [p["waiting"] for p in procs if p["waiting"] is not None]
            if wts:
                algo_names.append(name)
                avg_wts.append(sum(wts) / len(wts))
                colors.append(ALGO_COLORS.get(name, ACCENT))

        if not algo_names:
            self._embed_chart(card, fig)
            return

        y_pos = range(len(algo_names))
        bars  = ax.barh(y_pos, avg_wts, color=colors, height=0.5, edgecolor="none")
        ax.set_yticks(y_pos)
        ax.set_yticklabels(algo_names, color=TEXT_PRIMARY, fontsize=9)
        ax.invert_yaxis()
        for bar, val in zip(bars, avg_wts):
            ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                    f'{val:.1f}ms', va='center', color=TEXT_PRIMARY, fontsize=8)
        fig.tight_layout()
        self._embed_chart(card, fig)

    def _chart_throughput(self, parent, column):
        """Bar chart – throughput (processes/unit time) per algorithm."""
        card, fig, ax = self._make_chart_card(
            parent, column, "THROUGHPUT PER ALGORITHM (PROC/MS)")

        if not self.algo_history:
            ax.text(0.5, 0.5, "Run algorithms\nto see throughput",
                    transform=ax.transAxes, ha='center', va='center',
                    color=TEXT_MUTED, fontsize=10)
            self._embed_chart(card, fig)
            return

        names, throughputs, colors = [], [], []
        for name, procs in self.algo_history.items():
            completions = [p["completion"] for p in procs if p["completion"] is not None]
            if completions:
                total_t = max(completions)
                thru = len(procs) / max(total_t, 1)
                names.append(name)
                throughputs.append(thru)
                colors.append(ALGO_COLORS.get(name, ACCENT))

        x = range(len(names))
        bars = ax.bar(x, throughputs, color=colors, edgecolor="none", width=0.5)
        ax.set_xticks(x)
        ax.set_xticklabels(names, color=TEXT_PRIMARY, fontsize=8,
                            rotation=20, ha="right")
        ax.set_ylabel("procs/ms", color=TEXT_MUTED, fontsize=8)
        for bar, val in zip(bars, throughputs):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.005,
                    f'{val:.2f}', ha='center', color=TEXT_PRIMARY, fontsize=8)
        fig.tight_layout()
        self._embed_chart(card, fig)

    def _chart_turnaround_per_process(self, parent, column):
        """Grouped bar – turnaround & waiting per process."""
        card, fig, ax = self._make_chart_card(
            parent, column, "TURNAROUND TIME PER PROCESS")

        procs = self.result_procs
        if not procs:
            self._embed_chart(card, fig)
            return

        labels = [f"P{p['pid']}" for p in procs]
        tats   = [p["turnaround"] if p["turnaround"] is not None else 0 for p in procs]
        wts    = [p["waiting"]    if p["waiting"]    is not None else 0 for p in procs]

        x = range(len(labels))
        w = 0.35
        ax.bar([i - w/2 for i in x], tats, w, label="Turnaround",
               color=ACCENT, edgecolor="none")
        ax.bar([i + w/2 for i in x], wts, w, label="Waiting",
               color=COL_READY, edgecolor="none")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, color=TEXT_PRIMARY, fontsize=9)
        ax.set_ylabel("Time (ms)", color=TEXT_MUTED, fontsize=8)

        legend = ax.legend(fontsize=8, frameon=False)
        for t in legend.get_texts():
            t.set_color(TEXT_PRIMARY)
        fig.tight_layout()
        self._embed_chart(card, fig)

    def _chart_burst_vs_waiting(self, parent, column):
        """Scatter – burst time vs waiting time per process."""
        card, fig, ax = self._make_chart_card(
            parent, column, "BURST TIME VS WAITING TIME")

        procs = self.result_procs
        if not procs:
            self._embed_chart(card, fig)
            return

        bursts = [p["burst"] for p in procs]
        waits  = [p["waiting"] if p["waiting"] is not None else 0 for p in procs]
        sc_c   = [GANTT_COLORS[i % len(GANTT_COLORS)] for i in range(len(procs))]

        ax.scatter(bursts, waits, c=sc_c, s=80, zorder=5, edgecolors=BG_DARK)
        for i, p in enumerate(procs):
            ax.annotate(f'P{p["pid"]}',
                        (bursts[i], waits[i]),
                        textcoords="offset points",
                        xytext=(8, 4), color=TEXT_PRIMARY, fontsize=8)

        ax.set_xlabel("Burst time (ms)", color=TEXT_MUTED, fontsize=8)
        ax.set_ylabel("Waiting time (ms)", color=TEXT_MUTED, fontsize=8)
        fig.tight_layout()
        self._embed_chart(card, fig)

    # ──────────────────────────────────────────────────────────────────
    #  FORM HELPERS
    # ──────────────────────────────────────────────────────────────────
    def _clear_form(self):
        placeholders = [
            (self.ent_name,     "e.g. P7"),
            (self.ent_burst,    "e.g. 8"),
            (self.ent_arrival,  "e.g. 0"),
            (self.ent_priority, "e.g. 2"),
        ]
        for ent, ph in placeholders:
            ent.delete(0, "end")
            ent.insert(0, ph)
            ent.config(fg=TEXT_MUTED)


# ─────────────────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = ProcessManagerApp()
    app.mainloop()
