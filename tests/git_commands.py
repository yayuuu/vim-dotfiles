"""Git commands are discoverable in the palette and merges use a branch picker."""
from pathlib import Path
import subprocess
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-git-commands-') as directory:
    root = Path(directory)
    repo = root / 'project'
    repo.mkdir()

    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.STDOUT).decode().strip()

    git('init', '-b', 'main')
    git('config', 'user.name', 'UI Test')
    git('config', 'user.email', 'ui@example.invalid')
    source = repo / 'conflict.txt'
    notes = repo / 'notes.txt'
    source.write_text('baseline\n')
    notes.write_text('notes\n')
    git('add', '.')
    git('commit', '-m', 'Baseline')
    git('switch', '-c', 'feature')
    (repo / 'feature.txt').write_text('Merged feature\n')
    git('add', '.')
    git('commit', '-m', 'Feature')
    feature = git('rev-parse', 'HEAD')
    git('switch', 'main')
    git('switch', '-c', 'clash')
    source.write_text('other branch\n')
    git('add', '.')
    git('commit', '-m', 'Conflicting branch')
    git('switch', 'main')

    editor = Editor(repo, root / 'state')
    try:
        editor.lua('vim.g.ide_git_autofetch=false;require("config.ide").open_file(...);vim.cmd("stopinsert");'
                   'vim.api.nvim_buf_set_lines(0,0,-1,false,{"Unsaved notes"})', str(notes))
        editor.call('nvim_input', '<C-S-p>')
        editor.wait(lambda: editor.lua('local p=Snacks.picker.get({source="commands"})[1];return p and p.shown and #p:items()>0'),
                    'Ctrl+Shift+P opens the command palette')
        commands = editor.lua('local p=Snacks.picker.get({source="commands"})[1];local names={};for _,item in ipairs(p:items()) do names[item.cmd]=true end;return names')
        for name in ('GitMerge', 'GitMergeAbort', 'GitStatus', 'GitRefresh', 'GitSwitchBranch', 'GitCommit',
                     'GitFetch', 'GitPull', 'GitPush', 'GitSync', 'GitDiff', 'GitFileHistory', 'GitProjectHistory', 'GitBlame', 'GitStageHunk'):
            assert name in commands, name
        assert editor.lua('local p=Snacks.picker.get({source="commands"})[1];for i,item in ipairs(p:items()) do '
                          'if item.cmd=="GitMerge" then p.list:view(i);p:action("confirm");return true end end;return false')
        editor.wait(lambda: editor.lua('return vim.fn.getcmdline()') == 'GitMerge', 'Palette prepares the GitMerge command')
        editor.call('nvim_input', '<CR>')
        editor.wait(lambda: editor.lua('local p=Snacks.picker.get({source="git_branches"})[1];return p and #p:items()>=3'),
                    'GitMerge offers branch selection')
        main = git('rev-parse', 'HEAD')
        assert main != feature, 'Opening the picker does not merge anything'

        def select(branch):
            assert editor.lua('local p=Snacks.picker.get({source="git_branches"})[1];for i,item in ipairs(p:items()) do '
                              'if item.branch==... then p.list:view(i);p:action("confirm");return true end end;return false', branch)
            editor.wait(lambda: not editor.lua('return require("config.git_commands").busy'), 'Git operation finishes')

        select('feature')
        assert git('rev-parse', 'HEAD') == feature, 'Selected feature branch was merged'
        assert git('branch', '--show-current') == 'main', 'Merge does not switch branches'
        assert (repo / 'feature.txt').read_text() == 'Merged feature\n'
        assert editor.lua('return vim.api.nvim_buf_get_lines(vim.fn.bufnr(...),0,-1,false)', str(notes)) == ['Unsaved notes']
        source.write_text('current branch\n')
        git('add', 'conflict.txt')
        git('commit', '-m', 'Local conflict')
        current = git('rev-parse', 'HEAD')
        editor.lua('require("config.ide").git_explorer();vim.cmd("stopinsert");vim.cmd("GitMerge")')
        editor.wait(lambda: editor.lua('local p=Snacks.picker.get({source="git_branches"})[1];return p and #p:items()>=3'), 'Second merge picker opens')
        select('clash')
        assert git('rev-parse', 'HEAD') == current, 'Conflicted merge does not create a commit'
        assert git('diff', '--name-only', '--diff-filter=U') == 'conflict.txt'
        editor.wait(lambda: editor.lua('local s=require("config.sidebar").state();local n=s and s.tree and s.tree:get_node(...);return n and n.extra.status=="U"', str(source)),
                    'Failed merge refreshes conflicts in the Git panel')
        editor.lua('vim.cmd("GitMergeAbort")')
        editor.wait(lambda: not editor.lua('return require("config.git_commands").busy'), 'Merge abort finishes')
        assert git('diff', '--name-only', '--diff-filter=U') == ''
        assert source.read_text() == 'current branch\n'
        assert editor.lua('return vim.api.nvim_buf_get_lines(vim.fn.bufnr(...),0,-1,false)', str(notes)) == ['Unsaved notes']
        # Closing branch selection is cancellation, not an operation.
        editor.lua('vim.cmd("GitMerge")')
        editor.wait(lambda: editor.lua('local p=Snacks.picker.get({source="git_branches"})[1];return p and p.shown'), 'Cancellation picker opens')
        editor.lua('Snacks.picker.get({source="git_branches"})[1]:close()')
        assert git('rev-parse', 'HEAD') == current
        print('PASS: Ctrl+Shift+P lists Git commands; GitMerge selection merges without switching, refreshes conflicts, supports abort/cancellation, and preserves unsaved notes.')
    finally:
        editor.close()
