"""Command-line wq saves/closes a document without closing the editor split."""
from pathlib import Path
import subprocess
import tempfile

from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-write-close-') as directory:
    root = Path(directory)
    first, second = root / 'first.txt', root / 'second.txt'
    first.write_text('First document\n')
    second.write_text('Second document\n')
    subprocess.run(['git', 'init', '-b', 'main', str(root)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=UI Test', '-c', 'user.email=ui@example.invalid',
                    'commit', '-m', 'Baseline'], check=True, stdout=subprocess.DEVNULL)
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...)', str(first))
        firstbuf = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.lua('vim.api.nvim_buf_set_lines(0,0,-1,false,{"Unsaved first"})')
        editor.lua('require("config.ide").open_file(...)', str(second))
        secondbuf = editor.lua('return vim.api.nvim_get_current_buf()')
        main = editor.lua('return require("config.ide").editor_window()')
        windows = editor.lua('local r={};for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                             'if vim.api.nvim_win_get_config(w).relative=="" then r[#r+1]=w end end;return r')

        def closed(buf):
            return editor.lua('return not vim.api.nvim_buf_is_valid(...) or not vim.bo[...].buflisted', buf)

        def command(text):
            editor.call('nvim_input', '<Esc>')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Normal before command')
            editor.call('nvim_input', ':' + text + '<CR>')

        def intact():
            assert editor.lua('return vim.api.nvim_win_is_valid(...)', main), 'Main editor survives wq'
            assert editor.lua('local r={};for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                              'if vim.api.nvim_win_get_config(w).relative=="" then r[#r+1]=w end end;return r') == windows

        editor.lua('vim.api.nvim_buf_set_lines(0,0,-1,false,{"Saved second"})')
        command('wq')
        editor.wait(lambda: closed(secondbuf), 'wq closes the document card')
        intact()
        assert second.read_text() == 'Saved second\n'
        assert not closed(firstbuf)
        assert editor.lua('return vim.api.nvim_buf_get_lines(...,0,-1,false)', firstbuf) == ['Unsaved first']
        assert editor.lua('return vim.bo[...].modified', firstbuf)

        editor.lua('require("config.ide").open_file(nil,...)', firstbuf)
        command('wquit')
        editor.wait(lambda: closed(firstbuf), 'wquit closes the last file card')
        intact()
        assert first.read_text() == 'Unsaved first\n'
        assert editor.lua('return require("config.ide").is_document(vim.api.nvim_win_get_buf(...))', main)

        editor.lua('require("config.ide").open_file(...)', str(second))
        failedbuf = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.lua('vim.api.nvim_buf_set_lines(0,0,-1,false,{"Keep after failed save"});vim.bo.readonly=true')
        command('wq')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') != 'c', 'Failed write finishes command')
        intact()
        assert not closed(failedbuf)
        assert editor.lua('return vim.bo[...].modified', failedbuf)
        assert second.read_text() == 'Saved second\n'
        if editor.lua('return vim.fn.mode()') == 'r':
            editor.call('nvim_input', '<CR>')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') != 'r', 'Dismiss failed-write message')
        editor.lua('vim.bo.readonly=false')

        editor.lua('require("config.ide").new_file();vim.api.nvim_buf_set_lines(0,0,-1,false,{"New document"})')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'New document enters Insert')
        newbuf = editor.lua('return vim.api.nvim_get_current_buf()')
        saved = root / 'new.txt'
        # Use the normal save action's prompt without interacting with a picker.
        editor.lua('vim.g.write_close_prompt=false;vim.ui.input=function(opts,cb) '
                   'vim.g.write_close_prompt=opts.prompt;cb(nil) end')
        command('wq')
        editor.wait(lambda: editor.lua('return vim.g.write_close_prompt') == 'Save as: ', 'Unnamed document prompts')
        assert not closed(newbuf), 'Canceled save retains the document'
        assert editor.lua('return vim.bo[...].modified', newbuf)
        intact()
        editor.lua('local path=...;vim.g.write_close_prompt=false;vim.ui.input=function(opts,cb) '
                   'vim.g.write_close_prompt=opts.prompt;cb(path) end', str(saved))
        command('wq')
        editor.wait(lambda: closed(newbuf), 'Unnamed document saves before closing')
        intact()
        assert saved.read_text() == 'New document\n'
        assert editor.lua('return vim.g.write_close_prompt') == 'Save as: '

        editor.lua('require("config.diff").open(...)', str(first))
        editor.wait(lambda: editor.lua('return require("config.diff").active~=nil'), 'Diff opens')
        proxy = editor.lua('return require("config.diff").active.buf')
        editor.wait(lambda: editor.lua('local d=require("config.diff");return not d.busy '
                                      'and vim.api.nvim_get_current_win()==d.active.right'), 'Diff settles in editor')
        editor.lua('vim.api.nvim_buf_set_lines(0,0,-1,false,{"Saved from diff"})')
        command('wq')
        editor.wait(lambda: closed(proxy), 'wq closes the diff card')
        intact()
        assert first.read_text() == 'Saved from diff\n'
        assert editor.lua('return require("config.diff").active==nil')
        print('PASS: command-line wq/wquit close only the saved document, preserve other edits and panels, '
              'retain failed/canceled saves, and save unnamed/diff documents before closing', flush=True)
    finally:
        editor.close()
