"""The terminal list uses Normal mode; first/repeated console selection never adds splits."""
from pathlib import Path
import tempfile
import time

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-terminal-navigation-') as directory:
    root = Path(directory)
    path = root / 'document.txt'
    path.write_text('Preserved document\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...)', str(path))
        main = editor.lua('return require("config.ide").editor_window()')
        document = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.call('nvim_buf_set_lines', document, 0, -1, False, ['Unsaved document'])
        terminal, sessions = editor.lua('local t=require("config.terminals");return {t.win,t.list_win}')
        editor.call('nvim_win_set_height', terminal, 9)
        editor.wait(lambda: editor.lua('return require("config.layout").sizes.terminal') == 9, 'Remember chosen terminal height')

        def key(keys):
            editor.call('nvim_input', keys)
            time.sleep(.1)
            editor.lua('return true')

        def geometry():
            return editor.lua('local r={};for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                              'if vim.api.nvim_win_get_config(w).relative=="" then '
                              'r[tostring(w)]={vim.api.nvim_win_get_position(w),vim.api.nvim_win_get_width(w),'
                              'vim.api.nvim_win_get_height(w)} end end;return r')

        def select_sessions():
            editor.lua('vim.api.nvim_set_current_win(...);vim.cmd("startinsert")', main)
            key('<M-a><M-a><Down><Right><CR>')
            assert editor.lua('return vim.api.nvim_get_current_win()') == sessions
            assert editor.lua('return vim.fn.mode()') == 'n'
            key('i')
            assert editor.lua('return vim.fn.mode()') == 'n', 'Session list remains Normal'

        select_sessions()
        before = geometry()
        # Observe transient constructors as well as final dimensions: restoring
        # the layout after a temporary REPL split still produces visible flicker.
        editor.lua('_G.console_new_windows={};vim.api.nvim_create_autocmd("WinNew",{callback=function() '
                   'local w=vim.api.nvim_get_current_win();if vim.api.nvim_win_get_config(w).relative=="" then '
                   'table.insert(_G.console_new_windows,w) end end})')
        for visit in range(2):
            editor.lua('local t=require("config.terminals");vim.api.nvim_win_set_cursor(t.list_win,{t.console_row,0})')
            key('<CR>')
            editor.wait(lambda: editor.lua('return require("config.terminals").console_active and vim.fn.mode()=="i"'), 'Console prompt accepts input')
            assert geometry() == before, 'Console selection preserves native geometry'
            assert editor.lua('return _G.console_new_windows') == [], 'Console creates no temporary native split'
            assert editor.lua('return require("config.layout").sizes.terminal') == 9
            if visit == 0:
                editor.lua('require("config.terminals").show(require("config.terminals").active)')
                select_sessions()

        editor.lua('require("config.terminals").show(require("config.terminals").active)')
        key('<M-a><Right><CR>')
        assert editor.lua('return vim.api.nvim_get_current_win()') == sessions
        assert editor.lua('return vim.fn.mode()') == 'n', 'Terminal input to session list exits input mode'
        point = editor.lua('local t=require("config.terminals");local p=vim.fn.screenpos(t.list_win,t.console_row,1);'
                           'return {p.row-1,p.col+4}')
        editor.click(*point)
        assert editor.lua('return require("config.terminals").console_active and vim.fn.mode()=="i"')
        assert geometry() == before
        assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == ['Unsaved document']
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'Error executing' not in messages and 'E21:' not in messages and 'stack traceback' not in messages, messages
        print('PASS: editor/terminal keyboard selection keeps Terminals Normal; first/repeated/mouse console selection '
              'preserves all panel dimensions, saved height, terminal sessions and unsaved documents without temporary splits.')
    finally:
        editor.close()
