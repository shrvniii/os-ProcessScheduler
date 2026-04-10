"""
==============================================================================
  PARI'S CPU SCHEDULING ALGORITHMS MODULE
  File    : pari_scheduler.py
  Author  : Pari
  For     : OS Process Manager Simulator (integrates with Shravani's GUI)

  HOW TO INTEGRATE INTO SHRAVANI'S gui_process_manager.py:
  ─────────────────────────────────────────────────────────
    1. Copy everything from the "ALGORITHM FUNCTIONS" section downward
       (starting from fcfs_scheduling) into Shravani's file, just before
       the ProcessManagerApp class definition.

    2. These functions reference THREE globals that must exist in the GUI file:
         process_list    → list of PCB dicts  (already exists in the GUI)
         gantt_log       → list of (pid, start, end) tuples (add if missing)
         update_gui_table() → function that refreshes the Treeview

    3. In the GUI's "Run Scheduler" button callback, replace the current
       dispatcher call with:
           run_scheduler(algorithm_name, time_quantum=q)

    4. To show averages in the GUI after running:
           avgs = compute_averages()
           # avgs["avg_waiting_time"], avgs["avg_turnaround_time"], etc.

  PCB DICTIONARY KEYS USED BY PARI'S FUNCTIONS:
  ──────────────────────────────────────────────
    pid             – unique process identifier
    arrival_time    – time process enters the ready queue
    burst_time      – total CPU time required (never changes)
    remaining_burst – CPU time left (decremented during Round Robin)
    priority        – scheduling priority (lower number = higher urgency)
    status          – "Ready" / "Running" / "Terminated"
    completion_time – time process finished (None until computed)
    waiting_time    – time spent waiting in ready queue
    turnaround_time – completion_time − arrival_time
    response_time   – first_cpu_time − arrival_time

  STANDALONE TEST:
    python pari_scheduler.py
==============================================================================
"""

import copy
from collections import deque


# =============================================================================
#  STANDALONE TESTING SETUP
#  These stubs exist only for running this file independently.
#  When integrating into Shravani's GUI, these are already defined there
#  as real global variables — DO NOT paste this section into the GUI file.
# =============================================================================

def _make_pcb(pid, arrival_time, burst_time, priority):
    """
    Create a Process Control Block (PCB) dictionary.
    Uses Pari's field naming to match the integration spec.
    """
    return {
        "pid":             int(pid),
        "arrival_time":    int(arrival_time),
        "burst_time":      int(burst_time),
        "remaining_burst": int(burst_time),   # used by Round Robin
        "priority":        int(priority),     # lower = higher urgency
        "status":          "Ready",
        "completion_time": None,
        "waiting_time":    None,
        "turnaround_time": None,
        "response_time":   None,
    }

# Shared globals — the GUI exposes these; stubs used here for standalone testing
process_list = [
    _make_pcb(1, 0, 8, 2),   # P1  arrival=0  burst=8  priority=2
    _make_pcb(2, 1, 4, 1),   # P2  arrival=1  burst=4  priority=1 (highest)
    _make_pcb(3, 2, 9, 3),   # P3  arrival=2  burst=9  priority=3 (lowest)
    _make_pcb(4, 3, 5, 2),   # P4  arrival=3  burst=5  priority=2
]

gantt_log = []   # Each entry: (pid, start_time, end_time)
                 #   pid = -1 signals an IDLE interval

def update_gui_table():
    """Stub replacing Shravani's real update_gui_table() during standalone tests."""
    pass   # no-op in standalone mode; real GUI will have a full Treeview refresh


# =============================================================================
#  ALGORITHM 1 — FIRST COME FIRST SERVED (FCFS)
# =============================================================================

def fcfs_scheduling():
    """
    First Come First Served (FCFS)  ·  Non-Preemptive

    Theory:
        The simplest CPU scheduling algorithm. Processes are executed in the
        exact order they arrive. A process that arrives first is served first,
        and it runs until full completion — no preemption allowed.

    Characteristics:
        • Simple to implement (just sort by arrival_time).
        • Non-optimal: causes the "Convoy Effect" — long processes block
          shorter ones waiting behind them → high average waiting time.
        • Response time equals waiting time (single dispatch per process).

    How it works step-by-step:
        1. Sort all processes by arrival_time (tie-break: PID).
        2. Maintain a 'clock' variable representing current CPU time.
        3. If the next process hasn't arrived yet, the CPU is idle — record
           an IDLE gantt segment and advance the clock.
        4. Dispatch the process: record start time, run for full burst_time,
           advance clock, record end time, compute all metrics.

    Metrics computed:
        completion_time  = clock after process finishes
        turnaround_time  = completion_time − arrival_time
        waiting_time     = turnaround_time − burst_time
        response_time    = start_time − arrival_time  (same as waiting in FCFS)
    """
    global gantt_log
    gantt_log.clear()   # reset from any previous algorithm run

    # ── Step 1: Sort by arrival time; use PID as stable tie-breaker ──────────
    sorted_procs = sorted(process_list,
                          key=lambda p: (p["arrival_time"], p["pid"]))

    clock = 0   # CPU clock starts at time 0

    # ── Step 2–4: Serve each process in arrival order ─────────────────────────
    for proc in sorted_procs:

        # IDLE gap: if no process has arrived at current clock, fast-forward
        if clock < proc["arrival_time"]:
            gantt_log.append((-1, clock, proc["arrival_time"]))  # IDLE entry
            clock = proc["arrival_time"]

        # ── Dispatch ──────────────────────────────────────────────────────────
        proc["status"] = "Running"
        update_gui_table()          # refresh GUI to show green "Running" row

        start_time = clock          # note when this process first got the CPU
        clock     += proc["burst_time"]   # run to full completion

        # ── Gantt log entry ───────────────────────────────────────────────────
        gantt_log.append((proc["pid"], start_time, clock))

        # ── Compute scheduling metrics ────────────────────────────────────────
        proc["completion_time"] = clock
        proc["turnaround_time"] = clock - proc["arrival_time"]
        proc["waiting_time"]    = proc["turnaround_time"] - proc["burst_time"]
        proc["response_time"]   = start_time - proc["arrival_time"]

        # Clamp edge-case negatives to zero
        proc["waiting_time"]  = max(0, proc["waiting_time"])
        proc["response_time"] = max(0, proc["response_time"])

        proc["status"] = "Terminated"
        update_gui_table()          # refresh GUI to show grey "Terminated" row


# =============================================================================
#  ALGORITHM 2 — SHORTEST JOB FIRST (SJF)  ·  Non-Preemptive
# =============================================================================

def sjf_scheduling():
    """
    Shortest Job First (SJF)  ·  Non-Preemptive

    Theory:
        At every scheduling decision point, the CPU picks the process with the
        MINIMUM total burst_time among all processes that have already arrived.
        Once a process is dispatched, it runs to completion.

    Why SJF is optimal:
        SJF minimises AVERAGE waiting time across all non-preemptive algorithms.
        This is provable by an exchange argument: swapping a long job before a
        short job always increases the average wait.

    Limitation:
        Requires knowing burst times in advance (not possible in real OSes).
        Causes STARVATION of long processes if short ones keep arriving.

    Steps:
        1. Keep a pool of 'remaining' (unfinished) processes.
        2. At each decision point, collect all arrived processes.
        3. From those available, pick the one with the smallest burst_time.
        4. Run it to completion, update metrics.
        5. If none have arrived yet, advance clock to next arrival (IDLE).
    """
    global gantt_log
    gantt_log.clear()

    # Deep-copy so burst_time on original PCBs is not modified during simulation
    remaining    = copy.deepcopy(process_list)
    # Map from pid → original PCB in process_list so we can write metrics back
    original_map = {p["pid"]: p for p in process_list}

    clock = 0

    # ── Main scheduling loop — continues until all processes are done ─────────
    while remaining:

        # Processes that have arrived by the current clock
        available = [p for p in remaining if p["arrival_time"] <= clock]

        if not available:
            # No process ready: CPU is idle — jump to the next arrival
            next_arr = min(p["arrival_time"] for p in remaining)
            gantt_log.append((-1, clock, next_arr))   # IDLE segment
            clock = next_arr
            continue   # re-check after advancing clock

        # ── Select: minimum burst_time; tie-break by arrival then PID ─────────
        chosen = min(available,
                     key=lambda p: (p["burst_time"], p["arrival_time"], p["pid"]))
        remaining.remove(chosen)    # remove from unscheduled pool

        # Update GUI and record dispatch
        original_map[chosen["pid"]]["status"] = "Running"
        update_gui_table()

        start_time = clock
        clock     += chosen["burst_time"]

        gantt_log.append((chosen["pid"], start_time, clock))

        # Write computed metrics back to the original PCB in process_list
        orig = original_map[chosen["pid"]]
        orig["completion_time"] = clock
        orig["turnaround_time"] = clock - chosen["arrival_time"]
        orig["waiting_time"]    = orig["turnaround_time"] - chosen["burst_time"]
        orig["response_time"]   = start_time - chosen["arrival_time"]

        orig["waiting_time"]  = max(0, orig["waiting_time"])
        orig["response_time"] = max(0, orig["response_time"])

        orig["status"] = "Terminated"
        update_gui_table()


# =============================================================================
#  ALGORITHM 3 — PRIORITY SCHEDULING  ·  Non-Preemptive
# =============================================================================

def priority_scheduling():
    """
    Priority Scheduling  ·  Non-Preemptive

    Theory:
        Each process is tagged with a priority number. The CPU always picks the
        HIGHEST priority process (i.e., the one with the LOWEST priority number)
        among those that have arrived. Like FCFS within each priority tier.

    Priority convention (matches Linux 'nice' values):
        priority = 1  → highest urgency (served first)
        priority = 10 → lowest urgency  (served last)

    Tie-breaking rule:
        Equal priority → earlier arrival wins.
        Equal arrival  → smaller PID wins.
        This makes scheduling deterministic (reproducible results).

    Problem — Starvation:
        Low-priority processes may wait forever if high-priority ones keep
        arriving. The standard fix is 'ageing' (gradually raising the priority
        of waiting processes) — not implemented here for simplicity.

    Steps:
        1. Maintain a pool of remaining un-scheduled processes.
        2. At each decision point, gather all arrived processes.
        3. From those, choose the one with min(priority).
        4. Run to completion; update metrics.
        5. IDLE if no process has arrived yet.
    """
    global gantt_log
    gantt_log.clear()

    remaining    = copy.deepcopy(process_list)
    original_map = {p["pid"]: p for p in process_list}

    clock = 0

    while remaining:

        available = [p for p in remaining if p["arrival_time"] <= clock]

        if not available:
            next_arr = min(p["arrival_time"] for p in remaining)
            gantt_log.append((-1, clock, next_arr))
            clock = next_arr
            continue

        # ── Select: lowest priority number = highest urgency ──────────────────
        # Tie-break: arrival_time → PID (deterministic ordering)
        chosen = min(available,
                     key=lambda p: (p["priority"], p["arrival_time"], p["pid"]))
        remaining.remove(chosen)

        original_map[chosen["pid"]]["status"] = "Running"
        update_gui_table()

        start_time = clock
        clock     += chosen["burst_time"]

        gantt_log.append((chosen["pid"], start_time, clock))

        orig = original_map[chosen["pid"]]
        orig["completion_time"] = clock
        orig["turnaround_time"] = clock - chosen["arrival_time"]
        orig["waiting_time"]    = orig["turnaround_time"] - chosen["burst_time"]
        orig["response_time"]   = start_time - chosen["arrival_time"]

        orig["waiting_time"]  = max(0, orig["waiting_time"])
        orig["response_time"] = max(0, orig["response_time"])

        orig["status"] = "Terminated"
        update_gui_table()


# =============================================================================
#  ALGORITHM 4 — ROUND ROBIN (RR)  ·  Preemptive, Time-Sliced
# =============================================================================

def round_robin_scheduling(time_quantum: int = 2):
    """
    Round Robin (RR)  ·  Preemptive

    Theory:
        Round Robin is the standard algorithm used in time-sharing systems
        (e.g., interactive desktops). Every process in the ready queue receives
        a fixed CPU time slice called the TIME QUANTUM (or time slice). After
        its slice expires, the running process is preempted and placed at the
        BACK of the ready queue. The CPU then serves the next process in line.

    Why Round Robin?
        It is FAIR: every process gets regular CPU turns, so no starvation.
        It has good RESPONSE times for interactive processes.
        Disadvantage: high context-switch overhead if quantum is too small;
        degenerates to FCFS if quantum is very large.

    Key implementation details:
        • deque (double-ended queue) acts as the circular ready queue.
        • 'not_arrived' holds processes yet to be admitted.
        • admit_arrivals(t) is called after every clock tick during a slice
          so that newly arriving processes are queued in the correct order.
        • 'first_cpu_time[pid]' records when each process FIRST got the CPU —
          needed for response_time = first_cpu_time − arrival_time.
        • remaining_burst is decremented each slice; = 0 → Terminated.
        • If preempted, the process is appended to the BACK of the queue.

    Parameter:
        time_quantum : int – length of each time slice (default 2 time units)

    Steps:
        1. Reset remaining_burst for all processes.
        2. Sort processes by arrival_time into not_arrived pool.
        3. Admit all processes whose arrival_time ≤ clock into ready_queue.
        4. Pick the front of ready_queue; run for min(quantum, remaining_burst).
        5. Admit any new arrivals that occurred DURING the slice.
        6. If remaining_burst == 0 → Terminated; else → re-enqueue at back.
        7. Repeat until ready_queue and not_arrived are both empty.
    """
    global gantt_log
    gantt_log.clear()

    if time_quantum < 1:
        raise ValueError("time_quantum must be >= 1")

    # ── Step 1: Reset remaining_burst (crucial if running after another algo) ──
    for p in process_list:
        p["remaining_burst"] = p["burst_time"]
        p["status"]          = "Ready"

    # ── Step 2: Sort by arrival time for deterministic admission order ─────────
    not_arrived = sorted(
        copy.deepcopy(process_list),
        key=lambda p: (p["arrival_time"], p["pid"])
    )

    # Write metrics back to original PCBs through this map
    original_map = {p["pid"]: p for p in process_list}

    # first_cpu_time[pid] = clock value when process FIRST ran (for response_time)
    first_cpu_time: dict = {}

    ready_queue: deque = deque()   # circular FIFO ready queue
    clock = 0

    # ── Inner helper: admit newly arrived processes into the ready queue ───────
    def admit_arrivals(up_to: int):
        """
        Move all processes from not_arrived whose arrival_time <= up_to
        into ready_queue, preserving arrival order (then PID stability).
        Called at time=0 and after every clock tick during each slice.
        """
        to_admit = [p for p in not_arrived if p["arrival_time"] <= up_to]
        for p in sorted(to_admit, key=lambda x: (x["arrival_time"], x["pid"])):
            ready_queue.append(p)
            not_arrived.remove(p)

    # Admit any processes already present at time 0
    admit_arrivals(clock)

    # ── Steps 3–7: Main Round Robin scheduling loop ───────────────────────────
    while ready_queue or not_arrived:

        if not ready_queue:
            # CPU idle: no process is ready yet — jump to next arrival
            next_arr = min(p["arrival_time"] for p in not_arrived)
            gantt_log.append((-1, clock, next_arr))
            clock = next_arr
            admit_arrivals(clock)
            continue

        # Dequeue the FRONT process (FIFO order within the queue)
        proc = ready_queue.popleft()

        # Record the very first time this process received the CPU
        if proc["pid"] not in first_cpu_time:
            first_cpu_time[proc["pid"]] = clock

        # Mark as Running in original PCB (GUI updates the table row color)
        original_map[proc["pid"]]["status"] = "Running"
        update_gui_table()

        # How long does this slice actually run?
        run_for  = min(time_quantum, proc["remaining_burst"])
        end_time = clock + run_for

        # Record this execution interval in the Gantt log
        gantt_log.append((proc["pid"], clock, end_time))

        # ── Admit any processes that arrive DURING this slice ─────────────────
        # We step tick-by-tick so admission order exactly mirrors a real OS
        for tick in range(clock + 1, end_time + 1):
            admit_arrivals(tick)

        clock                   = end_time
        proc["remaining_burst"] -= run_for

        orig = original_map[proc["pid"]]

        if proc["remaining_burst"] == 0:
            # ── Process FINISHED during this slice ────────────────────────────
            orig["completion_time"] = clock
            orig["turnaround_time"] = clock - proc["arrival_time"]
            orig["waiting_time"]    = (orig["turnaround_time"]
                                       - proc["burst_time"])
            orig["response_time"]   = (first_cpu_time[proc["pid"]]
                                       - proc["arrival_time"])

            orig["waiting_time"]  = max(0, orig["waiting_time"])
            orig["response_time"] = max(0, orig["response_time"])
            orig["remaining_burst"] = 0

            orig["status"] = "Terminated"
            update_gui_table()

        else:
            # ── Preempted — quantum expired, put back at END of queue ─────────
            orig["status"] = "Ready"
            update_gui_table()
            ready_queue.append(proc)   # circular: back of the queue


# =============================================================================
#  DISPATCHER: run_scheduler()
# =============================================================================

def run_scheduler(algorithm_name: str, time_quantum: int = None):
    """
    Central dispatcher — routes to the correct scheduling function based on
    the algorithm name string received from the GUI's dropdown / button.

    This is the ONLY function the GUI needs to call. It handles normalisation
    of the algorithm name (case-insensitive, strips whitespace) so the GUI
    does not need to worry about exact string matching.

    Parameters
    ----------
    algorithm_name : str
        Name of the algorithm to run.
        Accepted values (case-insensitive):
            "FCFS"          → First Come First Served
            "SJF"           → Shortest Job First
            "Priority"/"PS" → Priority Scheduling
            "Round Robin"   → Round Robin (requires time_quantum)
            "RR"            → alias for Round Robin

    time_quantum : int or None
        Required only for Round Robin. Defaults to 2 if omitted.
        Ignored for all other algorithms.

    Raises
    ------
    ValueError
        If algorithm_name does not match any known algorithm.

    Example usage inside Shravani's GUI:
        # Inside the "Run Scheduler" button callback:
        algo = self.algo_var.get()          # e.g. "FCFS" or "Round Robin"
        q    = self.rr_quantum.get()        # only relevant for RR
        run_scheduler(algo, time_quantum=q)
        avgs = compute_averages()
        self.lbl_avg.config(text=f"Avg WT: {avgs['avg_waiting_time']:.2f}  "
                                  f"Avg TAT: {avgs['avg_turnaround_time']:.2f}")
    """
    # Normalise: lowercase + strip whitespace → robust string matching
    name = algorithm_name.strip().lower()

    if name == "fcfs":
        fcfs_scheduling()

    elif name == "sjf":
        sjf_scheduling()

    elif name in ("priority", "ps"):
        priority_scheduling()

    elif name in ("round robin", "rr"):
        # Default quantum = 2 if the caller did not supply one
        q = int(time_quantum) if time_quantum is not None else 2
        round_robin_scheduling(time_quantum=q)

    else:
        raise ValueError(
            f"Unknown algorithm name: '{algorithm_name}'.\n"
            "Valid options: 'FCFS', 'SJF', 'Priority', 'Round Robin'"
        )


# =============================================================================
#  ANALYTICS: compute_averages()
# =============================================================================

def compute_averages() -> dict:
    """
    Compute average scheduling performance metrics across all TERMINATED
    processes in process_list.

    Why only terminated processes?
        If a simulation is partially run or a process hasn't been reached yet,
        its metrics are None. Including None values would crash the summation.

    Metrics explained:
        Waiting Time (WT)      = time spent in the ready queue waiting for CPU
                               = turnaround_time − burst_time
        Turnaround Time (TAT)  = total time from arrival to completion
                               = completion_time − arrival_time
        Response Time (RT)     = time from arrival to FIRST CPU access
                               = first_cpu_time − arrival_time

    Returns
    -------
    dict with the following keys:
        "avg_waiting_time"    → float : mean WT  across all terminated processes
        "avg_turnaround_time" → float : mean TAT across all terminated processes
        "avg_response_time"   → float : mean RT  across all terminated processes
        "count"               → int   : number of terminated processes included
        "total_waiting"       → int   : sum of all waiting times
        "total_turnaround"    → int   : sum of all turnaround times
        "total_response"      → int   : sum of all response times

    Always returns valid floats (0.0 defaults when no process has run yet),
    so the GUI can safely display the result without a try/except.
    """

    # Include only processes that have fully completed (have a completion_time)
    terminated = [
        p for p in process_list
        if p["completion_time"] is not None
    ]

    # Guard: return zero-valued dict if nothing has been scheduled yet
    if not terminated:
        return {
            "avg_waiting_time":    0.0,
            "avg_turnaround_time": 0.0,
            "avg_response_time":   0.0,
            "count":               0,
            "total_waiting":       0,
            "total_turnaround":    0,
            "total_response":      0,
        }

    n                = len(terminated)
    total_waiting    = sum(p["waiting_time"]    for p in terminated)
    total_turnaround = sum(p["turnaround_time"] for p in terminated)
    total_response   = sum(p["response_time"]   for p in terminated)

    return {
        "avg_waiting_time":    total_waiting    / n,
        "avg_turnaround_time": total_turnaround / n,
        "avg_response_time":   total_response   / n,
        "count":               n,
        "total_waiting":       total_waiting,
        "total_turnaround":    total_turnaround,
        "total_response":      total_response,
    }


# =============================================================================
#  STANDALONE TEST  —  run:  python pari_scheduler.py
#  (Remove or comment out this section when integrating into the GUI file)
# =============================================================================

def _reset_processes():
    """Restore process_list to the original 4 sample PCBs before each test."""
    global process_list
    process_list = [
        _make_pcb(1, 0, 8, 2),
        _make_pcb(2, 1, 4, 1),
        _make_pcb(3, 2, 9, 3),
        _make_pcb(4, 3, 5, 2),
    ]

def _print_results(title: str):
    """Print a formatted per-process metrics table and Gantt log."""
    LINE = "=" * 70
    print(f"\n{LINE}")
    print(f"  {title}")
    print(LINE)

    # Column headers
    print(f"  {'PID':<5} {'AT':>4} {'BT':>4} {'CT':>5} "
          f"{'TAT':>5} {'WT':>5} {'RT':>5}  Status")
    print(f"  {'-'*60}")

    for p in sorted(process_list, key=lambda x: x["pid"]):
        def f(v):
            return str(v) if v is not None else "─"
        print(f"  P{p['pid']:<4} {p['arrival_time']:>4} {p['burst_time']:>4} "
              f"{f(p['completion_time']):>5} {f(p['turnaround_time']):>5} "
              f"{f(p['waiting_time']):>5} {f(p['response_time']):>5}  "
              f"{p['status']}")

    # Averages row
    avgs = compute_averages()
    print(f"\n  Avg Waiting Time    = {avgs['avg_waiting_time']:.2f}")
    print(f"  Avg Turnaround Time = {avgs['avg_turnaround_time']:.2f}")
    print(f"  Avg Response Time   = {avgs['avg_response_time']:.2f}")

    # Gantt log
    print(f"\n  Gantt Log:")
    print(f"  {'Proc':<7}  Start -> End")
    print(f"  {'-'*25}")
    for pid, s, e in gantt_log:
        label = f"P{pid}" if pid != -1 else "IDLE"
        print(f"  {label:<7}  {s:>3}  ->  {e:>3}")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  PARI'S SCHEDULING MODULE  —  Standalone Test")
    print("  Processes: P1(AT=0,BT=8,Pri=2)  P2(AT=1,BT=4,Pri=1)")
    print("             P3(AT=2,BT=9,Pri=3)  P4(AT=3,BT=5,Pri=2)")
    print("=" * 70)

    # ── FCFS ──────────────────────────────────────────────────────────────────
    _reset_processes()
    run_scheduler("FCFS")
    _print_results("Algorithm 1: First Come First Served (FCFS)")

    # ── SJF ───────────────────────────────────────────────────────────────────
    _reset_processes()
    run_scheduler("SJF")
    _print_results("Algorithm 2: Shortest Job First (SJF) — Non-Preemptive")

    # ── Priority Scheduling ───────────────────────────────────────────────────
    _reset_processes()
    run_scheduler("Priority")
    _print_results("Algorithm 3: Priority Scheduling — Non-Preemptive")

    # ── Round Robin  Q=2 ──────────────────────────────────────────────────────
    _reset_processes()
    run_scheduler("Round Robin", time_quantum=2)
    _print_results("Algorithm 4: Round Robin (Quantum = 2)")

    # ── Round Robin  Q=3 ──────────────────────────────────────────────────────
    _reset_processes()
    run_scheduler("Round Robin", time_quantum=3)
    _print_results("Algorithm 4: Round Robin (Quantum = 3)")

    # ── Dispatcher error handling test ────────────────────────────────────────
    print("\n  Testing invalid algorithm name...")
    try:
        run_scheduler("INVALID_ALGO")
    except ValueError as e:
        print(f"  ValueError caught correctly: {e}")

    print("\n  All tests complete.\n")
