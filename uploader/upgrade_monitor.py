import logging
import telnetlib
import time
import threading
from typing import Dict, Callable
import re

logger = logging.getLogger(__name__)

class UpgradeMonitor:
    """升级监控类，用于跟踪设备升级状态"""
    
    def __init__(self):
        self.monitors: Dict[str, threading.Thread] = {}  # 存储每个设备的监控线程
        self.stop_flags: Dict[str, bool] = {}  # 存储每个设备的停止标志
        
    def start_monitor(self, ip: str, target_version: str, status_callback: Callable[[str, str, str, dict], None]):
        """
        开始监控设备升级状态
        
        参数：
            ip: 设备IP地址
            target_version: 目标版本号
            status_callback: 状态回调函数，参数为(ip, status, color, device_info)
        """
        if ip in self.monitors and self.monitors[ip].is_alive():
            logger.warning(f"设备[{ip}]已在监控中")
            return
            
        self.stop_flags[ip] = False
        monitor_thread = threading.Thread(
            target=self._monitor_device,
            args=(ip, target_version, status_callback),
            name=f"upgrade_monitor_{ip}"
        )
        monitor_thread.daemon = True
        self.monitors[ip] = monitor_thread
        monitor_thread.start()
        logger.info(f"开始监控设备[{ip}]升级状态")
        
    def stop_monitor(self, ip: str):
        """停止监控指定设备"""
        if ip in self.stop_flags:
            self.stop_flags[ip] = True
            logger.info(f"停止监控设备[{ip}]升级状态")
            
    def stop_all(self):
        """停止所有设备的监控"""
        for ip in list(self.stop_flags.keys()):
            self.stop_monitor(ip)
            
    def _monitor_device(self, ip: str, target_version: str, status_callback: Callable[[str, str, str, dict], None]):
        """
        监控设备升级状态的内部方法
        
        参数：
            ip: 设备IP地址
            target_version: 目标版本号
            status_callback: 状态回调函数，参数为(ip, status, color, device_info)
        """
        logger.info(f"========== 开始监控设备升级状态 [{ip}] ==========")
        logger.info(f"[{ip}] 目标版本号: {target_version}")
        
        # 首次检查前等待60秒，让设备有足够时间开始升级
        logger.info(f"[{ip}] 等待60秒后开始首次检查")
        time.sleep(60)
        logger.info(f"[{ip}] 开始检查升级状态")
        
        start_time = time.time()
        timeout = 300  # 5分钟超时
        
        while not self.stop_flags.get(ip, True):
            current_time = time.time()
            elapsed_time = current_time - start_time
            logger.info(f"[{ip}] 已监控时间: {int(elapsed_time)}秒")
            
            # 检查是否超时
            if current_time - start_time > timeout:
                logger.warning(f"[{ip}] 升级超时 (已经过{int(elapsed_time)}秒)")
                status_callback(ip, "升级超时", "yellow", None)
                return  # 直接返回，不再继续检查
                
            try:
                # 尝试telnet连接
                logger.info(f"[{ip}] 尝试telnet连接")
                tn = telnetlib.Telnet(ip, timeout=5)
                
                try:
                    # 登录认证
                    logger.info(f"[{ip}] 等待登录提示")
                    tn.read_until(b"login: ", timeout=5)
                    tn.write(b"root\n")
                    logger.info(f"[{ip}] 等待密码提示")
                    tn.read_until(b"Password: ", timeout=5)
                    tn.write(b"123456\n")
                    
                    # 验证登录成功
                    logger.info(f"[{ip}] 验证登录结果")
                    index, _, _ = tn.expect([b"Login incorrect", b"#"], timeout=5)
                    if index == 0:
                        logger.error(f"[{ip}] 登录失败")
                        raise Exception("登录失败")
                    logger.info(f"[{ip}] 登录成功")
                        
                    # 获取版本号
                    logger.info(f"[{ip}] 获取版本号")
                    tn.write(b"cat /data/etc/version\n")
                    response = tn.read_until(b"#", timeout=5).decode('utf-8')
                    logger.info(f"[{ip}] 版本文件内容：\n{response}")
                    
                    # 解析版本号
                    current_version = "未知"
                    for line in response.split('\n'):
                        line = line.strip()
                        if "VERSION=" in line:  # 修改为精确匹配VERSION=
                            try:
                                # 提取版本号，处理格式：VERSION=4.4.1(12)
                                version_line = line.split('VERSION=')[1].strip()
                                logger.info(f"[{ip}] 提取到的版本行：{version_line}")
                                
                                # 直接使用提取到的版本号，不做额外处理
                                current_version = version_line
                                logger.info(f"[{ip}] 当前版本号：{current_version}，目标版本号：{target_version}")
                                
                                # 如果版本号匹配目标版本
                                if current_version == target_version:
                                    logger.info(f"[{ip}] 版本号匹配，升级成功")
                                    
                                    # 获取设备配置信息
                                    tn.write(b'grep -E "pid|did" /data/etc/gateway.conf\n')
                                    config_response = tn.read_until(b"#", timeout=5).decode('utf-8')
                                    logger.info(f"[{ip}] 设备配置信息：\n{config_response}")
                                    
                                    # 解析pid和did
                                    pid = "未知"
                                    did = "未知"
                                    for config_line in config_response.split('\n'):
                                        config_line = config_line.strip()
                                        if '"pid":' in config_line:
                                            numbers = re.findall(r'\d+', config_line)
                                            if numbers:
                                                pid = numbers[0]
                                        elif '"did":' in config_line:
                                            did_match = re.search(r'"did":\s*"([^"]+)"', config_line)
                                            if did_match:
                                                did = did_match.group(1)
                                    
                                    # 更新设备状态和信息
                                    device_info = {
                                        "version": current_version,
                                        "pid": pid,
                                        "did": did,
                                        "need_upgrade": "版本已是最新"
                                    }
                                    status_callback(ip, "升级成功", "green", device_info)
                                    return  # 升级成功，直接返回
                                else:
                                    logger.info(f"[{ip}] 版本号不匹配：当前[{current_version}]，目标[{target_version}]")
                            except Exception as e:
                                logger.warning(f"[{ip}] 版本号解析失败：{line}，错误：{str(e)}")
                            break
                    
                    # 如果版本号已知但不匹配
                    if current_version != "未知" and current_version != target_version:
                        logger.info(f"[{ip}] 版本号不匹配，升级失败")
                        status_callback(ip, "升级失败", "red", None)
                        return  # 升级失败，直接返回
                        
                finally:
                    try:
                        tn.close()
                        logger.info(f"[{ip}] telnet连接已关闭")
                    except:
                        pass
                        
            except Exception as e:
                logger.error(f"[{ip}] 监控异常：{str(e)}")
                if "Connection refused" in str(e):
                    logger.info(f"[{ip}] 拒绝连接，可能正在重启")
                elif "timed out" in str(e):
                    logger.info(f"[{ip}] 连接超时，可能正在重启")
                    
            # 等待10秒后再次检查
            logger.info(f"[{ip}] 等待10秒后重试")
            for i in range(10):  # 改为10秒
                if self.stop_flags.get(ip, True):
                    logger.info(f"[{ip}] 监控被手动停止")
                    break
                time.sleep(1)
                
        # 如果是因为stop_flag退出，且之前没有设置成功状态，则设置为失败
        if self.stop_flags.get(ip, True) and not (time.time() - start_time > timeout):
            logger.info(f"[{ip}] 监控被手动停止，设置为升级失败")
            status_callback(ip, "升级失败", "red", None)
            
        # 清理监控状态
        self.stop_flags.pop(ip, None)
        self.monitors.pop(ip, None)
        logger.info(f"========== 结束监控设备升级状态 [{ip}] ==========") 