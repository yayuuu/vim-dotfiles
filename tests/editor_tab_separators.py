"""Diagnostic counters and mouse scrolling keep separators at card boundaries."""
from pathlib import Path
import tempfile

from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-tab-separators-') as directory:
    root = Path(directory)
    editor = Editor(root, root / 'state')
    try:
        for index in range(12):
            file = root / f'document-{index:02}-long-name.txt'
            file.write_text('content\n')
            editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert");'
                       'local ns=vim.api.nvim_create_namespace("TabSeparatorDiagnostics");'
                       'vim.diagnostic.set(ns,vim.api.nvim_get_current_buf(),{'
                       '{lnum=0,col=0,severity=vim.diagnostic.severity.WARN,message="First warning"},'
                       '{lnum=0,col=1,severity=vim.diagnostic.severity.WARN,message="Second warning"}})', str(file))
        editor.call('nvim_input', '\x1b')
        editor.wait(lambda: editor.lua('return vim.api.nvim_get_mode().mode') == 'n', 'Normal mode updates diagnostic counters')
        editor.lua('require("config.editor_tabs").draw()')
        editor.wait(lambda: editor.lua('local t=require("config.editor_tabs");return t.buf and '
                                      'vim.api.nvim_buf_get_lines(t.buf,0,1,false)[1]:find("W 2",1,true)~=nil'), 'Warning counters displayed')

        def check_strip():
            result = editor.lua('local t=require("config.editor_tabs");'
                                'local ns=vim.api.nvim_get_namespaces().DesktopIDESharedTabs;'
                                'local line=vim.api.nvim_buf_get_lines(t.buf,0,1,false)[1];'
                                'local marks=vim.api.nvim_buf_get_extmarks(t.buf,ns,0,-1,{details=true});'
                                'local out={};for _,m in ipairs(marks) do out[#out+1]={first=m[3],last=m[4].end_col,'
                                'hl=m[4].hl_group,bg=vim.api.nvim_get_hl(0,{name=m[4].hl_group,link=false}).bg} end;'
                                'return {line=line,hits=t.hits,marks=out}')
            line, hits, marks = result['line'], result['hits'], result['marks']
            assert not any(symbol in line for symbol in ('▎', '▏', '▕')), line
            ids = list(dict.fromkeys(hit['id'] for hit in hits))
            separators = [mark for mark in marks if mark['hl'] == 'DesktopTabSeparator']
            trailing = line.endswith('▌')
            assert len(separators) == len(ids) - 1 + int(trailing), (line, separators)
            for mark in separators:
                assert line.encode()[mark['first']:mark['last']].decode() == '▌'
                column = len(line.encode()[:mark['first']].decode()) + 1
                assert not any(hit['first'] <= column <= hit['last'] for hit in hits), (line, hits)
                assert any(hit['last'] == column - 1 for hit in hits)
                if column < len(line):
                    assert any(hit['first'] == column + 1 for hit in hits)
            # Unhighlighted spacer cells used to expose the fill background after W 2.
            for card_id in ids:
                card_hits = [hit for hit in hits if hit['id'] == card_id]
                start = min(hit['first'] for hit in card_hits) - 1
                end = max(hit['last'] for hit in card_hits)
                card = line[start:end]
                before = len(line[:start].encode())
                after = len(line[:end].encode())
                backgrounds = {mark['bg'] for mark in marks if mark['first'] >= before and mark['last'] <= after}
                assert len(backgrounds) == 1 and None not in backgrounds, (card, backgrounds, marks)
                covered = {byte for mark in marks for byte in range(mark['first'], mark['last'])}
                assert all(byte in covered for byte in range(before, after)), (card, marks)
            assert 'W 2' in line, line
            assert editor.lua('local t=require("config.editor_tabs");local sep=vim.api.nvim_get_hl(0,{name="DesktopTabSeparator",link=false});'
                              'return sep.fg==vim.api.nvim_get_hl(0,{name="Normal",link=false}).bg and '
                              'sep.bg==vim.api.nvim_get_hl(0,{name="BufferLineBackground",link=false}).bg and '
                              'vim.wo[t.win].winhighlight=="Normal:BufferLineBackground,EndOfBuffer:BufferLineBackground"')

        check_strip()
        editor.lua('local t=require("config.editor_tabs");t.first=t.count;t.draw()')
        check_strip()
        assert editor.lua('local t=require("config.editor_tabs");return vim.api.nvim_buf_get_lines(t.buf,0,1,false)[1]').endswith('▌')
        editor.lua('local t=require("config.editor_tabs");t.first=1;t.draw()')
        position = editor.lua('return vim.api.nvim_win_get_position(require("config.editor_tabs").win)')
        current = editor.lua('return vim.api.nvim_get_current_buf()')
        for direction in ('down', 'up', 'down', 'up'):
            before = editor.lua('return require("config.editor_tabs").first')
            for _ in range(3):
                editor.call('nvim_input_mouse', 'wheel', direction, '', 0, position[0], position[1] + 5)
            editor.wait(lambda: editor.lua('return require("config.editor_tabs").first') != before, 'Wheel redraw completed')
            editor.lua('require("config.editor_tabs").draw()')
            check_strip()
            assert editor.lua('return vim.api.nvim_get_current_buf()') == current
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: W 2 counters keep uniform card backgrounds; separators only between cards during repeated mouse scrolling', flush=True)
    finally:
        editor.close()
