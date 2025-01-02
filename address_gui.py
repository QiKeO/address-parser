'''
Author: 柒刻
Date: 2024-12-28 23:31:15
LastEditTime: 2025-01-02 22:14:17
FilePath: \地区识别\address_gui.py
'''
import os
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit,
                            QListWidget, QGroupBox, QListWidgetItem, QMessageBox,
                            QCompleter, QScrollArea, QDialog, QDesktopWidget, QComboBox,
                            QAction, QGridLayout, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QPoint
from PyQt5.QtGui import QFont, QPixmap, QImage, QWheelEvent, QIcon
from address_completer import AddressCompleter
import json
from datetime import datetime
import re
import requests

# 获取图标路径
ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')

if hasattr(sys, 'frozen'):
    os.environ['PATH'] = sys._MEIPASS + ";" + os.environ['PATH']
QT_PLUGIN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.venv', 'Lib', 'site-packages', 'PyQt5', 'Qt5', 'plugins')
os.environ['QT_PLUGIN_PATH'] = QT_PLUGIN_PATH

# 图标常量定义
ICONS = {
    'file': '📁',
    'export': '📤',
    'settings': '⚙️',
    'api': '🔑',
    'theme': '🎨',
    'light': '☀️',
    'dark': '🌙',
    'system': '💻',
    'help': '❓',
    'about': 'ℹ️'
}

def get_app_data_dir():
    """获取应用数据目录"""
    app_name = "地址解析工具"
    if sys.platform == 'win32':
        app_data = os.path.join(os.environ['LOCALAPPDATA'], app_name)
    else:
        app_data = os.path.expanduser(f"~/.{app_name}")
        
    # 确保目录存在
    if not os.path.exists(app_data):
        os.makedirs(app_data)
    return app_data

class AddressInputEdit(QLineEdit):
    def __init__(self, parser, parent=None):
        super().__init__(parent)
        self.parser = parser
        self.completer = QCompleter(self)
        self.completer.setMaxVisibleItems(10)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.setCompleter(self.completer)
        
        # 创建定时器用于延迟请求
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.get_suggestions)
        
        # 记录上次请求的文本和时间
        self.last_text = ""
        self.last_request_time = 0
        self.min_text_length = 3  # 最小触发长度
        
        self.textChanged.connect(self.on_text_changed)
        
    def on_text_changed(self, text):
        # 重置定时器
        self.timer.stop()
        
        # 只有当文本长度大于最小触发长度时才发起请求
        if len(text) >= self.min_text_length:
            # 检查是否与上次请求文本相似
            if not self._is_similar_text(text):
                # 延迟1秒后发起请求
                self.timer.start(1000)
                
    def _is_similar_text(self, text):
        """检查文本是否与上次请求相似"""
        # 如果是上次文本的子串或包含上次文本，则认为相似
        return text in self.last_text or self.last_text in text
        
    def get_suggestions(self):
        """获取地址建议"""
        text = self.text()
        if text:
            tips_result = self.parser._get_input_tips(text)
            if tips_result and tips_result.get('tips'):
                suggestions = []
                current_city = self.parser._get_current_city()
                
                for tip in tips_result['tips']:
                    district = tip.get('district', '')
                    name = tip.get('name', '')
                    address = tip.get('address', '')
                    
                    # 组合完整地址建议
                    if district and name:
                        # 如果是当前城市的地址，添加标记
                        if current_city and current_city in district:
                            suggestion = f"[当前城市] {district} {name}"
                        else:
                            suggestion = f"{district} {name}"
                            
                        if address:
                            suggestion += f" ({address})"
                            
                        suggestions.append(suggestion)
                
                # 更新补全器的建议列表
                model = self.completer.model()
                if model is None:
                    from PyQt5.QtCore import QStringListModel
                    model = QStringListModel()
                    self.completer.setModel(model)
                model.setStringList(suggestions)

class AddressWindow(QMainWindow):
    VERSION = "1.0.0"
    AUTHOR = "柒刻"
    
    def __init__(self):
        super().__init__()
        self.icon_path = ICON_PATH
        self.completer = AddressCompleter()
        
        # 设置配置文件路径
        self.config_file = os.path.join(get_app_data_dir(), 'config.json')
        self.history_file = os.path.join(get_app_data_dir(), 'history.json')
        
        # 先检查是否是首次运行
        self.is_first_run = not os.path.exists(self.config_file)
        
        # 初始化UI
        self.history = self.load_history()
        self.initUI()
        
        # 如果是首次运行，显示欢迎对话框
        if self.is_first_run:
            self.show_welcome_dialog()
        else:
            # 检查已有的API Key是否有效
            self.check_api_key()
        
        # 启动时获取当前位置天气
        self.show_current_location_weather()
        
    def load_history(self):
        """加载历史记录"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"加载历史记录错误: {str(e)}")
        return []
            
    def save_history(self):
        """保存历史记录"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存历史记录错误: {str(e)}")
        
    def initUI(self):
        self.setWindowTitle('地址解析工具')
        self.setGeometry(300, 300, 900, 600)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 顶部输入区域
        top_layout = QHBoxLayout()
        
        # 输入框
        self.input_edit = AddressInputEdit(self.completer.parser)
        self.input_edit.setPlaceholderText('请输入需要解析的地址...')
        self.input_edit.setMinimumWidth(600)
        self.input_edit.setClearButtonEnabled(True)
        self.input_edit.returnPressed.connect(self.parse_address)
        
        # 按钮组
        parse_btn = QPushButton('解析地址')
        parse_btn.setMinimumWidth(100)
        parse_btn.clicked.connect(self.parse_address)
        clear_btn = QPushButton('清除历史')
        clear_btn.setMinimumWidth(100)
        clear_btn.clicked.connect(self.clear_history)
        
        top_layout.addWidget(self.input_edit, 7)  # 输入框占7份
        top_layout.addWidget(parse_btn)
        top_layout.addWidget(clear_btn)
        top_layout.addStretch()
        
        # 创建垂直分割的主要内容区域
        content_layout = QVBoxLayout()
        
        # 上部解析结果区域
        result_group = QGroupBox("解析结果")
        result_layout = QVBoxLayout(result_group)
        
        # 区域信息显示
        region_layout = QHBoxLayout()
        region_label = QLabel("区域信息：")
        region_label.setFont(QFont('Arial', 11))
        self.region_text = QLineEdit()
        self.region_text.setReadOnly(True)
        self.region_text.setFont(QFont('Arial', 11))
        region_layout.addWidget(region_label)
        region_layout.addWidget(self.region_text)
        
        # 详细地址显示
        address_layout = QHBoxLayout()
        address_label = QLabel("详细地址：")
        address_label.setFont(QFont('Arial', 11))
        self.address_text = QLineEdit()
        self.address_text.setReadOnly(True)
        self.address_text.setFont(QFont('Arial', 11))
        address_layout.addWidget(address_label)
        address_layout.addWidget(self.address_text)
        
        # 联系人信息显示
        contact_layout = QHBoxLayout()
        contact_label = QLabel("联系信息：")
        contact_label.setFont(QFont('Arial', 11))
        self.contact_text = QLineEdit()
        self.contact_text.setReadOnly(True)
        self.contact_text.setFont(QFont('Arial', 11))
        contact_layout.addWidget(contact_label)
        contact_layout.addWidget(self.contact_text)
        
        result_layout.addLayout(region_layout)
        result_layout.addLayout(address_layout)
        result_layout.addLayout(contact_layout)
        
        # 添加地图显示区域
        map_group = QGroupBox("位置地图")
        map_layout = QVBoxLayout(map_group)
        
        # 创建地图标签
        self.map_label = QLabel()
        self.map_label.setMinimumSize(400, 300)
        self.map_label.setAlignment(Qt.AlignCenter)
        self.map_label.setStyleSheet("background-color: #f0f0f0;")
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.map_label)
        scroll_area.setWidgetResizable(True)
        map_layout.addWidget(scroll_area)
        
        # 添加地图控制按钮
        control_layout = QHBoxLayout()
        zoom_in_btn = QPushButton("+")
        zoom_out_btn = QPushButton("-")
        reset_btn = QPushButton("重置")
        
        control_layout.addWidget(zoom_in_btn)
        control_layout.addWidget(zoom_out_btn) 
        control_layout.addWidget(reset_btn)
        
        # 添加地图类型切换
        map_type_combo = QComboBox()
        map_type_combo.addItems(["标准地图", "卫星图", "路网图"])
        control_layout.addWidget(map_type_combo)
        
        # 添加比例尺显示
        scale_label = QLabel()
        control_layout.addWidget(scale_label)
        
        # 下部历史记录区域
        history_group = QGroupBox("历史记录")
        history_layout = QVBoxLayout(history_group)
        self.history_list = QListWidget()
        self.history_list.setFont(QFont('Arial', 10))
        # 移除自动换行和最小高度设置
        self.history_list.itemClicked.connect(self.load_history_item)
        history_layout.addWidget(self.history_list)
        
        # 修改内容区域的布局
        content_layout.addWidget(result_group, 2)  # 解析结果占2份
        content_layout.addWidget(map_group, 3)     # 地图占3份
        content_layout.addWidget(history_group, 3) # 历史记录占3份
        
        # 添加到主布局
        main_layout.addLayout(top_layout)
        main_layout.addLayout(content_layout)
        
        # 加载历史记录
        self.update_history_list()
        
        # 状态栏布局
        status_bar = self.statusBar()
        status_bar.setStyleSheet("""
            QStatusBar {
                background: transparent;
                border-top: none;
            }
            QStatusBar::item {
                border: none;
            }
        """)
        
        # 天气信息（左侧）
        self.weather_label = QLabel()
        self.weather_label.setStyleSheet("""
            color: #666666;
            padding: 2px 10px;
        """)
        status_bar.addWidget(self.weather_label)
        
        # 添加弹性空间
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        status_bar.addWidget(spacer)
        
        # 版本和作者信息（右侧，无边距）
        version_label = QLabel(f"版本: v{self.VERSION}")
        separator1 = QLabel("|")
        separator1.setStyleSheet("color: #cccccc;")  # 只保留分隔符颜色
        author_label = QLabel(f"作者: {self.AUTHOR}")
        separator2 = QLabel("|")
        separator2.setStyleSheet("color: #cccccc;")  # 只保留分隔符颜色
        github_label = QLabel('<a href="https://github.com/QiKeO/address-parser">GitHub</a>')
        github_label.setOpenExternalLinks(True)
        
        # 移除所有标签的内外边距
        for label in [version_label, separator1, author_label, separator2, github_label]:
            label.setStyleSheet(label.styleSheet() + "margin: 0; padding: 0;")
        
        status_bar.addPermanentWidget(version_label)
        status_bar.addPermanentWidget(separator1)
        status_bar.addPermanentWidget(author_label)
        status_bar.addPermanentWidget(separator2)
        status_bar.addPermanentWidget(github_label)
        
        self.create_menu()
        
    def create_menu(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 设置菜单栏样式，移除复选框区域
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: transparent;
            }
            QMenuBar::item {
                padding: 4px 10px;
                background-color: transparent;
            }
            QMenuBar::item:selected {
                background-color: #e0e0e0;
            }
            QMenu {
                background-color: white;
                border: 1px solid #cccccc;
            }
            QMenu::item {
                padding: 5px 30px 5px 30px;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #e0e0e0;
            }
            /* 移除菜单项前的复选框区域 */
            QMenu::indicator {
                width: 0px;
                background: none;
            }
        """)
        
        # 文件菜单
        file_menu = menubar.addMenu(f"{ICONS['file']} 文件")
        export_action = QAction(f"{ICONS['export']} 导出历史", self)
        export_action.setShortcut('Ctrl+E')
        export_action.triggered.connect(self.export_history)
        file_menu.addAction(export_action)
        
        # 设置菜单
        settings_menu = menubar.addMenu(f"{ICONS['settings']} 设置")
        api_action = QAction(f"{ICONS['api']} API设置", self)
        api_action.setShortcut('Ctrl+A')
        api_action.triggered.connect(self.show_api_settings)
        settings_menu.addAction(api_action)
        
        # 主题菜单
        theme_menu = settings_menu.addMenu(f"{ICONS['theme']} 主题")
        light_action = QAction(f"{ICONS['light']} 浅色", self)
        dark_action = QAction(f"{ICONS['dark']} 深色", self)
        default_action = QAction(f"{ICONS['system']} 默认", self)
        
        light_action.triggered.connect(lambda: self.change_theme('light'))
        dark_action.triggered.connect(lambda: self.change_theme('dark'))
        default_action.triggered.connect(lambda: self.change_theme('default'))
        
        theme_menu.addAction(light_action)
        theme_menu.addAction(dark_action)
        theme_menu.addAction(default_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu(f"{ICONS['help']} 帮助")
        about_action = QAction(f"{ICONS['about']} 关于", self)
        about_action.setShortcut('F1')
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def update_history_list(self):
        self.history_list.clear()
        for item in reversed(self.history):
            # 修改时间格式为 YYYY-MM-DD HH:mm:ss
            timestamp = datetime.strptime(item['timestamp'], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
            address = re.sub(r'[\r\n\t\u3000\xa0]+', ' ', item['address'])
            address = re.sub(r'\s+', ' ', address).strip()
            if len(address) > 50:
                display_text = f"{timestamp} - {address[:50]}..."
            else:
                display_text = f"{timestamp} - {address}"
            self.history_list.addItem(display_text)
        
    def load_history_item(self, item):
        """加载历史记录项"""
        index = self.history_list.currentRow()
        history_item = self.history[-(index+1)]
        self.input_edit.setText(history_item['address'])
        
        # 如果有地图数据,直接显示
        components = history_item['components']
        if 'map_data' in components:
            import base64
            # 将base64字符串转回bytes
            map_data = base64.b64decode(components['map_data'])
            image = QImage.fromData(map_data)
            self.original_map = QPixmap.fromImage(image)
            self.map_label.setPixmap(self.original_map.scaled(
                self.map_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))
            self.map_label.mousePressEvent = self.show_map_viewer
            self.map_label.setCursor(Qt.PointingHandCursor)
            self.map_label.setToolTip("点击查看大图")
        
        self.display_result(components)
        
    def clear_history(self):
        """清除历史记录"""
        reply = QMessageBox.question(
            self, 
            '确认清除', 
            '确定要清除所有历史记录吗？',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 清空历史记录列表
            self.history = []
            self.history_list.clear()
            
            # 清空输入框
            self.input_edit.clear()
            
            # 清空结果显示
            self.region_text.clear()
            self.address_text.clear()
            self.contact_text.clear()
            
            # 清空地图显示
            self.map_label.clear()
            self.map_label.setStyleSheet("background-color: #f0f0f0;")
            if hasattr(self, 'original_map'):
                delattr(self, 'original_map')
            
            # 显示当前位置天气
            self.show_current_location_weather()
            
            # 保存空的历史记录
            self.save_history()
            
            # 显示提示
            QMessageBox.information(self, '提示', '历史记录已清除')
        
    def clear_display(self):
        self.region_text.setText('')
        self.address_text.setText('')
        self.contact_text.setText('')
        
    def parse_address(self):
        try:
            address = self.input_edit.text()
            if not address:
                self.clear_display()
                return
                
            components = self.completer.complete_address(address)
            
            # 检查是否解析成功
            if not any(components.values()):
                QMessageBox.warning(self, '解析失败', '无法解析该地址，请检查地址格式是否正确。')
                return
                
            # 保存到历史记录前，将map_data转换为base64字符串
            if 'map_data' in components:
                import base64
                components['map_data'] = base64.b64encode(components['map_data']).decode('utf-8')
            
            # 保存到历史记录
            history_item = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'address': address,
                'components': components
            }
            self.history.append(history_item)
            self.save_history()
            self.update_history_list()
            
            self.display_result(components)
        except Exception as e:
            QMessageBox.critical(self, '错误', f'解析过程中发生错误：{str(e)}')
            self.clear_display()
        
    def display_result(self, components):
        # 区域信息（仅显示省市区街道）
        region_parts = []
        # 按顺序添加行政区划信息
        if components.get('province'): 
            # 如果是直辖市，显示"北京 北京市"这样的格式
            if components['province'] in ['北京市', '上海市', '天津市', '重庆市']:
                # 去掉"市"字后添加省份名
                province_name = components['province'][:-1]
                region_parts.append(province_name)
                region_parts.append(components['province'])
            else:
                # 非直辖市正常显示省市
                region_parts.append(components['province'])
                if components.get('city'): 
                    region_parts.append(components['city'])
        elif components.get('city'):  # 如果没有省份但有城市
            region_parts.append(components['city'])
            
        if components.get('district'): 
            region_parts.append(components['district'])
        if components.get('street'): 
            # 从street中提取街道名称，去除小区等信息
            street = components['street']
            # 如果包含多个部分（用空格分隔），只取第一个街道部分
            street_parts = street.split()
            if street_parts:
                for part in street_parts:
                    if any(suffix in part for suffix in ['街道', '路', '街', '道']):
                        region_parts.append(part)
                        break
        self.region_text.setText(' '.join(region_parts))
        
        # 详细地址（显示小区、楼号、单元、房间号等信息）
        address_parts = []
        # 添加小区/院信息
        if components.get('street'):
            street_parts = components['street'].split()
            for part in street_parts:
                if any(keyword in part for keyword in ['号院', '小区', '公寓', '家园', '花园', '广场', '大厦']):
                    address_parts.append(part)
        
        # 添加楼号
        if components.get('building'):
            address_parts.append(components['building'])
        
        # 添加单元号
        if components.get('unit'):
            address_parts.append(components['unit'])
            
        # 添加房间号
        if components.get('room'):
            room = components['room']
            if not room.endswith('室'):
                room += '室'
            address_parts.append(room)
            
        self.address_text.setText(' '.join(address_parts))
        
        # 联系人信息（姓名 电话）
        contact_parts = []
        if components.get('name'): 
            contact_parts.append(components['name'])
        if components.get('phone'): 
            contact_parts.append(components['phone'])
        self.contact_text.setText(' '.join(contact_parts))
        
        # 显示地图
        self.show_map(components)
        
        # 更新天气信息显示
        if components.get('weather'):
            weather = components['weather']
            if weather.get('current'):
                current = weather['current']
                weather_text = f"天气: {current['weather']['desc']} "
                weather_text += f"温度: {current['temperature']} "
                weather_text += f"风向: {current['wind']['direction']} "
                weather_text += f"湿度: {current['humidity']}"
                self.weather_label.setText(weather_text)
            elif weather.get('forecast'):
                # 如果没有实时天气，显示今天的预报
                today = weather['forecast'][0]
                weather_text = f"今日天气: {today['day']['weather']['desc']} "
                weather_text += f"温度: {today['day']['temperature']}/{today['night']['temperature']} "
                weather_text += f"风向: {today['day']['wind']['direction']}"
                self.weather_label.setText(weather_text)
        else:
            self.weather_label.clear()
        
    def show_map(self, components):
        """显示地址位置的静态地图"""
        try:
            # 获取地址的经纬度
            address = f"{components['province']}{components['city']}{components['district']}{components['street']}"
            if components['building']:
                address += components['building']
                
            # 使用地理编码获取经纬度
            geo_result = self.completer.parser._geo_code(address)
            if geo_result.get('status') == '1' and geo_result.get('geocodes'):
                location = geo_result['geocodes'][0].get('location')
                if location:
                    # 构建静态地图URL
                    params = {
                        "location": location,
                        "zoom": 15,
                        "size": "800*600",
                        "markers": f"large,0xFF0000,A:{location}",  # 添加红色标记
                        "key": self.completer.parser.key
                    }
                    
                    # 发送请求获取地图图片
                    response = requests.get("https://restapi.amap.com/v3/staticmap", params=params)
                    if response.status_code == 200:
                        # 将图片数据转换为QPixmap
                        image = QImage.fromData(response.content)
                        pixmap = QPixmap.fromImage(image)
                        
                        # 显示缩略图
                        self.map_label.setPixmap(pixmap.scaled(
                            self.map_label.size(),
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation
                        ))
                        
                        # 存储原始图片用于查看器
                        self.original_map = pixmap
                        
                        # 保存图片数据到components中
                        components['map_data'] = response.content
                        
                        # 添加点击事件
                        self.map_label.mousePressEvent = self.show_map_viewer
                        self.map_label.setCursor(Qt.PointingHandCursor)
                        self.map_label.setToolTip("点击查看大图")
                        
                    else:
                        self.map_label.setText("地图加载失败")
                else:
                    self.map_label.setText("无法获取位置信息")
            else:
                self.map_label.setText("地址解析失败")
                
        except Exception as e:
            print(f"地图显示错误: {str(e)}")
            self.map_label.setText("地图显示错误")
        
    def show_map_viewer(self, event):
        """显示地图查看器"""
        if hasattr(self, 'original_map'):
            viewer = MapViewerDialog(self)
            viewer.set_image(self.original_map)
            viewer.exec_()

    def show_about(self):
        """显示关于对话框"""
        about_text = f"""
        <h3>地址解析工具 v{self.VERSION}</h3>
        <p>作者: {self.AUTHOR}</p>
        <p>基于高德地图API的地址解析工具，支持智能地址解析、天气查询、地图显示等功能。</p>
        <p>功能特点:</p>
        <ul>
            <li>智能地址解析和补全</li>
            <li>行政区划识别</li>
            <li>特殊地点(学校、医院等)智能识别</li>
            <li>天气信息查询和展示</li>
            <li>地图位置显示和交互</li>
            <li>历史记录管理</li>
            <li>数据导出功能</li>
            <li>深色/浅色主题切换</li>
        </ul>
        <p>开源地址: <a href="https://github.com/QiKeO/address-parser">https://github.com/QiKeO/address-parser</a></p>
        <p>问题反馈: <a href="https://github.com/QiKeO/address-parser/issues">提交Issue</a></p>
        <p>开源协议: MIT License</p>
        """
        QMessageBox.about(self, "关于", about_text)

    def export_history(self):
        """导出历史记录"""
        try:
            # 选择保存文件夹
            from PyQt5.QtWidgets import QFileDialog
            # 创建默认文件夹名称（替换冒号为下划线）
            current_time = datetime.now().strftime('%Y-%m-%d %H-%M-%S')  # 使用横杠替换冒号
            folder_name = f"地址解析工具_{current_time}"
            
            # 选择保存位置
            base_folder = QFileDialog.getExistingDirectory(
                self,
                "选择导出位置",
                os.getcwd()
            )
            
            if base_folder:
                # 创建导出文件夹
                export_folder = os.path.join(base_folder, folder_name)
                os.makedirs(export_folder, exist_ok=True)
                
                # 创建CSV文件
                csv_file = os.path.join(export_folder, f"历史记录_{current_time}.csv")
                with open(csv_file, 'w', encoding='utf-8-sig') as f:
                    # 写入标题行
                    headers = ["时间", "地址", "省份", "城市", "区县", "街道", "建筑", "单元", "房间", "联系人", "电话", "地图文件"]
                    f.write(','.join(headers) + '\n')
                    
                    # 写入历史记录
                    for i, item in enumerate(self.history):
                        components = item['components']
                        
                        # 保存地图图片(如果有)
                        map_filename = ""
                        if 'map_data' in components:
                            map_filename = f"地图_{i+1}.png"
                            map_path = os.path.join(export_folder, map_filename)
                            with open(map_path, 'wb') as map_file:
                                map_file.write(components['map_data'])
                        
                        # 准备CSV行数据
                        row = [
                            item['timestamp'],
                            item['address'],
                            components.get('province', ''),
                            components.get('city', ''),
                            components.get('district', ''),
                            components.get('street', ''),
                            components.get('building', ''),
                            components.get('unit', ''),
                            components.get('room', ''),
                            components.get('name', ''),
                            components.get('phone', ''),
                            map_filename
                        ]
                        
                        # 处理CSV特殊字符
                        escaped_row = []
                        for field in row:
                            field_str = str(field)
                            if '"' in field_str:
                                # 使用常规字符串格式化而不是f-string
                                field_str = '"{}"'.format(field_str.replace('"', '""'))
                            elif ',' in field_str:
                                field_str = '"{}"'.format(field_str)
                            escaped_row.append(field_str)
                        
                        f.write(','.join(escaped_row) + '\n')
                
                QMessageBox.information(self, "导出成功", f"历史记录已导出到:\n{export_folder}")
                
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出历史记录时发生错误：{str(e)}")

    def show_api_settings(self, first_time=False):
        """显示API设置对话框"""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("API设置")
            dialog.setFixedSize(400, 250)  # 固定窗口大小，防止缩放
            dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)  # 移除帮助按钮
            layout = QVBoxLayout()
            layout.setSpacing(15)  # 增加间距
            
            # 说明文本
            info_label = QLabel(
                "<h3>配置高德地图API Key</h3>"
                "<p>如果您还没有API Key，请访问高德开放平台申请：</p>"
                '<p><a href="https://lbs.amap.com/" style="color: #0066cc;">https://lbs.amap.com/</a></p>'
                "<p style='color: #666666;'>注：申请Web服务API Key时，请确保添加正确的服务平台信息。</p>"
            )
            info_label.setOpenExternalLinks(True)
            info_label.setWordWrap(True)
            info_label.setStyleSheet("""
                QLabel {
                    padding: 10px;
                    background-color: #f8f9fa;
                    border-radius: 4px;
                }
            """)
            layout.addWidget(info_label)
            
            # API密钥设置
            key_group = QGroupBox("API Key配置")
            key_layout = QVBoxLayout()
            key_layout.setSpacing(10)
            
            key_edit = QLineEdit()
            key_edit.setPlaceholderText("请输入您的API Key...")
            key_edit.setText(self.completer.parser.key)
            key_edit.setMinimumHeight(30)
            key_edit.setStyleSheet("""
                QLineEdit {
                    padding: 5px 10px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    background-color: white;
                }
                QLineEdit:focus {
                    border-color: #0066cc;
                }
            """)
            key_layout.addWidget(key_edit)
            key_group.setLayout(key_layout)
            layout.addWidget(key_group)
            
            # 按钮布局
            btn_layout = QHBoxLayout()
            btn_layout.setSpacing(10)
            
            save_btn = QPushButton("保存")
            cancel_btn = QPushButton("取消")
            
            # 设置按钮样式
            button_style = """
                QPushButton {
                    padding: 8px 20px;
                    border-radius: 4px;
                    font-weight: bold;
                    min-width: 80px;
                }
            """
            
            save_btn.setStyleSheet(button_style + """
                QPushButton {
                    background-color: #0066cc;
                    color: white;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #0052a3;
                }
            """)
            
            cancel_btn.setStyleSheet(button_style + """
                QPushButton {
                    background-color: #f8f9fa;
                    border: 1px solid #ddd;
                    color: #333;
                }
                QPushButton:hover {
                    background-color: #e9ecef;
                }
            """)
            
            btn_layout.addStretch()
            btn_layout.addWidget(save_btn)
            btn_layout.addWidget(cancel_btn)
            layout.addLayout(btn_layout)
            
            dialog.setLayout(layout)
            
            # 设置对话框样式
            dialog.setStyleSheet("""
                QDialog {
                    background-color: white;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    margin-top: 12px;
                    padding-top: 12px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
            """)
            
            def save_settings():
                new_key = key_edit.text().strip()
                if new_key:
                    if self.completer.parser._validate_key(new_key):
                        self.completer.parser.key = new_key
                        # 保存到配置文件
                        with open(self.config_file, 'w', encoding='utf-8') as f:
                            json.dump({'api_key': new_key}, f, ensure_ascii=False, indent=2)
                        QMessageBox.information(dialog, "成功", "API Key验证成功并已保存")
                        dialog.accept()
                    else:
                        QMessageBox.warning(dialog, "验证失败", "API Key无效，请检查后重试")
                else:
                    QMessageBox.warning(dialog, "输入错误", "API Key不能为空")
            
            def on_cancel():
                if first_time:
                    reply = QMessageBox.question(
                        dialog,
                        "确认退出",
                        "没有配置API Key将无法使用本程序，确定要退出吗？",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    if reply == QMessageBox.Yes:
                        dialog.reject()
                        self.close()
                else:
                    dialog.reject()
            
            save_btn.clicked.connect(save_settings)
            cancel_btn.clicked.connect(on_cancel)
            
            if first_time:
                dialog.setModal(True)
            
            dialog.exec_()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"显示设置对话框时发生错误：{str(e)}")

    def change_theme(self, theme: str):
        """切换主题"""
        if theme == 'light':
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #ffffff;
                }
                QGroupBox {
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    margin-top: 8px;
                    padding-top: 8px;
                }
                QGroupBox::title {
                    color: #333333;
                }
                QLineEdit, QTextEdit, QListWidget {
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 4px;
                    background-color: #ffffff;
                    color: #333333;
                }
                QPushButton {
                    background-color: #f0f0f0;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 4px 8px;
                    color: #333333;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
                QLabel {
                    color: #333333;
                }
                QStatusBar {
                    color: #666666;
                }
                QScrollArea {
                    background-color: transparent;
                    border: none;
                }
                QScrollArea > QWidget > QWidget {
                    background-color: transparent;
                }
                QDialog {
                    background-color: #ffffff;
                }
                QComboBox {
                    background-color: #ffffff;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 4px;
                    color: #333333;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox::down-arrow {
                    image: url(icons/down-arrow-dark.png);
                }
            """)
        elif theme == 'dark':
            dark_style = """
                /* 主窗口和对话框 */
                QMainWindow, QDialog, QMessageBox, QInputDialog {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                
                /* 所有标签和文本 */
                QLabel, QLineEdit, QTextEdit, QListWidget, QComboBox, QPushButton,
                QMessageBox QLabel, QInputDialog QLabel, QGroupBox {
                    color: #ffffff;
                }
                
                /* 输入框和列表 */
                QLineEdit, QTextEdit, QListWidget, QComboBox {
                    background-color: #333333;
                    border: 1px solid #404040;
                    border-radius: 4px;
                    padding: 4px;
                }
                
                /* 按钮样式 */
                QPushButton {
                    background-color: #404040;
                    border: 1px solid #505050;
                    border-radius: 4px;
                    padding: 4px 8px;
                    min-width: 70px;
                }
                QPushButton:hover {
                    background-color: #505050;
                }
                
                /* 分组框 */
                QGroupBox {
                    border: 1px solid #404040;
                    border-radius: 4px;
                    margin-top: 8px;
                    padding-top: 8px;
                }
                
                /* 菜单栏和菜单 */
                QMenuBar, QMenu {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QMenuBar::item:selected, QMenu::item:selected {
                    background-color: #404040;
                }
                QMenu {
                    border: 1px solid #404040;
                }
                
                /* 滚动区域 */
                QScrollArea {
                    background-color: transparent;
                    border: none;
                }
                QScrollArea > QWidget > QWidget {
                    background-color: transparent;
                }
                
                /* 下拉框 */
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox::down-arrow {
                    image: url(icons/down-arrow-light.png);
                }
                
                /* 对话框特殊处理 */
                QDialog QWidget, QMessageBox QWidget {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                
                /* 状态栏 */
                QStatusBar {
                    color: #cccccc;
                }
                QStatusBar QLabel {
                    color: #cccccc;
                }
                
                /* 链接颜色 */
                QLabel[link="true"] {
                    color: #3daee9;
                }
            """
            self.setStyleSheet(dark_style)
        else:  # default
            self.setStyleSheet("")  # 使用默认主题
        
        # 重新设置地图标签的样式和事件
        if hasattr(self, 'original_map'):
            self.map_label.setPixmap(self.original_map.scaled(
                self.map_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))
            self.map_label.mousePressEvent = self.show_map_viewer
            self.map_label.setCursor(Qt.PointingHandCursor)
            self.map_label.setToolTip("点击查看大图")

    def init_map_controls(self):
        """初始化地图控制区域"""
        map_control_group = QGroupBox("地图控制")
        map_control_layout = QHBoxLayout()
        
        # 缩放控制
        zoom_group = QWidget()
        zoom_layout = QHBoxLayout()
        zoom_label = QLabel("缩放:")
        zoom_in_btn = QPushButton("+")
        zoom_out_btn = QPushButton("-")
        zoom_reset_btn = QPushButton("重置")
        
        zoom_in_btn.clicked.connect(lambda: self.map_label.zoom_in())
        zoom_out_btn.clicked.connect(lambda: self.map_label.zoom_out())
        zoom_reset_btn.clicked.connect(lambda: self.map_label.reset_zoom())
        
        zoom_layout.addWidget(zoom_label)
        zoom_layout.addWidget(zoom_in_btn)
        zoom_layout.addWidget(zoom_out_btn)
        zoom_layout.addWidget(zoom_reset_btn)
        zoom_group.setLayout(zoom_layout)
        
        # 地图类型选择
        type_group = QWidget()
        type_layout = QHBoxLayout()
        type_label = QLabel("地图类型:")
        self.map_type_combo = QComboBox()
        self.map_type_combo.addItems(["标准地图", "卫星图", "路网图"])
        self.map_type_combo.currentIndexChanged.connect(self.change_map_type)
        
        type_layout.addWidget(type_label)
        type_layout.addWidget(self.map_type_combo)
        type_group.setLayout(type_layout)
        
        map_control_layout.addWidget(zoom_group)
        map_control_layout.addWidget(type_group)
        map_control_group.setLayout(map_control_layout)
        
        return map_control_group

    def show_current_location_weather(self):
        """显示当前位置的天气信息"""
        try:
            # 获取当前IP的城市信息
            ip_info = self.completer.parser._get_current_city_info()
            if ip_info:
                # 获取天气信息
                weather = self.completer.parser._get_weather_info(ip_info.get('adcode', ''))
                if weather:
                    if weather.get('current'):
                        current = weather['current']
                        weather_text = f"当前位置: {ip_info.get('city', '')} | "
                        weather_text += f"天气: {current['weather']['desc']} "
                        weather_text += f"温度: {current['temperature']} "
                        weather_text += f"风向: {current['wind']['direction']} "
                        weather_text += f"湿度: {current['humidity']}"
                        self.weather_label.setText(weather_text)
                    elif weather.get('forecast'):
                        today = weather['forecast'][0]
                        weather_text = f"当前位置: {ip_info.get('city', '')} | "
                        weather_text += f"今日天气: {today['day']['weather']['desc']} "
                        weather_text += f"温度: {today['day']['temperature']}/{today['night']['temperature']} "
                        weather_text += f"风向: {today['day']['wind']['direction']}"
                        self.weather_label.setText(weather_text)
        except Exception as e:
            print(f"获取当前位置天气错误: {str(e)}")

    def check_api_key(self):
        """检查API Key是否已配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if config.get('api_key'):
                        self.completer.parser.key = config['api_key']
                        if self.completer.parser._validate_key(config['api_key']):
                            return
                        else:
                            msg_box = QMessageBox(self)
                            msg_box.setWindowTitle("API Key无效")
                            msg_box.setIcon(QMessageBox.Warning)
                            msg_box.setText(
                                "<h3>API Key验证失败</h3>"
                                "<p>当前配置的API Key已失效，请重新配置。</p>"
                                "<p>可能的原因：</p>"
                                "<ul>"
                                "<li>API Key已过期</li>"
                                "<li>API Key被禁用</li>"
                                "<li>API Key额度用尽</li>"
                                "</ul>"
                            )
                            msg_box.setTextFormat(Qt.RichText)
                            msg_box.exec_()
                            self.show_api_settings()
                            
            if not self.is_first_run:
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("未配置API Key")
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setText(
                    "<h3>请配置API Key</h3>"
                    "<p>程序需要有效的高德地图API Key才能正常使用。</p>"
                    "<p>您可以通过以下方式配置：</p>"
                    "<ul>"
                    '<li>点击菜单 <span style="color: #0066cc;">设置 -> API设置</span></li>'
                    '<li>使用快捷键 <span style="color: #0066cc;">Ctrl+A</span></li>'
                    "</ul>"
                )
                msg_box.setTextFormat(Qt.RichText)
                msg_box.exec_()
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"检查API Key时发生错误：{str(e)}")

    def show_welcome_dialog(self):
        """显示欢迎对话框"""
        welcome_text = f"""
        <h3>欢迎使用地址解析工具 v{self.VERSION}</h3>
        
        <p>首次使用需要配置高德地图API Key。</p>
        <p>如果您还没有API Key，请按以下步骤获取：</p>
        
        <ol>
            <li>访问高德开放平台：<a href="https://lbs.amap.com/">https://lbs.amap.com/</a></li>
            <li>注册账号并登录</li>
            <li>申请Web服务API Key</li>
            <li>将获取的Key填入下一步的设置对话框</li>
        </ol>
        
        <p style="color: #666666;">提示：API Key用于访问高德地图服务，是程序正常运行的必要条件。</p>
        """
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("欢迎使用")
        msg_box.setIconPixmap(QPixmap(os.path.join(self.icon_path, 'welcome.png')).scaled(64, 64))
        msg_box.setText(welcome_text)
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.Yes)
        msg_box.button(QMessageBox.Yes).setText("立即配置")
        msg_box.button(QMessageBox.No).setText("稍后配置")
        
        # 延迟显示欢迎对话框，让主窗口先显示
        QTimer.singleShot(500, lambda: self._show_welcome_dialog(msg_box))

    def _show_welcome_dialog(self, msg_box):
        """显示欢迎对话框并处理结果"""
        reply = msg_box.exec_()
        
        if reply == QMessageBox.Yes:
            self.show_api_settings(first_time=True)
        else:
            warning_box = QMessageBox(self)
            warning_box.setWindowTitle("提示")
            warning_box.setIcon(QMessageBox.Warning)
            warning_box.setText(
                "您可以稍后通过以下方式配置API Key：\n\n"
                "1. 点击菜单 设置 -> API设置\n"
                "2. 使用快捷键 Ctrl+A\n\n"
                "注意：在配置有效的API Key之前，程序的功能将无法使用。"
            )
            warning_box.exec_()

class MapViewerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('地图查看器')
        self.setWindowFlags(Qt.Window)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # 移除边距
        
        # 创建滚动区域
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建地图标签
        self.map_label = MapLabel()
        self.scroll_area.setWidget(self.map_label)
        
        layout.addWidget(self.scroll_area)
        
        # 设置窗口大小为父窗口大小
        if self.parent_window:
            parent_size = self.parent_window.size()
            self.resize(parent_size)
        
    def set_image(self, pixmap):
        # 设置原始图片
        self.map_label.setPixmap(pixmap)
        self.map_label.original_pixmap = pixmap
        self.map_label.scale = 1.0
        
        # 调整滚动区域大小以适应图片
        self.adjustScrollArea()
        
    def adjustScrollArea(self):
        """调整滚动区域以适应图片和窗口"""
        if self.map_label.original_pixmap:
            # 获取图片和窗口的尺寸
            pixmap_size = self.map_label.original_pixmap.size()
            window_size = self.size()
            
            # 设置滚动区域的最小大小
            self.scroll_area.setMinimumSize(
                min(pixmap_size.width(), window_size.width()),
                min(pixmap_size.height(), window_size.height())
            )
            
    def resizeEvent(self, event):
        """窗口大小改变时调整滚动区域"""
        super().resizeEvent(event)
        self.adjustScrollArea()

class MapLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.scale = 1.0
        self.original_pixmap = None
        self.setMouseTracking(True)
        self.last_pos = None
        
        # 添加缩放控制
        self.min_scale = 0.1
        self.max_scale = 5.0
        self.scale_step = 0.1
        
        # 添加拖动状态
        self.dragging = False
        self.drag_start = None
        
        # 添加双击事件
        self.setMouseTracking(True)
        
    def wheelEvent(self, event: QWheelEvent):
        if self.original_pixmap:
            # 获取鼠标位置
            pos = event.pos()
            
            # 计算缩放比例
            old_scale = self.scale
            delta = event.angleDelta().y()
            if delta > 0:
                self.scale = min(self.scale * 1.1, 5.0)
            else:
                self.scale = max(self.scale / 1.1, 0.1)
                
            # 更新图片大小
            scaled_pixmap = self.original_pixmap.scaled(
                self.original_pixmap.size() * self.scale,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)
            
            # 调整滚动条位置以保持鼠标指向的点不变
            if old_scale != self.scale:
                scrollbar = self.parent().parent()
                ratio = self.scale / old_scale
                
                # 计算新的滚动条位置
                h_value = scrollbar.horizontalScrollBar().value()
                v_value = scrollbar.verticalScrollBar().value()
                
                # 调整水平滚动条
                new_h = int(h_value * ratio + (ratio - 1) * pos.x())
                scrollbar.horizontalScrollBar().setValue(new_h)
                
                # 调整垂直滚动条
                new_v = int(v_value * ratio + (ratio - 1) * pos.y())
                scrollbar.verticalScrollBar().setValue(new_v)
            
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_pos = event.pos()
            
    def mouseMoveEvent(self, event):
        if self.last_pos and event.buttons() & Qt.LeftButton:
            # 计算移动距离
            delta = event.pos() - self.last_pos
            # 移动滚动条
            scrollbar = self.parent().parent()
            scrollbar.horizontalScrollBar().setValue(
                scrollbar.horizontalScrollBar().value() - delta.x()
            )
            scrollbar.verticalScrollBar().setValue(
                scrollbar.verticalScrollBar().value() - delta.y()
            )
            self.last_pos = event.pos()
            
    def mouseReleaseEvent(self, event):
        self.last_pos = None

    def mouseDoubleClickEvent(self, event):
        """双击重置缩放"""
        if self.original_pixmap:
            self.scale = 1.0
            self.update_map()

class WeatherDialog(QDialog):
    def __init__(self, weather_data: dict, parent=None):
        super().__init__(parent)
        self.weather_data = weather_data
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("天气详情")
        self.setMinimumWidth(400)
        layout = QVBoxLayout()
        
        # 当前天气
        if self.weather_data.get('current'):
            current_group = QGroupBox("实时天气")
            current_layout = QGridLayout()
            current = self.weather_data['current']
            
            current_layout.addWidget(QLabel("天气:"), 0, 0)
            current_layout.addWidget(QLabel(current['weather']['desc']), 0, 1)
            current_layout.addWidget(QLabel("温度:"), 1, 0)
            current_layout.addWidget(QLabel(current['temperature']), 1, 1)
            current_layout.addWidget(QLabel("风向:"), 2, 0)
            current_layout.addWidget(QLabel(current['wind']['direction']), 2, 1)
            current_layout.addWidget(QLabel("湿度:"), 3, 0)
            current_layout.addWidget(QLabel(current['humidity']), 3, 1)
            
            current_group.setLayout(current_layout)
            layout.addWidget(current_group)
            
        # 天气预报
        if self.weather_data.get('forecast'):
            forecast_group = QGroupBox("未来天气预报")
            forecast_layout = QVBoxLayout()
            
            for day in self.weather_data['forecast']:
                day_widget = QWidget()
                day_layout = QGridLayout()
                
                day_layout.addWidget(QLabel(f"日期: {day['date']} ({day['week']}"), 0, 0, 1, 2)
                day_layout.addWidget(QLabel("白天:"), 1, 0)
                day_layout.addWidget(QLabel(f"{day['day']['weather']['desc']} {day['day']['temperature']}"), 1, 1)
                day_layout.addWidget(QLabel("夜间:"), 2, 0)
                day_layout.addWidget(QLabel(f"{day['night']['weather']['desc']} {day['night']['temperature']}"), 2, 1)
                
                day_widget.setLayout(day_layout)
                forecast_layout.addWidget(day_widget)
                
            forecast_group.setLayout(forecast_layout)
            layout.addWidget(forecast_group)
            
        self.setLayout(layout)

def main():
    app = QApplication(sys.argv)
    window = AddressWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main() 