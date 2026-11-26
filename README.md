# PaperBanana-Interact Codex Bridge

在本机运行 PaperBanana-Interact，通过已登录的 Codex 生成论文示意图，并在浏览器里用多轮反馈改图。仓库包含 PaperBanana-Interact 源码、Python 依赖锁文件和共用桥接器。

## 安装和启动

准备 [uv](https://docs.astral.sh/uv/getting-started/installation/) 以及支持内置生图的 [Codex CLI](https://learn.chatgpt.com/docs/cli)。在 CLI 中用自己的 ChatGPT 账号登录。macOS 上也可以使用 ChatGPT App 自带的 Codex。启动时，uv 会根据锁文件建立 Python 3.12 环境并安装依赖。

```sh
./launch
```

打开 [本地应用](http://127.0.0.1:7861)，保留默认的 `codex` 和 `codex-image`，API Key 留空。进入 **Iterative Refinement**，输入方法描述和图注，生成初稿后点 **Pin**，再发送修改意见。

端口已被使用时，可以指定另一个端口。终端中按 `Ctrl+C` 停止。

```sh
./launch --port 7862
```

启动器依次查找 `PAPERBANANA_CODEX_BIN`、`PATH` 中的 `codex`、macOS ChatGPT App 内置的 Codex。可以显式指定可执行文件。

```sh
PAPERBANANA_CODEX_BIN=/path/to/codex ./launch
```

## 桥接如何工作

[启动器](launch.py) 在加载上游 Gradio 界面时注册两个模型选项。[桥接器](codex_bridge.py) 通过标准输入输出与本机 Codex App Server 通信，转发文本及附图，再将文本结果或图片文件返回界面。每次请求使用临时会话。 [Codex App Server 协议](https://learn.chatgpt.com/docs/app-server#protocol)

服务只监听 `127.0.0.1`。论文文本和附图会由 Codex 发送给 ChatGPT 处理，使用当前账号的额度。出图宽高比与分辨率作为目标传入。参考图检索的数据集可按需安装，详见上游 README。

## 上游与许可证

[PaperBanana-Interact 原始 README](vendor/paperbanana-interact/README.md) 随源码保留。上游版本和 Apache 2.0 许可证见 [第三方声明](THIRD_PARTY_NOTICES.md)。
