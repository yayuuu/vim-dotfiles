"""Informational Neo-tree rows never become document buffers."""
from pathlib import Path
import tempfile

from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-tree-messages-') as directory:
    root = Path(directory)
    file = root / 'example.txt'
    file.write_text('Visible document\n')
    (root / '.neoconf.json').write_text('{}\n')
    (root / '.hidden').write_text('Hidden content\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...)', str(file))
        mainbuf = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.lua('local s=require("neo-tree.sources.manager").get_state("filesystem");'
                   's.filtered_items.visible=false;s.commands.refresh(s)')
        def message():
            return editor.lua('local s=require("neo-tree.sources.manager").get_state("filesystem");'
                              'if not s.tree or not s.winid or not vim.api.nvim_win_is_valid(s.winid) then return end;'
                              'for line=1,vim.api.nvim_buf_line_count(s.bufnr) do local n=s.tree:get_node(line);'
                              'if n and n.type=="message" and n.name:find("hidden",1,true) then '
                              'local p=vim.api.nvim_win_get_position(s.winid);return {row=p[1]+line,col=p[2]+6,line=line,win=s.winid,id=n:get_id()} end end')
        editor.wait(message, 'Hidden items message rendered')
        info = message()
        before = editor.files()
        editor.click(info['row'], info['col'])
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Message click leaves tree in Normal mode')
        assert editor.lua('return vim.api.nvim_win_get_buf(require("config.ide").editor_window())') == mainbuf, 'Message must not replace document'
        assert editor.files() == before, 'Message click must not create a document'
        editor.lua('local win,line=...;vim.api.nvim_set_current_win(win);vim.api.nvim_win_set_cursor(win,{line,0})', info['win'], info['line'])
        editor.call('nvim_input', '<CR>')
        editor.lua('vim.cmd("redraw!")')
        assert editor.files() == before, 'Enter on message must not create a document'
        editor.call('nvim_input_mouse', 'right', 'press', '', 0, info['row'], info['col'])
        editor.call('nvim_input_mouse', 'right', 'release', '', 0, info['row'], info['col'])
        editor.lua('vim.cmd("redraw!")')
        assert editor.lua('return vim.bo.filetype') != 'NvMenu', 'Message must not expose file actions'
        assert editor.files() == before
        # The real file still opens through the same command mapping.
        position = editor.lua('local s=require("neo-tree.sources.manager").get_state("filesystem");local _,line=s.tree:get_node(...);'
                              'local p=vim.api.nvim_win_get_position(s.winid);return {p[1]+line,p[2]+6}', str(file))
        editor.click(*position)
        editor.wait(lambda: editor.lua('return vim.api.nvim_win_get_buf(require("config.ide").editor_window())') == mainbuf, 'Real file still opens')
        assert editor.lua('return vim.bo.filetype') == 'neo-tree', 'Files retains keyboard focus'
        print('PASS: hidden-items message clicks, Enter and right-click never create synthetic documents; normal file opening works.')
    finally:
        editor.close()
