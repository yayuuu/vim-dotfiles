"""Switch full sidebar views and synchronize a disposable local remote."""
from pathlib import Path
import subprocess
import tempfile
import time
from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-sidebar-') as directory:
    root = Path(directory)
    remote, repo, peer = root/'remote.git', root/'project', root/'peer'
    def git(path, *args):
        return subprocess.check_output(['git', '-C', str(path), *args], stderr=subprocess.STDOUT).decode().strip()
    git(root, 'init', '--bare', '-b', 'main', str(remote))
    git(root, 'clone', str(remote), str(repo))
    for path in [repo]:
        git(path, 'config', 'user.name', 'UI Test'); git(path, 'config', 'user.email', 'ui@example.invalid')
    source = repo/'code.lua'; source.write_text('local function example()\n  return true\nend\nreturn example()\n')
    git(repo, 'add', '.'); git(repo, 'commit', '-m', 'Baseline'); git(repo, 'push', '-u', 'origin', 'main')
    git(root, 'clone', str(remote), str(peer))
    git(peer, 'config', 'user.name', 'UI Test'); git(peer, 'config', 'user.email', 'ui@example.invalid')
    git(repo, 'config', 'pull.rebase', 'false')
    state = root/'state'
    editor = Editor(Path.home(), state)
    try:
        def current():
            return editor.lua('local s=require("config.sidebar").state();return s and s.name')
        def panels():
            return editor.lua('local r={};for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                              'if vim.api.nvim_win_get_config(w).relative=="" then r[vim.bo[vim.api.nvim_win_get_buf(w)].filetype]=w end end;return r')
        def tab(label, source):
            editor.lua('vim.cmd("stopinsert");vim.cmd("redraw!")')
            row, left, width = editor.lua('local s,w=require("config.sidebar").state();local p=vim.api.nvim_win_get_position(w);'
                                         'return {p[1],p[2],vim.api.nvim_win_get_width(w)}')
            bar = ''.join(editor.grid[row][left:left+width])
            editor.click(row,left+bar.index(label)+len(label)//2)
            editor.wait(lambda:current()==source, label+' source click')
            editor.wait(lambda:not editor.lua('return require("config.sidebar").changing or require("config.sidebar").pending or require("config.layout").scaling'), label+' panels settle')
        assert current() == 'projects', current()
        assert 'aerial' not in panels() and 'ide_git_history' not in panels()
        assert 'ide_terminal_list' in panels()
        order = editor.lua('local s,w=require("config.sidebar").state();return vim.api.nvim_eval_statusline(vim.wo[w].winbar,{winid=w,use_winbar=true}).str')
        assert order.startswith(' '), order
        assert order.index('Projects') < order.index('Files') < order.index('Debug') < order.index('Git') < order.index('Tabs'), order
        editor.lua('require("config.ide").open_project(...);require("config.ide").open_file(select(2,...));vim.cmd("stopinsert")', str(repo), str(source))
        editor.wait(lambda:current()=='filesystem' and 'aerial' in panels(), 'Files and symbols after opening project')
        editor.wait(lambda:not editor.lua('return require("config.sidebar").changing or require("config.layout").scaling'), 'Opening project settles')
        editor.lua('local s,w=require("config.sidebar").state();vim.api.nvim_win_set_width(w,46);'
                   'for _,win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                   'if vim.bo[vim.api.nvim_win_get_buf(win)].filetype=="aerial" then vim.api.nvim_win_set_height(win,10) end end;'
                   'require("config.layout").save()')
        width = editor.lua('local s,w=require("config.sidebar").state();return vim.api.nvim_win_get_width(w)')
        filebuf = editor.lua('return vim.fn.bufnr(...)', str(source))
        tab('Git','git_status')
        editor.wait(lambda:'ide_git_history' in panels(), 'Git graph replaces symbols')
        editor.lua('local s=require("neo-tree.sources.manager").get_state("filesystem");'
                   'require("neo-tree.ui.renderer").show_nodes({{id=s.path,path=s.path,name="Late scan",type="directory"}},s)')
        assert current()=='git_status', 'Delayed Files scan must not override chosen Git tab'
        assert 'aerial' not in panels()
        editor.wait(lambda:editor.lua('local c=require("config.sidebar").commits;return c and c[1] and c[1].commit') == git(repo,'rev-parse','HEAD'), 'Graph starts at HEAD')
        graph = editor.lua('return vim.api.nvim_buf_get_lines(require("config.sidebar").history_buf,0,-1,false)')
        assert 'HEAD' in graph[0] and 'Baseline' in graph[0], graph
        tab('Tabs','buffers')
        assert 'aerial' not in panels() and 'ide_git_history' not in panels()
        editor.wait(lambda:'ide_terminal_list' in panels(), 'Terminal list remains in bottom panel')
        docs = editor.lua('local s=require("neo-tree.sources.manager").get_state("buffers");return vim.api.nvim_buf_get_lines(s.bufnr,0,-1,false)')
        assert not any('bash' in row or 'TERMINALS' in row for row in docs), docs
        terminalbuf = editor.lua('return require("config.terminals").items[1].buf')
        assert terminalbuf
        position = editor.lua('local w=require("config.terminals").list_win;local p=vim.api.nvim_win_get_position(w);return {p[1]+2,p[2]+4}')
        editor.click(*position)
        editor.wait(lambda:editor.lua('return vim.api.nvim_get_current_buf()')==terminalbuf, 'Click terminal focuses its bottom split')
        assert editor.lua('return vim.api.nvim_win_get_buf(require("config.ide").editor_window())')==filebuf, 'Terminal must not replace document'
        assert editor.lua('local p=vim.api.nvim_win_get_position(require("config.ide").editor_window());'
                          'local t=vim.api.nvim_win_get_position(vim.fn.win_findbuf(...)[1]);return t[1]>p[1] and t[2]==p[2]',terminalbuf)
        tab('Projects','projects')
        assert not any(ft in panels() for ft in ['aerial','ide_git_history'])
        tab('Files','filesystem')
        editor.wait(lambda:'aerial' in panels(), 'Files restores symbols')
        assert editor.lua('local s,w=require("config.sidebar").state();return vim.api.nvim_win_get_width(w)')==width, ('Sidebar width survives every source switch', width, editor.lua('local s,w=require("config.sidebar").state();return {width=vim.api.nvim_win_get_width(w),sizes=require("config.layout").sizes,ratios=require("config.layout").ratios}'))
        assert editor.lua('for _,win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                          'if vim.bo[vim.api.nvim_win_get_buf(win)].filetype=="aerial" then return vim.api.nvim_win_get_height(win) end end')==10, 'Symbol height survives source switches'
        tab('Git','git_status')
        # Counts and one real button click: divergent histories merge, then push.
        (repo/'local.txt').write_text('local\n');git(repo,'add','.');git(repo,'commit','-m','Local change')
        (peer/'remote.txt').write_text('remote\n');git(peer,'add','.');git(peer,'commit','-m','Remote change');git(peer,'push')
        editor.wait(lambda:not editor.lua('return require("config.git_sync").fetching[require("config.ide").root()]'), 'Initial automatic fetch finishes')
        editor.lua('require("config.git_sync").fetch(require("config.ide").root(),true)')
        editor.wait(lambda:not editor.lua('return require("config.git_sync").fetching[require("config.ide").root()]'), 'Background fetch sees remote commit')
        editor.wait(lambda:editor.lua('return require("config.git_sync").label()')=='[↑1 ↓1]', 'Both outgoing and incoming commit counts')
        editor.lua('vim.api.nvim_set_current_win(require("config.ide").editor_window());vim.cmd("redraw!")')
        def sync_position():
            editor.lua('vim.cmd("redraw!")')
            for row, cells in enumerate(editor.grid):
                text=''.join(cells)
                if '[↑1 ↓1]' in text:return row,text.index('[↑1 ↓1]')+2
        editor.wait(sync_position,'Synchronization button visible next to branch')
        editor.click(*sync_position())
        editor.wait(lambda:git(repo,'rev-parse','HEAD')==git(remote,'rev-parse','HEAD'), 'One click pulls and pushes')
        editor.wait(lambda:editor.lua('return require("config.git_sync").label()')=='[↑0 ↓0]', 'Counters return to zero')
        assert (repo/'remote.txt').read_text()=='remote\n'
        git(peer,'pull'); assert (peer/'local.txt').read_text()=='local\n'
        editor.wait(lambda:editor.lua('local c=require("config.sidebar").commits;return c and c[1] and c[1].commit') == git(repo,'rev-parse','HEAD'), 'Graph refreshes after synchronization')
        # A conflicting pull stops before push and preserves both remote tips.
        source.write_text('local conflict\n');git(repo,'add','.');git(repo,'commit','-m','Local conflict')
        (peer/'code.lua').write_text('remote conflict\n');git(peer,'add','.');git(peer,'commit','-m','Remote conflict');git(peer,'push')
        remote_tip=git(remote,'rev-parse','HEAD');local_tip=git(repo,'rev-parse','HEAD')
        editor.lua('require("config.git_sync").sync()')
        editor.wait(lambda:not editor.lua('return require("config.git_sync").busy'), 'Conflicting synchronization stops')
        assert git(remote,'rev-parse','HEAD')==remote_tip and git(repo,'rev-parse','HEAD')==local_tip
        assert git(repo,'diff','--name-only','--diff-filter=U')=='code.lua'
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
    finally:editor.close()
    editor=Editor(repo,state)
    try:
        editor.wait(lambda:editor.lua('local s=require("config.sidebar").state();return s and s.name')=='filesystem','Startup in project uses Files')
    finally:editor.close()
    print('PASS: tab order, Home/Projects and directory/Files startup, complete sidebar transitions and saved sizes, HEAD graph, '
          'documents versus terminal list, terminal click preserves editor, one-button pull/merge/push, '
          'ahead/behind counters and graph refresh, conflicting pull never pushes')
