from flask import Flask, jsonify, render_template, request, redirect, url_for, flash
from werkzeug.security import check_password_hash, generate_password_hash  
import os
import paho.mqtt.client as mqtt
import mysql.connector
from mysql.connector import Error
import json


app = Flask(__name__)
app.secret_key = os.urandom(24)  

# Thông tin kết nối MQTT
mqtt_server = " 192.168.132.68"  
mqtt_port = 1883              
mqtt_user = "admin"           
mqtt_password = "admin"       
mqtt_topic = "IOT"         


# Hàm kết nối csdl
def get_db_connection():
    connection = mysql.connector.connect(
        host='localhost',       
        database='iot',         
        user='root',            
        password='1234567890' 
    )
    return connection
def is_duplicate(status, mode):   
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Lấy bản ghi cuối cùng từ cơ sở dữ liệu
        query = "SELECT status, mode FROM history ORDER BY id DESC LIMIT 1"
        cursor.execute(query)
        last_record = cursor.fetchone()
        print(last_record)
        cursor.close()
        conn.close()
        
        if last_record:  # Nếu có bản ghi
            last_status, last_mode = last_record
            return last_status == status and last_mode == mode
        return False  
    except Error as e:
      print(f"Lỗi khi kiểm tra trùng lặp: {e}")
      return False      
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
# Hàm nhận msg từ mqtt
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
        update_device_status(status) 
        if not is_duplicate(status, mode):
            save_device_history("Light", status, mode)  
        else:
            print("Tin nhắn trùng lặp, bỏ qua.")    
        
    except Exception as e:
        print(f"Error while processing message: {e}")
  
# Khởi tạo client MQTT
client = mqtt.Client(clean_session=True)
client.on_message = on_message  
client.username_pw_set(mqtt_user, mqtt_password)
#Hàm lấy lịch sử từ cơ sở dữ liệu
def get_history(page, per_page, selected_date=None):
    offset = (page - 1) * per_page
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Nếu selected_date không phải None, thêm điều kiện lọc theo ngày vào truy vấn
        query = """
            SELECT * FROM history
            WHERE DATE(time) = %s
            ORDER BY id DESC
            LIMIT %s OFFSET %s;
            SELECT COUNT(*) FROM history WHERE DATE(time) = %s;
        """ if selected_date else """
            SELECT * FROM history ORDER BY id DESC LIMIT %s OFFSET %s;
            SELECT COUNT(*) FROM history;
        """
        
        if selected_date:
            cursor.execute(query, (selected_date, per_page, offset, selected_date))
        else:
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

# Hàm được gọi khi kết nối thành công
def on_connect(client, userdata, flags, rc):
    if rc == 0: 
      print(f"Đã kết nối đến MQTT broker với mã trạng thái {rc}")
      client.subscribe(mqtt_topic)


# Gắn callback khi kết nối thành công
client.on_connect = on_connect

global light_status
light_status= "OFF"
def update_device_status(status):
    global light_status  # Biến toàn cục lưu trạng thái đèn
    light_status = status  # Cập nhật trạng thái mới

# Hàm gửi lệnh bật/tắt đèn
def send_command(command):    
    if command in ["ON", "OFF", "AUTO"]:        
        # Gửi lệnh đến chủ đề MQTT mà ESP32 đang subscribe
        client.publish(mqtt_topic, command)
       
    else:
        print("Lệnh không hợp lệ. Chỉ có thể gửi 'ON', 'OFF', hoặc 'AUTO'.")

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
    if not phone or not password:
        flash("Vui lòng nhập cả số điện thoại và mật khẩu.", "error")
        return redirect(url_for('login_page'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Truy vấn để lấy thông tin người dùng theo số điện thoại
        query = "SELECT account_id, username, password, phonenumber FROM account WHERE phonenumber = %s"
        cursor.execute(query, (phone,))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()

        if user and user['password'] == password: 
            # Đăng nhập thành công
            flash("Đăng nhập thành công!", "success")
            return redirect(url_for('home'))  
        else:
            # Thông tin đăng nhập không hợp lệ
            flash("Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin.", "error")
            return redirect(url_for('login_page'))
            
    except Exception as e:
        print(f"Lỗi khi đăng nhập: {e}")
        flash(f"Lỗi trong quá trình đăng nhập: {e}", "error")
        return redirect(url_for('login_page'))

# Route for forgot password
@app.route('/forgot_password')
def forgot_password():
    return "Khôi phục mật khẩu - Liên kết gửi tới email."

# Route for home page
@app.route('/home')
def home():
    return render_template('index.html', light_status=light_status)

# Route for controlling the light
@app.route('/control_light', methods=['GET','POST'])
def control_light():
    action = request.form['action']
    if action == 'turn_on':
        send_command('ON')  
        flash("Đèn đã được bật", "success")
        light_state = 'turn_on'
    elif action == 'turn_off':
        send_command('OFF')  
        flash("Đèn đã được tắt", "success")
        light_state = 'turn_off'
    elif action == 'auto':
        send_command('AUTO')  
        flash("Đèn đã được chuyển sang chế độ tự động", "success")
        light_state = 'auto'
    return jsonify({'success': True, 'state':light_state})

# Route for light control page
@app.route('/control-light')
def control_light_page():
    return render_template('control-light.html')

# Route for history page
@app.route('/history', methods=['GET', 'POST'])
def lich_su_bat_tat():
    page = request.args.get('page', 1, type=int)  # Lấy trang từ query string, mặc định là trang 1
    per_page = 10  
    selected_date = request.form.get('date')  # Lấy ngày từ form 
    
    # Lấy dữ liệu lịch sử và tổng số trang từ 
    history, total_pages = get_history(page, per_page, selected_date)
    
    return render_template('history.html', history=history, page=page, total_pages=total_pages, selected_date=selected_date)
# Back to the main page
@app.route('/index')
def back_to_home():
    return redirect(url_for('home'))

if __name__ == '__main__':
    client.connect(mqtt_server, mqtt_port)
    client.loop_start() 
    
    # Bắt đầu vòng lặp MQTT
    app.run(debug=True)
