"""Clicking the sidebar graph renders a real commit and closes cleanly."""
from pathlib import Path
import subprocess
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-commit-preview-') as directory:
    root = Path(directory)
    repo = root / 'project'
    repo.mkdir()

    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.STDOUT).decode().strip()

    git('init', '-b', 'main')
    git('config', 'user.name', 'UI Test')
    git('config', 'user.email', 'ui@example.invalid')
    source = repo / 'example.txt'
    source.write_text('Original content\n')
    git('add', '.')
    git('commit', '-m', 'Baseline')
    source.write_text('Committed preview content\n')
    git('add', '.')
    subject = 'feat(ui): Preview commit ✓'
    git('commit', '-m', subject)
    head = git('rev-parse', 'HEAD')

    editor = Editor(repo, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert");'
                   'vim.api.nvim_buf_set_lines(0,0,-1,false,{"Unsaved editor content"});'
                   'vim.g.ide_git_autofetch=false;require("config.ide").git_explorer()', str(source))
        editor.wait(lambda: editor.lua('local s=require("config.sidebar");return s.commits and s.commits[1] and s.commits[1].commit') == head,
                    'Sidebar graph starts at the fixture HEAD')
        editor.wait(lambda: not editor.lua('return require("config.sidebar").changing or require("config.layout").scaling'),
                    'Sidebar layout settles')
        layout = editor.lua('return vim.fn.winlayout()')
        for row, message, content in ((1, subject, 'Committed preview content'), (2, 'Baseline', 'Original content')):
            position = editor.lua('local w=require("config.sidebar").history_win;local p=vim.api.nvim_win_get_position(w);'
                                  'local info=vim.fn.getwininfo(w)[1];return {p[1]+(...)-info.topline+(vim.wo[w].winbar~="" and 1 or 0),p[2]+4}', row)
            editor.click(*position)
            editor.wait(lambda: editor.lua('local p=Snacks.picker.get()[1];return p and p.shown'), 'Click opens commit picker')
            editor.wait(lambda: editor.lua('local p=Snacks.picker.get()[1];if not p then return false end;'
                                          'return table.concat(vim.api.nvim_buf_get_lines(p.list.win.buf,0,-1,false),string.char(10)):find(...,1,true)~=nil', message),
                        'Commit subject renders in the list')
            editor.wait(lambda: editor.lua('local p=Snacks.picker.get()[1];if not p or not p.preview.win:valid() then return false end;'
                                          'local text=table.concat(vim.api.nvim_buf_get_lines(p.preview.win.buf,0,-1,false),string.char(10));'
                                          'return text:find(...,1,true)~=nil and text:find(select(2,...),1,true)~=nil '
                                          'and text:find("example.txt",1,true)~=nil', message, content),
                        'Preview contains the selected commit and patch')
            editor.wait(lambda: editor.lua('local p=Snacks.picker.get()[1];return p and require("config.popup_ui").buttons[p.layout.root.win]~=nil'),
                        'Commit picker has a close button')
            close_position = editor.lua('local p=Snacks.picker.get()[1];local b=require("config.popup_ui").buttons[p.layout.root.win];'
                                        'local pos=vim.api.nvim_win_get_position(b.win);return {pos[1],pos[2]+1}')
            editor.click(*close_position)
            editor.wait(lambda: editor.lua('return #Snacks.picker.get()==0'), 'Close button closes all commit picker panes')
            assert editor.lua('return vim.fn.winlayout()') == layout, 'Native panel layout is preserved'
        assert editor.lua('return vim.api.nvim_buf_get_lines(vim.fn.bufnr(...),0,-1,false)', str(source)) == ['Unsaved editor content']
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'E5108' not in messages and 'attempt to index' not in messages, messages
        print('PASS: graph clicks render conventional/ordinary commit subjects and patches; close button preserves panels and unsaved edits.')
    finally:
        editor.close()
