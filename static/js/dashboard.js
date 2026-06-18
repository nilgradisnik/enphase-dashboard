let refreshTimer = null;

function updateRefreshInterval() {
    const rateInput = document.getElementById('refresh-rate');
    if (!rateInput) return;
    
    const rate = parseInt(rateInput.value);
    
    // Clear existing timer
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }

    // Set new timer if not Off and we are on the live tab
    if (rate > 0 && document.getElementById('live-tab').classList.contains('active')) {
        refreshTimer = setInterval(fetchMeters, rate);
    }
}

function formatPower(watts) {
    const absWatts = Math.abs(watts);
    if (absWatts >= 1000000) return (watts / 1000000).toFixed(2) + ' MW';
    if (absWatts >= 1000) return (watts / 1000).toFixed(2) + ' kW';
    return watts.toFixed(0) + ' W';
}

function openTab(evt, tabName) {
    const contents = document.getElementsByClassName("tab-content");
    for (let i = 0; i < contents.length; i++) contents[i].classList.remove("active");
    
    const buttons = document.getElementsByClassName("tab-btn");
    for (let i = 0; i < buttons.length; i++) buttons[i].classList.remove("active");
    
    const targetTab = document.getElementById(tabName);
    if (targetTab) {
        targetTab.classList.add("active");
    }
    
    // Handle button activation (via click or manual call)
    if (evt) {
        evt.currentTarget.classList.add("active");
    } else {
        // Try to find the button associated with this tabName
        const btn = Array.from(buttons).find(b => b.getAttribute('onclick') && b.getAttribute('onclick').includes(tabName));
        if (btn) btn.classList.add("active");
    }

    // Persist tab state in URL hash
    window.location.hash = tabName;

    // Manage refresh timer on tab switch
    if (tabName === 'live-tab') {
        updateRefreshInterval();
    } else if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }

    // Lazy load data for specific tabs
    const tabEl = document.getElementById(tabName);
    if (tabEl) {
        if (tabName === 'summary-tab' && document.getElementById('summary-data').querySelector('.loading')) {
            fetchSummary();
        }
        if (tabName === 'health-tab' && document.getElementById('health-data').querySelector('.loading')) {
            fetchHealth();
        }
        if (tabName === 'events-tab' && document.getElementById('events-data').querySelector('.loading')) {
            fetchEvents();
        }
        if (tabName === 'phase-tab' && document.getElementById('phase-data').querySelector('.loading')) {
            fetchPhases();
        }
        if (tabName === 'connectivity-tab' && document.getElementById('connectivity-data').querySelector('.loading')) {
            fetchConnectivity();
        }
    }
}

async function fetchMeters() {
    const rawPre = document.getElementById('raw-meters');
    
    try {
        const res = await fetch('/api/meters');
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'API Error');
        
        if (rawPre) rawPre.textContent = JSON.stringify(data, null, 2);
        
        if (data.length < 2) return;

        const prodPower = data[0].activePower || 0;
        const gridPower = data[1].activePower || 0;
        const consPower = prodPower + gridPower;

        // Update Production
        const valProd = document.getElementById('val-prod');
        if (valProd) valProd.textContent = formatPower(prodPower);

        // Update Grid
        const isExporting = gridPower < 0;
        const gridEl = document.getElementById('val-grid');
        const labelGrid = document.getElementById('label-grid');
        
        if (labelGrid && gridEl) {
            labelGrid.textContent = isExporting ? 'Exporting to Grid' : 'Importing from Grid';
            gridEl.textContent = formatPower(Math.abs(gridPower));
            gridEl.style.color = isExporting ? '#007bff' : '#dc3545';
        }

        // Update Consumption
        const valCons = document.getElementById('val-cons');
        if (valCons) valCons.textContent = formatPower(consPower);

    } catch (err) {
        console.error('Fetch error:', err);
    }
}

async function fetchSummary() {
    const target = document.getElementById('summary-data');
    const rawPre = document.getElementById('raw-summary');
    if (!target) return;
    target.innerHTML = '<p class="loading">Updating summary...</p>';
    
    try {
        const res = await fetch('/api/meters');
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'API Error');

        if (rawPre) rawPre.textContent = JSON.stringify(data, null, 2);
        
        if (data.length < 2) {
            target.innerHTML = '<p class="status-tag status-err">Error: Expected at least 2 meters for summary.</p>';
            return;
        }

        function formatEnergy(wh) {
            if (wh >= 1000000) return (wh / 1000000).toFixed(2) + ' MWh';
            if (wh >= 1000) return (wh / 1000).toFixed(2) + ' kWh';
            return wh.toFixed(0) + ' Wh';
        }

        const lifetimeProduction = data[0].actEnergyDlvd || 0;
        const lifetimeImport = data[1].actEnergyDlvd || 0;
        const lifetimeExport = data[1].actEnergyRcvd || 0;
        const lifetimeConsumption = lifetimeProduction - lifetimeExport + lifetimeImport;

        let html = '<div class="responsive-grid">';
        html += `
            <div class="data-box" style="margin-top: 0;">
                <h4 style="margin-top: 0; color: #28a745;">Lifetime Solar Production</h4>
                <p style="font-size: 1.1rem; margin-bottom: 0;">Total Generated: <strong>${formatEnergy(lifetimeProduction)}</strong></p>
            </div>
            <div class="data-box" style="margin-top: 0;">
                <h4 style="margin-top: 0; color: #007bff;">Grid Lifetime Totals</h4>
                <p style="font-size: 1.1rem; margin-bottom: 0;">
                    Total Imported: <strong style="color: #dc3545;">${formatEnergy(lifetimeImport)}</strong><br>
                    Total Exported: <strong style="color: #007bff;">${formatEnergy(lifetimeExport)}</strong>
                </p>
            </div>
            <div class="data-box" style="margin-top: 0; grid-column: span 2; background: #fff8f0; border: 1px solid #ff6600;">
                <h4 style="margin-top: 0; color: #ff6600;">House Lifetime Consumption</h4>
                <p style="font-size: 1.2rem; margin-bottom: 0;">Total Energy Used: <strong>${formatEnergy(lifetimeConsumption)}</strong></p>
            </div>
        `;
        html += '</div>';
        target.innerHTML = html;
    } catch (err) {
        target.innerHTML = `<p class="status-tag status-err">Error: ${err.message}</p>`;
    }
}

async function fetchPhases() {
    const target = document.getElementById('phase-data');
    const rawPre = document.getElementById('raw-phases');
    if (!target) return;
    target.innerHTML = '<p class="loading">Updating phase details...</p>';
    
    try {
        const res = await fetch('/api/meters');
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'API Error');

        if (rawPre) rawPre.textContent = JSON.stringify(data, null, 2);
        
        let html = '';
        data.forEach((meter, idx) => {
            if (meter.eid === 1023410688 || !meter.channels) return;
            const label = idx === 0 ? 'Production Meter' : 'Grid Meter';
            html += `<h3>${label}</h3>`;
            html += `<table style="width: 100%; border-collapse: collapse; margin-bottom: 1.5rem;">
                <tr style="border-bottom: 2px solid #eee; text-align: left;">
                    <th>Channel</th><th>Active Power</th><th>Voltage</th><th>Freq</th><th>Power Factor</th>
                </tr>`;
            meter.channels.forEach((ch, cidx) => {
                html += `<tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 0.5rem;">Phase ${cidx + 1}</td>
                    <td style="padding: 0.5rem;">${formatPower(ch.activePower || 0)}</td>
                    <td style="padding: 0.5rem;">${(ch.voltage || 0).toFixed(2)} V</td>
                    <td style="padding: 0.5rem;">${(ch.freq || 0).toFixed(2)} Hz</td>
                    <td style="padding: 0.5rem;">${(ch.pwrFactor || 0).toFixed(2)}</td>
                </tr>`;
            });
            html += '</table>';
        });
        target.innerHTML = html;
    } catch (err) {
        target.innerHTML = `<p class="status-tag status-err">Error: ${err.message}</p>`;
    }
}

async function fetchHealth() {
    const target = document.getElementById('health-data');
    const summary = document.getElementById('health-summary');
    const rawPre = document.getElementById('raw-inventory');
    if (!target) return;
    target.innerHTML = '<p class="loading">Updating inverter status...</p>';
    
    try {
        const res = await fetch('/api/inventory');
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'API Error');

        if (rawPre) rawPre.textContent = JSON.stringify(data, null, 2);
        const pcuGroup = data.find(g => g.type === 'PCU');
        if (!pcuGroup) throw new Error('No inverters found in inventory');

        const inverters = pcuGroup.devices;
        const total = inverters.length;
        const operating = inverters.filter(i => i.operating).length;
        const producing = inverters.filter(i => i.producing).length;
        const communicating = inverters.filter(i => i.communicating).length;

        if (summary) {
            summary.innerHTML = `
                <span class="status-tag ${operating === total ? 'status-ok' : 'status-err'}">Operating: ${operating}/${total}</span>
                <span class="status-tag ${producing === total ? 'status-ok' : 'status-err'}">Producing: ${producing}/${total}</span>
                <span class="status-tag ${communicating === total ? 'status-ok' : 'status-err'}">Communicating: ${communicating}/${total}</span>
            `;
        }

        let html = '';
        inverters.forEach(inv => {
            const statusClass = (inv.operating && inv.producing && inv.communicating) ? 'status-ok' : 'status-err';
            html += `
                <div style="border: 1px solid #eee; padding: 0.8rem; border-radius: 4px; background: white; font-size: 0.85rem;">
                    <div style="font-weight: bold; margin-bottom: 0.3rem;">SN: ${inv.serial_num}</div>
                    <div style="color: #666; margin-bottom: 0.5rem;">${inv.part_num}</div>
                    <div class="status-tag ${statusClass}" style="width: 100%; text-align: center; box-sizing: border-box;">
                        ${inv.operating ? 'ONLINE' : 'OFFLINE'}
                    </div>
                </div>
            `;
        });
        target.innerHTML = html;
    } catch (err) {
        target.innerHTML = `<p class="status-tag status-err">Error: ${err.message}</p>`;
    }
}

async function fetchConnectivity() {
    const target = document.getElementById('connectivity-data');
    const rawPre = document.getElementById('raw-connectivity');
    if (!target) return;
    target.innerHTML = '<p class="loading">Updating connectivity status...</p>';
    
    try {
        const res = await fetch('/api/connectivity');
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'API Error');

        if (rawPre) rawPre.textContent = JSON.stringify(data, null, 2);
        const conn = data.connection;
        const getStatusTag = (val) => {
            const ok = ['connected', 'ok', 'configured', 'enabled'].includes(val.toLowerCase());
            return `<span class="status-tag ${ok ? 'status-ok' : 'status-err'}">${val.toUpperCase()}</span>`;
        };

        let html = '<div class="responsive-grid">';
        html += `
            <div class="data-box" style="margin-top:0;">
                <p><strong>MQTT State:</strong> ${getStatusTag(conn.mqtt_state)}</p>
                <p><strong>Provisioning:</strong> ${getStatusTag(conn.prov_state)}</p>
                <p><strong>Auth State:</strong> ${getStatusTag(conn.auth_state)}</p>
            </div>
            <div class="data-box" style="margin-top:0;">
                <p><strong>Cloud Stream:</strong> ${getStatusTag(conn.sc_stream)}</p>
                <p><strong>Debug Stream:</strong> ${getStatusTag(conn.sc_debug)}</p>
                <p><strong>Last Meter Update:</strong> ${new Date(data.meters.last_update * 1000).toLocaleString()}</p>
            </div>
        `;
        html += '</div>';
        target.innerHTML = html;
    } catch (err) {
        target.innerHTML = `<p class="status-tag status-err">Error: ${err.message}</p>`;
    }
}

async function fetchEvents() {
    const target = document.getElementById('events-data');
    const rawPre = document.getElementById('raw-events');
    if (!target) return;
    target.innerHTML = '<p class="loading">Updating system alerts...</p>';
    
    try {
        const res = await fetch('/api/events');
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'API Error');

        if (rawPre) rawPre.textContent = JSON.stringify(data, null, 2);
        const alerts = data.alerts || [];
        if (alerts.length === 0) {
            target.innerHTML = '<p style="color: #28a745; font-weight: bold;">✓ No active system alerts.</p>';
            return;
        }

        let html = '<ul style="list-style: none; padding: 0;">';
        alerts.forEach(alert => {
            html += `
                <li style="padding: 1rem; border-bottom: 1px solid #eee; display: flex; align-items: center; gap: 10px;">
                    <span class="status-tag status-err">ALERT</span>
                    <span>${alert}</span>
                </li>
            `;
        });
        html += '</ul>';
        target.innerHTML = html;
    } catch (err) {
        target.innerHTML = `<p class="status-tag status-err">Error: ${err.message}</p>`;
    }
}

// Initial load
window.addEventListener('DOMContentLoaded', () => {
    // Check for hash in URL
    const hash = window.location.hash.substring(1); // remove #
    if (hash && document.getElementById(hash)) {
        openTab(null, hash);
    } else {
        // Default to live tab if no valid hash
        openTab(null, 'live-tab');
        fetchMeters();
        updateRefreshInterval();
    }
});
