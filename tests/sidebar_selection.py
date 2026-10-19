"""Returning to Files during a selection must not leave an empty Symbols split."""
from pathlib import Path
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-sidebar-selection-') as directory:
    root = Path(directory)
    path = root / 'example.lua'
    path.write_text('local function example()\n  return true\nend\nreturn example()\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(path))
        main = editor.lua('return require("config.ide").editor_window()')
        document = editor.call('nvim_win_get_buf', main)
        editor.call('nvim_buf_set_lines', document, 1, 2, False, ['  return "Unsaved"'])
        contents = editor.call('nvim_buf_get_lines', document, 0, -1, False)
        terminal = editor.lua('return require("config.terminals").active')
        job = editor.lua('return require("config.terminals").items[1].job')
        editor.lua('require("config.terminals").show_debug_console(false);'
                   'require("dap.repl").append("Preserved console output");require("config.terminals").hide()')
        console = editor.lua('return require("config.terminals").console_buf')
        console_text = editor.call('nvim_buf_get_lines', console, 0, -1, False)
        editor.lua('local _,w=require("config.sidebar").state();vim.api.nvim_win_set_width(w,48)')

        def settle():
            editor.wait(lambda: not editor.lua('local s=require("config.sidebar");local l=require("config.layout");'
                                               'return s.changing or s.pending or s.updating or l.scaling'),
                        'Sidebar settles')

        def native_windows():
            return editor.lua('local r={};for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                              'if vim.api.nvim_win_get_config(w).relative=="" then '
                              'r[#r+1]={win=w,ft=vim.bo[vim.api.nvim_win_get_buf(w)].filetype} end end;return r')

        def source(name):
            editor.lua('require("neo-tree.command").execute({source=...,action="show"})', name)
            settle()

        def click_source(label):
            editor.lua('vim.cmd("redraw!")')
            row, left, width = editor.lua('local _,w=require("config.sidebar").state();'
                                         'local p=vim.api.nvim_win_get_position(w);'
                                         'return {p[1],p[2],vim.api.nvim_win_get_width(w)}')
            bar = ''.join(editor.grid[row][left:left + width])
            assert label in bar, bar
            editor.click(row, left + bar.index(label) + 1)
            settle()

        def select(mode):
            editor.call('nvim_input', '<Esc>')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Normal before selection')
            editor.lua('vim.api.nvim_set_current_win((...));vim.cmd("stopinsert");'
                       'vim.cmd.normal({args={"gg0"..select(2,...).."jl"},bang=true});'
                       'if select(3,...) then vim.cmd.normal({args={vim.keycode("<C-g>")},bang=true}) end',
                       main, {'v': 'v', 'V': 'V', '\x16': '\x16', 's': 'v', 'S': 'V', '\x13': '\x16'}[mode],
                       mode in ('s', 'S', '\x13'))
            assert editor.lua('return vim.fn.mode()') == mode

        def check_documents():
            assert editor.call('nvim_win_get_buf', main) == document
            assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == contents
            assert editor.call('nvim_get_option_value', 'modified', {'buf': document})
            assert editor.lua('local t=require("config.terminals");return not t.win and not t.list_win '
                              'and #t.items==1 and t.active==... and t.items[1].job==select(2,...)', terminal, job)
            assert editor.lua('return vim.fn.jobwait({...},0)[1]', job) == -1
            assert editor.call('nvim_buf_get_lines', console, 0, -1, False) == console_text

        for mode in ('v', 'V', '\x16', 's', 'S', '\x13'):
            source('buffers')
            select(mode)
            selection = editor.lua('return {vim.fn.getpos("v"),vim.fn.getpos(".")}')
            source('filesystem')
            # The whole construction waits, so even before Escape there must
            # be no anonymous placeholder split or disturbed selection.
            windows = native_windows()
            assert len(windows) == 2, ('No split while selecting', mode, windows)
            assert editor.lua('return vim.fn.mode()') == mode
            assert editor.lua('return {vim.fn.getpos("v"),vim.fn.getpos(".")}') == selection
            editor.lua('require("config.ide").outline();require("config.sidebar").schedule()')
            settle()
            assert len(native_windows()) == 2, 'Repeated refresh cannot allocate placeholders'
            editor.call('nvim_input', '<Esc>')
            editor.wait(lambda: any(w['ft'] == 'aerial' for w in native_windows()), 'Symbols appears after selection')
            settle()
            windows = native_windows()
            assert sorted(w['ft'] for w in windows) == ['aerial', 'lua', 'neo-tree'], windows
            check_documents()

        # Exercise actual source-selector gestures as well as preserved editor
        # selections during programmatic/background updates.
        for mode in ('v', 's'):
            source('buffers')
            select(mode)
            click_source('Files')
            editor.call('nvim_input', '<Esc>')
            editor.wait(lambda: any(w['ft'] == 'aerial' for w in native_windows()), 'Mouse return to Files')
            settle()
            assert sorted(w['ft'] for w in native_windows()) == ['aerial', 'lua', 'neo-tree']
            check_documents()
        for label, panes in (('Projects', 2), ('Search', 2), ('Debug', 6), ('Git', 3), ('Tabs', 2), ('Files', 3)):
            click_source(label)
            editor.wait(lambda: len(native_windows()) == panes, label + ' replaces the whole sidebar')
            check_documents()

        # A callback from a previous Files visit must not add Symbols to Tabs.
        source('buffers')
        select('v')
        source('filesystem')
        source('buffers')
        editor.call('nvim_input', '<Esc>')
        settle()
        assert sorted(w['ft'] for w in native_windows()) == ['lua', 'neo-tree']
        check_documents()
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'Error executing' not in messages and 'stack traceback' not in messages, messages
        print('PASS: Files during all six selection modes defers Symbols without empty or duplicate splits; '
              'canceled visits, unsaved text, hidden terminal job and console output are preserved.')
    finally:
        editor.close()
