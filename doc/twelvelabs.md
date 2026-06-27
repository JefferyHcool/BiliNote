# TwelveLabs Pegasus 视频理解（可选）

BiliNote 默认链路是「下载 → 转写 → LLM 总结转写文本 → 笔记」。本可选后端用
[TwelveLabs](https://twelvelabs.io) 的 **Pegasus** 视频理解模型，让模型直接「看」视频，
从**画面 + 语音**两路信息生成笔记 —— 对演示、操作录屏、图表讲解类视频，画面里往往
承载了转写文本拿不到的信息。

> 这是一个**可选、不改默认行为**的供应商。不配置 TwelveLabs 供应商时，整条链路与原来完全一致。

## 它做了什么

- 新增 GPT 后端 `app/gpt/twelvelabs_gpt.py`（`TwelveLabsGPT`），实现既有 `GPT.summarize` 接口。
- `GPTFactory.from_config` 在供应商 `type == "twelvelabs"` 时路由到该后端；其余供应商不受影响。
- 复用现有笔记 prompt（`generate_base_prompt`），把风格 / 格式 / 标签等选项一并带给 Pegasus，
  但**不喂转写文本**——Pegasus 直接观看视频本身。

## 使用前提

1. 安装依赖（已加入 `backend/requirements.txt`）：

   ```bash
   pip install 'twelvelabs>=1.2.8'
   ```

2. 在 [twelvelabs.io](https://twelvelabs.io) 注册并获取 API Key（有较慷慨的免费额度）。

## 配置

在「设置 → 模型供应商」里新增一个供应商：

| 字段 | 值 |
|---|---|
| 类型(type) | `twelvelabs` |
| API Key | 你的 TwelveLabs API Key |
| 模型(model_name) | `pegasus1.5`（默认）|
| base_url | 留空即可（SDK 自带）|

之后在生成笔记时选择该供应商即可。API Key 完全从供应商配置读取，**不会硬编码、不写入仓库**。

## 已知限制

- **需要可公开访问的视频 URL**：Pegasus 1.5 直接拉取视频 URL 分析。本地文件 / 纯音频任务
  没有可用 URL，此时该后端会优雅报错并提示改用常规文本模型。
- **输出 token 下限**：Pegasus 1.5 要求 `max_tokens >= 512`（低于会被 API 拒绝）；本实现已固定满足。
- **被分析视频时长需 ≥ 4s**。
- 大文件上传（asset 直传）上限 200MB；公网 URL 上限 4GB。本集成走 URL 路径。

## 测试

无网络单测（默认随 `pytest` 运行）：

```bash
cd backend && pytest tests/test_twelvelabs_gpt.py
```

可选联网测试（仅在设置 `TWELVELABS_API_KEY` 时运行，会真实调用一次 Pegasus）：

```bash
TWELVELABS_API_KEY=tlk_xxx pytest tests/test_twelvelabs_gpt.py -k Live
```
