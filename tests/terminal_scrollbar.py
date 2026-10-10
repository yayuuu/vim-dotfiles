"""Terminal history dragging exits live input safely, then typing resumes on click."""
from pathlib import Path
import tempfile

from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-terminal-scrollbar-') as directory:
    root = Path(directory)
    editor = Editor(root, root / 'state')
    try:
        editor.lua('local t=require("config.terminals");t.show(t.active);'
                   'vim.api.nvim_chan_send(vim.b[t.active].terminal_job_id,"for i in {1..100}; do echo Line-$i; done"..string.char(10))')
        terminal = editor.lua('return require("config.terminals").win')
        tp = editor.call('nvim_win_get_position', terminal)
        def bar():
            return editor.lua('local s=require("config.vscroll").sources[...];return s and s.bar', terminal)
        editor.wait(lambda: editor.lua('return table.concat(vim.api.nvim_buf_get_lines(vim.api.nvim_win_get_buf(...),0,-1,false),"\\n"):find("Line%-100")~=nil', terminal), 'Output completed')
        editor.wait(bar, 'Terminal has scrollbar')
        for _ in range(2):
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Terminal input')
            b = bar()
            p = editor.call('nvim_win_get_position', b['win'])
            editor.call('nvim_input_mouse', 'left', 'press', '', 0, p[0]+b['start'], p[1])
            editor.wait(lambda: editor.lua('return require("config.mouse_capture").active()'), 'Press captured')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Terminal exits live input for scrollback')
            editor.call('nvim_input_mouse', 'left', 'drag', '', 0, p[0], p[1])
            editor.call('nvim_input_mouse', 'left', 'release', '', 0, p[0], p[1])
            editor.wait(lambda: bar()['start'] == 0, 'Drag reaches first history line')
            assert editor.lua('return vim.fn.mode()') == 'n'
            assert editor.lua('return vim.api.nvim_get_current_win()') == terminal
            assert not editor.lua('return require("config.mouse_capture").active()')
            editor.click(p[0]+editor.call('nvim_win_get_height', b['win'])-1, p[1])
            try:
                editor.wait(lambda: bar()['start'] == bar()['span'], 'Track click reaches bottom')
            except AssertionError:
                print(b, p, editor.lua('local w=...;return {bar=require("config.vscroll").sources[w],view=vim.api.nvim_win_call(w,vim.fn.winsaveview),mouse=vim.fn.getmousepos(),mode=vim.fn.mode(),scrolloff=vim.wo[w].scrolloff,messages=vim.fn.execute("messages")}', terminal))
                raise
            for _ in range(8):
                editor.call('nvim_input_mouse', 'wheel', 'down', '', 0, tp[0]+2, tp[1]+3)
                assert editor.lua('local w=...;local v=vim.api.nvim_win_call(w,vim.fn.winsaveview);return v.topline-1<=math.max(0,vim.api.nvim_win_text_height(w,{}).all-require("config.hscroll").content_height(w))', terminal), 'Terminal body wheel never overshoots'
            editor.call('nvim_input_mouse', 'wheel', 'up', '', 0, p[0]+2, p[1])
            editor.wait(lambda: bar()['start'] < bar()['span'], 'Wheel scrolls history')
            editor.click(tp[0]+2, tp[1]+3)
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Body click resumes shell input')
        editor.call('nvim_input', 'printf input-ok > scrollbar-input.txt<CR>')
        editor.wait(lambda: (root / 'scrollbar-input.txt').exists(), 'Typing still executes in shell')
        assert (root / 'scrollbar-input.txt').read_text() == 'input-ok'
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'schedule callback:' not in messages and 'vim.on_key() callbacks:' not in messages, messages
        assert 'Vertical scrollbar:' not in messages, messages
        print('PASS: terminal scrollbar drag, release, endpoints and wheel work from input mode; focus retained; body click resumes typing; no callback errors.')
    finally:
        editor.close()
