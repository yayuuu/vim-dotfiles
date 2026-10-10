"""Scrollbar geometry preserves content space, EOF caret, and terminal resizing."""
from pathlib import Path
import tempfile
from ui import Editor
with tempfile.TemporaryDirectory(prefix='nvim-scrollbar-layout-') as directory:
    root=Path(directory);short=root/'short.lua';long=root/'long.lua'
    short.write_text('return 1\n');long.write_text(('local value = "'+'x'*280+'"\n')*100)
    e=Editor(root,root/'state')
    try:
        e.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")',str(short))
        source=e.lua('return require("config.ide").editor_window()');height=e.call('nvim_win_get_height',source)
        layout=e.lua('return vim.fn.winlayout()')
        e.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")',str(long))
        def bar():return e.lua('local b=require("config.hscroll").bars[...];return b and b.win',source)
        e.wait(bar,'Overflow bar')
        assert e.call('nvim_win_get_height',source)==height,'Scrollbar must not create another split or steal an extra separator row'
        assert e.lua('return vim.fn.winlayout()')==layout,'Scrollbar must not change native layout'
        def geometry():
            p=e.call('nvim_win_get_position',source);b=e.call('nvim_win_get_position',bar())
            return b==[p[0]+e.call('nvim_win_get_height',source)-1,p[1]]
        e.wait(geometry,"Scrollbar occupies the panel last row")
        e.lua('vim.api.nvim_win_set_cursor(...,{100,0});vim.cmd("redraw!");require("config.hscroll").refresh()',source)
        def cursor_visible():
            return e.lua('local w=...;local b=require("config.hscroll").bars[w];local c=vim.api.nvim_win_get_cursor(w);local p=vim.fn.screenpos(w,c[1],c[2]+1);return p.row>0 and p.row<=vim.api.nvim_win_get_position(b.win)[1]',source)
        e.wait(cursor_visible,'EOF cursor remains above scrollbar')
        assert e.call('nvim_win_get_cursor',source)[0]==100,'Viewport adjustment preserves cursor line'
        terminal=e.lua('return require("config.terminals").win');before=e.call('nvim_win_get_height',terminal)
        pos=e.call('nvim_win_get_position',terminal);row=pos[0]-1;col=pos[1]+25
        offset=e.lua('return vim.api.nvim_win_call(...,vim.fn.winsaveview).leftcol',source)
        e.call('nvim_input_mouse','left','press','',0,row,col)
        e.lua('vim.cmd("redraw!")')
        e.call('nvim_input_mouse','left','drag','',0,row+3,col)
        e.lua('vim.cmd("redraw!")')
        e.call('nvim_input_mouse','left','release','',0,row+3,col)
        e.wait(lambda:e.call('nvim_win_get_height',terminal)!=before,'Dragging native boundary resizes terminal with scrollbar visible')
        assert e.lua('return vim.api.nvim_win_call(...,vim.fn.winsaveview).leftcol',source)==offset,'Boundary drag must not scroll horizontally'
        e.lua('vim.cmd("redraw!")');e.wait(geometry,'Scrollbar follows resized panel')
        print('PASS: scrollbar takes no extra split/separator row; EOF cursor stays visible; native terminal resize works without horizontal scrolling.')
    finally:e.close()
