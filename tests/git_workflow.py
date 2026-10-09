"""Stage, unstage, discard and commit via the installed sidebar, in a disposable repo."""
from pathlib import Path
import subprocess
import tempfile
import time
from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-git-workflow-') as directory:
    root=Path(directory);repo=root/'repo';repo.mkdir()
    def git(*args):
        return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.STDOUT).decode().strip()
    git('init','-b','main');git('config','user.name','UI Test');git('config','user.email','ui@example.invalid')
    file=repo/'both.txt';file.write_text('baseline\n')
    other=repo/'other.txt';other.write_text('baseline other\n')
    rename=repo/'rename-before.txt';rename.write_text('rename contents\n')
    git('add','.');git('commit','-m','Baseline')
    file.write_text('staged version\n');git('add','both.txt');file.write_text('working version\n')
    other.write_text('changed other\n')
    new=repo/'untracked.txt';new.write_text('new contents\n')
    git('mv','rename-before.txt','rename-after.txt')
    editor=Editor(repo,root/'state')
    try:
        editor.lua('require("config.ide").git_explorer();vim.cmd("stopinsert")')
        def node_exists(id):
            return editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status");return s.tree and s.tree:get_node(...)~=nil',id)
        editor.wait(lambda:node_exists(str(file)) and node_exists(str(file)+'::staged'),'Separate staged/working nodes for same file')
        assert editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status");return s.tree:get_node(...).extra.original',str(repo/'rename-after.txt')+'::staged')=='rename-before.txt'
        def node_position(id):
            return editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status");local p=vim.api.nvim_win_get_position(s.winid);'
                              'local _,line=s.tree:get_node(...);return {p[1]+line,p[2]+7}',id)
        def context_action(id,label):
            row,col=node_position(id)
            editor.call('nvim_input_mouse','right','press','',0,row,col)
            editor.call('nvim_input_mouse','right','release','',0,row,col)
            def menu_position():
                editor.lua('vim.cmd("redraw!")')
                for row,line in enumerate(editor.grid):
                    text=''.join(line)
                    if label in text:return row,text.index(label)+3
            editor.wait(menu_position,'Context action '+label)
            editor.click(*menu_position())
        context_action(str(file)+'::staged','Unstage Changes')
        editor.wait(lambda:git('show',':both.txt')=='baseline','Unstage keeps worktree edits')
        editor.wait(lambda:not node_exists(str(file)+'::staged'),'Unstage removes index row')
        assert file.read_text()=='working version\n'
        context_action(str(other),'Stage Changes')
        editor.wait(lambda:git('show',':other.txt')=='changed other','Right-click stages changes')
        editor.wait(lambda:node_exists(str(other)+'::staged'),'Refreshed staged group')
        editor.wait(lambda:not node_exists(str(other)),'Stage removes working row')
        # Section commands must also work for every child, including unsaved buffers.
        editor.lua('require("config.ide").open_file(...);vim.api.nvim_buf_set_lines(0,0,-1,false,{"unsaved working version"});require("config.ide").git_explorer()',str(file))
        editor.wait(lambda:node_exists(str(file)),'Working section present')
        editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status");require("config.git").action(s,"stage",s.tree:get_node(s.path.."::changes"))')
        editor.wait(lambda:git('show',':both.txt')=='unsaved working version' and git('show',':untracked.txt')=='new contents','Stage section saves unsaved files and stages all children')
        editor.wait(lambda:not node_exists(str(file)),'Working group empty after stage')
        # Discard cancellation preserves edits. Confirmation restores index and backs up.
        other.write_text('discard me\n');editor.lua('require("config.git").refresh()')
        editor.wait(lambda:node_exists(str(other)),'Discard candidate refreshed')
        editor.lua('local old=vim.ui.select;vim.ui.select=function(_,_,cb) cb("Cancel") end;local s=require("neo-tree.sources.manager").get_state("git_status");'
                   'require("config.git").action(s,"discard",s.tree:get_node(...));vim.ui.select=old',str(other))
        assert other.read_text()=='discard me\n'
        editor.lua('local old=vim.ui.select;vim.ui.select=function(_,_,cb) cb("Discard changes") end;local s=require("neo-tree.sources.manager").get_state("git_status");'
                   'require("config.git").action(s,"discard",s.tree:get_node(...));vim.ui.select=old',str(other))
        editor.wait(lambda:other.read_text()=='changed other\n','Discard restores index version')
        backups=list((root/'state'/'nvim'/'git-discard').rglob('other.txt'))
        assert backups and backups[0].read_text()=='discard me\n'
        assert git('show',':other.txt')=='changed other','Discard does not unstage'
        # A real editable field, then Enter creates a commit only from index.
        extra=repo/'left-unstaged.txt';extra.write_text('must remain unstaged\n')
        editor.lua('require("config.git").refresh()')
        editor.wait(lambda:node_exists(str(extra)),'Unstaged extra exists')
        p=editor.lua('local f=require("config.git").inputs[...];return vim.api.nvim_win_get_position(f.win)',str(repo))
        editor.click(p[0],p[1]+1)
        editor.call('nvim_input','Commit through sidebar')
        editor.wait(lambda:editor.lua('return require("config.git").messages[...]',str(repo))=='Commit through sidebar','Inline field receives typing')
        editor.call('nvim_input','<CR>')
        editor.wait(lambda:git('log','-1','--format=%s')=='Commit through sidebar','Enter commits staged changes')
        assert git('status','--porcelain')=='?? left-unstaged.txt'
        assert git('show','HEAD:both.txt')=='unsaved working version'
        assert editor.lua('return require("config.git").messages[...]',str(repo))==''
        editor.wait(lambda:node_exists(str(extra)),'Sidebar refresh after commit')
        assert 'Error rendering' not in editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status");return table.concat(vim.api.nvim_buf_get_lines(s.bufnr,0,-1,false),"\\n")')
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
    finally:editor.close()
    print('PASS: mixed staged/worktree nodes and rename parsing, real right-click stage/unstage, stage-all saves unsaved edits, discard cancellation/backup/index preservation, inline field Enter commits only staged changes and refreshes groups')
