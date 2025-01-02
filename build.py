import PyInstaller.__main__
import os
import shutil
import sys
import glob

def clean_build_files():
    """清理构建文件"""
    print("正在清理构建文件...")
    dirs_to_remove = ['build', 'dist', '__pycache__']
    files_to_remove = ['*.spec', '*.pyc', 'runtime_hook.py']
    
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"已删除目录: {dir_name}")
            
    for pattern in files_to_remove:
        for file in glob.glob(pattern):
            os.remove(file)
            print(f"已删除文件: {file}")

def check_requirements():
    """检查依赖"""
    print("检查项目依赖...")
    required_files = [
        'address_gui.py',
        'address_completer.py',
        'amap_address_parser.py',
    ]
    
    # 检查图标文件
    icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
    if not os.path.exists(icon_dir):
        os.makedirs(icon_dir)
        print("已创建icons目录")
    
    icon_file = os.path.join(icon_dir, 'app.ico')
    if not os.path.exists(icon_file):
        print("警告: 未找到app.ico文件，将使用默认图标")
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print("错误: 缺少以下必要文件:")
        for file in missing_files:
            print(f"- {file}")
        return False
    
    print("项目文件检查完成")
    return True

def create_runtime_hook():
    """创建运行时钩子"""
    hook_content = '''
import os
import sys

def get_application_path():
    """获取应用程序路径"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

# 设置环境变量
os.environ['ICON_PATH'] = os.path.join(get_application_path(), 'icons')
'''
    
    with open('runtime_hook.py', 'w', encoding='utf-8') as f:
        f.write(hook_content)
    print("已创建运行时钩子")

def build_application():
    """打包应用程序"""
    print("开始打包应用程序...")
    
    # 获取图标路径（使用绝对路径）
    icon_path = os.path.abspath(os.path.join('icons', 'app.ico'))
    if not os.path.exists(icon_path):
        print(f"警告: 未找到图标文件: {icon_path}")
    else:
        print(f"使用图标文件: {icon_path}")
    
    # PyInstaller参数
    params = [
        'address_gui.py',                # 主程序
        '--name=地址解析工具',           # 程序名称
        '--windowed',                    # 无控制台窗口
        '--noconfirm',                  # 覆盖输出目录
        '--clean',                      # 清理临时文件
        '--onefile',                    # 打包成单个文件
        f'--icon={icon_path}',          # 程序图标（移除条件判断）
        '--add-data=icons;icons',       # 添加图标目录
        # 隐式导入
        '--hidden-import=PyQt5',
        '--hidden-import=PyQt5.QtCore',
        '--hidden-import=PyQt5.QtGui',
        '--hidden-import=PyQt5.QtWidgets',
        '--hidden-import=requests',
        # 运行时钩子
        '--runtime-hook=runtime_hook.py',
        # 优化
        '--optimize=2',
        # 禁用控制台
        '--noconsole',
    ]
    
    # 移除空参数
    params = [p for p in params if p]
    
    try:
        PyInstaller.__main__.run(params)
        print("打包完成!")
        return True
    except Exception as e:
        print(f"打包失败: {str(e)}")
        return False

def main():
    """主函数"""
    print("=== 地址解析工具打包程序 ===")
    
    # 清理旧文件
    clean_build_files()
    
    # 检查依赖
    if not check_requirements():
        print("缺少必要文件，打包终止")
        return
    
    # 创建运行时钩子
    create_runtime_hook()
    
    # 打包应用
    if build_application():
        print("\n打包成功! 程序位于 dist/地址解析工具.exe")
    else:
        print("\n打包失败!")
    
    # 清理临时文件
    if os.path.exists('runtime_hook.py'):
        os.remove('runtime_hook.py')
        print("已清理临时文件")

if __name__ == '__main__':
    main() 