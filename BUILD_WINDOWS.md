# BiliNote Windows 安装包构建指南

本文档详细说明如何将 BiliNote 项目构建为 Windows 安装包（.exe 或 .msi）。

## 📋 前置要求

### 1. 必需软件

- **Python 3.8+**：用于后端打包
- **Node.js 16+** 和 **pnpm**：用于前端构建
- **Rust**：用于 Tauri 打包
  - 安装方式：访问 [https://rustup.rs/](https://rustup.rs/) 下载安装
  - 安装后运行：`rustup default stable`
- **PyInstaller**：用于打包 Python 后端
  ```bash
  pip install pyinstaller
  ```
- **FFmpeg**：必须安装并添加到系统 PATH
  - 下载地址：[https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)

### 2. 开发工具

- **Visual Studio Build Tools**（Rust 编译需要）
  - 下载地址：[https://visualstudio.microsoft.com/downloads/](https://visualstudio.microsoft.com/downloads/)
  - 安装时选择 "Desktop development with C++"

## 🔧 构建步骤

### 方式一：使用自动化脚本（推荐）

项目已提供 [`backend/build.bat`](backend/build.bat) 脚本，可自动完成后端打包。

#### 步骤 1：准备环境配置

```bash
# 在项目根目录下
copy .env.example .env
```

编辑 [`.env`](.env) 文件，配置必要的环境变量（如 API keys 等）。

#### 步骤 2：运行后端打包脚本

```bash
# 在项目根目录下执行
backend\build.bat
```

**脚本执行内容：**
1. 清理旧的构建文件
2. 创建 Tauri 所需的目录结构
3. 使用 PyInstaller 打包 Python 后端为独立可执行文件
4. 将打包后的文件放置到 `BillNote_frontend/src-tauri/bin/` 目录
5. 重命名可执行文件以匹配 Tauri 的命名规范

**输出位置：**
- `BillNote_frontend/src-tauri/bin/BiliNoteBackend/BiliNoteBackend-<target-triple>.exe`

#### 步骤 3：构建前端并打包为 Windows 安装程序

```bash
# 进入前端目录
cd BillNote_frontend

# 安装依赖（如果还没安装）
pnpm install

# 构建 Tauri 应用（生成 Windows 安装包）
pnpm tauri build
```

**构建产物位置：**
- 安装程序：`BillNote_frontend/src-tauri/target/release/bundle/nsis/BiliNote_<version>_x64-setup.exe`
- 便携版：`BillNote_frontend/src-tauri/target/release/bundle/nsis/BiliNote_<version>_x64_en-US.msi`

### 方式二：手动分步构建

如果自动化脚本遇到问题，可以手动执行以下步骤：

#### 1. 打包 Python 后端

```bash
# 在项目根目录
cd backend

# 安装依赖
pip install -r requirements.txt

# 使用 PyInstaller 打包
pyinstaller ^
  -y ^
  --name BiliNoteBackend ^
  --paths . ^
  --distpath ../BillNote_frontend/src-tauri/bin ^
  --workpath build ^
  --specpath . ^
  --hidden-import uvicorn ^
  --hidden-import fastapi ^
  --hidden-import starlette ^
  --add-data "app/db/builtin_providers.json;." ^
  --add-data "../.env;." ^
  main.py
```

#### 2. 重命名后端可执行文件

```bash
# 获取 Rust target triple
rustc -Vv | findstr "host"

# 假设输出为 x86_64-pc-windows-msvc，则重命名为：
move BillNote_frontend\src-tauri\bin\BiliNoteBackend\BiliNoteBackend.exe ^
     BillNote_frontend\src-tauri\bin\BiliNoteBackend\BiliNoteBackend-x86_64-pc-windows-msvc.exe
```

#### 3. 构建前端和 Tauri 应用

```bash
cd BillNote_frontend

# 安装前端依赖
pnpm install

# 构建前端资源
pnpm build --mode tauri

# 打包 Tauri 应用
pnpm tauri build
```

## 📦 构建产物说明

构建完成后，会在以下位置生成安装包：

```
BillNote_frontend/src-tauri/target/release/bundle/
├── nsis/
│   ├── BiliNote_1.8.1_x64-setup.exe    # NSIS 安装程序（推荐分发）
│   └── BiliNote_1.8.1_x64_en-US.msi    # MSI 安装程序
└── msi/
    └── BiliNote_1.8.1_x64_en-US.msi    # 另一个 MSI 版本
```

### 安装包类型说明

- **NSIS (.exe)**：更现代的安装程序，支持自定义安装界面，推荐使用
- **MSI (.msi)**：Windows 标准安装包格式，适合企业环境部署

## ⚠️ 常见问题

### 1. PyInstaller 打包失败

**问题：** 提示找不到某些模块

**解决方案：**
- 确保所有依赖都已安装：`pip install -r backend/requirements.txt`
- 检查 [`backend/build.bat`](backend/build.bat) 中的 `--hidden-import` 参数是否包含所有必需模块

### 2. Tauri 构建失败

**问题：** Rust 编译错误

**解决方案：**
- 确保已安装 Visual Studio Build Tools
- 更新 Rust：`rustup update`
- 清理缓存后重试：
  ```bash
  cd BillNote_frontend
  pnpm tauri build --clean
  ```

### 3. 后端可执行文件无法运行

**问题：** 双击 `.exe` 文件后闪退或报错

**解决方案：**
- 确保 `.env` 文件已正确打包（检查 `BiliNoteBackend/_internal/` 目录）
- 确保 FFmpeg 已安装并在系统 PATH 中
- 检查是否在非中文路径下运行（项目要求）

### 4. 缺少 DLL 文件

**问题：** 运行时提示缺少 `vcruntime140.dll` 等

**解决方案：**
- 安装 Visual C++ Redistributable：
  - [下载地址](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)

### 5. 打包后体积过大

**问题：** 生成的安装包超过 500MB

**解决方案：**
- 这是正常的，因为包含了：
  - Python 运行时
  - FastAPI 和所有依赖
  - FFmpeg 库
  - Whisper 模型（如果包含）
  - 前端资源

如需减小体积，可以考虑：
- 不打包大型 AI 模型，改为首次运行时下载
- 使用 UPX 压缩可执行文件（可能影响启动速度）

## 🔍 验证构建

构建完成后，建议进行以下测试：

1. **安装测试**
   ```bash
   # 运行安装程序
   BiliNote_1.8.1_x64-setup.exe
   ```

2. **功能测试**
   - 启动应用
   - 测试视频下载功能
   - 测试 AI 笔记生成功能
   - 检查配置保存是否正常

3. **卸载测试**
   - 通过控制面板卸载
   - 检查是否有残留文件

## 📝 自定义构建

### 修改应用信息

编辑 [`BillNote_frontend/src-tauri/tauri.conf.json`](BillNote_frontend/src-tauri/tauri.conf.json)：

```json
{
  "productName": "BiliNote",
  "version": "1.8.1",
  "identifier": "com.jefferyhuang.bilinote"
}
```

### 修改应用图标

替换以下文件：
- `BillNote_frontend/src-tauri/icons/icon.ico`（Windows 图标）
- `BillNote_frontend/src-tauri/icons/icon.png`（其他平台）

### 修改安装程序配置

Tauri 使用 NSIS 作为默认的 Windows 安装程序生成器。可以通过修改 [`tauri.conf.json`](BillNote_frontend/src-tauri/tauri.conf.json) 中的 `bundle` 配置来自定义：

```json
{
  "bundle": {
    "active": true,
    "targets": ["nsis", "msi"],
    "windows": {
      "certificateThumbprint": null,
      "digestAlgorithm": "sha256",
      "timestampUrl": ""
    }
  }
}
```

## 🚀 发布流程

1. **更新版本号**
   - 修改 [`BillNote_frontend/src-tauri/tauri.conf.json`](BillNote_frontend/src-tauri/tauri.conf.json) 中的 `version`
   - 修改 [`BillNote_frontend/package.json`](BillNote_frontend/package.json) 中的 `version`

2. **构建发布版本**
   ```bash
   backend\build.bat
   cd BillNote_frontend
   pnpm tauri build
   ```

3. **测试安装包**
   - 在干净的 Windows 系统上测试安装
   - 验证所有功能正常

4. **发布到 GitHub Releases**
   - 创建新的 Release tag
   - 上传生成的 `.exe` 和 `.msi` 文件
   - 编写 Release Notes

## 📚 相关资源

- [Tauri 官方文档](https://tauri.app/v1/guides/)
- [PyInstaller 文档](https://pyinstaller.org/en/stable/)
- [项目 README](README.md)
- [已发布的 Release](https://github.com/JefferyHcool/BiliNote/releases)

## 💡 提示

- **首次构建**可能需要较长时间（下载依赖、编译 Rust 等）
- **增量构建**会快很多
- 建议在**非中文路径**下进行构建
- 构建前确保**磁盘空间充足**（至少 5GB）
- 如遇到问题，可以加入项目 QQ 群：785367111

---

最后更新：2026-01-27
