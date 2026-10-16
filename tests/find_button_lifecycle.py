"""Find's Replace button never survives the input that owns it."""
from pathlib import Path
import tempfile
from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-find-lifecycle-') as directory:
    root = Path(directory)
    source = root / 'example.txt'
    source.write_text('needle in document\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.api.nvim_buf_set_lines(0,1,1,false,{"Unsaved notes"})', str(source))
        main = editor.lua('return require("config.ide").main_editor')
        document = editor.lua('return vim.api.nvim_win_get_buf(...)', main)
        def open_find():
            editor.lua('require("config.search").find()')
            editor.wait(lambda: editor.lua('local s=require("config.search");return s.find_button and vim.api.nvim_win_is_valid(s.find_button)'), 'Find button visible')
            return editor.lua('local s=require("config.search");return {s.find_input.win,s.find_button,s.find_input.buf}')
        def buttons():
            return editor.lua('local out={};for _,w in ipairs(vim.api.nvim_list_wins()) do local b=vim.api.nvim_win_get_buf(w);'
                              'if vim.api.nvim_buf_get_lines(b,0,1,false)[1]==" ⇄ " then out[#out+1]=w end end;return out')
        def closed(parent, button):
            editor.wait(lambda: not editor.lua('return vim.api.nvim_win_is_valid(...)', parent), 'Input closes')
            editor.wait(lambda: not editor.lua('return vim.api.nvim_win_is_valid(...)', button), 'Replace button closes with its input')
            assert not buttons(), 'No orphan Replace buttons'
            assert editor.lua('local s=require("config.search");return s.find_input==nil and s.find_button==nil')

        parent, button, _ = open_find()
        # WinClosed does not recursively fire for another window closed from it.
        editor.lua('local trigger=vim.api.nvim_open_win(vim.api.nvim_create_buf(false,true),false,'
                   '{relative="editor",row=10,col=10,width=4,height=1,noautocmd=true});'
                   'vim.api.nvim_create_autocmd("WinClosed",{pattern=tostring(trigger),once=true,callback=function() '
                   'require("config.search").find_input:execute("cancel") end});'
                   'vim.api.nvim_win_close(trigger,true)')
        closed(parent, button)

        parent, button, _ = open_find()
        for _ in range(3):
            editor.call('nvim_input', '<C-f>')
            editor.lua('vim.wait(20)')
            assert editor.lua('return require("config.search").find_input.win') == parent, 'Repeated Find focuses the same input'
            assert buttons() == [button]
        editor.call('nvim_input', 'needle<CR>')
        closed(parent, button)
        assert editor.lua('return vim.fn.getreg("/")') == r'\Vneedle'

        parent, button, _ = open_find()
        editor.lua('vim.api.nvim_win_close(...,true)', parent)
        closed(parent, button)
        parent, button, _ = open_find()
        editor.lua('local s=require("config.search");s.find_input:execute("cancel");require("config.search").find()')
        editor.wait(lambda: editor.lua('local s=require("config.search");return s.find_button and s.find_button~=(...)', button), 'Replacement Find opens')
        new_button = editor.lua('return require("config.search").find_button')
        editor.lua('vim.wait(100)')
        assert buttons() == [new_button], 'Old close callbacks leave the replacement intact'
        assert editor.lua('return vim.api.nvim_win_is_valid(...)', new_button)
        editor.lua('require("config.search").find_input:execute("cancel")')
        editor.wait(lambda: not buttons(), 'Last Find cleanup')
        assert editor.lua('return vim.api.nvim_win_get_buf(...)', main) == document
        assert editor.lua('return vim.bo[...].modified', document)
        assert editor.lua('return vim.api.nvim_buf_get_lines(...,0,-1,false)', document) == ['needle in document', 'Unsaved notes']
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: Find buttons removed after nested close, confirmation and native close; repeated Find and replacement callbacks keep one owner; unsaved document preserved', flush=True)
    except Exception:
        print(editor.lua('return vim.fn.execute("messages")'), flush=True)
        print(buttons(), flush=True)
        raise
    finally:
        editor.close()
