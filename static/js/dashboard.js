let historyChartInstance = null;
let effectivenessChartInstance = null;

function formatChartDate(dateStr) {
    if (!dateStr) return '';
    const parts = dateStr.split('-');
    if (parts.length !== 3) return dateStr;
    const monthIndex = parseInt(parts[1], 10) - 1;
    const day = parseInt(parts[2], 10);
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    if (monthIndex >= 0 && monthIndex < 12) {
        return `${months[monthIndex]} ${day}`;
    }
    return dateStr;
}

function formatChartDateLong(dateStr) {
    if (!dateStr) return '';
    const parts = dateStr.split('-');
    if (parts.length !== 3) return dateStr;
    const year = parts[0];
    const monthIndex = parseInt(parts[1], 10) - 1;
    const day = parseInt(parts[2], 10);
    const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    if (monthIndex >= 0 && monthIndex < 12) {
        return `${months[monthIndex]} ${day}, ${year}`;
    }
    return dateStr;
}

function formatPower(watts) {
    const absWatts = Math.abs(watts);
    if (absWatts >= 1000000) return (watts / 1000000).toFixed(2) + ' MW';
    if (absWatts >= 1000) return (watts / 1000).toFixed(2) + ' kW';
    return watts.toFixed(0) + ' W';
}

function calculateLinearRegression(x, y) {
    const n = x.length;
    if (n === 0) return [];
    
    let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
    for (let i = 0; i < n; i++) {
        sumX += x[i];
        sumY += y[i];
        sumXY += x[i] * y[i];
        sumXX += x[i] * x[i];
    }
    
    const denominator = (n * sumXX - sumX * sumX);
    if (denominator === 0) {
        return y;
    }
    const slope = (n * sumXY - sumX * sumY) / denominator;
    const intercept = (sumY - slope * sumX) / n;
    
    return x.map(val => slope * val + intercept);
}

function renderHistoryChart(data) {
    const canvas = document.getElementById('historyChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    if (historyChartInstance) {
        historyChartInstance.destroy();
    }
    
    // Limit chart data to the last 14 days
    const chartData = data.slice(-14);
    
    const dates = chartData.map(d => formatChartDate(d.date));
    const productions = chartData.map(d => d.production_kwh);
    const exports = chartData.map(d => d.export_kwh);
    const imports = chartData.map(d => d.import_kwh);
    const consumptions = chartData.map(d => d.consumption_kwh);
    
    historyChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'Solar Production (kWh)',
                    data: productions,
                    backgroundColor: 'rgba(16, 185, 129, 0.7)',
                    borderColor: '#10b981',
                    borderWidth: 1
                },
                {
                    label: 'Grid Export (kWh)',
                    data: exports,
                    backgroundColor: 'rgba(79, 70, 229, 0.7)',
                    borderColor: '#4f46e5',
                    borderWidth: 1
                },
                {
                    label: 'Grid Import (kWh)',
                    data: imports,
                    backgroundColor: 'rgba(239, 68, 68, 0.7)',
                    borderColor: '#ef4444',
                    borderWidth: 1
                },
                {
                    label: 'House Consumption (kWh)',
                    data: consumptions,
                    backgroundColor: 'rgba(71, 85, 105, 0.7)',
                    borderColor: '#475569',
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Energy (kWh)'
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        boxWidth: 12
                    }
                },
                tooltip: {
                    callbacks: {
                        title: function(context) {
                            const dataIndex = context[0].dataIndex;
                            if (chartData[dataIndex]) {
                                return formatChartDateLong(chartData[dataIndex].date);
                            }
                            return context[0].label;
                        },
                        afterBody: function(items) {
                            const dataIndex = items[0].dataIndex;
                            if (chartData[dataIndex] && chartData[dataIndex].is_interpolated) {
                                return '\n* Estimated data due to server downtime';
                            }
                            return '';
                        }
                    }
                }
            }
        }
    });
}

function renderEffectivenessChart(data) {
    const canvas = document.getElementById('effectivenessChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    if (effectivenessChartInstance) {
        effectivenessChartInstance.destroy();
    }
    
    // Limit chart data to the last 14 days
    const chartData = data.slice(-14);
    
    const dates = chartData.map(d => formatChartDate(d.date));
    const productions = chartData.map(d => d.production_kwh);
    const imports = chartData.map(d => d.import_kwh);
    
    const effectiveness = chartData.map(d => {
        const cons = d.consumption_kwh;
        if (cons <= 0) return 0;
        return (d.production_kwh / cons) * 100;
    });

    const indices = effectiveness.map((_, idx) => idx);
    const trendValues = calculateLinearRegression(indices, effectiveness);
    
    effectivenessChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'Solar Production (kWh)',
                    type: 'bar',
                    data: productions,
                    backgroundColor: 'rgba(16, 185, 129, 0.15)',
                    borderColor: '#10b981',
                    borderWidth: 1.5,
                    yAxisID: 'y'
                },
                {
                    label: 'Grid Import (kWh)',
                    type: 'bar',
                    data: imports,
                    backgroundColor: 'rgba(239, 68, 68, 0.15)',
                    borderColor: '#ef4444',
                    borderWidth: 1.5,
                    yAxisID: 'y'
                },
                {
                    label: 'Solar Effectiveness (%)',
                    type: 'line',
                    data: effectiveness,
                    borderColor: '#8b5cf6',
                    backgroundColor: 'rgba(139, 92, 246, 0.05)',
                    borderWidth: 3,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    tension: 0.3,
                    yAxisID: 'y1'
                },
                {
                    label: 'Effectiveness Trend Line',
                    type: 'line',
                    data: trendValues,
                    borderColor: 'rgba(139, 92, 246, 0.6)',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    borderDash: [6, 6],
                    pointRadius: 0,
                    fill: false,
                    tension: 0,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Daily Energy (kWh)',
                        font: { weight: 'bold' }
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    beginAtZero: true,
                    max: Math.max(100, Math.ceil(Math.max(...effectiveness) / 50) * 50),
                    title: {
                        display: true,
                        text: 'Solar Effectiveness (%)',
                        font: { weight: 'bold' }
                    },
                    grid: {
                        drawOnChartArea: false
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        boxWidth: 12,
                        usePointStyle: true
                    }
                },
                tooltip: {
                    callbacks: {
                        title: function(context) {
                            const dataIndex = context[0].dataIndex;
                            if (chartData[dataIndex]) {
                                return formatChartDateLong(chartData[dataIndex].date);
                            }
                            return context[0].label;
                        },
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed.y !== null) {
                                if (context.datasetIndex < 2) {
                                    label += context.parsed.y.toFixed(2) + ' kWh';
                                } else {
                                    label += context.parsed.y.toFixed(1) + '%';
                                }
                            }
                            return label;
                        }
                    }
                }
            }
        }
    });
}

document.addEventListener('alpine:init', () => {
    Alpine.data('dashboard', () => ({
        activeTab: 'live-tab',
        refreshRate: 3000,
        
        // Live power state
        meters: [],
        prodPower: 0,
        gridPower: 0,
        consPower: 0,
        rawMeters: 'No data yet.',
        loadingMeters: false,
        
        // Summary state
        lifetimeSolar: '',
        lifetimeImported: '',
        lifetimeExported: '',
        lifetimeConsumed: '',
        netSolarOffset: '0.0%',
        rawSummary: 'No data yet.',
        loadingSummary: false,
        showEffectivenessChart: false,
        
        // History state
        historyLogs: [],
        rawHistory: 'No data yet.',
        loadingHistory: false,
        historyPage: 1,
        historyPageSize: 20,
        
        // Phases state
        phases: [],
        rawPhases: 'No data yet.',
        loadingPhases: false,
        
        // Health state
        healthSummary: {
            operating: 0,
            producing: 0,
            communicating: 0,
            total: 0
        },
        inverters: [],
        rawInventory: 'No data yet.',
        loadingHealth: false,
        
        // Connectivity state
        connectivity: null,
        rawConnectivity: 'No data yet.',
        loadingConnectivity: false,
        
        // Events state
        events: [],
        rawEvents: 'No data yet.',
        loadingEvents: false,
        
        // Timer for auto-refresh
        refreshTimer: null,
        
        init() {
            // Load initial tab from hash
            const hash = window.location.hash.replace('#', '');
            if (hash && ['live-tab', 'summary-tab', 'history-tab', 'phase-tab', 'health-tab', 'connectivity-tab', 'events-tab', 'specs-tab'].includes(hash)) {
                this.activeTab = hash;
            } else {
                this.activeTab = 'live-tab';
            }
            
            // Watch tab changes to load data and handle browser history
            this.$watch('activeTab', (newVal) => {
                window.location.hash = newVal;
                this.handleTabSwitch(newVal);
            });
            
            // Trigger load for the initial active tab
            this.handleTabSwitch(this.activeTab);
        },
        
        openTab(tabName) {
            this.activeTab = tabName;
        },
        
        handleTabSwitch(tabName) {
            // Manage refresh timers
            if (tabName === 'live-tab') {
                this.fetchMeters();
                this.updateRefreshInterval();
            } else {
                this.stopRefreshTimer();
            }
            
            // Trigger lazy loading
            this.triggerTabLoad(tabName);
        },
        
        triggerTabLoad(tabName) {
            if (tabName === 'summary-tab') this.fetchSummary();
            if (tabName === 'history-tab') this.fetchHistory();
            if (tabName === 'phase-tab') this.fetchPhases();
            if (tabName === 'health-tab') this.fetchHealth();
            if (tabName === 'connectivity-tab') this.fetchConnectivity();
            if (tabName === 'events-tab') this.fetchEvents();
        },
        
        updateRefreshInterval() {
            this.stopRefreshTimer();
            if (this.refreshRate > 0 && this.activeTab === 'live-tab') {
                this.refreshTimer = setInterval(() => this.fetchMeters(), this.refreshRate);
            }
        },
        
        stopRefreshTimer() {
            if (this.refreshTimer) {
                clearInterval(this.refreshTimer);
                this.refreshTimer = null;
            }
        },
        
        formatPower(watts) {
            return formatPower(watts);
        },
        
        formatDate(timestamp) {
            if (!timestamp) return 'Never';
            return new Date(timestamp * 1000).toLocaleString();
        },
        
        isOkState(val) {
            if (!val) return false;
            return ['connected', 'ok', 'configured', 'enabled'].includes(val.toLowerCase());
        },
        
        async fetchMeters() {
            this.loadingMeters = true;
            try {
                const res = await fetch('/api/meters');
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'API Error');
                
                this.rawMeters = JSON.stringify(data, null, 2);
                if (data.length >= 2) {
                    this.meters = data;
                    this.prodPower = data[0].activePower || 0;
                    this.gridPower = data[1].activePower || 0;
                    this.consPower = this.prodPower + this.gridPower;
                }
            } catch (err) {
                console.error('Fetch meters error:', err);
            } finally {
                this.loadingMeters = false;
            }
        },
        
        async fetchSummary() {
            this.loadingSummary = true;
            this.showEffectivenessChart = false;
            try {
                const [resMeters, resHistory] = await Promise.all([
                    fetch('/api/meters'),
                    fetch('/api/history/daily')
                ]);
                
                const data = await resMeters.json();
                if (!resMeters.ok) throw new Error(data.error || 'API Error fetching meters');

                this.rawSummary = JSON.stringify(data, null, 2);
                
                if (data.length >= 2) {
                    const lifetimeProduction = data[0].actEnergyDlvd || 0;
                    const lifetimeImport = data[1].actEnergyDlvd || 0;
                    const lifetimeExport = data[1].actEnergyRcvd || 0;
                    const lifetimeConsumption = lifetimeProduction - lifetimeExport + lifetimeImport;
                    
                    const formatEnergy = (wh) => {
                        if (wh >= 1000000) return (wh / 1000000).toFixed(2) + ' MWh';
                        if (wh >= 1000) return (wh / 1000).toFixed(2) + ' kWh';
                        return wh.toFixed(0) + ' Wh';
                    };
                    
                    this.lifetimeSolar = formatEnergy(lifetimeProduction);
                    this.lifetimeImported = formatEnergy(lifetimeImport);
                    this.lifetimeExported = formatEnergy(lifetimeExport);
                    this.lifetimeConsumed = formatEnergy(lifetimeConsumption);
                    this.netSolarOffset = lifetimeConsumption > 0 
                        ? ((lifetimeProduction / lifetimeConsumption) * 100).toFixed(1) + '%' 
                        : '100.0%';
                }

                if (resHistory.ok) {
                    const historyData = await resHistory.json();
                    if (historyData && historyData.length > 0) {
                        this.showEffectivenessChart = true;
                        this.$nextTick(() => {
                            renderEffectivenessChart(historyData);
                        });
                    }
                }
            } catch (err) {
                console.error('Fetch summary error:', err);
            } finally {
                this.loadingSummary = false;
            }
        },
        
        async fetchHistory() {
            this.loadingHistory = true;
            try {
                const res = await fetch('/api/history/daily');
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'API Error');
                
                this.historyPage = 1;
                this.historyLogs = data;
                this.rawHistory = JSON.stringify(data, null, 2);
                
                if (data.length > 0) {
                    this.$nextTick(() => {
                        renderHistoryChart(data);
                    });
                }
            } catch (err) {
                console.error('Fetch history error:', err);
            } finally {
                this.loadingHistory = false;
            }
        },
        
        async syncDatabase() {
            this.loadingHistory = true;
            try {
                const res = await fetch('/api/history/refresh', { method: 'POST' });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Sync Error');
                await this.fetchHistory();
            } catch (err) {
                console.error("Sync error:", err);
                alert("Failed to sync database: " + err.message);
                this.loadingHistory = false;
            }
        },
        
        async fetchPhases() {
            this.loadingPhases = true;
            try {
                const res = await fetch('/api/meters');
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'API Error');

                this.rawPhases = JSON.stringify(data, null, 2);
                this.phases = data.filter(m => m.eid !== 1023410688 && m.channels);
            } catch (err) {
                console.error('Fetch phases error:', err);
            } finally {
                this.loadingPhases = false;
            }
        },
        
        async fetchHealth() {
            this.loadingHealth = true;
            try {
                const res = await fetch('/api/inventory');
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'API Error');

                this.rawInventory = JSON.stringify(data, null, 2);
                const pcuGroup = data.find(g => g.type === 'PCU');
                if (!pcuGroup) throw new Error('No inverters found in inventory');

                this.inverters = pcuGroup.devices || [];
                this.healthSummary = {
                    total: this.inverters.length,
                    operating: this.inverters.filter(i => i.operating).length,
                    producing: this.inverters.filter(i => i.producing).length,
                    communicating: this.inverters.filter(i => i.communicating).length
                };
            } catch (err) {
                console.error('Fetch health error:', err);
            } finally {
                this.loadingHealth = false;
            }
        },
        
        get paginatedHistoryLogs() {
            const reversed = [...this.historyLogs].reverse();
            const start = (this.historyPage - 1) * this.historyPageSize;
            const end = start + this.historyPageSize;
            return reversed.slice(start, end);
        },
        
        get totalHistoryPages() {
            return Math.ceil(this.historyLogs.length / this.historyPageSize) || 1;
        },
        
        get visibleHistoryPages() {
            const pages = [];
            const total = this.totalHistoryPages;
            const current = this.historyPage;
            const range = 2;
            for (let i = 1; i <= total; i++) {
                if (i === 1 || i === total || (i >= current - range && i <= current + range)) {
                    pages.push(i);
                } else if (pages[pages.length - 1] !== '...') {
                    pages.push('...');
                }
            }
            return pages;
        },
        
        prevHistoryPage() {
            if (this.historyPage > 1) {
                this.historyPage--;
            }
        },
        
        nextHistoryPage() {
            if (this.historyPage < this.totalHistoryPages) {
                this.historyPage++;
            }
        },
        
        setHistoryPage(page) {
            if (page >= 1 && page <= this.totalHistoryPages) {
                this.historyPage = page;
            }
        },
        
        async fetchConnectivity() {
            this.loadingConnectivity = true;
            try {
                const res = await fetch('/api/connectivity');
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'API Error');

                this.rawConnectivity = JSON.stringify(data, null, 2);
                const conn = data.connection;
                this.connectivity = {
                    mqtt_state: conn.mqtt_state || 'unknown',
                    prov_state: conn.prov_state || 'unknown',
                    auth_state: conn.auth_state || 'unknown',
                    sc_stream: conn.sc_stream || 'unknown',
                    sc_debug: conn.sc_debug || 'unknown',
                    meters_last_update: data.meters?.last_update || null
                };
            } catch (err) {
                console.error('Fetch connectivity error:', err);
            } finally {
                this.loadingConnectivity = false;
            }
        },
        
        async fetchEvents() {
            this.loadingEvents = true;
            try {
                const res = await fetch('/api/events');
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'API Error');

                this.rawEvents = JSON.stringify(data, null, 2);
                this.events = data.alerts || [];
            } catch (err) {
                console.error('Fetch events error:', err);
            } finally {
                this.loadingEvents = false;
            }
        }
    }));
});
