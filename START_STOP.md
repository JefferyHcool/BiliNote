# 启动与关闭

## 启动

在仓库根目录执行一键启动脚本，脚本会同时启动后端和前端，并在当前终端保持运行：

```bash
bash start.sh
```

启动完成后浏览器访问：<http://localhost:3015>

日志位于 `logs/backend.log` 和 `logs/frontend.log`。

如果启动输出 `already running; reusing it`，说明该服务已经由其他终端或进程启动；一键脚本不会接管它，按 `Ctrl+C` 也不会停止它。请回到启动该服务的终端按 `Ctrl+C`。

如果需要手动分别启动，也可以使用下面的命令。

后端：

```bash
cd /data0/zhoult/BiliNote
bash backend/run.sh
```

前端：

```bash
cd /data0/zhoult/BiliNote/BillNote_frontend
corepack pnpm@9.15.0 dev -- --host 0.0.0.0
```

## 关闭

运行一键脚本时，在当前终端按 `Ctrl+C` 会同时关闭该脚本启动的两个服务。手动启动时，在前端和后端各自的终端按 `Ctrl+C`。
