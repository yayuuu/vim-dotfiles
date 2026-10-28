"""Git rows/context menus and the pinned commit input share predictable keyboard focus."""
from pathlib import Path
import subprocess
import tempfile
import time

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-git-keyboard-') as directory:
    root = Path(directory)
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.STDOUT).decode().strip()
    git('init', '-b', 'main')
    git('config', 'user.name', 'UI Test')
    git('config', 'user.email', 'ui@example.invalid')
    first, second = root / 'first.txt', root / 'second.txt'
    for path in (first, second):
        path.write_text('Original\n')
    git('add', '.')
    git('commit', '-m', 'First commit')
    first.write_text('Staged change\n')
    git('add', 'first.txt')
    git('commit', '-m', 'Second commit')
    first.write_text('Staged again\n')
    second.write_text('Working change\n')
    git('add', 'first.txt')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...)', str(second))
        document = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.call('nvim_buf_set_lines', document, 0, -1, False, ['Unsaved working document'])
        terminal = editor.lua('return require("config.terminals").active')

        def key(keys):
            editor.call('nvim_input', keys)
            time.sleep(.1)
            editor.lua('return true')

        def field():
            return editor.lua('local s=require("config.sidebar").state();local f=require("config.git").inputs[s.path];return f and f.win')

        def normal_rows():
            assert editor.lua('return vim.fn.mode()') == 'n'
            assert editor.lua('return vim.o.guicursor') == 'a:DesktopPanelCursor', editor.lua('return {cursor=vim.o.guicursor,ft=vim.bo.filetype,win=vim.api.nvim_get_current_win(),source=require("config.sidebar").state().name}')
            assert editor.lua('return vim.wo.cursorline and vim.wo.cursorlineopt=="both"')

        def single_row():
            normal_rows()
            assert editor.lua('local s=require("config.sidebar").state();return vim.tbl_isempty(s.ide_selected or {})'), 'Arrows move focus without selecting files'
            assert editor.lua('local s=require("config.sidebar").state();return #vim.api.nvim_buf_get_extmarks(s.bufnr,'
                              'vim.api.nvim_create_namespace("DesktopIDEGitSelection"),0,-1,{})') == 0, 'No Visual selection remains'
            point = editor.lua('local w=...;local p=vim.fn.screenpos(w,vim.api.nvim_win_get_cursor(w)[1],1);'
                               'return {p.row-1,p.col-1+vim.api.nvim_win_get_width(w)-2}', status)
            wanted = editor.lua('return vim.api.nvim_get_hl(0,{name="NeoTreeCursorLine",link=false}).bg')
            assert editor.highlights[editor.attributes[point[0]][point[1]]]['background'] == wanted, 'Only the focused row uses the list highlight'

        def labels():
            return editor.lua('local b=require("config.ide").popup_buffer;return b and vim.tbl_map(function(i)return i.name end,require("menu.state").bufs[b].items)')

        def geometry():
            return editor.lua('local r={};for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                              'if vim.api.nvim_win_get_config(w).relative=="" then '
                              'r[tostring(w)]={vim.api.nvim_win_get_position(w),vim.api.nvim_win_get_width(w),'
                              'vim.api.nvim_win_get_height(w)} end end;return r')

        editor.wait(lambda: editor.lua('return vim.fn.mode()=="i" and not require("config.sidebar").changing '
                                       'and not require("config.sidebar").updating and not require("config.layout").scaling'), 'Document focus settles')
        key('<M-r>')
        editor.wait(lambda: editor.lua('local s=require("config.sidebar").state();return s.name=="git_status" and s.tree and s.tree:get_node(...)~=nil', str(first)+'::staged') and field(), 'Git rows and commit input')
        status, history = editor.lua('return {select(2,require("config.sidebar").state()),require("config.sidebar").history_win}')
        editor.wait(lambda: editor.lua('return #require("config.sidebar").commits') >= 2, 'Commit graph')
        if editor.lua('return vim.api.nvim_get_current_win()') != status:
            key('<M-a><Left><CR>')
        normal_rows()
        editor.call('nvim_win_set_cursor', status, [5, 0])
        key('<Down>')  # First staged file beneath its section heading.
        assert editor.lua('local s=require("config.sidebar").state();return s.tree:get_node():get_id()') == str(first)+'::staged'
        single_row()
        key('<Left><Right>')
        assert editor.call('nvim_win_get_cursor', status)[1] == 0
        key('<S-F10>')
        assert 'Open diff' in labels() and 'Unstage Changes' in labels()
        key('<Esc>')
        normal_rows()
        key('<Down><Down>')
        single_row()
        key('<S-F10>')
        assert 'Stage Changes' in labels() and 'Discard Changes…' in labels()
        key('<Esc>')

        key('<Up>' * 4)
        assert editor.lua('return vim.api.nvim_get_current_win()') == field()
        assert editor.lua('return vim.fn.mode()') == 'i'
        key('Draft commit message<Down>')
        assert editor.lua('return vim.api.nvim_get_current_win()') == status
        single_row()
        assert editor.lua('return require("config.git").messages[require("config.sidebar").state().path]') == 'Draft commit message'

        before = geometry()
        key('<M-a><Up>')
        assert editor.lua('return require("config.panel_navigation").state.target') == field()
        assert editor.lua('return vim.api.nvim_get_current_win()') == status
        assert editor.lua('return #require("config.panel_navigation").state.overlays') == 4, 'Commit input uses a border frame'
        assert editor.lua('local n=require("config.panel_navigation").state;local c=vim.api.nvim_win_get_config(n.target);'
                          'local p=vim.api.nvim_win_get_position(n.overlays[1]);'
                          'local bottom=vim.api.nvim_win_get_position(n.overlays[2]);'
                          'return p[1]==c.row and p[2]==c.col and bottom[1]==c.row+c.height+1'), 'Frame follows the commit input border'
        assert geometry() == before
        key('<CR>')
        assert editor.lua('return vim.api.nvim_get_current_win()') == field()
        assert editor.lua('return vim.fn.mode()') == 'i'
        key('<M-a><Down><CR>')
        assert editor.lua('return vim.api.nvim_get_current_win()') == status
        normal_rows()
        key('<M-a><Down><CR>')
        assert editor.lua('return vim.api.nvim_get_current_win()') == history
        normal_rows()
        key('<Down><S-F10>')
        assert 'View commit' in labels() and 'Copy commit hash' in labels()
        key('<Down><CR>')
        editor.wait(lambda: editor.lua('local p=Snacks.picker.get()[1];return p and p.shown'), 'Keyboard context action opens commit preview')
        editor.lua('Snacks.picker.get()[1]:close()')
        editor.wait(lambda: editor.lua('return #Snacks.picker.get()==0 and vim.fn.mode()=="n" '
                                       'and vim.api.nvim_get_current_win()==...', history), 'Close commit preview back to history')
        normal_rows()
        point = editor.lua('local p=vim.fn.screenpos(...,1,1);return {p.row-1,p.col+3}', history)
        editor.call('nvim_input_mouse', 'right', 'press', '', 0, *point)
        editor.call('nvim_input_mouse', 'right', 'release', '', 0, *point)
        editor.wait(lambda: labels(), 'Mouse commit context menu')
        assert 'View commit' in labels()
        key('<Esc>')
        assert geometry() == before
        assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == ['Unsaved working document']
        assert editor.lua('return require("config.terminals").active') == terminal
        assert git('log', '-1', '--format=%s') == 'Second commit', 'Typing a draft never commits'
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: Git status/commits use Normal full-row navigation and shared keyboard/mouse context menus; '
              'Up/Down and spatial panel selection enter/leave Commit message with correct modes, preserving draft, layout, terminal and unsaved text.')
    finally:
        editor.close()
