"""Wheel scrolling preserves offscreen selections and their copy/edit endpoints."""
from pathlib import Path
import tempfile

from ui import Editor

clipboard = ('lua _G.selection_clip={};vim.g.clipboard={name="selection-test",cache_enabled=0,'
             'copy={["+"]=function(lines,kind) _G.selection_clip={lines=lines,kind=kind} end,'
             '["*"]=function() end},paste={["+"]=function() return {{},"v"} end,'
             '["*"]=function() return {{},"v"} end}}')

with tempfile.TemporaryDirectory(prefix='nvim-selection-scroll-') as directory:
    root = Path(directory)
    file = root / 'document.txt'
    original = [f'line {index:03} alpha beta gamma delta' for index in range(1, 301)]
    file.write_text('\n'.join(original) + '\n')
    editor = Editor(root, root / 'state', args=('--cmd', clipboard))
    try:
        editor.lua('require("config.ide").open_file(...)', str(file))
        editor.call('nvim_input', '<Esc>')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Normal mode')
        win = editor.lua('return require("config.ide").editor_window()')

        def region():
            return editor.lua('local types={v="v",s="v",V="V",S="V",[string.char(22)]=string.char(22),[string.char(19)]=string.char(22)};'
                              'local mode=vim.fn.mode();return {anchor=vim.fn.getpos("v"),cursor=vim.fn.getpos("."),'
                              'mode=mode,text=vim.fn.getregion(vim.fn.getpos("v"),vim.fn.getpos("."),'
                              '{type=types[mode] or "v",exclusive=vim.o.selection=="exclusive"})}')

        def select():
            editor.call('nvim_input', '<Esc>')
            editor.lua('vim.api.nvim_set_current_win(...);vim.cmd("stopinsert");'
                       'vim.api.nvim_win_set_cursor(0,{10,0});vim.cmd("normal! zt")', win)
            first = editor.lua('local p=vim.fn.screenpos(...,12,3);return {p.row-1,p.col-1}', win)
            last = editor.lua('local p=vim.fn.screenpos(...,14,12);return {p.row-1,p.col-1}', win)
            editor.call('nvim_input_mouse', 'left', 'press', '', 0, *first)
            editor.lua('vim.cmd("redraw!")')
            editor.call('nvim_input_mouse', 'left', 'drag', '', 0, *last)
            editor.lua('vim.cmd("redraw!")')
            editor.call('nvim_input_mouse', 'left', 'release', '', 0, *last)
            editor.wait(lambda: editor.lua('return vim.fn.mode()') in ('s', 'v'), 'Mouse selection')
            return region()

        def wheel(direction, count):
            pos = editor.lua('local w=...;local p=vim.api.nvim_win_get_position(w);'
                             'local i=vim.fn.getwininfo(w)[1];return {p[1]+i.winbar+4,p[2]+i.textoff+8}', win)
            for _ in range(count):
                editor.call('nvim_input_mouse', 'wheel', direction, '', 0, *pos)
            editor.lua('vim.cmd("redraw!")')

        saved = select()
        before = editor.lua('return vim.api.nvim_buf_get_lines(0,0,-1,false)')
        wheel('down', 25)
        state = editor.lua('return require("config.selection_scroll").state')
        assert state and state['anchor'] == saved['anchor'] and state['cursor'] == saved['cursor'], (saved, state)
        assert editor.lua('return vim.fn.line("w0")') > saved['cursor'][1], 'Original endpoint left the viewport'
        assert editor.lua('return vim.api.nvim_buf_get_lines(0,0,-1,false)') == before
        # The native, clamped selection must not highlight the newly visible text.
        pos = editor.lua('local p=vim.fn.screenpos(...,vim.fn.line("w0")+3,5);return {p.row-1,p.col-1}', win)
        visual = editor.lua('return vim.api.nvim_get_hl(0,{name="DesktopSelectionScrollRange",link=false}).bg')
        assert editor.highlights[editor.attributes[pos[0]][pos[1]]].get('background') != visual
        wheel('up', 25)
        assert region()['text'] == saved['text'], 'Returning to the original viewport retains the exact range'
        pos = editor.lua('local p=vim.fn.screenpos(...,13,5);return {p.row-1,p.col-1}', win)
        assert editor.highlights[editor.attributes[pos[0]][pos[1]]].get('background') == visual, 'Original range is still highlighted'
        for line, column in ((12, 1), (14, 20)):
            pos = editor.lua('local w,line,column=...;local p=vim.fn.screenpos(w,line,column);return {p.row-1,p.col-1}', win, line, column)
            assert editor.highlights[editor.attributes[pos[0]][pos[1]]].get('background') != visual, 'Highlight does not extend beyond the original endpoints'
        wheel('down', 25)
        editor.lua('vim.wo.winhighlight=vim.wo.winhighlight..",LineNr:CursorLineNr"')
        editor.call('nvim_input', '<C-c>')
        editor.wait(lambda: editor.lua('return _G.selection_clip.lines') == saved['text'], 'Copy uses the original offscreen selection')
        assert editor.lua('return require("config.selection_scroll").state') is None
        assert editor.lua('return vim.wo.winhighlight') == 'LineNr:CursorLineNr', 'Unrelated window mappings survive restoration'
        assert editor.lua('return vim.api.nvim_buf_get_lines(0,0,-1,false)') == before

        # Typing in Select mode must replace the original range, not the range
        # between its anchor and the viewport-clamped native cursor.
        saved = select()
        if saved['mode'] == 'v':
            editor.call('nvim_input', '<C-g>')
        wheel('down', 25)
        editor.call('nvim_input', 'X')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Typing replaces the selection')
        expected = original[:11] + [original[11][:2] + 'X' + original[13][11:]] + original[14:]
        actual = editor.lua('return vim.api.nvim_buf_get_lines(0,0,-1,false)')
        assert actual == expected, (actual[10:15], expected[10:15])
        assert editor.lua('return vim.o.guicursor') != 'a:DesktopSelectionScrollCursor'
        editor.call('nvim_input', '<Esc>')
        editor.lua('vim.api.nvim_buf_set_lines(0,0,-1,false,...)', original)
        saved = select()
        wheel('down', 25)
        assert editor.call('nvim_paste', 'PASTE', False, -1)
        expected = original[:11] + [original[11][:2] + 'PASTE' + original[13][11:]] + original[14:]
        editor.wait(lambda: editor.lua('return vim.api.nvim_buf_get_lines(0,0,-1,false)') == expected, 'Terminal paste replaces the original range')
        editor.call('nvim_input', '<Esc>')
        editor.lua('vim.api.nvim_buf_set_lines(0,0,-1,false,...)', original)
        # Reversed character, whole-line and rectangular ranges must survive
        # moving below the viewport as well as above it.
        for kind in ('v', 'V', '\x16'):
            editor.call('nvim_input', '<Esc>')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Normal before another selection')
            editor.lua('vim.api.nvim_win_set_cursor(0,{160,4});vim.cmd("normal! zz");vim.cmd.normal({...,bang=true});'
                       'vim.api.nvim_win_set_cursor(0,{153,12})', kind)
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == kind, 'Keyboard selection mode')
            saved = region()
            wheel('up', 30)
            state = editor.lua('return require("config.selection_scroll").state')
            assert state and state['cursor'] == saved['cursor'] and state['anchor'] == saved['anchor']
            assert editor.lua('return vim.fn.line("w$")') < saved['cursor'][1]
            editor.call('nvim_input', '<C-c>')
            expected_copy = saved['text'] + ([''] if kind in ('V', '\x16') else [])
            editor.wait(lambda: editor.lua('return _G.selection_clip.lines') == expected_copy, 'Copy preserves reversed/line/block range')
            assert editor.lua('return require("config.selection_scroll").state') is None
            assert 'DesktopSelectionScrollMask' not in editor.lua('return vim.wo.winhighlight')
        saved = select()
        wheel('down', 25)
        clicked_line = editor.lua('return vim.fn.line("w0")+4')
        pos = editor.lua('local p=vim.fn.screenpos(...,vim.fn.line("w0")+4,5);return {p.row-1,p.col-1}', win)
        editor.click(*pos)
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'A fresh click starts editing at the scrolled position')
        assert editor.lua('return require("config.selection_scroll").state') is None
        assert editor.lua('return vim.api.nvim_win_get_cursor(0)[1]') == clicked_line
        assert editor.lua('return vim.fn.line("w0")') > saved['cursor'][1], 'A fresh click must not jump to the old selection'
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: offscreen forward/reversed character, line and block selections; exact copy/typing/paste ranges; no extra highlighting; fresh clicks and window settings preserved.')
    finally:
        editor.close()
