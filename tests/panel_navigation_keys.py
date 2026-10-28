"""Panel selection restores completion expression mappings without inserting key bytes."""
from pathlib import Path
import tempfile
import time

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-panel-navigation-keys-') as directory:
    root = Path(directory)
    path = root / 'example.lua'
    content = ['local value = 1', 'local other = 2', 'return value + other']
    path.write_text('\n'.join(content) + '\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...)', str(path))
        document = editor.lua('return vim.api.nvim_get_current_buf()')
        main = editor.lua('return vim.api.nvim_get_current_win()')

        def key(keys):
            editor.call('nvim_input', keys)
            time.sleep(.1)
            editor.lua('return true')

        # Blink attaches its local expression mappings on InsertEnter. Startup
        # already being in Insert can otherwise leave the arrows unmapped here.
        key('<Esc>i')
        editor.wait(lambda: editor.lua('return vim.fn.maparg("<Up>","i",false,true).expr') == 1, 'Completion mappings attached')
        editor.lua('_G.navigation_up=vim.fn.maparg("<Up>","i",false,true);'
                   '_G.navigation_down=vim.fn.maparg("<Down>","i",false,true)')
        assert editor.lua('return _G.navigation_up.replace_keycodes') == 0

        def arrows():
            assert editor.lua('return vim.fn.mode()') == 'i'
            for arrow, saved in (('<Up>', 'navigation_up'), ('<Down>', 'navigation_down')):
                assert editor.lua('local key,saved=...;local m=vim.fn.maparg(key,"i",false,true);'
                                  'return m.callback==_G[saved].callback and m.expr==_G[saved].expr '
                                  'and m.replace_keycodes==_G[saved].replace_keycodes', arrow, saved), 'Restore the exact completion mapping'
            editor.call('nvim_win_set_cursor', main, [2, 5])
            key('<Up>')
            assert editor.call('nvim_win_get_cursor', main)[0] == 1
            key('<Down>')
            assert editor.call('nvim_win_get_cursor', main)[0] == 2
            assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == content, 'Arrows must not insert internal key bytes'
            assert not editor.lua('return vim.bo[...].modified', document)

        for sequence in ('<M-a><Esc>', '<M-a><CR>', '<M-a><M-a><Esc>', '<M-a><M-a><CR>'):
            key(sequence)
            arrows()

        # Visit sidebar tabs and Symbols, then accept the editor spatially.
        key('<M-a><Left><CR>')
        assert editor.lua('return vim.bo.filetype') == 'neo-tree'
        key('<M-a><M-a><Right><Left><Esc><M-a><Down><CR>')
        assert editor.lua('return vim.bo.filetype') == 'aerial'
        key('<M-a><Up><Right><CR>')
        assert editor.lua('return vim.api.nvim_get_current_win()') == main
        arrows()
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: real completion arrow callbacks preserve replace_keycodes=false across tab acceptance/cancellation, '
              'panel cancellation and Files/Symbols visits; Up/Down move without changing document text.')
    finally:
        editor.close()
