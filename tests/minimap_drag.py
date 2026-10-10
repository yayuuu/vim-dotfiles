"""Minimap viewport follows every drag movement without waiting for debounce."""
from pathlib import Path
import tempfile
import time

from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-minimap-drag-') as directory:
    root = Path(directory)
    file = root / 'long.txt'
    original = [f'Line {i:04} ' + 'code structure ' * 5 for i in range(1, 1201)]
    file.write_text('\n'.join(original) + '\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...)', str(file))
        source = editor.lua('return require("config.ide").editor_window()')
        buf = editor.call('nvim_win_get_buf', source)
        def mapwin():
            return editor.lua('return require("neominimap.window.float.window_map").get_minimap_winid(...)', source)
        editor.wait(mapwin, 'Minimap opens')
        def snapshot():
            return editor.lua('local source=...;local w=require("neominimap.window.float.window_map").get_minimap_winid(source);'
                              'local b=vim.api.nvim_win_get_buf(w);local info=vim.fn.getwininfo(source)[1];'
                              'local c=require("neominimap.map.coord");local first=c.codepoint_to_mcodepoint(info.topline,1);'
                              'local last=c.codepoint_to_mcodepoint(info.botline,1);local rows={};'
                              'for _,m in ipairs(vim.api.nvim_buf_get_extmarks(b,vim.api.nvim_create_namespace("DesktopMinimapViewport"),0,-1,{details=true})) do '
                              'for row=m[2],(m[4].end_row or m[2]+1)-1 do rows[tostring(row)]=true end end;'
                              'local cursor=vim.api.nvim_win_get_cursor(w)[1];local expected_cursor=c.codepoint_to_mcodepoint(vim.api.nvim_win_get_cursor(source)[1],1);'
                              'return {top=info.topline,first=first-1,last=last-1,rows=rows,cursor=cursor,expected_cursor=expected_cursor}', source)
        def aligned(state):
            expected = {str(row) for row in range(state['first'], state['last'] + 1)}
            return set(state['rows']) == expected and state['cursor'] == state['expected_cursor']
        editor.wait(lambda: aligned(snapshot()), 'Initial viewport and cursor match source')
        assert editor.lua('return require("neominimap.config").delay') == 120, 'Text redraw debounce is retained'
        position = editor.call('nvim_win_get_position', mapwin())
        start = position[0] + 2
        column = position[1] + 5
        editor.call('nvim_input_mouse', 'left', 'press', '', 0, start, column)
        time.sleep(.02)
        editor.lua('vim.cmd("redraw!")')
        previous = snapshot()['top']
        for offset in (3, 5, 8, 11, 14):
            editor.call('nvim_input_mouse', 'left', 'drag', '', 0, start + offset, column)
            editor.wait(lambda: snapshot()['top'] > previous, 'Dragging scrolls the editor')
            # Flush native cursor/scroll events, without waiting the 120 ms
            # quiet period that previously left the large viewport behind.
            editor.lua('vim.cmd("redraw!")')
            state = snapshot()
            assert aligned(state), ('Viewport and cursor must follow each movement together', state)
            previous = state['top']
            time.sleep(.015)
        editor.call('nvim_input_mouse', 'left', 'release', '', 0, start + 14, column)
        editor.lua('vim.cmd("redraw!")')
        state = snapshot()
        assert aligned(state), ('Release leaves no deferred viewport jump', state)
        assert editor.lua('return vim.api.nvim_get_current_win()') == source
        assert editor.lua('return vim.fn.mode()') == 'i', 'Dragging preserves Insert mode'
        assert editor.call('nvim_buf_get_lines', buf, 0, -1, False) == original
        # Ordinary scrolling also updates the viewport promptly.
        previous = snapshot()['top']
        editor.call('nvim_input_mouse', 'wheel', 'down', '', 0, start + 14, column)
        editor.wait(lambda: snapshot()['top'] > previous, 'Wheel scrolls the source')
        editor.lua('vim.cmd("redraw!")')
        editor.wait(lambda: aligned(snapshot()), 'Wheel keeps viewport and cursor in sync')
        # A burst of queued movements must finish at the newest position and
        # preserve Normal mode as well as Insert mode.
        editor.lua('vim.cmd("stopinsert")')
        grab = editor.lua('local w=require("neominimap.window.float.window_map").get_minimap_winid(...);'
                          'local p=vim.api.nvim_win_get_position(w);local v=vim.api.nvim_win_call(w,vim.fn.winsaveview);'
                          'return {p[1]+vim.api.nvim_win_get_cursor(w)[1]-v.topline,p[2]+5}', source)
        editor.call('nvim_input_mouse', 'left', 'press', '', 0, *grab)
        time.sleep(.02)
        editor.lua('vim.cmd("redraw!")')
        previous = snapshot()['top']
        for offset in (2, 4, 6, 9):
            editor.call('nvim_input_mouse', 'left', 'drag', '', 0, grab[0] + offset, grab[1])
        editor.call('nvim_input_mouse', 'left', 'release', '', 0, grab[0] + 9, grab[1])
        editor.wait(lambda: snapshot()['top'] > previous, 'Queued drag reaches the newest position')
        editor.lua('vim.cmd("redraw!")')
        state = snapshot()
        assert aligned(state), ('Queued movements leave cursor and viewport synchronized', state)
        assert editor.lua('return vim.fn.mode()') == 'n', 'Dragging preserves Normal mode'
        assert editor.call('nvim_buf_get_lines', buf, 0, -1, False) == original
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'Error executing' not in messages and 'Invalid window' not in messages, messages
        print('PASS: minimap drag/wheel and queued movements keep cursor and viewport aligned, preserve Insert/Normal mode and content, and retain text-render debounce.')
    finally:
        editor.close()
