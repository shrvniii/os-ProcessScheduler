/**
 * OS Process Scheduler - Main Controller & Scheduling Engine
 * Enhanced with Pre-calculated Simulation Engine, Step-by-Step Playback, 
 * Algorithm Comparison, and Lifecycle Diagnostics.
 */

class Scheduler {
    constructor() {
        this.processes = [];
        this.nextPid = 1;
        this.selectedAlgo = 'FCFS';
        this.quantum = 3;
        this.isSimulating = false;
        this.isPaused = false;
        this.simulationSpeed = 300;
        
        // Simulation State
        this.simSteps = [];
        this.simIndex = 0;
        this.simTimer = null;
        
        // Tracking for Logs
        this.loggedStarted = [];
        this.loggedFinished = [];
        
        // Starts empty as requested
    }

    loadSampleData() {
        this.reset();
        this.addProcess("Chrome", 0, 8, 2, 1);
        this.addProcess("VSCode", 1, 5, 1, 2);
        this.addProcess("Terminal", 2, 12, 3, 2);
        this.addProcess("System", 4, 3, 1, 1);
        this.addLog("Sample workload loaded.");
        this.refreshUI();
    }

    addProcess(name, arrival, burst, priority, queueLevel) {
        const colors = ['#a0522d', '#d2b48c', '#ff9800', '#bb86fc', '#00e676', '#ffd740', '#ff4d6d', '#555555'];
        const p = {
            pid: this.nextPid++,
            name: name || "P" + (this.nextPid - 1),
            arrival: parseInt(arrival) || 0,
            burst: parseInt(burst) || 1,
            remaining: parseInt(burst) || 1,
            priority: parseInt(priority) || 1,
            queueLevel: parseInt(queueLevel) || 1,
            color: colors[(this.nextPid - 1) % colors.length],
            status: 'NEW',
            wt: 0,
            tat: 0,
            ct: 0,
            start: null
        };
        this.processes.push(p);
        this.triggerHaptic(20);
    }

    triggerHaptic(ms) {
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            sidebar.classList.add('haptic-shake');
            setTimeout(() => sidebar.classList.remove('haptic-shake'), 400);
        }
    }

    buildSteps(algo, rawProcesses, quantum) {
        let time = 0;
        const steps = [];
        const procs = rawProcesses.map(p => {
            return {
                ...p,
                rem: p.burst,
                done: false,
                status: 'NEW',
                firstStart: null
            };
        });
        
        const totalBurst = procs.reduce((s, p) => s + p.burst, 0);
        const maxTime = Math.max(...procs.map(p => p.arrival)) + totalBurst + 10;
        
        let rrQueue = [];
        let rrQuantumLeft = quantum;
        let rrCurrentPid = null;

        while (procs.some(p => !p.done) && time < maxTime) {
            const arrived = procs.filter(p => p.arrival <= time && !p.done);
            let chosen = null;
            let isPreemption = false;

            if (algo === 'FCFS') {
                if (arrived.length > 0) {
                    arrived.sort((a,b) => a.arrival - b.arrival || a.pid - b.pid);
                    const running = steps.length > 0 && !steps[steps.length-1].isIdle
                        ? procs.find(p => p.pid === steps[steps.length-1].pid && !p.done) : null;
                    chosen = running || arrived[0];
                }
            } else if (algo === 'SJF') {
                if (arrived.length > 0) {
                    const running = steps.length > 0 && !steps[steps.length-1].isIdle
                        ? procs.find(p => p.pid === steps[steps.length-1].pid && !p.done) : null;
                    arrived.sort((a,b) => a.burst - b.burst || a.arrival - b.arrival);
                    chosen = running || arrived[0];
                }
            } else if (algo === 'SRTN') {
                if (arrived.length > 0) {
                    arrived.sort((a,b) => a.rem - b.rem || a.arrival - b.arrival);
                    const prev = (steps.length > 0 && !steps[steps.length-1].isIdle) ? steps[steps.length-1].pid : null;
                    chosen = arrived[0];
                    if (prev && prev !== chosen.pid) isPreemption = true;
                }
            } else if (algo === 'Priority') {
                if (arrived.length > 0) {
                    const running = steps.length > 0 && !steps[steps.length-1].isIdle
                        ? procs.find(p => p.pid === steps[steps.length-1].pid && !p.done) : null;
                    arrived.sort((a,b) => a.priority - b.priority || a.arrival - b.arrival);
                    chosen = running || arrived[0];
                }
            } else if (algo === 'Priority_P') {
                if (arrived.length > 0) {
                    arrived.sort((a,b) => a.priority - b.priority || a.arrival - b.arrival);
                    const prev = (steps.length > 0 && !steps[steps.length-1].isIdle) ? steps[steps.length-1].pid : null;
                    chosen = arrived[0];
                    if (prev && prev !== chosen.pid) isPreemption = true;
                }
            } else if (algo === 'Round Robin') {
                arrived.forEach(p => {
                    if (!rrQueue.includes(p.pid) && (rrCurrentPid !== p.pid)) {
                        rrQueue.push(p.pid);
                    }
                });

                if (rrCurrentPid !== null) {
                    const cur = procs.find(p => p.pid === rrCurrentPid);
                    if (cur.done) {
                        rrCurrentPid = null;
                        rrQuantumLeft = quantum;
                    } else if (rrQuantumLeft <= 0) {
                        rrQueue.push(rrCurrentPid);
                        rrCurrentPid = null;
                        rrQuantumLeft = quantum;
                        isPreemption = true;
                    }
                }

                if (rrCurrentPid === null && rrQueue.length > 0) {
                    rrCurrentPid = rrQueue.shift();
                    rrQuantumLeft = quantum;
                }

                if (rrCurrentPid !== null) {
                    chosen = procs.find(p => p.pid === rrCurrentPid);
                }
            } else if (algo === 'MLQ') {
                if (arrived.length > 0) {
                    arrived.sort((a,b) => a.queueLevel - b.queueLevel || a.arrival - b.arrival);
                    const prev = (steps.length > 0 && !steps[steps.length-1].isIdle) ? steps[steps.length-1].pid : null;
                    chosen = arrived[0];
                    if (prev && prev !== chosen.pid) isPreemption = true;
                }
            }

            if (!chosen) {
                steps.push({ time, pid: 'IDLE', isIdle: true, isPreemption: false, snapshot: procs.map(p => ({...p})) });
                time++;
                continue;
            }

            if (chosen.firstStart === null) chosen.firstStart = time;
            chosen.rem--;
            if (algo === 'Round Robin') rrQuantumLeft--;

            if (chosen.rem === 0) {
                chosen.done = true;
                chosen.status = 'TERMINATED';
                chosen.ct = time + 1;
                chosen.tat = chosen.ct - chosen.arrival;
                chosen.wt = chosen.tat - chosen.burst;
            } else {
                chosen.status = 'RUNNING';
            }

            procs.forEach(p => {
                if (p.pid !== chosen.pid && !p.done) {
                    p.status = p.arrival <= time ? 'READY' : 'NEW';
                }
            });

            steps.push({ 
                time, 
                pid: chosen.pid, 
                name: chosen.name, 
                isIdle: false, 
                isPreemption, 
                color: chosen.color, 
                snapshot: procs.map(p => ({...p})) 
            });
            time++;
        }
        return steps;
    }

    start() {
        if (this.processes.length === 0) return;
        this.quantum = parseInt(document.getElementById('quantum').value) || 3;
        this.isSimulating = true;
        this.isPaused = false;
        this.simIndex = 0;
        this.loggedStarted = [];
        this.loggedFinished = [];
        this.simSteps = this.buildSteps(this.selectedAlgo, this.processes, this.quantum);
        
        document.getElementById('simStatus').innerText = "Running";
        document.getElementById('playbackControls').style.display = 'block';
        document.getElementById('runSimulationBtn').disabled = true;
        document.getElementById('systemLog').innerHTML = '';
        this.addLog(`Simulation started using ${this.selectedAlgo} algorithm.`);

        const ganttLiveRow = document.getElementById('ganttLiveRow');
        const ganttTimeRow = document.getElementById('ganttTimeRow');
        if (ganttLiveRow) ganttLiveRow.innerHTML = '';
        if (ganttTimeRow) ganttTimeRow.innerHTML = '';

        if (this.simTimer) clearInterval(this.simTimer);
        this.simTimer = setInterval(() => this.tick(), this.simulationSpeed);
    }

    tick() {
        if (this.isPaused) return;
        if (this.simIndex >= this.simSteps.length) {
            this.finish();
            return;
        }
        this.applyStep(this.simSteps[this.simIndex]);
        this.simIndex++;
    }

    applyStep(step) {
        if (!step) return;
        const { time, pid, name, isIdle, isPreemption, color, snapshot } = step;
        
        document.getElementById('simTimeDisplay').innerText = time;
        if (isPreemption) {
            const flash = document.getElementById('preemptFlash');
            if (flash) {
                flash.classList.add('flashing');
                setTimeout(() => flash.classList.remove('flashing'), 600);
            }
            this.addLog(`Context Switch: Preempted for ${isIdle ? 'IDLE' : name}`, 'warn');
        }

        const cpuSlot = document.getElementById('activeCpuSlot');
        if (cpuSlot) {
            if (isIdle) {
                cpuSlot.classList.remove('occupied');
                cpuSlot.innerHTML = `<div class="cpu-placeholder">SYSTEM IDLE</div>`;
            } else {
                cpuSlot.classList.add('occupied');
                cpuSlot.style.borderColor = color;
                cpuSlot.innerHTML = `
                <div style="display:flex; flex-direction:column; align-items:center; z-index:2;">
                    <div class="qn-pid-badge" style="margin-bottom:4px; opacity:0.8; font-size:0.5rem;">CORE_LOAD_ACTIVE</div>
                    <div class="qn-name" style="font-size:1.1rem; font-weight:800; color:var(--text-primary); text-shadow:0 0 10px ${color}44">${name}</div>
                    <div style="font-family:'JetBrains Mono'; font-size:0.55rem; color:${color}; letter-spacing:2px; font-weight:700; margin-top:2px;">EXECUTING_P${pid}</div>
                </div>
            `;
            }
        }

        const uiQueue = document.getElementById('readyQueueDisplay');
        if (uiQueue) {
            uiQueue.innerHTML = '';
            snapshot.filter(p => p.status === 'READY').forEach(p => {
                const node = document.createElement('div');
                node.className = 'queue-node-mini';
                node.style.borderLeftColor = p.color;
                const progress = (p.rem / p.burst) * 100;
                node.innerHTML = `
                    <div class="qn-top">
                        <div class="qn-name">${p.name}</div>
                        <div class="qn-pid-badge">ID: ${p.pid}</div>
                    </div>
                    <div class="qn-progress-container">
                        <div class="qn-progress-bar" style="width: ${progress}%; background: ${p.color}"></div>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px;">
                        <div class="qn-meta">REM: ${p.rem}ms</div>
                        <div class="qn-percent">${Math.round(progress)}%</div>
                    </div>
                `;
                uiQueue.appendChild(node);
            });
        }

        const ganttLiveRow = document.getElementById('ganttLiveRow');
        if (ganttLiveRow) {
            const lastBlock = ganttLiveRow.lastElementChild;
            const UNIT = 25;

            if (lastBlock && lastBlock.dataset.pid == pid) {
                let currentWidth = parseInt(lastBlock.style.width);
                lastBlock.style.width = (currentWidth + UNIT) + 'px';
            } else {
                const block = document.createElement('div');
                block.className = 'gantt-block' + (isIdle ? ' idle-block' : '');
                block.dataset.pid = pid;
                block.style.width = UNIT + 'px';
                if (!isIdle) block.style.backgroundColor = color;
                block.innerHTML = `<span class="pid" style="font-size:0.7rem">${isIdle ? '' : 'P'+pid}</span>`;
                ganttLiveRow.appendChild(block);

                const timeRow = document.getElementById('ganttTimeRow');
                if (timeRow) {
                    const marker = document.createElement('span');
                    marker.className = 'time-marker';
                    marker.textContent = time;
                    let offset = 0;
                    Array.from(ganttLiveRow.children).slice(0,-1).forEach(c => offset += parseInt(c.style.width));
                    marker.style.left = offset + 'px';
                    timeRow.appendChild(marker);
                }
            }
            ganttLiveRow.parentElement.scrollLeft = ganttLiveRow.parentElement.scrollWidth;
        }

        const tableBody = document.getElementById('processTableBody');
        if (tableBody) {
            tableBody.innerHTML = '';
            snapshot.forEach(p => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>#${p.pid}</td>
                    <td>${p.name}</td>
                    <td>${p.arrival}ms</td>
                    <td>${p.burst}ms</td>
                    <td><span class="status-pill status-${p.status.toLowerCase()}">${p.status}</span></td>
                    <td>${p.wt}/${p.tat}</td>
                `;
                tableBody.appendChild(row);
            });
        }

        document.querySelectorAll('.state-node-box').forEach(node => node.classList.remove('active'));
        document.querySelectorAll('.cabinet-link').forEach(link => link.classList.remove('active'));
        
        // 1. Process Heatmap
        if (snapshot.some(p => p.status === 'NEW')) document.getElementById('node-NEW')?.classList.add('active');
        if (snapshot.some(p => p.status === 'READY')) document.getElementById('node-READY')?.classList.add('active');
        if (!isIdle) document.getElementById('node-RUNNING')?.classList.add('active');
        if (snapshot.some(p => p.status === 'TERMINATED')) document.getElementById('node-TERMINATED')?.classList.add('active');

        // 2. Active Path Highlighting
        if (!isIdle) {
            document.getElementById('path-READY-RUNNING')?.classList.add('active');
            const finishingP = snapshot.find(p => p.pid === pid && p.rem === 0);
            if (finishingP) document.getElementById('path-RUNNING-TERMINATED')?.classList.add('active');
        }

        if (snapshot.some(p => p.arrival === time)) {
            document.getElementById('path-NEW-READY')?.classList.add('active');
        }

        if (isPreemption) {
            document.getElementById('path-PREEMPT')?.classList.add('active');
        }

        const total = snapshot.length;
        const doneProcs = snapshot.filter(p => p.done);
        const done = doneProcs.length;
        const avgWt = snapshot.reduce((s,p) => s + p.wt, 0) / (total || 1);
        const avgTat = snapshot.reduce((s,p) => s + p.tat, 0) / (total || 1);
        
        document.getElementById('statTotal').innerText = `${done}/${total}`;
        document.getElementById('statWait').innerText = avgWt.toFixed(1) + "ms";
        document.getElementById('statTAT').innerText = avgTat.toFixed(1) + "ms";
        document.getElementById('statCPU').innerText = (time > 0 ? (snapshot.reduce((s,p) => s + (p.burst - p.rem), 0)/time*100).toFixed(1) : 0) + "%";

        if (!isIdle) {
            const currentP = snapshot.find(p => p.pid === pid);
            if (currentP) {
                if (currentP.rem === 0 && !this.loggedFinished.includes(pid)) {
                    this.addLog(`Process ${name} (P${pid}) completed.`, 'success', time + 1);
                    this.loggedFinished.push(pid);
                }
                if (currentP.rem === currentP.burst - 1 && !this.loggedStarted.includes(pid)) {
                    this.addLog(`Process ${name} (P${pid}) started on CPU.`, 'info', time);
                    this.loggedStarted.push(pid);
                }
            }
        }
    }

    refreshUI() {
        const tableBody = document.getElementById('processTableBody');
        if (!tableBody) return;
        tableBody.innerHTML = '';
        this.processes.forEach(p => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>#${p.pid}</td>
                <td>${p.name}</td>
                <td>${p.arrival}ms</td>
                <td>${p.burst}ms</td>
                <td><span class="status-pill status-${p.status.toLowerCase()}">${p.status}</span></td>
                <td>${p.wt}/${p.tat}</td>
            `;
            tableBody.appendChild(row);
        });

        const statTotal = document.getElementById('statTotal');
        if (statTotal) statTotal.innerText = `0/${this.processes.length}`;
        const statCPU = document.getElementById('statCPU');
        if (statCPU) statCPU.innerText = "0%";
    }

    addLog(msg, type = 'info', forceTime = null) {
        const logDisplay = document.getElementById('systemLog');
        if (!logDisplay) return;
        const div = document.createElement('div');
        div.className = 'log-entry';
        
        let t = 0;
        if (forceTime !== null) {
            t = forceTime;
        } else if (this.simSteps && this.simSteps[this.simIndex]) {
            t = this.simSteps[this.simIndex].time;
        }
        
        if (type === 'warn') div.style.color = 'var(--accent-secondary)';
        if (type === 'success') div.style.color = 'var(--accent-primary)';
        
        div.innerHTML = `<span class="log-time">[${t}ms]</span> ${msg}`;
        logDisplay.appendChild(div);
        logDisplay.scrollTop = logDisplay.scrollHeight;
    }

    finish() {
        clearInterval(this.simTimer);
        this.isSimulating = false;
        document.getElementById('simStatus').innerText = "Finished";
        document.getElementById('runSimulationBtn').disabled = false;
        this.addLog("Simulation completed successfully.");
        
        if (this.simSteps.length > 0) {
            const finalSnapshot = this.simSteps[this.simSteps.length - 1].snapshot;
            this.updateAnalytics(finalSnapshot);
        }
    }

    updateAnalytics(procs) {
        const canvas = document.getElementById('performanceChart');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (window.perfChartInstance) window.perfChartInstance.destroy();
        window.perfChartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: procs.map(p => p.name),
                datasets: [
                    { label: 'Wait Time', data: procs.map(p => p.wt), backgroundColor: '#d2b48c' },
                    { label: 'Turnaround', data: procs.map(p => p.tat), backgroundColor: '#a0522d' }
                ]
            },
            options: { 
                responsive: true, 
                maintainAspectRatio: false,
                scales: { 
                    y: { beginAtZero: true, grid: { color: '#cccccc' } },
                    x: { grid: { display: false } }
                },
                plugins: { legend: { labels: { color: '#555555', font: { family: 'Times New Roman' } } } }
            }
        });
    }

    compareAll() {
        if (this.processes.length === 0) {
            const resultsDiv = document.getElementById('comparisonResults');
            if (resultsDiv) resultsDiv.innerHTML = '<div class="empty-state">No processes to compare.</div>';
            return;
        }

        const quantum = parseInt(document.getElementById('quantum').value) || 3;
        const algos = [
            { id: 'FCFS', name: 'FCFS' },
            { id: 'SJF', name: 'SJF' },
            { id: 'SRTN', name: 'SRTF' },
            { id: 'Round Robin', name: 'Round Robin' },
            { id: 'Priority', name: 'Priority' },
            { id: 'Priority_P', name: 'Priority (P)' },
            { id: 'MLQ', name: 'MLQ' }
        ];

        let results = algos.map(a => {
            const steps = this.buildSteps(a.id, this.processes, quantum);
            if (steps.length === 0) return { name: a.name, avgWt: 0, avgTat: 0 };
            const final = steps[steps.length - 1].snapshot;
            const avgWt = final.reduce((s, p) => s + p.wt, 0) / (final.length || 1);
            const avgTat = final.reduce((s, p) => s + p.tat, 0) / (final.length || 1);
            return { name: a.name, avgWt, avgTat };
        });

        // Rank by best wait time
        results.sort((a,b) => a.avgWt - b.avgWt);

        const bestWt = Math.min(...results.map(r => r.avgWt));
        const maxVal = Math.max(...results.map(r => Math.max(r.avgWt, r.avgTat)), 1);

        const container = document.getElementById('comparisonResults');
        if (container) {
            container.innerHTML = `
                <div class="comparison-grid">
                    ${results.map((res, idx) => `
                        <div class="comp-box ${res.avgWt === bestWt ? 'rank-1' : ''}">
                            <div class="comp-header">
                                <span class="comp-algo-name">
                                    ${res.avgWt === bestWt ? '🥇' : '💿'} ${res.name}
                                    ${res.avgWt === bestWt ? '<span class="best-badge">#1 RANKED</span>' : ''}
                                </span>
                                <span class="comp-metric-label">Efficiency: <span class="comp-metric-value">${(100 - (res.avgWt/maxVal*100)).toFixed(0)}%</span></span>
                            </div>
                            <div class="comp-bar-stack">
                                <div class="comp-bar-layer">
                                    <div class="comp-layer-info">
                                        <span>Avg Wait Time</span>
                                        <span>${res.avgWt.toFixed(1)}ms</span>
                                    </div>
                                    <div class="comp-bar-bg">
                                        <div class="comp-bar-fill" style="width: ${(res.avgWt / maxVal * 100)}%; background: var(--accent-secondary)"></div>
                                    </div>
                                </div>
                                <div class="comp-bar-layer">
                                    <div class="comp-layer-info">
                                        <span>Avg Turnaround</span>
                                        <span>${res.avgTat.toFixed(1)}ms</span>
                                    </div>
                                    <div class="comp-bar-bg">
                                        <div class="comp-bar-fill" style="width: ${(res.avgTat / maxVal * 100)}%; background: var(--accent-primary)"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        }
    }

    reset() {
        clearInterval(this.simTimer);
        this.isSimulating = false;
        this.isPaused = false;
        this.simIndex = 0;
        this.simSteps = [];
        this.loggedStarted = [];
        this.loggedFinished = [];
        document.getElementById('simStatus').innerText = "Idle";
        document.getElementById('simTimeDisplay').innerText = "0";
        document.getElementById('statCPU').innerText = "0%";
        
        const ganttLiveRow = document.getElementById('ganttLiveRow');
        if (ganttLiveRow) ganttLiveRow.innerHTML = '';
        const ganttTimeRow = document.getElementById('ganttTimeRow');
        if (ganttTimeRow) ganttTimeRow.innerHTML = '';
        
        document.querySelectorAll('.state-node-box').forEach(node => node.classList.remove('active'));
        document.querySelectorAll('.cabinet-link').forEach(link => link.classList.remove('active'));
        
        document.getElementById('systemLog').innerHTML = '<div class="log-entry">System reset.</div>';
        document.getElementById('playbackControls').style.display = 'none';
        document.getElementById('runSimulationBtn').disabled = false;
        this.refreshUI();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const scheduler = new Scheduler();
    scheduler.refreshUI();

    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            const view = document.getElementById(btn.dataset.view + 'View');
            if (view) view.classList.add('active');
        };
    });

    document.querySelectorAll('.algo-btn').forEach(btn => {
        btn.onclick = () => {
            if (scheduler.isSimulating) return;
            document.querySelectorAll('.algo-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            scheduler.selectedAlgo = btn.dataset.algo;
            document.getElementById('activeAlgo').innerText = btn.innerText;
            const rr = document.getElementById('rrSettings');
            if (rr) rr.style.display = (btn.dataset.algo === 'Round Robin') ? 'block' : 'none';
        };
    });

    document.getElementById('addProcessBtn').onclick = () => {
        const name = document.getElementById('pName').value;
        const arrival = document.getElementById('pArrival').value;
        const burst = document.getElementById('pBurst').value;
        const priority = document.getElementById('pPriority').value;
        const ql = document.getElementById('pQueue').value;
        scheduler.addProcess(name, arrival, burst, priority, ql);
        scheduler.addLog("Added Process " + (name || ("P" + (scheduler.nextPid - 1))));
        scheduler.refreshUI();
    };

    document.getElementById('loadSampleBtn').onclick = () => scheduler.loadSampleData();

    document.getElementById('runSimulationBtn').onclick = () => scheduler.start();
    document.getElementById('resetBtn').onclick = () => scheduler.reset();
    document.getElementById('compareAlgosBtn').onclick = () => {
        scheduler.compareAll();
        const tab = document.querySelector('[data-view="analytics"]');
        if (tab) tab.click();
    };

    document.getElementById('pauseResumeBtn').onclick = (e) => {
        scheduler.isPaused = !scheduler.isPaused;
        e.target.innerText = scheduler.isPaused ? 'Resume' : 'Pause';
    };

    document.getElementById('nextBtn').onclick = () => {
        if (scheduler.isPaused && scheduler.simIndex < scheduler.simSteps.length) {
            scheduler.applyStep(scheduler.simSteps[scheduler.simIndex]);
            scheduler.simIndex++;
        }
    };

    document.getElementById('prevBtn').onclick = () => {
        if (scheduler.isPaused && scheduler.simIndex > 1) {
            scheduler.simIndex -= 2;
            const gantt = document.getElementById('ganttLiveRow');
            const times = document.getElementById('ganttTimeRow');
            if (gantt) gantt.innerHTML = '';
            if (times) times.innerHTML = '';
            
            const targetIdx = scheduler.simIndex;
            scheduler.simIndex = 0;
            scheduler.loggedStarted = [];
            scheduler.loggedFinished = [];
            for (let i = 0; i <= targetIdx; i++) {
                scheduler.applyStep(scheduler.simSteps[i]);
                scheduler.simIndex = i + 1;
            }
        }
    };

    const speedSlider = document.getElementById('speedSlider');
    if (speedSlider) {
        speedSlider.oninput = () => {
            const val = parseInt(speedSlider.value);
            scheduler.simulationSpeed = 1010 - val;
            const sVal = document.getElementById('speedVal');
            if (sVal) sVal.innerText = val;
            if (scheduler.isSimulating && !scheduler.isPaused) {
                clearInterval(scheduler.simTimer);
                scheduler.simTimer = setInterval(() => scheduler.tick(), scheduler.simulationSpeed);
            }
        };
    }
});
