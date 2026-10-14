"""Git's horizontal divider resizes panels without triggering status-bar actions."""
from pathlib import Path
import subprocess
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-git-divider-') as directory:
    root = Path(directory)
    source = root / 'source.txt'
    source.write_text('Keep this document\n')
    subprocess.run(['git', 'init', '-b', 'main', str(root)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=UI Test', '-c', 'user.email=ui@example.invalid',
                    'commit', '-m', 'Baseline'], check=True, stdout=subprocess.DEVNULL)
    source.write_text('Working changes\n')
    long = root / ('long_changed_filename_' * 5 + '.txt')
    long.write_text('Horizontal overflow\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);require("config.ide").git_explorer();'
                   'vim.g.status_actions={branch=0,sync=0,problems=0};'
                   'local function count(name) local t=vim.g.status_actions;t[name]=t[name]+1;vim.g.status_actions=t end;'
                   'require("config.git").branches=function()count("branch")end;'
                   'require("config.git_sync").sync=function()count("sync")end;'
                   'require("config.problems").open=function()count("problems")end', str(source))
        main = editor.lua('return require("config.ide").editor_window()')
        document = editor.call('nvim_win_get_buf', main)

        def settled():
            return editor.lua('return not require("config.layout").scaling and not require("config.sidebar").changing')

        def geometry():
            editor.wait(settled, 'Git panels settle')
            return editor.lua('local s=require("config.sidebar");local w=s.state().winid;local h=s.history_win;'
                              'local p=vim.api.nvim_win_get_position(h);return {tree=w,history=h,row=p[1]-1,'
                              'height=vim.api.nvim_win_get_height(w),col=vim.api.nvim_win_get_position(w)[2],width=vim.api.nvim_win_get_width(w)}')

        def actions():
            return editor.lua('return vim.g.status_actions')

        editor.wait(lambda: editor.lua('return require("config.sidebar").history_win~=nil'), 'Commits panel')
        editor.wait(lambda: editor.lua('local s=require("config.sidebar").state();return '
                                      'require("config.hscroll").bars[s.winid]~=nil'), 'Horizontal Git scrollbar')
        for mode in ('normal', 'insert', 'select', 'terminal'):
            if editor.lua('return vim.fn.mode()') != 'n':
                editor.call('nvim_input', '<Esc><Esc>')
                editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Leave previous input/selection')
            editor.lua('vim.api.nvim_set_current_win(...);vim.cmd("startinsert")', main)
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Editor input before ' + mode)
            editor.call('nvim_input', '<Esc>')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Explicit Normal mode')
            if mode == 'insert':
                editor.lua('vim.cmd("startinsert")')
            elif mode == 'select':
                editor.call('nvim_input', 'gh')
            elif mode == 'terminal':
                editor.lua('require("config.terminals").show(require("config.terminals").active)')
            expected = {'normal': 'n', 'insert': 'i', 'select': 's', 'terminal': 't'}[mode]
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == expected, mode + ' active')
            focus = editor.lua('return vim.api.nvim_get_current_win()')
            cursor = editor.call('nvim_win_get_cursor', main)
            g = geometry()
            editor.lua('vim.cmd("redraw!")')
            status_row = editor.lua('return vim.o.lines-vim.o.cmdheight-1')
            text = ''.join(editor.grid[status_row])
            column = text.index('git main') + 5
            assert g['col'] <= column < g['col'] + g['width']
            before = actions()
            editor.click(g['row'], column)
            assert actions() == before, ('Divider click triggered status bar', mode, actions())
            assert editor.lua('return vim.fn.mode()') == expected
            assert editor.lua('return vim.api.nvim_get_current_win()') == focus

            for delta in (3, -3):
                g = geometry()
                editor.call('nvim_input_mouse', 'left', 'press', '', 0, g['row'], column)
                editor.lua('vim.cmd("redraw!")')
                editor.call('nvim_input_mouse', 'left', 'drag', '', 0, g['row'] + delta, column)
                editor.lua('vim.cmd("redraw!")')
                editor.call('nvim_input_mouse', 'left', 'release', '', 0, g['row'] + delta, column)
                editor.wait(lambda: editor.call('nvim_win_get_height', g['tree']) == g['height'] + delta,
                            'Divider changes height in ' + mode)
                editor.wait(settled, 'Resized panels settle')
                assert actions() == before
                assert editor.lua('return vim.fn.mode()') == expected
                assert editor.lua('return vim.api.nvim_get_current_win()') == focus
                assert editor.call('nvim_win_get_cursor', main) == cursor
                assert editor.call('nvim_win_get_buf', main) == document

        # A captured release over another control must not activate it.
        for target in ('console', 'status bar'):
            g = geometry()
            end = editor.lua('local t=require("config.terminals");local p=vim.api.nvim_win_get_position(t.list_win);'
                             'return {p[1]+t.console_row,p[2]+7}') if target == 'console' else [status_row, column]
            editor.call('nvim_input_mouse', 'left', 'press', '', 0, g['row'], column)
            editor.wait(lambda: editor.lua('return require("config.mouse_capture").active()'), 'Divider capture')
            editor.call('nvim_input_mouse', 'left', 'drag', '', 0, g['row'] + 2, column)
            editor.lua('vim.cmd("redraw!")')
            editor.call('nvim_input_mouse', 'left', 'release', '', 0, *end)
            editor.wait(lambda: editor.lua('return not require("config.mouse_capture").active()'), 'Divider capture released')
            assert actions() == before, 'Release activated ' + target
            assert not editor.lua('return require("config.terminals").console_active or false')
            assert editor.lua('return vim.fn.mode()') == 't'
            assert editor.lua('return vim.api.nvim_get_current_win()') == focus

        # A fresh press recovers when the preceding release was lost outside the host.
        g = geometry()
        editor.call('nvim_input_mouse', 'left', 'press', '', 0, g['row'], column)
        editor.wait(lambda: editor.lua('return require("config.mouse_capture").active()'), 'Unfinished divider gesture')
        position = editor.lua('local p=vim.fn.screenpos(...,1,1);return {p.row-1,p.col+1}', main)
        editor.click(*position)
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Fresh editor click recovers input')
        assert not editor.lua('return require("config.mouse_capture").active()')
        assert actions() == before
        assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == ['Working changes']

        # The real status bar retains its branch action.
        editor.lua('vim.cmd("redraw!")')
        column = ''.join(editor.grid[status_row]).index('git main') + 5
        editor.click(status_row, column)
        editor.wait(lambda: actions()['branch'] == 1, 'Real status-bar branch click works')
        assert actions()['sync'] == 0 and actions()['problems'] == 0
        print('PASS: Git divider clicks/drags beside a scrollbar preserve focus/modes/cursor/document; releases over controls and lost-release recovery are safe; the real branch button works.')
    finally:
        editor.close()
