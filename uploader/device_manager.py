"""
设备管理模块，负责：
1. 设备扫描
2. 设备连接
3. 设备状态管理
"""

import logging
from logging.handlers import RotatingFileHandler
import socket
import telnetlib
import threading
import re
from typing import List, Dict, Callable
import time
import os

def setup_logging():
    """配置日志系统"""
    # 获取根日志记录器并设置级别
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)  # 将全局日志级别设为INFO
    
    # 获取模块日志记录器
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)  # 将模块日志级别设为INFO
    
    # 移除所有已存在的处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 获取uploader目录的路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 如果日志文件已存在且大于1MB，则删除它和它的备份文件
    log_file = os.path.join(current_dir, 'scan_debug.log')
    backup_file = os.path.join(current_dir, 'scan_debug.log.1')
    
    try:
        if os.path.exists(log_file):
            if os.path.getsize(log_file) > 1024*1024:  # 改为1MB
                os.remove(log_file)
                print(f"已删除过大的日志文件: {log_file}")
        if os.path.exists(backup_file):
            if os.path.getsize(backup_file) > 1024*1024:  # 改为1MB
                os.remove(backup_file)
                print(f"已删除过大的备份文件: {backup_file}")
    except Exception as e:
        print(f"清理日志文件时出错: {e}")
    
    # 创建RotatingFileHandler，限制文件大小为1MB
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=1024*1024,  # 改为1MB
            backupCount=1,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)  # 将文件日志级别设为INFO
        
        # 使用更简洁的日志格式
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        file_handler.setFormatter(formatter)
        
        # 添加过滤器，过滤掉一些不必要的DEBUG日志
        class LogFilter(logging.Filter):
            def filter(self, record):
                # 过滤掉一些频繁的DEBUG日志
                if record.levelno == logging.DEBUG:
                    msg = record.getMessage()
                    if "正在扫描IP" in msg or "设备详细信息" in msg:
                        return False
                return True
        
        file_handler.addFilter(LogFilter())
        logger.addHandler(file_handler)
        
        # 同时将日志输出到控制台
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
    except Exception as e:
        print(f"设置日志处理器时出错: {e}")
    
    return logger

# 配置日志
logger = setup_logging()

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
        通过TELNET连接设备并获取版本信息和PID
        
        参数：
            ip: 目标设备IP地址
            
        返回：
            dict: 包含连接结果、版本信息和PID的字典
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
            logger.debug(f"版本命令输出：{response}")
            
            # 解析版本信息
            version = "未知"
            for line in response.split('\n'):
                line = line.strip()
                logger.debug(f"解析行：{line}")
                if "VERSION" in line:
                    try:
                        version = line.split('=')[1].strip()
                        logger.info(f"成功解析到版本号：{version}")
                    except IndexError:
                        logger.warning(f"版本行格式不正确：{line}")
                    break

            # 获取gateway.conf中的pid和did
            # 先清除可能的缓存内容
            tn.write(b"\n")
            tn.read_until(b"#", timeout=2)

            # 使用grep直接获取pid和did行
            tn.write(b'grep -E "pid|did" /data/etc/gateway.conf\n')
            config_response = tn.read_until(b"#", timeout=5).decode('utf-8')
            logger.debug(f"grep pid和did输出：\n{config_response}")

            # 如果grep方式失败，尝试读取整个文件
            if "pid" not in config_response.lower() or "did" not in config_response.lower():
                tn.write(b"cat /data/etc/gateway.conf\n")
                gateway_response = tn.read_until(b"#", timeout=5).decode('utf-8')
                logger.debug(f"gateway.conf完整输出：\n{gateway_response}")
                config_response = gateway_response

            # 解析pid和did
            pid = "未知"
            did = "未知"
            try:
                # 尝试方法1：直接查找行
                for line in config_response.split('\n'):
                    line = line.strip()
                    logger.debug(f"正在解析行: [{line}]")
                    if '"pid":' in line:
                        # 提取数字
                        import re
                        numbers = re.findall(r'\d+', line)
                        if numbers:
                            pid = numbers[0]
                            logger.info(f"方法1成功解析到PID：{pid}")
                    elif '"did":' in line:
                        # 提取did（在引号之间的内容）
                        import re
                        did_match = re.search(r'"did":\s*"([^"]+)"', line)
                        if did_match:
                            did = did_match.group(1)
                            logger.info(f"方法1成功解析到DID：{did}")

                # 如果方法1失败，尝试方法2：JSON解析
                if pid == "未知" or did == "未知":
                    logger.debug("尝试JSON解析方法")
                    import json
                    # 查找JSON内容的开始和结束
                    start_idx = config_response.find('{')
                    end_idx = config_response.rfind('}')
                    if start_idx != -1 and end_idx != -1:
                        json_text = config_response[start_idx:end_idx+1]
                        logger.debug(f"提取的JSON文本：{json_text}")
                        config = json.loads(json_text)
                        if 'pid' in config:
                            pid = str(config['pid'])
                            logger.info(f"方法2成功解析到PID：{pid}")
                        if 'did' in config:
                            did = str(config['did'])
                            logger.info(f"方法2成功解析到DID：{did}")

            except Exception as e:
                logger.error(f"解析配置失败：{str(e)}")
                logger.exception("详细错误堆栈：")

            tn.close()
            logger.info(f"设备连接成功：{ip}，版本号：{version}，PID：{pid}，DID：{did}")
            return {"status": "success", "message": "telnet连接成功", "version": version, "pid": pid, "did": did}
            
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

    def monitor_download(self, tn: telnetlib.Telnet, ip: str, callback) -> dict:
        """
        监控wget下载进度
        
        参数：
            tn: telnet连接实例
            ip: 设备IP地址
            callback: 进度回调函数
            
        返回：
            dict: 下载状态信息
        """
        try:
            last_progress = 0
            no_progress_count = 0
            max_no_progress = 10  # 最大允许无进度次数
            download_completed = False  # 标记是否已经完成下载
            
            while True:
                # 读取wget输出
                data = tn.read_until(b"\n", timeout=1)
                if not data:
                    if download_completed:
                        # 等待命令提示符
                        final_check = tn.read_until(b"#", timeout=5).decode('utf-8')
                        if '#' in final_check:
                            return {"status": "success", "progress": 100}
                    no_progress_count += 1
                    if no_progress_count > max_no_progress:
                        error_msg = "下载停滞不前"
                        logger.error(f"设备[{ip}] {error_msg}")
                        return {"status": "error", "message": error_msg}
                    continue
                    
                output = data.decode('utf-8', errors='ignore')
                logger.debug(f"设备[{ip}] wget输出: {output}")
                
                # 检查是否下载完成
                if any(sign in output.lower() for sign in ["saved", "100%", "'ota.img' saved"]):
                    logger.info(f"设备[{ip}] 下载完成")
                    callback(ip, 100)  # 确保显示100%
                    download_completed = True
                    continue  # 继续等待命令提示符
                
                # 匹配进度信息
                if "%" in output:
                    try:
                        # 提取进度百分比
                        percent = int(re.search(r'(\d+)%', output).group(1))
                        logger.info(f"设备[{ip}] 下载进度: {percent}%")
                        callback(ip, percent)  # 调用回调函数更新进度
                        
                        # 检查进度是否停滞
                        if percent > last_progress:
                            last_progress = percent
                            no_progress_count = 0
                        else:
                            no_progress_count += 1
                            if no_progress_count > max_no_progress:
                                error_msg = "下载进度停滞"
                                logger.error(f"设备[{ip}] {error_msg}")
                                return {"status": "error", "message": error_msg}
                    except (AttributeError, ValueError) as e:
                        logger.warning(f"设备[{ip}] 解析进度失败: {str(e)}")
                    
                # 检查是否出现错误
                if any(err in output.lower() for err in ["error", "failed", "unable to", "cannot"]):
                    error_msg = f"下载失败: {output}"
                    logger.error(f"设备[{ip}] {error_msg}")
                    return {"status": "error", "message": error_msg}
                    
                # 检查是否返回到命令提示符
                if output.strip().endswith('#'):
                    if not download_completed:
                        error_msg = "下载未完成就返回提示符"
                        logger.error(f"设备[{ip}] {error_msg}")
                        return {"status": "error", "message": error_msg}
                    else:
                        return {"status": "success", "progress": 100}
                    
        except Exception as e:
            error_msg = f"监控下载异常: {str(e)}"
            logger.error(f"设备[{ip}] {error_msg}")
            return {"status": "error", "message": error_msg}
            
    def get_file_md5(self, file_path: str) -> str:
        """
        计算文件的MD5值
        
        参数：
            file_path: 文件路径
            
        返回：
            str: MD5值
        """
        import hashlib
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            # 每次读取4M数据
            for chunk in iter(lambda: f.read(4096 * 1024), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()

    def download_firmware(self, ip: str, wget_cmd: str, progress_callback) -> dict:
        """
        通过wget下载固件到设备
        
        参数：
            ip: 设备IP地址
            wget_cmd: wget命令
            progress_callback: 进度回调函数
            
        返回：
            dict: 下载状态信息
        """
        logger.info(f"开始下载固件到设备 {ip}")
        logger.debug(f"wget命令: {wget_cmd}")
        
        # 获取服务器上固件文件的信息
        import os
        firmware_dir = '../firmware'
        img_files = [f for f in os.listdir(firmware_dir) if f.endswith('.img')]
        if not img_files:
            return {"status": "error", "message": "服务器上未找到固件文件"}
        
        firmware_path = os.path.join(firmware_dir, img_files[0])
        server_file_size = os.path.getsize(firmware_path)
        server_md5 = self.get_file_md5(firmware_path)
        logger.info(f"服务器固件文件大小: {server_file_size} 字节, MD5: {server_md5}")
        
        max_retries = 3  # 最大重试次数
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                if retry_count > 0:
                    logger.info(f"设备[{ip}] 开始第{retry_count + 1}次尝试下载")
                    progress_callback(ip, 0)  # 重置进度
                
                # 连接设备
                tn = telnetlib.Telnet(ip, timeout=5)
                
                # 登录认证
                tn.read_until(b"login: ", timeout=5)
                tn.write(b"root\n")
                tn.read_until(b"Password: ", timeout=5)
                tn.write(b"123456\n")
                
                # 验证登录成功
                index, _, _ = tn.expect([b"Login incorrect", b"#"], timeout=5)
                if index == 0:
                    error_msg = "设备登录失败"
                    logger.error(f"{error_msg}: {ip}")
                    tn.close()
                    return {"status": "error", "message": error_msg}
                
                # 检查并清理/tmp目录中的.img文件
                logger.info(f"检查设备[{ip}] /tmp目录")
                tn.write(b"ls /tmp/*.img 2>/dev/null\n")
                response = tn.read_until(b"#", timeout=5).decode('utf-8')
                if ".img" in response:
                    logger.info(f"设备[{ip}] 发现旧的.img文件，正在删除")
                    tn.write(b"rm -f /tmp/*.img\n")
                    tn.read_until(b"#", timeout=5)
                    logger.info(f"设备[{ip}] 旧的.img文件已删除")
                
                # 执行wget命令前先清理缓存
                tn.write(b"sync; echo 3 > /proc/sys/vm/drop_caches\n")
                tn.read_until(b"#", timeout=5)
                
                # 执行wget命令
                tn.write(wget_cmd.encode())
                
                # 监控下载进度
                result = self.monitor_download(tn, ip, progress_callback)
                
                # 如果下载成功，验证文件完整性
                if result["status"] == "success":
                    try:
                        progress_callback(ip, 100, "正在验证文件...")
                        
                        # 检查文件大小
                        tn.write(b"ls -l /tmp/ota.img\n")
                        ls_response = tn.read_until(b"#", timeout=5).decode('utf-8')
                        if "ota.img" not in ls_response:
                            raise Exception("文件下载不完整")
                        
                        # 解析文件大小
                        import re
                        size_match = re.search(r'root\s+root\s+(\d+)\s+', ls_response)
                        if not size_match:
                            raise Exception("无法获取文件大小")
                        
                        device_file_size = int(size_match.group(1))
                        if device_file_size != server_file_size:
                            raise Exception(f"文件大小不匹配: 设备上{device_file_size}字节, 服务器上{server_file_size}字节")
                        
                        # 计算设备上文件的MD5
                        progress_callback(ip, 100, "正在计算MD5...")
                        
                        # 确保我们在telnet连接中
                        tn.write(b"\n")  # 发送一个换行，确保我们在命令行
                        response = tn.read_until(b"#", timeout=5).decode('utf-8')
                        if '#' not in response:
                            raise Exception("无法访问设备命令行")
                            
                        # 执行md5sum命令并等待完成
                        logger.info(f"设备[{ip}] 开始计算MD5...")
                        tn.write(b"md5sum /tmp/ota.img\n")
                        
                        # 读取直到遇到下一个命令提示符
                        md5_response = ""
                        while True:
                            chunk = tn.read_until(b"#", timeout=30).decode('utf-8')
                            md5_response += chunk
                            if '#' in chunk:
                                break
                                
                        logger.info(f"设备[{ip}] MD5计算原始响应:\n{md5_response}")
                        
                        # 从响应中提取MD5值
                        md5_lines = md5_response.strip().split('\n')
                        device_md5 = None
                        for line in md5_lines:
                            # 跳过命令行本身
                            if line.strip().startswith('md5sum'):
                                continue
                            # 查找包含ota.img的行
                            if '/tmp/ota.img' in line:
                                parts = line.strip().split()
                                if len(parts) >= 1:
                                    device_md5 = parts[0].strip()
                                break
                                
                        if not device_md5:
                            logger.error(f"设备[{ip}] 无法从响应中提取MD5值")
                            logger.error(f"完整响应:\n{md5_response}")
                            raise Exception("无法获取设备MD5值")
                            
                        # 验证MD5值的格式（应该是32位十六进制）
                        if not re.match(r'^[a-fA-F0-9]{32}$', device_md5):
                            logger.error(f"设备[{ip}] MD5值格式不正确")
                            logger.error(f"提取的MD5值: [{device_md5}]")
                            raise Exception("设备返回的MD5值格式不正确")
                            
                        logger.info(f"设备[{ip}] MD5对比:")
                        logger.info(f"服务器MD5: [{server_md5}]")
                        logger.info(f"设备MD5:   [{device_md5}]")
                        
                        if device_md5.lower() != server_md5.lower():
                            raise Exception(f"MD5校验失败: 设备上{device_md5}, 服务器上{server_md5}")
                        
                        logger.info(f"设备[{ip}] 文件完整性验证成功")
                        progress_callback(ip, 100, "下载成功")
                        tn.close()
                        return {"status": "success", "message": "下载完成"}
                        
                    except Exception as e:
                        last_error = str(e)
                        retry_count += 1
                        if retry_count < max_retries:
                            logger.error(f"设备[{ip}] 验证失败详细信息:")
                            logger.error(f"错误类型: {type(e).__name__}")
                            logger.error(f"错误信息: {last_error}")
                            logger.error("-" * 50)
                            logger.error("MD5详细信息:")
                            logger.error(f"服务器MD5: [{server_md5}] (长度: {len(server_md5)})")
                            logger.error(f"设备响应原文:\n{md5_response}")
                            device_md5 = md5_response.split()[0].strip() if md5_response.split() else "未获取到MD5"
                            logger.error(f"提取的设备MD5: [{device_md5}] (长度: {len(device_md5)})")
                            logger.error("-" * 50)
                            
                            # 显示倒计时
                            for i in range(5, 0, -1):
                                progress_callback(ip, 100, f"验证失败，{i}秒后重试...")
                                time.sleep(1)
                                
                            logger.warning(f"设备[{ip}] 验证失败: {last_error}，将进行第{retry_count + 1}次重试")
                            tn.write(b"rm -f /tmp/*.img\n")  # 清理不完整的文件
                            tn.read_until(b"#", timeout=5)
                            tn.close()
                            continue
                        else:
                            tn.close()
                            return {"status": "error", "message": f"验证失败（重试{max_retries}次）: {last_error}"}
                
                # 如果下载失败
                last_error = result.get("message", "未知错误")
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"设备[{ip}] 下载失败: {last_error}，将进行第{retry_count + 1}次重试")
                    tn.write(b"rm -f /tmp/*.img\n")  # 清理不完整的文件
                    tn.read_until(b"#", timeout=5)
                    tn.close()
                    import time
                    time.sleep(3)  # 等待3秒后重试
                else:
                    tn.close()
                    return {"status": "error", "message": f"下载失败（重试{max_retries}次）: {last_error}"}
                    
            except Exception as e:
                last_error = str(e)
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"设备[{ip}] 发生异常: {last_error}，将进行第{retry_count + 1}次重试")
                    import time
                    time.sleep(3)  # 等待3秒后重试
                else:
                    return {"status": "error", "message": f"下载失败（重试{max_retries}次）: {last_error}"}
        
        return {"status": "error", "message": f"达到最大重试次数，最后错误: {last_error}"}
