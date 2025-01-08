# P3 OTA升级工具 V1.0.4

一个用于P3设备批量OTA升级的图形化工具。该工具支持自动扫描网络中的设备，检查设备版本，并进行批量升级操作。

## 主要功能

### 1. 设备扫描
- 自动扫描局域网内的所有P3设备
- 实时显示设备在线状态
- 动态显示扫描进度和结果

### 2. 设备信息显示
- 显示设备IP地址
- 显示当前固件版本
- 显示设备PID和DID
- 显示设备连接状态
- 显示设备升级状态

### 3. 固件管理
- 支持上传新的固件文件(.img格式)
- 显示当前固件版本信息
- 自动检查设备是否需要升级

### 4. 设备管理
- 按发现顺序显示设备列表
- 实时更新设备状态
- 支持设备状态动态更新

### 5. 升级功能
- 自动检测设备PID是否匹配(12581207)
- 自动下载固件到设备
- 实时显示下载进度
- 自动验证下载完整性
- 支持后台升级，不影响设备运行

### 6. 错误处理
- 自动重试连接失败的设备
- 显示详细的错误信息
- 支持断线重连
- 防止重复升级

## 配置说明

所有可配置的参数都集中在 `uploader/config.py` 文件中。修改这些参数可以直接影响软件的运行行为，无需重新编译，保存后重启软件即可生效。以下是详细的配置说明和对应的实际效果：

### 1. 基础路径配置
```python
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIRMWARE_DIR = os.path.join(BASE_DIR, 'firmware')  # 固件存储目录
LOG_DIR = os.path.join(BASE_DIR, 'uploader')      # 日志存储目录
```
**实际效果**：
- 修改 `FIRMWARE_DIR` 可以更改固件文件的存储位置
- 修改 `LOG_DIR` 可以更改日志文件的存储位置
- 这些路径支持相对路径和绝对路径，但建议使用绝对路径避免路径解析问题

### 2. 日志配置
```python
LOG_CONFIG = {
    'app_log': {
        'filename': 'app.log',        # 应用日志文件名
        'max_bytes': 1 * 1024 * 1024, # 单个日志文件最大大小（1MB）
        'backup_count': 1,            # 保留的备份文件数量
        'encoding': 'utf-8',          # 日志文件编码
        'level': 'INFO'               # 日志级别（DEBUG/INFO/WARNING/ERROR）
    },
    'scan_log': {
        'filename': 'scan_debug.log', # 扫描日志文件名
        'max_bytes': 1 * 1024 * 1024, # 单个日志文件最大大小（1MB）
        'backup_count': 1,            # 保留的备份文件数量
        'encoding': 'utf-8',          # 日志文件编码
        'level': 'INFO'               # 日志级别
    }
}
```
**实际效果**：
- 修改 `max_bytes` 可以控制单个日志文件的大小，超过此大小会自动滚动
- 修改 `backup_count` 可以控制保留的历史日志文件数量
- 修改 `level` 可以控制日志的详细程度：
  - DEBUG：显示所有调试信息，适合开发调试
  - INFO：显示常规操作信息，建议正常使用时采用
  - WARNING：只显示警告和错误信息
  - ERROR：只显示错误信息

### 3. 设备配置
```python
DEVICE_CONFIG = {
    'telnet': {
        'port': 23,                   # Telnet端口
        'timeout': 5,                 # 连接超时时间（秒）
        'username': 'root',           # 登录用户名
        'password': '123456'          # 登录密码
    },
    'pid_whitelist': ['12581207'],    # 支持升级的PID列表
    'scan_timeout': 2,                # 扫描超时时间（秒）
    'max_retries': 3,                 # 最大重试次数
    'retry_interval': 3               # 重试间隔（秒）
}
```
**实际效果**：
- 修改 `telnet` 配置可以适配不同的设备登录参数
- 修改 `pid_whitelist` 可以支持其他型号设备的升级
- 修改 `scan_timeout` 可以调整扫描响应时间，网络较差时可以适当增加
- 修改 `max_retries` 和 `retry_interval` 可以调整重试策略，网络不稳定时可以增加重试次数

### 4. 线程配置
```python
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
```
**实际效果**：
- 修改各模块的 `max_workers` 可以控制并发数：
  - 扫描并发数越大，扫描速度越快，但对网络负载要求更高
  - 下载并发数建议根据网络带宽调整，避免网络拥塞
  - 升级并发数建议保持较小值，避免设备负载过高
- 修改超时和重试参数可以适应不同的网络环境：
  - 网络较好时可以减小超时时间，提高操作速度
  - 网络较差时可以增加超时时间和重试次数，提高成功率

### 5. HTTP服务器配置
```python
HTTP_CONFIG = {
    'host': '0.0.0.0',               # 监听地址
    'port': 5000,                    # 监听端口
    'firmware_url_prefix': '/firmware',# 固件访问URL前缀
    'max_connections': 50,            # 最大并发连接数
    'request_timeout': 30             # 请求超时时间（秒）
}
```
**实际效果**：
- 修改 `host` 和 `port` 可以更改HTTP服务器的监听地址和端口
- 修改 `max_connections` 可以控制同时下载固件的设备数量
- 修改 `request_timeout` 可以调整HTTP请求的超时时间

### 6. GUI配置
```python
GUI_CONFIG = {
    'window': {
        'title': 'P3 OTA升级工具',    # 窗口标题
        'size': '800x600',           # 窗口大小
        'logo_size': 200             # logo基准宽度
    },
    'tree_columns': {
        'ip': {'width': 150, 'text': 'IP地址'},           # IP地址列配置
        'status': {'width': 100, 'text': '状态'},         # 状态列配置
        'version': {'width': 100, 'text': '版本号'},      # 版本号列配置
        'pid': {'width': 100, 'text': 'PID'},            # PID列配置
        'did': {'width': 150, 'text': 'DID'},            # DID列配置
        'upgrade_status': {'width': 100, 'text': '升级状态'} # 升级状态列配置
    },
    'refresh_interval': 1000         # 界面刷新间隔（毫秒）
}
```
**实际效果**：
- 修改 `window` 配置可以调整窗口外观
- 修改 `tree_columns` 可以调整设备列表的显示效果
- 修改 `refresh_interval` 可以调整界面刷新频率：
  - 值越小，界面响应越快，但CPU占用越高
  - 值越大，界面响应较慢，但CPU占用较低

### 7. 升级配置
```python
UPGRADE_CONFIG = {
    'temp_file': '/tmp/ota.img',     # 设备上的临时文件路径
    'upgrade_command': 'nohup ota_upgrade {} > /dev/null 2>&1 &',  # 升级命令模板
    'verify_timeout': 5,             # 验证超时时间（秒）
    'batch_size': 10,                # 每批升级的最大设备数
    'cleanup_old_files': True,       # 是否清理旧的升级文件
    'force_upgrade': False           # 是否强制升级（忽略版本检查）
}
```
**实际效果**：
- 修改 `temp_file` 可以更改设备上固件的临时存储位置
- 修改 `batch_size` 可以控制批量升级时的设备数量
- 修改 `cleanup_old_files` 可以控制是否自动清理历史文件
- 修改 `force_upgrade` 可以控制是否强制升级：
  - True：忽略版本检查，强制升级所有设备
  - False：只升级版本号较低的设备

## 使用说明

1. 启动软件
   - 运行程序后，软件会自动启动HTTP服务器
   - 界面上方会显示当前固件状态

2. 上传固件
   - 点击"上传固件"按钮
   - 选择要升级的.img固件文件
   - 等待固件上传完成

3. 扫描设备
   - 点击"扫描设备"按钮
   - 软件会自动扫描局域网内的设备
   - 设备列表会实时更新

4. 升级过程
   - 软件会自动识别需要升级的设备
   - 对于需要升级的设备，会自动开始下载固件
   - 下载完成后会自动执行升级命令
   - 升级过程在设备后台运行，不影响设备操作

## 注意事项

1. 确保电脑和设备在同一局域网内
2. 确保网络连接稳定
3. 升级过程中请勿断开设备电源
4. 仅支持PID为12581207的设备升级
5. 建议在升级前备份设备配置

## 系统要求

- 操作系统：Windows 10及以上
- Python版本：3.6及以上
- 网络：有线连接建议使用千兆网卡

## 更新历史

### V1.0.4 (2024-01-08)
- 添加下载线程数设置功能
- 限制最大下载线程数为15
- 优化状态栏显示
- 改进设备状态显示逻辑

### V1.0.3 (2024-01-08)
- 优化日志记录机制，限制日志文件大小
- 修复日志文件过大的问题
- 提高日志记录效率
- 改进日志文件管理
- 添加统一配置文件，方便参数配置

### V1.0.2 (2024-01-08)
- 修复设备状态更新时的线程安全问题
- 移除设备列表自动排序功能
- 优化设备状态更新逻辑
- 提高程序稳定性

### V1.0.1 (2024-01-08)
- 修复升级命令执行失败的问题
- 增加升级命令执行状态检查
- 优化错误处理和日志记录

### V1.0.0 (2024-01-08)
- 首次发布
- 实现基本的扫描、升级功能
- 支持批量设备管理
- 添加智能排序功能
- 实现后台升级功能