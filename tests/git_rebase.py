"""Palette rebase selects an upstream without switching or creating a merge."""
from pathlib import Path
import subprocess
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-git-rebase-') as directory:
    root = Path(directory)
    repo = root / 'project'
    repo.mkdir()

    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.STDOUT).decode().strip()

    git('init', '-b', 'main')
    git('config', 'user.name', 'UI Test')
    git('config', 'user.email', 'ui@example.invalid')
    source, notes = repo / 'conflict.txt', repo / 'notes.txt'
    source.write_text('baseline\n')
    notes.write_text('notes\n')
    git('add', '.')
    git('commit', '-m', 'Baseline')
    git('switch', '-c', 'topic')
    (repo / 'topic.txt').write_text('topic\n')
    git('add', '.')
    git('commit', '-m', 'Topic commit')
    old_topic = git('rev-parse', 'HEAD')
    git('switch', 'main')
    (repo / 'upstream.txt').write_text('upstream\n')
    git('add', '.')
    git('commit', '-m', 'Upstream commit')
    upstream = git('rev-parse', 'HEAD')
    git('update-ref', 'refs/remotes/origin/main', upstream)
    git('switch', 'topic')
    editor = Editor(repo, root / 'state')
    try:
        editor.lua('vim.g.ide_git_autofetch=false;require("config.ide").open_file(...);vim.cmd("stopinsert");'
                   'vim.api.nvim_buf_set_lines(0,0,-1,false,{"Unsaved notes"})', str(notes))
        editor.call('nvim_input', '<C-S-p>')
        editor.wait(lambda: editor.lua('local p=Snacks.picker.get({source="commands"})[1];return p and #p:items()>0'), 'Command palette opens')
        assert editor.lua('local p=Snacks.picker.get({source="commands"})[1];for i,item in ipairs(p:items()) do '
                          'if item.cmd=="GitRebase" then p.list:view(i);p:action("confirm");return true end end;return false')
        editor.wait(lambda: editor.lua('return vim.fn.getcmdline()') == 'GitRebase', 'Palette prepares GitRebase')
        editor.call('nvim_input', '<CR>')

        def picker():
            return editor.lua('local p=Snacks.picker.get({source="git_branches"})[1];return p and p.shown and #p:items()>=3')

        def select(branch):
            assert editor.lua('local p=Snacks.picker.get({source="git_branches"})[1];for i,item in ipairs(p:items()) do '
                              'if item.branch==... then p.list:view(i);p:action("confirm");return true end end;return false', branch)
            editor.wait(lambda: not editor.lua('return require("config.git_commands").busy'), 'Rebase command finishes')

        editor.wait(picker, 'Rebase offers local and remote branches')
        assert git('rev-parse', 'HEAD') == old_topic, 'Opening selection performs no rebase'
        select('remotes/origin/main')
        assert git('branch', '--show-current') == 'topic'
        assert git('rev-parse', 'HEAD') != old_topic, 'Topic commit is rewritten'
        assert git('rev-parse', 'HEAD^') == upstream, 'Topic is replayed onto the selected branch'
        assert git('rev-list', '--count', '--merges', 'main..topic') == '0'
        assert (repo / 'topic.txt').read_text() == 'topic\n'
        assert (repo / 'upstream.txt').read_text() == 'upstream\n'
        rebased = git('rev-parse', 'HEAD')

        # Canceling selection does nothing; explicit branch arguments work too.
        editor.lua('vim.cmd("GitRebase")')
        editor.wait(picker, 'Second picker opens')
        editor.lua('Snacks.picker.get({source="git_branches"})[1]:close()')
        assert git('rev-parse', 'HEAD') == rebased
        editor.lua('vim.cmd("GitRebase main")')
        editor.wait(lambda: not editor.lua('return require("config.git_commands").busy'), 'Explicit rebase finishes')
        assert git('rev-parse', 'HEAD') == rebased

        source.write_text('topic conflict\n')
        git('commit', '-am', 'Topic conflict')
        conflicted_topic = git('rev-parse', 'HEAD')
        git('switch', 'main')
        source.write_text('upstream conflict\n')
        git('commit', '-am', 'Upstream conflict')
        git('switch', 'topic')
        editor.lua('require("config.ide").git_explorer();vim.cmd("GitRebase main")')
        editor.wait(lambda: not editor.lua('return require("config.git_commands").busy'), 'Conflicted rebase releases its operation guard')
        assert git('diff', '--name-only', '--diff-filter=U') == 'conflict.txt'
        editor.wait(lambda: editor.lua('local s=require("config.sidebar").state();local n=s and s.tree and s.tree:get_node(...);'
                                      'return n and n.extra.status=="U"', str(source)), 'Rebase conflict refreshes Git status')
        editor.lua('vim.cmd("GitRebaseAbort")')
        editor.wait(lambda: not editor.lua('return require("config.git_commands").busy'), 'Rebase abort finishes')
        assert git('branch', '--show-current') == 'topic'
        assert git('rev-parse', 'HEAD') == conflicted_topic
        assert source.read_text() == 'topic conflict\n'

        # Continue after resolving a conflict using the matching palette command.
        editor.lua('vim.cmd("GitRebase main")')
        editor.wait(lambda: not editor.lua('return require("config.git_commands").busy'), 'Second conflicted rebase finishes')
        source.write_text('resolved conflict\n')
        git('add', 'conflict.txt')
        editor.lua('vim.cmd("GitRebaseContinue")')
        editor.wait(lambda: not editor.lua('return require("config.git_commands").busy'), 'Continue finishes the rebase')
        assert git('branch', '--show-current') == 'topic'
        assert git('rev-list', '--count', '--merges', 'main..topic') == '0'
        assert source.read_text() == 'resolved conflict\n'
        assert editor.lua('return vim.api.nvim_buf_get_lines(vim.fn.bufnr(...),0,-1,false)', str(notes)) == ['Unsaved notes']
        assert notes.read_text() == 'notes\n'
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: GitRebase in palette selects local/remote upstreams, replays commits without switching or merging, '
              'supports cancellation/explicit arguments/conflict refresh/abort/continue and preserves unsaved notes.')
    finally:
        editor.close()
