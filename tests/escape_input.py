"""Esc dismisses transient UI first; only editor documents can leave input."""
from pathlib import Path
import subprocess
import tempfile
import time

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-escape-input-') as directory:
    root = Path(directory)
    path = root / 'example.txt'
    path.write_text('escape_candidate_one escape_candidate_two\nescape_\n')
    for args in [('init', '-b', 'main'), ('add', '.'), ('-c', 'user.name=UI Test',
                 '-c', 'user.email=ui@example.invalid', 'commit', '-m', 'Baseline')]:
        subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...)', str(path))
        main = editor.lua('return vim.api.nvim_get_current_win()')
        document = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.wait(lambda: editor.lua('return not require("config.sidebar").changing and not require("config.sidebar").updating'), 'Sidebar startup settles')

        def key(keys):
            editor.call('nvim_input', keys)
            time.sleep(.1)
            editor.lua('return true')

        def mode():
            return editor.lua('return vim.fn.mode()')

        def reopen():
            editor.lua('require("config.ide").open_file(nil,...)', document)
            editor.wait(lambda: mode() == 'i', 'Editor accepts input')

        # Use actual Blink UI with a deterministic buffer source, independent
        # of installed language servers and their response timing.
        editor.lua('local c=require("blink.cmp.config");c.completion.trigger.show_on_keyword=false;'
                   'c.completion.trigger.show_on_insert=false;vim.api.nvim_win_set_cursor(0,{2,7})')
        editor.lua('require("blink.cmp").show({providers={"buffer"}})')
        editor.wait(lambda: editor.lua('return require("blink.cmp").is_menu_visible()'), 'Real completion opens')
        before = editor.call('nvim_buf_get_lines', document, 0, -1, False)
        editor.lua('_G.escape_normal=0;local w=...;vim.api.nvim_create_autocmd("ModeChanged",{pattern="i*:n",'
                   'callback=function() if vim.api.nvim_get_current_win()==w then _G.escape_normal=_G.escape_normal+1 end end})', main)
        key('<Esc>')
        assert mode() == 'i' and not editor.lua('return require("blink.cmp").is_visible()')
        assert editor.lua('return _G.escape_normal') == 0, 'Dismissing completion never visits Normal'
        assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == before
        key('<Esc>')
        assert mode() == 'n', 'Only the next Esc leaves document input'
        key('i')

        # Native completion must cancel its preview, too.
        editor.lua('vim.fn.complete(vim.fn.col("."),{"native_one","native_two"})')
        editor.wait(lambda: editor.lua('return vim.fn.pumvisible()') == 1, 'Native completion opens')
        key('<Esc>')
        assert mode() == 'i' and editor.lua('return vim.fn.pumvisible()') == 0
        assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == before

        # Native LSP previews can be non-focusable and have no custom button.
        popup = editor.lua('local _,w=vim.lsp.util.open_floating_preview({"Example help"},"plaintext",'
                           '{focusable=false,focus=false,close_events={}});return w')
        key('<Esc>')
        assert mode() == 'i' and not editor.call('nvim_win_is_valid', popup)
        key('<Esc>')
        assert mode() == 'n'
        key('i')

        # Noice renders hover help separately from native LSP preview windows.
        editor.lua('require("noice.lsp.hover").on_hover(nil,{contents={kind="markdown",value="Escape hover fixture"}},{bufnr=...})', document)

        def hover_window():
            return editor.lua('for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                              'local b=vim.api.nvim_win_get_buf(w);local c=vim.api.nvim_win_get_config(w);'
                              'if c.relative~="" and not c.hide and vim.bo[b].filetype=="noice" '
                              'and table.concat(vim.api.nvim_buf_get_lines(b,0,-1,false)," "):find("Escape hover fixture",1,true) then return w end end')

        editor.wait(hover_window, 'Noice hover opens')
        key('<Esc>')
        editor.wait(lambda: not hover_window(), 'Esc closes Noice hover')
        assert mode() == 'i'

        key('<M-f>')
        editor.wait(lambda: editor.lua('return vim.b.ide_search_input and vim.fn.mode()=="i"'), 'Search input')
        key('needle<Esc><Esc>-more')
        assert mode() == 'i' and editor.call('nvim_get_current_line') == 'needle-more'
        assert editor.lua('return vim.b.ide_search_input')
        key('<M-a><Esc>')
        assert mode() == 'i' and not editor.lua('return require("config.panel_navigation").state~=nil')
        reopen()

        key('<M-r>')
        editor.wait(lambda: editor.lua('local s=require("config.sidebar").state();'
                                       'local f=s and require("config.git").inputs[s.path];return f and f.win'), 'Commit input exists')
        editor.lua('local s=require("config.sidebar").state();'
                   'vim.api.nvim_set_current_win(require("config.git").inputs[s.path].win);vim.cmd("startinsert!")')
        editor.wait(lambda: mode() == 'i', 'Commit input accepts typing')
        key('Draft<Esc><Esc> message')
        assert mode() == 'i' and editor.call('nvim_get_current_line') == 'Draft message'
        assert editor.lua('return vim.b.ide_git_input')
        key('<C-a>')
        assert mode() in ('s', 'S', '\x13')
        key('<Esc>')
        assert mode() == 'i', 'Esc ends a field selection without leaving input'
        reopen()

        editor.lua('require("config.terminals").show_debug_console()')
        editor.wait(lambda: mode() == 'i', 'Debug console prompt')
        key('40 + 2<Esc>')
        assert mode() == 'i' and editor.call('nvim_get_current_line').endswith('40 + 2')
        reopen()

        # Dialogs cancel immediately rather than switching their input to Normal.
        editor.lua('_G.escape_answer="pending";vim.ui.input({prompt="Name: "},function(v) _G.escape_answer=v or "canceled" end)')
        editor.wait(lambda: editor.lua('return vim.bo.filetype=="snacks_input" and vim.fn.mode()=="i"'), 'Text dialog')
        key('draft<Esc>')
        editor.wait(lambda: editor.lua('return _G.escape_answer') == 'canceled', 'Single Esc cancels text dialog')
        editor.wait(lambda: mode() == 'i' and editor.lua('return vim.api.nvim_get_current_win()') == main, 'Dialog returns to editor input')
        editor.lua('_G.escape_choice="pending";vim.ui.select({"First","Second"},{prompt="Choose"},function(v) _G.escape_choice=v or "canceled" end)')
        editor.wait(lambda: editor.lua('return vim.bo.filetype=="snacks_picker_input" and vim.fn.mode()=="i"'), 'Picker input')
        key('<Esc>')
        editor.wait(lambda: editor.lua('return _G.escape_choice') == 'canceled', 'Single Esc cancels picker')
        editor.wait(lambda: mode() == 'i', 'Picker returns to editor input')

        # The command line stays active when its completion is dismissed.
        key('<Esc>:q<Tab>')
        editor.wait(lambda: editor.lua('return require("blink.cmp").is_menu_visible()'), 'Command completion')
        key('<Esc>')
        assert mode() == 'c' and editor.lua('return vim.fn.getcmdtype()') == ':'
        assert not editor.lua('return require("blink.cmp").is_visible()')
        key('<Esc>')
        editor.wait(lambda: mode() == 'i' and editor.lua('return vim.fn.getcmdtype()') == '', 'Second Esc cancels command and resumes input')
        assert editor.call('nvim_win_is_valid', main), 'Canceled :q never runs'
        assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == before
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: real Blink/native completion and LSP previews dismiss before Normal; Search, commit and console '
              'retain input; field selections, Alt+A cancellation, dialogs, pickers and command completion/cancellation preserve input and text.')
    finally:
        editor.close()
