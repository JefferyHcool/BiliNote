use tauri::{Manager, Emitter, State};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use std::env;
use std::collections::HashMap;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::Path;
use std::sync::Mutex;
use std::time::{Duration, Instant};
use serde::Serialize;

// Sidecar 启动期内前端不该看到「加载中」无限转。
// 总等待上限 = 启动期 PyInstaller 解压 + uvicorn bind 时间的最坏估计，
// 实测 macOS / Windows 慢盘大概 5-20s，设 45s 留余量但不至于让用户绝望。
const BACKEND_STARTUP_TIMEOUT_SECS: u64 = 45;
const BACKEND_DEFAULT_PORT: u16 = 8483;

// Sidecar 子进程句柄，用 Mutex 包裹方便 restart 时杀旧进程
struct SidecarHandle(Mutex<Option<CommandChild>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            let exe_path = env::current_exe().expect("无法获取当前可执行文件路径");

            // 安装路径诊断：PyInstaller sidecar 在含非 ASCII / 空格的路径下经常炸（README 已警告但缺主动防御）
            // 命中时把诊断信息 emit 给前端，由顶端横幅展示，不阻断启动
            let diag = analyze_install_path(&exe_path);
            if diag.path_has_non_ascii || diag.path_has_space || !diag.parent_writable {
                let app_handle = app.handle().clone();
                // 等前端首屏挂载好 listener；setup 阶段 window 已存在但 React 还没 render
                // 用独立线程 + 标准 sleep，不引入 tokio 依赖
                std::thread::spawn(move || {
                    std::thread::sleep(std::time::Duration::from_millis(1500));
                    if let Some(window) = app_handle.get_webview_window("main") {
                        let _ = window.emit("backend-warning", &diag);
                    }
                });
            }

            // 检查 ffmpeg 是否在 PATH 中可用
            check_ffmpeg_availability();

            // 启动 Sidecar 并把 child handle 存到 state，方便后续 restart_backend_sidecar 使用
            let child = spawn_backend_sidecar(app.handle()).map_err(|e| {
                eprintln!("Sidecar 启动失败: {}", e);
                e
            })?;
            app.manage(SidecarHandle(Mutex::new(Some(child))));

            // 启动 ready probe：异步轮询本地 BACKEND_PORT 是否在监听，
            // 解决前端 useCheckBackend 在 PyInstaller 解压期瞎猜后端起没起的问题。
            spawn_backend_ready_probe(app.handle().clone());

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_system_env_vars,
            find_executable_path,
            run_command_with_env,
            test_ffmpeg_access,
            get_install_path_diagnostics,
            restart_backend_sidecar
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        // 用 build()+run() 拿到 RunEvent 流，关键诉求：app 退出前必须 kill 掉 PyInstaller
        // sidecar，否则它会变成持有 8483 端口的孤儿进程，下次启动 BiliNote 直接 bind 失败。
        // 之前漏掉这一步导致用户 PID 96739 那种「上次没关干净 → 这次起不来」的死循环。
        .run(|app_handle, event| {
            match event {
                // ExitRequested 在用户 Cmd-Q / 点关闭 / Dock 退出时触发，先于实际进程结束。
                // Exit 是兜底——任何走到 Tauri 主循环结束的路径都会经过它。
                tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit => {
                    kill_backend_sidecar(app_handle);
                }
                _ => {}
            }
        });
}

// 关闭期统一杀 sidecar，take() 把 child 从 state 拿走避免重复 kill。
fn kill_backend_sidecar(app_handle: &tauri::AppHandle) {
    if let Some(state) = app_handle.try_state::<SidecarHandle>() {
        if let Ok(mut guard) = state.0.lock() {
            if let Some(child) = guard.take() {
                eprintln!("[shutdown] killing backend sidecar before app exit");
                let _ = child.kill();
            }
        }
    }
}

// 获取额外的二进制路径
fn get_additional_binary_paths() -> Vec<String> {
    if cfg!(target_os = "windows") {
        vec![
            "C:\\ffmpeg\\bin".to_string(),
            "C:\\Program Files\\ffmpeg\\bin".to_string(),
            "C:\\Program Files (x86)\\ffmpeg\\bin".to_string(),
            "C:\\tools\\ffmpeg\\bin".to_string(),
            "C:\\ProgramData\\chocolatey\\bin".to_string(),
        ]
    } else if cfg!(target_os = "macos") {
        vec![
            "/usr/local/bin".to_string(),
            "/opt/homebrew/bin".to_string(),
            "/usr/bin".to_string(),
            "/bin".to_string(),
            "/opt/local/bin".to_string(), // MacPorts
        ]
    } else {
        vec![
            "/usr/local/bin".to_string(),
            "/usr/bin".to_string(),
            "/bin".to_string(),
            "/snap/bin".to_string(),
            "/opt/bin".to_string(),
            "/usr/local/sbin".to_string(),
        ]
    }
}

// 增强 PATH 环境变量
fn enhance_path_variable(current_path: &str, additional_paths: &[String]) -> String {
    let path_separator = if cfg!(target_os = "windows") { ";" } else { ":" };

    let mut paths: Vec<String> = additional_paths.to_vec();

    // 添加当前 PATH
    if !current_path.is_empty() {
        paths.push(current_path.to_string());
    }

    paths.join(path_separator)
}

// 检查 ffmpeg 可用性
fn check_ffmpeg_availability() {
    use std::process::Command;

    match Command::new("ffmpeg").arg("-version").output() {
        Ok(output) => {
            if output.status.success() {
                println!("✓ FFmpeg is available in PATH");
                let version_info = String::from_utf8_lossy(&output.stdout);
                let first_line = version_info.lines().next().unwrap_or("Unknown version");
                println!("FFmpeg version: {}", first_line);
            } else {
                println!("✗ FFmpeg found but returned error");
            }
        }
        Err(e) => {
            println!("✗ FFmpeg not found in PATH: {}", e);

            // 尝试在常见路径中查找
            let common_paths = get_additional_binary_paths();
            for path in common_paths {
                let ffmpeg_path = if cfg!(target_os = "windows") {
                    format!("{}\\ffmpeg.exe", path)
                } else {
                    format!("{}/ffmpeg", path)
                };

                if std::path::Path::new(&ffmpeg_path).exists() {
                    println!("✓ Found FFmpeg at: {}", ffmpeg_path);
                    return;
                }
            }
            println!("✗ FFmpeg not found in common installation paths");
        }
    }
}

// Tauri 命令：获取系统环境变量
#[tauri::command]
fn get_system_env_vars() -> HashMap<String, String> {
    env::vars().collect()
}

// Tauri 命令：查找可执行文件路径
#[tauri::command]
fn find_executable_path(executable_name: String) -> Option<String> {
    use std::process::Command;

    // 首先尝试直接执行
    if Command::new(&executable_name).arg("--version").output().is_ok() {
        return Some(executable_name);
    }

    // 使用 which/where 命令查找
    let which_cmd = if cfg!(target_os = "windows") { "where" } else { "which" };

    if let Ok(output) = Command::new(which_cmd).arg(&executable_name).output() {
        if output.status.success() {
            let path = String::from_utf8_lossy(&output.stdout).trim().to_string();
            if !path.is_empty() {
                return Some(path);
            }
        }
    }

    // 在常见路径中搜索
    let common_paths = get_additional_binary_paths();
    for base_path in common_paths {
        let executable_path = if cfg!(target_os = "windows") {
            format!("{}\\{}.exe", base_path, executable_name)
        } else {
            format!("{}/{}", base_path, executable_name)
        };

        if std::path::Path::new(&executable_path).exists() {
            return Some(executable_path);
        }
    }

    None
}

// Tauri 命令：使用完整环境变量运行命令
#[tauri::command]
async fn run_command_with_env(
    program: String,
    args: Vec<String>
) -> Result<String, String> {
    use std::process::Command;

    let mut cmd = Command::new(&program);
    cmd.args(&args);

    // 设置所有环境变量
    for (key, value) in env::vars() {
        cmd.env(key, value);
    }

    // 增强 PATH
    let current_path = env::var("PATH").unwrap_or_default();
    let additional_paths = get_additional_binary_paths();
    let enhanced_path = enhance_path_variable(&current_path, &additional_paths);
    cmd.env("PATH", enhanced_path);

    match cmd.output() {
        Ok(output) => {
            if output.status.success() {
                Ok(String::from_utf8_lossy(&output.stdout).to_string())
            } else {
                Err(String::from_utf8_lossy(&output.stderr).to_string())
            }
        }
        Err(e) => Err(format!("Failed to execute {}: {}", program, e))
    }
}

// Tauri 命令：测试 ffmpeg 访问
#[tauri::command]
async fn test_ffmpeg_access() -> Result<String, String> {
    run_command_with_env("ffmpeg".to_string(), vec!["-version".to_string()]).await
}

// 启动后端 Sidecar：负责装环境变量、spawn、挂 stdout/stderr/terminated 监听并 emit 给前端。
// 第一次启动 + restart_backend_sidecar 都走这里，保持单一启动路径。
fn spawn_backend_sidecar(app_handle: &tauri::AppHandle) -> Result<CommandChild, String> {
    let exe_path = env::current_exe().map_err(|e| format!("无法获取可执行文件路径: {}", e))?;
    let sidecar_dir = exe_path
        .parent()
        .ok_or("无法获取可执行文件父目录")?
        .to_path_buf();

    // 收集所有系统环境变量并增强 PATH（含 ffmpeg 常见安装位置）
    let mut all_env_vars = HashMap::new();
    for (key, value) in env::vars() {
        all_env_vars.insert(key, value);
    }
    let current_path = all_env_vars.get("PATH").cloned().unwrap_or_default();
    let additional_paths = get_additional_binary_paths();
    let enhanced_path = enhance_path_variable(&current_path, &additional_paths);
    all_env_vars.insert("PATH".to_string(), enhanced_path);

    let mut sidecar_command = app_handle
        .shell()
        .sidecar("BiliNoteBackend")
        .map_err(|e| format!("找不到 BiliNoteBackend sidecar: {}", e))?;
    for (key, value) in &all_env_vars {
        sidecar_command = sidecar_command.env(key, value);
    }

    let (mut rx, child) = sidecar_command
        .current_dir(sidecar_dir)
        .spawn()
        .map_err(|e| format!("spawn sidecar 失败: {}", e))?;

    // 异步监听 stdout / stderr / terminated 事件，转发到前端 webview
    let app_handle_for_listener = app_handle.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            // window 句柄每次重新取，允许窗口关闭重开
            let window = app_handle_for_listener.get_webview_window("main");
            match event {
                CommandEvent::Stdout(line) => {
                    let output = String::from_utf8_lossy(&line).to_string();
                    println!("Backend stdout: {}", output);
                    if let Some(w) = window {
                        let _ = w.emit("backend-message", Some(output));
                    }
                }
                CommandEvent::Stderr(line) => {
                    let error = String::from_utf8_lossy(&line).to_string();
                    eprintln!("Backend stderr: {}", error);
                    if let Some(w) = window {
                        let _ = w.emit("backend-error", Some(error));
                    }
                }
                CommandEvent::Terminated(payload) => {
                    println!("Backend terminated with code: {:?}", payload.code);
                    if let Some(w) = window {
                        let _ = w.emit("backend-terminated", Some(payload.code));
                    }
                    break;
                }
                _ => {
                    println!("Backend event: {:?}", event);
                }
            }
        }
    });

    Ok(child)
}

// 重启 sidecar：杀旧 child，spawn 新 child，回写到 state。
#[tauri::command]
fn restart_backend_sidecar(
    state: State<'_, SidecarHandle>,
    app: tauri::AppHandle,
) -> Result<(), String> {
    // 0. 先告诉前端「我们要重启了」。前端可以借此忽略接下来 N 秒内的 backend-terminated
    //    事件——那是我们主动 kill 老 sidecar 的副作用，不是真异常。否则会出现：
    //    terminated 事件延迟到达 → 覆盖掉 'running' 状态 → 面板永远显示「已退出」。
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.emit("backend-restarting", ());
    }
    // 1. 拿出旧 child 并 kill（kill 失败也继续，可能进程已经退了）
    {
        let mut guard = state.0.lock().map_err(|e| format!("锁 sidecar state 失败: {}", e))?;
        if let Some(child) = guard.take() {
            let _ = child.kill();
        }
    }
    // 2. 重新 spawn
    let new_child = spawn_backend_sidecar(&app)?;
    {
        let mut guard = state.0.lock().map_err(|e| format!("锁 sidecar state 失败: {}", e))?;
        *guard = Some(new_child);
    }
    // 3. emit 一个事件让前端知道已重启
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.emit("backend-restarted", ());
    }
    // 4. 重启后同样起一次 ready probe，让前端能及时退出失败态
    spawn_backend_ready_probe(app);
    Ok(())
}

// 后端就绪探测：异步轮询 GET /api/sys_check，要求 HTTP 200 才算就绪。
//
// 旧实现只做 TcpStream::connect_timeout——但端口被另一个孤儿 sidecar 占着时也会
// 连得通，导致 emit('backend-ready') 误判：前端进入主界面，但真正的新 sidecar
// 没 bind 上立刻就死，banner 永远停在「后端进程已退出」。
//
// 真发一个 HTTP 请求拿 200 才算「这是我们的后端在响应」。
fn spawn_backend_ready_probe(app: tauri::AppHandle) {
    let port: u16 = env::var("BACKEND_PORT")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(BACKEND_DEFAULT_PORT);
    let addr: SocketAddr = format!("127.0.0.1:{}", port).parse().expect("invalid backend addr");
    let timeout = Duration::from_secs(BACKEND_STARTUP_TIMEOUT_SECS);

    std::thread::spawn(move || {
        let start = Instant::now();
        let probe_interval = Duration::from_millis(500);
        loop {
            if probe_sys_check(&addr) {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.emit("backend-ready", port);
                    println!("Backend ready on port {} after {:?}", port, start.elapsed());
                }
                return;
            }
            if start.elapsed() >= timeout {
                if let Some(window) = app.get_webview_window("main") {
                    let payload = format!(
                        "后端在 {}s 内 /api/sys_check 未返回 200，疑似启动失败或端口 {} 被其他进程占用",
                        timeout.as_secs(),
                        port
                    );
                    let _ = window.emit("backend-startup-timeout", payload);
                    eprintln!(
                        "Backend startup timeout: /api/sys_check did not return 200 on 127.0.0.1:{} after {:?}",
                        port,
                        start.elapsed()
                    );
                }
                return;
            }
            std::thread::sleep(probe_interval);
        }
    });
}

// 极简 HTTP/1.0 GET /api/sys_check —— 用 std::net 手写避免引 reqwest/ureq 的重依赖。
// 任何错都视为「还没就绪」，下次 tick 再试。
fn probe_sys_check(addr: &SocketAddr) -> bool {
    let connect_timeout = Duration::from_millis(800);
    let rw_timeout = Duration::from_millis(1500);
    let mut stream = match TcpStream::connect_timeout(addr, connect_timeout) {
        Ok(s) => s,
        Err(_) => return false,
    };
    let _ = stream.set_read_timeout(Some(rw_timeout));
    let _ = stream.set_write_timeout(Some(rw_timeout));
    // HTTP/1.0 + Connection: close 让服务端发完响应就关，免去 chunked / keep-alive 解析
    let req = format!(
        "GET /api/sys_check HTTP/1.0\r\nHost: 127.0.0.1:{}\r\nConnection: close\r\n\r\n",
        addr.port()
    );
    if stream.write_all(req.as_bytes()).is_err() {
        return false;
    }
    // 只要 status line，64 字节够了
    let mut buf = [0u8; 64];
    let n = match stream.read(&mut buf) {
        Ok(n) => n,
        Err(_) => return false,
    };
    let head = std::str::from_utf8(&buf[..n]).unwrap_or("");
    // 兼容 HTTP/1.0 / 1.1 起始行
    head.starts_with("HTTP/1.1 200") || head.starts_with("HTTP/1.0 200")
}

// 安装路径诊断：PyInstaller 在含非 ASCII / 空格的路径下加载 _internal/* 经常炸；
// 父目录不可写时模型 / 配置 / 日志也无法落盘
#[derive(Serialize, Clone)]
struct InstallPathDiagnostics {
    exe_path: String,
    path_has_non_ascii: bool,
    path_has_space: bool,
    parent_writable: bool,
    platform: String,
}

fn analyze_install_path(exe_path: &Path) -> InstallPathDiagnostics {
    let path_str = exe_path.to_string_lossy().to_string();
    // 不在 ASCII 范围内的字符（中文 / 日文 / 西里尔等都会命中 PyInstaller 路径解析坑）
    let has_non_ascii = path_str.chars().any(|c| !c.is_ascii());
    // 空格本身在 Windows shell 引号场景偶尔出问题，且 macOS path 里也偶尔触发 sidecar 启动失败
    let has_space = path_str.contains(' ');
    // 父目录可写：PyInstaller 解压 _internal/、写日志、写配置都需要这个
    let parent = exe_path.parent();
    let parent_writable = parent
        .and_then(|p| {
            let probe = p.join(".bilinote_write_probe");
            match std::fs::write(&probe, b"x") {
                Ok(_) => {
                    let _ = std::fs::remove_file(&probe);
                    Some(true)
                }
                Err(_) => Some(false),
            }
        })
        .unwrap_or(false);

    InstallPathDiagnostics {
        exe_path: path_str,
        path_has_non_ascii: has_non_ascii,
        path_has_space: has_space,
        parent_writable,
        platform: std::env::consts::OS.to_string(),
    }
}

// Tauri 命令：让前端按需重新查询诊断结果（比如用户卸载到新目录后重启）
#[tauri::command]
fn get_install_path_diagnostics() -> InstallPathDiagnostics {
    let exe_path = env::current_exe().unwrap_or_default();
    analyze_install_path(&exe_path)
}

// 可选：添加一个函数来动态更新 sidecar 的环境变量
#[tauri::command]
async fn update_sidecar_environment(
    app_handle: tauri::AppHandle,
    additional_env_vars: HashMap<String, String>
) -> Result<(), String> {
    // 这个函数可以用来在运行时更新环境变量
    // 注意：这需要重启 sidecar 才能生效

    for (key, value) in additional_env_vars {
        env::set_var(key, value);
    }

    Ok(())
}