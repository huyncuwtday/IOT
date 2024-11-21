from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import check_password_hash, generate_password_hash  # for password checking and hashing
import os
import paho.mqtt.client as mqtt
import mysql.connector
from mysql.connector import Error
import json


app = Flask(__name__)
app.secret_key = os.urandom(24)  # Needed for flash messages

# Thông tin kết nối MQTT
mqtt_server = "192.168.68.89"
mqtt_port = 1883             
mqtt_user = "admin"           
mqtt_password = "admin"       
mqtt_topic = "IOT"         

# Khởi tạo client MQTT
client = mqtt.Client()

# Cấu hình thông tin đăng nhập MQTT
client.username_pw_set(mqtt_user, mqtt_password)

# Hàm kết nối csdl
def get_db_connection():
    connection = mysql.connector.connect(
        host='localhost',       # Địa chỉ MySQL server
        database='iot',         # Tên cơ sở dữ liệu
        user='root',            # Tên người dùng
        password='1234567890' # Mật khẩu MySQL
    )
    return connection


# Hàm được gọi khi kết nối thành công
def on_connect(client, userdata, flags, rc):
    if rc == 0: 
      print(f"Đã kết nối đến MQTT broker với mã trạng thái {rc}")
      if not hasattr(client, '_subscribed'):  # Kiểm tra xem đã subscribe chưa
            client.subscribe(mqtt_topic)
            client._subscribed = True
            print(f"Subscribed to topic: {mqtt_topic}")
    else:
        print(f"Kết nối thất bại với mã lỗi: {rc}")
# Hàm nhận msg từ mqtt
def is_duplicate(status, mode):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT COUNT(*) FROM history WHERE status = %s AND mode = %s ORDER BY time DESC LIMIT 1"
        cursor.execute(query, (status, mode))
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count > 0  # Trả về True nếu đã có bản ghi trùng
    except Error as e:
        print(f"Lỗi khi kiểm tra trùng lặp: {e}")
        return False
def on_message(client, userdata, msg):
    try:
        print(f"Payload nhận được: {msg.payload.decode()}")
        # Giải mã dữ liệu JSON
        payload = msg.payload.decode()
        data = json.loads(payload)
        
        # Lấy thông tin 'mode' và 'status' từ dữ liệu JSON
        mode = data.get('mode')
        status = data.get('status')
        
        print(f"Nhận dữ liệu từ MQTT: mode={mode}, status={status}")
       
        #if not is_duplicate(status, mode):
        save_device_history("Light", status, mode) 
        update_device_status(status) 
    except Exception as e:
        print(f"Error while processing message: {e}")
        
def save_device_history(device_name, status, mode):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "INSERT INTO history (device_name, status, mode) VALUES (%s, %s, %s)"
        cursor.execute(query, (device_name, status, mode))
        conn.commit()
        cursor.close()
        conn.close()
    except Error as e:
        print(f"Lỗi khi lưu lịch sử: {e}")
# Hàm lấy lịch sử từ cơ sở dữ liệu
def get_history(page, per_page):
    offset = (page - 1) * per_page
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Truy vấn để lấy dữ liệu lịch sử và tổng số bản ghi trong cùng một lần
        query = """
            SELECT * FROM history ORDER BY time DESC LIMIT %s OFFSET %s;
            SELECT COUNT(*) FROM history;
        """
        cursor.execute(query, (per_page, offset))
        
        # Lấy dữ liệu lịch sử
        history = cursor.fetchall()
        
        # Di chuyển con trỏ đến kết quả của truy vấn thứ hai và lấy tổng số bản ghi
        cursor.nextset()
        total_records = cursor.fetchone()[0]
        
        # Tính tổng số trang
        total_pages = (total_records + per_page - 1) // per_page
        
        cursor.close()
        conn.close()
        
        return history, total_pages
    except Error as e:
        print(f"Lỗi khi lấy lịch sử: {e}")
        return [], 0

# Gắn callback khi kết nối thành công
client.on_connect = on_connect
client.on_message = on_message  # Gắn callback khi nhận tin nhắn
# Kết nối tới MQTT broker
client.connect(mqtt_server, mqtt_port, 60)

def update_device_status(status):
    global light_status  # Biến toàn cục lưu trạng thái đèn
    light_status = status  # Cập nhật trạng thái mới
# Hàm gửi lệnh bật/tắt đèn
def send_command(command):
    
    if command in ["ON", "OFF", "AUTO"]:
        # Gửi lệnh đến chủ đề MQTT mà ESP32 đang subscribe
       # client.publish(mqtt_topic, )
        
        # Gửi lệnh đến chủ đề MQTT mà ESP32 đang subscribe
        client.publish(mqtt_topic, command)
       
    else:
        print("Lệnh không hợp lệ. Chỉ có thể gửi 'ON', 'OFF', hoặc 'AUTO'.")

# Default user (using a hardcoded phone and password)
DEFAULT_USER = {
    'phone': '0123456789',
    'password': generate_password_hash('password123')  # Hashing the default password
}

# Route for login page
@app.route('/')
def login_page():
    return render_template('login.html')

# Route to handle login logic
@app.route('/login', methods=['POST'])
def login():
    phone = request.form['phone']
    password = request.form['password']
    
    # Check if the entered phone matches the default user
    if phone == DEFAULT_USER['phone'] and check_password_hash(DEFAULT_USER['password'], password):
        return redirect(url_for('home'))  # Redirect to 'home' after successful login
    else:
        flash("Đăng nhập thất bại. Vui lòng thử lại.", "error")  # Flash message for failed login
        return redirect(url_for('login_page'))

# Route for forgot password
@app.route('/forgot_password')
def forgot_password():
    return "Khôi phục mật khẩu - Liên kết gửi tới email."
light_status = "OFF"
# Route for home page
@app.route('/home')
def home():
    return render_template('index.html', light_status=light_status)

# Route for controlling the light
@app.route('/control_light', methods=['POST'])
def control_light():
    action = request.form['action']
    if action == 'turn_on':
        send_command('ON')  # Gửi lệnh bật đèn qua MQTT
        flash("Đèn đã được bật", "success")
    elif action == 'turn_off':
        send_command('OFF')  # Gửi lệnh tắt đèn qua MQTT
        flash("Đèn đã được tắt", "success")
    elif action == 'auto':
        send_command('AUTO')  # Gửi lệnh tự động qua MQTT
        flash("Đèn đã được chuyển sang chế độ tự động", "success")
    return redirect(url_for('control_light_page'))

# Route for light control page
@app.route('/control-light')
def control_light_page():
    return render_template('control-light.html')

# Route for history page
@app.route('/history')
def lich_su_bat_tat():
    page = request.args.get('page', 1, type=int)  # Lấy trang từ query string, mặc định là trang 1
    per_page = 10  # Số lượng bản ghi trên mỗi trang
    
    # Lấy dữ liệu lịch sử và tổng số trang từ hàm get_history_with_pagination
    history, total_pages = get_history(page, per_page)
    
    return render_template('history.html', history=history, page=page, total_pages=total_pages)

# Back to the main page
@app.route('/index')
def back_to_home():
    return redirect(url_for('home'))

if __name__ == '__main__':
   
    client.loop_start() 
    
    # Bắt đầu vòng lặp MQTT
    app.run(debug=True)