# PhoneHub - Ultra-Fast Mobile File Center & Cross-Device Control Hub

<p align="left">
  <a href="README.md">简体中文</a> | <b>English</b>
</p>

PhoneHub is a lightweight, ultra-fast, zero-overhead cross-device control hub bridging Android phones and Windows PCs.

Built entirely on the high-speed Android **ADB data pipeline**, PhoneHub requires **NO resident 3rd-party Android apps installed on the phone**. It completely bypasses router subnet isolation, NAT, TUN proxy traps, and local network broadcast issues—delivering instant responsiveness with zero background battery drain.

---

## ✨ Key Features

### 📂 1. Ultra-Fast Mobile File Management System
- **Dynamic Breadcrumb Navigation**: Seamless path travel (e.g. `Storage > Download > WeiXin`) with instant parent directory jumping.
- **One-Click Quick Bookmarks**:
  - 📥 Downloads (`/sdcard/Download`)
  - 📸 Camera Photos (`/sdcard/DCIM/Camera`)
  - 📱 Screenshots (`/sdcard/DCIM/Screenshots`)
  - 🟢 WeChat Files (`/sdcard/Download/WeiXin`)
  - 🐧 QQ Files (`/sdcard/Download/QQ`)
  - 🎵 Music & Audio (`/sdcard/Music`)
  - 📁 Internal Storage Root (`/sdcard`)
  - ⚙️ App Data Directory (`/sdcard/Android/data`)
- **Global Drag & Drop Fast Upload**: Drag any file (APKs, archives, photos, videos) directly from PC into the browser to push instantly to the open phone directory and auto-refresh the Android media store.
- **Batch Processing Matrix**:
  - Multi-item selection with one-click header select-all / deselect.
  - Live selection counter & total byte size calculation.
  - ⬇️ **Batch Download to Windows Desktop**.
  - 🗑️ **Batch Secure Deletion**.
- **Comprehensive File Operations**:
  - ⬇️ Single-click millisecond file download directly to Desktop.
  - 🖼️ High-resolution lightbox image preview (instant viewing without downloading).
  - 📁 Create new folders.
  - ✏️ In-place rename.
  - 🗑️ Safe item deletion (with confirmation & root safety guards).
- **Instant Search & Multi-criteria Sorting**: Real-time filename filtering, sort by modified date (newest first), filename (A-Z), or file size (largest first).

---

### ⚡ 2. Silky-Smooth Transfer Hub & Direct WeChat/QQ Cross-Screen Share
- **🟢 Direct Share to WeChat / 🐧 QQ / 📱 System Share Sheet**:
  - **Full-Window Smart Drag HUD Dispatch**: Drag files from anywhere on PC into the browser window. The glassmorphic HUD provides instant direct-dispatch cards: **"Send to WeChat"**, **"Send to QQ"**, **"System Share Sheet"**, and **"Current Folder"**. Releasing files pushes them to the phone in milliseconds via native ADB, while **automatically waking the screen, bypassing keyguard, and triggering the native WeChat/QQ contact picker**!
  - **Top Navigation Quick Share**: Dedicated **"🟢 Send to WeChat"** and **"🐧 Send to QQ"** buttons in the navigation bar to pick PC files and dispatch directly to mobile apps.
  - **On-Device File Direct Share**: Every file in the file explorer now features a **"🔗 Share"** button to pop up instant dispatch options to WeChat, QQ, or the system share sheet.
- **🚀 Global Clipboard Instant Paste (`Ctrl + V`)**: Press `Ctrl + V` anywhere on the page to instantly detect and transfer clipboard screenshots (`Win + Shift + S`) or copied files to the active phone directory with zero redundant clicks.
- **📊 Floating Transfer Dock**: Sleek floating drawer at the bottom-right corner displaying active transfer queues, direction indicators (⬆️ PC to Phone / ⬇️ Phone to PC), live neon progress bars, real-time speeds (MB/s), elapsed times, and dynamic "✅ Delivered to WeChat / QQ" confirmations.
- **📂 Reveal in Windows Explorer**: After pulling files to PC, click **"Show in Explorer"** in the transfer card to automatically highlight the downloaded file in native Windows File Explorer via `explorer.exe /select`!
- **🌐 Dual-Mode Download Engine**: Choose between instant millisecond ADB desktop save (`⬇️ Desktop`) or native browser HTTP stream download (`🌐 Browser DL`).
- **🛠️ Resilient ADB Stream Engine**: Completely reworked stream capture handling for ADB push stderr/stdout, eliminating false-positive upload errors and ensuring flawless file landing and media indexing.

---

### 🖥️ 3. Native Hardware-Accelerated Screen Mirroring
- **🚀 144Hz Geek High-Refresh Mode**:
  - Custom-tuned for high-refresh devices (e.g., Redmi Note 11T Pro with Dimensity 8100 & 144Hz LCD).
  - Flags: `--max-fps=144 --video-codec=h264 -b 20M --keyboard=uhid --mouse=uhid`.
  - True 144FPS monitor-grade display performance with hardware-level keyboard/mouse passthrough.
- **🌙 Dim Screen Anti-Overheating Mode**:
  - Solves the MediaTek physical screen-off video encoder disconnect issue.
  - Dynamically lowers the phone display brightness to near-zero backlight while maintaining full-frame rate rendering on PC.
- **Physical Power Toggle**: One-click phone wake / sleep controls.

---

### 💬 4. SMS & 2FA Verification Code Hub
- **Real-Time SMS Inbox**: View sender, timestamp, and message body.
- **Smart 2FA Code Parsing**: Automatically extracts 4~8 digit verification codes with a **`🔑 Copy Code`** button for instant copy to the Windows clipboard.
- **Background Notification Sync**: Dedicated background sync daemon pushes newly received SMS codes straight to the Windows clipboard and pops up native Windows toast alerts.
- **PC SMS Dispatch**: Compose and send SMS directly from PC through the phone's cellular baseband.

---

### ⚡ 5. Cross-Device Text Injection & Clipboard Sync
- One-click inject PC clipboard text, URLs, or code snippets directly into the active Android text field (`📋 PC Clipboard`).
- Inline text field to inject any custom text into the phone by pressing Enter.

---

### 🧹 6. Deep System Cleanup & Performance Booster
- **⚡ Trim Caches (1000G)**: Triggers Android `pm trim-caches 1000G` to aggressively purge accumulated application caches.
- **🛑 Kill Background Apps**: Invokes `am kill-all` to reclaim resident memory.
- **🚫 Disable Bloatware & Ads**: Root-free ADB deactivation of tracking, pre-installed adware (`msa`), and quick app services.

---

### 🌐 7. Native Bilingual Support (中文 / English)

- Integrated full-stack bilingual language toggle button (`🌐 English` / `🌐 简体中文`) in the top navigation bar.
- Instant, persistent language switching across all menus, tooltips, buttons, modals, and system alerts.

---

## 🚀 Quick Start

### Quick Launch
Double-click **`PhoneHub.lnk`** on your Desktop or execute `phonehub/launch_phonehub.vbs` to silently spin up the background backend and launch the standalone web app window.

### Manual Command Line Launch
```bash
cd phonehub
python server.py 18080
```
Open your browser and navigate to: `http://127.0.0.1:18080/`
