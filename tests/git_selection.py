"""Git source entry, Shift-click ranges and context actions through real mouse input."""
from pathlib import Path
import subprocess
import tempfile
import time
from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-git-selection-') as directory:
    root=Path(directory);repo=root/'repo';repo.mkdir()
    def git(*args):
        return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.STDOUT).decode().strip()
    git('init','-b','main');git('config','user.name','UI Test');git('config','user.email','ui@example.invalid')
    files={name:repo/(name+'.txt') for name in 'abcdefghz'}
    for name,path in files.items():path.write_text('baseline '+name+'\n')
    git('add','.');git('commit','-m','Baseline')
    for name,path in files.items():path.write_text('changed '+name+'\n')
    git('add',*[n+'.txt' for n in 'efghz'])
    files['z'].write_text('extra working z\n')
    editor=Editor(repo,root/'state')
    try:
        def exists(id):
            return editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status");return s.tree and s.tree:get_node(...)~=nil',id)
        def expanded():
            return editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status");if not s.tree then return false end;'
                              'if not s.winid or not vim.api.nvim_win_is_valid(s.winid) or vim.api.nvim_win_get_buf(s.winid)~=s.bufnr '
                              'or require("neo-tree.sources.manager").get_state_for_window(s.winid)~=s then return false end;'
                              'for _,id in ipairs({s.path,s.path.."::staged",s.path.."::changes"}) do local n=s.tree:get_node(id);if not n or not n:is_expanded() then return false end end;return true')
        def pos(id):
            return editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status");local p=vim.api.nvim_win_get_position(s.winid);'
                              'local _,line=s.tree:get_node(...);if line then local screen=vim.fn.screenpos(s.winid,line,1);'
                              'if screen.row>0 then return {screen.row-1,p[2]+8} end end',id)
        def selected():
            return sorted(editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status");return vim.tbl_keys(s.ide_selected or {})'))
        def click(id,shift=False,release_shift=None,ctrl=False):
            row,col=pos(id)
            editor.call('nvim_input_mouse','left','press','C' if ctrl else 'S' if shift else '',0,row,col)
            if release_shift is None:release_shift=shift or ctrl
            editor.call('nvim_input_mouse','left','release','C' if ctrl and release_shift is not False else 'S' if release_shift else '',0,row,col)
            time.sleep(.15);editor.lua('vim.cmd("redraw!")')
        def context(id):
            row,col=pos(id)
            editor.call('nvim_input_mouse','right','press','',0,row,col)
            editor.call('nvim_input_mouse','right','release','',0,row,col)
            def labels():
                return editor.lua('for b,data in pairs(require("menu.state").bufs) do if vim.api.nvim_buf_is_valid(b) then local r={};for _,item in ipairs(data.items) do r[#r+1]=item.name end;return r end end')
            editor.wait(labels,'Context menu opens')
            return labels()
        def choose(label):
            def location():
                editor.lua('vim.cmd("redraw!")')
                for row,line in enumerate(editor.grid):
                    text=''.join(line)
                    if label in text:return row,text.index(label)+3
            editor.wait(location,'Menu action '+label);editor.click(*location())
        def close_menu():editor.lua('require("menu.utils").delete_old_menus()')
        def source_tab(name):
            editor.lua('vim.cmd("redraw!")')
            text=''.join(editor.grid[1]);editor.click(1,text.index(name)+1)

        editor.lua('require("config.ide").git_explorer();vim.cmd("stopinsert")')
        editor.wait(expanded,'Both Git groups initially expanded')
        assert pos(str(files['a'])) and pos(str(files['e'])+'::staged')
        # A cached tree must reopen expanded when using the actual source-selector tabs.
        click(str(repo)+'::staged');click(str(repo)+'::changes')
        assert not expanded()
        source_tab('Files');source_tab('Git')
        editor.wait(expanded,'Reentering cached Git source expands groups')

        click(str(files['a']))
        editor.wait(lambda:selected()==[str(files['a'])],'Plain click sets selection anchor')
        proxy=editor.lua('return require("config.diff").active.buf')
        click(str(files['c']),True)
        expected=sorted(str(files[n]) for n in 'abc')
        assert selected()==expected,selected()
        assert editor.lua('return require("config.diff").active.buf')==proxy,'Shift-click selects without opening another diff'
        assert editor.lua('return vim.fn.mode()')=='n','No native text selection'
        # Selection highlighting covers each selected row and survives a redraw/resize.
        def highlights():
            return editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status");return #vim.api.nvim_buf_get_extmarks(s.bufnr,'
                              'vim.api.nvim_create_namespace("DesktopIDEGitSelection"),0,-1,{details=true})')
        assert highlights()==3
        # Some terminal paths drop Shift on release. It must not become a new
        # plain click that clears the range or opens the last file's diff.
        for mode in ['normal','insert']:
            click(str(files['a']))
            assert selected()==[str(files['a'])] and highlights()==1
            if mode=='insert':editor.lua('vim.cmd("startinsert")')
            click(str(files['c']),True,False)
            assert selected()==expected,('Shift press/plain release',mode,selected())
            assert highlights()==3
            assert editor.lua('return require("config.diff").active.buf')==proxy
            assert editor.lua('return vim.fn.mode()')=='n'
        # Ctrl toggles just the clicked file, without opening another diff.
        for mode in ['normal','insert']:
            click(str(files['a']))
            if mode=='insert':editor.lua('vim.cmd("startinsert")')
            click(str(files['c']),ctrl=True,release_shift=False if mode=='insert' else None)
            assert selected()==sorted(str(files[n]) for n in 'ac') and highlights()==2
            assert editor.lua('return require("config.diff").active.buf')==proxy
            click(str(files['a']),ctrl=True)
            assert selected()==[str(files['c'])] and highlights()==1
            click(str(files['c']),ctrl=True)
            assert selected()==[] and highlights()==0
            click(str(files['a']))
            click(str(files['c']),True)
            assert selected()==expected
        editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status");vim.api.nvim_win_set_width(s.winid,44);require("config.git").header(s)')
        editor.wait(lambda:highlights()==3,'Selection survives redraw')
        labels=context(str(files['b']))
        assert 'Stage Changes' in labels and 'Discard Changes…' in labels and 'Unstage Changes' not in labels,labels
        assert selected()==expected,'Right-click within selection preserves range'
        choose('Stage Changes')
        editor.wait(lambda:all(git('show',':'+n+'.txt')=='changed '+n for n in 'abc'),'Stage operates on all selected files')
        editor.wait(lambda:all(exists(str(files[n])+'::staged') and not exists(str(files[n])) for n in 'abc'),'Staged range refreshes')
        assert git('show',':d.txt')=='baseline d','Unselected file is unchanged'
        editor.wait(lambda:not selected(),'Removed selected rows are pruned')

        click(str(files['e'])+'::staged');click(str(files['g'])+'::staged',True)
        expected=sorted(str(files[n])+'::staged' for n in 'efg')
        assert selected()==expected,selected()
        labels=context(str(files['f'])+'::staged')
        assert 'Unstage Changes' in labels and 'Stage Changes' not in labels and 'Discard Changes…' not in labels,labels
        choose('Unstage Changes')
        editor.wait(lambda:all(git('show',':'+n+'.txt')=='baseline '+n for n in 'efg'),'Unstage operates on all selected files')
        editor.wait(lambda:all(exists(str(files[n])) and not exists(str(files[n])+'::staged') for n in 'efg'),'Unstaged range refreshes')
        assert git('show',':h.txt')=='changed h','Other staged file stays staged'
        assert all(files[n].read_text()=='changed '+n+'\n' for n in 'efg'),'Worktree edits survive unstage'

        # Reverse Shift-click and contracting a range retain the original anchor.
        click(str(files['g']));click(str(files['d']),True)
        assert selected()==sorted(str(files[n]) for n in 'defg'),selected()
        click(str(files['f']),True)
        assert selected()==sorted(str(files[n]) for n in 'fg'),selected()
        # Right-click outside the range changes the target to that single file.
        labels=context(str(files['d']));assert selected()==[str(files['d'])]
        assert 'Stage Changes' in labels and 'Unstage Changes' not in labels
        close_menu()
        # Same path in both sections has independent identities/menu state.
        labels=context(str(files['z'])+'::staged')
        assert 'Unstage Changes' in labels and 'Discard Changes…' not in labels
        close_menu();labels=context(str(files['z']))
        assert 'Stage Changes' in labels and 'Discard Changes…' in labels and 'Unstage Changes' not in labels
        close_menu()
        # Group headings have no file-only destructive/index actions.
        labels=context(str(repo)+'::changes')
        assert not any(label in labels for label in ['Stage Changes','Unstage Changes','Discard Changes…'])
        close_menu()
        # Closing a diff menu on press must not block the next Git-file click
        # when the host loses the corresponding release.
        context(str(files['d']))
        editor.lua('vim.cmd("redraw!")')
        pointer = next((row, ''.join(cells).index('Open diff') + 3)
                       for row, cells in enumerate(editor.grid) if 'Open diff' in ''.join(cells))
        editor.call('nvim_input_mouse', 'left', 'press', '', 0, *pointer)
        editor.wait(lambda: editor.lua('return #require("menu.state").bufids==0'), 'Open diff closes its menu on press')
        click(str(files['e']))
        editor.wait(lambda: editor.lua('local d=require("config.diff").active;return d and vim.b[d.buf].ide_diff_file') == str(files['e']),
                    'Git-file click recovers after the missing menu release')
        assert not editor.lua('return require("config.ide").menu_mouse_pending')
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
    finally:editor.close()
    print('PASS: first/cached Git entry expands groups, actual Shift-click ranges and Ctrl-click toggles in normal/insert mode including releases without modifiers, selection highlighting without changing diff, right-click preserves/resets selection, selected-only stage/unstage, unstaged/staged menu filtering including partial staging, reversed/contracted ranges and refresh pruning')
