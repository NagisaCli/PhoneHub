import os
import re
import sys
import time
import json
import base64
import tempfile
import subprocess
import mimetypes
from pathlib import Path

def find_adb():
    # 1. Check PATH
    try:
        res = subprocess.run(["where.exe", "adb"], capture_output=True, text=True)
        if res.returncode == 0:
            lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
            if lines:
                return lines[0]
    except Exception:
        pass

    # 2. Check WinGet Google PlatformTools
    localapp = os.environ.get("LOCALAPPDATA", "")
    p1 = Path(localapp) / "Microsoft/WinGet/Packages/Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe/platform-tools/adb.exe"
    if p1.exists():
        return str(p1)

    # 3. Check Scrcpy directory
    p2 = Path(localapp) / "Microsoft/WinGet/Packages/Genymobile.scrcpy_Microsoft.Winget.Source_8wekyb3d8bbwe/scrcpy-win64-v4.1/adb.exe"
    if p2.exists():
        return str(p2)

    return "adb.exe"

def find_scrcpy_dir():
    localapp = os.environ.get("LOCALAPPDATA", "")
    p = Path(localapp) / "Microsoft/WinGet/Packages/Genymobile.scrcpy_Microsoft.Winget.Source_8wekyb3d8bbwe/scrcpy-win64-v4.1"
    if p.exists():
        return str(p)
    return ""

ADB_BIN = find_adb()
SCRCPY_DIR = find_scrcpy_dir()

def run_adb(args, timeout=12):
    cmd = [ADB_BIN] + args
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        out = (res.stdout or "") + ("\n" + res.stderr if res.stderr else "")
        return out.strip()
    except Exception as e:
        return f"ERROR: {e}"

def is_scrcpy_running():
    try:
        out = subprocess.run(["tasklist.exe", "/FI", "IMAGENAME eq scrcpy.exe", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        return "scrcpy.exe" in out.lower()
    except Exception:
        return False

def get_device_status():
    devices_raw = run_adb(["devices", "-l"])
    lines = [l for l in devices_raw.splitlines() if l.strip() and not l.startswith("*") and not l.startswith("List of")]
    if not lines or "device" not in lines[0]:
        return {
            "connected": False,
            "raw": devices_raw,
            "message": "未检测到已连接并授权的安卓设备，请检查 USB 连接或网络调试"
        }

    # Model & Serial
    serial = lines[0].split()[0]
    model_match = re.search(r'model:(\S+)', lines[0])
    model = model_match.group(1) if model_match else "Android Device"

    # Android release
    release = run_adb(["shell", "getprop", "ro.build.version.release"])

    # Battery
    batt_raw = run_adb(["shell", "dumpsys", "battery"])
    level = -1
    temp_c = 0.0
    status_str = "未知"
    ac_powered = False
    usb_powered = False
    for b_line in batt_raw.splitlines():
        b_line = b_line.strip()
        if b_line.startswith("level:"):
            try:
                level = int(b_line.split(":")[1].strip())
            except ValueError:
                pass
        elif b_line.startswith("temperature:"):
            try:
                temp_c = int(b_line.split(":")[1].strip()) / 10.0
            except ValueError:
                pass
        elif b_line.startswith("status:"):
            s_code = b_line.split(":")[1].strip()
            if s_code == "2":
                status_str = "充电中"
            elif s_code == "3":
                status_str = "放电使用中"
            elif s_code == "5":
                status_str = "已充满"
            else:
                status_str = "未充电"
        elif b_line.startswith("AC powered:"):
            ac_powered = "true" in b_line.lower()
        elif b_line.startswith("USB powered:"):
            usb_powered = "true" in b_line.lower()

    # Storage (/sdcard)
    df_raw = run_adb(["shell", "df", "-h", "/sdcard"])
    storage_info = {"total": "--", "used": "--", "free": "--", "percent": "--"}
    for d_line in df_raw.splitlines():
        if "/storage/emulated" in d_line or "/sdcard" in d_line or "emulated" in d_line:
            parts = d_line.split()
            if len(parts) >= 5:
                storage_info = {
                    "total": parts[1],
                    "used": parts[2],
                    "free": parts[3],
                    "percent": parts[4]
                }
                break

    # IP Address
    ip_raw = run_adb(["shell", "ip", "route"])
    wlan_ip = "未连接 Wi-Fi"
    for r_line in ip_raw.splitlines():
        if "wlan0" in r_line and "src" in r_line:
            parts = r_line.split()
            if "src" in parts:
                wlan_ip = parts[parts.index("src") + 1]
                break

    # Screen state
    screen_interactive = False
    pwr = run_adb(["shell", "dumpsys", "power"])
    if "mHoldingDisplaySuspendBlocker=true" in pwr or "mIsPowered=true" in pwr or "isInteractive=true" in pwr:
        screen_interactive = True

    return {
        "connected": True,
        "serial": serial,
        "model": model,
        "android_version": release,
        "battery": {
            "level": level,
            "temp": temp_c,
            "status": status_str,
            "charging_type": "快速快充 (AC)" if ac_powered else ("USB 充电" if usb_powered else "电池供电")
        },
        "storage": storage_info,
        "wifi_ip": wlan_ip,
        "screen_on": screen_interactive,
        "scrcpy_running": is_scrcpy_running()
    }

def launch_scrcpy_screen_off():
    subprocess.run(["taskkill.exe", "/F", "/IM", "scrcpy.exe"], capture_output=True)

    if not SCRCPY_DIR:
        return {"success": False, "error": "scrcpy directory not found"}

    scrcpy_exe = os.path.join(SCRCPY_DIR, "scrcpy.exe")
    cmd = f'"{scrcpy_exe}" --turn-screen-off --stay-awake --no-audio'

    ps_script = f'''
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class DstLauncher {{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct STARTUPINFO {{
        public Int32 cb; public string lpReserved; public string lpDesktop; public string lpTitle;
        public Int32 dwX; public Int32 dwY; public Int32 dwXSize; public Int32 dwYSize;
        public Int32 dwXCountChars; public Int32 dwYCountChars; public Int32 dwFillAttribute;
        public Int32 dwFlags; public Int16 wShowWindow; public Int16 cbReserved2;
        public IntPtr lpReserved2; public IntPtr hStdInput; public IntPtr hStdOutput; public IntPtr hStdError;
    }}
    [StructLayout(LayoutKind.Sequential)]
    public struct PROCESS_INFORMATION {{
        public IntPtr hProcess; public IntPtr hThread; public Int32 dwProcessId; public Int32 dwThreadId;
    }}
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern bool CreateProcess(
        string lpApplicationName, string lpCommandLine, IntPtr lpProcessAttributes, IntPtr lpThreadAttributes,
        bool bInheritHandles, uint dwCreationFlags, IntPtr lpEnvironment, string lpCurrentDirectory,
        ref STARTUPINFO lpStartupInfo, out PROCESS_INFORMATION lpProcessInformation);
    public static int Launch(string appPath, string cmdLine, string workDir) {{
        STARTUPINFO si = new STARTUPINFO();
        si.cb = Marshal.SizeOf(si);
        si.lpDesktop = "WinSta0\\\\Default";
        PROCESS_INFORMATION pi = new PROCESS_INFORMATION();
        bool success = CreateProcess(appPath, cmdLine, IntPtr.Zero, IntPtr.Zero, false, 0, IntPtr.Zero, workDir, ref si, out pi);
        if (!success) return -Marshal.GetLastWin32Error();
        return pi.dwProcessId;
    }}
}}
"@
[DstLauncher]::Launch("{scrcpy_exe.replace('\\', '\\\\')}", '{cmd.replace('\\', '\\\\')}', "{SCRCPY_DIR.replace('\\', '\\\\')}")
'''
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
    return {"success": True, "output": res.stdout.strip()}

def launch_scrcpy(mode="normal"):
    subprocess.run(["taskkill.exe", "/F", "/IM", "scrcpy.exe"], capture_output=True)

    if not SCRCPY_DIR:
        return {"success": False, "error": "scrcpy directory not found"}

    # 1. First wake up device and dismiss keyguard to ensure display pipeline is active
    run_adb(["shell", "input keyevent 224; wm dismiss-keyguard"])

    scrcpy_exe = os.path.join(SCRCPY_DIR, "scrcpy.exe")

    if mode == "144hz":
        # Ultra-fluid 144Hz for Note 11T Pro 144Hz LCD
        cmd = f'"{scrcpy_exe}" --display-id=0 --stay-awake --no-audio --video-codec=h264 --max-fps=144 --max-size=1920 --video-buffer=0 --video-bit-rate=20M --keyboard=uhid --mouse=uhid'
        msg = "144Hz 极客满血高刷投屏已启动 (Note 11T Pro 满血高刷)"
    elif mode == "low_latency":
        # Ultra-low latency: H.265, 120FPS, 1600px, 0ms buffer, 16Mbps, UHID hardware keyboard
        cmd = f'"{scrcpy_exe}" --display-id=0 --stay-awake --no-audio --video-codec=h265 --max-fps=120 --max-size=1600 --video-buffer=0 --video-bit-rate=16M --keyboard=uhid'
        msg = "120FPS 竞技级超低延迟投屏已启动 (<15ms)"
    elif mode == "dim":
        # MediaTek workaround: dim phone brightness to minimum (near-black, zero heat) without breaking MTK encoder
        run_adb(["shell", "settings put system screen_brightness 1"])
        cmd = f'"{scrcpy_exe}" --display-id=0 --stay-awake --no-audio'
        msg = "天玑微光防发热投屏已启动（手机屏幕极暗防发热，电脑画面完全正常）"
    elif mode == "screen_off":
        # Native screen-off
        cmd = f'"{scrcpy_exe}" --display-id=0 --turn-screen-off --stay-awake --no-audio'
        msg = "熄屏投屏已启动（如遇联发科芯片黑屏，请改用微光防发热模式或按 Alt+P）"
    else: # normal
        cmd = f'"{scrcpy_exe}" --display-id=0 --stay-awake --no-audio'
        msg = "标准高清投屏已启动"

    ps_script = f'''
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class DstLauncher {{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct STARTUPINFO {{
        public Int32 cb; public string lpReserved; public string lpDesktop; public string lpTitle;
        public Int32 dwX; public Int32 dwY; public Int32 dwXSize; public Int32 dwYSize;
        public Int32 dwXCountChars; public Int32 dwYCountChars; public Int32 dwFillAttribute;
        public Int32 dwFlags; public Int16 wShowWindow; public Int16 cbReserved2;
        public IntPtr lpReserved2; public IntPtr hStdInput; public IntPtr hStdOutput; public IntPtr hStdError;
    }}
    [StructLayout(LayoutKind.Sequential)]
    public struct PROCESS_INFORMATION {{
        public IntPtr hProcess; public IntPtr hThread; public Int32 dwProcessId; public Int32 dwThreadId;
    }}
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern bool CreateProcess(
        string lpApplicationName, string lpCommandLine, IntPtr lpProcessAttributes, IntPtr lpThreadAttributes,
        bool bInheritHandles, uint dwCreationFlags, IntPtr lpEnvironment, string lpCurrentDirectory,
        ref STARTUPINFO lpStartupInfo, out PROCESS_INFORMATION lpProcessInformation);
    public static int Launch(string appPath, string cmdLine, string workDir) {{
        STARTUPINFO si = new STARTUPINFO();
        si.cb = Marshal.SizeOf(si);
        si.lpDesktop = "WinSta0\\\\Default";
        PROCESS_INFORMATION pi = new PROCESS_INFORMATION();
        bool success = CreateProcess(appPath, cmdLine, IntPtr.Zero, IntPtr.Zero, false, 0, IntPtr.Zero, workDir, ref si, out pi);
        if (!success) return -Marshal.GetLastWin32Error();
        return pi.dwProcessId;
    }}
}}
"@
[DstLauncher]::Launch("{scrcpy_exe.replace('\\', '\\\\')}", '{cmd.replace('\\', '\\\\')}', "{SCRCPY_DIR.replace('\\', '\\\\')}")
'''
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
    return {"success": True, "output": res.stdout.strip(), "mode": msg}

def launch_scrcpy_screen_off():
    return launch_scrcpy("screen_off")

def launch_scrcpy_low_latency():
    return launch_scrcpy("low_latency")

def launch_scrcpy_dim():
    return launch_scrcpy("dim")

def get_deep_diagnostics():
    # 1. Memory diagnostics
    mem_raw = run_adb(["shell", "dumpsys", "meminfo"], timeout=8)
    ram_info = {
        "total_ram": "--", "free_ram": "--", "used_ram": "--", "zram_swap": "--",
        "top_apps": []
    }
    for line in mem_raw.splitlines():
        line_s = line.strip()
        if line_s.startswith("Total RAM:"):
            ram_info["total_ram"] = line_s.split(":")[1].split("(")[0].strip()
        elif line_s.startswith("Free RAM:"):
            ram_info["free_ram"] = line_s.split(":")[1].split("(")[0].strip()
        elif line_s.startswith("Used RAM:"):
            ram_info["used_ram"] = line_s.split(":")[1].split("(")[0].strip()
        elif line_s.startswith("ZRAM:"):
            ram_info["zram_swap"] = line_s.split(":")[1].strip()
        elif "K:" in line_s and "(pid" in line_s and len(ram_info["top_apps"]) < 8:
            parts = line_s.split("K:")
            if len(parts) == 2:
                mem_kb = parts[0].strip()
                pkg_pid = parts[1].strip()
                ram_info["top_apps"].append({"memory": f"{mem_kb} KB", "process": pkg_pid})

    # 2. Battery telemetry
    batt_raw = run_adb(["shell", "dumpsys", "battery"])
    battery_diag = {
        "voltage_mv": "--", "health": "良好", "technology": "Li-poly",
        "charge_counter": "--", "max_charging_watt": "--"
    }
    for b in batt_raw.splitlines():
        b = b.strip()
        if b.startswith("voltage:"):
            try:
                v = int(b.split(":")[1].strip())
                battery_diag["voltage_mv"] = f"{v} mV ({v/1000.0:.2f}V)"
            except Exception:
                pass
        elif b.startswith("health:"):
            h_code = b.split(":")[1].strip()
            battery_diag["health"] = "极佳/良好 (Good)" if h_code == "2" else "过热/需注意"
        elif b.startswith("technology:"):
            battery_diag["technology"] = b.split(":")[1].strip()
        elif b.startswith("Charge counter:"):
            battery_diag["charge_counter"] = b.split(":")[1].strip() + " uAh"
        elif b.startswith("Max charging current:"):
            try:
                curr_a = int(b.split(":")[1].strip()) / 1000000.0
                battery_diag["max_current"] = f"{curr_a:.1f} A"
            except Exception:
                pass

    # 3. Screen display diagnostics
    size_raw = run_adb(["shell", "wm", "size"])
    density_raw = run_adb(["shell", "wm", "density"])
    screen_diag = {
        "resolution": size_raw.replace("Physical size:", "").strip(),
        "density": density_raw.replace("Physical density:", "").strip(),
        "fps_mode": "144Hz 高刷面板"
    }

    # 4. Thermal sensors
    thermal_raw = run_adb(["shell", "cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | head -n 6"])
    temps = []
    for t in thermal_raw.splitlines():
        try:
            val = float(t.strip())
            if val > 1000:
                val = val / 1000.0
            if 20.0 <= val <= 95.0:
                temps.append(round(val, 1))
        except Exception:
            pass

    return {
        "ram": ram_info,
        "battery": battery_diag,
        "screen": screen_diag,
        "thermals": temps
    }

def clean_system(clean_type):
    if clean_type == "trim_caches":
        # Android native global cache trim (safe, purge caches without losing app data)
        out = run_adb(["shell", "pm", "trim-caches", "1000G"])
        return {"success": True, "output": "系统底层缓存裁剪清理完成，已安全回收空间", "raw": out}

    elif clean_type == "kill_background":
        out = run_adb(["shell", "am", "kill-all"])
        return {"success": True, "output": "已清除所有可杀死的后台空闲应用进程", "raw": out}

    elif clean_type == "clean_temp_files":
        cmd = "rm -rf /sdcard/.thumbnails/* /sdcard/*.tmp /sdcard/*.log 2>/dev/null"
        out = run_adb(["shell", cmd])
        return {"success": True, "output": "已安全清空相册缓存缩略图与临时残存 log/tmp 文件"}

    elif clean_type == "debloat_miui_ads":
        # Safe debloat presets for Xiaomi/Redmi
        packages = [
            "com.miui.systemAdSolution", # msa 系统广告服务
            "com.miui.analytics",        # 小米分析与埋点
            "com.miui.hybrid",           # 快应用
            "com.miui.bugreport"         # 崩溃抓取上报
        ]
        results = []
        for p in packages:
            res = run_adb(["shell", "pm", "disable-user", p])
            results.append(f"{p}: {res}")
        return {"success": True, "output": "已停用小米广告全家桶(msa/analytics/hybrid/bugreport)", "details": results}

    elif clean_type == "restore_miui_ads":
        packages = [
            "com.miui.systemAdSolution",
            "com.miui.analytics",
            "com.miui.hybrid",
            "com.miui.bugreport"
        ]
        results = []
        for p in packages:
            res = run_adb(["shell", "pm", "enable", p])
            results.append(f"{p}: {res}")
        return {"success": True, "output": "已恢复小米默认服务", "details": results}

    return {"success": False, "error": f"Unknown clean type: {clean_type}"}

def execute_action(action_name):
    actions = {
        "home": ["shell", "input", "keyevent", "3"],
        "back": ["shell", "input", "keyevent", "4"],
        "recents": ["shell", "input", "keyevent", "187"],
        "screen_on": ["shell", "input", "keyevent", "224"],
        "screen_off": ["shell", "input", "keyevent", "223"],
        "expand_notif": ["shell", "cmd", "statusbar", "expand-notifications"],
        "collapse_notif": ["shell", "cmd", "statusbar", "collapse"],
        "vol_up": ["shell", "input", "keyevent", "24"],
        "vol_down": ["shell", "input", "keyevent", "25"],
        "vol_mute": ["shell", "input", "keyevent", "164"],
        "media_play_pause": ["shell", "input", "keyevent", "85"],
        "media_next": ["shell", "input", "keyevent", "87"],
        "media_prev": ["shell", "input", "keyevent", "88"],
        "call_end": ["shell", "input", "keyevent", "6"],
        "call_accept": ["shell", "input", "keyevent", "5"],
        "reboot": ["reboot"],
        "reboot_recovery": ["reboot", "recovery"],
        "reboot_bootloader": ["reboot", "bootloader"],
        "enable_tcpip": ["tcpip", "5555"],
        "start_shizuku": ["shell", "sh", "/storage/emulated/0/Android/data/moe.shizuku.privileged.api/start.sh"]
    }
    if action_name == "scrcpy_screen_off":
        return launch_scrcpy_screen_off()
    elif action_name == "scrcpy_144hz":
        return launch_scrcpy("144hz")
    elif action_name == "scrcpy_low_latency":
        return launch_scrcpy_low_latency()
    elif action_name == "scrcpy_dim":
        return launch_scrcpy_dim()
    elif action_name == "scrcpy_normal":
        return launch_scrcpy("normal")
    elif action_name == "scrcpy_stop":
        return stop_scrcpy()
    elif action_name.startswith("clean_"):
        clean_key = action_name[len("clean_"):]
        return clean_system(clean_key)
    elif action_name == "debloat_ads":
        return clean_system("debloat_miui_ads")
    elif action_name == "restore_ads":
        return clean_system("restore_miui_ads")
    elif action_name in actions:
        out = run_adb(actions[action_name])
        return {"success": True, "output": out}
    return {"success": False, "error": f"Unknown action: {action_name}"}

def send_text_input(text):
    safe_ascii = text.encode('ascii', 'ignore').decode('ascii')
    if safe_ascii and len(safe_ascii) == len(text):
        escaped = text.replace(" ", "%s").replace("&", r"\&").replace("<", r"\<").replace(">", r"\>").replace('"', r'\"').replace("'", r"\'")
        out = run_adb(["shell", "input", "text", escaped])
        return {"success": True, "method": "input_text", "output": out}
    else:
        b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        run_adb(["shell", f"cmd clipboard set text '{text}' 2>/dev/null || echo -n '{b64}' | base64 -d > /data/local/tmp/_clip.txt 2>/dev/null"])
        run_adb(["shell", "input", "keyevent", "279"])
        return {"success": True, "method": "clipboard_paste", "text": text}

def list_installed_apps(category="3"):
    flag = "-3" if category == "3" else "-s"
    raw = run_adb(["shell", "pm", "list", "packages", flag, "-f"])
    apps = []
    for line in raw.splitlines():
        if line.startswith("package:"):
            line = line[len("package:"):]
            if "=" in line:
                apk_path, pkg = line.rsplit("=", 1)
                apps.append({
                    "package": pkg.strip(),
                    "apk_path": apk_path.strip(),
                    "is_system": category == "s"
                })
    apps.sort(key=lambda x: x["package"])
    return apps

def app_action(pkg, action):
    if action == "uninstall":
        out = run_adb(["shell", "pm", "uninstall", "-k", "--user", "0", pkg])
        return {"success": "Success" in out, "output": out}
    elif action == "disable":
        out = run_adb(["shell", "pm", "disable-user", pkg])
        return {"success": "new state" in out or "disabled" in out, "output": out}
    elif action == "enable":
        out = run_adb(["shell", "pm", "enable", pkg])
        return {"success": "new state" in out or "enabled" in out, "output": out}
    elif action == "launch":
        out = run_adb(["shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"])
        return {"success": "Events injected" in out, "output": out}
    elif action == "extract_apk":
        path_raw = run_adb(["shell", "pm", "path", pkg])
        for p in path_raw.splitlines():
            if p.startswith("package:"):
                remote_apk = p.replace("package:", "").strip()
                desktop = str(Path.home() / "Desktop")
                local_apk = os.path.join(desktop, f"{pkg}.apk")
                pull_out = run_adb(["pull", remote_apk, local_apk])
                return {"success": os.path.exists(local_apk), "output": pull_out, "local_file": local_apk}
        return {"success": False, "error": "APK path not found"}
    return {"success": False, "error": f"Unknown app action: {action}"}

def push_file_to_device(temp_file_path, original_filename):
    remote_path = f"/sdcard/Download/{original_filename}"
    out = run_adb(["push", temp_file_path, remote_path])
    run_adb(["shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE", "-d", f"file://{remote_path}"])
    return {"success": "1 file pushed" in out or "pushed" in out, "remote_path": remote_path, "output": out}

def take_screenshot_base64():
    try:
        cmd = [ADB_BIN, "exec-out", "screencap", "-p"]
        p = subprocess.run(cmd, capture_output=True, timeout=8)
        if p.returncode == 0 and len(p.stdout) > 1000:
            return base64.b64encode(p.stdout).decode("ascii")
    except Exception as e:
        pass
    return None

def pull_latest_photo_to_desktop():
    find_cmd = "ls -t /sdcard/DCIM/Camera/* /sdcard/Pictures/Screenshots/* 2>/dev/null | head -n 1"
    latest_file = run_adb(["shell", find_cmd]).strip()
    if not latest_file or "No such file" in latest_file:
        return {"success": False, "error": "未找到相片或截图"}

    filename = os.path.basename(latest_file)
    desktop = str(Path.home() / "Desktop")
    local_path = os.path.join(desktop, filename)
    out = run_adb(["pull", latest_file, local_path])
    return {"success": os.path.exists(local_path), "local_path": local_path, "output": out}

def extract_code_from_text(text):
    patterns = [
        r'(?i)(?:验证码|校验码|动态码|code|otp|pin)[^0-9]{0,10}([0-9]{4,8})',
        r'([0-9]{4,8})[^0-9]{0,10}(?:验证码|code)'
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
    return ""

def get_sms_messages(limit=25):
    raw = run_adb(['shell', 'content', 'query', '--uri', 'content://sms', '--projection', 'address,body,date,type'])
    messages = []
    for line in raw.splitlines():
        if line.startswith("Row:"):
            m = re.search(r'address=(.*?), body=(.*?), date=(\d+), type=(\d+)', line)
            if m:
                addr, body, dt_str, tp = m.group(1), m.group(2), m.group(3), m.group(4)
                try:
                    ts = int(dt_str) / 1000.0
                    date_fmt = time.strftime('%m-%d %H:%M', time.localtime(ts))
                except Exception:
                    date_fmt = "--"
                code = extract_code_from_text(body)
                messages.append({
                    "address": addr,
                    "body": body,
                    "date": date_fmt,
                    "type": "recv" if tp == "1" else "sent",
                    "code": code
                })
    return messages[:limit]

def send_sms(number, body):
    escaped = body.replace("'", "\\'")
    out = run_adb(["shell", f"am start -a android.intent.action.SENDTO -d sms:{number} --es sms_body '{escaped}'"])
    return {"success": "Starting: Intent" in out, "output": out}

def launch_quick_app(app_key):
    apps = {
        "wechat": "com.tencent.mm",
        "qq": "com.tencent.mobileqq",
        "mms": "com.android.mms",
        "gallery": "com.miui.gallery",
        "camera": "com.android.camera",
        "settings": "com.android.settings",
        "browser": "com.android.browser",
        "dialer": "com.android.contacts"
    }
    pkg = apps.get(app_key, app_key)
    return app_action(pkg, "launch")

def dial_phone_number(number):
    clean_num = re.sub(r'[^0-9+*#]', '', number)
    if not clean_num:
        return {"success": False, "error": "无效的电话号码"}
    out = run_adb(["shell", f"am start -a android.intent.action.DIAL -d tel:{clean_num}"])
    return {"success": "Starting: Intent" in out, "output": out}

def format_file_size(b):
    try:
        b = int(b)
    except Exception:
        return '0 B'
    if b < 1024:
        return f'{b} B'
    elif b < 1024 * 1024:
        return f'{b / 1024:.1f} KB'
    elif b < 1024 * 1024 * 1024:
        return f'{b / (1024 * 1024):.1f} MB'
    else:
        return f'{b / (1024 * 1024 * 1024):.2f} GB'

def list_directory_full(remote_path='/sdcard', show_hidden=False):
    remote_path = remote_path.rstrip('/') if remote_path != '/' else '/'
    if not remote_path:
        remote_path = '/sdcard'
    parent_path = None
    if remote_path not in ['/sdcard', '/storage/emulated/0', '/']:
        parent_path = os.path.dirname(remote_path)
    out = run_adb(['shell', f'ls -la "{remote_path}/" 2>/dev/null'])
    items = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith('total') or 'No such file' in line:
            continue
        parts = line.split(None, 7)
        if len(parts) >= 8:
            perm, _, _, _, size_str, dt, tm, fname = parts
            if fname in ['.', '..']:
                continue
            if not show_hidden and fname.startswith('.'):
                continue
            is_dir = perm.startswith('d') or perm.startswith('l')
            try:
                sb = int(size_str)
            except ValueError:
                sb = 0
            ext = os.path.splitext(fname)[1].lower().lstrip('.') if not is_dir else ''
            items.append({
                'name': fname,
                'is_dir': is_dir,
                'size': '-' if is_dir else format_file_size(sb),
                'size_bytes': sb,
                'date': f'{dt} {tm}',
                'ext': ext,
                'path': f"{remote_path.rstrip('/')}/{fname}"
            })
    dirs = sorted([x for x in items if x['is_dir']], key=lambda x: x['name'].lower())
    files = sorted([x for x in items if not x['is_dir']], key=lambda x: x['date'], reverse=True)
    return {'success': True, 'current_path': remote_path, 'parent_path': parent_path, 'items': dirs + files}

def pull_file_or_dir(remote_path, target_local=None):
    if not remote_path or '..' in remote_path:
        return {'success': False, 'error': '非法路径'}
    fname = os.path.basename(remote_path.rstrip('/'))
    if not target_local:
        desktop = str(Path.home() / 'Desktop')
        target_local = os.path.join(desktop, fname)
    out = run_adb(['pull', remote_path, target_local])
    return {'success': os.path.exists(target_local), 'local_path': target_local, 'output': out}

def push_file_to_directory(temp_file_path, remote_dir, original_filename):
    remote_dir = remote_dir.rstrip('/') if remote_dir else '/sdcard/Download'
    remote_target = f"{remote_dir}/{original_filename}"
    res = subprocess.run([ADB_BIN, "push", temp_file_path, remote_target],
                         capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
    out = ((res.stdout or "") + "\n" + (res.stderr or "")).strip()
    ok = res.returncode == 0 or "pushed" in out or "1 file" in out
    if not ok:
        chk = run_adb(["shell", f'test -f "{remote_target}" && echo "EXISTS"'])
        if "EXISTS" in chk:
            ok = True
    if ok:
        run_adb(['shell', 'am', 'broadcast', '-a', 'android.intent.action.MEDIA_SCANNER_SCAN_FILE', '-d', f'file://{remote_target}'])
    return {'success': ok, 'remote_path': remote_target, 'filename': original_filename, 'output': out}

def get_content_uri(remote_path):
    """
    Scans remote file into Android MediaStore and retrieves its content:// URI.
    """
    if not remote_path:
        return None
    norm_path = remote_path.replace("/sdcard/", "/storage/emulated/0/")
    run_adb(['shell', 'am', 'broadcast', '-a', 'android.intent.action.MEDIA_SCANNER_SCAN_FILE', '-d', f'file://{remote_path}'])
    import time
    for _ in range(3):
        out = run_adb(['shell', f"content query --uri content://media/external/file --projection _id:_data --where \"_data='{norm_path}'\""])
        if "_id=" in out:
            for part in out.replace("\n", " ").split():
                if part.startswith("_id="):
                    mid = part.split("=")[1].strip(", ")
                    return f"content://media/external/file/{mid}"
        time.sleep(0.15)
    return None

def share_file_to_app(remote_path, target_app="chooser"):
    """
    Directly shares a remote file on phone to WeChat, QQ, or System Share Sheet.
    target_app: 'wechat' | 'qq' | 'wework' | 'chooser'
    """
    if not remote_path:
        return {"success": False, "error": "无效的文件路径"}

    # 1. Wake phone and dismiss keyguard
    run_adb(["shell", "input keyevent 224; wm dismiss-keyguard"])

    # 2. Detect mime type (NEVER use unquoted */* to prevent shell globbing)
    ext = os.path.splitext(remote_path)[1].lower().lstrip(".")
    mime = mimetypes.guess_type(remote_path)[0]
    if not mime:
        if ext in ["jpg", "jpeg", "png", "webp", "gif", "bmp"]:
            mime = "image/*"
        elif ext in ["mp4", "mkv", "avi", "mov", "flv", "wmv"]:
            mime = "video/*"
        elif ext in ["mp3", "flac", "aac", "wav", "m4a", "ogg"]:
            mime = "audio/*"
        elif ext in ["apk", "xapk"]:
            mime = "application/vnd.android.package-archive"
        elif ext == "pdf":
            mime = "application/pdf"
        elif ext in ["txt", "log", "md", "json", "py", "c", "cpp", "h", "java", "sh", "xml", "html", "css", "js"]:
            mime = "text/plain"
        elif ext in ["zip", "rar", "7z", "tar", "gz"]:
            mime = "application/zip"
        else:
            mime = "application/octet-stream"

    # 3. Resolve MediaStore content URI for Android 11+ / 14 Scoped Storage
    content_uri = get_content_uri(remote_path)
    stream_uri = content_uri if content_uri else f"file://{remote_path}"

    target_flags = []
    if target_app in ["wechat", "mm", "wx"]:
        target_flags = ["-n", "com.tencent.mm/.ui.tools.ShareImgUI"]
    elif target_app in ["qq"]:
        target_flags = ["-p", "com.tencent.mobileqq"]
    elif target_app in ["wework"]:
        target_flags = ["-p", "com.tencent.wework"]

    # 4. Construct intent with FLAG_ACTIVITY_NEW_TASK | FLAG_GRANT_READ_URI_PERMISSION (0x10000001)
    cmd = [
        "shell", "am", "start",
        "-a", "android.intent.action.SEND",
        "-t", mime,
        "--eu", "android.intent.extra.STREAM", stream_uri,
        "--grant-read-uri-permission",
        "-f", "0x10000001"
    ] + target_flags

    out = run_adb(cmd)

    app_names = {
        "wechat": "微信",
        "qq": "QQ",
        "wework": "企业微信",
        "chooser": "系统分享"
    }
    app_name = app_names.get(target_app, "系统分享")
    has_err = "Error:" in out or "Error type" in out or "Exception" in out
    ok = not has_err and ("Starting: Intent" in out or "Warning: Activity not started" in out or "delivered" in out)

    return {
        "success": ok,
        "app": app_name,
        "remote_path": remote_path,
        "content_uri": content_uri,
        "output": out,
        "error": out if not ok else ""
    }



def delete_remote_item(remote_path):
    safe_disallow = ['/', '/sdcard', '/sdcard/', '/storage', '/storage/emulated/0', '/storage/emulated/0/', '/system', '/data']
    cleaned = remote_path.rstrip('/')
    if not cleaned or cleaned in safe_disallow:
        return {'success': False, 'error': '受保护的关键系统或存储根目录禁止删除！'}
    out = run_adb(['shell', f'rm -rf "{cleaned}"'])
    return {'success': True, 'output': out}

def make_remote_directory(remote_dir, folder_name):
    clean_name = re.sub(r'[\\/:*?"<>|]', '_', folder_name).strip()
    if not clean_name:
        return {'success': False, 'error': '文件夹名称无效'}
    target = f"{remote_dir.rstrip('/')}/{clean_name}"
    out = run_adb(['shell', f'mkdir -p "{target}"'])
    return {'success': True, 'target': target, 'output': out}

def rename_remote_item(remote_path, new_name):
    clean_name = re.sub(r'[\\/:*?"<>|]', '_', new_name).strip()
    if not clean_name:
        return {'success': False, 'error': '新名称无效'}
    parent = os.path.dirname(remote_path.rstrip('/'))
    target = f"{parent}/{clean_name}"
    out = run_adb(['shell', f'mv "{remote_path}" "{target}"'])
    return {'success': True, 'target': target, 'output': out}

def get_image_preview_b64(remote_path):
    ext = os.path.splitext(remote_path)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.webp', '.heic']:
        return {'success': False, 'error': '不支持非图片文件预览'}
    try:
        from PIL import Image
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = tmp.name
        run_adb(['pull', remote_path, tmp_path])
        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            return {'success': False, 'error': '图片读取失败'}
        im = Image.open(tmp_path)
        im = im.convert('RGB')
        im.thumbnail((900, 1400))
        thumb_tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False).name
        im.save(thumb_tmp, 'JPEG', quality=82)
        with open(thumb_tmp, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('ascii')
        try:
            os.remove(tmp_path)
            os.remove(thumb_tmp)
        except Exception:
            pass
        return {'success': True, 'preview': f'data:image/jpeg;base64,{b64}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def batch_pull_files(remote_paths, target_dir=None):
    if not target_dir:
        target_dir = str(Path.home() / 'Desktop')
    results = []
    success_count = 0
    for p in remote_paths:
        if not p or '..' in p:
            continue
        fname = os.path.basename(p.rstrip('/'))
        local_dest = os.path.join(target_dir, fname)
        out = run_adb(['pull', p, local_dest])
        ok = os.path.exists(local_dest)
        if ok:
            success_count += 1
        results.append({'path': p, 'success': ok, 'local': local_dest})
    return {'success': True, 'count': success_count, 'total': len(remote_paths), 'target_dir': target_dir, 'details': results}

def batch_delete_items(remote_paths):
    safe_disallow = ['/', '/sdcard', '/sdcard/', '/storage', '/storage/emulated/0', '/storage/emulated/0/', '/system', '/data']
    deleted = []
    for p in remote_paths:
        cleaned = p.rstrip('/')
        if not cleaned or cleaned in safe_disallow:
            continue
        run_adb(['shell', f'rm -rf "{cleaned}"'])
        deleted.append(cleaned)
    return {'success': True, 'count': len(deleted), 'deleted': deleted}
