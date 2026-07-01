import os
import subprocess
import psutil
import requests
from edith.config import APP_MAP

import shlex

def open_app(name):
    key = name.lower().strip()
    cmd = APP_MAP.get(key, key)
    try:
        if os.name == 'nt':
            try:
                os.startfile(cmd)
            except Exception:
                # Fallback to subprocess.Popen without shell=True
                args = shlex.split(cmd) if " " in cmd else [cmd]
                subprocess.Popen(args)
        else:
            subprocess.Popen(shlex.split(cmd))
        return "Opened " + name
    except Exception as e:
        return "Could not open " + name + ": " + str(e)

def close_tab():
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "w")
        return "Closed the tab"
    except Exception:
        return "Could not close tab"

def check_internet():
    import socket
    try:
        # Connect to a fast, reliable DNS server
        socket.create_connection(("1.1.1.1", 53), timeout=1.0)
        return True
    except OSError:
        return False

def get_system_info():
    try:
        from edith.core.state import state
        # Ping the network quickly (this runs in the background thread)
        is_online = check_internet()
        state.is_online = is_online
        
        cpu  = psutil.cpu_percent(interval=0.5)
        ram  = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return {
            "cpu": cpu,
            "ram_used": round(ram.used / 1e9, 1),
            "ram_total": round(ram.total / 1e9, 1),
            "ram_pct": ram.percent,
            "disk_used": round(disk.used / 1e9, 1),
            "disk_total": round(disk.total / 1e9, 1),
            "disk_pct": disk.percent,
            "is_online": state.is_online,
            "active_model": state.active_model,
        }
    except Exception:
        return {}

def get_weather(city=""):
    try:
        if city:
            geo = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1},
                timeout=5
            ).json()
            results = geo.get("results", [])
            if not results:
                return None
            lat = results[0]["latitude"]
            lon = results[0]["longitude"]
            loc_name = results[0].get("name", city)
        else:
            lat, lon, loc_name = 51.5074, -0.1278, "London"

        wx = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": True,
                "hourly": "precipitation_probability",
                "forecast_days": 1,
            },
            timeout=5,
        ).json()

        cw   = wx.get("current_weather", {})
        weather_data = {
            "city": loc_name,
            "temp": cw.get("temperature", "?"),
            "wind": cw.get("windspeed", "?"),
            "code": cw.get("weathercode", 0),
        }
        return weather_data
    except Exception:
        return None
