const bridge = window.AstrBotPluginPage;

const logContainer = document.getElementById('logContainer');
const statusEl = document.getElementById('status');
const clearBtn = document.getElementById('clearBtn');
const autoScrollBtn = document.getElementById('autoScrollBtn');
const logCountEl = document.getElementById('logCount');
const lastUpdateEl = document.getElementById('lastUpdate');

let logs = [];
let subscriptionId = null;
let autoScroll = true;

function formatTime(date) {
    const d = new Date(date);
    return d.toLocaleTimeString('zh-CN', { 
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    }) + '.' + String(d.getMilliseconds()).padStart(3, '0');
}

function getLevelClass(level) {
    const levelMap = {
        'INFO': 'level-info',
        'ERROR': 'level-error',
        'WARN': 'level-warn',
        'WARNING': 'level-warn',
        'DEBUG': 'level-debug'
    };
    return levelMap[level?.toUpperCase()] || '';
}

function renderLog(log) {
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    
    const timestamp = log.timestamp ? formatTime(log.timestamp) : formatTime(new Date());
    const level = log.level || 'INFO';
    const message = log.message || log;
    
    entry.innerHTML = `
        <span class="timestamp">[${timestamp}]</span>
        <span class="${getLevelClass(level)}">[${level}]</span>
        <span>${typeof message === 'string' ? message : JSON.stringify(message)}</span>
    `;
    
    return entry;
}

function updateStats() {
    logCountEl.textContent = `日志条数: ${logs.length}`;
    lastUpdateEl.textContent = `最后更新: ${formatTime(new Date())}`;
}

function addLog(log) {
    // 清除占位符
    const placeholder = logContainer.querySelector('.log-placeholder');
    if (placeholder) {
        placeholder.remove();
    }
    
    logs.push(log);
    const entry = renderLog(log);
    logContainer.appendChild(entry);
    
    // 限制日志数量，防止内存溢出
    if (logs.length > 1000) {
        logs.shift();
        logContainer.removeChild(logContainer.firstChild);
    }
    
    updateStats();
    
    if (autoScroll) {
        logContainer.scrollTop = logContainer.scrollHeight;
    }
}

function clearLogs() {
    logs = [];
    logContainer.innerHTML = '<div class="log-placeholder">日志已清空，等待新日志...</div>';
    updateStats();
}

function setStatus(status, text) {
    statusEl.className = `status ${status}`;
    statusEl.textContent = text;
}

async function connectSSE() {
    setStatus('connecting', '连接中...');
    
    try {
        subscriptionId = await bridge.subscribeSSE(
            'logs/stream',
            {
                onOpen() {
                    setStatus('connected', '已连接');
                    console.log('SSE 连接已建立');
                },
                onMessage(event) {
                    try {
                        const log = event.parsed || event.raw;
                        if (typeof log === 'string') {
                            addLog({ message: log, level: 'INFO', timestamp: new Date().toISOString() });
                        } else {
                            addLog(log);
                        }
                    } catch (e) {
                        addLog({ message: event.raw, level: 'INFO', timestamp: new Date().toISOString() });
                    }
                },
                onError(error) {
                    setStatus('disconnected', '连接失败');
                    console.error('SSE 错误:', error);
                    // 3秒后重连
                    setTimeout(connectSSE, 3000);
                }
            }
        );
    } catch (error) {
        setStatus('disconnected', '连接失败');
        console.error('订阅失败:', error);
        // 3秒后重连
        setTimeout(connectSSE, 3000);
    }
}

// 事件监听
clearBtn.addEventListener('click', clearLogs);

autoScrollBtn.addEventListener('click', () => {
    autoScroll = !autoScroll;
    autoScrollBtn.classList.toggle('active', autoScroll);
    if (autoScroll) {
        logContainer.scrollTop = logContainer.scrollHeight;
    }
});

// 页面加载时初始化
async function init() {
    await bridge.ready();
    console.log('Bridge 就绪，开始连接日志流...');
    connectSSE();
}

// 页面卸载时清理
window.addEventListener('beforeunload', () => {
    if (subscriptionId) {
        bridge.unsubscribeSSE(subscriptionId);
    }
});

init();
