"""
内嵌浏览器 + 下载记录面板一体化。
- pywebview (Edge/WebView2) 显示小鹅通网页
- 右侧注入可折叠下载面板，实时显示下载/转录进度
- 下载/转录在后台线程运行，通过 evaluate_js 更新进度
- 历史记录持久化到 history.json
"""

import json
import re
import time
import threading
from datetime import datetime
from pathlib import Path

import webview

HOMEPAGE   = "https://appxkncwzsb8241.h5.xiaoeknow.com/p/decorate/homepage"
STORAGE_DIR = Path(__file__).parent / "browser_profile"
HISTORY_FILE = Path(__file__).parent / "history.json"
DEFAULT_OUTPUT = str(Path.home() / "Desktop" / "小鹅通转录")


def _safe_fn(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name.strip()[:80] or "课程视频"


def _load_history() -> list:
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _append_history(title: str, md_path: str):
    records = _load_history()
    records.insert(0, {
        "time": datetime.now().strftime("%m-%d %H:%M"),
        "title": title,
        "path": md_path,
    })
    HISTORY_FILE.write_text(
        json.dumps(records[:100], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 注入到页面的 JS：面板 UI + fetch/XHR 钩子
# ─────────────────────────────────────────────────────────────────────────────
_INJECT_JS = r"""
(function() {

// ── 面板只创建一次 ────────────────────────────────────────────────────────
if (!document.getElementById('__xdl_root__')) {

    var _css = document.createElement('style');
    _css.textContent = `
        #__xdl_root__ {
            position:fixed; top:0; right:0; height:100vh; width:300px;
            background:#1e293b; color:#e2e8f0;
            font-family:'Microsoft YaHei',system-ui,sans-serif; font-size:13px;
            z-index:2147483647; display:flex; flex-direction:column;
            box-shadow:-4px 0 24px rgba(0,0,0,.5);
            transform:translateX(100%); transition:transform .28s ease;
        }
        #__xdl_root__.xdl-open { transform:translateX(0); }
        #__xdl_tab__ {
            position:fixed; top:50%; right:0; transform:translateY(-50%);
            background:#2563eb; color:#fff; z-index:2147483648;
            writing-mode:vertical-rl; padding:14px 7px; border-radius:7px 0 0 7px;
            cursor:pointer; font-size:12px; font-weight:bold; letter-spacing:2px;
            box-shadow:-3px 0 10px rgba(0,0,0,.4); user-select:none;
            font-family:'Microsoft YaHei',sans-serif; transition:right .28s ease;
        }
        .__xdl_hd__ {
            background:#0f172a; padding:12px 14px; flex-shrink:0;
            display:flex; align-items:center; justify-content:space-between;
            border-bottom:1px solid #334155;
        }
        .__xdl_hd__ b { font-size:14px; }
        .__xdl_hd__ span { font-size:11px; color:#64748b; }
        .__xdl_dir__ {
            padding:8px 12px; background:#1e293b; flex-shrink:0;
            border-bottom:1px solid #334155; display:flex; align-items:center; gap:6px;
        }
        .__xdl_dir__ input {
            flex:1; background:#0f172a; border:1px solid #334155; color:#94a3b8;
            font-size:11px; padding:4px 7px; border-radius:4px; outline:none;
            font-family:inherit; min-width:0;
        }
        .__xdl_dir__ input:focus { border-color:#3b82f6; }
        .__xdl_dir_btn__ {
            background:#334155; border:none; color:#e2e8f0; padding:4px 10px;
            border-radius:4px; cursor:pointer; font-size:11px; flex-shrink:0;
            font-family:inherit; white-space:nowrap;
        }
        .__xdl_dir_btn__:hover { background:#475569; }
        .__xdl_list__ { flex:1; overflow-y:auto; padding:10px; display:flex; flex-direction:column; gap:8px; }
        .__xdl_empty__ { color:#475569; text-align:center; margin-top:48px; line-height:2; font-size:12px; }
        .__xdl_card__ {
            background:#0f172a; border-radius:8px; padding:12px;
            border:1px solid #334155; flex-shrink:0;
        }
        .__xdl_card__.xdl-done { border-color:#16a34a22; }
        .__xdl_card__.xdl-err  { border-color:#dc262622; }
        .__xdl_card__ .__xdl_ttl__ {
            font-size:12px; font-weight:bold; color:#cbd5e1;
            word-break:break-all; line-height:1.5; margin-bottom:10px;
        }
        .__xdl_br__ { display:flex; align-items:center; gap:7px; margin-bottom:5px; }
        .__xdl_lbl__ { font-size:11px; color:#64748b; width:26px; flex-shrink:0; }
        .__xdl_trk__ { flex:1; height:7px; background:#1e3a5f; border-radius:4px; overflow:hidden; }
        .__xdl_fill__ { height:100%; width:0; border-radius:4px; transition:width .4s ease; }
        .__xdl_fill__.xdl-dl   { background:#3b82f6; }
        .__xdl_fill__.xdl-tx   { background:#7c3aed; }
        .__xdl_fill__.xdl-done { background:#16a34a; }
        .__xdl_pct__ { font-size:11px; color:#64748b; width:34px; text-align:right; flex-shrink:0; font-family:monospace; }
        .__xdl_ft__  { display:flex; align-items:center; justify-content:space-between; margin-top:8px; }
        .__xdl_st__  { font-size:11px; color:#64748b; }
        .__xdl_ob__  {
            background:#15803d; border:none; color:#fff; padding:3px 10px;
            border-radius:4px; cursor:pointer; font-size:11px; display:none;
            font-family:inherit;
        }
        .__xdl_ob__:hover { background:#166534; }
        #__xdl_dl_btn__ {
            position:fixed; bottom:24px; left:50%; transform:translateX(-50%);
            background:#16a34a; color:#fff; padding:14px 36px; border-radius:40px;
            font-size:15px; font-weight:bold; cursor:pointer; z-index:2147483647;
            box-shadow:0 4px 20px rgba(0,0,0,.45); user-select:none;
            font-family:system-ui,sans-serif; letter-spacing:.5px;
            transition:background .2s; display:none;
        }
    `;
    document.head.appendChild(_css);

    // 面板根节点
    var _root = document.createElement('div');
    _root.id = '__xdl_root__';
    document.body.appendChild(_root);

    // 侧边展开按钮
    var _tab = document.createElement('div');
    _tab.id = '__xdl_tab__';
    _tab.textContent = '下载记录';
    document.body.appendChild(_tab);

    _tab.addEventListener('click', function() {
        var open = _root.classList.toggle('xdl-open');
        _tab.style.right = open ? '300px' : '0';
    });

    // 头部
    var _hd = document.createElement('div');
    _hd.className = '__xdl_hd__';
    _hd.innerHTML = '<b>📋 下载记录</b><span id="__xdl_cnt__"></span>';
    _root.appendChild(_hd);

    // 目录行
    var _dir = document.createElement('div');
    _dir.className = '__xdl_dir__';
    _dir.innerHTML =
        '<input id="__xdl_dir_inp__" type="text" spellcheck="false" />' +
        '<button class="__xdl_dir_btn__" id="__xdl_dir_btn__">选择</button>';
    _root.appendChild(_dir);

    // 任务列表
    var _list = document.createElement('div');
    _list.className = '__xdl_list__';
    _list.id = '__xdl_list__';
    _list.innerHTML = '<div class="__xdl_empty__" id="__xdl_empty__">暂无记录<br>选择视频后点击「⬇ 下载转录」</div>';
    _root.appendChild(_list);

    // 目录输入框失焦时同步到 Python
    document.getElementById('__xdl_dir_inp__').addEventListener('blur', function() {
        window.__xdl_output_dir__ = this.value;
        if (window.pywebview && window.pywebview.api)
            window.pywebview.api.set_folder(this.value);
    });

    // 选择文件夹按钮
    document.getElementById('__xdl_dir_btn__').addEventListener('click', function() {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.choose_folder().then(function(d) {
                if (d) {
                    document.getElementById('__xdl_dir_inp__').value = d;
                    window.__xdl_output_dir__ = d;
                }
            });
        }
    });

    // 全局路径表（taskId -> mdPath）
    window.__xdl_paths__ = {};
    window.__xdl_output_dir__ = '';
}

// ── 任务管理函数（每次注入都重新定义，防止页面刷新后丢失）───────────────

window.xdlSetFolder = function(dir) {
    var inp = document.getElementById('__xdl_dir_inp__');
    if (inp) { inp.value = dir; window.__xdl_output_dir__ = dir; }
};

window.xdlAddTask = function(id, title) {
    var empty = document.getElementById('__xdl_empty__');
    if (empty) empty.style.display = 'none';

    var card = document.createElement('div');
    card.className = '__xdl_card__';
    card.id = '__xdl_card_' + id;

    var ttl = document.createElement('div');
    ttl.className = '__xdl_ttl__';
    ttl.textContent = title;
    card.appendChild(ttl);

    function mkBar(cls, fillId, pctId) {
        var row = document.createElement('div');
        row.className = '__xdl_br__';
        row.innerHTML =
            '<span class="__xdl_lbl__">' + (cls === 'xdl-dl' ? '下载' : '转录') + '</span>' +
            '<div class="__xdl_trk__"><div class="__xdl_fill__ ' + cls + '" id="' + fillId + '"></div></div>' +
            '<span class="__xdl_pct__" id="' + pctId + '">0%</span>';
        return row;
    }
    card.appendChild(mkBar('xdl-dl', '__xdl_df_' + id, '__xdl_dp_' + id));
    card.appendChild(mkBar('xdl-tx', '__xdl_tf_' + id, '__xdl_tp_' + id));

    var ft = document.createElement('div');
    ft.className = '__xdl_ft__';

    var st = document.createElement('span');
    st.className = '__xdl_st__';
    st.id = '__xdl_st_' + id;
    st.textContent = '⏳ 下载中…';
    ft.appendChild(st);

    var ob = document.createElement('button');
    ob.className = '__xdl_ob__';
    ob.id = '__xdl_ob_' + id;
    ob.textContent = '📄 打开文件';
    ob.addEventListener('click', function() {
        var p = window.__xdl_paths__[id];
        if (p && window.pywebview && window.pywebview.api)
            window.pywebview.api.open_file_by_path(p);
    });
    ft.appendChild(ob);
    card.appendChild(ft);

    var list = document.getElementById('__xdl_list__');
    list.insertBefore(card, list.firstChild);

    // 自动展开面板
    var root = document.getElementById('__xdl_root__');
    if (!root.classList.contains('xdl-open')) {
        root.classList.add('xdl-open');
        document.getElementById('__xdl_tab__').style.right = '300px';
    }

    var cnt = document.querySelectorAll('.__xdl_card__').length;
    var cntEl = document.getElementById('__xdl_cnt__');
    if (cntEl) cntEl.textContent = cnt + ' 项';
};

window.xdlUpdate = function(id, type, pct) {
    var fillId = type === 'dl' ? '__xdl_df_' : '__xdl_tf_';
    var pctId  = type === 'dl' ? '__xdl_dp_' : '__xdl_tp_';
    var fill = document.getElementById(fillId + id);
    var pctEl = document.getElementById(pctId + id);
    var p = Math.min(Math.max(pct, 0), 100);
    if (fill)  fill.style.width = p + '%';
    if (pctEl) pctEl.textContent = Math.round(p) + '%';
    if (type === 'dl' && p >= 100) {
        var st = document.getElementById('__xdl_st_' + id);
        if (st) st.textContent = '⏳ 转录中…';
    }
};

window.xdlDone = function(id, mdPath) {
    window.__xdl_paths__[id] = mdPath;
    ['__xdl_df_', '__xdl_tf_'].forEach(function(pre) {
        var f = document.getElementById(pre + id);
        if (f) { f.style.width = '100%'; f.classList.add('xdl-done'); }
    });
    ['__xdl_dp_', '__xdl_tp_'].forEach(function(pre) {
        var p = document.getElementById(pre + id);
        if (p) p.textContent = '100%';
    });
    var st = document.getElementById('__xdl_st_' + id);
    if (st) st.textContent = '✅ 完成';
    var ob = document.getElementById('__xdl_ob_' + id);
    if (ob) ob.style.display = 'block';
    var card = document.getElementById('__xdl_card_' + id);
    if (card) card.classList.add('xdl-done');
};

window.xdlError = function(id, msg) {
    var st = document.getElementById('__xdl_st_' + id);
    if (st) st.textContent = '❌ ' + msg.substring(0, 40);
    var card = document.getElementById('__xdl_card_' + id);
    if (card) card.classList.add('xdl-err');
};

window.xdlLoadHistory = function(records) {
    if (window.__xdl_hist_loaded__) return;
    window.__xdl_hist_loaded__ = true;
    if (!records || !records.length) return;

    var list = document.getElementById('__xdl_list__');
    var empty = document.getElementById('__xdl_empty__');
    if (empty) empty.style.display = 'none';

    records.forEach(function(r, i) {
        var hid = 'h_' + i;
        window.__xdl_paths__[hid] = r.path || '';

        var card = document.createElement('div');
        card.className = '__xdl_card__ xdl-done';

        var ttl = document.createElement('div');
        ttl.className = '__xdl_ttl__';
        ttl.style.color = '#64748b';
        ttl.textContent = r.title || '（历史记录）';
        card.appendChild(ttl);

        function mkHistBar(label) {
            var row = document.createElement('div');
            row.className = '__xdl_br__';
            row.innerHTML =
                '<span class="__xdl_lbl__">' + label + '</span>' +
                '<div class="__xdl_trk__"><div class="__xdl_fill__ xdl-done" style="width:100%"></div></div>' +
                '<span class="__xdl_pct__">100%</span>';
            return row;
        }
        card.appendChild(mkHistBar('下载'));
        card.appendChild(mkHistBar('转录'));

        var ft = document.createElement('div');
        ft.className = '__xdl_ft__';
        var st = document.createElement('span');
        st.className = '__xdl_st__';
        st.textContent = '✅ ' + (r.time || '');
        ft.appendChild(st);

        var ob = document.createElement('button');
        ob.className = '__xdl_ob__';
        ob.style.display = 'block';
        ob.textContent = '📄 打开文件';
        (function(hid_) {
            ob.addEventListener('click', function() {
                var p = window.__xdl_paths__[hid_];
                if (p && window.pywebview && window.pywebview.api)
                    window.pywebview.api.open_file_by_path(p);
            });
        })(hid);
        ft.appendChild(ob);
        card.appendChild(ft);
        list.appendChild(card);
    });

    var cnt = document.querySelectorAll('.__xdl_card__').length;
    var cntEl = document.getElementById('__xdl_cnt__');
    if (cntEl) cntEl.textContent = cnt + ' 项';
};

// ── fetch/XHR 钩子（页面级守卫，全页刷新后重新注入）─────────────────────
if (!window.__xdl_hooked__) {
    window.__xdl_hooked__ = true;

    function _extractUrl(data) {
        try {
            var lines = data.data;
            if (!lines || !lines.length) return null;
            var line = lines.find(function(l){ return l.default; }) || lines[0];
            var items = line.line_sharpness;
            if (!items || !items.length) return null;
            var item = items.find(function(i){ return i.default; }) || items[0];
            return item.url || null;
        } catch(e) { return null; }
    }

    function _onDetected(playUrl) {
        var btn = document.getElementById('__xdl_dl_btn__');
        if (!btn) {
            btn = document.createElement('div');
            btn.id = '__xdl_dl_btn__';
            document.body.appendChild(btn);
        }
        btn.textContent = '⬇ 下载转录';
        btn.style.background = '#16a34a';
        btn.style.display = 'block';
        btn.style.pointerEvents = 'auto';
        btn.onclick = function() {
            btn.textContent = '⏳ 已加入队列';
            btn.style.background = '#f59e0b';
            btn.style.pointerEvents = 'none';
            setTimeout(function() { btn.style.display = 'none'; }, 2500);
            function _tryCall(n) {
                if (window.pywebview && window.pywebview.api && window.pywebview.api.on_download) {
                    window.pywebview.api.on_download(playUrl, document.title || '');
                } else if (n > 0) {
                    setTimeout(function(){ _tryCall(n - 1); }, 300);
                }
            }
            _tryCall(20);
        };
    }

    var _origFetch = window.fetch;
    window.fetch = function() {
        var args = arguments;
        var url = (args[0] instanceof Request) ? args[0].url : String(args[0]);
        return _origFetch.apply(this, args).then(function(resp) {
            if (url.indexOf('get_lookback_list') !== -1) {
                resp.clone().json().then(function(data) {
                    var u = _extractUrl(data);
                    if (u) _onDetected(u);
                }).catch(function(){});
            }
            return resp;
        });
    };

    var _origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(m, url) {
        this.__xurl__ = url;
        return _origOpen.apply(this, arguments);
    };
    var _origSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function() {
        if (this.__xurl__ && this.__xurl__.indexOf('get_lookback_list') !== -1) {
            var xhr = this;
            xhr.addEventListener('load', function() {
                try {
                    var u = _extractUrl(JSON.parse(xhr.responseText));
                    if (u) _onDetected(u);
                } catch(e) {}
            });
        }
        return _origSend.apply(this, arguments);
    };
}

})();
"""


# ─────────────────────────────────────────────────────────────────────────────
# Python API（暴露给 JS 的方法）
# ─────────────────────────────────────────────────────────────────────────────
class _Api:
    def __init__(self):
        self._win = None
        self._output_dir = DEFAULT_OUTPUT

    def _eval(self, js: str):
        try:
            if self._win and self._win in webview.windows:
                self._win.evaluate_js(js)
        except Exception:
            pass

    # JS 调用：用户点击「⬇ 下载转录」
    def on_download(self, play_url: str, title: str):
        task_id = f"t{int(time.time() * 1000)}"
        clean = _safe_fn((title or "课程视频").strip())
        self._eval(f"xdlAddTask({json.dumps(task_id)}, {json.dumps(clean)})")
        threading.Thread(
            target=self._pipeline,
            args=(task_id, play_url, clean),
            daemon=True,
        ).start()

    # JS 调用：选择输出文件夹（使用 pywebview 原生对话框）
    def choose_folder(self) -> str:
        try:
            result = self._win.create_file_dialog(webview.FOLDER_DIALOG)
            if result:
                chosen = result[0] if isinstance(result, (list, tuple)) else result
                if chosen:
                    self._output_dir = chosen
        except Exception:
            pass
        return self._output_dir

    # JS 调用：input 失焦时同步路径
    def set_folder(self, path: str):
        if path and path.strip():
            self._output_dir = path.strip()

    # JS 调用：打开文件所在目录
    def open_file_by_path(self, path: str):
        import subprocess
        try:
            subprocess.Popen(f'explorer /select,"{path}"')
        except Exception:
            pass

    # 后台线程：下载 + 转录 + 生成 Markdown
    def _pipeline(self, task_id: str, play_url: str, title: str):
        def ev(js): self._eval(js)

        try:
            output_dir = Path(self._output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            from downloader import download_video
            _last = [-1]

            def on_dl(pct):
                ev(f"xdlUpdate({json.dumps(task_id)}, 'dl', {pct:.1f})")
                b = int(pct) // 10
                if b != _last[0]:
                    _last[0] = b

            mp4_path = download_video(play_url, output_dir / title, [], on_progress=on_dl)
            ev(f"xdlUpdate({json.dumps(task_id)}, 'dl', 100)")

            from transcriber import transcribe

            def on_seg(seg, pct):
                ev(f"xdlUpdate({json.dumps(task_id)}, 'tx', {pct:.1f})")

            segments = transcribe(mp4_path, on_segment=on_seg)
            ev(f"xdlUpdate({json.dumps(task_id)}, 'tx', 100)")

            from formatter import format_md
            md_path = format_md(title, segments, output_dir / f"{title}.md")

            ev(f"xdlDone({json.dumps(task_id)}, {json.dumps(str(md_path))})")
            _append_history(title, str(md_path))

        except Exception as e:
            ev(f"xdlError({json.dumps(task_id)}, {json.dumps(str(e))})")


# ─────────────────────────────────────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────────────────────────────────────
def browse_and_capture():
    """打开内嵌浏览器，运行直到用户关闭窗口。"""
    STORAGE_DIR.mkdir(exist_ok=True)
    api = _Api()

    win = webview.create_window(
        title="小鹅通转录工具",
        url=HOMEPAGE,
        js_api=api,
        width=1200,
        height=820,
        min_size=(900, 600),
    )
    api._win = win

    def inject_loop():
        time.sleep(1.5)
        history_sent = False
        while win in webview.windows:
            try:
                win.evaluate_js(_INJECT_JS)
                if not history_sent:
                    records = _load_history()
                    win.evaluate_js(
                        f"xdlLoadHistory({json.dumps(records, ensure_ascii=False)})"
                    )
                    win.evaluate_js(
                        f"xdlSetFolder({json.dumps(api._output_dir)})"
                    )
                    history_sent = True
            except Exception:
                history_sent = False  # 整页刷新后重置，下次循环重新发
            time.sleep(0.8)

    webview.start(inject_loop, storage_path=str(STORAGE_DIR), private_mode=False)
