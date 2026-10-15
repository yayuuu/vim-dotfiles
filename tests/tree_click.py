"""File clicks work across modes and recover from a missing scrollbar release."""
from pathlib import Path
import tempfile

from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-tree-click-') as directory:
    root = Path(directory)
    first, second, long = [root / name for name in ('first.txt', 'second.txt', 'long.txt')]
    first.write_text('First document\nSecond line\n')
    second.write_text('Second document\n')
    long.write_text('long line ' * 120 + '\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...)', str(first))
        firstbuf = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.call('nvim_buf_set_lines', firstbuf, 0, 1, False, ['Unsaved document'])

        def position(file):
            return editor.lua('local s=require("neo-tree.sources.manager").get_state("filesystem");'
                              'if not s.tree then return end;local _,line=s.tree:get_node(...);if not line then return end;'
                              'local p=vim.api.nvim_win_get_position(s.winid);local info=vim.fn.getwininfo(s.winid)[1];'
                              'return {p[1]+line-info.topline+1,p[2]+8}', str(file))

        def current():
            return editor.lua('return vim.api.nvim_buf_get_name(vim.api.nvim_win_get_buf(require("config.ide").editor_window()))')

        def click(file, modifier=''):
            editor.wait(lambda: position(file), 'File row rendered')
            row, column = position(file)
            editor.call('nvim_input_mouse', 'left', 'press', modifier, 0, row, column)
            editor.lua('vim.cmd("redraw!")')
            editor.call('nvim_input_mouse', 'left', 'release', modifier, 0, row, column)
            editor.wait(lambda: current() == str(file), 'Mouse opens ' + file.name)

        for mode, keys in [('Normal', '<Esc>'), ('Insert', '<Esc>i'),
                           ('Visual', '<Esc>v'), ('Select', '<Esc>v<C-g>')]:
            editor.lua('require("config.ide").open_file(...)', str(first))
            editor.call('nvim_input', keys)
            editor.lua('vim.cmd("redraw!")')
            click(second)
            assert editor.call('nvim_buf_get_lines', firstbuf, 0, 1, False) == ['Unsaved document'], mode
            assert editor.call('nvim_get_option_value', 'modified', {'buf': firstbuf}), mode
        editor.lua('local t=require("config.terminals");vim.api.nvim_set_current_win(t.win);vim.cmd("startinsert")')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Terminal input')
        click(first)
        # Repeated native clicks must use the row under the pointer even when
        # repeated presses are mapped to no-ops to suppress Vim word selection.
        for file, modifier in [(second, '2'), (first, '3'), (second, '4')]:
            editor.call('nvim_input', '<Esc>')
            editor.lua('vim.cmd("redraw!")')
            click(file, modifier)

        editor.lua('require("config.ide").open_file(...)', str(long))
        editor.wait(lambda: editor.lua('return require("config.hscroll").bars[require("config.ide").editor_window()]~=nil'), 'Horizontal bar')
        pos = editor.lua('local b=require("config.hscroll").bars[require("config.ide").editor_window()];'
                         'local p=vim.api.nvim_win_get_position(b.win);return {p[1],p[2]+5}')
        editor.call('nvim_input_mouse', 'left', 'press', '', 0, *pos)
        editor.wait(lambda: editor.lua('return require("config.hscroll").drag~=nil'), 'Horizontal drag begins')
        # No release: simulate the pointer being released outside the host.
        click(second)
        assert editor.lua('return require("config.hscroll").drag==nil')

        # Earlier mode-transition diagnostics must not cover this gesture fixture.
        editor.lua('require("noice").cmd("dismiss")')
        preview = editor.lua('local b=vim.api.nvim_create_buf(false,true);local lines={};'
                             'for i=1,150 do lines[i]="Preview line "..i end;vim.api.nvim_buf_set_lines(b,0,-1,false,lines);'
                             'local w=vim.api.nvim_open_win(b,false,{relative="editor",row=5,col=80,width=35,height=15,style="minimal",border="single"});'
                             'require("config.vscroll").attach(w);return w')
        editor.wait(lambda: editor.lua('local s=require("config.vscroll").sources[...];return s and s.bar~=nil', preview), 'Vertical bar')
        editor.lua('vim.cmd("redraw!")')
        pos = editor.lua('local b=require("config.vscroll").sources[...].bar;return vim.api.nvim_win_get_position(b.win)', preview)
        editor.call('nvim_input_mouse', 'left', 'press', '', 0, pos[0]+3, pos[1])
        editor.wait(lambda: editor.lua('return require("config.mouse_capture").active()'), 'Vertical drag captures mouse')
        click(first)
        assert editor.lua('return not require("config.mouse_capture").active() and require("config.vscroll").drag==nil')
        editor.lua('require("config.vscroll").detach(...);vim.api.nvim_win_close(...,true)', preview)

        # A menu action closes on press. If the host loses its release, the
        # next independent click must not inherit the old menu's click guard.
        editor.lua('_G.tree_menu_action=false;require("config.ide").popup({'
                   '{name="Test action",cmd=function() _G.tree_menu_action=true end}})')
        editor.lua('vim.cmd("redraw!")')
        pos = next((row, ''.join(cells).index('Test action') + 2)
                   for row, cells in enumerate(editor.grid) if 'Test action' in ''.join(cells))
        editor.call('nvim_input_mouse', 'left', 'press', '', 0, *pos)
        editor.wait(lambda: editor.lua('return _G.tree_menu_action and #require("menu.state").bufids==0'), 'Menu action closes on press')
        # Intentionally omit release, as with releasing outside the host window.
        click(second)
        assert not editor.lua('return require("config.ide").menu_mouse_pending'), 'New click clears the closed menu guard'
        click(first)
        assert editor.call('nvim_buf_get_lines', firstbuf, 0, 1, False) == ['Unsaved document']
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: tree clicks open the pointed file from Normal/Insert/Visual/Select/terminal and repeated clicks; missing horizontal/vertical releases recover without losing unsaved edits.')
    except Exception:
        print(editor.lua('return vim.fn.execute("messages")'))
        print(editor.lua('return vim.inspect({mouse=vim.fn.getmousepos(),pending=require("config.ide").menu_mouse_pending,'
                         'capture=require("config.mouse_capture").owner,menus=package.loaded["menu.state"]})'))
        raise
    finally:
        editor.close()
