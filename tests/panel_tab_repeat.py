"""Held q never reaches document text during close callbacks, prompts or the last tab."""
from pathlib import Path
import tempfile
import time

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-panel-tab-repeat-') as directory:
    root = Path(directory)
    editor = Editor(root, root / 'state')
    try:
        buffers = []
        content = ['Original content', 'Second line']
        for index in range(8):
            path = root / f'document-{index}.txt'
            path.write_text('\n'.join(content) + '\n')
            editor.lua('require("config.ide").open_file(...)', str(path))
            buffers.append(editor.lua('return vim.api.nvim_get_current_buf()'))
        main = editor.lua('return require("config.ide").editor_window()')
        caret = editor.lua('return vim.o.guicursor')

        def key(keys, delay=.04):
            editor.call('nvim_input', keys)
            time.sleep(delay)
            editor.lua('return true')

        def clean_documents():
            for buf in buffers:
                if editor.call('nvim_buf_is_valid', buf) and editor.lua('return vim.bo[...].buflisted', buf):
                    actual = editor.call('nvim_buf_get_lines', buf, 0, -1, False)
                    assert actual == content, ('Repeated q leaked into a document', actual)
                    assert not editor.lua('return vim.bo[...].modified', buf)

        key('<M-a><M-a><Right>')
        key('q<CR>')
        clean_documents()
        assert editor.lua('return require("config.panel_navigation").state') is None, 'Queued Enter accepts after closing'
        key('<M-a><M-a>')
        for _ in buffers:
            # Include queued repeats within one input batch as well as repeats
            # arriving after the asynchronous close callback has completed.
            key('q' * 12)
            clean_documents()
        assert all(not editor.call('nvim_buf_is_valid', buf) or not editor.lua('return vim.bo[...].buflisted', buf) for buf in buffers)
        key('q' * 30)
        assert editor.lua('local s=require("config.panel_navigation").state;return s and s.phase=="tabs"')
        assert editor.call('nvim_get_current_line') == '', 'Held q cannot edit the blank editor after the last card'
        assert not editor.lua('return vim.bo.modified')
        key('<Left><Right><CR>')
        assert editor.lua('return require("config.panel_navigation").state') is None
        assert editor.lua('return vim.o.guicursor') == caret
        key('q')
        assert editor.call('nvim_get_current_line') == 'q', 'Enter deliberately restores normal typing'

        # Model a slow save/discard/cancel dialog without moving focus away
        # from the document: all repeats must be consumed until it resolves.
        path = root / 'modified.txt'
        path.write_text('Keep unsaved text\n')
        editor.lua('vim.bo.modified=false;require("config.ide").open_file(...)', str(path))
        document = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.call('nvim_buf_set_lines', document, 0, -1, False, ['Unsaved text'])
        editor.lua('_G.repeat_select=vim.ui.select;vim.ui.select=function(_,_,cb) '
                   '_G.repeat_dialogs=(_G.repeat_dialogs or 0)+1;_G.repeat_answer=cb end')
        key('<M-a><M-a>' + 'q' * 30)
        key('q' * 20)
        assert editor.call('nvim_get_current_line') == 'Unsaved text'
        assert editor.lua('return _G.repeat_dialogs') == 1
        editor.lua('_G.repeat_answer("Cancel");vim.ui.select=_G.repeat_select')
        editor.wait(lambda: editor.lua('return require("config.panel_navigation").state~=nil'), 'Resume selection after canceled close')
        key('<Esc>q')
        assert editor.lua('return require("config.panel_navigation").state') is None
        assert 'q' in editor.call('nvim_get_current_line'), 'Esc deliberately restores typing'
        key('<M-a><M-a>q')
        editor.wait(lambda: editor.lua('return #Snacks.picker.get()>0'), 'Real unsaved-changes dialog')
        key('<Esc>')
        editor.wait(lambda: editor.lua('return #Snacks.picker.get()==0'), 'Esc reaches the real save dialog')
        assert editor.lua('local n=require("config.panel_navigation");return n.state==nil and n.closing==nil')
        assert editor.call('nvim_win_is_valid', main)
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: queued/held q safely closes repeated cards, stays guarded during slow prompts and after the last tab, '
              'and restores typing only after explicit Enter/Esc.')
    finally:
        editor.close()
