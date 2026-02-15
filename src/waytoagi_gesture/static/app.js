/**
 * WayToAGI Gesture Control frontend
 */

const state = {
    cameraRunning: false,
    mouseEnabled: false,
    flipped: true,
    connected: false
};

const socket = io(window.location.origin);

const elements = {
    videoCanvas: document.getElementById('videoCanvas'),
    loading: document.getElementById('loading'),
    btnCamera: document.getElementById('btnCamera'),
    btnMouse: document.getElementById('btnMouse'),
    statusCamera: document.getElementById('statusCamera'),
    statusMouse: document.getElementById('statusMouse'),
    statusFPS: document.getElementById('statusFPS'),
    fpsText: document.getElementById('fpsText'),
    gestureHint: document.getElementById('gestureHint'),
    settingsPanel: document.getElementById('settingsPanel'),
    smoothing: document.getElementById('smoothing'),
    powerFactor: document.getElementById('powerFactor'),
    edgeBoost: document.getElementById('edgeBoost'),
    smoothingValue: document.getElementById('smoothingValue'),
    powerValue: document.getElementById('powerValue'),
    edgeValue: document.getElementById('edgeValue')
};

const api = {
    async getSettings() {
        const res = await fetch('/api/settings');
        return res.json();
    },
    async updateSettings(payload) {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        return res.json();
    },
    async post(path) {
        const res = await fetch(path, { method: 'POST' });
        return res.json();
    }
};

function applySettingsToUI(settings) {
    elements.smoothing.value = settings.smoothing;
    elements.powerFactor.value = settings.power_factor;
    elements.edgeBoost.value = settings.edge_boost;
    elements.smoothingValue.textContent = Number(settings.smoothing).toFixed(1);
    elements.powerValue.textContent = Number(settings.power_factor).toFixed(1);
    elements.edgeValue.textContent = Number(settings.edge_boost).toFixed(1);
}

function debounce(fn, wait = 120) {
    let timer = null;
    return (...args) => {
        if (timer) {
            clearTimeout(timer);
        }
        timer = setTimeout(() => fn(...args), wait);
    };
}

socket.on('connect', () => {
    state.connected = true;
    hideLoading();
});

socket.on('disconnect', () => {
    state.connected = false;
    showLoading('连接断开，正在重连...');
});

socket.on('video_frame', (data) => {
    if (data.image) {
        elements.videoCanvas.src = 'data:image/jpeg;base64,' + data.image;
    }

    if (data.fps !== undefined) {
        elements.fpsText.textContent = `FPS: ${data.fps}`;
        elements.statusFPS.className = data.fps > 20 ? 'status-dot active' : 'status-dot inactive';
    }

    if (data.gesture && data.gesture.click) {
        showClickFeedback(data.gesture.click);
    }
});

async function toggleCamera() {
    if (state.cameraRunning) {
        try {
            const result = await api.post('/api/camera/stop');
            if (!result.success) {
                return;
            }
            state.cameraRunning = false;
            elements.btnCamera.textContent = '📷 启动摄像头';
            elements.btnCamera.className = 'btn btn-primary';
            elements.btnMouse.disabled = true;
            elements.statusCamera.className = 'status-dot inactive';
            if (state.mouseEnabled) {
                await toggleMouse();
            }
        } catch (error) {
            console.error('停止摄像头失败:', error);
        }
        return;
    }

    showLoading('正在启动摄像头...');
    try {
        const result = await api.post('/api/camera/start');
        if (!result.success) {
            alert('启动摄像头失败: ' + result.message);
            hideLoading();
            return;
        }

        state.cameraRunning = true;
        elements.btnCamera.textContent = '⏹️ 停止摄像头';
        elements.btnCamera.className = 'btn btn-danger';
        elements.btnMouse.disabled = false;
        elements.statusCamera.className = 'status-dot active';
        hideLoading();
    } catch (error) {
        console.error('启动摄像头失败:', error);
        hideLoading();
    }
}

async function toggleMouse() {
    try {
        const result = await api.post('/api/mouse/toggle');
        if (!result.success) {
            alert(result.message || '切换鼠标控制失败');
            return;
        }

        state.mouseEnabled = result.enabled;
        elements.btnMouse.textContent = result.enabled ? '🖱️ 停用鼠标' : '🖱️ 启用鼠标';
        elements.btnMouse.className = result.enabled ? 'btn btn-success' : 'btn btn-secondary';
        elements.statusMouse.className = result.enabled ? 'status-dot active' : 'status-dot inactive';
        elements.gestureHint.style.display = result.enabled ? 'block' : 'none';
    } catch (error) {
        console.error('切换鼠标控制失败:', error);
    }
}

async function toggleFlip() {
    try {
        const result = await api.post('/api/settings/flip');
        if (result.success) {
            state.flipped = result.flipped;
        }
    } catch (error) {
        console.error('翻转画面失败:', error);
    }
}

function toggleSettings() {
    const panel = elements.settingsPanel;
    const hint = elements.gestureHint;

    if (panel.classList.contains('active')) {
        panel.classList.remove('active');
        if (state.mouseEnabled) {
            hint.style.display = 'block';
        }
        return;
    }

    panel.classList.add('active');
    hint.style.display = 'none';
}

function showClickFeedback(clickType) {
    const feedback = document.createElement('div');
    feedback.style.position = 'fixed';
    feedback.style.top = '50%';
    feedback.style.left = '50%';
    feedback.style.transform = 'translate(-50%, -50%)';
    feedback.style.padding = '20px 40px';
    feedback.style.borderRadius = '16px';
    feedback.style.fontSize = '24px';
    feedback.style.fontWeight = 'bold';
    feedback.style.color = 'white';
    feedback.style.zIndex = '1000';
    feedback.style.pointerEvents = 'none';
    feedback.style.animation = 'fadeOut 0.5s ease-out';
    feedback.className = 'glass';

    if (clickType === 'left') {
        feedback.textContent = '🖱️ 左键';
        feedback.style.background = 'rgba(0, 122, 255, 0.3)';
    } else {
        feedback.textContent = '🖱️ 右键';
        feedback.style.background = 'rgba(88, 86, 214, 0.3)';
    }

    document.body.appendChild(feedback);
    setTimeout(() => {
        document.body.removeChild(feedback);
    }, 500);
}

function showLoading(message = '正在加载...') {
    elements.loading.style.display = 'block';
    elements.loading.querySelector('p').textContent = message;
}

function hideLoading() {
    elements.loading.style.display = 'none';
}

const persistSetting = debounce(async (payload) => {
    try {
        await api.updateSettings(payload);
    } catch (error) {
        console.error('更新设置失败:', error);
    }
}, 150);

elements.smoothing.addEventListener('input', (e) => {
    const value = parseFloat(e.target.value);
    elements.smoothingValue.textContent = value.toFixed(1);
    persistSetting({ smoothing: value });
});

elements.powerFactor.addEventListener('input', (e) => {
    const value = parseFloat(e.target.value);
    elements.powerValue.textContent = value.toFixed(1);
    persistSetting({ power_factor: value });
});

elements.edgeBoost.addEventListener('input', (e) => {
    const value = parseFloat(e.target.value);
    elements.edgeValue.textContent = value.toFixed(1);
    persistSetting({ edge_boost: value });
});

const style = document.createElement('style');
style.textContent = `
    @keyframes fadeOut {
        from {
            opacity: 1;
            transform: translate(-50%, -50%) scale(1);
        }
        to {
            opacity: 0;
            transform: translate(-50%, -50%) scale(1.2);
        }
    }
`;
document.head.appendChild(style);

document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'm') {
        e.preventDefault();
        if (state.cameraRunning && !elements.btnMouse.disabled) {
            toggleMouse();
        }
    }

    if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
        e.preventDefault();
        toggleCamera();
    }

    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault();
        toggleFlip();
    }

    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        toggleSettings();
    }
});

(async () => {
    try {
        const response = await api.getSettings();
        if (response.success && response.settings) {
            applySettingsToUI(response.settings);
        }
    } catch (error) {
        console.error('加载配置失败:', error);
    }
})();
