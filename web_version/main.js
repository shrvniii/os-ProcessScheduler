/**
 * OS Process Scheduler - Main Controller & Scheduling Engine
 * Enhanced with Bento Grid, Playback History, Activity Logs, and Haptic Feedback Layers
 */

class Scheduler {
    constructor() {
        this.processes = [];
        this.gantt = [];
        this.history = [];
        this.logs = [];
        this.nextPid = 1;
        this.selectedAlgo = 'FCFS';
        this.quantum = 2;
        this.isSimulating = false;
        this.isPaused = false;
        this.stepRequested = false;
        this.simulationSpeed = 300;

        // Initial Sample Data
        this.addProcess("Chrome", 0, 8, 2, 1);
        this.addProcess("VSCode", 1, 5, 1, 2);
        this.addProcess("Terminal", 2, 12, 3, 2);
    }

    addProcess(name, arrival, burst, priority, queueLevel) {
        this.triggerHaptic(20);
        const p = {
            pid: this.nextPid++,
            name: name || `Proc-${this.nextPid}`,
            arrival: parseInt(arrival) || 0,
            burst: parseInt(burst) || 1,
            remaining: parseInt(burst) || 1,
            priority: parseInt(priority) || 1,
            queueLevel: parseInt(queueLevel) || 1,
            status: 'NEW',
            startTime: null,
            completionTime: null,
            turnaround: 0,
            waiting: 0,
            color: this.generateProfessionalColor()
        };
        this.processes.push(p);
    }

    triggerHaptic(ms) {
        if (navigator.vibrate) navigator.vibrate(ms);
        // Visual Haptic: Shake the sidebar
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            sidebar.classList.add('haptic-shake');
            setTimeout(() => sidebar.classList.remove('haptic-shake'), 400);
        }
    }

    generateProfessionalColor() {
        const colors = ['#10b981', '#059669', '#f59e0b', '#d97706', '#0ea5e9', '#0284c7', '#6366f1', '#4f46e5', '#f43f5e'];
        return colors[Math.floor(Math.random() * colors.length)];
    }

    reset() {
        this.processes.forEach(p => {
            p.remaining = p.burst;
            p.status = 'NEW';
            p.startTime = null;
            p.completionTime = null;
            p.turnaround = 0;
            p.waiting = 0;
        });
        this.gantt = [];
        this.history = [];
        this.logs = [];
    }

    async execute() {
        if (this.isSimulating) return;
        this.isSimulating = true;
        this.reset();
        
        let time = 0;
        let queue = [];
        let procs = this.processes.map(p => ({ ...p, remaining: p.burst, status: 'NEW', startTime: null }));
        let notArrived = [...procs].sort((a, b) => a.arrival - b.arrival);
        let gantt = [];
        let doneCount = 0;
        let currentP = null;

        const uiQueue = document.getElementById('readyQueueDisplay');
        const cpuSlot = document.getElementById('activeCpuSlot');
        const logDisplay = document.getElementById('systemLog');

        const addLog = (msg) => {
            const div = document.createElement('div');
            div.className = 'log-entry';
            div.innerHTML = `<span class="log-time">[${time}ms]</span> ${msg}`;
            logDisplay.appendChild(div);
            logDisplay.scrollTop = logDisplay.scrollHeight;
        };

        const triggerCardHaptic = (selector) => {
            const card = document.querySelector(selector);
            if (card) {
                card.classList.add('haptic-shake');
                setTimeout(() => card.classList.remove('haptic-shake'), 400);
            }
        };

        const updateUIQueue = (runningProcess = null) => {
            uiQueue.innerHTML = '';
            queue.forEach(p => {
                const node = document.createElement('div');
                node.className = 'queue-node';
                node.style.borderLeftColor = p.color;
                node.innerHTML = `
                    <div class="qn-left"><div class="qn-name">${p.name}</div><div class="qn-pid">ID: ${p.pid}</div></div>
                    <div class="qn-right"><div class="qn-meta">REM: ${p.remaining}ms</div></div>
                `;
                uiQueue.appendChild(node);
            });
            if (runningProcess) {
                cpuSlot.classList.add('occupied');
                cpuSlot.style.borderColor = runningProcess.color;
                cpuSlot.innerHTML = `<div class="queue-node" style="border:none; background:transparent; width:100%;"><div class="qn-left"><div class="qn-name" style="font-size: 1.1rem">${runningProcess.name}</div><div class="qn-pid">EXECUTING...</div></div><div class="qn-right"><div class="qn-meta" style="font-size: 1rem">REM: ${runningProcess.remaining}ms</div></div></div>`;
            } else {
                cpuSlot.classList.remove('occupied');
                cpuSlot.style.borderColor = 'var(--border)';
                cpuSlot.innerHTML = `<div class="cpu-placeholder">IDLE</div>`;
            }
        };

        const saveSnapshot = (p) => {
            this.history.push(JSON.stringify({
                time, queue, notArrived, gantt, doneCount, procs, activeP: p, logs: [...this.logs]
            }));
        };

        const waitForTick = async () => {
            while (this.isPaused && !this.stepRequested) {
                await new Promise(r => setTimeout(r, 50));
                if (!this.isSimulating) return;
            }
            this.stepRequested = false;
        };

        const sleep = (ms) => new Promise(res => setTimeout(res, ms));
        const getDelay = (factor = 1) => this.simulationSpeed * factor;

        logDisplay.innerHTML = '';
        addLog(`Simulation started: ${this.selectedAlgo}`);
        triggerCardHaptic('.bento-logs');

        while (doneCount < procs.length) {
            await waitForTick();
            if (!this.isSimulating) break;

            let arrivedNow = false;
            while (notArrived.length > 0 && notArrived[0].arrival <= time) {
                let p = notArrived.shift();
                p.status = 'READY';
                queue.push(p);
                arrivedNow = true;
                addLog(`Process ${p.name} arrived at queue.`);
                triggerCardHaptic('.bento-queue');
            }
            
            if (arrivedNow) {
                updateUIQueue(currentP);
                await sleep(getDelay(0.5)); 
            }

            if (queue.length === 0 && !currentP) {
                let nextArrival = notArrived.length > 0 ? notArrived[0].arrival : time + 1;
                addLog(`CPU Idle. Waiting for next arrival.`);
                gantt.push({ pid: -1, name: 'IDLE', start: time, end: nextArrival });
                time = nextArrival;
                continue;
            }

            if (!currentP) {
                if (this.selectedAlgo === 'FCFS') currentP = queue.shift();
                else if (this.selectedAlgo === 'SJF') { queue.sort((a,b) => a.burst - b.burst || a.arrival - b.arrival); currentP = queue.shift(); }
                else if (this.selectedAlgo === 'Priority') { queue.sort((a,b) => a.priority - b.priority || a.arrival - b.arrival); currentP = queue.shift(); }
                else if (this.selectedAlgo === 'SRTF') { queue.sort((a,b) => a.remaining - b.remaining || a.arrival - b.arrival); currentP = queue.shift(); }
                else if (this.selectedAlgo === 'Round Robin') currentP = queue.shift();
                else if (this.selectedAlgo === 'MLQ') { queue.sort((a,b) => a.queueLevel - b.queueLevel || a.arrival - b.arrival); currentP = queue.shift(); }
                
                if (currentP) {
                    currentP.status = 'RUNNING';
                    if (currentP.startTime === null) currentP.startTime = time;
                    addLog(`CPU picked ${currentP.name}.`);
                    updateUIQueue(currentP);
                    await sleep(getDelay(0.3));
                }
            }

            if (currentP) {
                let slice = (this.selectedAlgo === 'Round Robin') ? Math.min(currentP.remaining, this.quantum) : currentP.remaining;
                if (this.selectedAlgo === 'SRTF') slice = 1;
                
                gantt.push({ pid: currentP.pid, name: currentP.name, start: time, end: time + slice, color: currentP.color });
                
                for(let s=0; s<slice; s++) {
                    saveSnapshot(currentP);
                    await waitForTick();
                    time++;
                    currentP.remaining--;
                    
                    let inSliceArrival = false;
                    while (notArrived.length > 0 && notArrived[0].arrival <= time) {
                        let incoming = notArrived.shift();
                        incoming.status = 'READY';
                        queue.push(incoming);
                        inSliceArrival = true;
                    }
                    if(inSliceArrival) { updateUIQueue(currentP); triggerCardHaptic('.bento-queue'); }
                    
                    if (this.selectedAlgo === 'SRTF') break; 
                }

                if (currentP.remaining === 0) {
                    addLog(`${currentP.name} completed.`);
                    triggerCardHaptic('.bento-table');
                    currentP.completionTime = time;
                    currentP.turnaround = currentP.completionTime - currentP.arrival;
                    currentP.waiting = currentP.turnaround - currentP.burst;
                    currentP.status = 'Terminated';
                    doneCount++;
                    currentP = null;
                } else if (this.selectedAlgo === 'Round Robin' || this.selectedAlgo === 'SRTF') {
                    currentP.status = 'READY';
                    queue.push(currentP);
                    currentP = null;
                }
            }

            this.processes.forEach(p => {
                let latest = procs.find(lp => lp.pid === p.pid);
                if (latest) Object.assign(p, latest);
            });
            this.gantt = [...gantt];
            this.mergeGantt();
            window.refreshUI();
            updateUIQueue(currentP);
            await sleep(getDelay(0.1));
        }

        this.isSimulating = false;
        triggerCardHaptic('.bento-stats');
        window.updateAnalytics();
    }

    mergeGantt() {
        if (this.gantt.length === 0) return;
        let merged = [];
        let curr = { ...this.gantt[0] };
        for (let i = 1; i < this.gantt.length; i++) {
            let next = this.gantt[i];
            if (next.pid === curr.pid && next.start === curr.end) {
                curr.end = next.end;
            } else {
                merged.push(curr);
                curr = { ...next };
            }
        }
        merged.push(curr);
        this.gantt = merged;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const engine = new Scheduler();
    const tableBody = document.getElementById('processTableBody');
    const ganttChart = document.getElementById('ganttChart');
    let performanceChart = null;

    window.refreshUI = () => {
        tableBody.innerHTML = '';
        engine.processes.forEach(p => {
            const row = document.createElement('tr');
            row.innerHTML = `<td>#${p.pid}</td><td style="font-weight: 600;">${p.name}</td><td>${p.arrival}ms</td><td>${p.burst}ms</td><td><span class="status-pill ${p.status === 'Terminated' ? 'status-terminated' : (p.status === 'RUNNING' ? 'status-running' : 'status-ready')}">${p.status}</span></td><td style="font-weight: 500;">${p.turnaround}/${p.waiting}</td>`;
            tableBody.appendChild(row);
        });

        ganttChart.innerHTML = '';
        const timeline = document.createElement('div');
        timeline.className = 'gantt-timeline';
        engine.gantt.forEach(seg => {
            const block = document.createElement('div');
            block.className = 'gantt-block';
            block.style.width = `${Math.max(40, (seg.end - seg.start) * 30)}px`;
            if (seg.pid !== -1) {
                block.style.backgroundColor = seg.color;
                block.innerHTML = `<span class="pid">${seg.name}</span><span class="time-label">${seg.start}</span>`;
            } else {
                block.style.backgroundColor = 'var(--bg-main)';
                block.innerHTML = `<span class="pid" style="color: var(--text-dim)">IDLE</span><span class="time-label">${seg.start}</span>`;
            }
            if(seg === engine.gantt[engine.gantt.length-1]) {
                const el = document.createElement('span');el.className = 'time-label';el.style.right = '0';el.innerText = seg.end;block.appendChild(el);
            }
            timeline.appendChild(block);
        });
        ganttChart.appendChild(timeline);

        document.getElementById('statTotal').innerText = engine.processes.length;
        document.getElementById('statWait').innerText = (engine.processes.length ? (engine.processes.reduce((s,p)=>s+p.waiting,0)/engine.processes.length).toFixed(1) : 0) + "ms";
        document.getElementById('statTAT').innerText = (engine.processes.length ? (engine.processes.reduce((s,p)=>s+p.turnaround,0)/engine.processes.length).toFixed(1) : 0) + "ms";
        const lastEnd = engine.gantt.length ? engine.gantt[engine.gantt.length-1].end : 0;
        document.getElementById('statCPU').innerText = (lastEnd ? ((engine.processes.reduce((s,p)=>s+p.burst,0)/lastEnd)*100).toFixed(1) : 0) + "%";
    };

    window.updateAnalytics = () => {
        const ctx = document.getElementById('performanceChart').getContext('2d');
        if (performanceChart) performanceChart.destroy();
        performanceChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: engine.processes.map(p => p.name),
                datasets: [
                    { label: 'Turnaround', data: engine.processes.map(p => p.turnaround), backgroundColor: '#10b981' },
                    { label: 'Wait', data: engine.processes.map(p => p.waiting), backgroundColor: '#f59e0b' }
                ]
            },
            options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, grid: { color: '#2d323d' } } } }
        });
    };

    document.getElementById('addProcessBtn').onclick = () => {
        engine.addProcess(document.getElementById('pName').value, document.getElementById('pArrival').value, document.getElementById('pBurst').value, document.getElementById('pPriority').value, document.getElementById('pQueue').value);
        window.refreshUI();
    };

    document.getElementById('runSimulationBtn').onclick = () => {
        if (engine.isSimulating) return;
        engine.triggerHaptic(50);
        document.getElementById('simStatus').innerText = "Running...";
        document.getElementById('runSimulationBtn').disabled = true;
        document.getElementById('playbackControls').style.display = 'block';
        engine.execute().then(() => {
            document.getElementById('runSimulationBtn').disabled = false;
            document.getElementById('runSimulationBtn').style.opacity = '1';
        });
    };

    const pauseBtn = document.getElementById('pauseResumeBtn');
    pauseBtn.onclick = () => {
        engine.triggerHaptic(10);
        engine.isPaused = !engine.isPaused;
        pauseBtn.innerText = engine.isPaused ? 'Resume' : 'Pause';
    };

    document.getElementById('nextBtn').onclick = () => { if (engine.isPaused) { engine.triggerHaptic(5); engine.stepRequested = true; } };

    document.getElementById('prevBtn').onclick = () => {
        if (!engine.isPaused || engine.history.length < 2) return;
        engine.triggerHaptic(5);
        engine.history.pop();
        const last = JSON.parse(engine.history.pop());
        engine.processes = last.procs;
        engine.gantt = last.gantt;
        const logDisplay = document.getElementById('systemLog');
        logDisplay.innerHTML = '';
        (last.logs || []).forEach(l => {
            const div = document.createElement('div');div.className = 'log-entry';div.innerHTML = `<span class="log-time">[${l.time}ms]</span> ${l.msg}`;logDisplay.appendChild(div);
        });
        window.refreshUI();
    };

    document.getElementById('resetBtn').onclick = () => {
        engine.triggerHaptic(30);
        engine.isSimulating = false;
        engine.reset();
        document.getElementById('systemLog').innerHTML = '<div class="log-entry">System reset.</div>';
        window.refreshUI();
        document.getElementById('playbackControls').style.display = 'none';
        if (performanceChart) performanceChart.destroy();
    };

    document.querySelectorAll('.algo-btn').forEach(btn => {
        btn.onclick = () => {
            if (engine.isSimulating) return;
            engine.triggerHaptic(10);
            document.querySelectorAll('.algo-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            engine.selectedAlgo = btn.dataset.algo;
            document.getElementById('activeAlgo').innerText = engine.selectedAlgo;
            document.getElementById('rrSettings').style.display = engine.selectedAlgo === 'Round Robin' ? 'block' : 'none';
        }
    });

    const speedSlider = document.getElementById('speedSlider');
    speedSlider.oninput = () => {
        engine.simulationSpeed = 1010 - speedSlider.value;
        document.getElementById('speedVal').innerText = engine.simulationSpeed;
    };
    engine.simulationSpeed = 1010 - speedSlider.value;

    window.refreshUI();
});
