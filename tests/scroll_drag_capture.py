"""Map and horizontal-bar releases cannot activate other UI controls."""
from pathlib import Path
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-scroll-capture-') as directory:
    root = Path(directory)
    long = root / 'long.txt'
    other = root / 'other.txt'
    content = [f'Line {i:04} ' + 'wide content ' * 30 for i in range(1000)]
    long.write_text('\n'.join(content)+'\n')
    other.write_text('Other document\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...)', str(other))
        otherbuf = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.lua('require("config.ide").open_file(...)', str(long))
        source = editor.lua('return require("config.ide").editor_window()')
        buf = editor.call('nvim_win_get_buf', source)

        def grab(widget):
            if widget == 'map':
                return editor.lua('local w=require("neominimap.window.float.window_map").get_minimap_winid(...);'
                                  'if not w then return end;local p=vim.api.nvim_win_get_position(w);return {p[1]+3,p[2]+3}', source)
            return editor.lua('local b=require("config.hscroll").bars[...];if not b then return end;'
                              'local p=vim.api.nvim_win_get_position(b.win);return {p[1],p[2]+b.start}', source)

        def target(label):
            if label == 'console':
                return editor.lua('local t=require("config.terminals");local p=vim.api.nvim_win_get_position(t.list_win);'
                                  'return {p[1]+t.console_row,p[2]+7}')
            if label == 'new terminal':
                return editor.lua('local t=require("config.terminals");local p=vim.api.nvim_win_get_position(t.list_win);return {p[1]+1,p[2]+7}')
            if label == 'terminal body':
                return editor.lua('local t=require("config.terminals");local p=vim.api.nvim_win_get_position(t.win);return {p[1]+2,p[2]+10}')
            if label == 'close tab':
                return editor.lua('local t=require("config.editor_tabs");local p=vim.api.nvim_win_get_position(t.win);'
                                  'for _,h in ipairs(t.hits) do if h.id==... and h.close then return {p[1],p[2]+h.first-1} end end', otherbuf)
            return [0, 2]  # File menu heading.

        for widget in ('map', 'horizontal bar'):
            for mode in ('normal', 'insert'):
                for label in ('console', 'new terminal', 'terminal body', 'close tab', 'menu'):
                    editor.lua('vim.api.nvim_set_current_win(...);vim.cmd("stopinsert")', source)
                    if mode == 'insert': editor.lua('vim.cmd("startinsert")')
                    editor.wait(lambda: grab(widget), widget+' is visible')
                    start = grab(widget)
                    end = target(label)
                    assert end, 'Target exists: '+label
                    terminals = editor.lua('return #require("config.terminals").items')
                    editor.call('nvim_input_mouse', 'left', 'press', '', 0, *start)
                    editor.lua('vim.cmd("redraw!")')
                    editor.call('nvim_input_mouse', 'left', 'drag', '', 0, *end)
                    editor.lua('vim.cmd("redraw!")')
                    editor.call('nvim_input_mouse', 'left', 'release', '', 0, *end)
                    editor.lua('vim.cmd("redraw!")')
                    label = widget+' / '+mode+' / '+label
                    assert not editor.lua('return require("config.terminals").console_active or false'), label+' activated Debug console'
                    assert editor.lua('return #require("config.terminals").items') == terminals, label+' created a terminal'
                    assert editor.lua('return vim.api.nvim_get_current_win()') == source, label+' stole editor focus'
                    assert editor.call('nvim_win_get_buf', source) == buf, label+' changed document'
                    assert editor.call('nvim_buf_is_valid', otherbuf), label+' closed a tab'
                    assert editor.lua('return #require("menu.state").bufids') == 0, label+' opened the menu'
                    assert editor.lua('return vim.fn.mode()') == ('i' if mode == 'insert' else 'n'), label+' changed mode'
                    editor.wait(lambda: editor.lua('return not require("config.mouse_capture").active()'), 'Release clears capture')
        assert editor.call('nvim_buf_get_lines', buf, 0, -1, False) == content
        # Genuine clicks after a drag must still work.
        editor.click(*target('console'))
        editor.wait(lambda: editor.lua('return require("config.terminals").console_active'), 'Independent console click works')
        print('PASS: map/horizontal drag releases over console, terminal controls/body, tab close and menu preserve editor, contents and modes; subsequent clicks work.')
    finally:
        editor.close()
