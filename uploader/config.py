"""
配置文件，包含所有可配置参数
"""

import os

# 基础路径配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIRMWARE_DIR = os.path.join(BASE_DIR, 'firmware')
LOG_DIR = os.path.join(BASE_DIR, 'uploader')

# 日志配置
LOG_CONFIG = {
    'app_log': {
        'filename': os.path.join(LOG_DIR, 'app.log'),
        'max_bytes': 1 * 1024 * 1024,  # 1MB
        'backup_count': 1,
        'encoding': 'utf-8',
        'level': 'INFO'
    },
    'scan_log': {
        'filename': os.path.join(LOG_DIR, 'scan_debug.log'),
        'max_bytes': 1 * 1024 * 1024,  # 1MB
        'backup_count': 1,
        'encoding': 'utf-8',
        'level': 'INFO'
    }
}

# 设备配置
DEVICE_CONFIG = {
    'telnet': {
        'port': 23,
        'timeout': 5,
        'username': 'root',
        'password': '123456'
    },
    'pid_whitelist': ['12581207'],  # 支持升级的PID列表
    'scan_timeout': 2,  # 扫描超时时间（秒）
    'max_retries': 3,  # 最大重试次数
    'retry_interval': 3,  # 重试间隔（秒）
    'network': {
        'subnet_mask': 24,  # 默认子网掩码位数
        'min_mask': 16,     # 最小允许的掩码位数
        'max_mask': 30      # 最大允许的掩码位数
    }
}

# 线程配置
THREAD_CONFIG = {
    'scan': {
        'max_workers': 100,           # 扫描时的最大线程数
        'max_retries': 3,             # 扫描失败最大重试次数
        'retry_interval': 2           # 扫描重试间隔（秒）
    },
    'connect': {
        'max_workers': 20,            # 连接设备的最大线程数
        'max_retries': 3,             # 连接失败最大重试次数
        'retry_interval': 3,          # 连接重试间隔（秒）
        'connection_timeout': 5       # 连接超时时间（秒）
    },
    'download': {
        'max_workers': 10,            # 固件下载的最大线程数
        'max_retries': 3,             # 下载失败最大重试次数
        'retry_interval': 5,          # 下载重试间隔（秒）
        'download_timeout': 300,      # 下载超时时间（秒）
        'verify_timeout': 30,         # MD5校验超时时间（秒）
        'no_progress_timeout': 30     # 无进度超时时间（秒）
    },
    'upgrade': {
        'max_workers': 5,             # 升级操作的最大线程数
        'max_retries': 2,             # 升级失败最大重试次数
        'retry_interval': 10,         # 升级重试间隔（秒）
        'upgrade_timeout': 60         # 升级超时时间（秒）
    }
}

# HTTP服务器配置
HTTP_CONFIG = {
    'host': '0.0.0.0',
    'port': 5000,
    'firmware_url_prefix': '/firmware',
    'max_connections': 50,            # 最大并发连接数
    'request_timeout': 30             # 请求超时时间（秒）
}

# GUI配置
GUI_CONFIG = {
    'window': {
        'title': 'P3 OTA升级工具',
        'size': '800x600',
        'logo_size': 200  # logo基准宽度
    },
    'tree_columns': {
        'ip': {'width': 150, 'text': 'IP地址'},
        'status': {'width': 100, 'text': '状态'},
        'version': {'width': 100, 'text': '版本号'},
        'pid': {'width': 100, 'text': 'PID'},
        'did': {'width': 150, 'text': 'DID'},
        'upgrade_status': {'width': 100, 'text': '升级状态'}
    },
    'refresh_interval': 1000  # 界面刷新间隔（毫秒）
}

# 升级配置
UPGRADE_CONFIG = {
    'temp_file': '/tmp/ota.img',  # 设备上的临时文件路径
    'upgrade_command': 'nohup ota_upgrade {} > /dev/null 2>&1 &',  # 升级命令模板
    'verify_timeout': 5,  # 验证超时时间（秒）
    'batch_size': 10,    # 每批升级的最大设备数
    'cleanup_old_files': True,  # 是否清理旧的升级文件
    'force_upgrade': False  # 是否强制升级（忽略版本检查）
}

# 版本信息
VERSION = "V1.0.8" 