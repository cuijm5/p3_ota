"""
设备管理模块，负责：
1. 设备扫描
2. 设备连接
3. 设备状态管理
"""

import logging
import socket
import telnetlib
import threading
from typing import List, Dict

# 配置日志
logger = logging.getLogger(__name__)

class DeviceManager:
    """
    设备管理类，负责管理网络设备的扫描、连接和状态维护
    
    属性：
        devices: 当前发现的设备列表
        lock: 线程安全锁
    """
    def __init__(self):
        """
        初始化设备管理器
        """
        self.devices = []
        self.lock = threading.Lock()
        logger.info("设备管理器初始化完成")
        
    def scan_network(self) -> List[Dict]:
        """
        扫描局域网内的设备
        
        返回：
            List[Dict]: 发现的设备列表，每个设备包含ip和status字段
        """
        logger.info("开始扫描网络设备")
        base_ip = self.get_local_ip()
        if not base_ip:
            logger.warning("无法获取本地IP地址")
            return []
            
        network_prefix = '.'.join(base_ip.split('.')[:3])
        devices = []
        logger.info(f"扫描网络范围：{network_prefix}.1-100")
        
        # 扫描100个IP地址
        for i in range(1, 101):
            ip = f"{network_prefix}.{i}"
            logger.debug(f"正在扫描IP：{ip}")
            if self.ping_device(ip):
                logger.info(f"发现在线设备：{ip}")
                devices.append({
                    'ip': ip,
                    'status': '在线'
                })
        
        with self.lock:
            self.devices = devices
        logger.info(f"扫描完成，共发现{len(devices)}个设备")
        return devices
        
    def get_local_ip(self) -> str:
        """
        获取本机IP地址
        
        返回：
            str: 本机IP地址，获取失败返回空字符串
        """
        logger.info("获取本地IP地址")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            logger.info(f"获取到本地IP地址：{ip}")
            return ip
        except Exception as e:
            logger.error(f"获取本地IP地址失败：{str(e)}")
            return ""
            
    def ping_device(self, ip: str) -> bool:
        """
        Ping设备检查是否在线
        
        参数：
            ip: 目标设备IP地址
            
        返回：
            bool: 设备是否在线
        """
        logger.debug(f"Ping设备：{ip}")
        try:
            socket.setdefaulttimeout(1)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((ip, 80))
            s.close()
            logger.debug(f"设备在线：{ip}")
            return True
        except Exception as e:
            logger.debug(f"设备离线或无法连接：{ip} - {str(e)}")
            return False
            
    def connect(self, ip: str) -> str:
        """
        通过TELNET连接设备
        
        参数：
            ip: 目标设备IP地址
            
        返回：
            str: 连接结果信息
        """
        logger.info(f"尝试连接设备：{ip}")
        try:
            # 检查IP地址格式
            try:
                socket.inet_aton(ip)
            except socket.error:
                return f"IP地址格式错误：{ip}"
                
            # 尝试连接
            tn = telnetlib.Telnet(ip, timeout=5)
            
            # 登录认证
            tn.read_until(b"login: ")
            tn.write(b"root\n")
            tn.read_until(b"Password: ")
            tn.write(b"123456\n")
            
            # 验证登录成功
            index, _, _ = tn.expect([b"Login incorrect", b"#"], timeout=5)
            if index == 0:
                tn.close()
                return f"设备认证失败：{ip}（用户名或密码错误）"
                
            tn.close()
            logger.info(f"设备连接成功：{ip}")
            return "telnet连接成功"
            
        except ConnectionRefusedError:
            return f"连接被拒绝：{ip}（可能未开启Telnet服务）"
        except socket.timeout:
            return f"连接超时：{ip}（设备可能不在线）"
        except Exception as e:
            return f"连接失败：{ip} - {str(e)}"
            
    def get_devices(self) -> List[Dict]:
        """
        获取当前设备列表
        
        返回：
            List[Dict]: 设备列表的副本
        """
        logger.debug("获取设备列表")
        with self.lock:
            devices = self.devices.copy()
            logger.debug(f"当前设备数量：{len(devices)}")
            return devices
            
    def upload_firmware(self, ip: str, file_path: str) -> bool:
        """
        上传固件到指定设备
        
        参数：
            ip: 目标设备IP地址
            file_path: 本地固件文件路径
            
        返回：
            bool: 上传是否成功
        """
        logger.info(f"开始上传固件到设备：{ip}")
        try:
            # 连接到设备
            tn = telnetlib.Telnet(ip, timeout=10)
            
            # 登录认证
            tn.read_until(b"login: ")
            tn.write(b"root\n")
            tn.read_until(b"Password: ")
            tn.write(b"123456\n")
            
            # 验证登录成功
            index, _, _ = tn.expect([b"Login incorrect", b"#"])
            if index == 0:
                logger.error(f"设备认证失败：{ip}")
                return False
                
            # 发送固件上传命令
            tn.write(b"upload firmware\n")
            
            # 发送文件
            with open(file_path, 'rb') as f:
                while chunk := f.read(1024):
                    tn.write(chunk)
                    
            # 等待上传完成
            tn.write(b"exit\n")
            tn.close()
            
            logger.info(f"固件上传成功：{ip}")
            return True
        except Exception as e:
            logger.error(f"固件上传失败：{ip} - {str(e)}")
            return False
