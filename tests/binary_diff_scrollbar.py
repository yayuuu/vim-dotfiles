"""Binary HEAD content cannot break horizontal bars or later text diffs."""
from pathlib import Path
import py_compile
import subprocess
import tempfile

from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-binary-diff-scroll-') as directory:
    root = Path(directory)
    source = root / 'example.py'
    source.write_text('payload = ' + repr('compiled content ' * 40) + '\nprint(payload)\n')
    binary = root / 'example.pyc'
    py_compile.compile(str(source), cfile=str(binary), doraise=True)
    subprocess.run(['git', 'init', '-b', 'main', str(root)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=UI Test', '-c', 'user.email=ui@example.invalid',
                    'commit', '-m', 'Binary fixture'], check=True, stdout=subprocess.DEVNULL)
    binary.unlink()
    text = root / 'AGENTS.md'
    text.write_text('# Instructions\n\n' + 'Long document line ' * 30 + '\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.diff").open(...)', str(binary))
        active = editor.lua('local d=require("config.diff").active;return {left=d.left,right=d.right,buf=d.buf}')
        editor.lua('local w=...;_G.binary_head_lines=vim.api.nvim_buf_get_lines(vim.api.nvim_win_get_buf(w),0,-1,false)', active['left'])
        assert editor.lua('for _,line in ipairs(_G.binary_head_lines) do if line:find("%z") then return true end end;return false'), 'Real pyc fixture contains NUL bytes'
        # Measuring the real binary buffer used to raise E976 (Blob as String).
        assert editor.lua('return require("config.hscroll").bounds(...)', active['left']) > 0
        def bars_ready():
            return editor.lua('local d=require("config.diff").active;local h=require("config.hscroll");'
                              'local l,r=h.bars[d.left],h.bars[d.right];return l and r and '
                              'vim.api.nvim_win_is_valid(l.win) and vim.api.nvim_win_is_valid(r.win) and not h.running')
        editor.wait(bars_ready, 'Binary diff has both horizontal bars')
        editor.lua('require("config.hscroll").set(...,20)', active['left'])
        editor.wait(lambda: editor.lua('local d=require("config.diff").active;local h=require("config.hscroll");'
                                      'local l=vim.api.nvim_win_call(d.left,vim.fn.winsaveview).leftcol;'
                                      'local r=vim.api.nvim_win_call(d.right,vim.fn.winsaveview).leftcol;'
                                      'return l>0 and l==r and not h.syncing'), 'Binary scrolling stays synchronized without a stuck guard')
        assert editor.lua('return vim.deep_equal(_G.binary_head_lines,vim.api.nvim_buf_get_lines(vim.api.nvim_win_get_buf(...),0,-1,false))', active['left']), 'Width measurement preserves raw HEAD content'
        editor.lua('require("config.diff").open(...)', str(text))
        editor.wait(bars_ready, 'Text diff still has horizontal bars after binary diff')
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'E976' not in messages and 'Horizontal scrollbar:' not in messages, messages
        assert not editor.lua('return require("config.diff").busy or require("config.hscroll").running or require("config.hscroll").syncing')
        print('PASS: real pyc HEAD width/scrolling handles NUL without E976, preserves binary content, and leaves Markdown diff bars working.')
    finally:
        editor.close()
