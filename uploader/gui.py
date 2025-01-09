"""
GUI模块，负责：
1. 设备扫描界面
2. 设备连接界面
3. 固件上传界面
4. 状态显示

该模块使用Tkinter构建图形用户界面，主要功能包括：
- 扫描网络中的设备并显示在设备列表中
- 连接选中的设备
- 上传固件文件到设备
- 显示当前固件上传状态
- 提供OTA脚本编辑功能

类：
    UploaderGUI: 主GUI类，负责管理所有界面元素和功能

依赖：
    - tkinter: 用于构建GUI界面
    - PIL: 用于处理logo图片
    - device_manager: 用于设备管理相关操作
"""

import logging
from logging.handlers import RotatingFileHandler
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from PIL import Image, ImageTk, ImageFilter
from device_manager import DeviceManager
import urllib.parse
import time
import telnetlib
import os
import sys
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional
from config import THREAD_CONFIG, GUI_CONFIG, VERSION, DEVICE_CONFIG
from upgrade_monitor import UpgradeMonitor

# 定义下载状态常量
class DownloadStatus:
    """下载状态常量类"""
    SUCCESS = "下载成功"
    IN_PROGRESS = "正在下载"
    FAILED = "下载失败"
    CONNECTED = "已连接"
    UPGRADING = "升级中"
    UPGRADE_FAILED = "升级失败"
    WAITING = "等待下载"  # 新增等待下载状态

def setup_logging():
    """配置日志系统"""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
    # 移除所有已存在的处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 如果日志文件已存在且大于2MB，则删除它和它的备份文件
    log_file = 'app.log'
    backup_file = 'app.log.1'
    
    try:
        if os.path.exists(log_file):
            if os.path.getsize(log_file) > 2*1024*1024:
                os.remove(log_file)
                print(f"已删除过大的日志文件: {log_file}")
        if os.path.exists(backup_file):
            if os.path.getsize(backup_file) > 2*1024*1024:
                os.remove(backup_file)
                print(f"已删除过大的备份文件: {backup_file}")
    except Exception as e:
        print(f"清理日志文件时出错: {e}")
    
    # 创建文件处理器
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=2*1024*1024,
            backupCount=1,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"设置日志处理器时出错: {e}")
    
    # 设置根日志记录器，确保所有模块的日志都能被捕获
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    return logger

# 配置日志
logger = setup_logging()

def resource_path(relative_path):
    """获取资源的绝对路径，支持开发环境和打包环境"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller创建临时文件夹，将路径存储在_MEIPASS中
        base_path = sys._MEIPASS
    else:
        # 在开发环境中，使用项目根目录
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

class UploaderGUI:
    """
    固件上传机GUI主类，负责管理整个图形用户界面
    
    属性：
        device_manager: DeviceManager实例，用于设备管理操作
        root: Tkinter主窗口对象
        device_tree: ttk.Treeview实例，用于显示设备列表
        status_var: tk.StringVar实例，用于状态栏文本显示
        firmware_status: tk.Label实例，显示固件上传状态
        logo: ImageTk.PhotoImage实例，存储程序logo
        scan_button: 扫描设备按钮
        connect_button: 连接设备按钮
        upload_button: 上传固件按钮
        script_button: 查看OTA脚本按钮
    """
    
    def extract_version(self, filename):
        """
        从固件文件名中提取版本号
        
        参数：
            filename: 固件文件名
            
        返回：
            str: 提取到的版本号，如果没有找到返回None
        """
        import re
        version_pattern = r'(\d+\.\d+\.\d+(?:\(\d+\))?)'
        match = re.search(version_pattern, filename)
        return match.group(1) if match else None
        
    def update_firmware_status(self):
        """
        更新固件状态显示和版本号
        
        功能：
            - 检查firmware目录下是否存在.img固件文件
            - 根据检查结果更新界面显示状态
            - 如果存在固件文件，显示文件名和绿色状态
            - 从文件名中提取并显示版本号
            - 如果不存在固件文件，显示红色警告状态
            
        注意：
            - 如果firmware目录不存在会自动创建
            - 只显示第一个找到的.img文件
        """
        import os
        firmware_dir = '../firmware'
        if not os.path.exists(firmware_dir):
            os.makedirs(firmware_dir)
            
        img_files = [f for f in os.listdir(firmware_dir) if f.endswith('.img')]
        
        if img_files:
            filename = img_files[0]
            self.firmware_status.config(
                text=f"已上传: {filename}",
                fg="green",
                font=("Arial", 10, "bold")
            )
            
            # 提取并显示版本号
            version = self.extract_version(filename)
            if version:
                self.version_label.config(text=f"待升级版本: {version}")
            else:
                self.version_label.config(text="待升级版本: 未知")
        else:
            self.firmware_status.config(
                text="未上传固件",
                fg="red",
                font=("Arial", 10, "italic")
            )
            self.version_label.config(text="待升级版本: -")

    def __init__(self, device_manager, flask_app=None):
        """
        初始化GUI
        
        参数：
            device_manager: DeviceManager实例
            flask_app: Flask应用实例（可选）
        """
        self.device_manager = device_manager
        self.flask_app = flask_app
        self.tree_lock = threading.Lock()
        self.monitor_count = 0  # 添加监控计数器
        self.scanning_in_progress = False  # 添加扫描流程状态标志
        
        # 创建主窗口
        self.root = tk.Tk()
        self.root.title(f"P3 OTA升级工具 {VERSION}")  # 使用导入的VERSION
        
        # 设置窗口大小
        window_width = 800
        window_height = 600
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # 设置窗口图标
        try:
            icon_path = resource_path(os.path.join("image", "app_logo.ico"))
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
                logger.info(f"已加载窗口图标：{icon_path}")
            else:
                logger.warning(f"未找到窗口图标文件：{icon_path}")
        except Exception as e:
            logger.warning(f"加载窗口图标失败：{str(e)}")

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)  # 设置窗口关闭处理函数
            
        # 加载并显示logo
        logo_path = resource_path(os.path.join("image", "logo.png"))
        
        if not os.path.exists(logo_path):
            # 创建默认logo
            from PIL import ImageDraw
            logo_image = Image.new('RGB', (200, 100), color = (73, 109, 137))
            d = ImageDraw.Draw(logo_image)
            d.text((10,10), "OTA Uploader", fill=(255,255,0))
            logger.warning("使用默认logo，未找到logo文件：%s", logo_path)
        else:
            logo_image = Image.open(logo_path)
            logger.info("加载logo文件：%s", logo_path)
        
        # 按宽度缩放，保持宽高比
        base_width = 200
        w_percent = (base_width / float(logo_image.size[0]))
        h_size = int((float(logo_image.size[1]) * float(w_percent)))
        logo_image = logo_image.resize((base_width, h_size), Image.Resampling.LANCZOS)
        
        self.logo = ImageTk.PhotoImage(logo_image)
        logo_label = tk.Label(self.root, image=self.logo, cursor="hand2")  # 添加手型光标
        logo_label.pack(pady=10)
        
        # 添加点击计数器和处理函数
        self.logo_click_count = 0
        self.last_click_time = 0
        
        def on_logo_click(event):
            current_time = time.time()
            if current_time - self.last_click_time > 1.5:  # 重置计数器的时间阈值
                self.logo_click_count = 1
            else:
                self.logo_click_count += 1
                
            self.last_click_time = current_time
            
            if self.logo_click_count == 5:
                self.logo_click_count = 0  # 重置计数器
                messagebox.showinfo("彩蛋", "作者：黄浩然")
                
        logo_label.bind("<Button-1>", on_logo_click)  # 绑定点击事件
        
        logger.info("主窗口创建成功")
        
        # 设备列表
        self.device_tree = ttk.Treeview(
            self.root,
            columns=("ip", "status", "version", "pid", "did", "upgrade_status"),
            show="headings",
            selectmode="browse"
        )
        
        # 配置颜色标签
        self.device_tree.tag_configure("red", foreground="red")
        self.device_tree.tag_configure("green", foreground="green")
        self.device_tree.tag_configure("yellow", foreground="orange")
        
        # 设置列标题
        self.device_tree.heading("ip", text="IP地址")
        self.device_tree.heading("status", text="状态")
        self.device_tree.heading("version", text="版本号")
        self.device_tree.heading("pid", text="PID")
        self.device_tree.heading("did", text="DID")
        self.device_tree.heading("upgrade_status", text="升级状态")
        # 设置列宽
        self.device_tree.column("ip", width=150)
        self.device_tree.column("status", width=100)
        self.device_tree.column("version", width=100)
        self.device_tree.column("pid", width=100)
        self.device_tree.column("did", width=150)
        self.device_tree.column("upgrade_status", width=100)
        self.device_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 控制按钮
        control_frame = tk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 添加子网掩码设置
        mask_frame = tk.Frame(control_frame)
        mask_frame.pack(side=tk.LEFT, padx=5)
        
        tk.Label(mask_frame, text="子网掩码位数:").pack(side=tk.LEFT)
        self.mask_var = tk.StringVar(value=str(self.device_manager.subnet_mask))
        mask_values = list(range(DEVICE_CONFIG['network']['min_mask'], 
                               DEVICE_CONFIG['network']['max_mask'] + 1))
        self.mask_combo = ttk.Combobox(mask_frame, 
                                     textvariable=self.mask_var,
                                     values=mask_values,
                                     width=3,
                                     state="readonly")
        self.mask_combo.pack(side=tk.LEFT)
        
        # 绑定选择事件
        def on_mask_select(event):
            try:
                new_mask = int(self.mask_var.get())
                if self.device_manager.set_subnet_mask(new_mask):
                    self.status_var.set(f"子网掩码已设置为 /{new_mask}")
                else:
                    self.status_var.set("子网掩码设置失败")
            except ValueError:
                self.status_var.set("无效的子网掩码值")
                
        self.mask_combo.bind('<<ComboboxSelected>>', on_mask_select)

        self.scan_button = tk.Button(control_frame, text="扫描设备", command=self.start_scan)
        self.scan_button.pack(side=tk.LEFT, padx=5)
        
        self.upload_button = tk.Button(control_frame, text="上传固件", command=self.upload_firmware)
        self.upload_button.pack(side=tk.LEFT, padx=5)
        
        # 固件状态显示
        self.firmware_status = tk.Label(control_frame, text="未上传固件", fg="red", font=("Arial", 10, "italic"))
        self.firmware_status.pack(side=tk.LEFT, padx=10)
        
        # HTTP服务器状态显示
        self.http_status = tk.Label(control_frame, text="HTTP服务: 未启动", fg="red", font=("Arial", 10, "italic"))
        self.http_status.pack(side=tk.RIGHT, padx=10)
        
        # 状态栏
        status_frame = tk.Frame(self.root)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar = tk.Label(status_frame, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 监控计数显示
        self.monitor_label = tk.Label(status_frame, text="升级中: 0", bd=1, relief=tk.SUNKEN, anchor=tk.E)
        self.monitor_label.pack(side=tk.RIGHT, padx=5)
        
        # 版本号显示
        self.version_label = tk.Label(status_frame, text="待升级版本: -", bd=1, relief=tk.SUNKEN, anchor=tk.E)
        self.version_label.pack(side=tk.RIGHT, padx=5)
        
        # 创建进度条Frame
        self.progress_frame = tk.Frame(self.root)
        self.progress_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 创建进度条和标签
        self.progress_label = tk.Label(self.progress_frame, text="", anchor="w")
        self.progress_label.pack(side=tk.LEFT, padx=5)
        
        self.progress_bar = ttk.Progressbar(self.progress_frame, length=300, mode='determinate')
        self.progress_bar.pack(side=tk.LEFT, padx=5)
        
        # 隐藏进度条（默认）
        self.progress_frame.pack_forget()
        
        # 初始化完成后更新固件状态
        self.update_firmware_status()
        
        # 更新HTTP服务器状态
        if self.flask_app:
            self.update_http_status()
            
        # 创建线程池
        self.download_executor = ThreadPoolExecutor(
            max_workers=THREAD_CONFIG['download']['max_workers'],
            thread_name_prefix='download'
        )
            
        self.upgrade_monitor = UpgradeMonitor()
        
    def start_scan(self):
        """
        启动设备扫描线程
        """
        # 检查是否正在进行扫描和升级流程
        if self.scanning_in_progress:
            messagebox.showwarning("警告", "当前正在进行扫描和升级流程，请等待所有设备升级监控结束后再进行扫描")
            return
            
        logger.info("启动设备扫描")
        self.status_var.set("正在扫描设备...")
        try:
            self.scanning_in_progress = True  # 设置扫描流程开始
            threading.Thread(target=self.scan_devices).start()
            logger.info("设备扫描线程启动成功")
        except Exception as e:
            logger.error(f"设备扫描线程启动失败：{str(e)}")
            self.status_var.set("扫描失败")
            self.scanning_in_progress = False  # 扫描失败时重置状态
        
    def ip_to_int(self, ip: str) -> int:
        """将IP地址转换为整数以便正确排序"""
        try:
            parts = list(map(int, ip.split('.')))
            return (parts[0] << 24) + (parts[1] << 16) + (parts[2] << 8) + parts[3]
        except:
            return 0

    def insert_device_sorted(self, device_info):
        """
        更新或插入设备信息（不进行排序）
        
        参数：
            device_info: 设备信息字典，包含ip、status、version等信息
        """
        with self.tree_lock:  # 使用线程锁保护设备列表操作
            # 检查设备是否已存在
            device_exists = False
            for item_id in self.device_tree.get_children():
                values = self.device_tree.item(item_id)['values']
                if values[0] == device_info['ip']:
                    # 更新现有设备，重置颜色标签
                    self.device_tree.item(item_id, values=(
                        device_info['ip'],
                        device_info['status'],
                        device_info['version'],
                        device_info['pid'],
                        device_info['did'],
                        device_info['upgrade_status']
                    ), tags=())  # 重置颜色标签
                    device_exists = True
                    break
            
            # 如果设备不存在，添加新设备
            if not device_exists:
                self.device_tree.insert("", tk.END, values=(
                    device_info['ip'],
                    device_info['status'],
                    device_info['version'],
                    device_info['pid'],
                    device_info['did'],
                    device_info['upgrade_status']
                ), tags=())  # 新设备不带颜色标签

    def scan_devices(self):
        """扫描并连接设备"""
        try:
            # 获取本机IP
            local_ip = self.device_manager.get_local_ip()
            if not local_ip:
                self.status_var.set("获取本机IP失败")
                self.scanning_in_progress = False  # 重置扫描状态
                return
                
            # 扫描设备
            devices = self.device_manager.scan_network()
            if not devices:
                self.status_var.set("未发现设备")
                self.scanning_in_progress = False  # 重置扫描状态
                return
                
            # 用于跟踪是否有需要升级的设备
            has_upgrade_devices = False
                
            # 更新设备列表
            for device in devices:
                # 连接设备并获取详细信息
                device_info = self.device_manager.connect(device['ip'])
                if device_info['status'] == 'success':
                    # 检查是否需要升级
                    firmware_dir = '../firmware'
                    img_files = [f for f in os.listdir(firmware_dir) if f.endswith('.img')]
                    target_version = self.get_target_version() if img_files else ""
                    
                    # 只有当PID匹配且版本号不同时才需要升级
                    needs_upgrade = (
                        img_files 
                        and device_info['pid'] == '12581207'
                        and target_version 
                        and device_info['version'] != target_version
                    )
                    
                    if needs_upgrade:
                        has_upgrade_devices = True  # 标记有需要升级的设备
                        # 需要升级的设备
                        self.insert_device_sorted({
                            'ip': device['ip'],
                            'status': DownloadStatus.WAITING,  # 设置为等待下载状态
                            'version': device_info['version'],
                            'pid': device_info['pid'],
                            'did': device_info['did'],
                            'upgrade_status': '需要升级'
                        })
                        # 启动下载
                        self.start_firmware_download(device['ip'], local_ip)
                    else:
                        # 不需要升级的设备
                        upgrade_status = '-'
                        if device_info['pid'] != '12581207':
                            upgrade_status = 'PID不匹配'
                        elif target_version and device_info['version'] == target_version:
                            upgrade_status = '版本已是最新'
                            
                        self.insert_device_sorted({
                            'ip': device['ip'],
                            'status': DownloadStatus.CONNECTED,
                            'version': device_info['version'],
                            'pid': device_info['pid'],
                            'did': device_info['did'],
                            'upgrade_status': upgrade_status
                        })
                else:
                    # 连接失败的设备
                    self.insert_device_sorted({
                        'ip': device['ip'],
                        'status': device_info['message'],
                        'version': '-',
                        'pid': '-',
                        'did': '-',
                        'upgrade_status': '-'
                    })
                    
            # 更新状态栏，只显示发现的设备数量
            self.status_var.set(f"发现 {len(devices)} 个设备")
            
            # 如果没有需要升级的设备，重置扫描状态
            if not has_upgrade_devices:
                self.scanning_in_progress = False
                logger.info("扫描完成，没有发现需要升级的设备")
            
        except Exception as e:
            logger.error(f"扫描设备时出错：{str(e)}")
            self.status_var.set("扫描失败")
            self.scanning_in_progress = False  # 出错时重置扫描状态
            
    def connect_and_update_device(self, ip: str, local_ip: str, target_version: str):
        """
        连接设备并更新其状态
        
        参数：
            ip: 设备IP地址
            local_ip: 本地IP地址
            target_version: 目标版本号
        """
        max_retries = 3  # 最大重试次数
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                if retry_count > 0:
                    logger.info(f"设备[{ip}] 第{retry_count + 1}次尝试连接")
                    # 更新状态显示重试次数
                    device_info = {
                        'ip': ip,
                        'status': f"正在重试({retry_count + 1}/{max_retries})",
                        'version': "",
                        'pid': "",
                        'did': "",
                        'upgrade_status': "",
                        'sort_key': 4
                    }
                    self.insert_device_sorted(device_info)
                    time.sleep(2)  # 等待2秒后重试
                
                result = self.device_manager.connect(ip)
                if result["status"] == "success":
                    device_info = {
                        'ip': ip,
                        'status': DownloadStatus.CONNECTED,
                        'version': result.get("version", "未知"),
                        'pid': result.get("pid", "未知"),
                        'did': result.get("did", "未知"),
                        'upgrade_status': "",
                        'sort_key': 3
                    }
                    
                    # 检查版本和PID
                    upgrade_needed = device_info['version'] != target_version
                    pid_matched = device_info['pid'] == "12581207"
                    
                    if upgrade_needed and pid_matched:
                        device_info['upgrade_status'] = "需要升级"
                        device_info['sort_key'] = 0
                    elif not upgrade_needed:
                        device_info['upgrade_status'] = "不需要升级"
                        device_info['sort_key'] = 1
                    elif not pid_matched:
                        device_info['upgrade_status'] = "PID不匹配"
                        device_info['sort_key'] = 2
                    
                    if target_version is None:
                        device_info['upgrade_status'] = "-"
                        device_info['sort_key'] = 3
                    
                    self.insert_device_sorted(device_info)
                    logger.info(f"设备连接成功：{ip}，版本：{device_info['version']}，PID：{device_info['pid']}，DID：{device_info['did']}，升级状态：{device_info['upgrade_status']}")
                    
                    # 如果需要升级且PID匹配，启动固件下载
                    if device_info['upgrade_status'] == "需要升级":
                        self.start_firmware_download(ip, local_ip)
                    
                    return  # 连接成功，直接返回
                else:
                    last_error = result["message"]
                    retry_count += 1
                    if retry_count >= max_retries:
                        device_info = {
                            'ip': ip,
                            'status': result["message"],
                            'version': "",
                            'pid': "",
                            'did': "",
                            'upgrade_status': "",
                            'sort_key': 4
                        }
                        self.insert_device_sorted(device_info)
                        logger.warning(f"设备连接失败（重试{max_retries}次）：{ip}")
                    
            except Exception as e:
                last_error = str(e)
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error(f"设备连接异常（重试{max_retries}次）：{ip} - {str(e)}")
                    device_info = {
                        'ip': ip,
                        'status': "连接异常",
                        'version': "",
                        'pid': "",
                        'did': "",
                        'upgrade_status': "",
                        'sort_key': 4
                    }
                    self.insert_device_sorted(device_info)
        
    def connect_devices(self):
        """
        连接选中的设备
        
        功能：
            1. 检查是否有设备被选中
            2. 遍历所有选中的设备
            3. 对每个设备调用device_manager的connect方法
            4. 根据连接结果更新设备状态和版本信息
            5. 记录连接成功/失败数量
            
        异常处理：
            - 如果没有选中设备会弹出警告框
            - 连接异常会记录错误日志并更新设备状态
        """
        logger.info("尝试连接设备")
        selected = self.device_tree.selection()
        if not selected:
            logger.warning("未选择任何设备")
            messagebox.showwarning("警告", "请先选择设备")
            return
        
        success_count = 0
        for item in selected:
            ip = self.device_tree.item(item)['values'][0]
            logger.info(f"正在连接设备：{ip}")
            try:
                result = self.device_manager.connect(ip)
                if result["status"] == "success":
                    self.device_tree.item(item, values=(
                        ip, 
                        DownloadStatus.CONNECTED, 
                        result.get("version", "未知"),
                        result.get("pid", "未知"),
                        result.get("did", "未知"),
                        ""
                    ))
                    success_count += 1
                    logger.info(f"设备连接成功：{ip}")
                else:
                    self.device_tree.item(item, values=(
                        ip,
                        result["message"],
                        "",
                        "",
                        "",
                        ""
                    ))
                    logger.warning(f"设备连接失败：{ip}")
            except Exception as e:
                logger.error(f"设备连接异常：{ip} - {str(e)}")
                self.device_tree.item(item, values=(
                    ip,
                    "连接异常",
                    "",
                    "",
                    "",
                    ""
                ))
        
        logger.info(f"设备连接完成，成功连接{success_count}/{len(selected)}个设备")
                
    def upload_firmware(self):
        """
        固件上传功能
        
        功能：
            1. 弹出文件选择对话框选择固件文件
            2. 调用app模块的copy_firmware方法拷贝固件
            3. 根据拷贝结果显示成功/失败消息
            4. 更新固件状态显示
            5. 记录上传日志
            
        异常处理：
            - 如果未选择文件会记录警告日志
            - 拷贝过程中发生错误会弹出错误框并记录错误日志
        """
        logger.info("尝试上传固件")
        
        # 选择固件文件
        from tkinter import filedialog
        file_path = filedialog.askopenfilename(
            title="选择固件文件",
            filetypes=[("固件文件", "*.img")]
        )
        
        if not file_path:
            logger.warning("未选择固件文件")
            return
            
        # 开始上传
        self.status_var.set("正在拷贝固件...")
        try:
            from app import copy_firmware
            dest_path = copy_firmware(file_path)
            
            if dest_path:
                messagebox.showinfo("成功", f"固件拷贝成功：{dest_path}")
                self.status_var.set("固件拷贝成功")
                logger.info(f"固件拷贝成功：{dest_path}")
                self.update_firmware_status()
            else:
                messagebox.showerror("失败", "固件拷贝失败")
                self.status_var.set("固件拷贝失败")
                logger.error("固件拷贝失败")
        except Exception as e:
            messagebox.showerror("错误", f"拷贝过程中发生错误：{str(e)}")
            self.status_var.set("拷贝错误")
            logger.error(f"拷拷贝过程中发生错误：{str(e)}")
        
    def open_script_editor(self):
        """
        打开脚本编辑器窗口
        
        功能：
            1. 创建新的顶级窗口
            2. 添加文本编辑区域
            3. 检查是否存在ota.sh文件
                - 如果存在则加载内容并设置为只读
                - 如果不存在则创建新的可编辑文件
            4. 记录编辑器初始化日志
            
        异常处理：
            - 如果初始化失败会记录错误日志并抛出异常
        """
        logger.info("打开脚本编辑器")
        try:
            script_window = tk.Toplevel(self.root)
            script_window.title("脚本编辑器")
            script_window.geometry("600x400")
            
            # 脚本编辑区域
            self.script_text = tk.Text(script_window, wrap=tk.WORD)
            self.script_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # 检查是否存在ota.sh文件
            import os
            script_path = "../sh/ota.sh"
            if os.path.exists(script_path):
                try:
                    with open(script_path, 'r') as f:
                        content = f.read()
                        self.script_text.insert(tk.END, content)
                        self.script_text.config(state=tk.DISABLED)  # 设置为只读
                        logger.info(f"已加载现有脚本：{script_path}")
                except Exception as e:
                    logger.error(f"读取脚本文件失败：{str(e)}")
                    messagebox.showerror("错误", f"读取脚本文件失败：{str(e)}")
            else:
                self.script_text.config(state=tk.NORMAL)  # 新文件可编辑
                logger.info("未找到现有脚本，创建新文件")
            
            logger.info("脚本编辑器初始化完成")
        except Exception as e:
            logger.error(f"脚本编辑器初始化失败：{str(e)}")
            raise
            
    def run(self):
        """
        启动GUI主循环
        
        功能：
            - 调用Tkinter的mainloop方法启动事件循环
            - 记录GUI启动和结束日志
            
        异常处理：
            - 如果运行异常会记录错误日志并抛出异常
        """
        logger.info("启动GUI主循环")
        try:
            self.root.mainloop()
            logger.info("GUI主循环结束")
        except Exception as e:
            logger.error(f"GUI运行异常：{str(e)}")
            raise

    def on_closing(self):
        """
        窗口关闭时的清理操作
        """
        logger.info("正在关闭程序...")
        try:
            # 关闭线程池
            self.download_executor.shutdown(wait=True)
            logger.info("下载线程池已关闭")
        except Exception as e:
            logger.error(f"关闭线程池时出错：{str(e)}")
            
        self.root.destroy()
        logger.info("程序已关闭")

    def update_http_status(self):
        """更新HTTP服务器状态显示"""
        if not hasattr(self, 'http_status'):
            return
            
        if self.flask_app and self.flask_app.thread and self.flask_app.thread.is_alive():
            self.http_status.config(
                text=f"HTTP服务: 运行中 (端口:5000)",
                fg="green",
                font=("Arial", 10, "bold")
            )
        else:
            self.http_status.config(
                text="HTTP服务: 未启动",
                fg="red",
                font=("Arial", 10, "italic")
            )

    def update_download_progress(self, status: str, percent: int):
        """
        更新下载进度显示
        
        参数：
            status: 状态信息
            percent: 进度百分比（-1表示错误）
        """
        def update():
            # 确保进度条可见
            self.progress_frame.pack(fill=tk.X, padx=10, pady=5)
            
            if percent >= 0:
                self.progress_bar['value'] = percent
                self.progress_label.config(text=f"{status} {percent}%", fg="black")
            else:
                # 错误状态
                self.progress_bar['value'] = 0
                self.progress_label.config(text=status, fg="red")
                
            # 如果下载完成，延时隐藏进度条
            if percent == 100:
                self.root.after(3000, lambda: self.progress_frame.pack_forget())
                
        # 在主线程中更新UI
        self.root.after(0, update)
        
    def update_device_progress(self, ip: str, percent: int, status_text: str = None):
        """
        更新设备下载进度
        
        参数：
            ip: 设备IP地址
            percent: 进度百分比
            status_text: 状态文本（可选）
        """
        # 在主线程中更新UI
        def update():
            for item_id in self.device_tree.get_children():
                if self.device_tree.item(item_id)['values'][0] == ip:
                    # 保存当前的值
                    current_values = self.device_tree.item(item_id)['values']
                    status = status_text if status_text else f"{DownloadStatus.IN_PROGRESS} {percent}%"
                    self.device_tree.item(item_id, values=(
                        ip,
                        status,
                        current_values[2],  # version
                        current_values[3],  # pid
                        current_values[4],  # did
                        current_values[5]   # upgrade_status
                    ))
                    break
        
        self.root.after(0, update)

    def start_firmware_download(self, ip: str, local_ip: str):
        """
        启动固件下载线程
        """
        logger.info(f"============= 开始固件下载流程 [{ip}] =============")
        
        # 获取实际的固件文件名
        firmware_dir = '../firmware'
        img_files = [f for f in os.listdir(firmware_dir) if f.endswith('.img')]
        if not img_files:
            logger.error("未找到固件文件")
            return
            
        firmware_name = img_files[0]
        encoded_name = urllib.parse.quote(firmware_name)  # URL编码文件名
        logger.info(f"固件文件名: {firmware_name}")
        logger.info(f"URL编码后: {encoded_name}")
        
        # 构建wget命令
        firmware_url = f"http://{local_ip}:5000/firmware/{encoded_name}"
        wget_cmd = f"cd /tmp && wget '{firmware_url}' -O ota.img\n"
        logger.info(f"wget命令：{wget_cmd}")
        
        def download_thread():
            logger.info(f"[{ip}] 开始下载线程")
            # 找到对应的设备项
            for item_id in self.device_tree.get_children():
                if self.device_tree.item(item_id)['values'][0] == ip:
                    try:
                        # 保存当前的所有值
                        current_values = self.device_tree.item(item_id)['values']
                        version = current_values[2]
                        pid = current_values[3]
                        did = current_values[4]
                        upgrade_status = current_values[5]
                        
                        logger.info(f"[{ip}] 当前设备信息: version={version}, pid={pid}, did={did}, status={upgrade_status}")
                        
                        # 更新状态为"等待下载"
                        self.device_tree.item(item_id, values=(
                            ip,
                            DownloadStatus.WAITING,
                            version,
                            pid,
                            did,
                            upgrade_status
                        ))
                        
                        # 开始下载并监控进度
                        logger.info(f"[{ip}] 开始执行下载命令")
                        result = self.device_manager.download_firmware(
                            ip, 
                            wget_cmd,
                            self.update_device_progress
                        )
                        
                        # 根据下载结果更新状态
                        if result["status"] == "success":
                            # 下载成功
                            logger.info(f"[{ip}] 固件下载成功，准备执行升级命令")
                            self.device_tree.item(item_id, values=(
                                ip,
                                DownloadStatus.SUCCESS,
                                version,
                                pid,
                                did,
                                upgrade_status
                            ))
                            
                            try:
                                # 连接设备
                                logger.info(f"[{ip}] 尝试telnet连接")
                                tn = telnetlib.Telnet(ip, timeout=5)
                                
                                # 登录认证
                                tn.read_until(b"login: ", timeout=5)
                                tn.write(b"root\n")
                                tn.read_until(b"Password: ", timeout=5)
                                tn.write(b"123456\n")
                                
                                # 验证登录成功
                                index, _, _ = tn.expect([b"Login incorrect", b"#"], timeout=5)
                                if index == 0:
                                    raise Exception("设备登录失败")
                                
                                logger.info(f"[{ip}] telnet登录成功")
                                
                                # 执行升级命令
                                logger.info(f"[{ip}] 开始执行升级命令")
                                try:
                                    # 确保连接状态
                                    tn.write(b"\n")
                                    response = tn.read_until(b"#", timeout=5).decode('utf-8')
                                    if '#' not in response:
                                        logger.error(f"[{ip}] 执行升级命令前检查连接失败")
                                        raise Exception("设备连接状态异常")
                                    
                                    # 在后台执行升级命令
                                    logger.info(f"[{ip}] 发送升级命令")
                                    tn.write(b"nohup ota_upgrade /tmp/ota.img > /dev/null 2>&1 &\n")
                                    
                                    # 等待命令响应
                                    response = tn.read_until(b"#", timeout=5).decode('utf-8')
                                    logger.info(f"[{ip}] 升级命令响应: {response}")
                                    
                                    if '#' not in response:
                                        logger.error(f"[{ip}] 升级命令可能未执行成功")
                                        raise Exception("升级命令执行异常")
                                    
                                    # 验证命令是否在运行
                                    tn.write(b"ps | grep ota_upgrade\n")
                                    ps_response = tn.read_until(b"#", timeout=5).decode('utf-8')
                                    logger.info(f"[{ip}] 进程检查结果: {ps_response}")
                                    
                                    if 'ota_upgrade' not in ps_response:
                                        logger.error(f"[{ip}] 未检测到升级进程")
                                        raise Exception("升级进程未启动")
                                    
                                    # 更新状态为升级中
                                    self.device_tree.item(item_id, values=(
                                        ip,
                                        DownloadStatus.UPGRADING,
                                        version,
                                        pid,
                                        did,
                                        upgrade_status
                                    ))
                                    logger.info(f"[{ip}] 升级命令已在后台执行")
                                    
                                    # 启动升级监控
                                    target_version = self.get_target_version()
                                    logger.info(f"[{ip}] 目标版本号: {target_version}")
                                    if target_version:
                                        logger.info(f"[{ip}] 启动升级监控")
                                        with self.tree_lock:
                                            self.monitor_count += 1  # 增加监控计数
                                            self.monitor_label.config(text=f"升级中: {self.monitor_count}")  # 更新显示
                                        self.upgrade_monitor.start_monitor(
                                            ip,
                                            target_version,
                                            self.update_device_status
                                        )
                                        logger.info(f"[{ip}] 升级监控已启动")
                                    else:
                                        logger.error(f"[{ip}] 无法获取目标版本号，不启动监控")
                                except Exception as e:
                                    logger.error(f"[{ip}] 执行升级命令时出错: {str(e)}")
                                    self.device_tree.item(item_id, values=(
                                        ip,
                                        DownloadStatus.UPGRADE_FAILED,
                                        version,
                                        pid,
                                        did,
                                        upgrade_status
                                    ))
                                finally:
                                    try:
                                        tn.close()
                                    except:
                                        pass
                            except Exception as e:
                                error_msg = f"执行升级命令失败: {str(e)}"
                                logger.error(f"[{ip}] {error_msg}")
                                self.device_tree.item(item_id, values=(
                                    ip,
                                    DownloadStatus.UPGRADE_FAILED,
                                    version,
                                    pid,
                                    did,
                                    upgrade_status
                                ))
                        else:
                            # 下载失败
                            error_msg = result.get("message", "未知错误")
                            logger.error(f"[{ip}] 固件下载失败: {error_msg}")
                            self.device_tree.item(item_id, values=(
                                ip,
                                f"{DownloadStatus.FAILED}: {error_msg}",
                                version,
                                pid,
                                did,
                                upgrade_status
                            ))
                    except Exception as e:
                        # 发生异常
                        logger.error(f"[{ip}] 固件下载异常: {str(e)}")
                        self.device_tree.item(item_id, values=(
                            ip,
                            f"{DownloadStatus.FAILED}: {str(e)}",
                            version,
                            pid,
                            did,
                            upgrade_status
                        ))
                    break
                
        # 使用线程池提交下载任务
        logger.info(f"[{ip}] 提交下载任务到线程池")
        self.download_executor.submit(download_thread)
        logger.info(f"============= 下载任务已提交 [{ip}] =============")

    def update_device_status(self, ip: str, status: str, color: str = "black", device_info: dict = None):
        """
        更新设备状态和信息
        """
        def update():
            with self.tree_lock:
                for item_id in self.device_tree.get_children():
                    values = list(self.device_tree.item(item_id)['values'])
                    if values[0] == ip:
                        values[1] = status  # 更新状态
                        
                        # 如果设备升级完成、失败或超时，减少监控计数
                        if status in ["升级成功", "升级失败", "升级超时"]:
                            self.monitor_count -= 1
                            self.monitor_label.config(text=f"升级中: {self.monitor_count}")  # 更新显示
                            logger.info(f"设备[{ip}]升级{status}，剩余监控数量：{self.monitor_count}")
                            # 如果所有监控都结束，重置扫描状态
                            if self.monitor_count <= 0:
                                self.monitor_count = 0
                                self.monitor_label.config(text="升级中: 0")  # 更新显示为0
                                self.scanning_in_progress = False
                                logger.info("所有设备升级监控已结束，可以开始新的扫描")
                        
                        # 如果提供了设备信息，更新相应字段
                        if device_info:
                            if 'version' in device_info:
                                values[2] = device_info['version']  # 更新版本号
                            if 'pid' in device_info:
                                values[3] = device_info['pid']  # 更新PID
                            if 'did' in device_info:
                                values[4] = device_info['did']  # 更新DID
                            if 'need_upgrade' in device_info:
                                values[5] = device_info['need_upgrade']  # 更新是否需要升级
                        
                        # 更新树形视图
                        self.device_tree.item(item_id, values=tuple(values))
                        self.device_tree.item(item_id, tags=(color,))
                        logger.info(f"设备[{ip}]状态已更新：{status}，信息：{device_info if device_info else '无'}")
                        break
        
        # 在主线程中更新UI
        self.root.after(0, update)
        
    def get_target_version(self) -> str:
        """获取目标版本号"""
        try:
            firmware_dir = '../firmware'
            img_files = [f for f in os.listdir(firmware_dir) if f.endswith('.img')]
            if not img_files:
                logger.error("固件目录为空")
                return ""
                
            # 从文件名中提取版本号
            filename = img_files[0]
            logger.info(f"固件文件名：{filename}")
            
            # 尝试两种格式匹配：
            # 1. OTA_P3_4.4.1(11)_RPC.img
            # 2. OTA_xxx_4.4.1(11).img
            version_patterns = [
                r'OTA_P3_(\d+\.\d+\.\d+\(\d+\))_RPC',  # 格式1
                r'OTA_[^_]+_(\d+\.\d+\.\d+\(\d+\))'    # 格式2
            ]
            
            for i, pattern in enumerate(version_patterns, 1):
                logger.info(f"尝试模式{i}: {pattern}")
                version_match = re.search(pattern, filename)
                if version_match:
                    version = version_match.group(1)
                    logger.info(f"模式{i}匹配成功，提取到版本号：{version}")
                    return version
                else:
                    logger.info(f"模式{i}匹配失败")
                    
            # 如果上面的模式都失败了，尝试更宽松的匹配
            logger.info("尝试通用模式匹配")
            version_match = re.search(r'(\d+\.\d+\.\d+\(\d+\))', filename)
            if version_match:
                version = version_match.group(1)
                logger.info(f"通用模式匹配成功，提取到版本号：{version}")
                return version
                
            logger.warning(f"所有模式都无法匹配文件名：{filename}")
            return ""
        except Exception as e:
            logger.error(f"获取目标版本号失败：{str(e)}")
            return ""
            
    def __del__(self):
        """析构函数，确保清理所有监控线程"""
        if hasattr(self, 'upgrade_monitor'):
            self.upgrade_monitor.stop_all()
