"""Editing shortcuts finish in Select/Insert, while Escape deliberately enters Normal."""
from pathlib import Path
import tempfile
import time

from ui import Editor

clipboard = ('lua _G.edit_clip={{"PASTED"},"v"};vim.g.clipboard={name="editing-test",cache_enabled=0,'
             'copy={["+"]=function(lines,kind) _G.edit_clip={lines,kind} end,["*"]=function() end},'
             'paste={["+"]=function() return _G.edit_clip end,["*"]=function() return _G.edit_clip end}}')

with tempfile.TemporaryDirectory(prefix='nvim-editing-modes-') as directory:
    root = Path(directory)
    path = root / 'sample.lua'
    original = ['local a = 1', 'local b = 2', 'local c = 3']
    path.write_text('\n'.join(original) + '\n')
    editor = Editor(root, root / 'state', args=('--cmd', clipboard))
    try:
        editor.lua('require("config.ide").open_file(...)', str(path))
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Initial editor input')
        win = editor.lua('return vim.api.nvim_get_current_win()')

        def keys(sequence):
            # Queue Ctrl+C without interrupting the RPC or running a nested
            # input loop that waits indefinitely when Insert is resumed.
            editor.lua('vim.api.nvim_feedkeys(vim.keycode(...),"mt",false)', sequence)
            time.sleep(.08)
            editor.lua('return true')

        def contents():
            return editor.call('nvim_buf_get_lines', document, 0, -1, False)

        def reset(mode='select'):
            keys('<Esc>')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Escape leaves editing')
            editor.lua('local w,lines=...;vim.api.nvim_set_current_win(w);vim.api.nvim_buf_set_lines(0,0,-1,false,lines);'
                       'vim.bo.modified=false;vim.api.nvim_win_set_cursor(0,{1,0});_G.edit_clip={{"PASTED"},"v"}', win, original)
            if mode == 'normal':
                return
            keys('i')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Insert before selection')
            if mode == 'insert':
                return
            if mode == 'mouse':
                points = editor.lua('local w=...;local a=vim.fn.screenpos(w,1,1);local b=vim.fn.screenpos(w,1,6);'
                                    'return {{a.row-1,a.col-1},{b.row-1,b.col-1}}', win)
                editor.call('nvim_input_mouse', 'left', 'press', '', 0, *points[0])
                editor.lua('vim.cmd("redraw!")')
                editor.call('nvim_input_mouse', 'left', 'drag', '', 0, *points[1])
                editor.lua('vim.cmd("redraw!")')
                editor.call('nvim_input_mouse', 'left', 'release', '', 0, *points[1])
            else:
                keys('<S-End>')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') in ('s', 'v'), 'Selected text: ' + mode)
            if mode == 'visual':
                editor.lua('vim.cmd.normal({args={vim.keycode("<C-g>")},bang=true})')
                editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'v', 'Visual text')

        def editing():
            mode = editor.lua('return vim.fn.mode()')
            assert mode in ('i', 's', 'S', '\x13'), ('Unexpected editing mode', mode)
            assert editor.lua('return vim.api.nvim_get_current_win()') == win

        document = editor.lua('return vim.api.nvim_get_current_buf()')
        for mode in ('insert', 'select', 'visual', 'mouse'):
            reset(mode)
            selection = editor.lua('return vim.fn.mode()~="i" and vim.fn.getregion(vim.fn.getpos("v"),vim.fn.getpos("."),'
                                   '{type="v",exclusive=true}) or nil')
            keys('<C-c>')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Copy resumes Insert: ' + mode)
            assert contents() == original and not editor.lua('return vim.bo.modified'), 'Copy preserves text and modification state'
            if selection:
                assert editor.lua('return _G.edit_clip[1]') == selection
            keys('XYZ')
            assert 'XYZ' in contents()[0], 'Typing after Copy inserts literal text'

        for mode in ('select', 'visual'):
            for shortcut, expected in (
                ('<C-x>', ['', *original[1:]]),
                ('<C-v>', ['PASTED', *original[1:]]),
                ('<C-d>', [original[0] * 2, *original[1:]]),
                ('<C-q>', ['-- ' + original[0], *original[1:]]),
                ('<C-S-Down>', [original[1], original[0], original[2]]),
            ):
                reset(mode)
                keys(shortcut)
                assert contents() == expected, (mode, shortcut, contents())
                editing()

        # Typeahead must reach Insert, even when delivered with the shortcut.
        reset()
        keys('<C-c>XYZ')
        assert contents()[0].count('XYZ') == 1 and contents()[1:] == original[1:]
        editing()
        reset()
        keys('<C-x>XYZ')
        assert contents() == ['XYZ', *original[1:]], contents()
        editing()

        for shortcut in ('<Left>', '<Right>', '<Up>', '<Down>', '<Home>', '<End>', '<Del>', '<BS>'):
            reset()
            keys(shortcut)
            editing()

        reset('insert')
        keys('XYZ<S-End><C-z>')
        assert contents() == original, ('Undo from selection', contents())
        editing()
        keys('<S-End><C-y>')
        assert contents() == ['XYZ' + original[0], *original[1:]], ('Redo from selection', contents())
        editing()

        reset()
        keys('<Tab>')
        assert contents()[0].lstrip() == original[0] and contents()[0].startswith(' ')
        editing()
        keys('<S-Tab>')
        assert contents() == original
        editing()
        keys('<C-s>')
        editing()
        assert not editor.lua('return vim.bo.modified')
        keys('<Esc>')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Escape from Select stays Normal')
        keys('<Down>')
        assert editor.lua('return vim.fn.mode()') == 'n', 'Normal navigation after Escape remains available'
        reset('normal')
        keys('<C-c>')
        assert editor.lua('return vim.fn.mode()') == 'n', 'Explicit Normal-mode workflow is preserved'

        reset()
        editor.lua('require("config.ide").menu("Edit",true)')
        keys('<Down><Down><Down><CR>')  # Undo, Redo, Copy (skip separator).
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Edit > Copy resumes Insert')
        assert contents() == original
        assert editor.lua('return _G.edit_clip[1]') == [original[0]]
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: keyboard/mouse and Visual Copy resumes Insert; cut/paste/duplicate/comment/move/indent/save/undo/redo retain editing; '
              'queued typing remains literal; Edit > Copy shares the behavior; Escape preserves deliberate Normal navigation.')
    finally:
        editor.close()
