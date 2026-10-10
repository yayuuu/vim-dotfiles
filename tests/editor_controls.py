"""Actual document-strip, toolbar, minimap and horizontal-scrollbar gestures."""
from pathlib import Path
import subprocess
import tempfile
import time
from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-editor-controls-') as directory:
    root = Path(directory); repo = root/'repo'; repo.mkdir()
    def git(*args):
        return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.STDOUT).decode()
    git('init','-b','main'); git('config','user.name','UI Test'); git('config','user.email','ui@example.invalid')
    file = repo/'long.txt'
    lines = [f'line {i:03} '+ 'word '*55 for i in range(1,121)]
    file.write_text('\n'.join(lines)+'\n'); git('add','.'); git('commit','-m','Baseline')
    lines[9]='changed '+ 'new '*85; lines.insert(35,'Added green line'); del lines[80]
    file.write_text('\n'.join(lines)+'\n')
    editor=Editor(repo,root/'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert");vim.wo.wrap=false',str(file))
        def bar_info(side=None):
            return editor.lua('local h=require("config.hscroll");local d=require("config.diff").active;'
                              'local w=(... and d) and d[...] or require("config.ide").editor_window();local b=h.bars[w];'
                              'if not b or not vim.api.nvim_win_is_valid(b.win) then return end; '
                              'local p=vim.api.nvim_win_get_position(b.win);return {source=w,row=p[1],col=p[2],width=vim.api.nvim_win_get_width(b.win),start=b.start,thumb=b.thumb}',side)
        editor.wait(lambda: bar_info(), 'Normal overflow scrollbar')
        bar=bar_info()
        def horizontal(win):
            return editor.lua('return vim.api.nvim_win_call(...,function() return vim.fn.winsaveview().leftcol end)',win)
        editor.click(bar['row'],bar['col']+bar['width']*3//4)
        editor.wait(lambda: horizontal(bar['source'])>25, 'Normal bar scrolls code')
        # Grab the actual thumb, drag it to the start, with no selection.
        bar=bar_info(); x=bar['col']+bar['start']
        editor.call('nvim_input_mouse','left','press','',0,bar['row'],x)
        editor.call('nvim_input_mouse','left','drag','',0,bar['row'],bar['col']+2)
        editor.call('nvim_input_mouse','left','release','',0,bar['row'],bar['col']+2)
        editor.wait(lambda: horizontal(bar['source'])<10, 'Thumb drag returns to start')
        editor.lua('require("config.diff").open(...)',str(file))
        editor.wait(lambda: bar_info('left') and bar_info('right') and editor.lua(
            'local d=require("config.diff").active;local h=require("config.hscroll");'
            'if require("config.layout").scaling then return false end;'
            'for _,w in ipairs({d.left,d.right}) do local b=h.bars[w];local p=vim.api.nvim_win_get_position(w);'
            'local bp=vim.api.nvim_win_get_position(b.win);if bp[2]~=p[2] '
            'or vim.api.nvim_win_get_width(b.win)~=vim.api.nvim_win_get_width(w) then return false end end;return true'),
            'Each comparison scrollbar settles after layout resizing')
        right=bar_info('right');left=bar_info('left')
        editor.click(right['row'],right['col']+right['width']*3//4)
        editor.wait(lambda: horizontal(right['source'])>25 and horizontal(right['source'])==horizontal(left['source']), 'Diff bars synchronize')
        editor.lua('local d=require("config.diff").active;vim.api.nvim_set_current_win(d.right);vim.cmd("stopinsert");vim.cmd("normal! 0");vim.cmd("normal! 30zl")')
        editor.wait(lambda: horizontal(right['source'])==horizontal(left['source']), 'Native horizontal scrolling synchronizes')
        def map_win():
            return editor.lua('local d=require("config.diff").active;return require("neominimap.window.float.window_map").get_minimap_winid(d.right)')
        editor.wait(map_win,'Editable diff has a minimap')
        assert not editor.lua('local d=require("config.diff").active;return require("neominimap.window.float.window_map").get_minimap_winid(d.left)'), 'No old-side minimap'
        def map_colors():
            return editor.lua('local d=require("config.diff").active;local w=require("neominimap.window.float.window_map").get_minimap_winid(d.right);'
                              'local b=vim.api.nvim_win_get_buf(w);local found={};for _,ns in pairs(vim.api.nvim_get_namespaces()) do '
                              'for _,mark in ipairs(vim.api.nvim_buf_get_extmarks(b,ns,0,-1,{details=true})) do '
                              'local h=mark[4].hl_group;if h then found[h]=true end end end;return found')
        editor.wait(lambda: all(h in map_colors() for h in ['DesktopMapAdd','DesktopMapDelete','DesktopMapChange']), 'Colored added/deleted/modified minimap')
        # Toolbar clicks move the editable cursor to the next/previous hunk.
        editor.lua('local d=require("config.diff").active;vim.api.nvim_win_set_cursor(d.right,{1,0})')
        def toolbar(button):
            return editor.lua('local d=require("config.diff").active;local t=require("config.editor_tabs");local p=vim.api.nvim_win_get_position(d.header);'
                              'return {p[1]+1,p[2]+t[...]+2}',button)
        editor.click(*toolbar('next'))
        editor.wait(lambda: editor.lua('local d=require("config.diff").active;return vim.api.nvim_win_get_cursor(d.right)[1]')==10,'Next hunk toolbar')
        editor.click(*toolbar('next'))
        editor.wait(lambda: editor.lua('local d=require("config.diff").active;return vim.api.nvim_win_get_cursor(d.right)[1]')==36,'Second hunk toolbar')
        editor.click(*toolbar('previous'))
        editor.wait(lambda: editor.lua('local d=require("config.diff").active;return vim.api.nvim_win_get_cursor(d.right)[1]')==10,'Previous hunk toolbar')
        # Selecting/reopening either type of card promotes it to the first slot.
        proxy=editor.lua('return require("config.diff").active.buf')
        ordinary=repo/'second.txt';ordinary.write_text('short\n')
        editor.lua('require("config.ide").open_file(...)',str(ordinary))
        second=editor.lua('return vim.api.nvim_get_current_buf()')
        def first_id():
            return editor.lua('local t=require("config.editor_tabs");return t.hits and t.hits[1] and t.hits[1].id')
        editor.wait(lambda:first_id()==second,'Ordinary MRU first')
        def card_position(buf):
            return editor.lua('local t=require("config.editor_tabs");local p=vim.api.nvim_win_get_position(t.win);'
                              'for _,h in ipairs(t.hits) do if h.id==... and not h.close then return {p[1],p[2]+h.first} end end',buf)
        editor.click(*card_position(proxy))
        editor.wait(lambda:first_id()==proxy,'Clicking diff card promotes it')
        editor.lua('require("config.ide").open_file(...)',str(ordinary))
        editor.wait(lambda:first_id()==second,'Reopening existing file promotes it')
        # Lots of cards: wheel shows hidden cards without changing the selected file.
        for i in range(14):
            path=repo/f'document-{i:02}-long-name.txt';path.write_text('short\n')
            editor.lua('require("config.ide").open_file(...)',str(path))
        current=editor.lua('return vim.api.nvim_get_current_buf()')
        editor.wait(lambda:first_id()==current,'Latest document first')
        p=editor.lua('return vim.api.nvim_win_get_position(require("config.editor_tabs").win)')
        for _ in range(8):editor.call('nvim_input_mouse','wheel','down','',0,p[0],p[1]+5)
        editor.wait(lambda:editor.lua('return require("config.editor_tabs").first')>1,'Wheel over cards scrolls horizontally')
        assert editor.lua('return vim.api.nvim_get_current_buf()')==current
        assert first_id()!=current
        for _ in range(8):editor.call('nvim_input_mouse','wheel','up','',0,p[0],p[1]+5)
        editor.wait(lambda:first_id()==current,'Wheel back to beginning')
        editor.call('nvim_input_mouse','middle','press','',0,p[0],p[1]+5)
        editor.wait(lambda:not editor.lua('return vim.api.nvim_buf_is_valid(...) and vim.bo[...].buflisted',current),'Middle press closes ordinary tab without requiring release')
        editor.call('nvim_input_mouse','middle','release','',0,p[0],p[1]+5)
        # Short lines remove the overflow bar rather than leaving an orphan split.
        editor.wait(lambda:editor.lua('return vim.tbl_count(require("config.hscroll").bars)')==0,'Short document hides all horizontal bars')
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
    finally:editor.close()
    print('PASS: real horizontal scroll/drag, synchronized diff bars/native scroll, colored current minimap, toolbar next/previous, MRU ordinary/diff clicks and reopen, horizontal wheel browsing and middle press close')
