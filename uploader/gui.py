"""
GUI模块，负责：
1. 设备扫描界面
2. 设备连接界面
3. 固件上传界面
4. 状态显示
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from device_manager import DeviceManager

# 配置日志
logger = logging.getLogger(__name__)

class UploaderGUI:
    """
    固件上传机GUI主类
    
    属性：
        device_manager: 设备管理实例
        root: 主窗口
        device_tree: 设备列表树
        status_var: 状态栏变量
    """
    def update_firmware_status(self):
        """更新固件状态显示"""
        import os
        firmware_dir = 'firmware'
        if not os.path.exists(firmware_dir):
            os.makedirs(firmware_dir)
            
        img_files = [f for f in os.listdir(firmware_dir) if f.endswith('.img')]
        
        if img_files:
            self.firmware_status.config(
                text=f"已上传: {img_files[0]}",
                fg="green",
                font=("Arial", 10, "bold")
            )
        else:
            self.firmware_status.config(
                text="未上传固件",
                fg="red",
                font=("Arial", 10, "italic")
            )

    def __init__(self, device_manager):
        """
        初始化GUI界面
        
        参数：
            device_manager: 设备管理实例
        """
        self.device_manager = device_manager
        logger.info("初始化GUI界面")
        
        try:
            self.root = tk.Tk()
            self.root.title("固件上传机")
            self.root.geometry("800x600")
            logger.info("主窗口创建成功")
        except Exception as e:
            logger.error(f"主窗口初始化失败：{str(e)}")
            raise
        
        # 设备列表
        self.device_tree = ttk.Treeview(self.root, columns=("ip", "status"), show="headings")
        self.device_tree.heading("ip", text="IP地址")
        self.device_tree.heading("status", text="状态")
        self.device_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 控制按钮
        control_frame = tk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.scan_button = tk.Button(control_frame, text="扫描设备", command=self.start_scan)
        self.scan_button.pack(side=tk.LEFT, padx=5)
        
        self.connect_button = tk.Button(control_frame, text="连接设备", command=self.connect_devices)
        self.connect_button.pack(side=tk.LEFT, padx=5)
        
        self.upload_button = tk.Button(control_frame, text="上传固件", command=self.upload_firmware)
        self.upload_button.pack(side=tk.LEFT, padx=5)
        
        self.script_button = tk.Button(control_frame, text="查看OTA脚本", command=self.open_script_editor)
        self.script_button.pack(side=tk.LEFT, padx=5)
        
        # 固件状态显示
        self.firmware_status = tk.Label(control_frame, text="未上传固件", fg="red", font=("Arial", 10, "italic"))
        self.firmware_status.pack(side=tk.LEFT, padx=10)
        self.update_firmware_status()
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def start_scan(self):
        """
        启动设备扫描线程
        """
        logger.info("启动设备扫描")
        self.status_var.set("正在扫描设备...")
        try:
            threading.Thread(target=self.scan_devices).start()
            logger.info("设备扫描线程启动成功")
        except Exception as e:
            logger.error(f"设备扫描线程启动失败：{str(e)}")
            self.status_var.set("扫描失败")
        
    def scan_devices(self):
        """
        扫描网络中的设备并更新设备列表
        """
        logger.info("开始扫描设备")
        try:
            devices = self.device_manager.scan_network()
            logger.info(f"扫描到{len(devices)}个设备")
            
            self.device_tree.delete(*self.device_tree.get_children())
            for device in devices:
                self.device_tree.insert("", tk.END, values=(device['ip'], device['status']))
                logger.debug(f"添加设备：{device['ip']} - {device['status']}")
                
            self.status_var.set(f"发现 {len(devices)} 个设备")
            logger.info("设备列表更新完成")
        except Exception as e:
            logger.error(f"设备扫描失败：{str(e)}")
            self.status_var.set("扫描失败")
        
    def connect_devices(self):
        """
        连接选中的设备
        
        返回：
            None
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
                if self.device_manager.connect(ip):
                    self.device_tree.item(item, values=(ip, "已连接"))
                    success_count += 1
                    logger.info(f"设备连接成功：{ip}")
                else:
                    self.device_tree.item(item, values=(ip, "连接失败"))
                    logger.warning(f"设备连接失败：{ip}")
            except Exception as e:
                logger.error(f"设备连接异常：{ip} - {str(e)}")
                self.device_tree.item(item, values=(ip, "连接异常"))
        
        logger.info(f"设备连接完成，成功连接{success_count}/{len(selected)}个设备")
                
    def upload_firmware(self):
        """
        固件上传功能
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
            logger.error(f"拷贝过程中发生错误：{str(e)}")
        
    def open_script_editor(self):
        """
        打开脚本编辑器窗口
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
            script_path = "sh/ota.sh"
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
        """
        logger.info("启动GUI主循环")
        try:
            self.root.mainloop()
            logger.info("GUI主循环结束")
        except Exception as e:
            logger.error(f"GUI运行异常：{str(e)}")
            raise
