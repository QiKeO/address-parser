'''
Author: 柒刻
Date: 2024-12-28 23:27:28
LastEditTime: 2025-01-02 21:14:14
FilePath: \地区识别\address_completer.py
'''
from typing import Dict
from amap_address_parser import AmapAddressParser

class AddressCompleter:
    def __init__(self):
        self.parser = AmapAddressParser()
        
    def complete_address(self, address_string: str) -> Dict[str, str]:
        """解析并补全地址"""
        return self.parser.parse_address(address_string) 