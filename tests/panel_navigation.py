"""Alt+A previews tabs/panels and commits focus only with Enter; mouse remains native."""
from pathlib import Path
import subprocess
import tempfile
import time

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-panel-navigation-') as directory:
    root = Path(directory)
    files = [root / name for name in ('one.lua', 'two.lua', 'three.lua')]
    for path in files:
        path.write_text('local function example()\n  return true\nend\nreturn example()\n')
    (root / 'reader.py').write_text('import os,pathlib,tty\ntty.setraw(0)\n'
                                   'pathlib.Path("ready").touch()\n'
                                   'with open("input","ab",buffering=0) as log:\n'
                                   '    while True: log.write(os.read(0,4096))\n')
    subprocess.run(['git', 'init', '-b', 'main', str(root)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=UI Test', '-c',
                    'user.email=ui@example.invalid', 'commit', '-m', 'Baseline'],
                   check=True, stdout=subprocess.DEVNULL)
    editor = Editor(root, root / 'state')
    try:
        buffers = []
        for path in files:
            editor.lua('require("config.ide").open_file(...)', str(path))
            buffers.append(editor.lua('return vim.api.nvim_get_current_buf()'))
        editor.call('nvim_buf_set_lines', buffers[-1], 1, 2, False, ['  return "Unsaved"'])
        main = editor.lua('return require("config.ide").editor_window()')
        editor.lua('local _,w=require("config.sidebar").state();vim.api.nvim_win_set_width(w,55)')
        editor.wait(lambda: editor.lua('return require("config.layout").sizes.tree') == 55, 'Sidebar settles')

        def pump():
            time.sleep(.08)
            editor.lua('return true')

        def key(keys):
            editor.call('nvim_input', keys)
            pump()

        def state():
            return editor.lua('local s=require("config.panel_navigation").state;'
                              'return s and {phase=s.phase,kind=s.kind,index=s.index,target=s.target,origin=s.origin}')

        def current():
            return editor.lua('return vim.api.nvim_get_current_win()')

        def mode():
            return editor.lua('return vim.fn.mode()')

        def native_geometry():
            return editor.lua('local r={};for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                              'if vim.api.nvim_win_get_config(w).relative=="" then '
                              'r[tostring(w)]={vim.api.nvim_win_get_position(w),vim.api.nvim_win_get_width(w),'
                              'vim.api.nvim_win_get_height(w)} end end;return r')

        def highlighted(win, column):
            position = editor.call('nvim_win_get_position', win)
            attribute = editor.attributes[position[0]][position[1] + column]
            wanted = editor.lua('return vim.api.nvim_get_hl(0,{name="DesktopNavigationTab",link=false}).bg')
            assert editor.highlights[attribute].get('background') == wanted

        editor.wait(lambda: mode() == 'i', 'Editable document input')
        caret = editor.lua('return vim.o.guicursor')
        geometry = native_geometry()
        order = editor.lua('return require("config.editor_tabs").ids')
        key('<M-a>')
        assert state()['phase'] == 'tabs' and state()['kind'] == 'documents'
        key('<Right>')
        assert editor.call('nvim_win_get_buf', main) == editor.call('nvim_get_current_buf')
        assert editor.lua('return vim.api.nvim_win_get_buf(...)', main) == buffers[-1], 'Tab preview must not open a document'
        strip, column = editor.lua('local t=require("config.editor_tabs");for _,h in ipairs(t.hits) do '
                                   'if h.id==t.preview then return {t.win,h.first} end end')
        highlighted(strip, column)
        assert native_geometry() == geometry
        key('<CR>')
        assert state() is None
        assert editor.lua('return vim.api.nvim_win_get_buf(...)', main) == order[1]
        assert mode() == 'i' and editor.lua('return vim.o.guicursor') == caret
        key('<M-a><Right><Esc>')
        assert state() is None and current() == main
        before = editor.call('nvim_buf_get_lines', order[1], 0, 1, False)[0]
        key('X')
        assert editor.call('nvim_buf_get_lines', order[1], 0, 1, False)[0] != before, 'Restore Insert mappings'

        key('<M-a><M-a><Left>')
        assert state()['phase'] == 'panels' and current() == main
        tree = editor.lua('local _,w=require("config.sidebar").state();return w')
        assert state()['target'] == tree
        assert native_geometry() == geometry, 'Panel frame cannot resize windows'
        frames = editor.lua('return require("config.panel_navigation").state.overlays')
        assert len(frames) == 4
        for frame in frames:
            config = editor.call('nvim_win_get_config', frame)
            assert not config['focusable'] and not config['mouse']
        def check_frame():
            assert editor.lua('local s=require("config.panel_navigation").state;'
                              'local p=vim.api.nvim_win_get_position(s.target);'
                              'local bottom=vim.api.nvim_win_get_position(s.overlays[2]);'
                              'return bottom[1]==p[1]+vim.api.nvim_win_get_height(s.target)-1'), 'Frame stays above the divider'
        check_frame()
        editor.call('nvim_win_set_width', tree, 56)
        editor.wait(lambda: editor.lua('return require("config.layout").sizes.tree') == 56, 'Resize during selection')
        pump()
        check_frame()
        editor.call('nvim_win_set_width', tree, 55)
        editor.wait(lambda: editor.lua('return require("config.layout").sizes.tree') == 55, 'Restore sidebar width')
        key('<Down>')
        symbols = state()['target']
        assert editor.lua('return vim.bo[vim.api.nvim_win_get_buf(...)].filetype', symbols) == 'aerial'
        key('<CR>')
        assert current() == symbols and mode() == 'n'
        key('i')
        assert mode() == 'n', 'Symbols remains in Normal mode'
        key('<M-a><Right>')
        assert state()['kind'] == 'sidebar' and state()['index'] == 3
        assert editor.lua('return require("config.sidebar").state().name') == 'filesystem'
        row = editor.call('nvim_win_get_position', tree)[0]
        column = ''.join(editor.grid[row]).index('Search') + 1
        highlighted(tree, column)
        key('<CR>')
        editor.wait(lambda: editor.lua('return require("config.sidebar").state().name') == 'search', 'Commit Search tab')
        key('<M-a><Left><CR>')
        editor.wait(lambda: editor.lua('return require("config.sidebar").state().name') == 'filesystem', 'Commit Files tab')
        assert mode() == 'n'
        editor.lua('local s=require("config.sidebar").state();local n=s.tree:get_node(...);require("config.files").select(s,n)', str(files[0]))
        editor.lua('_G.before_panel_enter=vim.fn.maparg("<CR>","n",false,true).callback')
        key('<M-a><Esc>')
        assert editor.lua('return vim.fn.maparg("<CR>","n",false,true).callback==_G.before_panel_enter'), 'Restore Neo-tree mappings'
        key('<S-F10>')
        editor.wait(lambda: editor.lua('return vim.bo.filetype') == 'NvMenu', 'Keyboard file context menu')
        items = editor.lua('return vim.tbl_map(function(i)return i.name end,require("menu.state").bufs[vim.api.nvim_get_current_buf()].items)')
        assert 'Open' in items and 'Rename' in items
        key('<Esc>')
        assert mode() == 'n' and editor.lua('return vim.bo.filetype') == 'neo-tree'
        key(chr(57443))
        assert editor.lua('return vim.bo.filetype') == 'NvMenu', 'Optional standalone left Alt event'
        key('<Esc>')
        key('<M-a><M-a>')
        point = editor.lua('local s=require("config.sidebar").state();local _,l=s.tree:get_node(...);'
                           'local p=vim.fn.screenpos(s.winid,l,1);return {p.row-1,p.col+4}', str(files[1]))
        editor.click(*point)
        assert state() is None and current() == tree and mode() == 'n'
        assert editor.lua('return vim.api.nvim_win_get_buf(...)', main) == buffers[1], 'Click opens the Files row while canceling preview'

        # A mouse press cancels selection before the real document-tab handler.
        editor.lua('require("config.ide").open_file(nil,...)', buffers[-1])
        key('<M-a><Right>')
        point = editor.lua('local t=require("config.editor_tabs");local p=vim.api.nvim_win_get_position(t.win);'
                           'for _,h in ipairs(t.hits) do if h.id==... and not h.close then return {p[1],p[2]+h.first} end end', buffers[-1])
        editor.click(*point)
        assert state() is None and editor.lua('return vim.api.nvim_get_current_buf()') == buffers[-1]
        assert mode() == 'i'

        # The menu bar is reachable both spatially and through the Alt+A cycle.
        key('<M-a><M-a><Up>')
        assert state()['target'] == 'menu'
        key('<CR>')
        assert editor.lua('return require("config.ide").menu_name') == 'File'
        key('<Right>')
        assert editor.lua('return require("config.ide").menu_name') == 'Edit'
        key('<Left><Left>')
        assert editor.lua('return require("config.ide").menu_name') == 'Help'
        key('<Right><Down>')
        assert editor.lua('return require("config.ide").menu_name') == 'File'
        previous = editor.lua('return #vim.tbl_filter(function(b)return vim.bo[b].buflisted end,vim.api.nvim_list_bufs())')
        key('<CR>')
        assert editor.lua('return #vim.tbl_filter(function(b)return vim.bo[b].buflisted end,vim.api.nvim_list_bufs())') > previous
        assert mode() == 'i', 'Enter runs New file from the chosen top menu'
        key('<M-a><M-a><M-a>')
        assert state() is None and editor.lua('return require("config.ide").menu_name') == 'File'
        key('<Esc>')

        # Terminal selection keys must not be forwarded to the actual PTY child.
        editor.lua('local t=require("config.terminals");t.show(t.active);'
                   'vim.fn.chansend(t.items[1].job,"/usr/bin/python3 -B reader.py\\n")')
        editor.wait((root / 'ready').exists, 'Raw terminal child')
        terminal = current()
        editor.wait(lambda: mode() == 't', 'Terminal input')
        key('<M-a>')
        assert state()['phase'] == 'panels' and current() == terminal
        key('<Up><Left>abc<Right><Esc>')
        assert state() is None and current() == terminal and mode() == 't'
        assert (root / 'input').read_bytes() == b'', 'Panel preview cannot send keys to the terminal'
        key('ok')
        editor.wait(lambda: (root / 'input').read_bytes() == b'ok', 'Terminal mappings restored')
        key('<M-a><Up><CR>')
        assert current() == main and mode() == 'i'
        assert editor.call('nvim_buf_get_lines', buffers[-1], 1, 2, False) == ['  return "Unsaved"']

        editor.lua('require("config.diff").open(...)', str(files[0]))
        diff = editor.lua('return require("config.diff").active')
        for pane in (diff['left'], diff['right']):
            editor.lua('vim.cmd("stopinsert");vim.api.nvim_set_current_win(...)', pane)
            pump()
            geometry = native_geometry()
            key('<M-a>')
            assert state()['kind'] == 'documents', 'Both diff columns share document tabs'
            key('<Right>')
            assert native_geometry() == geometry and current() == pane
            key('<Esc>')
            assert native_geometry() == geometry and current() == pane
        key('<M-a><Right><CR>')
        assert editor.lua('return require("config.diff").active') is None, 'Accept a regular tab from a diff'
        assert mode() == 'i'

        for index in range(10):
            path = root / f'overflow-document-with-long-name-{index}.txt'
            path.write_text('Tab overflow\n')
            editor.lua('require("config.ide").open_file(...)', str(path))
        key('<M-a>' + '<Right>' * 8)
        assert editor.lua('return require("config.editor_tabs").first') > 1
        key('<Esc>')
        assert editor.lua('return require("config.editor_tabs").first') == 1, 'Esc restores tab scrolling'
        key('<M-a>' + '<Right>' * 8)
        candidate, point = editor.lua('local t=require("config.editor_tabs");local p=vim.api.nvim_win_get_position(t.win);'
                                      'for _,h in ipairs(t.hits) do if h.id==t.preview and not h.close then '
                                      'return {t.preview,{p[1],p[2]+h.first}} end end')
        editor.click(*point)
        assert state() is None and editor.lua('return vim.api.nvim_get_current_buf()') == candidate, 'Mouse opens the visible scrolled preview card'
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: deferred document/sidebar tab selection, spatial framed panels, Enter/Esc, native mouse cancellation, '
              'menu-bar navigation/actions, Normal Files/Symbols, keyboard file menu, restored mappings/caret, '
              'and real terminal input isolation; unsaved documents and window geometry preserved.')
    finally:
        editor.close()
