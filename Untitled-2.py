#!/usr/bin/env python3
"""
🍄 Raspberry Pi Mushroom Detection Server
ESP32 (Master) gọi → Pi chụp ảnh → Nhận diện YOLO → Trả kết quả JSON
"""

from flask import Flask, jsonify, request
import cv2
from ultralytics import YOLO
import time
import logging
import os
from datetime import datetime
import threading

# ========== CẤU HÌNH ==========
MODEL_PATH = "/home/dung/Desktop/nam/best.pt"  # Đường dẫn model YOLO
LABEL_HU = "HU"  # Nhãn nấm hư trong model
PORT = 2177  # Port server Flask

# ========== LOGGING ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [PI SERVER] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/mushroom_detection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========== KHỞI TẠO HỆ THỐNG ==========
def initialize_system():
    """Kiểm tra và khởi tạo hệ thống"""
    logger.info("=" * 60)
    logger.info("🚀 RASPBERRY PI MUSHROOM DETECTION SERVER")
    logger.info("=" * 60)
    
    # Kiểm tra file model
    if not os.path.exists(MODEL_PATH):
        logger.error(f"❌ KHÔNG TÌM THẤY MODEL: {MODEL_PATH}")
        logger.info("📁 Vui lòng kiểm tra đường dẫn model")
        return False
    
    # Kiểm tra camera
    logger.info("📷 Kiểm tra camera...")
    for camera_index in [0, -1, 1, 2]:
        camera = cv2.VideoCapture(camera_index)
        if camera.isOpened():
            logger.info(f"✅ Tìm thấy camera tại index {camera_index}")
            camera.release()
            break
        camera.release()
    else:
        logger.error("❌ Không tìm thấy camera nào")
        return False
    
    return True

# ========== LOAD MODEL YOLO ==========
try:
    model = YOLO(MODEL_PATH)
    logger.info(f"✅ Đã load model YOLO: {MODEL_PATH}")
    logger.info(f"📊 Số lớp trong model: {len(model.names)}")
    logger.info(f"🏷️ Danh sách lớp: {model.names}")
except Exception as e:
    logger.error(f"❌ Lỗi load model: {e}")
    exit(1)

# ========== HÀM CHỤP ẢNH VÀ NHẬN DIỆN ==========
def capture_and_detect():
    """
    Chụp ảnh từ camera và nhận diện nấm
    Returns: (classification, region)
    """
    camera = None
    start_time = time.time()
    
    try:
        logger.info("📸 Bắt đầu quá trình nhận diện...")
        
        # Thử các index camera khác nhau
        camera_indexes = [0, -1, 1, 2]
        camera = None
        
        for idx in camera_indexes:
            camera = cv2.VideoCapture(idx)
            if camera.isOpened():
                logger.info(f"✅ Mở camera index {idx}")
                break
            camera.release()
        
        if not camera or not camera.isOpened():
            logger.error("❌ Không thể mở camera")
            return "PHOI", "none"
        
        # Đặt thông số camera
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        # Chờ camera ổn định
        logger.info("⏳ Chờ camera ổn định...")
        time.sleep(2)
        
        # Chụp ảnh
        success, image = camera.read()
        if not success:
            logger.error("❌ Không thể chụp ảnh")
            return "PHOI", "none"
        
        capture_time = time.time() - start_time
        logger.info(f"✅ Đã chụp ảnh ({capture_time:.1f}s): {image.shape}")
        
        # ========== NHẬN DIỆN VỚI YOLO ==========
        logger.info("🔍 Đang nhận diện với YOLO...")
        results = model(image, verbose=False)[0]
        boxes = results.boxes
        
        # Lấy danh sách vật thể phát hiện
        detected_objects = []
        confidence_scores = []
        
        if boxes is not None and len(boxes) > 0:
            for box in boxes:
                class_id = int(box.cls[0])
                label = model.names[class_id]
                confidence = float(box.conf[0])
                detected_objects.append(label)
                confidence_scores.append(confidence)
                logger.info(f"  - Phát hiện: {label} (độ tin cậy: {confidence:.2f})")
        
        logger.info(f"🎯 Tổng số vật thể phát hiện: {len(detected_objects)}")
        
        # ========== PHÂN LOẠI GIAI ĐOẠN ==========
        if not detected_objects:
            classification = "PHOI"
            logger.info("🏷️ Không phát hiện vật thể → Giai đoạn: PHOI")
        elif "NON" in detected_objects:
            classification = "NON"
            logger.info("🏷️ Phát hiện NON → Giai đoạn: NON")
        elif "TRUONG-THANH" in detected_objects:
            classification = "TRUONG-THANH"
            logger.info("🏷️ Phát hiện TRUONG-THANH → Giai đoạn: TRUONG-THANH")
        elif LABEL_HU in detected_objects:
            classification = "HU"
            logger.info("🏷️ Phát hiện HU → Giai đoạn: HU (NẤM HƯ)")
        else:
            classification = "PHOI"
            logger.info("🏷️ Không phát hiện lớp đặc biệt → Giai đoạn: PHOI")
        
        # ========== XÁC ĐỊNH VỊ TRÍ NẤM HƯ ==========
        region_flags = set()
        
        if boxes is not None and LABEL_HU in detected_objects:
            # Lấy kích thước ảnh
            height, width = image.shape[:2]
            mid_y = height // 2
            
            # Vẽ đường chia đôi cho debug
            cv2.line(image, (0, mid_y), (width, mid_y), (200, 200, 200), 2)
            cv2.putText(image, "TREN", (10, mid_y//2), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
            cv2.putText(image, "DUOI", (10, mid_y + mid_y//2), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
            
            # Kiểm tra từng nấm hư
            hu_count = 0
            for box in boxes:
                class_id = int(box.cls[0])
                label = model.names[class_id]
                
                if label != LABEL_HU:
                    continue
                
                hu_count += 1
                # Lấy tọa độ bounding box
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                center_y = (y1 + y2) // 2
                
                # Xác định vị trí
                if center_y < mid_y:
                    region = "TREN"
                else:
                    region = "DUOI"
                
                region_flags.add(region)
                
                # Vẽ box và nhãn (để debug)
                color = (0, 0, 255)  # Màu đỏ cho nấm hư
                cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
                cv2.putText(image, f"{label}-{region}", 
                           (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 
                           0.6, color, 2)
                cv2.circle(image, ((x1+x2)//2, center_y), 5, color, -1)
            
            logger.info(f"📍 Số nấm hư phát hiện: {hu_count}")
        
        # ========== TỔNG HỢP VỊ TRÍ ==========
        if "TREN" in region_flags and "DUOI" in region_flags:
            region_text = "TREN+DUOI"
        elif "TREN" in region_flags:
            region_text = "TREN"
        elif "DUOI" in region_flags:
            region_text = "DUOI"
        else:
            region_text = "none"
        
        logger.info(f"📍 Vị trí nấm hư: {region_text}")
        
        # ========== LƯU ẢNH KẾT QUẢ ==========
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = "detection_results"
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = f"{output_dir}/detect_{timestamp}.jpg"
        cv2.imwrite(output_path, image)
        logger.info(f"💾 Đã lưu ảnh kết quả: {output_path}")
        
        # Thời gian xử lý
        total_time = time.time() - start_time
        logger.info(f"⏱️ Tổng thời gian xử lý: {total_time:.2f} giây")
        
        return classification, region_text
        
    except Exception as e:
        logger.error(f"❌ Lỗi trong quá trình nhận diện: {e}")
        return "PHOI", "none"
        
    finally:
        if camera is not None:
            camera.release()

# ========== FLASK SERVER ==========
app = Flask(__name__)

@app.route('/detect', methods=['GET'])
def detect_endpoint():
    """
    Endpoint chính cho ESP32 gọi đến
    ESP32 gửi GET request → Pi nhận diện → Trả JSON kết quả
    """
    logger.info("\n" + "=" * 60)
    logger.info(f"📡 [{datetime.now().strftime('%H:%M:%S')}] NHẬN YÊU CẦU TỪ ESP32")
    
    # Lấy thông tin client
    client_ip = request.remote_addr if request.remote_addr else "unknown"
    logger.info(f"👤 Client IP: {client_ip}")
    
    # Thực hiện nhận diện
    start_time = time.time()
    classification, region = capture_and_detect()
    processing_time = time.time() - start_time
    
    # Tạo response JSON
    response = {
        "status": "success",
        "class": classification,
        "region": region,
        "processing_time": round(processing_time, 2),
        "timestamp": datetime.now().isoformat(),
        "server": "Raspberry Pi YOLOv8",
        "model": os.path.basename(MODEL_PATH),
        "client_ip": client_ip
    }
    
    logger.info(f"📤 TRẢ KẾT QUẢ VỀ ESP32:")
    logger.info(f"   Giai đoạn: {classification}")
    logger.info(f"   Vị trí: {region}")
    logger.info(f"   Thời gian xử lý: {processing_time:.2f}s")
    logger.info("=" * 60)
    
    return jsonify(response)

@app.route('/health', methods=['GET'])
def health_check():
    """Kiểm tra trạng thái server"""
    # Kiểm tra camera
    camera_ok = False
    try:
        camera = cv2.VideoCapture(0)
        camera_ok = camera.isOpened()
        camera.release()
    except:
        camera_ok = False
    
    return jsonify({
        "status": "healthy",
        "service": "Mushroom Detection Server",
        "model_loaded": os.path.exists(MODEL_PATH),
        "camera_available": camera_ok,
        "timestamp": datetime.now().isoformat(),
        "port": PORT,
        "model_path": MODEL_PATH
    })

@app.route('/test', methods=['GET'])
def test_detection():
    """Endpoint test nhận diện (không cần ESP32)"""
    logger.info("\n🔧 TEST NHẬN DIỆN THỦ CÔNG")
    classification, region = capture_and_detect()
    
    return jsonify({
        "test": True,
        "class": classification,
        "region": region,
        "message": "Test detection completed",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/', methods=['GET'])
def home_page():
    """Trang chủ hiển thị thông tin"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🍄 Mushroom Detection Server</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }
            
            .container {
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                overflow: hidden;
                max-width: 800px;
                width: 100%;
            }
            
            .header {
                background: linear-gradient(135deg, #4CAF50, #2E7D32);
                color: white;
                padding: 40px;
                text-align: center;
            }
            
            .header h1 {
                font-size: 2.5rem;
                margin-bottom: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 15px;
            }
            
            .header p {
                font-size: 1.1rem;
                opacity: 0.9;
            }
            
            .content {
                padding: 40px;
            }
            
            .status-card {
                background: #f8f9fa;
                border-radius: 15px;
                padding: 25px;
                margin-bottom: 25px;
                border-left: 5px solid #4CAF50;
            }
            
            .status-card h3 {
                color: #333;
                margin-bottom: 15px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .endpoint-list {
                list-style: none;
            }
            
            .endpoint-list li {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                margin-bottom: 15px;
                padding: 20px;
                transition: transform 0.3s, box-shadow 0.3s;
            }
            
            .endpoint-list li:hover {
                transform: translateY(-3px);
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            }
            
            .endpoint-method {
                display: inline-block;
                background: #4CAF50;
                color: white;
                padding: 5px 15px;
                border-radius: 20px;
                font-weight: bold;
                margin-right: 10px;
            }
            
            .endpoint-path {
                font-family: monospace;
                background: #f5f5f5;
                padding: 8px 15px;
                border-radius: 5px;
                display: block;
                margin: 10px 0;
            }
            
            .btn {
                display: inline-block;
                background: #4CAF50;
                color: white;
                padding: 12px 25px;
                border-radius: 30px;
                text-decoration: none;
                font-weight: bold;
                margin-top: 10px;
                transition: background 0.3s, transform 0.3s;
            }
            
            .btn:hover {
                background: #388E3C;
                transform: translateY(-2px);
            }
            
            .info-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-top: 20px;
            }
            
            .info-item {
                background: white;
                padding: 20px;
                border-radius: 10px;
                border: 1px solid #e0e0e0;
            }
            
            .info-label {
                font-weight: bold;
                color: #666;
                margin-bottom: 5px;
            }
            
            .info-value {
                color: #333;
                font-size: 1.1rem;
            }
            
            .badge {
                display: inline-block;
                padding: 5px 12px;
                border-radius: 20px;
                font-size: 0.9rem;
                font-weight: bold;
                margin-left: 10px;
            }
            
            .badge-success {
                background: #4CAF50;
                color: white;
            }
            
            .badge-warning {
                background: #FFC107;
                color: #333;
            }
            
            .badge-error {
                background: #F44336;
                color: white;
            }
            
            @media (max-width: 768px) {
                .header {
                    padding: 30px 20px;
                }
                
                .header h1 {
                    font-size: 2rem;
                }
                
                .content {
                    padding: 20px;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🍄 Raspberry Pi Mushroom Detection Server</h1>
                <p>ESP32 (Master) gọi → Pi (Slave) nhận diện → Trả kết quả</p>
            </div>
            
            <div class="content">
                <div class="status-card">
                    <h3>📊 Trạng thái hệ thống</h3>
                    <div class="info-grid">
                        <div class="info-item">
                            <div class="info-label">Model YOLOv8</div>
                            <div class="info-value">""" + os.path.basename(MODEL_PATH) + """</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">Port server</div>
                            <div class="info-value">""" + str(PORT) + """</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">Trạng thái</div>
                            <div class="info-value">
                                <span id="status-text">Đang kiểm tra...</span>
                                <span class="badge badge-success" id="status-badge"></span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="status-card">
                    <h3>🔌 API Endpoints</h3>
                    <ul class="endpoint-list">
                        <li>
                            <span class="endpoint-method">GET</span>
                            <strong>Endpoint chính</strong>
                            <div class="endpoint-path">/detect</div>
                            <p>ESP32 gọi endpoint này để nhận diện nấm. Trả về JSON với kết quả nhận diện.</p>
                            <a href="/detect" class="btn" target="_blank">Test ngay</a>
                        </li>
                        <li>
                            <span class="endpoint-method">GET</span>
                            <strong>Kiểm tra sức khỏe</strong>
                            <div class="endpoint-path">/health</div>
                            <p>Kiểm tra trạng thái server, camera và model.</p>
                            <a href="/health" class="btn" target="_blank">Kiểm tra</a>
                        </li>
                        <li>
                            <span class="endpoint-method">GET</span>
                            <strong>Test nhận diện</strong>
                            <div class="endpoint-path">/test</div>
                            <p>Test nhận diện thủ công (không cần ESP32).</p>
                            <a href="/test" class="btn" target="_blank">Test</a>
                        </li>
                    </ul>
                </div>
                
                <div class="status-card">
                    <h3>📝 Thông tin hoạt động</h3>
                    <ul class="endpoint-list">
                        <li>
                            <strong>🎯 Giai đoạn nấm phát hiện:</strong>
                            <p>PHOI, NON, TRUONG-THANH, HU</p>
                        </li>
                        <li>
                            <strong>📍 Vị trí nấm hư:</strong>
                            <p>TREN, DUOI, TREN+DUOI, none</p>
                        </li>
                        <li>
                            <strong>📁 Lưu ảnh:</strong>
                            <p>Ảnh kết quả được lưu trong thư mục: detection_results/</p>
                        </li>
                        <li>
                            <strong>📋 Logs:</strong>
                            <p>Xem file log: /tmp/mushroom_detection.log</p>
                        </li>
                    </ul>
                </div>
                
                <div style="text-align: center; margin-top: 30px;">
                    <p style="color: #666;">🍄 Hệ thống nhận diện nấm thông minh - Raspberry Pi Server</p>
                    <p style="color: #888; font-size: 0.9rem; margin-top: 10px;">
                        ESP32 gọi mỗi 5 phút khi hệ thống rảnh
                    </p>
                </div>
            </div>
        </div>
        
        <script>
            // Kiểm tra trạng thái server
            async function checkServerStatus() {
                try {
                    const response = await fetch('/health');
                    const data = await response.json();
                    
                    const statusText = document.getElementById('status-text');
                    const statusBadge = document.getElementById('status-badge');
                    
                    if (data.status === 'healthy') {
                        statusText.textContent = 'Hoạt động tốt';
                        statusBadge.textContent = 'ONLINE';
                        statusBadge.className = 'badge badge-success';
                    } else {
                        statusText.textContent = 'Có vấn đề';
                        statusBadge.textContent = 'ERROR';
                        statusBadge.className = 'badge badge-error';
                    }
                } catch (error) {
                    const statusText = document.getElementById('status-text');
                    const statusBadge = document.getElementById('status-badge');
                    
                    statusText.textContent = 'Không thể kết nối';
                    statusBadge.textContent = 'OFFLINE';
                    statusBadge.className = 'badge badge-error';
                }
            }
            
            // Kiểm tra khi trang load
            document.addEventListener('DOMContentLoaded', checkServerStatus);
            
            // Kiểm tra mỗi 30 giây
            setInterval(checkServerStatus, 30000);
        </script>
    </body>
    </html>
    """
    return html

# ========== CHẠY SERVER ==========
if __name__ == '__main__':
    # Khởi tạo hệ thống
    if not initialize_system():
        logger.error("❌ Khởi tạo thất bại, thoát chương trình")
        exit(1)
    
    # Lấy IP của Pi
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        pi_ip = s.getsockname()[0]
        s.close()
    except:
        pi_ip = "localhost"
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ KHỞI ĐỘNG THÀNH CÔNG!")
    logger.info(f"🌐 Server URL: http://{pi_ip}:{PORT}")
    logger.info(f"🌐 ESP32 gọi đến: http://{pi_ip}:{PORT}/detect")
    logger.info("=" * 60)
    logger.info("\n📡 SERVER ĐANG CHẠY - CHỜ YÊU CẦU TỪ ESP32")
    logger.info("🔄 Kiểm tra nhanh: http://localhost:" + str(PORT))
    logger.info("📊 Health check: http://localhost:" + str(PORT) + "/health")
    logger.info("=" * 60)
    
    # Chạy Flask server
    try:
        app.run(
            host='0.0.0.0',      # Chấp nhận kết nối từ mọi IP
            port=PORT,           # Port 2177
            debug=False,         # Tắt debug mode cho production
            threaded=True        # Xử lý nhiều request cùng lúc
        )
    except Exception as e:
        logger.error(f"❌ Lỗi khởi động server: {e}")