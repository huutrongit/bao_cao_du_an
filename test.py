from flask import Flask, jsonify
import cv2
from ultralytics import YOLO
import requests
from datetime import datetime
import time
import threading
import logging
import os
import subprocess

app = Flask(__name__)

# ----------- CẤU HÌNH ------------
# KIỂM TRA ĐƯỜNG DẪN MODEL - SỬA LẠI CHO ĐÚNG
MODEL_PATH = "/home/dung/Desktop/nam/best.pt"  # ĐIỀU CHỈNH ĐƯỜNG DẪN THẬT
GOOGLE_SHEETS_URL = ""  # DÁN URL APPS SCRIPT VÀO ĐÂY
LABEL_HU = "HU"

# ----------- KIỂM TRA HỆ THỐNG ------------
def kiem_tra_he_thong():
    """Kiểm tra hệ thống trước khi chạy"""
    logger = logging.getLogger(__name__)
    
    # 1. Kiểm tra model
    if not os.path.exists(MODEL_PATH):
        logger.error(f"❌ KHÔNG TÌM THẤY MODEL: {MODEL_PATH}")
        logger.info("📁 Danh sách file trong /home/dung/Desktop/nam/:")
        try:
            files = os.listdir("/home/dung/Desktop/nam/")
            for f in files:
                logger.info(f"   - {f}")
        except:
            pass
        return False
    
    # 2. Kiểm tra camera
    try:
        result = subprocess.run(['vcgencmd', 'get_camera'], 
                              capture_output=True, text=True)
        logger.info(f"📷 Camera check: {result.stdout}")
        
        # Kiểm tra /dev/video*
        video_devices = [d for d in os.listdir('/dev') if d.startswith('video')]
        logger.info(f"📹 Video devices: {video_devices}")
        
    except Exception as e:
        logger.warning(f"⚠️ Không kiểm tra được camera: {e}")
    
    # 3. Kiểm tra URL
    if not GOOGLE_SHEETS_URL or "script.google.com" not in GOOGLE_SHEETS_URL:
        logger.warning("⚠️ Chưa cấu hình Google Sheets URL")
    
    return True

# ----------- LOGGING ------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/nam_detection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ----------- KHỞI TẠO ------------
if not kiem_tra_he_thong():
    logger.error("❌ HỆ THỐNG KIỂM TRA THẤT BẠI")
    exit(1)

try:
    model = YOLO(MODEL_PATH)
    logger.info(f"✅ Đã load model từ: {MODEL_PATH}")
except Exception as e:
    logger.error(f"❌ Lỗi load model: {e}")
    exit(1)

# Lock cho camera (tránh xung đột)
camera_lock = threading.Lock()

# ----------- HÀM GỬI DỮ LIỆU ------------
def gui_len_google_sheets(giai_doan, vi_tri=""):
    """Gửi dữ liệu lên Google Sheets"""
    if not GOOGLE_SHEETS_URL:
        logger.warning("⚠️ Chưa cấu hình Google Sheets URL")
        return False
    
    try:
        du_lieu = {"class": giai_doan, "region": vi_tri}
        logger.info(f"📤 Gửi dữ liệu: {du_lieu}")
        
        # Thêm timeout và retry
        for retry in range(3):
            try:
                phan_hoi = requests.post(
                    GOOGLE_SHEETS_URL,
                    json=du_lieu,
                    timeout=5
                )
                
                if phan_hoi.status_code == 200:
                    logger.info(f"✅ Đã gửi lên Google Sheets")
                    return True
                else:
                    logger.error(f"❌ Lỗi {phan_hoi.status_code}: {phan_hoi.text}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"⏱️ Timeout lần {retry+1}")
                time.sleep(1)
                continue
                
            except Exception as e:
                logger.error(f"❌ Lỗi kết nối: {e}")
                break
                
        return False
        
    except Exception as e:
        logger.error(f"❌ Lỗi gửi dữ liệu: {e}")
        return False

# ----------- HÀM NHẬN DIỆN ------------
def nhan_dien_nam():
    """Nhận diện nấm từ camera"""
    camera = None
    try:
        with camera_lock:  # Dùng lock để tránh xung đột
            # Thử mở camera với các index khác nhau
            for camera_index in [0, 1, 2, -1]:
                camera = cv2.VideoCapture(camera_index)
                time.sleep(0.5)
                if camera.isOpened():
                    logger.info(f"✅ Mở camera index {camera_index}")
                    break
                camera.release()
            
            if not camera or not camera.isOpened():
                logger.error("❌ Không thể mở camera")
                return None, None, None
            
            # Đặt thông số camera
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            time.sleep(1)  # Chờ camera ổn định
            
            # Chụp ảnh
            thanh_cong, anh = camera.read()
            if not thanh_cong:
                logger.error("❌ Không đọc được ảnh từ camera")
                return None, None, None
            
            logger.info(f"📸 Ảnh kích thước: {anh.shape}")
            
            # Nhận diện với YOLO
            ket_qua = model(anh, verbose=False)[0]
            hop = ket_qua.boxes
            
            # Lấy danh sách vật thể
            vat_the = []
            if hop is not None:
                for h in hop:
                    class_id = int(h.cls[0])
                    nhan = model.names[class_id]
                    vat_the.append(nhan)
            
            logger.info(f"🎯 Vật thể phát hiện: {vat_the}")
            
            # Phân loại giai đoạn
            if not vat_the:
                giai_doan = "PHOI"
            elif "NON" in vat_the:
                giai_doan = "NON"
            elif "TRUONG-THANH" in vat_the:
                giai_doan = "TRUONG-THANH"
            elif LABEL_HU in vat_the:
                giai_doan = "HU"
            else:
                giai_doan = "PHOI"
            
            # Xác định vị trí nấm hư
            vi_tri_cum = set()
            if hop is not None and LABEL_HU in vat_the:
                cao = anh.shape[0]
                giua = cao // 2
                
                for h in hop:
                    class_id = int(h.cls[0])
                    nhan = model.names[class_id]
                    
                    if nhan != LABEL_HU:
                        continue
                    
                    x1, y1, x2, y2 = map(int, h.xyxy[0])
                    giua_y = (y1 + y2) // 2
                    
                    vi_tri = "TREN" if giua_y < giua else "DUOI"
                    vi_tri_cum.add(vi_tri)
            
            # Tổng hợp vị trí
            if "TREN" in vi_tri_cum and "DUOI" in vi_tri_cum:
                vi_tri_text = "TREN+DUOI"
            elif "TREN" in vi_tri_cum:
                vi_tri_text = "TREN"
            elif "DUOI" in vi_tri_cum:
                vi_tri_text = "DUOI"
            else:
                vi_tri_text = ""
            
            logger.info(f"🏷️ Kết quả: {giai_doan} - Vị trí: {vi_tri_text}")
            return giai_doan, vi_tri_text, anh
            
    except Exception as e:
        logger.error(f"❌ Lỗi nhận diện: {e}", exc_info=True)
        return None, None, None
        
    finally:
        if camera is not None:
            camera.release()

# ----------- WORKER TỰ ĐỘNG ------------
worker_running = True

def worker_tu_dong():
    """Worker tự động nhận diện"""
    logger.info("🤖 Khởi động worker tự động")
    
    while worker_running:
        try:
            logger.info("⏳ Chờ 60 giây...")  # Test với 60 giây trước
            time.sleep(60)
            
            logger.info("🔄 Đang nhận diện tự động...")
            giai_doan, vi_tri, anh = nhan_dien_nam()
            
            if giai_doan and anh is not None:
                # Gửi lên Google Sheets
                if GOOGLE_SHEETS_URL:
                    gui_len_google_sheets(giai_doan, vi_tri)
                
                # Lưu ảnh
                thoi_gian = datetime.now().strftime("%Y%m%d_%H%M%S")
                ten_file = f"/tmp/auto_{thoi_gian}.jpg"
                cv2.imwrite(ten_file, anh)
                logger.info(f"💾 Đã lưu ảnh: {ten_file}")
                
        except Exception as e:
            logger.error(f"❌ Lỗi worker: {e}")
            time.sleep(10)

# ----------- API ENDPOINTS ------------
@app.route("/")
def trang_chu():
    return """
    <h1>🍄 Hệ Thống Nhận Diện Nấm</h1>
    <p><strong>Trạng thái:</strong> Đang chạy</p>
    <p><strong>Endpoints:</strong></p>
    <ul>
        <li><a href="/nhan_dien">/nhan_dien</a> - Nhận diện thủ công</li>
        <li><a href="/trang_thai">/trang_thai</a> - Trạng thái hệ thống</li>
        <li><a href="/test_camera">/test_camera</a> - Test camera</li>
    </ul>
    """

@app.route("/nhan_dien")
def endpoint_nhan_dien():
    """Nhận diện thủ công"""
    logger.info("🔘 Nhận diện thủ công được gọi")
    
    giai_doan, vi_tri, anh = nhan_dien_nam()
    
    if giai_doan and anh is not None:
        # Lưu ảnh
        thoi_gian = datetime.now().strftime("%Y%m%d_%H%M%S")
        ten_anh = f"/tmp/manual_{thoi_gian}.jpg"
        cv2.imwrite(ten_anh, anh)
        
        # Gửi lên Google Sheets
        thanh_cong = False
        if GOOGLE_SHEETS_URL:
            thanh_cong = gui_len_google_sheets(giai_doan, vi_tri)
        
        return jsonify({
            "trang_thai": "thanh_cong",
            "giai_doan": giai_doan,
            "vi_tri": vi_tri,
            "anh": ten_anh,
            "gui_sheets": thanh_cong,
            "thoi_gian": thoi_gian
        })
    
    return jsonify({
        "trang_thai": "loi",
        "message": "Không thể nhận diện"
    }), 500

@app.route("/trang_thai")
def trang_thai():
    """Trạng thái hệ thống"""
    return jsonify({
        "he_thong": "hoat_dong",
        "model": os.path.exists(MODEL_PATH),
        "url_sheets": bool(GOOGLE_SHEETS_URL),
        "thoi_gian": datetime.now().isoformat(),
        "port": 2177
    })

@app.route("/test_camera")
def test_camera():
    """Test camera đơn giản"""
    try:
        camera = cv2.VideoCapture(0)
        time.sleep(1)
        success, frame = camera.read()
        camera.release()
        
        if success:
            cv2.imwrite("/tmp/test_camera.jpg", frame)
            return jsonify({
                "trang_thai": "thanh_cong",
                "message": "Camera hoạt động tốt",
                "kích_thước": f"{frame.shape}"
            })
        else:
            return jsonify({
                "trang_thai": "loi",
                "message": "Không đọc được camera"
            }), 500
            
    except Exception as e:
        return jsonify({
            "trang_thai": "loi",
            "message": str(e)
        }), 500

# ----------- XỬ LÝ TẮT ỨNG DỤNG ------------
import signal
import sys

def signal_handler(sig, frame):
    """Xử lý tín hiệu tắt"""
    global worker_running
    logger.info("🛑 Nhận tín hiệu tắt, đang dừng...")
    worker_running = False
    time.sleep(2)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ----------- KHỞI ĐỘNG ------------
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🚀 KHỞI ĐỘNG HỆ THỐNG NHẬN DIỆN NẤM")
    logger.info(f"📁 Model: {MODEL_PATH}")
    logger.info(f"📤 Google Sheets URL: {'✓' if GOOGLE_SHEETS_URL else '✗ Chưa cấu hình'}")
    logger.info(f"🌐 Port: 2177")
    logger.info("=" * 50)
    
    # Khởi động worker (tạm thời comment để test)
    # luong = threading.Thread(target=worker_tu_dong, daemon=True)
    # luong.start()
    
    # Chạy Flask server
    try:
        app.run(
            host="0.0.0.0",
            port=2177,
            debug=False,
            threaded=True,
            use_reloader=False
        )
    except Exception as e:
        logger.error(f"❌ Lỗi khởi động server: {e}")