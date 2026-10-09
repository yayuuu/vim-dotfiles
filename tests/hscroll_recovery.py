"""Transient scrollbar failures release guards and allow subsequent rendering."""
from pathlib import Path
import tempfile
from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-scroll-recovery-') as directory:
    root=Path(directory)
    file=root/'long.txt';file.write_text('long '*70+'\n')
    editor=Editor(root,root/'state')
    try:
        editor.lua('require("config.ide").open_file(...)',str(file))
        editor.wait(lambda:editor.lua('local h=require("config.hscroll");local w=require("config.ide").editor_window();return h.bars[w]~=nil and not h.pending and not h.running'),'Initial scrollbar')
        # Simulate a failed native split while a redraw is in progress.
        editor.lua('local h=require("config.hscroll");_G.scroll_original_draw=h.draw;'
                   'h.draw=function() h.draw=_G.scroll_original_draw;error("Test: transient window resize failure") end;h.refresh()')
        editor.wait(lambda:editor.lua('return not require("config.hscroll").pending'),'Refresh attempted')
        assert not editor.lua('return require("config.hscroll").running'), 'A failed redraw must not permanently disable scrollbars'
        editor.lua('local h=require("config.hscroll");h.close(require("config.ide").editor_window());h.refresh()')
        editor.wait(lambda:editor.lua('local h=require("config.hscroll");return h.bars[require("config.ide").editor_window()]~=nil and not h.running'),'Scrollbar recovers after error')
        # A split failure must also release the shared diff guard and remove its scratch buffer.
        scratch_before=editor.lua('local count=0;for _,b in ipairs(vim.api.nvim_list_bufs()) do if vim.bo[b].filetype=="ide_hscroll" then count=count+1 end end;return count')
        editor.lua('local h=require("config.hscroll");h.close(require("config.ide").editor_window());'
                   '_G.scroll_original_open=vim.api.nvim_open_win;vim.api.nvim_open_win=function(buf,enter,config) '
                   'if vim.b[buf].ide_hscroll then vim.api.nvim_open_win=_G.scroll_original_open;error("Test: cannot split during resize") end;'
                   'return _G.scroll_original_open(buf,enter,config) end;h.refresh()')
        editor.wait(lambda:editor.lua('return not require("config.hscroll").pending'),'Split failure handled')
        assert not editor.lua('return require("config.hscroll").running'), 'Failed split releases renderer'
        assert not editor.lua('return require("config.diff").busy'), 'Failed split releases diff guard'
        scratch_after=editor.lua('local count=0;for _,b in ipairs(vim.api.nvim_list_bufs()) do if vim.bo[b].filetype=="ide_hscroll" then count=count+1 end end;return count')
        assert scratch_after <= scratch_before, 'Failed split must not leak scratch buffers'
        editor.lua('require("config.hscroll").refresh()')
        editor.wait(lambda:editor.lua('local h=require("config.hscroll");return h.bars[require("config.ide").editor_window()]~=nil and not h.running'),'Scrollbar recovers after failed split')
        print('PASS: redraw and split failures release rendering/diff guards, clean scratch buffers, and allow later scrollbars.')
    finally:
        editor.close()
