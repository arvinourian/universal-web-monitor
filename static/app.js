document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const targetUrl = document.getElementById('targetUrl');
    const selectorType = document.getElementById('selectorType');
    const targetSelector = document.getElementById('targetSelector');
    const selectorLabel = document.getElementById('selectorLabel');
    const selectorInputGroup = document.getElementById('selectorInputGroup');
    const checkInterval = document.getElementById('checkInterval');
    const chkDesktop = document.getElementById('chkDesktop');
    const chkSound = document.getElementById('chkSound');
    const chkTelegram = document.getElementById('chkTelegram');
    const telegramConfigBox = document.getElementById('telegramConfigBox');
    const telegramToken = document.getElementById('telegramToken');
    const telegramChatId = document.getElementById('telegramChatId');
    
    // Buttons
    const btnTestSelector = document.getElementById('btnTestSelector');
    const btnTestTelegram = document.getElementById('btnTestTelegram');
    const btnStart = document.getElementById('btnStart');
    const btnStop = document.getElementById('btnStop');
    const btnClearLogs = document.getElementById('btnClearLogs');
    const btnCopyLogs = document.getElementById('btnCopyLogs');

    // Display & Stats
    const testResultBox = document.getElementById('testResultBox');
    const tgTestResult = document.getElementById('tgTestResult');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const liveValueDisplay = document.getElementById('liveValueDisplay');
    const statChecks = document.getElementById('statChecks');
    const statChanges = document.getElementById('statChanges');
    const statElapsed = document.getElementById('statElapsed');
    const lastCheckText = document.getElementById('lastCheckText');

    // Terminal
    const terminalWindow = document.getElementById('terminalWindow');
    const chkAutoScroll = document.getElementById('chkAutoScroll');
    const sseStatusDot = document.getElementById('sseStatusDot');
    const sseStatusText = document.getElementById('sseStatusText');
    const logCountText = document.getElementById('logCountText');

    let logCount = 0;
    let logEntries = [];
    let isRunning = false;
    let startTimestamp = null;
    let elapsedTimer = null;

    // 1. Selector Type Change Handler
    selectorType.addEventListener('change', () => {
        const type = selectorType.value;
        if (type === 'xpath') {
            selectorInputGroup.classList.remove('hidden');
            selectorLabel.innerText = 'XPath Expression';
            targetSelector.placeholder = '//*[@id="my-element"]/div/span';
        } else if (type === 'full_xpath') {
            selectorInputGroup.classList.remove('hidden');
            selectorLabel.innerText = 'Full XPath Expression';
            targetSelector.placeholder = '/html/body/div[1]/div[2]/div/span';
        } else if (type === 'css') {
            selectorInputGroup.classList.remove('hidden');
            selectorLabel.innerText = 'CSS Selector';
            targetSelector.placeholder = '#appointment-card .date-badge, div.firstAvailableDate';
        } else if (type === 'regex') {
            selectorInputGroup.classList.remove('hidden');
            selectorLabel.innerText = 'Regex Pattern';
            targetSelector.placeholder = 'firstAvailableDate">([0-9/]+)<';
        } else if (type === 'full_text') {
            selectorInputGroup.classList.add('hidden');
        }
    });

    // 2. Telegram Toggle Visibility
    chkTelegram.addEventListener('change', () => {
        if (chkTelegram.checked) {
            telegramConfigBox.classList.remove('hidden');
        } else {
            telegramConfigBox.classList.add('hidden');
        }
    });

    // 3. Test Selector Button
    btnTestSelector.addEventListener('click', async () => {
        const url = targetUrl.value.trim();
        const type = selectorType.value;
        const selector = targetSelector.value.trim();

        if (!url) {
            alert('Please enter a target website URL.');
            targetUrl.focus();
            return;
        }
        if (!selector && type !== 'full_text') {
            alert('Please enter a selector expression.');
            targetSelector.focus();
            return;
        }

        btnTestSelector.disabled = true;
        btnTestSelector.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin text-[10px]"></i><span>Extracting...</span>';
        testResultBox.className = 'mt-2 p-2.5 rounded-lg bg-zinc-950 border border-zinc-800 text-xs block text-zinc-400';
        testResultBox.innerText = 'Fetching webpage and extracting...';

        try {
            const resp = await fetch('/api/test-selector', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, selector_type: type, selector })
            });
            const data = await resp.json();

            if (data.success) {
                testResultBox.className = 'mt-2 p-2.5 rounded-lg bg-zinc-900/80 border border-emerald-900/50 text-xs block';
                testResultBox.innerHTML = `
                    <div class="text-[11px] text-emerald-400 font-medium mb-1">Extracted Value:</div>
                    <div class="font-mono text-zinc-200 bg-zinc-950 p-1.5 rounded border border-zinc-800 break-all">
                        ${escapeHtml(data.value)}
                    </div>
                `;
            } else {
                testResultBox.className = 'mt-2 p-2.5 rounded-lg bg-zinc-900/80 border border-rose-900/50 text-xs block text-rose-300';
                testResultBox.innerHTML = `
                    <div class="font-medium text-rose-400 mb-0.5">Extraction Failed</div>
                    <div class="text-[11px] text-rose-300/90">${escapeHtml(data.error)}</div>
                `;
            }
        } catch (err) {
            testResultBox.className = 'mt-2 p-2.5 rounded-lg bg-zinc-900/80 border border-rose-900/50 text-xs block text-rose-300';
            testResultBox.innerText = `Request error: ${err.message}`;
        } finally {
            btnTestSelector.disabled = false;
            btnTestSelector.innerHTML = '<i class="fa-solid fa-play text-[10px]"></i><span>Test Extraction</span>';
        }
    });

    // 4. Test Telegram Bot Connection
    btnTestTelegram.addEventListener('click', async () => {
        const botToken = telegramToken.value.trim();
        const chatId = telegramChatId.value.trim();

        if (!botToken) {
            alert('Please enter your Telegram Bot API Token.');
            telegramToken.focus();
            return;
        }

        btnTestTelegram.disabled = true;
        btnTestTelegram.innerText = 'Testing connection...';
        tgTestResult.className = 'text-xs p-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-400 block mt-2';
        tgTestResult.innerText = 'Checking bot on Telegram...';

        try {
            const resp = await fetch('/api/test-telegram', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bot_token: botToken, chat_id: chatId })
            });
            const data = await resp.json();

            if (data.success) {
                tgTestResult.className = 'text-xs p-2 rounded-lg bg-zinc-900/80 text-emerald-300 border border-emerald-900/50 block mt-2';
                tgTestResult.innerText = data.message;
                if (data.chat_id) {
                    telegramChatId.value = data.chat_id;
                }
            } else {
                tgTestResult.className = 'text-xs p-2 rounded-lg bg-zinc-900/80 text-rose-300 border border-rose-900/50 block mt-2 text-[11px]';
                tgTestResult.innerText = data.error;
            }
        } catch (err) {
            tgTestResult.className = 'text-xs p-2 rounded-lg bg-zinc-900/80 text-rose-300 border border-rose-900/50 block mt-2 text-[11px]';
            tgTestResult.innerText = `Request error: ${err.message}`;
        } finally {
            btnTestTelegram.disabled = false;
            btnTestTelegram.innerText = 'Test Bot Connection';
        }
    });

    // 5. Start Monitoring
    btnStart.addEventListener('click', async () => {
        const url = targetUrl.value.trim();
        const type = selectorType.value;
        const selector = targetSelector.value.trim();
        const interval = parseInt(checkInterval.value) || 30;

        if (!url) {
            alert('Please enter a target URL.');
            targetUrl.focus();
            return;
        }
        if (!selector && type !== 'full_text') {
            alert('Please enter a selector.');
            targetSelector.focus();
            return;
        }

        const payload = {
            url,
            selector_type: type,
            selector,
            interval,
            enable_desktop_notifications: chkDesktop.checked,
            enable_sound: chkSound.checked,
            enable_telegram: chkTelegram.checked,
            telegram_bot_token: telegramToken.value.trim(),
            telegram_chat_id: telegramChatId.value.trim()
        };

        btnStart.disabled = true;

        try {
            const resp = await fetch('/api/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await resp.json();

            if (data.success) {
                setRunningState(true, data.start_time);
            } else {
                alert('Failed to start monitor: ' + data.error);
                btnStart.disabled = false;
            }
        } catch (err) {
            alert('Error starting monitor: ' + err.message);
            btnStart.disabled = false;
        }
    });

    // 6. Stop Monitoring
    btnStop.addEventListener('click', async () => {
        btnStop.disabled = true;
        try {
            const resp = await fetch('/api/stop', { method: 'POST' });
            const data = await resp.json();
            if (data.success) {
                setRunningState(false);
            }
        } catch (err) {
            alert('Error stopping monitor: ' + err.message);
        } finally {
            btnStop.disabled = false;
        }
    });

    function setRunningState(running, startTime = null) {
        isRunning = running;
        if (running) {
            btnStart.disabled = true;
            btnStop.disabled = false;
            targetUrl.disabled = true;
            selectorType.disabled = true;
            targetSelector.disabled = true;
            checkInterval.disabled = true;

            statusDot.className = 'w-2 h-2 rounded-full bg-emerald-500 animate-pulse';
            statusText.innerText = 'Monitoring';
            statusText.className = 'text-emerald-400 font-medium';

            startTimestamp = startTime ? new Date(startTime.replace(' ', 'T')) : new Date();
            clearInterval(elapsedTimer);
            elapsedTimer = setInterval(updateElapsedTime, 1000);
        } else {
            btnStart.disabled = false;
            btnStop.disabled = true;
            targetUrl.disabled = false;
            selectorType.disabled = false;
            targetSelector.disabled = false;
            checkInterval.disabled = false;

            statusDot.className = 'w-2 h-2 rounded-full bg-zinc-600';
            statusText.innerText = 'Idle';
            statusText.className = 'text-zinc-400 font-medium';

            clearInterval(elapsedTimer);
        }
    }

    function updateElapsedTime() {
        if (!startTimestamp) return;
        const now = new Date();
        const diff = Math.floor((now - startTimestamp) / 1000);
        if (diff < 0) return;
        const hrs = String(Math.floor(diff / 3600)).padStart(2, '0');
        const mins = String(Math.floor((diff % 3600) / 60)).padStart(2, '0');
        const secs = String(diff % 60).padStart(2, '0');
        statElapsed.innerText = `${hrs}:${mins}:${secs}`;
    }

    // 7. Server-Sent Events (SSE) Live Log Stream
    function initSSE() {
        const evtSource = new EventSource('/api/logs/stream');

        evtSource.onopen = () => {
            sseStatusDot.className = 'w-1.5 h-1.5 rounded-full bg-emerald-500';
            sseStatusText.innerText = 'Connected';
        };

        evtSource.onmessage = (e) => {
            if (!e.data || e.data.trim() === '') return;
            try {
                const log = JSON.parse(e.data);
                appendLogEntry(log);
            } catch (err) {
                console.error('SSE parse error:', err);
            }
        };

        evtSource.onerror = () => {
            sseStatusDot.className = 'w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse';
            sseStatusText.innerText = 'Reconnecting...';
        };
    }

    function appendLogEntry(log) {
        logCount++;
        logEntries.push(log);
        logCountText.innerText = `${logCount} entries`;

        // Update metric values
        if (log.details && log.details.value) {
            liveValueDisplay.innerText = log.details.value;
        }
        if (log.details && log.details.new) {
            liveValueDisplay.innerText = log.details.new;
        }
        if (log.level === 'alert') {
            const currentChanges = parseInt(statChanges.innerText) || 0;
            statChanges.innerText = currentChanges + 1;
        }
        if (log.message && log.message.includes('Check #')) {
            const match = log.message.match(/Check #(\d+)/);
            if (match) {
                statChecks.innerText = match[1];
            }
        }
        lastCheckText.innerText = `${log.timestamp}`;

        // Create log line
        const line = document.createElement('div');
        line.className = 'flex items-start space-x-2 py-0.5 leading-relaxed';

        let badgeColor = 'text-zinc-400';
        let msgColor = 'text-zinc-300';

        if (log.level === 'info') {
            badgeColor = 'text-zinc-500';
            msgColor = 'text-zinc-300';
        } else if (log.level === 'success') {
            badgeColor = 'text-emerald-400';
            msgColor = 'text-zinc-200';
        } else if (log.level === 'warning') {
            badgeColor = 'text-amber-400';
            msgColor = 'text-amber-200/90';
        } else if (log.level === 'alert') {
            badgeColor = 'text-rose-400 font-bold';
            msgColor = 'text-rose-300 font-medium';
        } else if (log.level === 'error') {
            badgeColor = 'text-rose-500';
            msgColor = 'text-rose-300';
        }

        const timeOnly = log.timestamp.split(' ')[1] || log.timestamp;

        line.innerHTML = `
            <span class="text-zinc-600 select-none">${timeOnly}</span>
            <span class="${badgeColor} text-[11px] font-mono">[${log.level.toUpperCase()}]</span>
            <span class="${msgColor} flex-1 break-all">${escapeHtml(log.message)}</span>
        `;

        terminalWindow.appendChild(line);

        if (chkAutoScroll.checked) {
            terminalWindow.scrollTop = terminalWindow.scrollHeight;
        }
    }

    // 8. Clear & Copy Logs
    btnClearLogs.addEventListener('click', async () => {
        terminalWindow.innerHTML = '<div class="text-zinc-600">Console logs cleared.</div>';
        logCount = 0;
        logEntries = [];
        logCountText.innerText = '0 entries';
        try {
            await fetch('/api/logs/clear', { method: 'POST' });
        } catch (e) {}
    });

    btnCopyLogs.addEventListener('click', () => {
        if (logEntries.length === 0) return;
        const text = logEntries.map(l => `[${l.timestamp}] [${l.level.toUpperCase()}] ${l.message}`).join('\n');
        navigator.clipboard.writeText(text).then(() => {
            btnCopyLogs.innerText = 'Copied!';
            setTimeout(() => { btnCopyLogs.innerText = 'Copy'; }, 1500);
        });
    });

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // Check backend status on page load
    async function checkInitialStatus() {
        try {
            const resp = await fetch('/api/status');
            const data = await resp.json();
            if (data.is_running) {
                setRunningState(true, data.start_time);
                if (data.last_value) {
                    liveValueDisplay.innerText = data.last_value;
                }
                statChecks.innerText = data.check_count || 0;
                statChanges.innerText = data.change_count || 0;
            }
        } catch (e) {}
    }

    // Initialize
    initSSE();
    checkInitialStatus();
});
