"""Clicking the editable diff body starts input and synchronizes the real file."""
from pathlib import Path
import subprocess
import tempfile

from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-diff-input-') as directory:
    root = Path(directory)
    file = root / 'example.lua'
    original = ['local a = 1', 'local b = 2', 'local c = 3']
    file.write_text('\n'.join(original) + '\n')
    subprocess.run(['git', 'init', '-b', 'main', str(root)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=UI Test', '-c',
                    'user.email=ui@example.invalid', 'commit', '-m', 'Baseline'],
                   check=True, stdout=subprocess.DEVNULL)
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.diff").open(...)', str(file))
        editor.call('nvim_input', '<Esc>')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Normal diff mode')
        active = editor.lua('local d=require("config.diff");return {right=d.active.right,left=d.active.left,'
                            'buf=d.active.buf,filebuf=d.entries[d.active.buf].filebuf,'
                            'before=d.entries[d.active.buf].before}')

        def location(win, line):
            return editor.lua('local w,l=...;local p=vim.fn.screenpos(w,l,1);return {p.row-1,p.col-1}', win, line)

        def lines(buf):
            return editor.lua('return vim.api.nvim_buf_get_lines(...,0,-1,false)', buf)

        editor.click(*location(active['right'], 1))
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Click in focused right editor starts input')
        editor.call('nvim_input', '-- first ')
        editor.wait(lambda: lines(active['filebuf'])[0] == '-- first ' + original[0], 'Typed changes reach real file')
        editor.call('nvim_input', '<Esc>')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Esc exits input')
        editor.click(*location(active['left'], 2))
        assert editor.lua('return vim.api.nvim_get_current_win()') == active['left']
        assert editor.lua('return vim.fn.mode()') == 'n', 'HEAD stays in Normal mode'
        editor.click(*location(active['right'], 2))
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Click from HEAD to right editor starts input')
        editor.call('nvim_input', '-- second ')
        editor.wait(lambda: lines(active['filebuf'])[1] == '-- second ' + original[1], 'Second edit reaches real file')
        assert lines(active['before']) == original, 'HEAD content is unchanged'
        print('PASS: right diff clicks start input from the same pane and from HEAD; typed edits synchronize to the real file.')
    finally:
        editor.close()
