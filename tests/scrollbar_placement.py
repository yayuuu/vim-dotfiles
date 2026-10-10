"""Horizontal bars remain directly below their source when bottom tools reopen."""
from pathlib import Path
import tempfile

from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-scrollbar-placement-') as directory:
    root = Path(directory)
    file = root / 'long.txt'
    file.write_text(('Long content ' * 35 + '\n') * 8)
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(file))
        main = editor.lua('return require("config.ide").editor_window()')
        buf = editor.call('nvim_win_get_buf', main)

        def bar():
            return editor.lua('local b=require("config.hscroll").bars[...];return b and vim.api.nvim_win_is_valid(b.win) and b.win', main)

        def attached():
            source = editor.call('nvim_win_get_position', main)
            scroll = editor.call('nvim_win_get_position', bar())
            terminal = editor.lua('return vim.api.nvim_win_get_position(require("config.terminals").win)')
            return scroll[1] == source[1] and source[0] < scroll[0] < terminal[0]

        editor.wait(bar, 'Long document has a scrollbar')
        editor.wait(attached, 'Initial scrollbar is between editor and terminal')
        original_bar = bar()
        job = editor.lua('return require("config.terminals").items[1].job')
        for _ in range(3):
            editor.lua('require("config.terminals").hide()')
            editor.lua('require("config.terminals").toggle({start_insert=false})')
            editor.wait(attached, 'Reopening terminal keeps the scrollbar directly below the editor')
            assert bar() == original_bar, 'Repair reuses the existing scrollbar window'
            assert editor.lua('return vim.api.nvim_get_current_win()') == main, 'Moving scrollbar preserves editor focus'
            assert editor.call('nvim_win_get_buf', main) == buf
            assert editor.lua('return require("config.terminals").items[1].job') == job, 'Terminal session survives'
        editor.lua('require("config.terminals").new({start_insert=false})')
        editor.wait(attached, 'New session leaves the scrollbar above terminals')
        editor.lua('require("config.problems").open()')
        editor.wait(lambda: editor.lua('local p=require("config.problems");return p.view and p.view.win and p.view.win:valid() and not p.suspended'), 'Problems replaces terminal')
        editor.wait(lambda: editor.lua('local b=require("config.hscroll").bars[...];local p=require("config.problems").view;'
                                      'return vim.api.nvim_win_get_position(b.win)[1]<vim.api.nvim_win_get_position(p.win.win)[1]', main), 'Scrollbar remains above Problems')
        editor.lua('require("config.problems").hide()')
        editor.wait(attached, 'Hide Problems restores terminal below scrollbar')
        editor.call('nvim_ui_try_resize', 128, 36)
        editor.wait(attached, 'Scrollbar stays above terminal after resize')
        # The repaired bar still scrolls the document.
        position = editor.call('nvim_win_get_position', bar())
        width = editor.call('nvim_win_get_width', bar())
        editor.click(position[0], position[1] + width - 1)
        editor.wait(lambda: editor.lua('return vim.api.nvim_win_call(...,vim.fn.winsaveview).leftcol>0', main), 'Repositioned scrollbar remains clickable')
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'Horizontal scrollbar:' not in messages and 'Invalid window id' not in messages, messages
        print('PASS: horizontal scrollbar stays between editor and bottom tools through terminal reopen, new sessions, Problems/Hide, and resize; focus, terminal session, and scrolling survive.')
    finally:
        editor.close()
