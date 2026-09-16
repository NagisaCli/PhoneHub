import re
import time
import subprocess
import threading
from pathlib import Path

CURRENT_DIR = Path(__file__).parent.resolve()
import adb_helper

IGNORED_PKGS = {
    "android",
    "com.android.systemui",
    "com.miui.securitycenter",
    "com.miui.misound",
    "com.miui.voicetrigger",
    "com.xiaomi.aicr",
    "com.xiaomi.mi_connect_service",
    "com.miui.powerkeeper",
    "com.miui.freeform"
}

PKG_FRIENDLY_NAMES = {
    "com.tencent.mm": "微信",
    "com.tencent.mobileqq": "QQ",
    "com.tencent.androidqqmail": "QQ邮箱",
    "com.android.mms": "短信",
    "com.android.phone": "电话",
    "com.google.android.gm": "Gmail",
    "com.alibaba.android.rimet": "钉钉",
    "com.ss.android.lark": "飞书",
    "com.jingdong.app.mall": "京东",
    "com.taobao.taobao": "淘宝",
    "com.sankuai.meituan": "美团"
}

def pop_windows_toast(title, message):
    # Escape single quotes
    t_safe = title.replace("'", "''").replace("\"", "")
    m_safe = message.replace("'", "''").replace("\"", "")

    ps_cmd = f'''
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$textNodes = $template.GetElementsByTagName('text')
$textNodes.Item(0).AppendChild($template.CreateTextNode('{t_safe}')) > $null
$textNodes.Item(1).AppendChild($template.CreateTextNode('{m_safe}')) > $null
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}}\\WindowsPowerShell\\v1.0\\powershell.exe').Show($toast)
'''
    try:
        subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_cmd], capture_output=True, timeout=5)
    except Exception as e:
        print(f"Toast error: {e}")

class NotificationListener:
    def __init__(self):
        self.running = False
        self.seen_notifs = set()
        self.thread = None

    def parse_notifications(self):
        raw = adb_helper.run_adb(["shell", "dumpsys", "notification", "--noredact"], timeout=6)
        if not raw or "NotificationRecord" not in raw:
            return []

        records = raw.split("NotificationRecord(")
        notifs = []

        for rec in records[1:]:
            # Parse package
            pkg_m = re.search(r'pkg=([a-zA-Z0-9_\.]+)', rec)
            if not pkg_m:
                continue
            pkg = pkg_m.group(1)
            if pkg in IGNORED_PKGS:
                continue

            # Parse title
            title_m = re.search(r'android\.title=String \((.*?)\)', rec)
            title = title_m.group(1).strip() if title_m else ""

            # Parse text
            text_m = re.search(r'android\.text=String \((.*?)\)', rec)
            text = text_m.group(1).strip() if text_m else ""

            # Parse key or id
            key_m = re.search(r'key=(.*?)(?:\s|$)', rec)
            notif_key = key_m.group(1) if key_m else f"{pkg}_{title}_{text}"

            if title or text:
                app_name = PKG_FRIENDLY_NAMES.get(pkg, pkg)
                notifs.append({
                    "key": notif_key,
                    "pkg": pkg,
                    "app_name": app_name,
                    "title": title or app_name,
                    "text": text
                })

        return notifs

    def start(self):
        if self.running:
            return
        self.running = True

        # Initialize seen with current active notifications so we don't burst past notifications
        init_notifs = self.parse_notifications()
        for n in init_notifs:
            self.seen_notifs.add(n["key"])

        def loop():
            print("PhoneHub 手机通知同步与验证码自动提取监听器已启动...")
            last_call_state = "0"
            while self.running:
                try:
                    # 1. Parse notifications
                    current_notifs = self.parse_notifications()
                    current_keys = set()
                    for n in current_notifs:
                        current_keys.add(n["key"])
                        if n["key"] not in self.seen_notifs:
                            self.seen_notifs.add(n["key"])
                            app_display = f"[{n['app_name']}] {n['title']}"
                            body_display = n['text'] or "收到新消息"

                            # Check for verification code
                            full_msg = f"{n['title']} {n['text']}"
                            code = adb_helper.extract_code_from_text(full_msg)
                            if code:
                                # Automatically copy to Windows Clipboard!
                                try:
                                    subprocess.run(["powershell.exe", "-NoProfile", "-Command", f"Set-Clipboard -Value '{code}'"], capture_output=True, timeout=3)
                                except Exception:
                                    pass
                                pop_windows_toast(f"🔑 验证码已自动复制: [{code}]", f"来源: {app_display}\n内容: {body_display}\n(直接在电脑上按 Ctrl+V 粘贴)")
                            else:
                                pop_windows_toast(app_display, body_display)

                    # Purge old seen keys
                    self.seen_notifs = self.seen_notifs.intersection(current_keys)

                    # 2. Check incoming calls
                    call_raw = adb_helper.run_adb(["shell", "dumpsys telephony.registry | grep -E 'mCallState|mCallIncomingNumber'"], timeout=4)
                    if "mCallState=1" in call_raw:
                        if last_call_state != "1":
                            num_m = re.search(r'mCallIncomingNumber=(\S+)', call_raw)
                            caller = num_m.group(1).strip() if (num_m and num_m.group(1).strip()) else "来电提醒"
                            pop_windows_toast("📞 手机来电呼入", f"来电号码: {caller}，手机正在响铃...")
                        last_call_state = "1"
                    else:
                        last_call_state = "0"

                except Exception as e:
                    pass
                time.sleep(1.8)

        self.thread = threading.Thread(target=loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

listener = NotificationListener()

if __name__ == "__main__":
    listener.start()
    pop_windows_toast("PhoneHub 手机通知同步", "服务已启动，验证码已开启自动提取并复制到电脑剪贴板！")
    time.sleep(10)
