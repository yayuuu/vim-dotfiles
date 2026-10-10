"""Added-file diffs scroll from either side without snapping back to empty HEAD."""
from pathlib import Path
import subprocess
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-diff-vertical-') as directory:
    root = Path(directory)
    subprocess.run(['git', 'init', '-b', 'main', directory], check=True, stdout=subprocess.DEVNULL)
    files = []
    for number in range(2):
        file = root / f'added_{number}.lua'
        file.write_text('\n'.join(f'-- Line {i:03} ' + 'long content ' * 20 for i in range(180))+'\n')
        files.append(file)
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").git_explorer()')
        def open_diff(file):
            def pointer():
                return editor.lua('local s=require("config.sidebar").state();if not s.tree then return end;'
                                  'local n,line=s.tree:get_node(...);if n then return vim.fn.screenpos(s.winid,line,6) end', str(file))
            editor.wait(pointer, 'Added file appears in Git')
            editor.wait(lambda: editor.lua('return not require("config.layout").scaling and not require("config.sidebar").changing'), 'Git layout settled before clicking')
            p = pointer()
            editor.click(p['row']-1,p['col']-1)
            editor.wait(lambda: editor.lua('local d=require("config.diff").active;return d and require("config.diff").entries[d.buf].path==...', str(file)), 'Git click opens diff')
            return editor.lua('local d=require("config.diff").active;return {left=d.left,right=d.right}')
        d = open_diff(files[0])
        def top():
            return editor.lua('return vim.api.nvim_win_call(...,vim.fn.winsaveview).topline', d['right'])
        def wheel(side, direction, count):
            p = editor.call('nvim_win_get_position', d[side])
            for _ in range(count):
                editor.call('nvim_input_mouse', 'wheel', direction, '', 0, p[0]+10, p[1]+10)
            editor.lua('vim.cmd("redraw!")')
        for mode in ('normal', 'insert'):
            editor.lua('local w=...;vim.api.nvim_set_current_win(w);vim.cmd("stopinsert");vim.api.nvim_win_set_cursor(w,{1,0});'
                       'vim.api.nvim_win_call(w,function()vim.fn.winrestview({topline=1,topfill=0,lnum=1,col=0})end)', d['right'])
            if mode == 'insert': editor.lua('vim.cmd("startinsert")')
            before = top()
            wheel('right','down',8)
            editor.wait(lambda: top()>before+10, 'Mouse wheel scrolls added-file diff downward in '+mode)
            reached = top()
            # Allow deferred scrollbar redraws to run before checking for a snap.
            editor.wait(lambda: editor.lua('return not require("config.hscroll").pending'), 'Scrollbar redraw settled')
            assert top() >= reached, 'Empty HEAD must not reset editable side to start'
            wheel('right','up',4)
            editor.wait(lambda: top()<reached, 'Upward wheel scrolls back in '+mode)
            before = top()
            wheel('left','down',4)
            editor.wait(lambda: top()>before, 'Wheel over empty HEAD scrolls comparison downward in '+mode)
        d = open_diff(files[1])
        assert editor.call('nvim_win_is_valid', d['right'])
        # Scrolling the Git list beside an Insert/Select editor must not run an
        # insertion command against the readonly tree.
        for i in range(60): (root / f'extra_{i:03}.txt').write_text('Extra\n')
        editor.lua('require("config.git").refresh()')
        editor.wait(lambda: editor.lua('local s=require("config.sidebar").state();return s.tree:get_node(...)~=nil', str(root/'extra_059.txt')), 'Git overflow refreshed')
        editor.lua('vim.api.nvim_set_current_win(...);vim.cmd("stopinsert");vim.cmd("normal! gh")', d['right'])
        assert editor.lua('return vim.fn.mode()') == 's', 'Regression is exercised in Select mode'
        tree = editor.lua('return require("config.sidebar").state().winid')
        p = editor.call('nvim_win_get_position', tree)
        for _ in range(3): editor.call('nvim_input_mouse','wheel','down','',0,p[0]+12,p[1]+5)
        editor.wait(lambda: editor.lua('return vim.api.nvim_win_call(...,vim.fn.winsaveview).topline', tree)>1, 'Sidebar scroll works beside Select mode')
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'Error executing' not in messages and 'Vertical scrollbar:' not in messages and 'E21' not in messages, messages
        print('PASS: added-file diff wheel scrolling in Normal/Insert, no empty-HEAD snap, another diff opens, readonly Git list scrolls beside Select mode without errors.')
    finally:
        editor.close()
