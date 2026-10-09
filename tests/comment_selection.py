"""Ctrl+Q toggles selected lines and the current line through actual keyboard input."""
import tempfile
from pathlib import Path
from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-comment-selection-') as directory:
    root = Path(directory)
    path = root / 'sample.lua'
    original = ['local a = 1', 'local b = 2', 'local c = 3', 'local d = 4']
    path.write_text('\n'.join(original) + '\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(path))
        def contents():
            return editor.lua('return vim.api.nvim_buf_get_lines(0,0,-1,false)')
        def keys(sequence):
            editor.call('nvim_input', sequence)
        for mode in ['select', 'visual']:
            editor.lua('vim.cmd("stopinsert");vim.api.nvim_win_set_cursor(0,{1,0})')
            keys('<S-Down><S-End>')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 's', 'Shift selection')
            if mode == 'visual':
                editor.lua('vim.api.nvim_feedkeys(vim.keycode("<C-g>"),"nx",false)')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == ('s' if mode == 'select' else 'v'), mode)
            keys('<C-q>')
            editor.wait(lambda: contents()[:2] == ['-- local a = 1', '-- local b = 2'], mode + ' comments selected lines')
            assert contents()[2:] == original[2:], contents()
            editor.lua('vim.api.nvim_win_set_cursor(0,{1,0})')
            keys('<S-Down><S-End>')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 's', 'Shift selection')
            if mode == 'visual':
                editor.lua('vim.api.nvim_feedkeys(vim.keycode("<C-g>"),"nx",false)')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == ('s' if mode == 'select' else 'v'), mode)
            keys('<C-q>')
            editor.wait(lambda: contents() == original, mode + ' uncomments selected lines')
        editor.lua('vim.api.nvim_win_set_cursor(0,{3,0})')
        keys('<C-q>')
        editor.wait(lambda: contents()[2] == '-- local c = 3', 'normal comments current line')
        assert contents()[:2] == original[:2] and contents()[3:] == original[3:]
        keys('<C-q>')
        editor.wait(lambda: contents() == original, 'normal uncomments current line')
        editor.lua('vim.api.nvim_win_set_cursor(0,{1,0});vim.cmd("startinsert")')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'insert')
        keys('<C-q>')
        editor.wait(lambda: contents()[0] == '-- local a = 1', 'insert comments current line')
        print('PASS: Ctrl+Q toggles selected lines in Select and Visual modes, and the current line in Normal and Insert modes.')
    finally:
        editor.close()
