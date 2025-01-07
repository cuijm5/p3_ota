"""
主应用模块，负责：
1. 文件上传接口
2. 设备管理接口
3. 启动GUI和Web服务
"""

import logging
from flask import Flask, request, jsonify
import os
import telnetlib
from device_manager import DeviceManager
from gui import UploaderGUI

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 创建格式化器
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 文件处理器（每次启动时清空日志）
file_handler = logging.FileHandler('app.log', mode='w')
file_handler.setFormatter(formatter)

# 控制台处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# 添加处理器
logger.addHandler(file_handler)
logger.addHandler(console_handler)

app = Flask(__name__)
device_manager = DeviceManager()

UPLOAD_FOLDER = 'firmware'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
logger.info(f"初始化完成，上传目录：{UPLOAD_FOLDER}")

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

if __name__ == '__main__':
    """
    主程序入口
    1. 启动GUI界面
    2. 启动Web服务
    """
    logger.info("启动应用程序")
    try:
        gui = UploaderGUI(device_manager)
        logger.info("GUI初始化完成")
        gui.run()
        logger.info("启动Web服务")
        app.run(host='0.0.0.0', port=5000)
    except Exception as e:
        logger.error(f"应用程序启动失败：{str(e)}")
        raise
