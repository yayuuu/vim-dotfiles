"""Status-bar branch creation and publication use real input and disposable remotes."""
from pathlib import Path
import subprocess
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-branch-publish-') as directory:
    root = Path(directory)
    repo, origin, other = root / 'project', root / 'origin.git', root / 'other.git'
    repo.mkdir()

    def git(path, *args, check=True):
        result = subprocess.run(['git', '-C', str(path), *args], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
        if check and result.returncode:
            raise AssertionError((args, result.stdout))
        return result.stdout.strip() if check else result

    git(repo, 'init', '-b', 'main')
    git(repo, 'config', 'user.name', 'UI Test')
    git(repo, 'config', 'user.email', 'ui@example.invalid')
    notes = repo / 'notes.txt'
    notes.write_text('baseline\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'Baseline')
    for remote in (origin, other):
        git(root, 'init', '--bare', '-b', 'main', str(remote))
    git(repo, 'remote', 'add', 'origin', str(origin))
    git(repo, 'remote', 'add', 'other', str(other))
    git(repo, 'push', '-u', 'origin', 'main')
    editor = Editor(repo, root / 'state')
    try:
        editor.lua('vim.g.ide_git_autofetch=false;require("config.ide").open_file(...);'
                   'vim.cmd("stopinsert");vim.api.nvim_buf_set_lines(0,0,-1,false,{"Unsaved notes"});'
                   '_G.git_test_notifications={};local notify=vim.notify;vim.notify=function(message,...) '
                   'table.insert(_G.git_test_notifications,tostring(message));return notify(message,...) end', str(notes))

        def notifications():
            return editor.lua('return table.concat(_G.git_test_notifications,"\\n")')

        def bar_position(branch=False):
            editor.lua('vim.cmd("redraw!")')
            for row, cells in enumerate(editor.grid):
                text = ''.join(cells)
                if '[↑' in text:
                    column = text.index('[↑')
                    if branch:
                        name = git(repo, 'branch', '--show-current')
                        column = text.rfind(name, 0, column)
                        if column < 0:
                            continue
                    return row, column + 1

        def open_picker():
            editor.lua('require("config.git").refresh()')
            editor.wait(lambda: bar_position(True), 'Branch button is visible')
            editor.click(*bar_position(True))
            editor.wait(lambda: editor.lua('local p=Snacks.picker.get({source="git_branches"})[1];'
                                          'return p and p.shown and #p:items()>0'), 'Branch picker opens from status bar')

        def type_name(name):
            editor.call('nvim_input', name)
            editor.wait(lambda: editor.lua('local p=Snacks.picker.get({source="git_branches"})[1];'
                                          'return p and p.input:get()==... and #p:items()==0', name),
                        'A new branch name has no existing matches')

        def click_sync():
            editor.lua('require("config.git").refresh()')
            editor.wait(lambda: bar_position(), 'Sync button is visible')
            editor.click(*bar_position())

        branch = 'EP-7468-payer-policy-poprawienie-plikow-docker-compose-i-docker-compose-dev'
        open_picker()
        type_name(branch)
        editor.call('nvim_input', '<CR>')
        editor.wait(lambda: git(repo, 'branch', '--show-current') == branch,
                    'Enter creates and switches to the typed branch')
        assert git(repo, 'rev-parse', '--verify', '@{upstream}', check=False).returncode != 0
        click_sync()
        editor.wait(lambda: git(repo, 'config', '--get', 'branch.' + branch + '.remote', check=False).stdout.strip() == 'origin',
                    'One sync click publishes and sets the upstream')
        editor.wait(lambda: not editor.lua('return require("config.git_sync").busy'), 'Publication finishes')
        assert git(origin, 'rev-parse', 'refs/heads/' + branch) == git(repo, 'rev-parse', 'HEAD')
        assert git(repo, 'rev-parse', '--abbrev-ref', '@{upstream}') == 'origin/' + branch
        editor.wait(lambda: editor.lua('return require("config.git_sync").label()') == '[↑0 ↓0]', 'Published counters refresh')
        click_sync()
        editor.wait(lambda: not editor.lua('return require("config.git_sync").busy'), 'Next click performs ordinary sync')

        # Ordinary selection, fuzzy search, invalid input, and cancellation still work.
        open_picker()
        editor.call('nvim_input', 'mai')
        editor.wait(lambda: editor.lua('local p=Snacks.picker.get({source="git_branches"})[1];'
                                      'return p and p.input:get()=="mai" and p:current().branch=="main"'), 'Fuzzy search selects main')
        editor.call('nvim_input', '<CR>')
        editor.wait(lambda: git(repo, 'branch', '--show-current') == 'main', 'Enter switches to an existing branch')
        open_picker()
        type_name('invalid..branch')
        editor.call('nvim_input', '<CR>')
        editor.wait(lambda: 'Invalid branch name' in notifications(), 'Invalid name reports a message')
        assert git(repo, 'branch', '--show-current') == 'main'
        editor.lua('Snacks.picker.get({source="git_branches"})[1]:close()')
        open_picker()
        type_name('cancelled-new-branch')
        editor.lua('Snacks.picker.get({source="git_branches"})[1]:close()')
        assert git(repo, 'show-ref', '--verify', 'refs/heads/cancelled-new-branch', check=False).returncode != 0

        def new_branch(name):
            git(repo, 'switch', '-c', name)
            editor.lua('require("config.git").refresh()')

        # A configured push remote takes precedence over origin.
        new_branch('configured-publish')
        git(repo, 'tag', 'configured-publish')
        git(repo, 'config', 'remote.pushDefault', 'other')
        editor.lua('require("config.git_sync").sync()')
        editor.wait(lambda: git(repo, 'config', '--get', 'branch.configured-publish.remote', check=False).stdout.strip() == 'other',
                    'Configured push remote wins')
        editor.wait(lambda: not editor.lua('return require("config.git_sync").busy'), 'Configured publication finishes')
        assert git(other, 'rev-parse', 'refs/heads/configured-publish') == git(repo, 'rev-parse', 'HEAD')
        git(repo, 'config', '--unset', 'remote.pushDefault')
        new_branch('branch-push-remote')
        git(repo, 'config', 'remote.pushDefault', 'other')
        git(repo, 'config', 'branch.branch-push-remote.pushRemote', 'origin')
        editor.lua('require("config.git_sync").sync()')
        editor.wait(lambda: git(repo, 'config', '--get', 'branch.branch-push-remote.remote', check=False).stdout.strip() == 'origin',
                    'Branch pushRemote wins over pushDefault')
        editor.wait(lambda: not editor.lua('return require("config.git_sync").busy'), 'Branch-specific publication finishes')
        git(repo, 'config', '--unset', 'remote.pushDefault')

        # Ambiguous remotes require selection; cancel must do nothing.
        git(repo, 'remote', 'rename', 'origin', 'first')
        new_branch('remote-choice')
        editor.lua('require("config.git_sync").sync()')
        editor.wait(lambda: editor.lua('local p=Snacks.picker.get({source="select"})[1];return p and p.shown'), 'Remote selection opens')
        editor.lua('Snacks.picker.get({source="select"})[1]:close()')
        assert git(repo, 'rev-parse', '--verify', '@{upstream}', check=False).returncode != 0
        editor.lua('require("config.git_sync").sync()')
        editor.wait(lambda: editor.lua('local p=Snacks.picker.get({source="select"})[1];return p and p.shown'), 'Remote selection reopens')
        assert editor.lua('local p=Snacks.picker.get({source="select"})[1];for i,item in ipairs(p:items()) do '
                          'if item.item=="other" then p.list:view(i);p:action("confirm");return true end end;return false')
        editor.wait(lambda: git(repo, 'config', '--get', 'branch.remote-choice.remote', check=False).stdout.strip() == 'other',
                    'Selected remote receives the branch')
        editor.wait(lambda: not editor.lua('return require("config.git_sync").busy'), 'Selected publication finishes')

        # A single remote with a custom name also works.
        git(repo, 'remote', 'remove', 'first')
        new_branch('single-remote')
        editor.lua('require("config.git_sync").sync()')
        editor.wait(lambda: git(repo, 'config', '--get', 'branch.single-remote.remote', check=False).stdout.strip() == 'other',
                    'Single remote is selected automatically')
        editor.wait(lambda: not editor.lua('return require("config.git_sync").busy'), 'Single-remote publication finishes')

        # Failed publication must neither set tracking nor leave synchronization locked.
        new_branch('rejected-publication')
        hook = other / 'hooks' / 'pre-receive'
        hook.write_text('#!/bin/sh\necho rejected-by-test >&2\nexit 1\n')
        hook.chmod(0o755)
        editor.lua('require("config.git_sync").sync()')
        editor.wait(lambda: not editor.lua('return require("config.git_sync").busy'), 'Rejected push releases sync lock')
        assert git(repo, 'rev-parse', '--verify', '@{upstream}', check=False).returncode != 0
        assert git(other, 'show-ref', '--verify', 'refs/heads/rejected-publication', check=False).returncode != 0
        assert 'rejected-by-test' in notifications()

        git(repo, 'remote', 'remove', 'other')
        new_branch('no-remote')
        editor.lua('require("config.git_sync").sync()')
        assert 'Add a Git remote' in notifications()
        git(repo, 'switch', '--detach')
        editor.lua('require("config.git_sync").sync()')
        assert 'detached HEAD' in notifications()
        assert not editor.lua('return require("config.git_sync").busy')
        assert editor.lua('return vim.api.nvim_buf_get_lines(vim.fn.bufnr(...),0,-1,false)', str(notes)) == ['Unsaved notes']
        assert notes.read_text() == 'baseline\n', 'Git actions preserve unsaved editor contents'
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: status-bar create/publish, existing fuzzy selection, invalid names/cancel, configured/selected/single remotes, '
              'push failure, no remote, detached HEAD, counters, repeat sync, and unsaved notes.')
    finally:
        editor.close()
