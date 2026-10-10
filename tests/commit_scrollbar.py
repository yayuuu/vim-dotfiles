"""Commit preview scrollbar follows wrapped text, mouse scrolling, and resizing."""
from pathlib import Path
import subprocess
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-commit-scrollbar-') as directory:
    root = Path(directory)
    repo = root / 'repo'
    repo.mkdir()

    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.STDOUT).decode().strip()

    git('init', '-b', 'main')
    git('config', 'user.name', 'UI Test')
    git('config', 'user.email', 'ui@example.invalid')
    file = repo / 'example.txt'
    file.write_text('Original content\n')
    git('add', '.')
    git('commit', '-m', 'Small commit')
    file.write_text(''.join(f'Line {i:03}: ' + 'wrapped preview content ' * 8 + '\n' for i in range(180)))
    git('add', '.')
    git('commit', '-m', 'Long wrapped patch')
    editor = Editor(repo, root / 'state')
    try:
        editor.lua('vim.g.ide_git_autofetch=false;require("config.ide").git_explorer();vim.cmd("stopinsert")')
        editor.wait(lambda: editor.lua('local s=require("config.sidebar");return s.commits and s.commits[1]~=nil'), 'Graph is loaded')
        layout = editor.lua('return vim.fn.winlayout()')

        def open_commit(row):
            editor.lua('local s=require("config.sidebar");vim.api.nvim_set_current_win(s.history_win);vim.api.nvim_win_set_cursor(s.history_win,{...,0})', row)
            editor.call('nvim_input', '<CR>')
            editor.wait(lambda: editor.lua('local p=Snacks.picker.get()[1];return p and p.shown and p.preview.win:valid()'), 'Commit preview opens')

        def bar():
            return editor.lua('local p=Snacks.picker.get()[1];if not p then return false end;local s=require("config.vscroll").sources[p.preview.win.win];'
                              'local b=s and s.bar;return b and vim.api.nvim_win_is_valid(b.win) and {source=p.preview.win.win,win=b.win,start=b.start,thumb=b.thumb,span=b.span}')

        def view():
            return editor.lua('local p=Snacks.picker.get()[1];return vim.api.nvim_win_call(p.preview.win.win,vim.fn.winsaveview)')

        def close():
            position = editor.lua('local p=Snacks.picker.get()[1];local b=require("config.popup_ui").buttons[p.layout.root.win];'
                                  'local pos=vim.api.nvim_win_get_position(b.win);return {pos[1],pos[2]+1}')
            editor.click(*position)
            editor.wait(lambda: editor.lua('return #Snacks.picker.get()==0 and next(require("config.vscroll").sources)==nil'), 'Picker close also removes scrollbar')
            assert editor.lua('return vim.fn.winlayout()') == layout

        open_commit(1)
        editor.wait(bar, 'Long commit has a vertical scrollbar')
        original = view()
        state = bar()
        position = editor.lua('return vim.api.nvim_win_get_position(...)', state['win'])
        height = editor.call('nvim_win_get_height', state['win'])
        editor.click(position[0]+height-1, position[1])
        editor.wait(lambda: view()['topline'] > original['topline'], 'Clicking track scrolls the preview')
        editor.wait(lambda: bar()['start'] > 0, 'Thumb follows scrolling')
        state = bar()
        position = editor.lua('return vim.api.nvim_win_get_position(...)', state['win'])
        editor.call('nvim_input_mouse', 'left', 'press', '', 0, position[0]+state['start'], position[1])
        editor.call('nvim_input_mouse', 'left', 'drag', '', 0, position[0], position[1])
        editor.call('nvim_input_mouse', 'left', 'release', '', 0, position[0], position[1])
        editor.wait(lambda: bar()['start'] == 0 and view()['topline'] == 1, 'Dragging thumb returns to the top')
        assert editor.lua('local p=Snacks.picker.get()[1];return vim.api.nvim_get_current_win()==p.input.win.win'), 'Scrollbar does not steal picker focus'
        # Drag beyond the popup's lower border, above the terminal session list.
        # Release still belongs to the scrollbar, including when the pointer
        # is over empty space that Neovim maps to the Debug console row.
        state = bar()
        position = editor.lua('return vim.api.nvim_win_get_position(...)', state['win'])
        console = editor.lua('return require("config.terminals").console_active or false')
        editor.call('nvim_input_mouse', 'left', 'press', '', 0, position[0]+state['start'], position[1])
        editor.wait(lambda: editor.lua('return require("config.vscroll").drag~=nil'), 'Scrollbar receives the press before dragging')
        editor.call('nvim_input_mouse', 'left', 'drag', '', 0, 45, position[1])
        editor.wait(lambda: bar()['start'] == bar()['span'], 'Dragging past the bottom clamps at the end of the patch')
        editor.call('nvim_input_mouse', 'left', 'release', '', 0, 45, position[1])
        editor.lua('vim.cmd("redraw!")')
        assert editor.lua('local p=Snacks.picker.get()[1];return p and not p.closed'), 'Releasing bottom drag must keep the commit picker open'
        assert editor.lua('return require("config.terminals").console_active or false') == console, 'Release must not select the underlying Debug console'
        editor.wait(lambda: bar()['start'] == bar()['span'], 'Dragging past the bottom clamps at the end of the patch')
        assert editor.lua('return not require("config.mouse_capture").active()'), 'Release clears mouse capture'
        # Moving above the preview must not turn release into a close-button click.
        state = bar()
        position = editor.lua('return vim.api.nvim_win_get_position(...)', state['win'])
        button = editor.lua('local p=Snacks.picker.get()[1];local b=require("config.popup_ui").buttons[p.layout.root.win];'
                            'local pos=vim.api.nvim_win_get_position(b.win);return {pos[1],pos[2]+1}')
        editor.call('nvim_input_mouse', 'left', 'press', '', 0, position[0]+state['start'], position[1])
        editor.wait(lambda: editor.lua('return require("config.mouse_capture").active()'), 'Bottom thumb receives press')
        editor.call('nvim_input_mouse', 'left', 'drag', '', 0, *button)
        editor.wait(lambda: bar()['start'] == 0, 'Dragging above the preview clamps at the top')
        editor.call('nvim_input_mouse', 'left', 'release', '', 0, *button)
        editor.wait(lambda: editor.lua('return not require("config.mouse_capture").active()'), 'Release above preview clears capture')
        assert editor.lua('local p=Snacks.picker.get()[1];return p and not p.closed and vim.api.nvim_get_current_win()==p.input.win.win'), 'Release over close button preserves the picker and input focus'
        editor.call('nvim_input_mouse', 'wheel', 'down', '', 0, position[0]+2, position[1])
        editor.wait(lambda: view()['topline'] > 1 or view()['skipcol'] > 0, 'Wheel on scrollbar scrolls the preview')
        for width, height in ((128, 36), (180, 52), (160, 48)):
            editor.call('nvim_ui_try_resize', width, height)
            editor.wait(lambda: editor.lua('local p=Snacks.picker.get()[1];local s=p and require("config.vscroll").sources[p.preview.win.win];local b=s and s.bar;'
                                          'if not b or not vim.api.nvim_win_is_valid(b.win) then return false end;local c=vim.api.nvim_win_get_config(b.win);'
                                          'return c.win==p.preview.win.win and c.col==vim.api.nvim_win_get_width(p.preview.win.win) '
                                          'and c.height==vim.api.nvim_win_get_height(p.preview.win.win)'), 'Scrollbar stays on preview border after resize')
        close()
        open_commit(2)
        editor.wait(lambda: editor.lua('local p=Snacks.picker.get()[1];return table.concat(vim.api.nvim_buf_get_lines(p.preview.win.buf,0,-1,false),string.char(10)):find("Original content",1,true)~=nil'), 'Small commit preview renders')
        assert not bar(), 'No scrollbar is needed when the entire preview fits'
        close()
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'Vertical scrollbar:' not in messages and 'Invalid window id' not in messages, messages
        print('PASS: commit preview scrollbar supports click, drag/release outside both borders, wheel, wrapped lines, resize, hiding, and clean close without activating underlying controls.')
    finally:
        editor.close()
