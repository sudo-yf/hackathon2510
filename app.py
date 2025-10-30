"""
手势控制系统 V2.0
基于 MediaPipe Hands 的实时手势识别鼠标控制系统

特性：
- 全屏相机视图 + 亚克力玻璃UI
- 美观的手部骨架绘制（21个关键点）
- 取幂增稳-边缘加速鼠标映射算法
- 拇指接触中指的点击检测
- 实时视频流传输（Flask-SocketIO）
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import cv2
import mediapipe as mp
import numpy as np
import base64
import threading
import time
import pyautogui

# Flask 应用初始化
app = Flask(__name__, static_folder='static', static_url_path='')
app.config['SECRET_KEY'] = 'gesture_control_v2_0'
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

class GestureControlService:
    """手势控制服务类 - 核心业务逻辑"""

    def __init__(self):
        """初始化服务"""
        # ========== MediaPipe 初始化 ==========
        self.hands = mp.solutions.hands.Hands(
            model_complexity=1,              # 模型复杂度：0=轻量, 1=中等, 2=完整
            max_num_hands=2,                 # 最大检测手数
            min_detection_confidence=0.5,    # 检测置信度阈值
            min_tracking_confidence=0.5      # 跟踪置信度阈值
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_hands = mp.solutions.hands

        # ========== 摄像头和运行状态 ==========
        self.cap = None                      # 摄像头对象
        self.running = False                 # 运行状态标志
        self.thread = None                   # 处理线程

        # ========== 屏幕尺寸 ==========
        self.screen_w, self.screen_h = pyautogui.size()

        # ========== 鼠标控制状态 ==========
        self.mouse_enabled = False           # 鼠标控制开关
        self.flip_horizontal = True          # 水平翻转（镜像模式）

        # ========== 鼠标映射参数（取幂增稳-边缘加速） ==========
        self.power_factor = 2.0              # 幂次，用于中心区域增稳（1.0-3.0）
        self.edge_boost = 1.5                # 边缘加速系数（1.0-3.0）
        self.dead_zone = 0.05                # 死区，减少抖动（0.01-0.1）

        # ========== 平滑参数 ==========
        self.cursor_x = None                 # 当前鼠标X坐标
        self.cursor_y = None                 # 当前鼠标Y坐标
        self.smoothing_alpha = 0.3           # 平滑系数（0.1-0.9）

        # ========== 手势检测参数 ==========
        self.click_threshold = 0.05          # 点击检测阈值（距离）
        self.last_gesture = None             # 上一次手势
        self.gesture_cooldown = 0.3          # 手势冷却时间（秒）
        self.last_gesture_time = 0           # 上一次手势时间

        # ========== 校准状态（预留功能） ==========
        self.calibration_mode = False
        self.calibration_data = {
            'left_samples': [],
            'right_samples': [],
            'left_threshold': 0.05,
            'right_threshold': 0.05
        }

        # ========== 统计信息 ==========
        self.fps = 0                         # 当前FPS
        self.frame_count = 0                 # 帧计数
        self.last_fps_time = time.time()    # 上次FPS计算时间
    
    def start(self):
        """
        启动摄像头和处理线程

        Returns:
            dict: {"success": bool, "message": str}
        """
        if self.running:
            return {"success": False, "message": "已在运行中"}

        try:
            # 打开摄像头（0=默认摄像头）
            self.cap = cv2.VideoCapture(0)

            # 设置摄像头参数
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)   # 宽度
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)   # 高度
            self.cap.set(cv2.CAP_PROP_FPS, 30)             # 帧率

            if not self.cap.isOpened():
                return {"success": False, "message": "无法打开摄像头"}

            # 启动处理线程
            self.running = True
            self.thread = threading.Thread(target=self.process_loop, daemon=True)
            self.thread.start()

            return {"success": True, "message": "摄像头已启动"}
        except Exception as e:
            return {"success": False, "message": f"启动失败: {str(e)}"}

    def stop(self):
        """
        停止摄像头

        Returns:
            dict: {"success": bool, "message": str}
        """
        self.running = False
        if self.cap:
            self.cap.release()
        return {"success": True, "message": "摄像头已停止"}
    
    def process_loop(self):
        """主处理循环"""
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                continue
            
            # 水平翻转
            if self.flip_horizontal:
                frame = cv2.flip(frame, 1)
            
            # 转换为RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # MediaPipe 处理
            results = self.hands.process(rgb_frame)
            
            # 绘制手部骨架
            annotated_frame = frame.copy()
            gesture_info = None
            
            if results.multi_hand_landmarks:
                for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    # 绘制美观的手部骨架
                    self.draw_hand_skeleton(annotated_frame, hand_landmarks)
                    
                    # 手势检测和鼠标控制（只处理第一只手）
                    if idx == 0:
                        gesture_info = self.process_hand_gesture(hand_landmarks, annotated_frame)
            
            # 绘制信息叠加层
            self.draw_overlay_info(annotated_frame, gesture_info)
            
            # 编码并发送
            _, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            
            # 发送视频帧
            socketio.emit('video_frame', {
                'image': frame_base64,
                'gesture': gesture_info,
                'fps': self.fps
            })
            
            # 计算FPS
            self.frame_count += 1
            current_time = time.time()
            if current_time - self.last_fps_time >= 1.0:
                self.fps = self.frame_count
                self.frame_count = 0
                self.last_fps_time = current_time
            
            time.sleep(0.01)
    
    def draw_hand_skeleton(self, frame, landmarks):
        """绘制美观的手部骨架"""
        h, w, _ = frame.shape
        
        # 定义连接关系
        connections = [
            # 大拇指
            [0, 1], [1, 2], [2, 3], [3, 4],
            # 食指
            [0, 5], [5, 6], [6, 7], [7, 8],
            # 中指
            [0, 9], [9, 10], [10, 11], [11, 12],
            # 无名指
            [0, 13], [13, 14], [14, 15], [15, 16],
            # 小指
            [0, 17], [17, 18], [18, 19], [19, 20],
            # 手掌
            [5, 9], [9, 13], [13, 17]
        ]
        
        # 绘制连接线（渐变色）
        for start_idx, end_idx in connections:
            start = landmarks.landmark[start_idx]
            end = landmarks.landmark[end_idx]
            
            start_point = (int(start.x * w), int(start.y * h))
            end_point = (int(end.x * w), int(end.y * h))
            
            # 使用渐变色效果（蓝紫色）
            cv2.line(frame, start_point, end_point, (220, 100, 50), 3, cv2.LINE_AA)
        
        # 绘制关键点
        for idx, landmark in enumerate(landmarks.landmark):
            x, y = int(landmark.x * w), int(landmark.y * h)
            
            # 手腕用红色，其他用白色
            if idx == 0:
                cv2.circle(frame, (x, y), 8, (50, 50, 255), -1, cv2.LINE_AA)
                cv2.circle(frame, (x, y), 8, (220, 100, 50), 2, cv2.LINE_AA)
            else:
                cv2.circle(frame, (x, y), 5, (255, 255, 255), -1, cv2.LINE_AA)
                cv2.circle(frame, (x, y), 5, (220, 100, 50), 2, cv2.LINE_AA)
    
    def process_hand_gesture(self, landmarks, frame):
        """处理手势并控制鼠标"""
        # 获取关键点
        thumb_tip = landmarks.landmark[4]      # 大拇指指尖
        index_tip = landmarks.landmark[8]      # 食指指尖
        middle_tip = landmarks.landmark[12]    # 中指指尖
        middle_mid = landmarks.landmark[10]    # 中指中间关节
        
        gesture_info = {
            'type': None,
            'mouse_pos': None,
            'click': None
        }
        
        # 鼠标移动（使用食指）
        if self.mouse_enabled:
            self.update_mouse_position_advanced(index_tip)
            gesture_info['mouse_pos'] = (self.cursor_x, self.cursor_y)
        
        # 手势检测：大拇指接触中指
        current_time = time.time()
        
        # 计算距离
        dist_to_tip = self.calculate_distance(thumb_tip, middle_tip)
        dist_to_mid = self.calculate_distance(thumb_tip, middle_mid)
        
        # 左键：大拇指接触中指指尖
        if dist_to_tip < self.calibration_data['left_threshold']:
            if current_time - self.last_gesture_time > self.gesture_cooldown:
                if self.last_gesture != 'left_click':
                    gesture_info['type'] = 'left_click'
                    gesture_info['click'] = 'left'
                    if self.mouse_enabled:
                        pyautogui.click()
                        print("🖱️ 左键点击")
                    self.last_gesture = 'left_click'
                    self.last_gesture_time = current_time
        
        # 右键：大拇指接触中指中间
        elif dist_to_mid < self.calibration_data['right_threshold']:
            if current_time - self.last_gesture_time > self.gesture_cooldown:
                if self.last_gesture != 'right_click':
                    gesture_info['type'] = 'right_click'
                    gesture_info['click'] = 'right'
                    if self.mouse_enabled:
                        pyautogui.rightClick()
                        print("🖱️ 右键点击")
                    self.last_gesture = 'right_click'
                    self.last_gesture_time = current_time
        else:
            self.last_gesture = None
        
        return gesture_info
    
    def calculate_distance(self, point1, point2):
        """计算两点之间的欧氏距离"""
        return np.sqrt((point1.x - point2.x)**2 + (point1.y - point2.y)**2)
    
    def update_mouse_position_advanced(self, finger_tip):
        """高级鼠标位置更新：取幂增稳-边缘加速"""
        # 归一化坐标 (0-1)
        norm_x = finger_tip.x
        norm_y = finger_tip.y
        
        # 中心化 (-0.5 to 0.5)
        centered_x = norm_x - 0.5
        centered_y = norm_y - 0.5
        
        # 计算到中心的距离
        distance_from_center = np.sqrt(centered_x**2 + centered_y**2)
        
        # 死区处理
        if distance_from_center < self.dead_zone:
            return
        
        # 取幂增稳：中心区域移动变慢
        # 边缘加速：靠近边缘时加速
        if distance_from_center < 0.3:
            # 中心区域：使用幂函数减速
            factor = np.power(distance_from_center / 0.3, self.power_factor)
        else:
            # 边缘区域：线性加速
            factor = 1.0 + (distance_from_center - 0.3) * self.edge_boost
        
        # 应用映射
        mapped_x = 0.5 + centered_x * factor
        mapped_y = 0.5 + centered_y * factor
        
        # 限制范围
        mapped_x = max(0, min(1, mapped_x))
        mapped_y = max(0, min(1, mapped_y))
        
        # 转换为屏幕坐标
        target_x = int(mapped_x * self.screen_w)
        target_y = int(mapped_y * self.screen_h)
        
        # 平滑处理
        if self.cursor_x is None:
            self.cursor_x, self.cursor_y = target_x, target_y
        else:
            self.cursor_x = int(self.cursor_x + self.smoothing_alpha * (target_x - self.cursor_x))
            self.cursor_y = int(self.cursor_y + self.smoothing_alpha * (target_y - self.cursor_y))
        
        # 移动鼠标
        try:
            pyautogui.moveTo(self.cursor_x, self.cursor_y, duration=0)
        except Exception as e:
            print(f"鼠标移动失败: {e}")
    
    def draw_overlay_info(self, frame, gesture_info):
        """绘制信息叠加层"""
        h, w, _ = frame.shape
        
        # FPS显示（左上角）
        cv2.putText(frame, f"FPS: {self.fps}", (20, 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        
        # 鼠标状态（左上角）
        mouse_status = "ON" if self.mouse_enabled else "OFF"
        color = (0, 255, 0) if self.mouse_enabled else (128, 128, 128)
        cv2.putText(frame, f"Mouse: {mouse_status}", (20, 75),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
        
        # 手势信息（右上角，亚克力效果）
        if gesture_info and gesture_info['type']:
            self.draw_glass_card(frame, gesture_info)
    
    def draw_glass_card(self, frame, gesture_info):
        """绘制亚克力效果的手势卡片"""
        h, w, _ = frame.shape
        
        # 卡片位置和大小
        card_w, card_h = 200, 80
        card_x = w - card_w - 20
        card_y = 100
        
        # 创建半透明背景
        overlay = frame.copy()
        cv2.rectangle(overlay, (card_x, card_y), (card_x + card_w, card_y + card_h),
                     (255, 255, 255), -1)
        cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
        
        # 边框
        cv2.rectangle(frame, (card_x, card_y), (card_x + card_w, card_y + card_h),
                     (200, 200, 200), 2, cv2.LINE_AA)
        
        # 文字
        gesture_text = "左键" if gesture_info['click'] == 'left' else "右键"
        text_color = (255, 100, 50) if gesture_info['click'] == 'left' else (220, 100, 220)
        
        cv2.putText(frame, gesture_text, (card_x + 60, card_y + 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, text_color, 3, cv2.LINE_AA)

# 全局服务实例
service = GestureControlService()

# API 路由
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/camera/start', methods=['POST'])
def start_camera():
    result = service.start()
    return jsonify(result)

@app.route('/api/camera/stop', methods=['POST'])
def stop_camera():
    result = service.stop()
    return jsonify(result)

@app.route('/api/mouse/toggle', methods=['POST'])
def toggle_mouse():
    service.mouse_enabled = not service.mouse_enabled
    return jsonify({
        "success": True,
        "enabled": service.mouse_enabled,
        "message": f"鼠标控制已{'启用' if service.mouse_enabled else '禁用'}"
    })

@app.route('/api/settings/flip', methods=['POST'])
def toggle_flip():
    service.flip_horizontal = not service.flip_horizontal
    return jsonify({
        "success": True,
        "flipped": service.flip_horizontal
    })

@app.route('/api/settings', methods=['POST'])
def update_settings():
    data = request.get_json()
    if 'smoothing' in data:
        service.smoothing_alpha = float(data['smoothing'])
    if 'power_factor' in data:
        service.power_factor = float(data['power_factor'])
    if 'edge_boost' in data:
        service.edge_boost = float(data['edge_boost'])
    return jsonify({"success": True})

# SocketIO 事件
@socketio.on('connect')
def handle_connect():
    emit('status', {"message": "已连接到服务器"})

@socketio.on('disconnect')
def handle_disconnect():
    print("客户端断开连接")

if __name__ == '__main__':
    print("🚀 手势控制系统 V2.0 启动中...")
    print("📱 访问地址: http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)

