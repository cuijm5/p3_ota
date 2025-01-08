"""
主应用模块，负责：
1. 文件上传接口
2. 设备管理接口
3. 启动GUI和Web服务
"""

import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import telnetlib
from device_manager import DeviceManager
from gui import UploaderGUI
import socket
import subprocess
import threading
import signal
import sys

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 创建格式化器
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 文件处理器（每次启动时清空日志）
file_handler = logging.FileHandler('app.log', mode='w')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

# 控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)

# 添加处理器
logger.addHandler(file_handler)
logger.addHandler(console_handler)

class FlaskAppWrapper:
    def __init__(self, app, host, port):
        self.app = app
        self.host = host
        self.port = port
        self.server = None
        self.thread = None

    def run(self):
        """在新线程中启动Flask服务器"""
        def run_server():
            self.app.run(
                host=self.host,
                port=self.port,
                debug=False,
                use_reloader=False,
                threaded=True
            )
        self.thread = threading.Thread(target=run_server)
        self.thread.daemon = True  # 设置为守护线程，这样主程序退出时会自动结束
        self.thread.start()
        logger.info(f"HTTP服务器启动于 http://{self.host}:{self.port}")

    def shutdown(self):
        """关闭Flask服务器"""
        logger.info("HTTP服务器将随主程序退出而关闭")

app = Flask(__name__)
CORS(app)  # 启用CORS支持
device_manager = DeviceManager()

# 获取本机IP地址
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        logger.error(f"获取本机IP失败: {str(e)}")
        return '0.0.0.0'

UPLOAD_FOLDER = os.path.abspath('../firmware')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
local_ip = get_local_ip()

# 系统诊断
logger.info("=== 系统诊断开始 ===")
logger.info(f"上传目录绝对路径：{UPLOAD_FOLDER}")
logger.info(f"本机IP地址：{local_ip}")
logger.info("=== 系统诊断结束 ===")

@app.before_request
def log_request_info():
    """记录每个请求的详细信息"""
    logger.debug('=== 收到新请求 ===')
    logger.debug(f'请求头: {dict(request.headers)}')
    logger.debug(f'请求方法: {request.method}')
    logger.debug(f'请求URL: {request.url}')
    logger.debug(f'请求参数: {dict(request.args)}')
    logger.debug(f'客户端IP: {request.remote_addr}')
    logger.debug(f'客户端信息: {request.user_agent}')
    logger.debug('=== 请求信息结束 ===')

def copy_firmware(src_path):
    """
    拷贝固件文件到firmware目录
    参数：
        src_path: 源文件路径
    返回：
        - 成功：目标文件路径
        - 失败：None
    """
    try:
        import shutil
        # 清理旧固件文件
        for old_file in os.listdir(UPLOAD_FOLDER):
            if old_file.endswith('.img'):
                os.remove(os.path.join(UPLOAD_FOLDER, old_file))
                logger.info(f"已删除旧固件文件：{old_file}")
        
        # 拷贝新固件文件
        filename = os.path.basename(src_path)
        dest_path = os.path.join(UPLOAD_FOLDER, filename)
        shutil.copy(src_path, dest_path)
        logger.info(f"文件拷贝成功：{src_path} -> {dest_path}")
        return dest_path
    except Exception as e:
        logger.error(f"文件拷贝失败：{str(e)}")
        return None

@app.route('/devices', methods=['GET'])
def get_devices():
    """
    获取当前连接的设备列表
    返回：
        - 200状态码和设备列表
    """
    logger.info("收到设备列表请求")
    try:
        devices = device_manager.get_devices()
        logger.info(f"获取到{len(devices)}个设备")
        return jsonify(devices), 200
    except Exception as e:
        logger.error(f"获取设备列表失败：{str(e)}")
        return jsonify({'error': 'Failed to get devices'}), 500

@app.route('/firmware/<path:filename>')
def serve_firmware(filename):
    """
    提供固件文件的下载服务
    参数：
        filename: 文件名
    返回：
        - 文件内容
        - 404 如果文件不存在
    """
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    logger.info(f"收到固件文件请求：{filename}")
    logger.debug(f"完整文件路径：{file_path}")
    logger.debug(f"请求来源：{request.remote_addr}")
    
    if not os.path.exists(file_path):
        logger.error(f"文件不存在：{file_path}")
        return jsonify({'error': 'File not found'}), 404
        
    if not os.path.isfile(file_path):
        logger.error(f"路径不是文件：{file_path}")
        return jsonify({'error': 'Not a file'}), 400
        
    try:
        logger.debug(f"尝试发送文件，文件大小：{os.path.getsize(file_path)} bytes")
        response = send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Cache-Control'] = 'no-cache'
        logger.info(f"文件发送成功：{filename}")
        return response
    except Exception as e:
        logger.error(f"文件访问失败：{str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    """
    主程序入口
    1. 启动GUI界面
    2. 启动Web服务
    """
    logger.info("启动应用程序")
    try:
        # 配置Flask应用
        app.config['PREFERRED_URL_SCHEME'] = 'http'
        app.config['PROXY_FIX_X_FOR'] = 0
        app.config['PROXY_FIX_X_PROTO'] = 0
        
        # 创建Flask服务器包装器
        flask_app = FlaskAppWrapper(app, '0.0.0.0', 5000)
        
        # 创建GUI并传入Flask服务器实例
        gui = UploaderGUI(device_manager, flask_app)
        logger.info("GUI初始化完成")
        
        # 启动HTTP服务器
        flask_app.run()
        logger.info(f"启动Web服务 http://{local_ip}:5000")
        
        # 运行GUI（这会阻塞直到GUI关闭）
        gui.run()
        
        logger.info("应用程序正常退出")
        
    except Exception as e:
        logger.error(f"应用程序启动失败：{str(e)}", exc_info=True)
        raise
    finally:
        # 确保程序完全退出
        sys.exit(0)
