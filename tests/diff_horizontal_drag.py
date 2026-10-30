"""Grabbing a diff scrollbar preserves its exact offset between pointer moves."""
from pathlib import Path
import subprocess
import tempfile
import time

from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-diff-horizontal-drag-') as directory:
    root = Path(directory)
    file = root / 'long.txt'
    file.write_text(('short\n' + 'long text ' * 100 + '\n') * 40)
    subprocess.run(['git', 'init', '-b', 'main', str(root)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=UI Test', '-c', 'user.email=ui@example.invalid',
                    'commit', '-m', 'Baseline'], check=True, stdout=subprocess.DEVNULL)
    file.write_text(file.read_text().replace('long text', 'changed text'))
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.diff").open(...)', str(file))
        editor.wait(lambda: editor.lua('local d=require("config.diff").active;local h=require("config.hscroll");'
                                      'return d and h.bars[d.left] and h.bars[d.right] and not require("config.layout").scaling'), 'Diff and bars settle')

        def views():
            return editor.lua('local d=require("config.diff").active;local r={};for _,w in ipairs({d.left,d.right}) do '
                              'local v=vim.api.nvim_win_call(w,vim.fn.winsaveview);r[#r+1]={leftcol=v.leftcol,topline=v.topline,topfill=v.topfill} end;return r')

        def settle():
            time.sleep(.08)
            editor.lua('vim.cmd("redraw!")')

        for mode in ('normal', 'insert'):
            for side in ('left', 'right'):
                editor.lua('require("config.selection_scroll").restore();vim.cmd("stopinsert");local d=require("config.diff").active;vim.api.nvim_set_current_win(d.right);'
                           'vim.api.nvim_win_set_cursor(d.right,{21,0})')
                if mode == 'insert':
                    editor.lua('vim.cmd("startinsert")')
                    editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Insert mode')
                else:
                    settle()
                    editor.call('nvim_input', '<Esc>')
                editor.lua('require("config.hscroll").set(require("config.diff").active[...],37)', side)
                settle()
                before = views()
                assert all(v['leftcol'] == 37 for v in before), before
                assert editor.lua('local s=require("config.selection_scroll").state;'
                                  'return s and s.cursor[2]==21 and s.cursor[3]==1'), 'Horizontal scrolling parks the original editor column'
                bar = editor.lua('local b=require("config.hscroll").bars[require("config.diff").active[...]];'
                                 'local p=vim.api.nvim_win_get_position(b.win);return {row=p[1],col=p[2],'
                                 'start=b.start,thumb=b.thumb,span=b.span,maximum=b.maximum}', side)
                row, x = bar['row'], bar['col'] + bar['start'] - 1 + bar['thumb'] // 2
                editor.call('nvim_input_mouse', 'left', 'press', '', 0, row, x)
                settle()
                assert views() == before, ('Thumb press jumps', mode, side, before, views(), bar)
                for delta in (1, 2, 3, 4, 3, 2, 1, 0):
                    editor.call('nvim_input_mouse', 'left', 'drag', '', 0, row, x + delta)
                    settle()
                    actual = views()
                    expected = int(37 + delta * bar['maximum'] / max(1, bar['span']))
                    assert all(v['leftcol'] == expected for v in actual), ('Pointer offset drift', mode, side, expected, actual)
                    assert all((v['topline'], v['topfill']) == (old['topline'], old['topfill'])
                               for v, old in zip(actual, before)), ('Vertical jump during horizontal drag', before, actual)
                    settle()
                    assert views() == actual, ('Redraw changes drag position', actual, views())
                editor.call('nvim_input_mouse', 'left', 'release', '', 0, row, x)
                settle()
                assert views() == before, ('Release jumps', mode, side, before, views())
        print('PASS: both diff scrollbars preserve the initial offset on grab/release and track pointer movement without horizontal drift or vertical jumps in Normal/Insert.')
    finally:
        editor.close()
