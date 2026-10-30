"""Horizontal wheels and bars preserve logical cursors and selection endpoints."""
from pathlib import Path
import tempfile
import time

from ui import Editor


clipboard = ('lua _G.horizontal_clip={};vim.g.clipboard={name="horizontal-test",cache_enabled=0,'
             'copy={["+"]=function(lines,kind) _G.horizontal_clip={lines=lines,kind=kind} end,["*"]=function() end},'
             'paste={["+"]=function() return {{},"v"} end,["*"]=function() return {{},"v"} end}}')

with tempfile.TemporaryDirectory(prefix='nvim-horizontal-selection-') as directory:
    root = Path(directory)
    path = root / 'document.txt'
    original = [f'{index:03} ' + '0123456789' * 60 for index in range(1, 101)]
    original[19] = '\tżółw 界 ' + 'abcdefghij' * 60
    original[29] = 'short'
    path.write_text('\n'.join(original) + '\n')
    editor = Editor(root, root / 'state', args=('--cmd', clipboard))
    try:
        editor.lua('require("config.ide").open_file(...)', str(path))
        win = editor.lua('return require("config.ide").editor_window()')
        document = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.wait(lambda: editor.lua('return require("config.hscroll").bars[...]~=nil', win), 'Horizontal scrollbar')

        def pump():
            time.sleep(.08)
            editor.lua('vim.cmd("redraw!")')

        def view():
            return editor.lua('return vim.api.nvim_win_call(...,vim.fn.winsaveview)', win)

        def logical():
            return editor.lua('local types={v="v",s="v",V="V",S="V",[string.char(22)]=string.char(22),[string.char(19)]=string.char(22)};'
                              'local m=vim.fn.mode();return {mode=m,cursor=vim.fn.getpos("."),anchor=types[m] and vim.fn.getpos("v") or nil,'
                              'text=types[m] and vim.fn.getregion(vim.fn.getpos("v"),vim.fn.getpos("."),'
                              '{type=types[m],exclusive=vim.o.selection=="exclusive"}) or nil,guicursor=vim.o.guicursor}')

        def prepare(mode='n', row=10, column=9, reverse=False):
            editor.lua('require("config.selection_scroll").restore();vim.cmd("stopinsert");'
                       'vim.api.nvim_set_current_win(...);vim.api.nvim_feedkeys(vim.keycode("<Esc>"),"ni",false)', win)
            pump()
            editor.lua('vim.api.nvim_buf_set_lines(0,0,-1,false,...);vim.bo.modified=false;'
                       'vim.wo.wrap=false;vim.wo.sidescrolloff=7;vim.wo.scrolloff=3', original)
            anchor = [row, column]
            cursor = [row + 2, column + 12] if not reverse else [row - 2, column - 12]
            editor.call('nvim_win_set_cursor', win, anchor)
            if mode in ('v', 'V', '\x16', 's', 'S', '\x13'):
                editor.lua('local kind=...;vim.cmd.normal({args={kind},bang=true})', {'s': 'v', 'S': 'V', '\x13': '\x16'}.get(mode, mode))
                editor.call('nvim_win_set_cursor', win, cursor)
                if mode in ('s', 'S', '\x13'):
                    editor.lua('vim.api.nvim_feedkeys(vim.keycode("<C-g>"),"ni",false)')
            elif mode == 'i':
                editor.lua('vim.cmd("startinsert")')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == mode, 'Prepared mode ' + repr(mode))
            editor.lua('local v=vim.fn.winsaveview();v.leftcol=math.max(0,v.col-35);v.topline=math.max(1,v.lnum-5);vim.fn.winrestview(v)')
            pump()
            return logical(), view()

        def wheel(direction, count=18, modifiers=''):
            row, col = editor.lua('local w=...;local p=vim.api.nvim_win_get_position(w);local i=vim.fn.getwininfo(w)[1];'
                                  'return {p[1]+i.winbar+3,p[2]+i.textoff+8}', win)
            for _ in range(count):
                editor.call('nvim_input_mouse', 'wheel', direction, modifiers, 0, row, col)
            pump()

        def parked(saved):
            state = editor.lua('return require("config.selection_scroll").state')
            assert state and state['cursor'] == saved['cursor'], (saved, state)
            assert state.get('anchor') == saved.get('anchor'), (saved, state)
            assert editor.lua('return vim.fn.mode()') == saved['mode']
            assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == original
            assert not editor.lua('return vim.bo[...].modified', document)
            assert editor.lua('return vim.o.guicursor') == 'a:DesktopSelectionScrollCursor'

        def return_to(saved, initial):
            editor.lua('require("config.hscroll").set(...,select(2,...))', win, initial['leftcol'])
            pump()
            assert view()['leftcol'] == initial['leftcol']
            actual = logical()
            assert actual['cursor'] == saved['cursor'] and actual.get('anchor') == saved.get('anchor'), (saved, actual)
            assert actual.get('text') == saved.get('text')
            assert actual['guicursor'] == saved['guicursor']

        for mode in ('n', 'i', 'v', 'V', '\x16', 's', 'S', '\x13'):
            saved, initial = prepare(mode)
            wheel('right')
            assert view()['leftcol'] > 50
            parked(saved)
            if mode in ('v', 's', '\x16', '\x13'):
                visual = editor.lua('return vim.api.nvim_get_hl(0,{name="DesktopSelectionScrollRange",link=false}).bg')
                point = editor.lua('local w,row=...;local p=vim.fn.screenpos(w,row,vim.fn.winsaveview().leftcol+9);return {p.row-1,p.col-1}', win, 11)
                selected = editor.highlights[editor.attributes[point[0]][point[1]]].get('background') == visual
                assert selected == (mode in ('v', 's')), 'Only the original range is painted after horizontal scrolling'
                if mode in ('v', 's'):
                    point = editor.lua('local w=...;local p=vim.fn.screenpos(w,12,vim.fn.winsaveview().leftcol+9);return {p.row-1,p.col-1}', win)
                    assert editor.highlights[editor.attributes[point[0]][point[1]]].get('background') != visual, 'Clamped native endpoint must not extend the range'
            return_to(saved, initial)
            if mode not in ('n', 'i'):
                wheel('right')
                editor.call('nvim_input', '<C-c>')
                expected = saved['text'] + ([''] if mode in ('V', 'S', '\x16', '\x13') else [])
                editor.wait(lambda: editor.lua('return _G.horizontal_clip.lines') == expected, 'Copy retains offscreen selection')
                assert editor.lua('return require("config.selection_scroll").state') is None
                assert editor.lua('return vim.wo.sidescrolloff') == 7

        # A reversed rectangular/line/character selection can leave the right
        # edge as well as the left, with the anchor and exact text unchanged.
        for mode in ('v', 'V', '\x16', 's', 'S', '\x13'):
            saved, initial = prepare(mode, column=430, reverse=True)
            wheel('left', 50)
            parked(saved)
            return_to(saved, initial)

        # The custom bar must capture the gesture without treating its press
        # as a new text selection or allowing its release to activate the editor.
        saved, initial = prepare('s')
        b = editor.lua('local b=require("config.hscroll").bars[...];local p=vim.api.nvim_win_get_position(b.win);'
                       'return {row=p[1],col=p[2],width=vim.api.nvim_win_get_width(b.win)}', win)
        editor.call('nvim_input_mouse', 'left', 'press', '', 0, b['row'], b['col'] + b['width'] - 1)
        pump()
        parked(saved)
        editor.call('nvim_input_mouse', 'left', 'drag', '', 0, b['row'], b['col'])
        editor.call('nvim_input_mouse', 'left', 'release', '', 0, b['row'], b['col'])
        pump()
        return_to(saved, initial)
        assert editor.lua('return vim.fn.mode()') == 's'

        saved, _ = prepare('i')
        editor.click(b['row'], b['col'] + b['width'] - 1)
        parked(saved)
        editor.call('nvim_input', 'X')
        expected = original[9][:9] + 'X' + original[9][9:]
        editor.wait(lambda: editor.call('nvim_buf_get_lines', document, 9, 10, False) == [expected], 'Typing with the pointer still over the bar restores the original column')
        assert editor.lua('return require("config.selection_scroll").state') is None

        # Combined axes and terminal paste restore both logical endpoints.
        saved, _ = prepare('s')
        wheel('right')
        wheel('down', 20)
        parked(saved)
        assert editor.call('nvim_paste', 'PASTE', False, -1)
        first, last = saved['anchor'], saved['cursor']
        expected = original[:first[1] - 1] + [original[first[1] - 1][:first[2] - 1] + 'PASTE' + original[last[1] - 1][last[2] - 1:]] + original[last[1]:]
        editor.wait(lambda: editor.call('nvim_buf_get_lines', document, 0, -1, False) == expected, 'Paste uses the original offscreen range')

        saved, _ = prepare('s')
        wheel('right')
        editor.call('nvim_input', 'X')
        expected = original[:9] + [original[9][:9] + 'X' + original[11][21:]] + original[12:]
        editor.wait(lambda: editor.call('nvim_buf_get_lines', document, 0, -1, False) == expected, 'Typing replaces the original horizontally hidden range')
        saved, _ = prepare('n')
        wheel('right')
        editor.call('nvim_input', '<Down>')
        editor.wait(lambda: editor.lua('return vim.api.nvim_win_get_cursor(0)') == [11, 9], 'Keyboard movement resumes at the original preferred column')

        # Literal typing uses column 10 even after the physical caret was
        # moved far away to keep the horizontally scrolled viewport stable.
        for row, column in ((10, 9), (20, len('\tżółw 界 '.encode()) + 2), (30, 2)):
            saved, _ = prepare('i', row=row, column=column)
            wheel('right')
            parked(saved)
            editor.call('nvim_input', 'X')
            expected = original[row - 1].encode()[:column] + b'X' + original[row - 1].encode()[column:]
            editor.wait(lambda: editor.call('nvim_buf_get_lines', document, row - 1, row, False) == [expected.decode()], 'Typing restores byte/virtual cursor position')
            assert editor.lua('return require("config.selection_scroll").state') is None
            assert editor.lua('return vim.wo.sidescrolloff') == 7
            assert editor.lua('return vim.wo.virtualedit') == 'onemore'

        saved, _ = prepare('i')
        wheel('down', 18, 'S')
        parked(saved)
        left = view()['leftcol']
        point = editor.lua('local w=...;local p=vim.api.nvim_win_get_position(w);local i=vim.fn.getwininfo(w)[1];'
                           'return {p[1]+i.winbar+3,p[2]+i.textoff+8}', win)
        editor.click(*point)
        editor.wait(lambda: editor.lua('return require("config.selection_scroll").state') is None, 'Fresh click discards the old logical position')
        assert view()['leftcol'] >= left - 2, 'Fresh click does not jump to the old cursor'
        assert editor.lua('return vim.fn.col(".")') > 50
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: wheel/Shift-wheel and bar preserve offscreen Normal/Insert cursors and all six selection modes; '
              'reversed and combined-axis ranges, copy/paste, Unicode/tabs/short lines, typing, fresh clicks and window settings survive.')
    finally:
        editor.close()
