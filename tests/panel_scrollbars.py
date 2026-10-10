"""Panels get automatic full-block vertical bars; editors keep only minimaps."""
from pathlib import Path
import subprocess
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-panel-scrollbars-') as directory:
    root = Path(directory)
    for i in range(70):
        (root / f'file_{i:03}.txt').write_text('File\n')
    source = root / 'symbols.lua'
    source.write_text('\n'.join(f'local function symbol_{i:03}_' + 'long_name_' * 9 + f'() return {i} end' for i in range(80)) + '\n')
    subprocess.run(['git', 'init', '-b', 'main', str(root)], check=True, stdout=subprocess.DEVNULL)
    editor = Editor(root, root / 'state')
    try:
        def window(ft):
            return editor.lua('for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                              'if vim.bo[vim.api.nvim_win_get_buf(w)].filetype==... then return w end end', ft)

        def bar(win):
            return editor.lua('local s=require("config.vscroll").sources[...];return s and s.bar', win)

        def check(win, combined=False):
            editor.wait(lambda: bar(win), 'Automatic vertical bar')
            b = bar(win)
            config = editor.call('nvim_win_get_config', b['win'])
            height = editor.lua('return require("config.hscroll").content_height(...)', win)
            pinned = editor.lua('return require("config.git_header").height(...)', win)
            assert config['height'] == height - pinned
            assert config['row'] == pinned
            assert config['col'] == editor.call('nvim_win_get_width', win) - 1
            assert set(editor.call('nvim_buf_get_lines', b['buf'], 0, -1, False)) == {'█'}
            if combined:
                horizontal = editor.lua('return require("config.hscroll").bars[...]', win)
                editor.wait(lambda: editor.call('nvim_win_get_config', horizontal['win'])['width'] == editor.call('nvim_win_get_width', win), 'Horizontal width catches up after resize')
                hc = editor.call('nvim_win_get_config', horizontal['win'])
                assert hc['width'] == editor.call('nvim_win_get_width', win), 'Horizontal bar spans full width'
                assert set(editor.call('nvim_buf_get_lines', horizontal['buf'], 0, -1, False)[0]) == {'▄'}
                assert config['row'] + config['height'] == hc['row'], 'Vertical ends above horizontal'
                assert config['zindex'] > hc['zindex']
                assert config['height'] + pinned + 1 == editor.call('nvim_win_get_height', win)
            return b

        editor.lua('require("config.ide").open_file(...);require("config.ide").explorer()', str(source))
        tree = window('neo-tree')
        check(tree)
        symbols = window('aerial')
        editor.wait(lambda: editor.lua('return table.concat(vim.api.nvim_buf_get_lines(vim.api.nvim_win_get_buf(...),0,-1,false),"\\n"):find("symbol_079",1,true)~=nil', symbols), 'Symbols backend rendered all entries')
        editor.wait(lambda: editor.lua('return not require("config.layout").scaling and not require("config.sidebar").changing'), 'Sidebar layout settled')
        editor.wait(lambda: editor.lua('return require("config.hscroll").bars[...]~=nil', symbols), 'Symbols has both scrollbars')
        b = check(symbols, True)
        main = editor.lua('return require("config.ide").editor_window()')
        assert not bar(main), 'Editor uses minimap'

        # Both axes scroll, and vertical dragging does not enter the editor or open a file.
        focus = editor.lua('return vim.api.nvim_get_current_win()')
        position = editor.call('nvim_win_get_position', b['win'])
        editor.call('nvim_input_mouse', 'left', 'press', '', 0, position[0]+b['start'], position[1])
        editor.wait(lambda: editor.lua('return require("config.mouse_capture").active()'), 'Scrollbar press captured before dragging')
        editor.call('nvim_input_mouse', 'left', 'drag', '', 0, position[0]+b['span']+4, position[1])
        editor.call('nvim_input_mouse', 'left', 'release', '', 0, position[0]+b['span']+4, position[1])
        editor.wait(lambda: bar(symbols)['start'] == bar(symbols)['span'], 'Drag stops at bottom')
        assert editor.lua('return vim.api.nvim_get_current_win()') == focus
        assert not editor.lua('return require("config.mouse_capture").active()')

        # Resize retains the shared lower edge and reserved right margin.
        for width, height in ((128, 36), (180, 60), (160, 48)):
            editor.call('nvim_ui_try_resize', width, height)
            editor.wait(lambda: bar(symbols) and editor.call('nvim_win_get_config', bar(symbols)['win'])['height'] == editor.lua('return require("config.hscroll").content_height(...)', symbols), 'Vertical bar resized')
            check(symbols, True)

        editor.lua('require("config.ide").git_explorer()')
        editor.wait(lambda: window('neo-tree') and editor.lua('return require("config.sidebar").state().name') == 'git_status', 'Git panel')
        check(window('neo-tree'))
        editor.wait(lambda: not bar(symbols), 'Switching panels removes obsolete bar')
        editor.lua('require("config.diff").open(...)', str(source))
        assert not editor.lua('local d=require("config.diff").active;return require("config.vscroll").sources[d.left]~=nil or require("config.vscroll").sources[d.right]~=nil'), 'Diff uses minimaps'

        # Problems is a real diagnostics panel, with automatically discovered overflow.
        editor.lua('local b=vim.fn.bufnr(...);local items={};for i=0,79 do items[#items+1]={lnum=i,col=0,message="Diagnostic "..i,severity=vim.diagnostic.severity.ERROR} end;'
                   'vim.diagnostic.set(vim.api.nvim_create_namespace("ScrollbarTest"),b,items);require("config.problems").open()', str(source))
        editor.wait(lambda: window('trouble'), 'Problems opens')
        check(window('trouble'))
        editor.lua('require("config.problems").hide()')

        # Picker list buffers are virtualized: the scrollbar follows all items.
        editor.lua('local items={};for i=1,120 do items[i]={text="Item "..i} end;Snacks.picker({items=items,format="text",preview=false})')
        editor.wait(lambda: editor.lua('local p=Snacks.picker.get()[1];return p and p.shown and p.list:count()==120'), 'Picker items')
        listwin = editor.lua('return Snacks.picker.get()[1].list.win.win')
        editor.wait(lambda: bar(listwin), 'Virtual picker list has a scrollbar')
        b = bar(listwin)
        assert b['maximum'] > 50, 'Uses all items, not visible rows'
        position = editor.call('nvim_win_get_position', b['win'])
        editor.click(position[0]+editor.call('nvim_win_get_height', b['win'])-1, position[1])
        editor.wait(lambda: editor.lua('return Snacks.picker.get()[1].list.top>1'), 'Scrollbar scrolls item model')
        assert editor.lua('local p=Snacks.picker.get()[1];return vim.api.nvim_get_current_win()==p.input.win.win'), 'Picker focus retained'
        editor.lua('Snacks.picker.get()[1]:close()')
        editor.wait(lambda: not bar(listwin), 'Picker bars cleaned up')

        # Terminal scrollback is also a panel; producing output adds its bar.
        editor.lua('require("config.diff").leave();local t=require("config.terminals");t.show(t.active);'
                   'vim.api.nvim_chan_send(vim.b[t.active].terminal_job_id,"for i in {1..100}; do echo Line-$i; done"..string.char(10))')
        terminal = editor.lua('return require("config.terminals").win')
        editor.wait(lambda: editor.lua('return table.concat(vim.api.nvim_buf_get_lines(vim.api.nvim_win_get_buf(...),0,-1,false),"\\n"):find("Line%-100")~=nil', terminal), 'Terminal output completed')
        check(terminal)
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Terminal keeps input')
        # Each reserved axis must disappear when content fits without either
        # reservation; bars must not keep each other alive after shrinking.
        fitwin = editor.lua('vim.cmd("stopinsert");local b=vim.api.nvim_create_buf(false,true);'
                            'vim.bo[b].filetype="ide_git_history";local w=vim.api.nvim_open_win(b,false,{split="above",win=require("config.ide").editor_window(),height=6});'
                            'vim.wo[w].wrap=false;vim.wo[w].winbar="";local lines={};for i=1,100 do lines[i]=string.rep("x",300) end;'
                            'vim.api.nvim_buf_set_lines(b,0,-1,false,lines);return w')
        editor.wait(lambda: bar(fitwin) and editor.lua('return require("config.hscroll").bars[...]~=nil', fitwin), 'Scratch panel has both axes')
        editor.lua('local w=...;local h=vim.api.nvim_win_get_height(w);local width=vim.api.nvim_win_get_width(w)-vim.fn.getwininfo(w)[1].textoff;'
                   'local lines={};for i=1,h do lines[i]=string.rep("x",width) end;vim.api.nvim_buf_set_lines(vim.api.nvim_win_get_buf(w),0,-1,false,lines)', fitwin)
        try:
            editor.wait(lambda: not bar(fitwin) and editor.lua('return require("config.hscroll").bars[...] == nil', fitwin), 'Both bars disappear at exact full-window fit')
        except AssertionError:
            print(editor.lua('local w=...;return {bounds={require("config.hscroll").bounds(w)},lines=vim.api.nvim_win_text_height(w,{}).all,height=vim.api.nvim_win_get_height(w),width=vim.api.nvim_win_get_width(w),textoff=vim.fn.getwininfo(w)[1].textoff,v=require("config.vscroll").sources[w],h=require("config.hscroll").bars[w]}', fitwin))
            raise
        editor.call('nvim_win_close', fitwin, True)
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'Vertical scrollbar:' not in messages and 'Invalid window id' not in messages, messages
        print('PASS: automatic full-block bars in Files/Symbols/Git/Problems/picker/terminal; combined-axis layout and resize; drag/virtual list scrolling retain focus; no editor/diff bars; cleanup works.')
    finally:
        editor.close()
