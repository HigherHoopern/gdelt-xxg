import os
import sys

# 自动将当前目录（项目根目录）添加到 Python 路径中，解决 ModuleNotFoundError
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

# 从 web 文件夹导入 demo 实例
try:
    from web.app import demo
    from common.logger import setup_logger
    logger = setup_logger("WebLauncher")
except ImportError as e:
    print(f"启动失败，请确保在项目根目录下运行。错误信息: {e}")
    sys.exit(1)

if __name__ == "__main__":
    logger.info("正在启动 Web 可视化仪表盘 (Port: 8090)...")
    demo.launch(server_name="0.0.0.0", server_port=8090)
