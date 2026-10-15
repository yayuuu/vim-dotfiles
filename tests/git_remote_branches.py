"""Status-bar selection fetches server-only branches and switches with tracking."""
from pathlib import Path
import subprocess
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-remote-branches-') as directory:
    root = Path(directory)
    repo, origin = root / 'project', root / 'origin.git'
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
    notes, source = repo / 'notes.txt', repo / 'source.txt'
    notes.write_text('notes\n')
    source.write_text('baseline\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'Baseline')
    git(root, 'init', '--bare', '-b', 'main', str(origin))
    git(repo, 'remote', 'add', 'origin', str(origin))
    git(repo, 'push', '-u', 'origin', 'main')
    # A single-branch clone's fetch configuration must not hide other branches.
    git(repo, 'config', 'remote.origin.fetch', '+refs/heads/main:refs/remotes/origin/main')
    git(origin, 'update-ref', 'refs/heads/feature/server-only', 'refs/heads/main')
    assert git(repo, 'show-ref', '--verify', 'refs/remotes/origin/feature/server-only', check=False).returncode != 0

    editor = Editor(repo, root / 'state')
    try:
        editor.lua('vim.g.ide_git_autofetch=false;require("config.ide").open_file(...);'
                   'vim.cmd("stopinsert");vim.api.nvim_buf_set_lines(0,0,-1,false,{"Unsaved notes"});'
                   '_G.remote_branch_notifications={};local notify=vim.notify;vim.notify=function(message,...) '
                   'table.insert(_G.remote_branch_notifications,tostring(message));return notify(message,...) end', str(notes))

        def branch_position():
            editor.lua('vim.cmd("redraw!")')
            name = git(repo, 'branch', '--show-current')
            for row, cells in enumerate(editor.grid):
                text = ''.join(cells)
                if '[↑' in text:
                    column = text.rfind(name, 0, text.index('[↑'))
                    if column >= 0:
                        return row, column + 1

        def open_picker(expected):
            editor.lua('require("config.git").refresh()')
            editor.wait(branch_position, 'Status-bar branch button is visible')
            editor.click(*branch_position())
            editor.wait(lambda: editor.lua('local p=Snacks.picker.get({source="git_branches"})[1];'
                                          'if not p then return false end;for _,item in ipairs(p:items()) do '
                                          'if item.branch==... then return true end end;return false', expected),
                        'Picker lists ' + expected)

        def select(branch):
            assert editor.lua('local p=Snacks.picker.get({source="git_branches"})[1];'
                              'for i,item in ipairs(p:items()) do if item.branch==... then '
                              'p.list:view(i);p:action("confirm");return true end end;return false', branch)

        remote = 'remotes/origin/feature/server-only'
        open_picker(remote)
        assert git(repo, 'branch', '--show-current') == 'main', 'Opening the picker does not switch branches'
        assert git(repo, 'show-ref', '--verify', 'refs/heads/feature/server-only', check=False).returncode != 0
        select(remote)
        editor.wait(lambda: git(repo, 'branch', '--show-current') == 'feature/server-only', 'Remote selection creates a local branch')
        editor.wait(lambda: git(repo, 'rev-parse', '--abbrev-ref', '@{upstream}') == 'origin/feature/server-only', 'New branch tracks origin')
        assert git(repo, 'config', '--get', 'branch.feature/server-only.merge') == 'refs/heads/feature/server-only'
        assert git(repo, 'rev-parse', 'HEAD') == git(origin, 'rev-parse', 'refs/heads/feature/server-only')

        # Reuse a diverged local branch without resetting it; update its upstream.
        git(repo, 'branch', 'reuse')
        git(repo, 'switch', 'reuse')
        git(repo, 'commit', '--allow-empty', '-m', 'Local commit to preserve')
        local_head = git(repo, 'rev-parse', 'HEAD')
        git(repo, 'branch', '--set-upstream-to=origin/main', 'reuse')
        git(repo, 'switch', 'main')
        git(origin, 'update-ref', 'refs/heads/reuse', 'refs/heads/main')
        open_picker('remotes/origin/reuse')
        select('remotes/origin/reuse')
        editor.wait(lambda: git(repo, 'branch', '--show-current') == 'reuse', 'Remote selection reuses the existing local branch')
        editor.wait(lambda: git(repo, 'rev-parse', '--abbrev-ref', '@{upstream}') == 'origin/reuse', 'Existing local branch gets the selected upstream')
        assert git(repo, 'rev-parse', 'HEAD') == local_head, 'Existing local commits are preserved'

        # Native checkout protection must stop switching before upstream changes.
        seed = root / 'seed'
        git(root, 'clone', str(origin), str(seed))
        git(seed, 'config', 'user.name', 'UI Test')
        git(seed, 'config', 'user.email', 'ui@example.invalid')
        git(seed, 'switch', '-c', 'blocked')
        (seed / 'source.txt').write_text('remote version\n')
        git(seed, 'commit', '-am', 'Remote source change')
        git(seed, 'push', 'origin', 'blocked')
        open_picker('remotes/origin/blocked')
        git(repo, 'branch', 'blocked', 'refs/remotes/origin/blocked')
        git(repo, 'branch', '--set-upstream-to=origin/main', 'blocked')
        source.write_text('local changes to preserve\n')
        select('remotes/origin/blocked')
        editor.wait(lambda: 'Git switch failed' in editor.lua('return table.concat(_G.remote_branch_notifications,"\\n")'),
                    'Conflicting local changes prevent switching')
        assert git(repo, 'branch', '--show-current') == 'reuse'
        assert git(repo, 'rev-parse', '--abbrev-ref', 'blocked@{upstream}') == 'origin/main'
        assert source.read_text() == 'local changes to preserve\n'
        source.write_text('baseline\n')

        # Fetch on every opening picks up newly created server branches; cancel
        # changes neither the active branch nor the set of local branches.
        git(origin, 'update-ref', 'refs/heads/arrived-later', 'refs/heads/main')
        open_picker('remotes/origin/arrived-later')
        editor.lua('Snacks.picker.get({source="git_branches"})[1]:close()')
        assert git(repo, 'branch', '--show-current') == 'reuse'
        assert git(repo, 'show-ref', '--verify', 'refs/heads/arrived-later', check=False).returncode != 0

        # A failed fetch still leaves cached/local branches selectable.
        git(repo, 'remote', 'set-url', 'origin', str(root / 'missing-origin.git'))
        open_picker('main')
        editor.wait(lambda: 'Git fetch origin failed' in editor.lua('return table.concat(_G.remote_branch_notifications,"\\n")'),
                    'Failed fetch reports its error')
        select('main')
        editor.wait(lambda: git(repo, 'branch', '--show-current') == 'main', 'Local selection works after fetch failure')

        # Canceling while fetch is running cannot reopen the closed picker.
        editor.wait(lambda: not editor.lua('return require("config.git_sync").fetching[...]', str(repo)), 'Failed fetch releases its guard')
        git(repo, 'remote', 'set-url', 'origin', str(origin))
        git(repo, 'config', 'remote.origin.uploadpack', 'sleep 1; git-upload-pack')
        open_picker('main')
        editor.lua('Snacks.picker.get({source="git_branches"})[1]:close()')
        editor.wait(lambda: not editor.lua('return require("config.git_sync").fetching[...]', str(repo)), 'Canceled picker lets fetch finish')
        assert not editor.lua('return Snacks.picker.get({source="git_branches"})[1] ~= nil')
        assert git(repo, 'branch', '--show-current') == 'main'

        git(repo, 'remote', 'remove', 'origin')
        open_picker('reuse')
        select('reuse')
        editor.wait(lambda: git(repo, 'branch', '--show-current') == 'reuse', 'Local selection works without origin')
        assert editor.lua('return vim.api.nvim_buf_get_lines(vim.fn.bufnr(...),0,-1,false)', str(notes)) == ['Unsaved notes']
        assert notes.read_text() == 'notes\n'
        print('PASS: status-bar remote selection fetches server-only branches even with a narrow refspec, '
              'creates/reuses tracking branches without resetting commits, refreshes new branches, '
              'supports cancellation during fetch/fetch failure/no origin, blocks conflicting switches, and preserves unsaved notes.')
    except Exception:
        print(editor.lua('return table.concat(_G.remote_branch_notifications,"\\n")'))
        print(editor.lua('return vim.fn.execute("messages")'))
        raise
    finally:
        editor.close()
