/**
 * 手势控制系统 V2.0 - 前端控制脚本
 *
 * 功能：
 * - Socket.IO 实时通信
 * - 视频流显示
 * - 控制面板交互
 * - 设置参数调节
 * - 键盘快捷键
 */

// ========== 全局状态 ==========
const state = {
    cameraRunning: false,    // 摄像头运行状态
    mouseEnabled: false,     // 鼠标控制状态
    flipped: true,           // 画面翻转状态
    connected: false         // Socket.IO 连接状态
};

// ========== Socket.IO 连接 ==========
const socket = io(window.location.origin);

// ========== DOM 元素引用 ==========
const elements = {
    // 视频和加载
    videoCanvas: document.getElementById('videoCanvas'),
    loading: document.getElementById('loading'),

    // 按钮
    btnCamera: document.getElementById('btnCamera'),
    btnMouse: document.getElementById('btnMouse'),

    // 状态指示器
    statusCamera: document.getElementById('statusCamera'),
    statusMouse: document.getElementById('statusMouse'),
    statusFPS: document.getElementById('statusFPS'),
    fpsText: document.getElementById('fpsText'),

    // 面板
    gestureHint: document.getElementById('gestureHint'),
    settingsPanel: document.getElementById('settingsPanel'),

    // 设置滑块
    smoothing: document.getElementById('smoothing'),
    powerFactor: document.getElementById('powerFactor'),
    edgeBoost: document.getElementById('edgeBoost'),

    // 设置值显示
    smoothingValue: document.getElementById('smoothingValue'),
    powerValue: document.getElementById('powerValue'),
    edgeValue: document.getElementById('edgeValue')
};

// ========== Socket.IO 事件处理 ==========

/**
 * 连接成功事件
 */
socket.on('connect', () => {
    console.log('✅ 已连接到服务器');
    state.connected = true;
    hideLoading();
});

/**
 * 断开连接事件
 */
socket.on('disconnect', () => {
    console.log('❌ 与服务器断开连接');
    state.connected = false;
    showLoading('连接断开，正在重连...');
});

/**
 * 状态更新事件
 */
socket.on('status', (data) => {
    console.log('状态更新:', data);
});

/**
 * 视频帧接收事件
 * @param {Object} data - 包含 image, fps, gesture 的数据
 */
socket.on('video_frame', (data) => {
    // 更新视频画面
    if (data.image) {
        elements.videoCanvas.src = 'data:image/jpeg;base64,' + data.image;
    }

    // 更新FPS显示
    if (data.fps !== undefined) {
        elements.fpsText.textContent = `FPS: ${data.fps}`;
        // FPS > 20 显示绿色，否则灰色
        elements.statusFPS.className = data.fps > 20 ? 'status-dot active' : 'status-dot inactive';
    }

    // 处理手势信息
    if (data.gesture) {
        handleGestureInfo(data.gesture);
    }
});

// 摄像头控制
async function toggleCamera() {
    if (state.cameraRunning) {
        // 停止摄像头
        try {
            const response = await fetch('/api/camera/stop', { method: 'POST' });
            const result = await response.json();
            
            if (result.success) {
                state.cameraRunning = false;
                elements.btnCamera.textContent = '📷 启动摄像头';
                elements.btnCamera.className = 'btn btn-primary';
                elements.btnMouse.disabled = true;
                elements.statusCamera.className = 'status-dot inactive';
                
                // 停止鼠标控制
                if (state.mouseEnabled) {
                    await toggleMouse();
                }
            }
        } catch (error) {
            console.error('停止摄像头失败:', error);
            alert('停止摄像头失败');
        }
    } else {
        // 启动摄像头
        showLoading('正在启动摄像头...');
        
        try {
            const response = await fetch('/api/camera/start', { method: 'POST' });
            const result = await response.json();
            
            if (result.success) {
                state.cameraRunning = true;
                elements.btnCamera.textContent = '⏹️ 停止摄像头';
                elements.btnCamera.className = 'btn btn-danger';
                elements.btnMouse.disabled = false;
                elements.statusCamera.className = 'status-dot active';
                hideLoading();
            } else {
                alert('启动摄像头失败: ' + result.message);
                hideLoading();
            }
        } catch (error) {
            console.error('启动摄像头失败:', error);
            alert('启动摄像头失败');
            hideLoading();
        }
    }
}

// 鼠标控制
async function toggleMouse() {
    try {
        const response = await fetch('/api/mouse/toggle', { method: 'POST' });
        const result = await response.json();
        
        if (result.success) {
            state.mouseEnabled = result.enabled;
            elements.btnMouse.textContent = result.enabled ? '🖱️ 停用鼠标' : '🖱️ 启用鼠标';
            elements.btnMouse.className = result.enabled ? 'btn btn-success' : 'btn btn-secondary';
            elements.statusMouse.className = result.enabled ? 'status-dot active' : 'status-dot inactive';
            
            // 显示/隐藏手势提示
            if (result.enabled) {
                elements.gestureHint.style.display = 'block';
            } else {
                elements.gestureHint.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('切换鼠标控制失败:', error);
        alert('切换鼠标控制失败');
    }
}

// 翻转画面
async function toggleFlip() {
    try {
        const response = await fetch('/api/settings/flip', { method: 'POST' });
        const result = await response.json();
        
        if (result.success) {
            state.flipped = result.flipped;
            console.log('画面翻转:', state.flipped);
        }
    } catch (error) {
        console.error('翻转画面失败:', error);
    }
}

// 切换设置面板
function toggleSettings() {
    const panel = elements.settingsPanel;
    const hint = elements.gestureHint;
    
    if (panel.classList.contains('active')) {
        panel.classList.remove('active');
        if (state.mouseEnabled) {
            hint.style.display = 'block';
        }
    } else {
        panel.classList.add('active');
        hint.style.display = 'none';
    }
}

// 处理手势信息
function handleGestureInfo(gesture) {
    // 可以在这里添加手势可视化效果
    if (gesture.click) {
        console.log('检测到点击:', gesture.click);
        // 可以添加视觉反馈
        showClickFeedback(gesture.click);
    }
}

// 显示点击反馈
function showClickFeedback(clickType) {
    // 创建临时反馈元素
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

// 设置滑块事件
elements.smoothing.addEventListener('input', async (e) => {
    const value = parseFloat(e.target.value);
    elements.smoothingValue.textContent = value.toFixed(1);
    
    try {
        await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ smoothing: value })
        });
    } catch (error) {
        console.error('更新设置失败:', error);
    }
});

elements.powerFactor.addEventListener('input', async (e) => {
    const value = parseFloat(e.target.value);
    elements.powerValue.textContent = value.toFixed(1);
    
    try {
        await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ power_factor: value })
        });
    } catch (error) {
        console.error('更新设置失败:', error);
    }
});

elements.edgeBoost.addEventListener('input', async (e) => {
    const value = parseFloat(e.target.value);
    elements.edgeValue.textContent = value.toFixed(1);
    
    try {
        await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ edge_boost: value })
        });
    } catch (error) {
        console.error('更新设置失败:', error);
    }
});

// 工具函数
function showLoading(message = '正在加载...') {
    elements.loading.style.display = 'block';
    elements.loading.querySelector('p').textContent = message;
}

function hideLoading() {
    elements.loading.style.display = 'none';
}

// 添加淡出动画
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

// 键盘快捷键
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + M: 切换鼠标控制
    if ((e.ctrlKey || e.metaKey) && e.key === 'm') {
        e.preventDefault();
        if (state.cameraRunning && !elements.btnMouse.disabled) {
            toggleMouse();
        }
    }
    
    // Ctrl/Cmd + C: 切换摄像头
    if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
        e.preventDefault();
        toggleCamera();
    }
    
    // Ctrl/Cmd + F: 翻转画面
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault();
        toggleFlip();
    }
    
    // Ctrl/Cmd + S: 切换设置
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        toggleSettings();
    }
});

// 初始化
console.log('🚀 手势控制系统 V2.0 已加载');
console.log('快捷键:');
console.log('  Ctrl/Cmd + C: 切换摄像头');
console.log('  Ctrl/Cmd + M: 切换鼠标控制');
console.log('  Ctrl/Cmd + F: 翻转画面');
console.log('  Ctrl/Cmd + S: 切换设置');

