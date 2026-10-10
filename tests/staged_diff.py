"""Changes compares against staged content when the same file is in both groups."""
from pathlib import Path
import subprocess
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-staged-diff-') as directory:
    root = Path(directory)
    repo = root / 'repo'
    repo.mkdir()

    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.STDOUT).decode().strip()

    git('init', '-b', 'main')
    git('config', 'user.name', 'UI Test')
    git('config', 'user.email', 'ui@example.invalid')
    tracked = repo / '[tracked] file.txt'
    other = repo / 'other.txt'
    tracked.write_text('HEAD content\n')
    other.write_text('Other HEAD content\n')
    git('add', '.')
    git('commit', '-m', 'Baseline')
    tracked.write_text('Staged content\n')
    added = repo / 'added.txt'
    added.write_text('Staged new file\n')
    git('add', '.')
    tracked.write_text('Working content\n')
    added.write_text('Working new file\n')
    other.write_text('Other working content\n')

    editor = Editor(repo, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert");'
                   'vim.api.nvim_buf_set_lines(0,0,-1,false,{"Unsaved editor content"});'
                   'vim.g.ide_git_autofetch=false;require("config.ide").git_explorer()', str(tracked))
        editor.wait(lambda: editor.lua('local s=require("config.sidebar").state();return s and s.tree and s.tree:get_node(...)~=nil', str(tracked)+'::staged'),
                    'Both staged and working rows are visible')

        def click(path, staged=False):
            node_id = str(path) + ('::staged' if staged else '')
            position = editor.lua('local s,w=require("config.sidebar").state();local _,line=s.tree:get_node(...);'
                                  'local p=vim.api.nvim_win_get_position(w);local info=vim.fn.getwininfo(w)[1];'
                                  'return {p[1]+line-info.topline+(vim.wo[w].winbar~="" and 1 or 0),p[2]+6}', node_id)
            editor.click(*position)
            editor.wait(lambda: editor.lua('local d=require("config.diff");return d.active and d.entries[d.active.buf].path==...', str(path)),
                        'Click opens the selected file diff')

        def check(before, after, label):
            assert editor.lua('local d=require("config.diff");return vim.api.nvim_buf_get_lines(d.entries[d.active.buf].before,0,-1,false)') == [before]
            assert editor.lua('local d=require("config.diff");return vim.api.nvim_buf_get_lines(d.active.buf,0,-1,false)') == [after]
            editor.wait(lambda: editor.lua('local d=require("config.diff").active;return vim.api.nvim_buf_get_lines(d.toolbar,0,1,false)[1]:find(...,1,true)~=nil', label),
                        'Toolbar names the comparison baseline')

        click(tracked)
        check('Staged content', 'Unsaved editor content', 'Staged → Working tree')
        proxy = editor.lua('return require("config.diff").active.buf')
        click(tracked, staged=True)
        check('HEAD content', 'Unsaved editor content', 'HEAD → Working tree')
        assert editor.lua('return require("config.diff").active.buf') == proxy, 'Switching baseline reuses the same document card'
        editor.lua('local s=require("config.sidebar").state();require("config.git").menu(s,s.tree:get_node(...))[1].cmd()', str(tracked))
        check('Staged content', 'Unsaved editor content', 'Staged → Working tree')
        click(added)
        check('Staged new file', 'Working new file', 'Staged → Working tree')
        click(added, staged=True)
        check('', 'Working new file', 'HEAD → Working tree')
        click(other)
        check('Other HEAD content', 'Other working content', 'HEAD → Working tree')
        tracked.unlink()
        editor.lua('require("config.git").refresh()')
        editor.wait(lambda: editor.lua('local s=require("config.sidebar").state();local n=s.tree:get_node(...);return n and n.extra.status=="D"', str(tracked)),
                    'Deleted working file retains staged counterpart')
        # Preserve an unsaved editor buffer even if its file has been deleted on disk.
        click(tracked)
        check('Staged content', 'Unsaved editor content', 'Staged → Working tree')
        assert git('show', ':[tracked] file.txt') == 'Staged content', 'Viewing diffs does not modify the index'
        assert git('show', 'HEAD:[tracked] file.txt') == 'HEAD content'
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: Changes uses staged baselines for mixed tracked/new/deleted files; Staged Changes and ordinary changes use HEAD; clicks/menu reuse cards and preserve edits/index.')
    finally:
        editor.close()
