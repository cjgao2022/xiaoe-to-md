# xiaoe-to-md

把小鹅通课程视频自动转录为 Markdown 笔记。

## 目录结构

```
xiaoe-to-md/
├── app_gui.py       # 入口：修正 stdio 编码，启动浏览器
├── browser.py       # 核心：pywebview 内嵌浏览器 + 右侧下载面板 + 后台下载/转录
├── downloader.py    # m3u8 下载 + AES-128 解密 + ts 合并
├── transcriber.py   # faster-whisper 语音转录
├── formatter.py     # 转录结果格式化为 Markdown
├── requirements.txt
└── xiaoe-gui.spec   # PyInstaller 打包配置
```

## 运行方式

```
# 开发环境直接运行
D:\software\python313\python.exe app_gui.py

# 打包 exe
D:\software\python313\python.exe -m PyInstaller --onefile --noconsole --name xiaoe-gui ^
  --add-data "D:\software\python313\Lib\site-packages\faster_whisper\assets;faster_whisper\assets" ^
  --hidden-import "webview.platforms.winforms" ^
  --collect-all "webview" ^
  app_gui.py
```

## 依赖安装

使用系统全局 Python 3.13（`D:\software\python313\python.exe`）：

```
D:\software\python313\Scripts\pip.exe install -r requirements.txt --only-binary :all:
```

## 约定

- 内嵌浏览器：pywebview + Edge/WebView2，Cookie 持久化到 `browser_profile/`
- 下载/转录进度实时显示在右侧面板，不关闭浏览器窗口
- 历史记录持久化到 `history.json`（最多 100 条）
- 临时 ts 分片保存到 `tmp/`，合并后自动清理
- 输出 md 默认保存到桌面 `小鹅通转录/`（可在面板内修改）
- Whisper 模型：small，CPU int8，国内用 hf-mirror.com 下载
