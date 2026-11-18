# -*- coding: utf-8 -*-
import os
import json
import uuid

# 服务端网关主机
HOST_RUN = "https://run.gxapp.iydsj.com"
HOST_DISCOVERY = "https://discovery.gxapp.iydsj.com"
HOST_DATAPOINT = "https://datapoint.gxapp.iydsj.com"
HOST_PARTNER = "https://partner.iydsj.com"

# 7.3.92 通用设备占位配置 (标准 ARM64 真机特征)
DEFAULT_DEVICE_CONFIG = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "appVersion": "7.3.92",
    "physicPixel": "1080x2400",
    "logicPixel": "393x873",
    "isRoot": "0",
    "osType": "0",
    "cpuModel": "arm64-v8a",
    "deviceName": "Android Device",
    "DeviceId": "00000000000000000000000000000000",
    "osVersion": "13",
    "User-Agent": "okhttp/4.12.0"
}

def load_customer_device(config_path: str = None) -> dict:
    dev = dict(DEFAULT_DEVICE_CONFIG)
    # [PATCH] DeviceId 必须固定：原来每次运行都生成新的 uuid，服务端会把它当成
    # "另一台设备登录"，触发互斥保护（错误码 10121 此账号已在其他设备登录）。
    # 改为首次生成后写入文件，之后复用，服务端视为同一台设备。
    _dev_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_device_id.txt")
    if os.path.exists(_dev_file):
        try:
            _cached = open(_dev_file, "r", encoding="utf-8").read().strip()
            if _cached:
                dev["DeviceId"] = _cached
            else:
                dev["DeviceId"] = uuid.uuid4().hex
        except Exception:
            dev["DeviceId"] = uuid.uuid4().hex
    else:
        dev["DeviceId"] = uuid.uuid4().hex
        try:
            with open(_dev_file, "w", encoding="utf-8") as _f:
                _f.write(dev["DeviceId"])
        except Exception:
            pass
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                phone = cfg.get("setting", {}).get("phone", {})
                if phone:
                    if "brand" in phone or "model" in phone:
                        dev["deviceName"] = f"{phone.get('brand', 'Android')} {phone.get('model', 'Device')}"
                    if "vdid" in phone:
                        dev["DeviceId"] = phone["vdid"].replace("-", "")
        except Exception:
            pass
    return dev
