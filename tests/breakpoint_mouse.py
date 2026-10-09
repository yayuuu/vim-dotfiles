"""Actual gutter clicks toggle DAP on the clicked line, including scrolled diffs."""
from pathlib import Path
import subprocess
import tempfile

from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-breakpoint-mouse-') as directory:
    root = Path(directory)
    file = root / 'example.txt'
    file.write_text(''.join(f'Line {line}\n' for line in range(1, 101)))
    subprocess.run(['git', 'init', '-b', 'main', str(root)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=UI Test', '-c', 'user.email=ui@example.invalid', 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=UI Test', '-c', 'user.email=ui@example.invalid', 'commit', '-m', 'Baseline'], check=True, stdout=subprocess.DEVNULL)
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...)', str(file))
        editor.call('nvim_input', '\x1b')
        editor.wait(lambda: editor.lua('return vim.api.nvim_get_mode().mode') == 'n', 'Normal mode')
        win = editor.lua('return require("config.ide").editor_window()')
        buffer = editor.lua('return vim.api.nvim_win_get_buf(...)', win)
        editor.lua('require("config.debugger").show()')
        editor.wait(lambda: editor.lua('return require("config.debugger").is_open()'), 'Debug sidebar opens')

        def location(win, line, offset=0):
            return editor.lua('local w,l,offset=...;local p=vim.fn.screenpos(w,l,1);'
                              'local left=vim.api.nvim_win_get_position(w)[2];return {p.row-1,left+offset}', win, line, offset)

        def lines(buf):
            return editor.lua('local buf=...;local out={};for _,bp in ipairs(require("dap.breakpoints").get(buf)[buf] or {}) do out[#out+1]=bp.line end;table.sort(out);return out', buf)

        cursor = editor.lua('return vim.api.nvim_win_get_cursor(...)', win)
        editor.click(*location(win, 3))
        editor.wait(lambda: lines(buffer) == [3], 'Gutter adds clicked-line breakpoint')
        editor.wait(lambda: editor.lua('local w=require("config.debugger").wins[2];return '
                                      'table.concat(vim.api.nvim_buf_get_lines(vim.api.nvim_win_get_buf(w),0,-1,false),"\\n"):find("example.txt",1,true)~=nil'), 'Breakpoints pane updates before starting a debug session')
        assert editor.lua('return vim.api.nvim_win_get_cursor(...)', win) == cursor
        assert editor.lua('return #vim.fn.sign_getplaced(...,{group="dap_breakpoints"})[1].signs', buffer) == 1
        editor.click(*location(win, 3, 1))
        editor.wait(lambda: lines(buffer) == [], 'Second click removes breakpoint')
        editor.lua('vim.api.nvim_win_set_cursor(...,{60,0});vim.cmd("normal! zt");vim.cmd("redraw!")', win)
        cursor = editor.lua('return vim.api.nvim_win_get_cursor(...)', win)
        editor.click(*location(win, 65))
        editor.wait(lambda: lines(buffer) == [65], 'Scrolled gutter uses buffer line')
        assert editor.lua('return vim.api.nvim_win_get_cursor(...)', win) == cursor
        editor.click(*location(win, 66, 3))
        assert lines(buffer) == [65], 'Number column does not toggle breakpoints'
        editor.lua('vim.cmd("startinsert")')
        editor.click(*location(win, 65))
        editor.wait(lambda: lines(buffer) == [], 'Gutter removes breakpoint from Insert mode')
        assert editor.lua('return vim.api.nvim_get_mode().mode') == 'i'
        editor.lua('require("config.diff").open(...)', str(file))
        editor.call('nvim_input', '\x1b')
        right = editor.lua('return require("config.diff").active.right')
        proxy = editor.lua('return require("config.diff").active.buf')
        editor.lua('vim.api.nvim_win_set_cursor(...,{1,0});vim.cmd("normal! zt");vim.cmd("redraw!")', right)
        editor.click(*location(right, 4))
        editor.wait(lambda: lines(buffer) == [4], 'Diff gutter attaches breakpoint to real file')
        assert lines(proxy) == [], 'Proxy is not sent to the debugger as a source'
        assert editor.lua('return #vim.fn.sign_getplaced(...,{group="DesktopBreakpointMirror"})[1].signs', proxy) == 1
        left = editor.lua('return require("config.diff").active.left')
        editor.click(*location(left, 5))
        assert lines(buffer) == [4], 'Read-only HEAD does not add breakpoint'
        editor.click(*location(right, 4))
        editor.wait(lambda: lines(buffer) == [], 'Diff gutter removes real-file breakpoint')
        assert editor.lua('return #vim.fn.sign_getplaced(...,{group="DesktopBreakpointMirror"})[1].signs', proxy) == 0
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: gutter adds/removes real DAP breakpoints on clicked and scrolled lines; preserves cursor/Insert mode; number column and HEAD are excluded; diff uses real source with mirrored signs', flush=True)
    finally:
        editor.close()
