"""Large diffs stay unloaded; commit preview remains closable while Git is running."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import time
from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-commit-large-') as directory:
    root = Path(directory)
    repo = root / 'repo'
    repo.mkdir()
    git_bin = shutil.which('git')
    def git(*args):
        return subprocess.check_output([git_bin, '-C', str(repo), *args], stderr=subprocess.STDOUT).decode().strip()
    git('init', '-b', 'main')
    git('config', 'user.name', 'UI Test')
    git('config', 'user.email', 'ui@example.invalid')
    source = repo / 'small [literal].txt'
    deleted = repo / 'deleted.min.js'
    source.write_text('Original content\n')
    deleted.write_text('DELETED_BUNDLE' + 'x' * 1_000_000 + '\n')
    git('add', '.')
    git('commit', '-m', 'Baseline')
    source.write_text('Changed small content\n')
    (repo / 'bundle.min.js').write_text('MINIFIED_BUNDLE' + 'x' * 2_000_000 + '\n')
    (repo / 'many-lines.txt').write_text(''.join(f'Large line {i}\n' for i in range(2500)))
    deleted.unlink()
    git('add', '.')
    git('commit', '-m', 'Large generated files and a small change')
    # Delay metadata on demand so Esc/close can be checked during real Git work.
    bindir = root / 'bin'
    bindir.mkdir()
    delay = root / 'delay'
    wrapper = bindir / 'git'
    wrapper.write_text('#!/usr/bin/python3\nimport os,sys,time\n'
                       f'if "--raw" in sys.argv and os.path.exists({str(delay)!r}): time.sleep(2)\n'
                       f'os.execv({git_bin!r},[{git_bin!r},*sys.argv[1:]])\n')
    wrapper.chmod(0o755)
    previous_path = os.environ['PATH']
    os.environ['PATH'] = str(bindir) + os.pathsep + previous_path
    try:
        editor = Editor(repo, root / 'state')
    finally:
        os.environ['PATH'] = previous_path
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert");'
                   'vim.api.nvim_buf_set_lines(0,0,-1,false,{"Unsaved document"});'
                   'vim.g.ide_git_autofetch=false;require("config.ide").git_explorer()', str(source))
        document = editor.lua('return vim.fn.bufnr(...)', str(source))
        terminal = editor.lua('return require("config.terminals").active')
        editor.wait(lambda: editor.lua('local s=require("config.sidebar");return s.commits and #s.commits==2 '
                                       'and not s.changing and not require("config.layout").scaling'), 'Git layout settles')
        layout = editor.lua('return vim.fn.winlayout()')
        native_windows = editor.lua('local r={};for _,w in ipairs(vim.api.nvim_list_wins()) do '
                                   'if vim.api.nvim_win_get_config(w).relative=="" then '
                                   'r[tostring(w)]={vim.api.nvim_win_get_width(w),vim.api.nvim_win_get_height(w)} end end;return r')
        def open_preview():
            editor.lua('local s=require("config.sidebar");vim.api.nvim_set_current_win(s.history_win);s.open_commit(1)')
            editor.wait(lambda: editor.lua('local p=Snacks.picker.get()[1];return p and p.shown'), 'Preview opens')
        def text():
            return editor.lua('local p=Snacks.picker.get()[1];return p and '
                              'table.concat(vim.api.nvim_buf_get_lines(p.preview.win.buf,0,-1,false),string.char(10))') or ''
        def closed():
            editor.wait(lambda: editor.lua('return #Snacks.picker.get()==0'), 'All picker panes close')
            assert editor.lua('return vim.fn.winlayout()') == layout, 'Git status, commits and editor layout survive'
            assert editor.lua('local r={};for _,w in ipairs(vim.api.nvim_list_wins()) do '
                              'if vim.api.nvim_win_get_config(w).relative=="" then '
                              'r[tostring(w)]={vim.api.nvim_win_get_width(w),vim.api.nvim_win_get_height(w)} end end;return r') == native_windows
            assert editor.lua('return vim.api.nvim_get_current_win()==require("config.sidebar").history_win')
        start = time.monotonic()
        open_preview()
        editor.wait(lambda: 'Changed small content' in text(), 'Small patch loads independently')
        assert time.monotonic() - start < 5, 'Generated files must not stall the UI'
        assert 'MINIFIED_BUNDLE' not in text() and 'DELETED_BUNDLE' not in text() and 'Large line 2499' not in text()
        assert 'Large file' in text() and 'Large diff' in text()
        assert editor.lua('local s=Snacks.picker.get()[1].ide_commit_preview;local count=0;'
                          'for _,f in ipairs(s.files) do if f.reason then assert(not f.patch and not f.loading);count=count+1 end end;return count') == 3
        editor.call('nvim_input', 'q')
        closed()

        # Esc works in the input, list and preview; q is a close action in input too.
        for pane in ['input', 'list', 'preview']:
            open_preview()
            editor.lua('local p=Snacks.picker.get()[1];vim.cmd("stopinsert");vim.api.nvim_set_current_win(p[...].win.win)', pane)
            editor.call('nvim_input', '<Esc>')
            closed()

        open_preview()
        editor.wait(lambda: 'Large file' in text(), 'Large file header ready')
        position = editor.lua('local p=Snacks.picker.get()[1];local s=p.ide_commit_preview;'
                              'for row,f in pairs(s.rows) do if f.path=="bundle.min.js" then '
                              'local a=vim.fn.screenpos(p.preview.win.win,row,1);return {a.row-1,a.col+3} end end')
        editor.click(*position)
        editor.wait(lambda: 'MINIFIED_BUNDLE' in text(), 'Header click loads only the requested large patch')
        assert '[line shortened]' in text() and 'preview limited' in text()
        assert len(text()) < 20_000, 'Even explicit expansion bounds minified display width'
        button = editor.lua('local p=Snacks.picker.get()[1];local b=require("config.popup_ui").buttons[p.layout.root.win];'
                            'local a=vim.api.nvim_win_get_position(b.win);return {a[1],a[2]+1}')
        editor.click(*button)
        closed()

        delay.touch()
        open_preview()
        state = editor.lua('_G.closed_commit_state=Snacks.picker.get()[1].ide_commit_preview;return _G.closed_commit_state~=nil')
        assert state
        editor.call('nvim_input', '<Esc>')
        closed()
        editor.wait(lambda: editor.lua('return _G.closed_commit_state.closed and next(_G.closed_commit_state.jobs)==nil'), 'Closing cancels pending Git jobs')
        time.sleep(2.1)
        assert editor.lua('return #Snacks.picker.get()==0 and vim.fn.winlayout()') == layout, 'Late jobs never recreate panes'
        assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == ['Unsaved document']
        assert editor.lua('return require("config.terminals").active') == terminal
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'Error executing' not in messages and 'E5108' not in messages, messages
        print('PASS: line-heavy, minified and deleted large files stay unloaded; small patch is responsive; row click loads bounded preview; q/Esc/close button preserve every panel; closing cancels Git jobs and preserves documents/terminals', flush=True)
    except Exception:
        print(editor.lua('return vim.fn.execute("messages")'), flush=True)
        print(text()[:5000], flush=True)
        raise
    finally:
        editor.close()
