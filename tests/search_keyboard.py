"""Search field/results use Insert/Normal, spatial focus and a shared Shift+Tab mode switch."""
from pathlib import Path
import tempfile
import time

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-search-keyboard-') as directory:
    root = Path(directory)
    first, second = root / 'alpha.txt', root / 'needle-file.txt'
    first.write_text('needle first\nbetween\nneedle second\n')
    second.write_text('needle third\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...)', str(first))
        document = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.call('nvim_buf_set_lines', document, 3, 3, False, ['Unsaved notes'])
        saved_lines = editor.call('nvim_buf_get_lines', document, 0, -1, False)
        terminal = editor.lua('return require("config.terminals").active')

        def key(keys):
            editor.call('nvim_input', keys)
            time.sleep(.08)
            editor.lua('return true')

        def session():
            return editor.lua('local s=require("config.project_search").sessions[require("config.ide").root()];'
                              'return {query=s.query,mode=s.mode,count=s.count,busy=s.busy or false,dirty=s.dirty}')

        def settled(mode, query, count):
            editor.wait(lambda: session() == dict(mode=mode, query=query, count=count, busy=False, dirty=False), 'Search results: '+mode+' / '+query)

        def field():
            return editor.lua('return require("config.project_search").header.input')

        def selected():
            return editor.lua('local s=require("config.sidebar").state();local n=s.tree:get_node();'
                              'return {type=n.type,path=n.path,line=n.extra and n.extra.line}')

        def normal_results():
            assert editor.lua('return vim.fn.mode()') == 'n'
            assert editor.lua('return vim.o.guicursor') == 'a:DesktopPanelCursor'
            assert editor.lua('return vim.wo.cursorline and vim.wo.cursorlineopt=="both"')

        def geometry():
            return editor.lua('local r={};for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                              'if vim.api.nvim_win_get_config(w).relative=="" then '
                              'r[tostring(w)]={vim.api.nvim_win_get_position(w),vim.api.nvim_win_get_width(w),'
                              'vim.api.nvim_win_get_height(w)} end end;return r')

        key('<M-f>')
        editor.wait(lambda: editor.lua('return vim.b.ide_search_input and vim.fn.mode()=="i"'), 'Search input accepts typing')
        results = editor.lua('return require("config.project_search").header.source')
        key('needle')
        settled('content', 'needle', 3)
        key('<Down>')
        assert editor.lua('return vim.api.nvim_get_current_win()') == results
        normal_results()
        assert selected()['type'] == 'search_file' and selected()['path'] == str(first)
        point = editor.lua('local w=...;local p=vim.fn.screenpos(w,vim.api.nvim_win_get_cursor(w)[1],1);'
                           'return {p.row-1,p.col-1+vim.api.nvim_win_get_width(w)-2}', results)
        wanted = editor.lua('return vim.api.nvim_get_hl(0,{name="NeoTreeCursorLine",link=false}).bg')
        assert editor.highlights[editor.attributes[point[0]][point[1]]]['background'] == wanted, 'Selection extends to the row edge'
        key('<Down>')
        assert selected()['type'] == 'search_match' and selected()['line'] == 1
        key('<Down>')
        assert selected()['line'] == 3
        column = editor.call('nvim_win_get_cursor', results)[1]
        key('<Left><Right>')
        assert editor.call('nvim_win_get_cursor', results)[1] == column
        key('<S-Tab>')
        settled('files', 'needle', 1)
        assert editor.lua('return vim.api.nvim_get_current_win()') == results
        normal_results()
        key('<Down>')
        assert selected()['type'] == 'search_file' and selected()['path'] == str(second)
        key('<S-Tab>')
        settled('content', 'needle', 3)
        key('<Up>')
        assert editor.lua('return vim.api.nvim_get_current_win()') == field()
        assert editor.lua('return vim.fn.mode()') == 'i'
        key('<S-Tab>')
        settled('files', 'needle', 1)
        assert editor.lua('return vim.fn.mode()') == 'i'
        key('<S-Tab>')
        settled('content', 'needle', 3)
        assert editor.call('nvim_get_current_line') == 'needle', 'Shift+Tab must not indent the query'
        key('<Down>')

        before = geometry()
        key('<M-a><M-a><Up>')
        assert editor.lua('return require("config.panel_navigation").state.target') == field()
        assert editor.lua('return vim.api.nvim_get_current_win()') == results
        assert editor.lua('return #require("config.panel_navigation").state.overlays') == 4
        assert geometry() == before
        key('<CR>')
        assert editor.lua('return vim.api.nvim_get_current_win()') == field()
        assert editor.lua('return vim.fn.mode()') == 'i'
        key('<M-a><Down><CR>')
        assert editor.lua('return vim.api.nvim_get_current_win()') == results
        normal_results()
        key('<M-a><M-a><Up><CR><Esc>')
        assert editor.lua('return vim.api.nvim_get_current_win()') == field()
        assert editor.lua('return vim.fn.mode()') == 'n', 'Esc cancels a pending automatic Insert request'
        key('<Down>')
        editor.lua('vim.api.nvim_set_current_win(...)', field())
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Direct field entry automatically resumes Insert')

        key('<C-u>no-such-result')
        settled('content', 'no-such-result', 0)
        key('<Down><CR>')
        normal_results()
        assert editor.lua('return vim.api.nvim_get_current_win()') == results
        key('<Up>')
        key('<C-u>needle<S-Tab>')
        settled('files', 'needle', 1)
        key('<S-Tab>')
        settled('content', 'needle', 3)

        (root / 'bulk.txt').write_text('needle bulk\n' * 70)
        editor.lua('require("config.project_search").refresh()')
        settled('content', 'needle', 73)
        key('<Down>' * 66)
        normal_results()
        editor.wait(lambda: editor.call('nvim_win_get_cursor', results)[0] >= 71, 'Repeated Down scrolls through the result list')
        row = editor.call('nvim_win_get_cursor', results)[0]
        editor.lua('local m=require("config.project_search");m.navigate(require("config.sidebar").state(),require("config.ide").root())')
        assert editor.call('nvim_win_get_cursor', results)[0] == row, 'Background source refresh retains the deep selection'
        key('<Up>' * 66)
        editor.wait(lambda: editor.lua('return vim.api.nvim_get_current_win()') == field(), 'Keyboard scrolls back past the pinned header into the input')
        assert editor.lua('return vim.fn.mode()') == 'i'
        key('<Down><Down><CR>')
        editor.wait(lambda: editor.lua('return vim.api.nvim_get_current_buf()==... and vim.fn.mode()=="i"', document), 'Enter opens a match in the editor')
        assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == saved_lines
        assert editor.lua('return vim.bo[...].modified', document)
        assert editor.lua('return require("config.terminals").active') == terminal
        assert geometry() == before
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: Search field and result rows use Insert/Normal with full-row selection; Up/Down and Alt+A enter/leave '
              'the pinned input; Shift+Tab toggles modes without changing query/focus, including queued typing and empty/scrolling results; '
              'Enter, geometry, terminal and unsaved documents are preserved.')
    finally:
        editor.close()
