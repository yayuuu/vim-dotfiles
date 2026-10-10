"""Returning to editable documents starts input without undoing explicit Escape."""
from pathlib import Path
import subprocess
import tempfile
import time

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-editor-focus-') as directory:
    root = Path(directory)
    first, second = root / 'first.txt', root / 'second.txt'
    first.write_text('First document\nSecond line\n')
    second.write_text('Second document\n')
    subprocess.run(['git', 'init', '-b', 'main', str(root)], check=True, stdout=subprocess.DEVNULL)
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...)', str(first))
        main = editor.lua('return require("config.ide").editor_window()')
        firstbuf = editor.call('nvim_win_get_buf', main)
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Opening starts Insert')

        def normal():
            editor.call('nvim_input', '<Esc>')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Esc enters Normal')
            time.sleep(.3)
            assert editor.lua('return vim.fn.mode()') == 'n', 'Render/focus restoration must not undo Escape'

        def click_editor():
            position = editor.lua('local w=require("config.ide").editor_window();local p=vim.fn.screenpos(w,1,1);return {p.row-1,p.col+1}')
            editor.click(*position)
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Returning to editor starts Insert')

        def click_tab(buf):
            def position():
                return editor.lua('local t=require("config.editor_tabs");if not t.win then return end;local p=vim.api.nvim_win_get_position(t.win);'
                                  'for _,h in ipairs(t.hits or {}) do if h.id==... and not h.close then return {p[1],p[2]+h.first} end end', buf)
            editor.wait(position, 'Document tab rendered')
            editor.click(*position())
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Selecting document tab starts Insert')

        normal()
        editor.lua('require("config.ide").explorer()')
        click_editor()
        assert editor.call('nvim_win_get_buf', main) == firstbuf, 'Same buffer still enters Insert'
        normal()
        editor.lua('require("config.ide").explorer()')
        click_tab(firstbuf)
        editor.lua('local t=require("config.terminals");vim.api.nvim_set_current_win(t.win);vim.cmd("startinsert")')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Terminal input active')
        click_editor()
        normal()
        editor.lua('local t=require("config.terminals");vim.api.nvim_set_current_win(t.win);vim.cmd("startinsert")')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Terminal input active again')
        click_tab(firstbuf)

        # Buffer changes in the same window (keyboard cycling) also enable input.
        editor.lua('require("config.ide").open_file(...)', str(second))
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Second file starts Insert')
        normal()
        editor.call('nvim_input', '<C-Tab>')
        editor.wait(lambda: editor.call('nvim_win_get_buf', main) == firstbuf and editor.lua('return vim.fn.mode()') == 'i', 'Keyboard tab cycling starts Insert')

        editor.lua('require("config.diff").open(...)', str(first))
        proxy = editor.lua('return require("config.diff").active.buf')
        normal()
        editor.lua('require("config.ide").explorer()')
        click_tab(proxy)
        editor.lua('local t=require("config.terminals");vim.api.nvim_set_current_win(t.win);vim.cmd("startinsert")')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Terminal beside diff')
        click_editor()
        normal()
        left = editor.lua('return require("config.diff").active.left')
        position = editor.lua('local p=vim.api.nvim_win_get_position(...);return {p[1],p[2]+8}', left)
        editor.click(*position)
        time.sleep(.2)
        assert editor.lua('return vim.fn.mode()') == 'n', 'Read-only HEAD stays Normal'
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: Files/terminal to same editor or tab, keyboard cycling, editable diff; Escape persists and HEAD stays Normal.')
    finally:
        editor.close()
