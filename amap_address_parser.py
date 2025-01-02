import http.client
import json
import urllib.parse
from typing import Dict, List
import re
import time
from datetime import datetime

class AmapError(Exception):
    """高德地图API错误"""
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(f"错误码 {code}: {message}")

class AmapAddressParser:
    # 错误码映射
    ERROR_MESSAGES = {
        "10001": "API密钥不正确或已过期",
        "10002": "没有权限使用该服务",
        "10003": "访问量超出日限额",
        "10004": "访问过于频繁",
        "10005": "IP白名单错误",
        "10009": "请求key与绑定平台不符",
        "10010": "IP访问超限",
        "20000": "请求参数非法",
        "20001": "缺少必填参数",
        "20011": "查询点在海外，但无海外地图权限",
        "20012": "查询信息存在非法内容",
        "30000": "服务响应失败，请检查参数"
    }
    
    # 天气现象映射
    WEATHER_DESC = {
        # 晴朗天气
        "晴": "晴朗无云",
        "少云": "晴朗，有少量云朵",
        "晴间多云": "晴天为主，间有云层",
        "多云": "云量较多",
        "阴": "云层厚密，天色阴沉",
        
        # 风力天气
        "有风": "有明显的风",
        "平静": "无风或微风",
        "微风": "树叶轻微摇动",
        "和风": "树枝摇动",
        "清风": "吹动衣物",
        "强风/劲风": "大树摇动",
        "疾风": "行走困难",
        "大风": "树枝折断",
        "烈风": "房屋损坏",
        
        # 雨雪天气
        "阵雨": "短时降雨",
        "雷阵雨": "雷雨天气",
        "小雨": "雨量较小",
        "中雨": "明显降雨",
        "大雨": "雨量较大",
        "暴雨": "雨量很大",
        "雨夹雪": "雨雪混合",
        "小雪": "雪量较小",
        "中雪": "明显降雪",
        "大雪": "雪量较大",
        
        # 特殊天气
        "雾": "能见度较低",
        "浓雾": "能见度很低",
        "霾": "空气混浊",
        "热": "气温偏高",
        "冷": "气温偏低"
    }
    
    # 风力等级描述
    WIND_POWER = {
        "≤3": "微风(小于12km/h)",
        "4": "和风(13-19km/h)",
        "5": "清风(20-29km/h)",
        "6": "强风(30-39km/h)",
        "7": "疾风(40-49km/h)",
        "8": "大风(50-61km/h)",
        "9": "烈风(62-74km/h)",
        "10": "狂风(75-87km/h)",
        "11": "暴风(88-102km/h)",
        "12": "台风(≥103km/h)"
    }
    
    # 风向描述
    WIND_DIRECTION = {
        "无风向": "无明显风向",
        "东北": "东北风",
        "东": "东风",
        "东南": "东南风",
        "南": "南风",
        "西南": "西南风",
        "西": "西风",
        "西北": "西北风",
        "北": "北风",
        "旋转不定": "风向不定"
    }
    
    def __init__(self):
        self.host = "restapi.amap.com"
        self.key = ""  # 高德key
        self.last_request_time = 0
        self.request_count = 0
        self._quota_counter = {}
        self.district_cache = {}
        
    def _check_response(self, result: Dict) -> None:
        """检查API响应结果"""
        if not result:
            raise AmapError("30000", "服务响应为空")
            
        status = result.get('status')
        info = result.get('info')
        infocode = result.get('infocode')
        
        if status != '1':
            error_msg = self.ERROR_MESSAGES.get(infocode, info)
            raise AmapError(infocode, error_msg)
    
    def _rate_limit(self):
        """请求频率限制"""
        current_time = time.time()
        # 计算距离上次请求的时间间隔
        time_diff = current_time - self.last_request_time
        
        # 如果间隔小于0.1秒(每秒最多10次请求)，则等待
        if time_diff < 0.1:
            time.sleep(0.1 - time_diff)
        
        self.last_request_time = time.time()
        self.request_count += 1
        
    def parse_address(self, address: str, coordinates: str = None, coordsys: str = None) -> Dict[str, str]:
        """使用高德地图API解析地址
        
        Args:
            address: 要解析的地址
            coordinates: 可选的坐标信息 (经度,纬度)
            coordsys: 坐标系类型 (gps/mapbar/baidu)
        """
        try:
            # 清理地址字符串
            clean_address = self._clean_address_string(address)
            
            # 如果提供了坐标，先进行转换
            location = None
            if coordinates:
                if coordsys and coordsys != 'autonavi':
                    location = self._convert_coordinates(coordinates, coordsys)
                else:
                    location = coordinates
                    
            # 如果有坐标，优先使用坐标进行解析
            if location:
                regeo_result = self._regeo_code(location)
                if regeo_result.get('status') == '1' and regeo_result.get('regeocode'):
                    regeo = regeo_result['regeocode']
                    address_component = regeo.get('addressComponent', {})
                    
                    # 使用逆地理编码结果
                    components = {
                        'province': address_component.get('province', ''),
                        'city': address_component.get('city', '') or address_component.get('province', ''),
                        'district': address_component.get('district', ''),
                        'street': address_component.get('township', ''),
                        'building': '',
                        'unit': '',
                        'room': '',
                        'name': '',
                        'phone': '',
                        'weather': None
                    }
                    
                    # 提取详细地址信息
                    if address:
                        # 提取联系人信息
                        name, phone = self._extract_contact_info(address)
                        components['name'] = name
                        components['phone'] = phone
                        
                        # 提取建筑物信息
                        building_info = self._extract_building_info(address, components)
                        components.update(building_info)
                        
                    # 获取天气信息
                    weather_info = None
                    if address_component.get('adcode'):
                        weather_info = self._get_weather_info(address_component['adcode'])
                    
                    return components
                    
            # 如果没有坐标或坐标解析失败，使用地址解析
            return self._parse_address_by_text(address)
            
        except Exception as e:
            print(f"地址解析错误: {str(e)}")
            return self._empty_components()
            
    def _geo_code(self, address: str) -> Dict:
        """地理编码：地址转换为经纬度"""
        try:
            params = {
                "address": address,
                "key": self.key,
                "output": "json"
            }
            
            query_string = urllib.parse.urlencode(params)
            path = f"/v3/geocode/geo?{query_string}"
            
            conn = http.client.HTTPSConnection(self.host)
            conn.request("GET", path)
            response = conn.getresponse()
            data = response.read().decode('utf-8')
            conn.close()
            
            return json.loads(data)
        except Exception as e:
            print(f"地理编码错误: {str(e)}")
            return {}
            
    def _regeo_code(self, location: str) -> Dict:
        """逆地理编码：经纬度转换为地址"""
        try:
            params = {
                "location": location,
                "key": self.key,
                "extensions": "all",
                "output": "json"
            }
            
            query_string = urllib.parse.urlencode(params)
            path = f"/v3/geocode/regeo?{query_string}"
            
            conn = http.client.HTTPSConnection(self.host)
            conn.request("GET", path)
            response = conn.getresponse()
            data = response.read().decode('utf-8')
            conn.close()
            
            return json.loads(data)
        except Exception as e:
            print(f"逆地理编码错误: {str(e)}")
            return {}
        
    def _clean_address_string(self, address: str) -> str:
        """清理地址字符串"""
        # 替换换行符和特殊空白字符为普通空格
        address = re.sub(r'[\r\n\t\u3000\xa0]+', ' ', address)
        
        # 移除重复的行政区划信息
        for region in ['北京', '上海', '天津', '重庆']:
            pattern = f'{region}+(?:市)?{region}+(?:市)?'
            address = re.sub(pattern, f'{region}市', address)
            
        # 移除省市区重复信息
        address = re.sub(r'([省市区县])\1+', r'\1', address)
        
        # 处理街道重复信息
        address = re.sub(r'([\u4e00-\u9fa5]+(?:街道|路|街|道))\1+', r'\1', address)
        
        # 替换多个空格为单个空格
        address = re.sub(r'\s+', ' ', address)
        
        # 移除首尾空白
        address = address.strip()
        
        # 移除行政区划之间的多余空格
        address = re.sub(r'([省市区县])\s+(?=[\u4e00-\u9fa5])', r'\1', address)
        
        # 处理行政区划和地点名称重复的情况
        parts = address.split()
        seen = set()
        cleaned_parts = []
        for part in parts:
            if part not in seen:
                cleaned_parts.append(part)
                seen.add(part)
        
        # 处理县级地址
        county_patterns = [
            r'([临|蒲|永|洪|清]县)',  # 常见的县名
            r'([\u4e00-\u9fa5]{1,3}[县])'  # 通用县名匹配
        ]
        
        for pattern in county_patterns:
            matches = re.finditer(pattern, address)
            for match in matches:
                county = match.group()
                # 确保县名前有省市信息
                if not any(region in address[:match.start()] for region in ['省', '市']):
                    # 尝试获取完整的行政区划
                    district_info = self._get_district_by_name(county)
                    if district_info:
                        province = district_info.get('province', '')
                        city = district_info.get('city', '')
                        address = f"{province}{city}{address}"
                        
        return ' '.join(cleaned_parts)
        
    def _extract_address_components(self, formatted_address: str, province: str, city: str, district: str) -> Dict[str, str]:
        """从格式化地址中提取街道和详细地址信息"""
        components = {}
        
        # 清理地址字符串
        formatted_address = self._clean_address_string(formatted_address)
        detail_address = formatted_address  # 保存完整地址用于提取详细信息
        
        # 移除已知的省市区信息
        for region in [province, city, district]:
            if region:
                formatted_address = formatted_address.replace(region, '')
        
        # 提取街道名称
        street_patterns = [
            r'[\u4e00-\u9fa5]+街道',  # 匹配街道
            r'[\u4e00-\u9fa5]+(?:路|街|道|巷|弄)'  # 匹配道路
        ]
        
        street_parts = []
        for pattern in street_patterns:
            match = re.search(pattern, formatted_address)
            if match:
                street_part = match.group()
                if street_part not in street_parts:
                    street_parts.append(street_part)
                formatted_address = formatted_address.replace(street_part, '')
                detail_address = detail_address.replace(street_part, '')
        
        if street_parts:
            components['street'] = ' '.join(street_parts)
        
        # 从剩余文本中提取详细地址
        # 移除省市区街道等基本区域信息
        for region in [province, city, district] + street_parts:
            if region:
                detail_address = detail_address.replace(region, '')
        
        # 清理详细地址中的多余空格和标点
        detail_address = re.sub(r'[\s,，。、]+', ' ', detail_address).strip()
        
        # 如果详细地址不为空，则作为building
        if detail_address:
            components['building'] = detail_address
            
            # 尝试提取单元号
            unit_match = re.search(r'\d+单元', detail_address)
            if unit_match:
                components['unit'] = unit_match.group()
                components['building'] = components['building'].replace(unit_match.group(), '').strip()
            
            # 尝试提取房间号（放在最后提取）
            room_patterns = [
                r'(?<!\d)\d{2,4}(?=室|房|$)',  # 标准房间号
                r'[A-Za-z]\d{2,4}(?=室|房|$)',  # 字母开头的房间号
                r'[东南西北]\d{2,4}(?=室|房|$)',  # 方位开头的房间号
                r'(?<=-)\d{2,4}(?=室|房|$)',    # 带连字符的房间号
            ]
            
            for pattern in room_patterns:
                room_match = re.search(pattern, detail_address)
                if room_match:
                    components['room'] = room_match.group()
                    components['building'] = components['building'].replace(room_match.group(), '').strip()
                    # 如果房间号后面有"室"，也一并移除
                    components['building'] = re.sub(r'室\s*$', '', components['building']).strip()
                    break
        
        # 清理building中的多余空格
        if components.get('building'):
            components['building'] = re.sub(r'\s+', ' ', components['building']).strip()
            # 移除building末尾可能残留的标点
            components['building'] = re.sub(r'[,，。、]+$', '', components['building']).strip()
        
        return components
        
    def _extract_contact_info(self, address: str) -> tuple:
        """提取姓名和电话信息"""
        name = ''
        phone = ''
        
        # 提取电话号码
        phone_match = re.search(r'1[3-9]\d{9}', address)
        if phone_match:
            phone = phone_match.group()
            address = address.replace(phone, '')
            
        # 提取姓名（优化姓名识别规则）
        name_pattern = r'(?:[\u4e00-\u9fa5]{2,3}(?:先生|女士|小姐)?|[\u4e00-\u9fa5]{1}(?:先生|女士|小姐))(?=\s|$|[，,。.]|1[3-9]\d{9})'
        name_match = re.search(name_pattern, address)
        
        # 增加更严格的姓名验证
        if name_match:
            potential_name = name_match.group().strip()
            # 排除地址关键词
            invalid_keywords = [
                '北京', '上海', '广州', '深圳',  # 城市名
                '省', '市', '区', '县', '镇',    # 行政区划
                '街道', '路', '街', '道', '巷',  # 道路
                '小区', '公寓', '家园', '花园',  # 小区
                '广场', '大厦', '大街', '号院'   # 建筑
            ]
            
            # 检查是否包含地址关键词
            if not any(keyword in potential_name for keyword in invalid_keywords):
                # 检查是否是常见姓氏开头
                common_surnames = ['王', '李', '张', '刘', '陈', '杨', '黄', '赵', '吴', '周', '徐', 
                                 '孙', '马', '朱', '胡', '郭', '何', '高', '林', '郑', '尹', '钱', '梁']
                if any(potential_name.startswith(surname) for surname in common_surnames):
                    name = potential_name
        
        return name, phone
        
    def _empty_components(self) -> Dict[str, str]:
        """返回空的地址组件"""
        return {
            'province': '',
            'city': '',
            'district': '',
            'street': '',
            'building': '',
            'unit': '',
            'room': '',
            'name': '',
            'phone': '',
            'weather': None
        } 
        
    def _extract_possible_street(self, formatted_address: str, regions_to_remove: list) -> str:
        """从格式化地址中提取可能的街道信息"""
        # 移除已知的省市区信息
        remaining_address = formatted_address
        for region in regions_to_remove:
            if region:
                remaining_address = remaining_address.replace(region, '')
        
        # 尝试匹配可能的街道信息
        street_patterns = [
            r'[\u4e00-\u9fa5]{2,}[街道]',  # 匹配xx街道
            r'[\u4e00-\u9fa5]{2,}[路](?!口)',  # 匹配xx路（排除路口）
            r'[\u4e00-\u9fa5]{2,}[街](?!道)',  # 匹配xx街（排除街道）
            r'[\u4e00-\u9fa5]{2,}[大道]',  # 匹配xx大道
            r'[\u4e00-\u9fa5]{2,}[广场]',  # 匹配xx广场
            r'[\u4e00-\u9fa5]{2,}[开发区]',  # 匹配xx开发区
            r'[\u4e00-\u9fa5]{2,}[工业园]',  # 匹配xx工业园
            r'[\u4e00-\u9fa5]{2,}[科技园]'   # 匹配xx科技园
        ]
        
        for pattern in street_patterns:
            match = re.search(pattern, remaining_address)
            if match:
                return match.group()
        
        # 如果没有匹配到任何模式，返回空字符串
        return '' 
        
    def _get_district_info(self, adcode: str) -> Dict:
        """获取行政区域信息"""
        # 先检查缓存
        if adcode in self.district_cache:
            return self.district_cache[adcode]
            
        try:
            params = {
                "keywords": adcode,
                "subdistrict": "3",  # 获取到街道级别
                "key": self.key,
                "output": "json"
            }
            
            query_string = urllib.parse.urlencode(params)
            path = f"/v3/config/district?{query_string}"
            
            conn = http.client.HTTPSConnection(self.host)
            conn.request("GET", path)
            response = conn.getresponse()
            data = response.read().decode('utf-8')
            conn.close()
            
            result = json.loads(data)
            if result.get('status') == '1' and result.get('districts'):
                self.district_cache[adcode] = result['districts'][0]
                return result['districts'][0]
                
        except Exception as e:
            print(f"行政区域查询错误: {str(e)}")
        return {}
        
    def _find_street_from_district(self, district_info: Dict, address: str) -> str:
        """从行政区域信息中查找街道"""
        try:
            # 获取所有街道列表
            streets = []
            if 'districts' in district_info:
                for city in district_info['districts']:
                    if 'districts' in city:
                        for district in city['districts']:
                            if 'districts' in district:
                                streets.extend(district['districts'])
            
            # 在地址中查找匹配的街道
            for street in streets:
                street_name = street['name']
                if street_name in address:
                    return street_name
                    
        except Exception as e:
            print(f"查找街道错误: {str(e)}")
        return '' 
        
    def _get_input_tips(self, keywords: str) -> Dict:
        """获取输入提示信息"""
        try:
            # 检查缓存
            cache_key = f"tips_{keywords}"
            if hasattr(self, '_tips_cache') and cache_key in self._tips_cache:
                return self._tips_cache[cache_key]
            
            # 获取结果
            params = {
                "keywords": keywords,
                "key": self.key,
                "datatype": "all",
                "city": self._get_current_city(),  # 优先显示当前城市的结果
                "citylimit": "true" if self._get_current_city() else "false",  # 如果有城市信息则限制在当前城市
                "output": "json"
            }
            
            result = self._make_request("/v3/assistant/inputtips", params)
            
            # 缓存结果
            if not hasattr(self, '_tips_cache'):
                self._tips_cache = {}
            self._tips_cache[cache_key] = result
            
            return result
            
        except Exception as e:
            print(f"输入提示API错误: {str(e)}")
            return {}
            
    def _get_current_city(self) -> str:
        """获取当前IP所在城市"""
        try:
            # 检查缓存
            if hasattr(self, '_current_city'):
                return self._current_city
                
            params = {
                "key": self.key,
                "output": "json"
            }
            
            result = self._make_request("/v3/ip", params)
            
            if result.get('status') == '1':
                city = result.get('city', '')
                # 缓存结果
                self._current_city = city
                return city
                
        except Exception as e:
            print(f"IP定位错误: {str(e)}")
        return ''
        
    def _extract_building_info(self, address: str, components: Dict[str, str]) -> Dict[str, str]:
        """提取详细地址信息"""
        result = {
            'building': '',
            'unit': '',
            'room': ''
        }
        
        # 移除已知的区域信息
        remaining_address = address
        for key in ['province', 'city']:  # 不移除district和street，因为可能是地址的一部分
            if components.get(key):
                remaining_address = remaining_address.replace(components[key], '')
        
        # 移除联系人信息
        if components.get('name'):
            remaining_address = remaining_address.replace(components['name'], '')
        if components.get('phone'):
            remaining_address = remaining_address.replace(components['phone'], '')
            
        # 清理地址字符串
        remaining_address = self._clean_address_string(remaining_address)
        
        # 检查是否是特殊地点（学校、医院等）
        special_keywords = [
            (r'[\u4e00-\u9fa5]+大学', False),  # (pattern, should_keep_district)
            (r'[\u4e00-\u9fa5]+学院', False),
            (r'[\u4e00-\u9fa5]+中学', True),
            (r'[\u4e00-\u9fa5]+一中', True),  # 添加一中的特殊处理
            (r'[\u4e00-\u9fa5]+二中', True),
            (r'[\u4e00-\u9fa5]+三中', True),
            (r'[\u4e00-\u9fa5]+小学', True),
            (r'[\u4e00-\u9fa5]+医院', True),
            (r'[\u4e00-\u9fa5]+政府', True),
            (r'[\u4e00-\u9fa5]+银行', False),
            (r'[\u4e00-\u9fa5]+广场', False)
        ]
        
        for pattern, should_keep_district in special_keywords:
            match = re.search(pattern, address)
            if match:
                # 如果是特殊地点，使用完整名称作为建筑物名称
                special_place = address
                for key in ['province', 'city']:
                    if components.get(key):
                        special_place = special_place.replace(components[key], '')
                        
                # 根据配置决定是否保留区县名称
                if not should_keep_district and components.get('district'):
                    special_place = special_place.replace(components['district'], '')
                    
                result['building'] = special_place.strip()
                return result
        
        # 如果不是特殊地点，继续原有的处理逻辑
        # 提取单元号
        unit_match = re.search(r'\d+单元', remaining_address)
        if unit_match:
            result['unit'] = unit_match.group()
            remaining_address = remaining_address.replace(unit_match.group(), '')
        
        # 提取房间号
        room_patterns = [
            r'(?<!\d)\d{2,4}(?=室|$)',  # 普通房间号
            r'[A-Za-z]\d{2,4}(?=室|$)',  # 字母开头的房间号
            r'(?<=-)\d{2,4}(?=室|$)'     # 带连字符的房间号
        ]
        
        for pattern in room_patterns:
            room_match = re.search(pattern, remaining_address)
            if room_match:
                result['room'] = room_match.group()
                remaining_address = remaining_address.replace(room_match.group(), '')
                # 移除"室"字
                remaining_address = re.sub(r'室\s*$', '', remaining_address)
                break
        
        # 剩余部分作为建筑物信息
        remaining_address = re.sub(r'\s+', ' ', remaining_address).strip()
        if remaining_address:
            result['building'] = remaining_address
        
        return result 
        
    def _make_request(self, path: str, params: Dict) -> Dict:
        """发送API请求"""
        try:
            # 检查配额
            if not self._check_quota(path):
                raise AmapError("10003", "超出日配额限制")
            
            self._rate_limit()
            
            query_string = urllib.parse.urlencode(params)
            full_path = f"{path}?{query_string}"
            
            conn = http.client.HTTPSConnection(self.host)
            conn.request("GET", full_path)
            response = conn.getresponse()
            data = response.read().decode('utf-8')
            conn.close()
            
            result = json.loads(data)
            self._check_response(result)
            return result
            
        except json.JSONDecodeError:
            raise AmapError("30000", "响应数据格式错误")
        except Exception as e:
            raise AmapError("30000", f"请求失败: {str(e)}") 
        
    def _extract_special_place(self, address: str) -> str:
        """提取特殊地点名称"""
        # 特殊地点的关键词
        special_keywords = [
            r'[\u4e00-\u9fa5]{1,10}[一二三四五六七八九十]\s*中',  # xx一中、xx二中等
            r'[\u4e00-\u9fa5]{1,10}中学',
            r'[\u4e00-\u9fa5]{1,10}小学',
            r'[\u4e00-\u9fa5]{1,10}医院',
            r'[\u4e00-\u9fa5]{1,10}大学',
            r'[\u4e00-\u9fa5]{1,10}学院',
            r'[\u4e00-\u9fa5]{1,10}政府',
            r'[\u4e00-\u9fa5]{1,10}银行',
            r'[\u4e00-\u9fa5]{1,10}商场',
            r'[\u4e00-\u9fa5]{1,10}广场'
        ]
        
        for pattern in special_keywords:
            match = re.search(pattern, address)
            if match:
                return match.group()
        
        return '' 
        
    def _validate_address_with_walking(self, address: str, reference_point: str = None) -> Dict:
        """使用步行路线验证地址并获取详细信息"""
        try:
            # 获取地址的经纬度
            geo_result = self._geo_code(address)
            if not geo_result.get('geocodes'):
                return {'valid': False}
            
            location = geo_result['geocodes'][0]['location']
            
            # 如果有参考点，验证两点间路线
            if reference_point:
                params = {
                    "origin": reference_point,
                    "destination": location,
                    "key": self.key,
                    "show_fields": "cost,navi",  # 获取更多信息
                    "alternative_route": "3"  # 获取3条备选路线
                }
                
                result = self._make_request("/v5/direction/walking", params)
                
                if result.get('status') == '1':
                    paths = result.get('route', {}).get('paths', [])
                    if paths:
                        # 获取最短路径
                        shortest_path = min(paths, key=lambda x: int(x.get('distance', '999999')))
                        distance = int(shortest_path.get('distance', '5001'))
                        
                        return {
                            'valid': distance <= 5000,
                            'distance': distance,
                            'duration': shortest_path.get('duration'),
                            'steps': shortest_path.get('steps', []),
                            'alternative_count': len(paths)
                        }
                        
            return {'valid': True}  # 没有参考点时默认有效
        except:
            return {'valid': True}  # 出错时默认有效 
        
    def _convert_coordinates(self, locations: str, coordsys: str = 'gps') -> str:
        """转换坐标系到高德坐标系"""
        try:
            params = {
                "locations": locations,
                "coordsys": coordsys,
                "key": self.key,
                "output": "json"
            }
            
            result = self._make_request("/v3/assistant/coordinate/convert", params)
            
            if result.get('status') == '1':
                return result.get('locations', '')
            
        except Exception as e:
            print(f"坐标转换错误: {str(e)}")
        return locations  # 转换失败时返回原坐标 
        
    def _get_weather_info(self, adcode: str) -> Dict:
        """获取地区天气信息"""
        try:
            params = {
                "key": self.key,
                "city": adcode,
                "extensions": "all",
                "output": "json"
            }
            
            result = self._make_request("/v3/weather/weatherInfo", params)
            
            if result.get('status') == '1':
                weather_info = {
                    'current': None,
                    'forecast': []
                }
                
                # 获取实时天气
                if result.get('lives'):
                    live = result['lives'][0]
                    weather_info['current'] = {
                        'weather': {
                            'code': live.get('weather', ''),
                            'desc': self.WEATHER_DESC.get(live.get('weather', ''), '未知天气')
                        },
                        'temperature': f"{live.get('temperature', '')}℃",
                        'wind': {
                            'direction': self.WIND_DIRECTION.get(live.get('winddirection', ''), '未知风向'),
                            'power': self.WIND_POWER.get(live.get('windpower', ''), '未知风力')
                        },
                        'humidity': f"{live.get('humidity', '')}%",
                        'reporttime': live.get('reporttime', '')
                    }
                    
                # 获取天气预报
                if result.get('forecasts'):
                    for cast in result['forecasts'][0].get('casts', []):
                        forecast = {
                            'date': cast.get('date', ''),
                            'week': cast.get('week', ''),
                            'day': {
                                'weather': {
                                    'code': cast.get('dayweather', ''),
                                    'desc': self.WEATHER_DESC.get(cast.get('dayweather', ''), '未知天气')
                                },
                                'temperature': f"{cast.get('daytemp', '')}℃",
                                'wind': {
                                    'direction': self.WIND_DIRECTION.get(cast.get('daywind', ''), '未知风向'),
                                    'power': self.WIND_POWER.get(cast.get('daypower', ''), '未知风力')
                                }
                            },
                            'night': {
                                'weather': {
                                    'code': cast.get('nightweather', ''),
                                    'desc': self.WEATHER_DESC.get(cast.get('nightweather', ''), '未知天气')
                                },
                                'temperature': f"{cast.get('nighttemp', '')}℃",
                                'wind': {
                                    'direction': self.WIND_DIRECTION.get(cast.get('nightwind', ''), '未知风向'),
                                    'power': self.WIND_POWER.get(cast.get('nightpower', ''), '未知风力')
                                }
                            }
                        }
                        weather_info['forecast'].append(forecast)
                        
                return weather_info
                
        except Exception as e:
            print(f"天气查询错误: {str(e)}")
        return None 
        
    def _search_poi(self, keywords: str, city: str = '', types: str = '') -> Dict:
        """搜索POI信息"""
        try:
            params = {
                "key": self.key,
                "keywords": keywords,
                "city": city,
                "types": types,
                "extensions": "all",  # 获取完整信息
                "output": "json"
            }
            
            result = self._make_request("/v3/place/text", params)
            
            if result.get('status') == '1':
                return result.get('pois', [])
                
        except Exception as e:
            print(f"POI搜索错误: {str(e)}")
        return [] 
        
    def _find_best_poi_match(self, pois: List[Dict], address: str) -> Dict:
        """找到最匹配的POI"""
        if not pois:
            return None
        
        # 计算每个POI的匹配分数
        scored_pois = []
        for poi in pois:
            score = 0
            
            # 名称匹配
            if poi.get('name') in address:
                score += 5
                # 完全匹配给更高分
                if poi.get('name') == address:
                    score += 3
                    
            # 地址匹配
            if poi.get('address'):
                if poi['address'] in address:
                    score += 3
                elif address in poi['address']:
                    score += 2
                    
            # 区域匹配
            if poi.get('adname') in address:
                score += 2
                
            # 商圈匹配
            if poi.get('business', {}).get('business_area'):
                if poi['business']['business_area'] in address:
                    score += 1
                    
            # 类型匹配
            if poi.get('type') and any(t in address for t in poi['type'].split(';')):
                score += 1
                
            # 别名匹配
            if poi.get('alias') and poi['alias'] in address:
                score += 1
                
            # 子POI匹配
            if poi.get('children'):
                for child in poi['children']:
                    if child.get('name') in address:
                        score += 2
                        
            scored_pois.append((score, poi))
            
        # 返回得分最高的POI
        if scored_pois:
            return max(scored_pois, key=lambda x: x[0])[1]
            
        return None 
        
    def _search_poi_v2(self, keywords: str, region: str = '', types: str = '') -> List[Dict]:
        """使用POI搜索2.0搜索地点信息"""
        try:
            # 检查缓存
            cache_key = f"poi_{keywords}_{region}_{types}"
            if hasattr(self, '_poi_cache') and cache_key in self._poi_cache:
                return self._poi_cache[cache_key]
            
            params = {
                "key": self.key,
                "keywords": keywords,
                "region": region,
                "types": types,
                "show_fields": "business,children,indoor,navi",
                "page_size": "25",
                "city_limit": "true" if region else "false"
            }
            
            result = self._make_request("/v5/place/text", params)
            
            if result.get('status') == '1':
                pois = result.get('pois', [])
                # 缓存结果
                if not hasattr(self, '_poi_cache'):
                    self._poi_cache = {}
                self._poi_cache[cache_key] = pois
                return pois
                
        except Exception as e:
            print(f"POI搜索错误: {str(e)}")
        return [] 
        
    def _check_quota(self, path: str) -> bool:
        """检查API配额"""
        # 初始化配额计数器
        if not hasattr(self, '_quota_counter'):
            self._quota_counter = {}
            
        # 获取当前日期
        today = datetime.now().strftime('%Y-%m-%d')
        if not hasattr(self, '_quota_date') or self._quota_date != today:
            self._quota_date = today
            self._quota_counter = {}
            
        # 检查配额
        if path.startswith('/v3/place'):
            # 搜索服务每天100次
            quota = 100
        else:
            # 其他基础服务每天5000次
            quota = 5000
            
        # 更新计数
        self._quota_counter[path] = self._quota_counter.get(path, 0) + 1
        
        return self._quota_counter[path] <= quota 
        
    def _get_district_by_name(self, name: str) -> Dict:
        """根据地名获取行政区划信息"""
        try:
            # 检查缓存
            if not hasattr(self, '_district_cache'):
                self._district_cache = {}
            
            # 如果已经缓存过，直接返回缓存结果
            if name in self._district_cache:
                return self._district_cache[name]
            
            params = {
                "keywords": name,
                "subdistrict": "0",
                "key": self.key
            }
            
            result = self._make_request("/v3/config/district", params)
            
            if result.get('status') == '1' and result.get('districts'):
                district = result['districts'][0]
                district_info = {
                    'province': district.get('province', ''),
                    'city': district.get('cityname', ''),
                    'district': district.get('name', ''),
                    'adcode': district.get('adcode', '')
                }
                # 缓存结果
                self._district_cache[name] = district_info
                return district_info
            
        except Exception as e:
            print(f"获取行政区划信息错误: {str(e)}")
        return {} 
        
    def _parse_address_by_text(self, address: str) -> Dict[str, str]:
        """通过文本解析地址"""
        try:
            # 清理地址字符串
            clean_address = self._clean_address_string(address)
            
            # 先尝试行政区划查询
            district_info = self._get_district_by_name(clean_address)
            if district_info and district_info.get('province'):
                components = {
                    'province': district_info.get('province', ''),
                    'city': district_info.get('city', '') or district_info.get('province', ''),
                    'district': district_info.get('district', ''),  # 确保返回空字符串而不是空列表
                    'street': '',
                    'building': '',
                    'unit': '',
                    'room': '',
                    'name': '',
                    'phone': '',
                    'weather': None
                }
                
                # 如果输入的地址不是行政区划名称，则作为建筑物名称
                if clean_address not in [
                    district_info.get('province', ''),
                    district_info.get('city', ''),
                    district_info.get('district', '')
                ]:
                    components['building'] = clean_address
                
                # 获取天气信息
                if district_info.get('adcode'):
                    components['weather'] = self._get_weather_info(district_info['adcode'])
                    
                return components
                
            # 如果行政区划查询失败，再使用地理编码
            geo_result = self._geo_code(clean_address)
            if geo_result.get('status') == '1' and geo_result.get('geocodes'):
                geocode = geo_result['geocodes'][0]
                
                # 提取基本组件
                components = {
                    'province': geocode.get('province', ''),
                    'city': geocode.get('city', '') or geocode.get('province', ''),
                    'district': geocode.get('district', ''),  # 确保这里也返回空字符串
                    'street': '',
                    'building': '',
                    'unit': '',
                    'room': '',
                    'name': '',
                    'phone': '',
                    'weather': None
                }
                
                # 提取街道信息
                formatted_address = geocode.get('formatted_address', '')
                if formatted_address:
                    street = self._extract_possible_street(
                        formatted_address,
                        [components['province'], components['city'], components['district']]
                    )
                    if street:
                        components['street'] = street
                        
                # 提取详细地址信息
                building_info = self._extract_building_info(clean_address, components)
                components.update(building_info)
                
                # 提取联系人信息
                name, phone = self._extract_contact_info(clean_address)
                components['name'] = name
                components['phone'] = phone
                
                # 获取天气信息
                if geocode.get('adcode'):
                    components['weather'] = self._get_weather_info(geocode['adcode'])
                    
                return components
                
        except Exception as e:
            print(f"地址解析错误: {str(e)}")
        return self._empty_components() 
        
    def _get_current_city_info(self) -> Dict:
        """获取当前IP的详细位置信息"""
        try:
            params = {
                "key": self.key,
                "output": "json"
            }
            
            result = self._make_request("/v3/ip", params)
            
            if result.get('status') == '1':
                return {
                    'province': result.get('province', ''),
                    'city': result.get('city', ''),
                    'adcode': result.get('adcode', ''),
                    'rectangle': result.get('rectangle', '')  # 城市矩形区域范围
                }
            
        except Exception as e:
            print(f"IP定位错误: {str(e)}")
        return {} 
        
    def _validate_key(self, key: str) -> bool:
        """验证API密钥是否有效"""
        try:
            # 使用一个简单的IP定位请求来验证密钥
            params = {
                "key": key,
                "output": "json"
            }
            
            result = self._make_request("/v3/ip", params)
            return result.get('status') == '1'
            
        except Exception as e:
            print(f"API密钥验证错误: {str(e)}")
            return False 