"""
=============================================================================
  INTERACTIVE OPERATING SYSTEM PROCESS MANAGER WITH LIVE SCHEDULING VIZ
=============================================================================
  Author : OS Process Manager
  Version: 1.0
  Desc   : A fully interactive terminal-based OS Process Manager that
           simulates CPU scheduling with live Gantt chart visualization,
           process lifecycle management, and performance metric analysis.

  Scheduling Algorithms Supported:
    1. FCFS  - First Come First Served
    2. SJF   - Shortest Job First (Non-Preemptive)
    3. PS    - Priority Scheduling (Non-Preemptive, lower number = higher priority)
    4. RR    - Round Robin (with configurable time quantum)

  Libraries Required:
    pip install rich colorama
=============================================================================
"""

import time
import copy
import sys
import io
from collections import deque
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# Force UTF-8 output on Windows so box-drawing / emoji chars render correctly
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Third-party imports ─────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.progress import Progress, BarColumn, TextColumn
    from rich.layout import Layout
    from rich.live import Live
    from rich.columns import Columns
    from rich import box
    from rich.rule import Rule
    from rich.align import Align
    from rich.style import Style
    from rich.padding import Padding
    from rich.markup import escape
except ImportError:
    print("Installing 'rich' …")
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "rich"])
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.progress import Progress, BarColumn, TextColumn
    from rich.layout import Layout
    from rich.live import Live
    from rich.columns import Columns
    from rich import box
    from rich.rule import Rule
    from rich.align import Align
    from rich.style import Style
    from rich.padding import Padding
    from rich.markup import escape

try:
    import colorama
    colorama.init(autoreset=True)
    from colorama import Fore, Back, Style as CStyle
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "colorama"])
    import colorama
    colorama.init(autoreset=True)
    from colorama import Fore, Back, Style as CStyle

# ── Global Console ───────────────────────────────────────────────────────────
console = Console(force_terminal=True, legacy_windows=False)

# ═══════════════════════════════════════════════════════════════════════════
#  DATA MODEL
# ═══════════════════════════════════════════════════════════════════════════

# Process states matching real OS lifecycle
STATES = ["NEW", "READY", "RUNNING", "WAITING", "TERMINATED"]

# Rich colour per state for Gantt chart and tables
STATE_COLORS = {
    "NEW":        "bold white",
    "READY":      "bold cyan",
    "RUNNING":    "bold green",
    "WAITING":    "bold yellow",
    "TERMINATED": "bold red",
    "IDLE":       "bold bright_black",
}

# Background colours used in the Gantt bar (colorama)
GANTT_BG = [
    Back.BLUE, Back.GREEN, Back.MAGENTA, Back.CYAN,
    Back.RED, Back.YELLOW, Back.WHITE, Back.LIGHTBLUE_EX,
]

@dataclass
class Process:
    """Represents a single OS process with all scheduling metadata."""
    pid: int
    name: str
    arrival_time: int
    burst_time: int
    priority: int                        # lower number = higher priority
    state: str = "NEW"
    remaining_time: int = 0             # decremented during RR/preemptive
    start_time: Optional[int] = None    # first time it got the CPU
    completion_time: Optional[int] = None
    waiting_time: int = 0
    turnaround_time: int = 0
    response_time: int = 0
    io_events: List[int] = field(default_factory=list)   # future: I/O waits

    def __post_init__(self):
        self.remaining_time = self.burst_time

    # ── Derived metric helpers ────────────────────────────────────────────
    def calc_metrics(self):
        """Compute TAT, WT, RT once process is terminated."""
        if self.completion_time is not None and self.start_time is not None:
            self.turnaround_time = self.completion_time - self.arrival_time
            self.waiting_time    = self.turnaround_time - self.burst_time
            self.response_time   = self.start_time - self.arrival_time
        # Clamp negatives (edge-case guard)
        self.waiting_time  = max(0, self.waiting_time)
        self.response_time = max(0, self.response_time)

    # ── String representation ─────────────────────────────────────────────
    def __repr__(self):
        return (f"Process(PID={self.pid}, name={self.name}, "
                f"arrival={self.arrival_time}, burst={self.burst_time}, "
                f"priority={self.priority}, state={self.state})")

# ── Gantt segment: records which process ran during [start, end) ─────────
@dataclass
class GanttSegment:
    pid: int           # -1 = CPU idle
    name: str
    start: int
    end: int
    color_index: int   # index into GANTT_BG list


# ═══════════════════════════════════════════════════════════════════════════
#  READY QUEUE
# ═══════════════════════════════════════════════════════════════════════════

class ReadyQueue:
    """
    Manages the pool of processes that are ready to run.
    Supports FIFO, priority-sorted, and burst-time-sorted orderings.
    """
    def __init__(self):
        self._queue: deque = deque()

    def enqueue(self, process: Process):
        """Add a process to the tail of the queue and mark it READY."""
        process.state = "READY"
        self._queue.append(process)

    def dequeue_fcfs(self) -> Optional[Process]:
        """Remove and return the process at the head (FIFO order)."""
        return self._queue.popleft() if self._queue else None

    def dequeue_sjf(self) -> Optional[Process]:
        """Remove and return the process with the shortest burst time."""
        if not self._queue:
            return None
        proc = min(self._queue, key=lambda p: p.burst_time)
        self._queue.remove(proc)
        return proc

    def dequeue_priority(self) -> Optional[Process]:
        """Remove and return the process with the highest priority (lowest number)."""
        if not self._queue:
            return None
        proc = min(self._queue, key=lambda p: p.priority)
        self._queue.remove(proc)
        return proc

    def dequeue_rr(self) -> Optional[Process]:
        """Round Robin simply takes from the front."""
        return self._queue.popleft() if self._queue else None

    def re_enqueue_front(self, process: Process):
        """Return a process to the front (used in Round Robin)."""
        process.state = "READY"
        self._queue.appendleft(process)

    def peek_all(self) -> List[Process]:
        """Return a snapshot of the current queue without modifying it."""
        return list(self._queue)

    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def size(self) -> int:
        return len(self._queue)

    def __len__(self):
        return len(self._queue)


# ═══════════════════════════════════════════════════════════════════════════
#  SCHEDULER ALGORITHMS
# ═══════════════════════════════════════════════════════════════════════════

class Scheduler:
    """
    Contains all four scheduling algorithm implementations.
    Each method accepts a list of Process objects, runs the full
    simulation, and returns:
      - The modified (with metrics) process list
      - The Gantt chart segments list
    """

    # ── FCFS ──────────────────────────────────────────────────────────────
    @staticmethod
    def fcfs(processes: List[Process]) -> Tuple[List[Process], List[GanttSegment]]:
        """
        First Come, First Served (non-preemptive).
        Processes are served in order of arrival time only.
        """
        procs   = sorted(copy.deepcopy(processes), key=lambda p: p.arrival_time)
        gantt   = []
        clock   = 0
        color_i = 0

        for proc in procs:
            # Advance clock if CPU is idle (no process has arrived yet)
            if clock < proc.arrival_time:
                gantt.append(GanttSegment(-1, "IDLE", clock, proc.arrival_time, -1))
                clock = proc.arrival_time

            proc.state      = "RUNNING"
            proc.start_time = proc.start_time or clock   # record first dispatch

            gantt.append(GanttSegment(proc.pid, proc.name, clock,
                                      clock + proc.burst_time, color_i % len(GANTT_BG)))
            clock             += proc.burst_time
            proc.completion_time = clock
            proc.state           = "TERMINATED"
            proc.calc_metrics()
            color_i += 1

        return procs, gantt

    # ── SJF ───────────────────────────────────────────────────────────────
    @staticmethod
    def sjf(processes: List[Process]) -> Tuple[List[Process], List[GanttSegment]]:
        """
        Shortest Job First (non-preemptive).
        Among processes that have arrived, pick the one with the
        smallest TOTAL burst time.
        """
        procs    = copy.deepcopy(processes)
        color_map = {p.pid: i % len(GANTT_BG) for i, p in enumerate(procs)}
        gantt    = []
        clock    = 0
        done     = []
        remaining = list(procs)  # processes not yet finished

        while remaining:
            # Gather all processes that have arrived by 'clock'
            available = [p for p in remaining if p.arrival_time <= clock]

            if not available:
                # No process ready yet – advance time to next arrival
                next_arr = min(p.arrival_time for p in remaining)
                gantt.append(GanttSegment(-1, "IDLE", clock, next_arr, -1))
                clock = next_arr
                continue

            # Pick shortest burst time
            proc = min(available, key=lambda p: p.burst_time)
            remaining.remove(proc)

            proc.state      = "RUNNING"
            proc.start_time = clock

            gantt.append(GanttSegment(proc.pid, proc.name, clock,
                                      clock + proc.burst_time, color_map[proc.pid]))
            clock               += proc.burst_time
            proc.completion_time = clock
            proc.state           = "TERMINATED"
            proc.calc_metrics()
            done.append(proc)

        # Re-sort by PID for consistent display
        done.sort(key=lambda p: p.pid)
        return done, gantt

    # ── Priority Scheduling ───────────────────────────────────────────────
    @staticmethod
    def priority(processes: List[Process]) -> Tuple[List[Process], List[GanttSegment]]:
        """
        Non-preemptive Priority Scheduling.
        Lower priority number = higher urgency (like Linux nice values).
        Among arrived processes, select the one with the smallest priority number.
        FCFS is used as a tie-breaker.
        """
        procs     = copy.deepcopy(processes)
        color_map = {p.pid: i % len(GANTT_BG) for i, p in enumerate(procs)}
        gantt     = []
        clock     = 0
        done      = []
        remaining = list(procs)

        while remaining:
            available = [p for p in remaining if p.arrival_time <= clock]

            if not available:
                next_arr = min(p.arrival_time for p in remaining)
                gantt.append(GanttSegment(-1, "IDLE", clock, next_arr, -1))
                clock = next_arr
                continue

            # Pick highest priority (lowest number), break ties by arrival
            proc = min(available, key=lambda p: (p.priority, p.arrival_time))
            remaining.remove(proc)

            proc.state      = "RUNNING"
            proc.start_time = clock

            gantt.append(GanttSegment(proc.pid, proc.name, clock,
                                      clock + proc.burst_time, color_map[proc.pid]))
            clock               += proc.burst_time
            proc.completion_time = clock
            proc.state           = "TERMINATED"
            proc.calc_metrics()
            done.append(proc)

        done.sort(key=lambda p: p.pid)
        return done, gantt

    # ── Round Robin ───────────────────────────────────────────────────────
    @staticmethod
    def round_robin(processes: List[Process],
                    quantum: int = 2) -> Tuple[List[Process], List[GanttSegment]]:
        """
        Round Robin (preemptive by time slice).
        Each process gets at most 'quantum' time units before being
        preempted and placed at the back of the ready queue.
        """
        procs     = sorted(copy.deepcopy(processes), key=lambda p: p.arrival_time)
        color_map = {p.pid: i % len(GANTT_BG) for i, p in enumerate(procs)}
        gantt     = []
        clock     = 0

        # Set remaining_time for all processes
        for p in procs:
            p.remaining_time = p.burst_time

        done        = []
        queue       = deque()   # ready queue (ordered by arrival)
        not_arrived = list(procs)
        active      = None

        def admit_arrivals(t):
            """Move processes that have arrived by time t into the ready queue."""
            arrived = [p for p in not_arrived if p.arrival_time <= t]
            for p in arrived:
                p.state = "READY"
                queue.append(p)
                not_arrived.remove(p)

        admit_arrivals(clock)

        while queue or not_arrived:
            if not queue:
                # CPU idle: jump to next process arrival
                next_arr = min(p.arrival_time for p in not_arrived)
                gantt.append(GanttSegment(-1, "IDLE", clock, next_arr, -1))
                clock = next_arr
                admit_arrivals(clock)
                continue

            proc = queue.popleft()
            proc.state = "RUNNING"

            if proc.start_time is None:
                proc.start_time = clock   # first time on CPU

            # Determine how long this process runs
            run_time = min(quantum, proc.remaining_time)
            end_time = clock + run_time

            gantt.append(GanttSegment(proc.pid, proc.name,
                                      clock, end_time, color_map[proc.pid]))

            # Advance clock, admit new arrivals during this slice
            for t in range(clock + 1, end_time + 1):
                admit_arrivals(t)

            clock                = end_time
            proc.remaining_time -= run_time

            if proc.remaining_time == 0:
                # Process finished
                proc.completion_time = clock
                proc.state           = "TERMINATED"
                proc.calc_metrics()
                done.append(proc)
            else:
                # Preempted – goes to back of queue
                proc.state = "READY"
                queue.append(proc)

        done.sort(key=lambda p: p.pid)
        return done, gantt


# ═══════════════════════════════════════════════════════════════════════════
#  GANTT CHART RENDERER
# ═══════════════════════════════════════════════════════════════════════════

class GanttRenderer:
    """
    Draws a live, colour-coded Gantt chart in the terminal using colorama
    and a rich Panel wrapper.  The chart shows execution blocks per time unit.
    """

    @staticmethod
    def render(gantt: List[GanttSegment], title: str = "Gantt Chart") -> Panel:
        """
        Build a Rich Panel containing the ASCII Gantt chart,
        with colour blocks and time axis.
        """
        if not gantt:
            return Panel("No data", title=title)

        total_time = gantt[-1].end
        # Max display width characters (one char = 1 time unit)
        MAX_WIDTH  = 70

        # Scale if timeline is too wide
        scale = max(1, (total_time + MAX_WIDTH - 1) // MAX_WIDTH)

        # Build process→color map
        color_map: Dict[int, int] = {}
        for seg in gantt:
            if seg.pid != -1 and seg.pid not in color_map:
                color_map[seg.pid] = seg.color_index

        # ── Line 1: process name labels (top border) ─────────────────────
        top_border    = "┌"
        label_row     = "│"
        bottom_border = "└"

        for seg in gantt:
            seg_len = max(1, (seg.end - seg.start) // scale)
            top_border    += "─" * seg_len + "┬"
            bottom_border += "─" * seg_len + "┴"

            if seg.pid == -1:
                label = "IDLE"
            else:
                label = f"P{seg.pid}"

            # Truncate/pad label to fit segment width
            label = label[:seg_len].center(seg_len)
            label_row += label + "│"

        # Remove trailing separators and close
        top_border    = top_border.rstrip("┬")  + "┐"
        bottom_border = bottom_border.rstrip("┴") + "┘"

        # ── Line 2: time axis ─────────────────────────────────────────────
        time_axis = ""
        pos       = 0
        for seg in gantt:
            seg_len = max(1, (seg.end - seg.start) // scale)
            t_label = str(seg.start * scale)
            time_axis += t_label.ljust(seg_len)
            pos       += seg_len
        time_axis += str(gantt[-1].end)

        # ── Assemble into a Text object with per-segment colours ──────────
        text = Text()
        text.append(top_border + "\n", style="bright_white")
        text.append("│", style="bright_white")

        for seg in gantt:
            seg_len = max(1, (seg.end - seg.start) // scale)
            if seg.pid == -1:
                label = "IDLE"[:seg_len].center(seg_len)
                text.append(label, style="on bright_black bold white")
            else:
                label = f"P{seg.pid}"[:seg_len].center(seg_len)
                # Map colour index to rich style
                rich_colours = [
                    "on blue", "on green", "on magenta", "on cyan",
                    "on red", "on dark_orange", "on purple", "on steel_blue1"
                ]
                bg = rich_colours[seg.color_index % len(rich_colours)]
                text.append(label, style=f"bold white {bg}")
            text.append("│", style="bright_white")

        text.append("\n", style="")
        text.append(bottom_border + "\n", style="bright_white")
        text.append(time_axis, style="dim")

        if scale > 1:
            text.append(f"\n  [dim](scale: 1 char = {scale} time units)[/dim]")

        return Panel(text, title=f"[bold yellow]⏱  {title}[/bold yellow]",
                     border_style="yellow", padding=(0, 1))

    @staticmethod
    def render_live(gantt: List[GanttSegment], title: str,
                    delay: float = 0.08):
        """
        'Live' rendering: progressively reveals each Gantt segment
        one by one so the user can see the schedule building up in real time.
        Uses Rich's Live context to avoid screen flicker.
        """
        revealed: List[GanttSegment] = []

        with Live(console=console, refresh_per_second=20) as live:
            for seg in gantt:
                revealed.append(seg)
                # Compact status line above chart
                if seg.pid == -1:
                    status = Text("⬛ CPU IDLE", style="bold bright_black")
                else:
                    status = Text(f"▶  Running P{seg.pid} ({seg.name})  "
                                  f"[{seg.start} → {seg.end}]",
                                  style="bold green")

                panel = GanttRenderer.render(revealed, title)
                live.update(
                    Padding(
                        Columns([panel,
                                 Panel(status, title="[bold]Status[/bold]",
                                       border_style="green", width=34)]),
                        pad=(0, 0, 0, 2)
                    )
                )
                time.sleep(delay)

        # Final static render after live finishes
        console.print(GanttRenderer.render(gantt, title))


# ═══════════════════════════════════════════════════════════════════════════
#  METRICS TABLE RENDERER
# ═══════════════════════════════════════════════════════════════════════════

class MetricsRenderer:
    """Renders per-process metrics and averages using Rich tables."""

    @staticmethod
    def single_algo(procs: List[Process], algo_name: str) -> Table:
        """Build a metrics table for ONE algorithm's result."""
        table = Table(
            title=f"[bold cyan]{algo_name} — Per-Process Metrics[/bold cyan]",
            box=box.DOUBLE_EDGE,
            border_style="cyan",
            header_style="bold magenta",
            show_lines=True,
        )

        # ── Columns ───────────────────────────────────────────────────────
        table.add_column("PID",            justify="center", style="bold white",  no_wrap=True)
        table.add_column("Name",           justify="left",   style="bold cyan")
        table.add_column("Arrival",        justify="center", style="yellow")
        table.add_column("Burst",          justify="center", style="yellow")
        table.add_column("Priority",       justify="center", style="magenta")
        table.add_column("Start",          justify="center", style="green")
        table.add_column("Completion",     justify="center", style="green")
        table.add_column("Turnaround",     justify="center", style="bold blue")
        table.add_column("Waiting",        justify="center", style="bold red")
        table.add_column("Response",       justify="center", style="bold yellow")

        # ── Rows ──────────────────────────────────────────────────────────
        sum_tat = sum_wt = sum_rt = 0
        for p in procs:
            table.add_row(
                str(p.pid),
                p.name,
                str(p.arrival_time),
                str(p.burst_time),
                str(p.priority),
                str(p.start_time),
                str(p.completion_time),
                str(p.turnaround_time),
                str(p.waiting_time),
                str(p.response_time),
            )
            sum_tat += p.turnaround_time
            sum_wt  += p.waiting_time
            sum_rt  += p.response_time

        n = len(procs)
        # ── Average row ───────────────────────────────────────────────────
        table.add_row(
            "─", "[bold]AVG[/bold]", "─", "─", "─", "─", "─",
            f"[bold blue]{sum_tat/n:.2f}[/bold blue]",
            f"[bold red]{sum_wt/n:.2f}[/bold red]",
            f"[bold yellow]{sum_rt/n:.2f}[/bold yellow]",
        )
        return table

    @staticmethod
    def comparison(results: Dict[str, Tuple[List[Process], List[GanttSegment]]]) -> Table:
        """
        Build a side-by-side comparison table across all four algorithms,
        showing average TAT, WT, and RT for each.
        """
        table = Table(
            title="[bold yellow]📊  Algorithm Comparison (Averages)[/bold yellow]",
            box=box.DOUBLE_EDGE,
            border_style="yellow",
            header_style="bold white",
            show_lines=True,
        )

        table.add_column("Algorithm",         justify="left",   style="bold cyan",   min_width=18)
        table.add_column("Avg Turnaround",    justify="center", style="bold blue",   min_width=16)
        table.add_column("Avg Waiting",       justify="center", style="bold red",    min_width=14)
        table.add_column("Avg Response",      justify="center", style="bold yellow", min_width=14)
        table.add_column("CPU Efficiency %",  justify="center", style="bold green",  min_width=16)

        best_wt = float('inf')
        rows    = []

        for algo, (procs, gantt) in results.items():
            n     = len(procs)
            avg_t = sum(p.turnaround_time for p in procs) / n
            avg_w = sum(p.waiting_time    for p in procs) / n
            avg_r = sum(p.response_time   for p in procs) / n

            # CPU efficiency = (total burst) / (total time) × 100
            total_burst = sum(p.burst_time for p in procs)
            total_time  = gantt[-1].end if gantt else 1
            eff         = (total_burst / total_time) * 100

            rows.append((algo, avg_t, avg_w, avg_r, eff))
            if avg_w < best_wt:
                best_wt = avg_w

        for algo, avg_t, avg_w, avg_r, eff in rows:
            marker = " ★" if avg_w == best_wt else ""
            table.add_row(
                f"{algo}{marker}",
                f"{avg_t:.2f}",
                f"{avg_w:.2f}",
                f"{avg_r:.2f}",
                f"{eff:.1f}%",
            )

        return table


# ═══════════════════════════════════════════════════════════════════════════
#  PROCESS MANAGER (core controller)
# ═══════════════════════════════════════════════════════════════════════════

class ProcessManager:
    """
    The central controller that manages the process pool, interfaces
    with the scheduler, and coordinates all rendering.
    """

    # ── 4 hardcoded sample processes so the app works right away ─────────
    DEFAULT_PROCESSES = [
        Process(pid=1, name="Chrome",   arrival_time=0, burst_time=8,  priority=2),
        Process(pid=2, name="VSCode",   arrival_time=1, burst_time=4,  priority=1),
        Process(pid=3, name="Terminal", arrival_time=2, burst_time=9,  priority=3),
        Process(pid=4, name="Spotify",  arrival_time=3, burst_time=5,  priority=2),
    ]

    def __init__(self):
        # Deep-copy so original defaults are never mutated
        self.processes: List[Process] = copy.deepcopy(self.DEFAULT_PROCESSES)
        self.rr_quantum:  int         = 2
        self._results: Dict           = {}   # cache of algorithm results

    # ── Process management helpers ────────────────────────────────────────

    def add_process(self, pid: int, name: str, arrival: int,
                    burst: int, priority: int):
        """Add a new process to the pool."""
        # PID uniqueness check
        if any(p.pid == pid for p in self.processes):
            console.print(f"[red]✖  PID {pid} already exists.[/red]")
            return
        p = Process(pid=pid, name=name, arrival_time=arrival,
                    burst_time=burst, priority=priority)
        self.processes.append(p)
        console.print(f"[green]✔  Process P{pid} ({name}) added.[/green]")

    def terminate_process(self, pid: int):
        """
        Manually terminate a process — simulates SIGKILL.
        Resources (process entry) are cleaned up from the pool.
        """
        proc = next((p for p in self.processes if p.pid == pid), None)
        if proc is None:
            console.print(f"[red]✖  PID {pid} not found.[/red]")
            return
        proc.state = "TERMINATED"
        self.processes.remove(proc)
        console.print(f"[yellow]⚡ Process P{pid} ({proc.name}) terminated and resources freed.[/yellow]")

    def list_processes(self):
        """Print all current processes in a formatted Rich table."""
        if not self.processes:
            console.print("[dim]No processes in the pool.[/dim]")
            return

        table = Table(
            title="[bold cyan]Process Pool[/bold cyan]",
            box=box.ROUNDED,
            border_style="cyan",
            header_style="bold white",
            show_lines=True,
        )
        table.add_column("PID",      justify="center", style="bold white")
        table.add_column("Name",     justify="left",   style="cyan")
        table.add_column("Arrival",  justify="center", style="yellow")
        table.add_column("Burst",    justify="center", style="yellow")
        table.add_column("Priority", justify="center", style="magenta")
        table.add_column("State",    justify="center")

        for p in sorted(self.processes, key=lambda x: x.pid):
            state_style = STATE_COLORS.get(p.state, "white")
            table.add_row(
                str(p.pid), p.name,
                str(p.arrival_time), str(p.burst_time), str(p.priority),
                Text(p.state, style=state_style),
            )

        console.print(table)

    def modify_process(self, pid: int, field: str, value):
        """Modify a field of an existing process."""
        proc = next((p for p in self.processes if p.pid == pid), None)
        if proc is None:
            console.print(f"[red]✖  PID {pid} not found.[/red]")
            return
        if hasattr(proc, field):
            setattr(proc, field, value)
            if field == "burst_time":
                proc.remaining_time = value
            console.print(f"[green]✔  P{pid}.{field} → {value}[/green]")
        else:
            console.print(f"[red]✖  Unknown field '{field}'.[/red]")

    # ── Scheduling runners ────────────────────────────────────────────────

    def _run_algorithm(self, algo: str,
                       live: bool = True) -> Tuple[List[Process], List[GanttSegment]]:
        """
        Internal helper: dispatch to the correct scheduling function,
        render the live Gantt chart, then display metrics.
        """
        procs = self.processes

        # Run the selected algorithm
        if algo == "FCFS":
            result_procs, gantt = Scheduler.fcfs(procs)
            title = "First Come First Served (FCFS)"
        elif algo == "SJF":
            result_procs, gantt = Scheduler.sjf(procs)
            title = "Shortest Job First (SJF)"
        elif algo == "PS":
            result_procs, gantt = Scheduler.priority(procs)
            title = "Priority Scheduling"
        elif algo == "RR":
            result_procs, gantt = Scheduler.round_robin(procs, self.rr_quantum)
            title = f"Round Robin (Quantum = {self.rr_quantum})"
        else:
            console.print(f"[red]Unknown algorithm: {algo}[/red]")
            return [], []

        console.print(Rule(f"[bold yellow]{title}[/bold yellow]"))

        # ── Live Gantt animation ──────────────────────────────────────────
        if live:
            delay = 0.06 if algo == "RR" else 0.10  # RR has many segments
            GanttRenderer.render_live(gantt, title, delay)
        else:
            console.print(GanttRenderer.render(gantt, title))

        # ── Per-process metrics table ─────────────────────────────────────
        console.print()
        console.print(MetricsRenderer.single_algo(result_procs, title))

        return result_procs, gantt

    def run_fcfs(self):
        p, g = self._run_algorithm("FCFS")
        self._results["FCFS"] = (p, g)

    def run_sjf(self):
        p, g = self._run_algorithm("SJF")
        self._results["SJF"] = (p, g)

    def run_priority(self):
        p, g = self._run_algorithm("PS")
        self._results["PS"] = (p, g)

    def run_rr(self):
        p, g = self._run_algorithm("RR")
        self._results["RR"] = (p, g)

    def run_all_and_compare(self):
        """Run all four algorithms silently, then show a comparison table."""
        console.print(Rule("[bold magenta]Running all algorithms for comparison…[/bold magenta]"))
        algos = ["FCFS", "SJF", "PS", "RR"]
        all_results = {}

        for algo in algos:
            procs = self.processes
            if algo == "FCFS":
                rp, g = Scheduler.fcfs(procs)
            elif algo == "SJF":
                rp, g = Scheduler.sjf(procs)
            elif algo == "PS":
                rp, g = Scheduler.priority(procs)
            else:
                rp, g = Scheduler.round_robin(procs, self.rr_quantum)
            all_results[f"{algo} (Q={self.rr_quantum})" if algo == "RR" else algo] = (rp, g)
            console.print(f"  [green]✔[/green] {algo} complete")

        # Show individual Gantt charts (no live animation for speed)
        for algo_label, (rp, g) in all_results.items():
            console.print(GanttRenderer.render(g, algo_label))

        # Comparison table
        console.print()
        console.print(MetricsRenderer.comparison(all_results))
        self._results = all_results

    def set_quantum(self, q: int):
        """Update the Round Robin time quantum."""
        if q < 1:
            console.print("[red]✖  Quantum must be ≥ 1.[/red]")
            return
        self.rr_quantum = q
        console.print(f"[green]✔  RR Quantum set to {q}.[/green]")

    def reset_to_defaults(self):
        """Restore the four hardcoded sample processes."""
        self.processes = copy.deepcopy(self.DEFAULT_PROCESSES)
        self._results  = {}
        console.print("[green]✔  Process pool reset to default sample processes.[/green]")


# ═══════════════════════════════════════════════════════════════════════════
#  TERMINAL UI
# ═══════════════════════════════════════════════════════════════════════════

class TerminalUI:
    """
    Drives the interactive terminal menu.
    Delegates all business logic to ProcessManager.
    """

    BANNER = r"""
  +------------------------------------------------------------------+
  |   ___  ____    __  __                                           |
  |  / _ \/ ___|  |  \/  | __ _ _ __   __ _  __ _  ___ _ __       |
  | | | | \___ \  | |\/| |/ _` | '_ \ / _` |/ _` |/ _ \ '__|      |
  | | |_| |___) | | |  | | (_| | | | | (_| | (_| |  __/ |         |
  |  \___/|____/  |_|  |_|\__,_|_| |_|\__,_|\__, |\___|_|         |
  |                                           |___/                 |
  |          Interactive Process Manager  v1.0                      |
  +------------------------------------------------------------------+
    """

    def __init__(self):
        self.manager = ProcessManager()

    # ── Input helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _input_int(prompt: str, min_val: int = 0, max_val: int = 9999) -> Optional[int]:
        """Read and validate an integer input from the user."""
        try:
            val = int(input(f"  {prompt}: ").strip())
            if not (min_val <= val <= max_val):
                console.print(f"[red]  ✖  Value must be in [{min_val}, {max_val}].[/red]")
                return None
            return val
        except ValueError:
            console.print("[red]  ✖  Invalid input — integer expected.[/red]")
            return None

    @staticmethod
    def _input_str(prompt: str) -> str:
        return input(f"  {prompt}: ").strip()

    # ── Main banner ───────────────────────────────────────────────────────

    def print_banner(self):
        console.print(Text(self.BANNER, style="bold blue"))
        console.print(Align.center(
            Text("Interactive OS Process Manager · Scheduling Visualiser",
                 style="italic cyan")
        ))
        console.print()

    # ── Menu renderer ─────────────────────────────────────────────────────
    def print_menu(self):
        menu = Table(box=box.MINIMAL_HEAVY_HEAD, border_style="blue",
                     show_header=False, min_width=52)
        menu.add_column("opt",  style="bold yellow", width=5)
        menu.add_column("desc", style="white")

        entries = [
            ("─── Process Management ───────────────────────────", ""),
            (" 1 ", "List all processes"),
            (" 2 ", "Add a new process"),
            (" 3 ", "Remove / terminate a process"),
            (" 4 ", "Modify process attributes"),
            (" 5 ", "Reset to default sample processes"),
            ("─── Scheduling Algorithms ────────────────────────", ""),
            (" 6 ", "Run  FCFS  (First Come First Served)"),
            (" 7 ", "Run  SJF   (Shortest Job First)"),
            (" 8 ", "Run  PS    (Priority Scheduling)"),
            (" 9 ", "Run  RR    (Round Robin)"),
            ("10 ", f"Set  RR Quantum  (current: {self.manager.rr_quantum})"),
            ("─── Analysis ─────────────────────────────────────", ""),
            ("11 ", "Compare all algorithms (side-by-side)"),
            ("─── System ───────────────────────────────────────", ""),
            (" 0 ", "Exit"),
        ]
        for opt, desc in entries:
            if desc == "":
                menu.add_row(f"[bold magenta]{opt}[/bold magenta]", "")
            else:
                menu.add_row(opt, desc)

        console.print(Panel(menu, title="[bold yellow]MAIN MENU[/bold yellow]",
                            border_style="yellow", padding=(0, 2)))

    # ── Sub-flows ─────────────────────────────────────────────────────────

    def flow_add_process(self):
        console.print(Rule("[bold cyan]Add New Process[/bold cyan]"))
        pid      = self._input_int("PID (unique integer)", 1, 9999)
        if pid is None: return
        name     = self._input_str("Process name")
        arrival  = self._input_int("Arrival time (≥ 0)", 0, 9999)
        if arrival is None: return
        burst    = self._input_int("Burst time (≥ 1)", 1, 9999)
        if burst is None: return
        priority = self._input_int("Priority (1=highest)", 1, 99)
        if priority is None: return
        self.manager.add_process(pid, name or f"P{pid}", arrival, burst, priority)

    def flow_remove_process(self):
        console.print(Rule("[bold red]Terminate Process[/bold red]"))
        self.manager.list_processes()
        pid = self._input_int("PID to terminate", 1, 9999)
        if pid is None: return
        self.manager.terminate_process(pid)

    def flow_modify_process(self):
        console.print(Rule("[bold yellow]Modify Process[/bold yellow]"))
        self.manager.list_processes()
        pid = self._input_int("PID to modify", 1, 9999)
        if pid is None: return

        fields = {
            "1": ("burst_time",    int),
            "2": ("priority",      int),
            "3": ("arrival_time",  int),
            "4": ("name",          str),
        }
        console.print("  Fields: [1] Burst Time  [2] Priority  "
                      "[3] Arrival Time  [4] Name")
        choice = self._input_str("Select field").strip()
        if choice not in fields:
            console.print("[red]  ✖  Invalid selection.[/red]")
            return
        field_name, f_type = fields[choice]
        if f_type == int:
            val = self._input_int(f"New value for {field_name}", 0, 9999)
            if val is None: return
        else:
            val = self._input_str(f"New value for {field_name}")
        self.manager.modify_process(pid, field_name, f_type(val))

    def flow_set_quantum(self):
        console.print(Rule("[bold cyan]Set Round Robin Quantum[/bold cyan]"))
        q = self._input_int(f"New quantum (current={self.manager.rr_quantum})", 1, 20)
        if q is None: return
        self.manager.set_quantum(q)

    # ── Main event loop ───────────────────────────────────────────────────

    def run(self):
        """Start the interactive session."""
        self.print_banner()
        console.print(
            Panel(
                "[bold green]4 sample processes loaded automatically.[/bold green]\n"
                "[dim]Chrome · VSCode · Terminal · Spotify[/dim]",
                border_style="green", padding=(0, 2)
            )
        )
        console.print()

        while True:
            self.print_menu()
            choice = input("  ➤  Enter option: ").strip()
            console.print()

            try:
                if   choice == "1":  self.manager.list_processes()
                elif choice == "2":  self.flow_add_process()
                elif choice == "3":  self.flow_remove_process()
                elif choice == "4":  self.flow_modify_process()
                elif choice == "5":  self.manager.reset_to_defaults()
                elif choice == "6":  self.manager.run_fcfs()
                elif choice == "7":  self.manager.run_sjf()
                elif choice == "8":  self.manager.run_priority()
                elif choice == "9":  self.manager.run_rr()
                elif choice == "10": self.flow_set_quantum()
                elif choice == "11": self.manager.run_all_and_compare()
                elif choice == "0":
                    console.print(Panel(
                        "[bold yellow]Session ended. Goodbye![/bold yellow]",
                        border_style="yellow"
                    ))
                    sys.exit(0)
                else:
                    console.print("[red]  ✖  Invalid option. Choose 0–11.[/red]")
            except KeyboardInterrupt:
                console.print("\n[yellow]  ⚠  Interrupted. Back to menu.[/yellow]")

            console.print()
            input("  Press [Enter] to continue…")
            console.clear()
            self.print_banner()


# ═══════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    ui = TerminalUI()
    ui.run()
