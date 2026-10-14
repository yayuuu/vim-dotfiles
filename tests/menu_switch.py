"""Toolbar headings toggle/switch once, without stale callbacks reopening menus."""
from pathlib import Path
import tempfile
import time

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-menu-switch-') as directory:
    root = Path(directory)
    editor = Editor(root, root/'state')
    try:
        editor.lua('vim.g.menu_test={opened=0,closed=0,wins={}};'
                   'vim.api.nvim_create_autocmd("FileType",{pattern="NvMenu",callback=function() local t=vim.g.menu_test;'
                   't.opened=t.opened+1;t.wins[tostring(vim.api.nvim_get_current_win())]=true;vim.g.menu_test=t end});'
                   'vim.api.nvim_create_autocmd("WinClosed",{callback=function(a)local t=vim.g.menu_test;'
                   'if t.wins[a.match] then t.closed=t.closed+1;t.wins[a.match]=nil;vim.g.menu_test=t end end})')
        expected_open, expected_close, previous = 0, 0, None
        for name in ('Edit','Edit','Edit','View','File','Edit','View','View','File','View','Edit',
                     'Terminal','Debug','Terminal','Debug','Help','Terminal','Debug','Debug'):
            editor.lua('vim.cmd("redraw!")')
            column = ''.join(editor.grid[0]).index(' '+name+' ')+2
            editor.click(0,column)
            if previous == name:
                expected_close += 1
                previous = None
            else:
                expected_open += 1
                if previous is not None: expected_close += 1
                previous = name
            editor.wait(lambda: editor.lua('return require("config.ide").menu_name') == previous, 'Toolbar toggle/switch completes')
            state = editor.lua('return vim.g.menu_test')
            assert (state['opened'],state['closed']) == (expected_open,expected_close), 'One transition per click, without flickering reopen'
            assert editor.lua('return #require("menu.state").bufids') == (1 if previous else 0)
        for width in (80, 100, 160, 240):
            editor.lua('require("config.ide").close_menu()')
            editor.call('nvim_ui_try_resize', width, 48)
            for name in ('Terminal', 'Debug', 'Terminal', 'Debug', 'Help', 'Terminal', 'Debug'):
                editor.lua('vim.cmd("redraw!")')
                column = ''.join(editor.grid[0]).index(' ' + name + ' ') + 2
                editor.click(0, column)
                editor.wait(lambda: editor.lua('return require("config.ide").menu_name') == name,
                            f'Switch to {name} at width {width}')
                time.sleep(.2)
                assert editor.lua('return require("config.ide").menu_name') == name, 'Replacement menu stays open'
                assert editor.lua('return #require("menu.state").bufids') == 1
        # Choosing an action still closes exactly once and creates a document.
        editor.click(0,3)
        editor.wait(lambda: editor.lua('return require("config.ide").menu_name') == 'File', 'Switch to File')
        pointer = editor.lua('local b=require("menu.state").bufids[1];local w=vim.fn.bufwinid(b);return vim.fn.screenpos(w,1,3)')
        editor.click(pointer['row']-1,pointer['col']-1)
        editor.wait(lambda: editor.lua('return #require("menu.state").bufids') == 0, 'New file action closes menu')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'New file action reaches Insert mode')
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'Error executing' not in messages and 'Invalid window id' not in messages, messages
        print('PASS: repeated toolbar switches and same-button toggles have one open/close per click; no stale callback closes/reopens the new menu; New file action works.')
    finally:
        editor.close()
