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
logger.setLevel(logging.DEBUG)

# 创建文件日志处理器
file_handler = logging.FileHandler('scan_debug.log')
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

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
        logger.info(f"扫描网络范围：{network_prefix}.1-255")
        
        # 使用线程池并发扫描
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def scan_single_ip(ip):
            """扫描单个IP地址"""
            logger.debug(f"正在扫描IP：{ip}")
            if self.telnet_check_device(ip):
                logger.info(f"发现有效设备：{ip}")
                device_info = {
                    'ip': ip,
                    'status': '在线'
                }
                logger.debug(f"设备详细信息：{device_info}")
                return device_info
            return None
            
        # 创建线程池，最大并发数100
        with ThreadPoolExecutor(max_workers=100) as executor:
            # 提交所有扫描任务
            futures = {
                executor.submit(scan_single_ip, f"{network_prefix}.{i}"): i
                for i in range(1, 256)
            }
            
            # 显示进度
            total = len(futures)
            completed = 0
            for future in as_completed(futures):
                completed += 1
                if completed % 10 == 0 or completed == total:
                    logger.info(f"扫描进度：{completed}/{total} ({completed/total*100:.1f}%)")
                
                result = future.result()
                if result:
                    devices.append(result)
        
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
            
    def telnet_check_device(self, ip: str) -> bool:
        """
        通过telnet检查设备是否在线并验证NX5标识
        
        参数：
            ip: 目标设备IP地址
            
        返回：
            bool: 设备是否在线且包含NX5标识
        """
        logger.debug(f"Telnet检查设备：{ip}")
        try:
            tn = telnetlib.Telnet(ip, timeout=2)
            # 读取欢迎信息
            index, match, text = tn.expect([b"NX5"], timeout=2)
            
            if index == -1:
                logger.debug(f"设备未包含NX5标识：{ip}")
                tn.close()
                return False
                
            # 尝试登录
            tn.read_until(b"login: ")
            tn.write(b"root\n")
            tn.read_until(b"Password: ")
            tn.write(b"123456\n")
            
            # 验证登录成功
            index, _, _ = tn.expect([b"Login incorrect", b"#"], timeout=2)
            tn.close()
            
            if index == 0:
                logger.debug(f"设备登录失败：{ip}")
                return False
                
            logger.debug(f"设备检查成功：{ip}")
            return True
        except Exception as e:
            logger.debug(f"设备无法连接：{ip} - {str(e)}")
            return False
            
    def connect(self, ip: str) -> dict:
        """
        通过TELNET连接设备并获取版本信息
        
        参数：
            ip: 目标设备IP地址
            
        返回：
            dict: 包含连接结果和版本信息的字典
        """
        logger.info(f"尝试连接设备：{ip}")
        try:
            # 检查IP地址格式
            try:
                socket.inet_aton(ip)
            except socket.error:
                return {"status": "error", "message": f"IP地址格式错误：{ip}"}
                
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
                return {"status": "error", "message": f"设备认证失败：{ip}（用户名或密码错误）"}

            # 执行获取版本命令
            tn.write(b"cat /data/etc/version\n")
            # 等待命令执行完成并读取输出
            response = tn.read_until(b"#", timeout=5).decode('utf-8')
            print("命令输出原始内容：")
            print("="*50)
            print(response)
            print("="*50)
            logger.debug(f"版本命令输出：{response}")  # 添加日志以便调试
            
            # 解析版本信息
            version = "未知"
            print("\n逐行解析内容：")
            print("-"*50)
            for line in response.split('\n'):
                line = line.strip()
                print(f"当前解析行: [{line}]")
                logger.debug(f"解析行：{line}")  # 添加日志以便调试
                if "VERSION" in line:
                    try:
                        version = line.split('=')[1].strip()
                        print(f"找到版本行，解析结果: {version}")
                        logger.info(f"成功解析到版本号：{version}")
                    except IndexError:
                        print(f"版本行格式解析失败: {line}")
                        logger.warning(f"版本行格式不正确：{line}")
                    break
            print("-"*50)
            
            tn.close()
            logger.info(f"设备连接成功：{ip}，版本号：{version}")
            return {"status": "success", "message": "telnet连接成功", "version": version}
            
        except ConnectionRefusedError:
            return {"status": "error", "message": f"连接被拒绝：{ip}（可能未开启Telnet服务）"}
        except socket.timeout:
            return {"status": "error", "message": f"连接超时：{ip}（设备可能不在线）"}
        except Exception as e:
            return {"status": "error", "message": f"连接失败：{ip} - {str(e)}"}
            
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
