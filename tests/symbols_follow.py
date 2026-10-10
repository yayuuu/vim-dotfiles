"""Symbols follows cursor movement in Insert and Normal without stealing focus."""
from pathlib import Path
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-symbols-follow-') as directory:
    root = Path(directory)
    file = root / 'functions.lua'
    content = [line for i in range(60) for line in (f'local function symbol_{i:02}()', '  return true', 'end', '')]
    file.write_text('\n'.join(content)+'\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(file))
        source = editor.lua('return require("config.ide").editor_window()')
        buf = editor.call('nvim_win_get_buf', source)
        def outline():
            return editor.lua('for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                              'if vim.bo[vim.api.nvim_win_get_buf(w)].filetype=="aerial" then return w end end')
        editor.wait(outline, 'Symbols exists')
        symbols = outline()
        editor.wait(lambda: editor.call('nvim_buf_line_count', editor.call('nvim_win_get_buf', symbols))==60, 'All functions appear')
        def follows(index):
            return editor.lua('local w,index=...;local b=vim.api.nvim_win_get_buf(w);local row=index+1;'
                              'local highlighted=false;for _,mark in ipairs(vim.api.nvim_buf_get_extmarks(b, '
                              'vim.api.nvim_create_namespace("aerial-line"),0,-1,{details=true})) do '
                              'if mark[2]==row-1 and mark[4].hl_group=="AerialLine" then highlighted=true end end;'
                              'local info=vim.fn.getwininfo(w)[1];return highlighted and '
                              'vim.api.nvim_win_get_cursor(w)[1]==row and info.topline<=row and info.botline>=row', symbols,index)
        editor.lua('vim.api.nvim_set_current_win(...);vim.cmd("stopinsert")',source)
        editor.call('nvim_input','<Down>'*101)
        editor.lua('vim.cmd("redraw!")')
        editor.wait(lambda:follows(25), 'Normal mode follows symbol')
        editor.lua('vim.cmd("startinsert")')
        for index in (3,45,12):
            line=4*index+2
            current=editor.call('nvim_win_get_cursor',source)[0]
            editor.call('nvim_input', ('<Down>' if line>current else '<Up>')*abs(line-current))
            editor.lua('vim.cmd("redraw!")')
            editor.wait(lambda:follows(index), 'Insert mode follows symbol '+str(index))
            assert editor.lua('return vim.fn.mode()')=='i', 'Cursor following preserves Insert mode'
            assert editor.lua('return vim.api.nvim_get_current_win()')==source, 'Symbols must not steal focus'
        assert editor.call('nvim_buf_get_lines',buf,0,-1,False)==content
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: Symbols cursor, background highlight and viewport follow Normal/Insert movement without changing mode, focus or contents.')
    finally:
        editor.close()
