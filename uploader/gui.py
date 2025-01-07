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
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from PIL import Image, ImageTk, ImageFilter
from device_manager import DeviceManager

# 配置日志模块
# 使用当前模块名(__name__)作为日志记录器名称
# 可以在其他模块中通过logging.getLogger(__name__)获取相同记录器
logger = logging.getLogger(__name__)

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

    def __init__(self, device_manager):
        """
        初始化GUI界面
        
        参数：
            device_manager: DeviceManager实例，用于设备管理操作
            
        功能：
            1. 初始化主窗口
            2. 加载并显示logo
            3. 创建设备列表
            4. 添加控制按钮
            5. 初始化状态栏
            6. 检查固件状态
            
        异常处理：
            - 如果初始化失败会记录错误日志并抛出异常
        """
        self.device_manager = device_manager
        logger.info("初始化GUI界面")
        
        try:
            self.root = tk.Tk()
            self.root.title("固件上传机")
            self.root.geometry("800x600")
            
            # 加载并显示logo
            import os
            logo_path = os.path.join(os.path.dirname(__file__), "..", "image", "logo.png")
            
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
            logo_label = tk.Label(self.root, image=self.logo)
            logo_label.pack(pady=10)
            
            logger.info("主窗口创建成功")
        except Exception as e:
            logger.error(f"主窗口初始化失败：{str(e)}")
            raise
        
        # 设备列表
        self.device_tree = ttk.Treeview(self.root, columns=("ip", "status", "version", "upgrade_status"), show="headings")
        self.device_tree.heading("ip", text="IP地址")
        self.device_tree.heading("status", text="状态")
        self.device_tree.heading("version", text="版本号")
        self.device_tree.heading("upgrade_status", text="升级状态")
        # 设置列宽
        self.device_tree.column("ip", width=150)
        self.device_tree.column("status", width=100)
        self.device_tree.column("version", width=100)
        self.device_tree.column("upgrade_status", width=100)
        self.device_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 控制按钮
        control_frame = tk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.scan_button = tk.Button(control_frame, text="扫描设备", command=self.start_scan)
        self.scan_button.pack(side=tk.LEFT, padx=5)
        
        self.upload_button = tk.Button(control_frame, text="上传固件", command=self.upload_firmware)
        self.upload_button.pack(side=tk.LEFT, padx=5)
        
        # 固件状态显示
        self.firmware_status = tk.Label(control_frame, text="未上传固件", fg="red", font=("Arial", 10, "italic"))
        self.firmware_status.pack(side=tk.LEFT, padx=10)
        
        # 状态栏
        status_frame = tk.Frame(self.root)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar = tk.Label(status_frame, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 版本号显示
        self.version_label = tk.Label(status_frame, text="待升级版本: -", bd=1, relief=tk.SUNKEN, anchor=tk.E)
        self.version_label.pack(side=tk.RIGHT, padx=5)
        
        # 初始化完成后更新固件状态
        self.update_firmware_status()
        
    def start_scan(self):
        """
        启动设备扫描线程
        
        功能：
            - 更新状态栏显示
            - 启动后台线程执行scan_devices方法
            - 记录扫描开始日志
            
        异常处理：
            - 如果线程启动失败会记录错误日志并更新状态栏
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
        扫描网络中的设备并更新设备列表，然后自动连接在线设备
        
        功能：
            1. 调用device_manager的scan_network方法扫描设备
            2. 清空当前设备列表
            3. 将扫描到的设备添加到设备树中
            4. 更新状态栏显示扫描结果
            5. 自动连接所有在线设备
            6. 比对设备版本与待升级版本
            
        异常处理：
            - 如果扫描失败会记录错误日志并更新状态栏
        """
        logger.info("开始扫描设备")
        try:
            devices = self.device_manager.scan_network()
            logger.info(f"扫描到{len(devices)}个设备")
            
            # 获取待升级版本
            import os
            firmware_dir = '../firmware'
            target_version = None
            if os.path.exists(firmware_dir):
                img_files = [f for f in os.listdir(firmware_dir) if f.endswith('.img')]
                if img_files:
                    target_version = self.extract_version(img_files[0])
            
            self.device_tree.delete(*self.device_tree.get_children())
            online_devices = []
            for device in devices:
                item_id = self.device_tree.insert("", tk.END, values=(
                    device['ip'],
                    device['status'],
                    "",
                    ""
                ))
                logger.debug(f"添加设备：{device['ip']} - {device['status']}")
                if device['status'] == '在线':
                    online_devices.append(item_id)
                
            self.status_var.set(f"发现 {len(devices)} 个设备")
            logger.info("设备列表更新完成")

            # 自动连接在线设备并比对版本
            if online_devices:
                logger.info(f"开始自动连接{len(online_devices)}个在线设备")
                self.device_tree.selection_set(online_devices)
                
                # 连接设备并获取版本信息
                for item_id in online_devices:
                    ip = self.device_tree.item(item_id)['values'][0]
                    try:
                        result = self.device_manager.connect(ip)
                        if result["status"] == "success":
                            device_version = result.get("version", "未知")
                            upgrade_status = "不需要升级" if device_version == target_version else "需要升级"
                            if target_version is None:
                                upgrade_status = "-"
                            self.device_tree.item(item_id, values=(
                                ip,
                                "已连接",
                                device_version,
                                upgrade_status
                            ))
                            logger.info(f"设备连接成功：{ip}，版本：{device_version}，升级状态：{upgrade_status}")
                        else:
                            self.device_tree.item(item_id, values=(
                                ip,
                                result["message"],
                                "",
                                "-"
                            ))
                            logger.warning(f"设备连接失败：{ip}")
                    except Exception as e:
                        logger.error(f"设备连接异常：{ip} - {str(e)}")
                        self.device_tree.item(item_id, values=(
                            ip,
                            "连接异常",
                            "",
                            "-"
                        ))
            
        except Exception as e:
            logger.error(f"设备扫描失败：{str(e)}")
            self.status_var.set("扫描失败")
        
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
                    self.device_tree.item(item, values=(ip, "已连接", result.get("version", "未知"), ""))
                    success_count += 1
                    logger.info(f"设备连接成功：{ip}")
                else:
                    self.device_tree.item(item, values=(ip, result["message"], "", ""))
                    logger.warning(f"设备连接失败：{ip}")
            except Exception as e:
                logger.error(f"设备连接异常：{ip} - {str(e)}")
                self.device_tree.item(item, values=(ip, "连接异常", "", ""))
        
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
            logger.error(f"拷贝过程中发生错误：{str(e)}")
        
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
