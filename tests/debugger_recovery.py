"""A blocked or failed renderer must not hide the other debugger sections."""
from pathlib import Path
import tempfile
from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-debugger-recovery-') as directory:
    root = Path(directory)
    source = root / 'example.lua'
    source.write_text('local answer = 42\nprint(answer)\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert");'
                   'vim.api.nvim_buf_set_lines(0,1,2,false,{"print(answer + 1)"})', str(source))
        main = editor.lua('return require("config.ide").main_editor')
        document = editor.lua('return vim.api.nvim_win_get_buf(...)', main)
        editor.lua('_G.debug_errors={};local notify=vim.notify;vim.notify=function(message,...) '
                   '_G.debug_errors[#_G.debug_errors+1]=tostring(message);return notify(message,...) end')
        editor.lua('require("dap");local e=require("dapui").elements.scopes;'
                   '_G.debug_render=e.render;_G.debug_gate=require("nio").control.event();'
                   'e.render=function() _G.debug_gate.wait();return _G.debug_render() end;'
                   'require("config.debugger").show()')
        editor.wait(lambda: editor.lua('return require("config.debugger").is_open()'),
                    'Four panes mount even while Scopes waits for a DAP response')
        assert not editor.lua('return require("config.debugger").opening')
        assert editor.lua('return #require("config.debugger").wins') == 4
        editor.lua('_G.debug_gate.set();require("dapui").elements.scopes.render=_G.debug_render')

        # A renderer error must be reported while all four sections remain usable.
        editor.lua('require("config.ide").explorer()')
        editor.wait(lambda: not editor.lua('return require("config.debugger").is_open()'), 'Debug hidden')
        editor.lua('require("dapui").elements.scopes.render=function() error("test renderer failure") end;'
                   'require("config.debugger").show()')
        editor.wait(lambda: editor.lua('return require("config.debugger").is_open()'), 'Panes survive renderer error')
        editor.wait(lambda: 'test renderer failure' in editor.lua('return table.concat(_G.debug_errors,"\\n")'), 'Render error reported')
        assert not editor.lua('return require("config.debugger").opening')
        editor.lua('require("dapui").elements.scopes.render=_G.debug_render')

        # A late buffer lookup from an older visit cannot change the new layout.
        editor.lua('require("config.ide").explorer()')
        editor.wait(lambda: not editor.lua('return require("config.debugger").is_open()'), 'Debug hidden before delayed lookup')
        editor.lua('local e=require("dapui").elements.scopes;local buffer=e.buffer;'
                   '_G.debug_buffer_gate=require("nio").control.event();'
                   'e.buffer=function() e.buffer=buffer;_G.debug_buffer_gate.wait();return buffer() end;'
                   'require("config.debugger").show()')
        editor.wait(lambda: editor.lua('return require("config.debugger").opening'), 'Buffer lookup in progress')
        editor.lua('require("config.ide").explorer()')
        editor.wait(lambda: not editor.lua('return require("config.debugger").opening'), 'Switch cancels old mount')
        editor.lua('require("config.debugger").show()')
        editor.wait(lambda: editor.lua('return require("config.debugger").is_open()'), 'New Debug visit mounts')
        panes = editor.lua('return require("config.debugger").wins')
        editor.lua('_G.debug_buffer_gate.set();vim.wait(100)')
        assert editor.lua('return require("config.debugger").wins') == panes, 'Late callback preserves replacement panes'

        # Close an interior pane; checking only the first/last windows misses this.
        editor.lua('vim.api.nvim_win_close(require("config.debugger").wins[2],true);require("config.sidebar").schedule()')
        editor.wait(lambda: editor.lua('local d=require("config.debugger");if not d.is_open() then return false end;'
                                      'for _,w in ipairs(d.wins) do if not vim.api.nvim_win_is_valid(w) then return false end end;'
                                      'return #d.wins==4'), 'An incomplete set is rebuilt without duplicate panes')
        for _ in range(3):
            editor.lua('require("config.ide").explorer();require("config.debugger").show()')
            editor.wait(lambda: editor.lua('return require("config.debugger").is_open()'), 'Rapid Files/Debug return')
        assert editor.lua('return vim.api.nvim_win_get_buf(...)', main) == document
        assert editor.lua('return vim.bo[...].modified', document)
        assert editor.lua('local n=0;for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                          'if vim.bo[vim.api.nvim_win_get_buf(w)].filetype:match("^dapui_") then n=n+1 end end;return n') == 4
        print('PASS: Debug mounts while rendering waits, survives errors, rebuilds missing panes and repeated switches; unsaved document preserved', flush=True)
    finally:
        editor.close()
