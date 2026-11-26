# PaperBanana-Interact Codex Bridge

在本机运行 PaperBanana-Interact，通过已登录的 Codex 生成论文示意图，并在浏览器里用多轮反馈改图。仓库包含 PaperBanana-Interact 源码、Python 依赖锁文件和共用桥接器。

## 第一次安装

1. 克隆本仓库，或在 GitHub 上点 **Code → Download ZIP** 并解压。打开终端，进入同时包含 `README.md` 和 `pyproject.toml` 的项目目录。
2. 按官方说明安装 uv，并重新打开终端。运行 `uv --version` 确认安装。 [uv 安装指南](https://docs.astral.sh/uv/getting-started/installation/)
3. 准备支持 App Server 和内置生图的 Codex CLI。使用独立版 CLI 时，运行 `codex --version` 和 `codex login status` 检查版本与登录状态。如果尚未用 ChatGPT 账号登录，运行 `codex login`，在浏览器中完成登录。每位使用者使用自己的账号。 [Codex CLI 安装指南](https://learn.chatgpt.com/docs/codex/cli#install-codex) · [Codex 登录说明](https://learn.chatgpt.com/docs/auth)

### 已安装 ChatGPT App 时

**macOS** 上，如果 ChatGPT 位于 `/Applications/ChatGPT.app`，启动器会自动查找它内置的 Codex CLI，可以直接进入「启动和试用」。内置 CLI 的完整路径如下，可用来检查登录状态。如果尚未登录，将命令末尾的 `login status` 改为 `login`。

```sh
"/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex" login status
```

如果 App 放在别处，在 Finder 中右键 `ChatGPT.app`，选择 **显示包内容**，进入 `Contents/Resources/codex-cli`。对里面的 `CodexCLI.app` 再选择一次 **显示包内容**，即可在 `Contents/MacOS` 找到 `codex`。把这个文件的完整路径填入下方「手动指定 Codex 路径」中的 `PAPERBANANA_CODEX_BIN`。

**Windows** 上，项目通过 `PATH` 或 `PAPERBANANA_CODEX_BIN` 找到 CLI。可以按第 3 步安装 Windows 版独立 Codex CLI，再用自己的 ChatGPT 账号登录。

## 启动和试用

在项目目录运行下面的命令。macOS、Linux 和 Windows PowerShell 使用同一条命令。第一次启动时，uv 会准备 Python 3.12 虚拟环境，并按 `uv.lock` 安装依赖。

```sh
uv run --locked -- python -B launch.py
```

macOS 和 Linux 也可以运行 `./launch`。打开 [本地应用](http://127.0.0.1:7861)，保留默认的 `codex` 和 `codex-image`，API Key 留空。进入 **Iterative Refinement**，点 **Load Example** 载入示例，生成初稿后点 **Pin**，再发送修改意见。终端中按 `Ctrl+C` 停止服务。

如果默认端口已被占用，在启动命令末尾加 `--port 7862`，然后打开 [备用端口](http://127.0.0.1:7862)。

## 手动指定 Codex 路径

桥接器依次查找 `PAPERBANANA_CODEX_BIN`、`PATH` 中的 `codex`、macOS ChatGPT App 内置的 Codex。如果安装在自定义目录，或者终端通过别名调用 Codex，可以直接指定可执行文件的完整路径。将示例路径替换成自己的路径，再在同一个终端运行启动命令。

**macOS / Linux**

```sh
export PAPERBANANA_CODEX_BIN="/path/to/codex"
"$PAPERBANANA_CODEX_BIN" login status
uv run --locked -- python -B launch.py
```

**Windows PowerShell**

```powershell
$env:PAPERBANANA_CODEX_BIN = 'C:\Tools\codex.exe'
& $env:PAPERBANANA_CODEX_BIN login status
uv run --locked -- python -B launch.py
```

如果页面能打开但生成时提示登录，用桥接器实际选中的 Codex 可执行文件运行 `login`，然后重试生成。

端到端的生图和改图已在 macOS Apple Silicon 上验证。Windows x64 已通过锁文件的目标平台依赖检查。

## 桥接如何工作

[启动器](launch.py) 在加载上游 Gradio 界面时注册两个模型选项。[桥接器](codex_bridge.py) 通过标准输入输出与本机 Codex App Server 通信，转发文本及附图，再将文本结果或图片文件返回界面。每次请求使用临时会话。 [Codex App Server 协议](https://learn.chatgpt.com/docs/app-server#protocol)

服务只监听 `127.0.0.1`。论文文本和附图会由 Codex 发送给 ChatGPT 处理，使用当前账号的额度。出图宽高比与分辨率作为目标传入。参考图检索的数据集可按需安装，详见上游 README。

## 上游与许可证

[PaperBanana-Interact 原始 README](vendor/paperbanana-interact/README.md) 随源码保留。上游版本和 Apache 2.0 许可证见 [第三方声明](THIRD_PARTY_NOTICES.md)。
