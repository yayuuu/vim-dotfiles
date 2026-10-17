"""q closes the previewed document, with repeated selection and safe unsaved prompts."""
from pathlib import Path
import tempfile
import time

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-panel-tab-close-') as directory:
    root = Path(directory)
    files = [root / name for name in ('modified.txt', 'second.txt', 'current.txt')]
    for path in files:
        path.write_text('Original\n')
    editor = Editor(root, root / 'state')
    try:
        buffers = []
        for path in files:
            editor.lua('require("config.ide").open_file(...)', str(path))
            buffers.append(editor.lua('return vim.api.nvim_get_current_buf()'))
        editor.call('nvim_buf_set_lines', buffers[0], 0, -1, False, ['Unsaved'])
        main = editor.lua('return require("config.ide").editor_window()')
        caret = editor.lua('return vim.o.guicursor')

        def key(keys):
            editor.call('nvim_input', keys)
            time.sleep(.08)
            editor.lua('return true')

        def preview():
            return editor.lua('local s=require("config.panel_navigation").state;'
                              'return s and s.kind=="documents" and s.items[s.index]')

        def closed(buf):
            return editor.lua('return not vim.api.nvim_buf_is_valid(...) or not vim.bo[...].buflisted', buf)

        key('<M-a><Right>')
        assert preview() == buffers[1]
        key('q')
        editor.wait(lambda: closed(buffers[1]) and preview() == buffers[0], 'q closes the highlighted inactive card and selects its neighbor')
        assert editor.lua('return vim.api.nvim_get_current_buf()') == buffers[2], 'Closing a preview must not open another document'

        # Keep the actual shared close workflow, but answer its asynchronous
        # dialog explicitly so cancellation and saving can be checked precisely.
        editor.lua('_G.tab_close_select=vim.ui.select;vim.ui.select=function(items,opts,cb) '
                   '_G.tab_close_choices=items;_G.tab_close_answer=cb end')
        key('q')
        assert preview() is None and not closed(buffers[0])
        assert editor.lua('return _G.tab_close_choices') == ['Save', "Don't save", 'Cancel']
        editor.lua('_G.tab_close_answer("Cancel")')
        editor.wait(lambda: preview() == buffers[0], 'Cancel retains the highlighted modified card')
        assert editor.call('nvim_buf_get_lines', buffers[0], 0, -1, False) == ['Unsaved']
        assert files[0].read_text() == 'Original\n'
        key('q')
        editor.lua('_G.tab_close_answer("Save");vim.ui.select=_G.tab_close_select')
        editor.wait(lambda: closed(buffers[0]) and preview() == buffers[2], 'Save closes the card and continues selection')
        assert files[0].read_text() == 'Unsaved\n'
        key('<CR>')
        assert preview() is None and editor.lua('return vim.api.nvim_get_current_buf()') == buffers[2]
        assert editor.lua('return vim.o.guicursor') == caret
        key('q')
        assert editor.call('nvim_buf_get_lines', buffers[2], 0, 1, False)[0].startswith('q'), 'q outside the picker still types normally'
        editor.call('nvim_buf_set_lines', buffers[2], 0, -1, False, ['Original'])
        editor.lua('vim.bo.modified=false')
        key('<M-a>q')
        editor.wait(lambda: closed(buffers[2]), 'q closes the last original document')
        assert editor.lua('local s=require("config.panel_navigation").state;return s and s.phase=="tabs" and #s.items==0')
        key('<CR>')
        assert editor.lua('return require("config.panel_navigation").state') is None
        assert editor.call('nvim_win_is_valid', main)
        assert editor.lua('return vim.o.guicursor') == caret
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: q closes inactive/current/last preview cards, retains selection, honors cancel/save, '
              'and restores Enter, typing, caret and the main editor.')
    finally:
        editor.close()
