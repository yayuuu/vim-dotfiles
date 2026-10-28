"""Project Git buttons survive virtual buffers, tool extensions and project changes."""
from pathlib import Path
import subprocess
import tempfile
import time

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-git-statusline-') as directory:
    root = Path(directory)
    repo, origin, peer = root / 'project', root / 'origin.git', root / 'peer'
    repo.mkdir()

    def git(path, *args):
        return subprocess.check_output(['git', '-C', str(path), '-c', 'user.name=UI Test',
                                        '-c', 'user.email=ui@example.invalid', *args],
                                       stderr=subprocess.STDOUT).decode().strip()

    git(repo, 'init', '-b', 'main')
    path = repo / 'example.lua'
    path.write_text('local function example()\n  return true\nend\nreturn example()\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'Baseline')
    git(root, 'init', '--bare', '-b', 'main', str(origin))
    git(repo, 'remote', 'add', 'origin', str(origin))
    git(repo, 'push', '-u', 'origin', 'main')
    git(root, 'clone', str(origin), str(peer))
    (repo / 'local.txt').write_text('local commit\n')
    git(repo, 'add', 'local.txt')
    git(repo, 'commit', '-m', 'Local commit')
    (peer / 'remote.txt').write_text('remote commit\n')
    git(peer, 'add', 'remote.txt')
    git(peer, 'commit', '-m', 'Remote commit')
    git(peer, 'push')
    git(repo, 'fetch')

    editor = Editor(repo, root / 'state', args=('--cmd', 'let g:ide_git_autofetch = v:false'))
    try:
        editor.lua('require("config.ide").open_file(...)', str(path))
        document = editor.call('nvim_get_current_buf')
        unsaved = ['local function example()', '  return "Unsaved"', 'end', 'return example()']
        editor.call('nvim_buf_set_lines', document, 0, -1, False, unsaved)

        def snapshot(branch='main', counts='[↑1 ↓1]', covered=False):
            editor.wait(lambda: editor.lua('return require("config.git_sync").branch()') == branch
                        and editor.lua('return require("config.git_sync").label()') == counts, 'Project Git cache refreshes')
            editor.lua('require("lualine").refresh({force=true});vim.cmd("redrawstatus")')
            time.sleep(.1)
            editor.lua('return true')
            text = ''.join(editor.grid[-1])
            if covered:
                # Full-screen tool dialogs can cover the native status row;
                # verify the extension's statusline beneath their border.
                text = editor.lua('return vim.api.nvim_eval_statusline(vim.o.statusline,{winid=0,maxwidth=vim.o.columns}).str')
            assert 'git ' + branch in text and counts in text, text
            assert text.count(counts) == 1, 'Menus must not duplicate the Git section'
            return text

        snapshot()
        editor.lua('require("config.diff").open(...)', str(path))
        diff = editor.lua('return require("config.diff").active')
        assert editor.call('nvim_buf_get_name', editor.call('nvim_win_get_buf', diff['left'])).startswith('git-before://')
        for win in (diff['left'], diff['right']):
            editor.lua('vim.api.nvim_set_current_win(...)', win)
            snapshot()
            editor.lua('require("config.git_sync").refresh()')
            snapshot()  # Refresh while a virtual document owns focus.

        # Exercise the actual clickable cells from HEAD, without synchronizing
        # the fixture's deliberately divergent branches.
        editor.lua('vim.api.nvim_set_current_win(...);'
                   '_G.statusline_branches=require("config.git").branches;'
                   '_G.statusline_sync=require("config.git_sync").sync;'
                   'require("config.git").branches=function() _G.branch_root=require("config.ide").root() end;'
                   'require("config.git_sync").sync=function() _G.sync_root=require("config.ide").root() end', diff['left'])
        text = snapshot()
        editor.click(len(editor.grid) - 1, text.index('main') + 1)
        editor.wait(lambda: editor.lua('return _G.branch_root') == str(repo), 'HEAD branch button targets the project')
        text = snapshot()
        editor.click(len(editor.grid) - 1, text.index('[↑') + 1)
        editor.wait(lambda: editor.lua('return _G.sync_root') == str(repo), 'HEAD sync button targets the project')
        editor.lua('require("config.git").branches=_G.statusline_branches;require("config.git_sync").sync=_G.statusline_sync')

        for ft in ('neo-tree', 'aerial', 'ide_terminal_list'):
            editor.lua('for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                       'if vim.bo[vim.api.nvim_win_get_buf(w)].filetype==... then vim.api.nvim_set_current_win(w);return end end;'
                       'error("Missing panel")', ft)
            snapshot()
        editor.lua('local t=require("config.terminals");t.show(t.active)')
        snapshot()
        editor.lua('require("config.ide").git_explorer()')
        editor.wait(lambda: editor.lua('local s=require("config.sidebar").state();return s and s.name=="git_status"'), 'Git sidebar')
        editor.lua('local s=require("config.sidebar").state();require("config.git").input(s,true)')
        snapshot()
        editor.lua('require("config.project_search").show()')
        editor.wait(lambda: editor.lua('return vim.b.ide_search_input'), 'Search input')
        snapshot()
        editor.lua('require("config.ide").menu("File",true)')
        snapshot()
        editor.lua('require("config.ide").close_menu();require("config.ide").open_file(nil,...)', document)
        editor.lua('vim.cmd("stopinsert");vim.cmd("Lazy")')
        editor.wait(lambda: editor.lua('return vim.bo.filetype=="lazy"'), 'Plugins dialog')
        snapshot(covered=True)
        editor.lua('require("lazy.view").view:close()')

        # Cache entries are scoped to projects, including detached and unborn HEAD.
        git(repo, 'switch', '--detach')
        editor.lua('require("config.git_sync").refresh()')
        snapshot('HEAD ' + git(repo, 'rev-parse', '--short', 'HEAD'), '[↑– ↓–]')
        git(repo, 'switch', 'main')
        editor.lua('require("config.git_sync").refresh()')
        snapshot()
        git(repo, 'switch', '-c', 'feature/50%status')
        editor.lua('require("config.git_sync").refresh()')
        snapshot('feature/50%status', '[↑– ↓–]')
        git(repo, 'switch', 'main')
        editor.lua('require("config.git_sync").refresh()')
        snapshot()
        empty = root / 'empty'
        empty.mkdir()
        git(empty, 'init', '-b', 'new-project')
        editor.lua('require("config.ide").open_project(...)', str(empty))
        snapshot('new-project', '[↑– ↓–]')
        outside = root / 'outside'
        outside.mkdir()
        editor.lua('require("config.ide").open_project(...)', str(outside))
        editor.wait(lambda: editor.lua('local s=require("config.git_sync").cache[require("config.ide").root()];return s and not s.repo'), 'Non-repository cache')
        assert editor.lua('return require("config.git_sync").branch()') == ''
        assert editor.lua('return require("config.git_sync").label()') == ''
        editor.lua('require("config.ide").open_project(...)', str(repo))
        snapshot()
        assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == unsaved
        assert editor.lua('return vim.bo[...].modified', document)
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: rendered project branch/sync and clickable HEAD buttons survive diff sides, panels, inputs, menu and Plugins; '
              'refresh, detached/unborn HEAD and project/non-repository switches preserve context and unsaved text.')
    finally:
        editor.close()
