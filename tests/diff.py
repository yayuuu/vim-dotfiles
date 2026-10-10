"""Exercise sidebar diff clicks, editing, saving and buffer-tab transitions."""
from pathlib import Path
import subprocess
import tempfile
import time
from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-diff-tabs-') as directory:
    root = Path(directory)
    repo = root / 'repo'; repo.mkdir()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.STDOUT).decode()
    git('init', '-b', 'master')
    git('config', 'user.name', 'UI Test'); git('config', 'user.email', 'ui@example.invalid')
    source = repo / 'src' / 'nested'; source.mkdir(parents=True)
    file = source / 'tracked.txt'
    before = ['original', 'keep', 'removed', 'last']
    file.write_text('\n'.join(before) + '\n')
    other = repo / 'other.txt'; other.write_text('Other editor tab\n')
    git('add', '.'); git('commit', '-m', 'Baseline')
    after = ['replacement', 'keep', 'last', 'added']
    file.write_text('\n'.join(after) + '\n')
    editor = Editor(repo, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(other))
        time.sleep(.3)
        def panels():
            return editor.lua('local result={};for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                              'local ft=vim.bo[vim.api.nvim_win_get_buf(w)].filetype; '
                              'if ft=="neo-tree" or ft=="aerial" or ft=="snacks_terminal" then '
                              'result[ft]={vim.api.nvim_win_get_width(w),vim.api.nvim_win_get_height(w)} end end;return result')
        dimensions = panels()
        editor.lua('require("config.ide").git_explorer()')
        editor.wait(lambda: editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status");return s.tree and s.tree:get_node(...)~=nil',str(file)), 'Changed file in Git')
        def assert_tree_rendered():
            lines = editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status");return vim.api.nvim_buf_get_lines(s.bufnr,0,-1,false)')
            assert not any('Error rendering' in line for line in lines), lines
            assert any('src' in line for line in lines), lines
            assert any('nested' in line for line in lines), lines
        assert_tree_rendered()
        # Repeated redraw/resize also renders expanded directories, not just
        # the root header that the original fixture covered.
        editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status");vim.api.nvim_win_set_width(s.winid,38);require("config.git").header(s)')
        time.sleep(.2)
        assert_tree_rendered()
        dimensions = panels()
        def node_position(path):
            return editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status");'
                              'local p=vim.api.nvim_win_get_position(s.winid);local _,line=s.tree:get_node(...);'
                              'return {p[1]+line,p[2]+6}',str(path))
        editor.click(*node_position(file))
        editor.wait(lambda: editor.lua('return require("config.diff").active~=nil'), 'Single Git click opens diff')
        active = editor.lua('return require("config.diff").active')
        entry = editor.lua('local e=require("config.diff").entries[...]; return {buf=e.buf,before=e.before,filebuf=e.filebuf}',active['buf'])
        time.sleep(.25)
        assert panels()==dimensions,(panels(),dimensions)
        assert editor.call('nvim_buf_get_lines',entry['before'],0,-1,False)==before
        assert editor.call('nvim_buf_get_lines',entry['buf'],0,-1,False)==after
        assert editor.lua('local d=require("config.diff").active;return vim.wo[d.left].diff and vim.wo[d.right].diff')
        assert not editor.lua('return vim.bo[...].modifiable',entry['before'])
        assert not editor.lua('return pcall(vim.api.nvim_buf_set_lines,...,0,1,false,{"forbidden"})',entry['before'])
        assert editor.lua('return vim.bo[...].modifiable',entry['buf'])
        assert editor.lua('local n=0;for _,b in ipairs(vim.api.nvim_list_bufs()) do if vim.bo[b].buflisted and vim.b[b].ide_diff_file then n=n+1 end end;return n')==1
        def tab_position(label):
            editor.lua('vim.cmd("redraw!")')
            line=''.join(editor.grid[1])
            if label in line:return 1,line.index(label)+2
        def middle_click(label):
            editor.wait(lambda: tab_position(label), 'Middle click target visible: '+label)
            row,col=tab_position(label)
            editor.call('nvim_input_mouse','middle','press','',0,row,col)
            editor.call('nvim_input_mouse','middle','release','',0,row,col)
            time.sleep(.1)
            editor.lua('vim.cmd("redraw!")')
        editor.wait(lambda: tab_position('tracked.txt (diff)'), 'One visible diff tab')
        def shared_strip_spans_editor():
            return editor.lua('local d=require("config.diff").active;local t=require("config.editor_tabs");'
                              'if not t.win or not vim.api.nvim_win_is_valid(t.win) then return false end;'
                              'local l=vim.api.nvim_win_get_position(d.left);local r=vim.api.nvim_win_get_position(d.right);'
                              'local p=vim.api.nvim_win_get_position(t.win);local h=vim.api.nvim_win_get_position(d.header);return p[1]==h[1] and p[1]<l[1] and p[2]==l[2] '
                              'and vim.api.nvim_win_get_width(t.win)==r[2]+vim.api.nvim_win_get_width(d.right)-l[2]')
        editor.wait(shared_strip_spans_editor, 'Shared strip starts at left column and spans both columns')
        assert editor.lua('local d=require("config.diff").active;return vim.wo[d.left].winbar=="" and vim.wo[d.right].winbar==""')
        assert editor.lua('return vim.wo[...].winhighlight',active['left']).startswith('DiffAdd:DesktopDiffRemoved')
        palette = editor.lua('return require("config.colors").palette')
        for group, color in [('DiffAdd', 'diff_added_bg'), ('DesktopDiffRemoved', 'diff_deleted_bg'), ('DiffChange', 'diff_changed_bg')]:
            assert editor.lua('return vim.api.nvim_get_hl(0,{name=...}).bg', group) == int(palette[color][1:], 16)
        def line_highlights():
            return editor.lua('local d=require("config.diff").active;return vim.api.nvim_win_call(d.right,function()'
                              'local result={};for l,text in ipairs(vim.api.nvim_buf_get_lines(0,0,-1,false)) do '
                              'result[text]=vim.fn.synIDattr(vim.fn.diff_hlID(l,1),"name") end;return result end)')
        assert line_highlights()['keep']==''
        assert line_highlights()['last']==''
        # Native diff keeps hidden buffers in its comparison set unless both
        # windows leave diff mode. Another file must never color this one.
        editor.lua('require("config.diff").open(...)',str(other))
        assert line_highlights()['Other editor tab']=='',line_highlights()
        editor.lua('require("config.diff").open(...)',str(file))
        assert line_highlights()['keep']=='',line_highlights()
        assert line_highlights()['last']=='',line_highlights()
        assert line_highlights()['replacement']!='',line_highlights()
        for _ in range(12):
            editor.lua('require("config.diff").open(...)',str(other))
            assert line_highlights()['Other editor tab']=='',line_highlights()
            editor.lua('require("config.diff").open(...)',str(file))
            assert line_highlights()['keep']=='',line_highlights()
        editor.lua('local d=require("config.diff");require("config.ide").close_buffer(d.paths[...])',str(other))
        editor.lua('vim.api.nvim_buf_set_lines(...,0,1,false,{"Edited in diff"})',entry['buf'])
        editor.wait(lambda: editor.call('nvim_buf_get_lines',entry['filebuf'],0,1,False)==['Edited in diff'], 'Edits reach regular file tab')
        editor.click(*tab_position('other.txt'))
        editor.wait(lambda: editor.lua('return require("config.diff").active==nil'), 'Normal tab removes comparison column')
        editor.wait(lambda: editor.lua('local t=require("config.editor_tabs");return t.win and vim.api.nvim_win_is_valid(t.win)'), 'Normal editor has scrollable tabs')
        assert panels()==dimensions,(panels(),dimensions)
        assert not editor.call('nvim_win_is_valid',active['left'])
        assert editor.lua('return vim.api.nvim_buf_get_name(0)')==str(other)
        editor.wait(lambda: tab_position('tracked.txt (diff)'), 'Diff tab remains available')
        editor.click(*tab_position('tracked.txt (diff)'))
        editor.wait(lambda: editor.lua('return require("config.diff").active~=nil'), 'Diff tab restores two columns')
        editor.wait(shared_strip_spans_editor, 'Shared strip restored with comparison')
        editor.lua('require("config.ide").save()')
        assert file.read_text().startswith('Edited in diff\n')
        assert not editor.lua('return vim.bo[...].modified',entry['buf'])
        assert not editor.lua('return vim.bo[...].modified',entry['filebuf'])
        # Keyboard cycling is also handled, including a cycle made from the
        # read-only column instead of the editable window.
        editor.lua('vim.cmd("stopinsert");vim.cmd("BufferLineCycleNext")')
        editor.wait(lambda: editor.lua('return require("config.diff").active==nil'), 'Keyboard normal tab closes diff split')
        editor.lua('require("config.ide").open_file(nil,...)',entry['filebuf'])
        editor.lua('vim.api.nvim_buf_set_lines(0,0,1,false,{"Unsaved normal edit"})')
        editor.lua('require("config.diff").open(...)',str(file))
        assert editor.call('nvim_buf_get_lines',entry['buf'],0,1,False)==['Unsaved normal edit']
        middle_click('tracked.txt (diff)')
        editor.wait(lambda: editor.lua('return require("config.diff").entries[...] == nil',entry['buf']), 'Middle click closes diff card')
        assert editor.lua('return require("config.diff").active==nil')
        assert editor.call('nvim_buf_get_lines',entry['filebuf'],0,1,False)==['Unsaved normal edit']
        assert editor.lua('return vim.bo[...].modified',entry['filebuf'])
        closable=repo/'close-me.txt';closable.write_text('Middle click ordinary tab\n')
        for mode in ['normal','insert']:
            editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")',str(closable))
            if mode=='insert':editor.lua('vim.cmd("startinsert")')
            middle_click('close-me.txt')
            editor.wait(lambda: str(closable) not in editor.files(), 'Middle click closes ordinary card from '+mode+' mode')
        # New files have an empty HEAD side; deleted files have an empty current side.
        new = repo / 'new.txt'; new.write_text('New file\n')
        editor.lua('require("config.diff").open(...)',str(new))
        assert editor.lua('local d=require("config.diff");return vim.api.nvim_buf_get_lines(d.entries[d.active.buf].before,0,-1,false)')==['']
        editor.lua('require("config.ide").open_file(...)',str(closable))
        editor.lua('require("config.diff").open(...)',str(new))
        middle_click('close-me.txt')
        editor.wait(lambda: str(closable) not in editor.files(), 'Middle click closes ordinary card from shared diff strip')
        assert editor.lua('return require("config.diff").active~=nil')
        other.unlink()
        # An already loaded clean file must also reflect a deletion on disk.
        editor.lua('require("config.diff").leave()')
        editor.lua('require("config.diff").open(...)',str(other))
        assert editor.lua('return vim.api.nvim_buf_get_lines(0,0,-1,false)')==['']
        assert editor.lua('local d=require("config.diff");return vim.api.nvim_buf_get_lines(d.entries[d.active.buf].before,0,-1,false)')==['Other editor tab']
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
    finally:
        editor.close()
    print('PASS: Git single click; one diff tab/two code columns; read-only HEAD; editable current version; '
          'add/delete/change colors; edit synchronization/save; mouse and keyboard tab transitions; '
          'shared clickable strip spans both columns; nested Git directory render/resize; '
          '24 diff switches keep unchanged lines uncolored and editor responsive; '
          'middle click closes diff and normal tabs in normal/insert mode; '
          'panel dimensions; unsaved edits survive closing diff; added/deleted files')
