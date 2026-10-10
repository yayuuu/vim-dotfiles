"""Vertical sidebar wheel scrolling stops before overshooting the last item."""
from pathlib import Path
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-sidebar-vertical-') as directory:
    root = Path(directory)
    for index in range(90):
        (root / f'file_{index:03}.txt').write_text('Text\n')
    source = root / 'symbols.lua'
    source.write_text('\n'.join(f'local function symbol_{i:03}_' + 'long_name_' * 9 + f'() return {i} end' for i in range(60)) + '\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);require("config.ide").explorer()', str(source))
        editor.wait(lambda: editor.lua('return require("aerial").num_symbols(vim.api.nvim_win_get_buf(require("config.ide").editor_window()))>=60'), 'Symbols extracted')
        editor.wait(lambda: editor.lua('for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                                      'if vim.bo[vim.api.nvim_win_get_buf(w)].filetype=="aerial" then return require("config.hscroll").bars[w]~=nil end end'), 'Symbols also has horizontal overflow')
        editor.wait(lambda: editor.lua('return not require("config.sidebar").changing'), 'Layout settled')
        for ft in ('neo-tree', 'aerial'):
            win = editor.lua('for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                             'if vim.bo[vim.api.nvim_win_get_buf(w)].filetype==... then return w end end', ft)
            maximum = editor.lua('return math.max(1,vim.api.nvim_buf_line_count(vim.api.nvim_win_get_buf(...))-require("config.hscroll").content_height(...)+1)', win)
            assert maximum > 3, 'Panel must overflow vertically'
            editor.lua('local w=...;vim.g.sidebar_scroll_overshoot=false;vim.api.nvim_create_autocmd("WinScrolled",{callback=function() '
                       'if vim.api.nvim_win_is_valid(w) then local v=vim.api.nvim_win_call(w,vim.fn.winsaveview);'
                       'if v.topline>math.max(1,vim.api.nvim_buf_line_count(vim.api.nvim_win_get_buf(w))-require("config.hscroll").content_height(w)+1) then '
                       'vim.g.sidebar_scroll_overshoot=true end end end})', win)
            p = editor.call('nvim_win_get_position', win)

            def view():
                return editor.lua('return vim.api.nvim_win_call(...,vim.fn.winsaveview)', win)

            # Approach EOF with a partial wheel step, then keep scrolling down.
            for _ in range(40):
                editor.call('nvim_input_mouse', 'wheel', 'down', '', 0, p[0]+3, p[1]+8)
                editor.lua('vim.cmd("redraw!")')
                assert view()['topline'] <= maximum, ft + ': transient overshoot'
            editor.wait(lambda: view()['topline'] == maximum, ft + ': exact bottom boundary')
            assert not editor.lua('return vim.g.sidebar_scroll_overshoot'), ft + ': WinScrolled observed overshoot'
            editor.call('nvim_input_mouse', 'wheel', 'up', '', 0, p[0]+3, p[1]+8)
            editor.wait(lambda: view()['topline'] < maximum, ft + ': reversing immediately scrolls up')
            for _ in range(40):
                editor.call('nvim_input_mouse', 'wheel', 'up', '', 0, p[0]+3, p[1]+8)
            editor.wait(lambda: view()['topline'] == 1, ft + ': exact top boundary')
        assert editor.lua('return vim.bo.filetype') == 'neo-tree', 'Scrolling does not transfer input focus'
        main = editor.lua('return require("config.ide").editor_window()')
        editor.call('nvim_set_current_win', main)
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Editor input')
        for expected, keys in (('i', ''), ('n', '<Esc>'), ('v', 'v')):
            if keys:
                editor.call('nvim_input', keys)
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == expected, 'Set editor mode ' + expected)
            for _ in range(3):
                editor.call('nvim_input_mouse', 'wheel', 'down', '', 0, p[0]+3, p[1]+8)
                editor.lua('vim.cmd("redraw!")')
            assert editor.lua('return vim.api.nvim_get_current_win()') == main, 'Wheel keeps editor focus'
            assert editor.lua('return vim.fn.mode()') == expected, 'Wheel keeps editor mode ' + expected
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: Files/Symbols exact boundaries and partial steps, including horizontal-bar space; no transient overshoot; reverse scrolling preserves focus and Normal/Insert/Visual modes.')
    finally:
        editor.close()
