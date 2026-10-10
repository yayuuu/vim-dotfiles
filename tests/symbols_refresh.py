"""Symbols follows opened documents while Files retains keyboard focus."""
from pathlib import Path
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-symbols-refresh-') as directory:
    root = Path(directory)
    files = [root / name for name in ('first.lua', 'second.lua', 'third.lua')]
    for path, name in zip(files, ('first_symbol', 'second_symbol', 'third_symbol')):
        path.write_text('local function ' + name + '()\n  return true\nend\nreturn ' + name + '()\n')
    plain = root / 'plain.txt'
    plain.write_text('No functions here\n')
    editor = Editor(root, root / 'state')
    try:
        def outline():
            return editor.lua('for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                              'if vim.bo[vim.api.nvim_win_get_buf(w)].filetype=="aerial" then return w end end')

        editor.wait(outline, 'Symbols window exists')
        symbols = outline()
        geometry = editor.call('nvim_win_get_height', symbols)

        def check(name):
            def follows():
                return editor.lua('local w=...;local b=vim.api.nvim_win_get_buf(w);'
                                  'return vim.b[b].source_buffer==vim.api.nvim_win_get_buf(require("config.ide").editor_window()) '
                                  'and table.concat(vim.api.nvim_buf_get_lines(b,0,-1,false),string.char(10)):find(select(2,...),1,true)~=nil', symbols, name)
            editor.wait(follows, 'Symbols updates to ' + name + ' without entering the editor')
            assert editor.lua('return vim.bo.filetype=="neo-tree" and vim.fn.mode()=="n"'), 'Files retains input'
            assert outline() == symbols, 'Existing Symbols window is reused'
            assert editor.call('nvim_win_get_height', symbols) == geometry, 'Panel height is preserved'

        def click(path):
            position = editor.lua('local s=require("config.sidebar").state();local _,line=s.tree:get_node(...);'
                                  'local p=vim.fn.screenpos(s.winid,line,1);local x=vim.api.nvim_win_get_position(s.winid);'
                                  'return {p.row-1,x[2]+8}', str(path))
            editor.click(*position)

        editor.lua('require("config.ide").explorer()')
        click(files[0])
        check('first_symbol')
        firstbuf = editor.lua('return vim.api.nvim_win_get_buf(require("config.ide").editor_window())')
        editor.call('nvim_buf_set_lines', firstbuf, 1, 2, False, ['  return "Unsaved"'])
        click(files[1])
        check('second_symbol')
        click(files[2])
        check('third_symbol')
        click(files[0])
        check('first_symbol')
        assert editor.call('nvim_buf_get_lines', firstbuf, 1, 2, False) == ['  return "Unsaved"']
        click(plain)
        check('No symbols')
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: Symbols updates on first/cached file clicks without editor focus; latest document and No symbols are shown; focus, window size and unsaved text preserved.')
    finally:
        editor.close()
