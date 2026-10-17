"""Files and menu actions preserve editor/terminal geometry during construction."""
from pathlib import Path
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-ui-stability-') as directory:
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
        terminal = editor.lua('return require("config.terminals").win')
        terminal_buf = editor.call('nvim_win_get_buf', terminal)
        editor.lua('local wins={...};_G.DesktopStabilitySample=function() '
                   'local r={};for _,w in ipairs(wins) do '
                   'r[#r+1]={vim.api.nvim_win_get_position(w),vim.api.nvim_win_get_width(w),vim.api.nvim_win_get_height(w)} end;return r end', main, terminal)
        editor.lua('vim.api.nvim_create_autocmd({"WinNew","WinEnter","WinResized","FileType"},{callback=function() '
                   'if vim.g.stability_recording then local r=vim.g.stability_frames;'
                   'r[#r+1]=DesktopStabilitySample();vim.g.stability_frames=r end end})')

        def settle():
            editor.wait(lambda: not editor.lua('local s=require("config.sidebar");local l=require("config.layout");'
                                               'return s.changing or s.pending or s.updating or l.scaling'),
                        'Sidebar construction settles')

        def tab(name):
            editor.lua('vim.cmd("stopinsert");vim.cmd("redraw!")')
            row, left, width = editor.lua('local _,w=require("config.sidebar").state();local p=vim.api.nvim_win_get_position(w);'
                                         'return {p[1],p[2],vim.api.nvim_win_get_width(w)}')
            text = ''.join(editor.grid[row][left:left + width])
            assert name in text, (name, text, row, left, width)
            editor.click(row, left + text.index(name) + 1)
            settle()

        def start():
            editor.lua('vim.g.stability_frames={};vim.g.stability_recording=true')
            return editor.lua('return DesktopStabilitySample()')

        def check(expected):
            editor.lua('vim.g.stability_recording=false')
            frames = editor.lua('return vim.g.stability_frames')
            assert frames, 'Construction events were observed'
            assert all(frame == expected for frame in frames), ('Transient workspace resize', expected, frames)
            assert editor.lua('return DesktopStabilitySample()') == expected
            assert editor.call('nvim_win_get_buf', main) == document
            actual = editor.call('nvim_win_get_buf', terminal)
            assert actual == terminal_buf, (actual, terminal_buf)
            assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == contents
            assert editor.call('nvim_get_option_value', 'modified', {'buf': document})

        settle()
        editor.lua('local _,w=require("config.sidebar").state();vim.api.nvim_win_set_width(w,55)')
        editor.wait(lambda: editor.lua('return require("config.layout").sizes.tree') == 55, 'Sidebar width is remembered')
        for source in ('Projects', 'Git', 'Search', 'Debug', 'Tabs'):
            tab(source)
            expected = start()
            tab('Files')
            check(expected)
            assert editor.lua('return require("config.sidebar").symbols_enabled() and require("aerial").is_open()')

        # Use the real menu click path while returning to Files. Count queued
        # dismissal keys as they can run a nested input loop before the action.
        tab('Projects')
        editor.lua('vim.g.stability_keys={};local feed=vim.api.nvim_feedkeys;'
                   'vim.api.nvim_feedkeys=function(keys,mode,escape) '
                   'local r=vim.g.stability_keys;r[#r+1]=keys;vim.g.stability_keys=r;return feed(keys,mode,escape) end')
        expected = start()
        editor.lua('vim.cmd("redraw!")')
        editor.click(0, ''.join(editor.grid[0]).index(' View ') + 2)
        pointer = editor.lua('local b=require("menu.state").bufids[1];return vim.fn.screenpos(vim.fn.bufwinid(b),1,3)')
        editor.click(pointer['row'] - 1, pointer['col'] - 1)
        settle()
        check(expected)
        assert editor.lua('return require("config.sidebar").symbols_enabled() and #require("menu.state").bufids==0')
        assert 'q' not in editor.lua('return vim.g.stability_keys'), 'Mouse menu dismissal must not inject q'
        previous_wrap = editor.call('nvim_get_option_value', 'wrap', {'win': main})
        editor.click(0, ''.join(editor.grid[0]).index(' View ') + 2)
        editor.call('nvim_input', '<Down>' * 8 + '<CR>')
        editor.wait(lambda: editor.call('nvim_get_option_value', 'wrap', {'win': main}) != previous_wrap,
                    'Enter executes Toggle word wrap')
        assert editor.lua('return #require("menu.state").bufids') == 0
        assert 'q' not in editor.lua('return vim.g.stability_keys'), 'Keyboard menu dismissal must not inject q'
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'Error executing' not in messages and 'Invalid window id' not in messages, messages
        print('PASS: Files construction and View > Project files keep editor/terminal geometry stable throughout events; '
              'menu dismissal injects no keys; unsaved text and terminal session survive.')
    finally:
        editor.close()
