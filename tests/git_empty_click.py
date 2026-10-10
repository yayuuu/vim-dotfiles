"""Whitespace below Git Status must not act on its last file or selection."""
from pathlib import Path
import subprocess
import tempfile
import time

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-git-empty-click-') as directory:
    root = Path(directory)
    file, document = root / 'last.txt', root / 'document.txt'
    file.write_text('Changed file\n')
    document.write_text('Editor content\n')
    subprocess.run(['git', 'init', '-b', 'main', str(root)], check=True, stdout=subprocess.DEVNULL)
    editor = Editor(root, root / 'state')
    try:
        editor.lua('vim.g.ide_git_autofetch=false;require("config.ide").open_file(...)', str(document))
        buf = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.call('nvim_buf_set_lines', buf, 0, -1, False, ['Unsaved editor'])
        editor.lua('require("config.ide").git_explorer()')
        editor.wait(lambda: editor.lua('local s=require("config.sidebar").state();return s and s.tree and s.tree:get_node(...)~=nil', str(file)), 'Changed file in Git Status')

        def blank():
            return editor.lua('local s=require("config.sidebar").state();local count=vim.api.nvim_buf_line_count(s.bufnr);'
                              'local p=vim.fn.screenpos(s.winid,count,1);local x=vim.api.nvim_win_get_position(s.winid);'
                              'return {p.row,x[2]+8}',)

        def unchanged():
            assert not editor.lua('return require("config.diff").active~=nil'), 'Empty click must not open a diff'
            assert editor.call('nvim_buf_get_lines', buf, 0, -1, False) == ['Unsaved editor']

        for modifier in ('', '2', 'S', 'C'):
            row, column = blank()
            for extra in (0, 3):
                editor.call('nvim_input_mouse', 'left', 'press', modifier, 0, row+extra, column)
                editor.lua('vim.cmd("redraw!")')
                editor.call('nvim_input_mouse', 'left', 'release', modifier if modifier in ('S', 'C') else '', 0, row+extra, column)
                time.sleep(.15)
                unchanged()

        # Real rows remain clickable. Returning to an ordinary file then clicking
        # below the selected final row must not reopen that cached comparison.
        position = editor.lua('local s=require("config.sidebar").state();local _,l=s.tree:get_node(...);'
                              'local p=vim.fn.screenpos(s.winid,l,1);local x=vim.api.nvim_win_get_position(s.winid);return {p.row-1,x[2]+8}', str(file))
        editor.click(*position)
        editor.wait(lambda: editor.lua('return require("config.diff").active~=nil'), 'Clicking file opens its diff')
        editor.lua('require("config.ide").open_file(nil,...)', buf)
        editor.click(*blank())
        unchanged()
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: empty Git Status clicks below EOF (plain/repeated/Shift/Ctrl) do nothing; actual file rows and unsaved editor remain intact.')
    finally:
        editor.close()
