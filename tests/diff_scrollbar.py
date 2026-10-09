"""Added Markdown files get synchronized horizontal diff bars against empty HEAD."""
from pathlib import Path
import subprocess
import tempfile

from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-added-markdown-scroll-') as directory:
    root = Path(directory)
    baseline = root / 'tracked.txt'
    baseline.write_text('Baseline\n')
    subprocess.run(['git', 'init', '-b', 'main', str(root)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=UI Test', '-c', 'user.email=ui@example.invalid',
                    'commit', '-m', 'Baseline'], check=True, stdout=subprocess.DEVNULL)
    file = root / 'AGENTS.md'
    file.write_text('# Instructions\n\n' + 'Long Markdown content ' * 20 + '\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").git_explorer()')
        def position():
            return editor.lua('local s=require("neo-tree.sources.manager").get_state("git_status");'
                              'if not s.tree then return end;local n,line=s.tree:get_node(...);if not n then return end;'
                              'local p=vim.api.nvim_win_get_position(s.winid);return {p[1]+line,p[2]+6}', str(file))
        editor.wait(position, 'New Markdown file appears in Git')
        editor.click(*position())
        editor.wait(lambda: editor.lua('return require("config.diff").active~=nil'), 'Git click opens diff')
        active = editor.lua('local d=require("config.diff").active;return {left=d.left,right=d.right,buf=d.buf}')
        assert editor.lua('return vim.api.nvim_buf_get_lines(vim.api.nvim_win_get_buf(...),0,-1,false)', active['left']) == ['']
        def bar(side):
            return editor.lua('local w=...;local b=require("config.hscroll").bars[w];'
                              'if not b or not vim.api.nvim_win_is_valid(b.win) then return end;'
                              'local p=vim.api.nvim_win_get_position(b.win);return {row=p[1],col=p[2],width=vim.api.nvim_win_get_width(b.win)}', active[side])
        editor.wait(lambda: bar('left') and bar('right'), 'Both columns have horizontal bars for actual overflow')
        def leftcol(side):
            return editor.lua('return vim.api.nvim_win_call(...,function() return vim.fn.winsaveview().leftcol end)', active[side])
        right = bar('right')
        editor.click(right['row'], right['col'] + right['width'] - 1)
        editor.wait(lambda: leftcol('right') > 0 and leftcol('right') == leftcol('left'), 'Bars scroll both columns against empty HEAD')
        editor.lua('require("config.hscroll").set(...,0)', active['right'])
        editor.wait(lambda: leftcol('right') == 0 and leftcol('left') == 0, 'Both columns return to start')
        editor.lua('require("config.ide").open_file(...)', str(baseline))
        editor.wait(lambda: not bar('left') and not bar('right'), 'Leaving diff removes its bars')
        print('PASS: new Markdown diff has working horizontal bars on both columns, synchronized scrolling against empty HEAD, and clean exit.')
    finally:
        editor.close()
