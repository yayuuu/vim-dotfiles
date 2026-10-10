"""Panel bars respect dialog layers and the pinned Git header."""
from pathlib import Path
import subprocess
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-scrollbar-layering-') as directory:
    root = Path(directory)
    subprocess.run(['git', 'init', '-b', 'main', directory], check=True, stdout=subprocess.DEVNULL)
    for i in range(80):
        (root / (f'file_{i:03}_' + 'long_name_' * 8 + '.txt')).write_text('Text\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").git_explorer()')
        def bars():
            return editor.lua('local s=require("config.sidebar").state();'
                              'if not s or s.name~="git_status" then return end;'
                              'local v=require("config.vscroll").sources[s.winid];'
                              'local h=require("config.hscroll").bars[s.winid];'
                              'if v and v.bar and h then return {source=s.winid,v=v.bar.win,h=h.win,buf=s.bufnr} end')
        editor.wait(bars, 'Git Status has both scrollbars')
        b = bars()
        def header_fits():
            return editor.lua('local b=...;local text=vim.api.nvim_buf_get_lines(b.buf,0,1,false)[1];'
                              'return text:find("[⟳]",1,true)~=nil and '
                              'vim.fn.strdisplaywidth(text)<=vim.api.nvim_win_get_width(b.source)', b)
        editor.wait(header_fits, 'Header refresh button fits full panel width')
        header = editor.lua('return require("config.git_header").windows[...].win', b['source'])
        vp = editor.call('nvim_win_get_position', b['v'])
        hpinned = editor.call('nvim_win_get_position', header)
        assert vp[0] == hpinned[0] + editor.call('nvim_win_get_height', header), 'Vertical scrollbar starts after pinned header'
        staged = editor.lua('local s=require("config.sidebar").state();local _,line=s.tree:get_node(s.path.."::staged");return line')
        assert staged == 5, 'Staged Changes starts immediately after the four header rows'
        field = editor.lua('local s=require("config.sidebar").state();return require("config.git").inputs[s.path]')
        input_before = editor.call('nvim_win_get_config', field['win'])
        editor.wait(lambda: editor.lua('return not require("config.popup_ui").pending and not require("config.popup_ui").scanning'), 'Popup scan settled')
        assert not editor.lua('return require("config.popup_ui").buttons[...]~=nil', field['win']), 'Commit message has no close cross'
        editor.lua('require("config.popup_ui").close(...)', field['win'])
        assert editor.call('nvim_win_is_valid', field['win']), 'Commit input cannot be dismissed as a dialog'
        ip = editor.call('nvim_win_get_position', field['win'])
        editor.click(ip[0], ip[1]+3)
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Empty commit input click starts typing')
        editor.lua('vim.cmd("stopinsert")')
        editor.call('nvim_buf_set_lines', field['buf'], 0, -1, False, ['Draft message'])
        original_title = editor.call('nvim_buf_get_lines', editor.call('nvim_win_get_buf', header), 0, 1, False)
        editor.lua('require("config.vscroll").set(...,99999)', b['source'])
        editor.wait(lambda: editor.lua('local s=require("config.vscroll").sources[...];return s.bar.start==s.bar.span', b['source']), 'Git body reaches bottom')
        assert editor.lua('return vim.api.nvim_win_call(...,vim.fn.winsaveview).topline', b['source']) > 1
        assert editor.call('nvim_win_get_position', header) == hpinned, 'Header stays fixed while body scrolls'
        assert editor.call('nvim_buf_get_lines', editor.call('nvim_win_get_buf', header), 0, 1, False) == original_title
        assert editor.call('nvim_win_get_config', field['win'])['width'] == input_before['width'], 'Commit message width is preserved'
        assert editor.call('nvim_buf_get_lines', field['buf'], 0, -1, False) == ['Draft message']
        editor.lua('vim.cmd("redraw!")')
        assert 'GIT STATUS' in ''.join(editor.grid[hpinned[0]])
        assert any('file_079_' in ''.join(row) for row in editor.grid[vp[0]:vp[0]+editor.call('nvim_win_get_height', b['v'])]), 'Final file remains visible below pinned header'
        # Opening several diffs must not move the commit field or reset its border.
        geometry = (editor.call('nvim_win_get_position', field['win']), input_before['width'], input_before['border'])
        for i in (79, 78, 77):
            path = str(root / (f'file_{i:03}_' + 'long_name_' * 8 + '.txt'))
            pointer = editor.lua('local s=require("config.sidebar").state();local _,line=s.tree:get_node(...);return vim.fn.screenpos(s.winid,line,5)', path)
            editor.click(pointer['row']-1, pointer['col']-1)
            editor.wait(lambda: editor.lua('local d=require("config.diff").active;return d and require("config.diff").entries[d.buf].path==...', path), 'Git row opens its diff')
            editor.wait(lambda: editor.lua('return not require("config.layout").scaling'), 'Diff layout settled')
            current = editor.call('nvim_win_get_config', field['win'])
            assert (editor.call('nvim_win_get_position', field['win']), current['width'], current['border']) == geometry, 'Commit field geometry stays fixed while opening diffs'
            assert editor.call('nvim_buf_get_lines', field['buf'], 0, -1, False) == ['Draft message']
        for axis in ('v', 'h'):
            assert editor.call('nvim_win_get_config', b[axis])['zindex'] < 50

        # A generic default-layer dialog covers native bars on both axes.
        popup = editor.lua('local b=vim.api.nvim_create_buf(false,true);vim.bo[b].buftype="nofile";'
                           'vim.api.nvim_buf_set_lines(b,0,-1,false,{string.rep("X",120)});'
                           'local w=vim.api.nvim_open_win(b,false,{relative="editor",row=3,col=5,width=120,height=40,style="minimal"});'
                           'vim.wo[w].winbar="";return w')
        editor.lua('vim.cmd("redraw!")')
        vp = editor.call('nvim_win_get_position', b['v'])
        hp = editor.call('nvim_win_get_position', b['h'])
        assert editor.grid[vp[0]+5][vp[1]] == ' ', 'Native vertical bar must not show through a dialog'
        assert editor.grid[hp[0]][hp[1]+10] == ' ', 'Native horizontal bar must not show through a dialog'
        editor.call('nvim_win_close', popup, True)

        # Reproduce the actual Plugins dialog, whose default layer is 50.
        editor.lua('vim.cmd("stopinsert");vim.cmd("Lazy")')
        lazy = editor.lua('return require("lazy.view").view.win')
        editor.wait(lambda: editor.lua('return require("config.popup_ui").buttons[...]~=nil', lazy), 'Plugins dialog ready')
        lc = editor.call('nvim_win_get_config', lazy)
        assert editor.call('nvim_win_get_config', b['v'])['zindex'] < lc['zindex']
        lp = editor.call('nvim_win_get_position', lazy)
        row = max(lp[0]+2, vp[0]+2)
        editor.lua('vim.cmd("redraw!")')
        assert editor.grid[row][vp[1]] != '█', 'Git scrollbar must not show through Plugins'
        editor.call('nvim_win_close', lazy, True)
        editor.wait(lambda: bars() and header_fits(), 'Underlying bars and header survive closing dialog')
        editor.lua('require("config.ide").explorer()')
        editor.wait(lambda: not editor.lua('return next(require("config.git_header").windows)~=nil'), 'Switching panels removes pinned Git header')
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'Vertical scrollbar:' not in messages and 'Error executing' not in messages, messages
        print('PASS: native bars stay below Plugins and generic dialogs on both axes; Git header stays above the vertical bar; closing dialogs preserves bars.')
    finally:
        editor.close()
