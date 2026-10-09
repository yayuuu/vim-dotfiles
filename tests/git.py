"""Check Git sidebar refresh and clickable branch switching in an isolated repo."""
from pathlib import Path
import subprocess
import tempfile
from ui import Editor
import time


with tempfile.TemporaryDirectory(prefix='nvim-git-controls-') as directory:
    root = Path(directory)
    repo, state = root / 'repo', root / 'state'
    repo.mkdir(); state.mkdir()

    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.STDOUT).decode().strip()

    git('init', '-b', 'master')
    git('config', 'user.name', 'UI Test')
    git('config', 'user.email', 'ui-test@example.invalid')
    tracked = repo / 'tracked.txt'
    tracked.write_text('Master branch\n')
    git('add', '.'); git('commit', '-m', 'Initial test commit')
    git('switch', '-c', 'feature')
    tracked.write_text('Feature branch\n')
    git('commit', '-am', 'Feature test commit')
    git('switch', 'master')
    editor = Editor(repo, state)
    try:
        editor.lua('require("config.ide").open_file(...)', str(tracked))
        # A previously visited clean repository must not remain bound to Git
        # after opening another project and clicking the source-selector tab.
        other = root / 'other-repository'; other.mkdir()
        subprocess.run(['git','-C',str(other),'init','-q'],check=True)
        editor.lua('require("config.ide").open_project(...);require("config.ide").git_explorer()',str(other))
        editor.lua('require("config.ide").open_project(...);vim.cmd("stopinsert");vim.cmd("redraw!")',str(repo))
        time.sleep(.5)  # Let the project switch and filesystem watcher settle.
        # The source-selector callback dispatches this exact command, without
        # an explicit directory; its previously cached path must be updated.
        editor.lua('require("neo-tree.command").execute({source="git_status",action="focus"})')
        editor.wait(lambda: editor.lua('return require("neo-tree.sources.manager").get_state("git_status").path')==str(repo) and editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status"); local current=require("neo-tree.sources.manager").get_state_for_window(s.winid);return current and current.name')=='git_status','Git follows changed project')
        new = repo / 'new.txt'; new.write_text('Untracked\n')
        editor.lua('vim.cmd("redraw!")')
        def header_location():
            return editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status"); '
                              'local p=vim.api.nvim_win_get_position(s.winid); '
                              'local _,line=s.tree:get_node(s.path); '
                              'local text=vim.api.nvim_buf_get_lines(s.bufnr,line-1,line,false)[1]; '
                              'local tabs=vim.api.nvim_eval_statusline(vim.wo[s.winid].winbar,{winid=s.winid,use_winbar=true}).str; '
                              'return {p[1]+line,p[2],vim.api.nvim_win_get_width(s.winid),text,tabs}')
        def header_is_right_aligned():
            editor.lua('vim.cmd("redraw!")')
            row,col,width,text,tabs=header_location()
            return ''.join(editor.grid[row][col:col+width]).endswith('[⟳]')
        editor.wait(header_is_right_aligned,'Refresh arrow at right edge')
        location=header_location()
        assert 'GIT STATUS' in location[3],location
        assert '[⟳]' not in location[4],location
        for _ in range(3):
            location=header_location()
            editor.click(location[0],location[1]+location[2]-2)
            assert editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status"); '
                              'return vim.api.nvim_win_call(s.winid,function() return vim.fn.winsaveview().leftcol end)')==0
            assert header_is_right_aligned()
        editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status");vim.api.nvim_win_set_width(s.winid,46)')
        editor.wait(header_is_right_aligned,'Refresh arrow follows panel resize')
        location=header_location()
        editor.click(location[0],location[1]+location[2]-2)
        editor.wait(lambda: editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status"); '
                                      'return s.tree:get_node(...)~=nil', str(new)), 'Refresh button scans status')
        new.unlink()
        editor.call('nvim_input', '<F5>')
        editor.wait(lambda: editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status"); '
                                      'return s.tree:get_node(...)==nil', str(new)), 'F5 refresh removes vanished file')
        editor.lua('vim.api.nvim_set_current_win(require("config.ide").editor_window()); vim.cmd("redraw!")')
        def status_position(branch):
            editor.lua('vim.cmd("redraw!")')
            for row in range(45,48):
                line=''.join(editor.grid[row])
                if 'git '+branch in line:return row,line.index('git '+branch)+5
        editor.wait(lambda: status_position('master'), 'branch statusline')
        editor.click(*status_position('master'))
        editor.wait(lambda: editor.lua('return #Snacks.picker.get({source="git_branches"})>0'), 'Branch statusline click')
        editor.wait(lambda: editor.lua('local p=Snacks.picker.get({source="git_branches"})[1]; '
                                      'return p and #p:items()>=2'), 'Branch list')
        assert editor.lua('local p=Snacks.picker.get({source="git_branches"})[1]; '
                          'for i,item in ipairs(p:items()) do if item.branch=="feature" then '
                          'p.list:view(i);p:action("confirm");return true end end;return false')
        editor.wait(lambda: git('branch', '--show-current') == 'feature', 'Branch switch')
        editor.wait(lambda: status_position('feature'), 'Refreshed branch statusline')
        assert editor.lua('return vim.api.nvim_buf_get_lines(vim.fn.bufnr(...),0,1,false)[1]', str(tracked)) == 'Feature branch'
        # Git rejects a conflicting working-tree change; our action must preserve it.
        tracked.write_text('Keep these local changes\n')
        editor.lua('require("config.git").branches()')
        editor.wait(lambda: editor.lua('local p=Snacks.picker.get({source="git_branches"})[1]; '
                                      'return p and #p:items()>=2'), 'Second branch list')
        editor.lua('local p=Snacks.picker.get({source="git_branches"})[1]; '
                   'for i,item in ipairs(p:items()) do if item.branch=="master" then '
                   'p.list:view(i);p:action("confirm");return end end')
        editor.wait(lambda: editor.lua('return #Snacks.picker.get({source="git_branches"})==0'), 'Picker closes')
        import time
        time.sleep(.3)
        assert git('branch', '--show-current') == 'feature'
        assert tracked.read_text() == 'Keep these local changes\n'
    finally:
        editor.close()
    print('PASS: changed project Git source follows current repo; Refresh arrow pinned right across resize; '
          'repeated clicks keep horizontal scroll at zero; F5 status scan, real statusline branch click, '
          'branch picker/switch, updated statusline and file contents, conflicting local changes preserved')
