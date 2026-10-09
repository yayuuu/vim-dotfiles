"""Saving ordinary and diff documents clears the displayed modified markers."""
import tempfile
import subprocess
from pathlib import Path
from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-save-marker-') as directory:
    root = Path(directory)
    path = root / 'example.txt'
    path.write_text('original\n')
    subprocess.run(['git', 'init', '-b', 'main', str(root)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=UI Test', '-c', 'user.email=ui@example.invalid', 'commit', '-m', 'Baseline'], check=True, stdout=subprocess.DEVNULL)
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...)', str(path))
        filebuf = editor.lua('return vim.api.nvim_get_current_buf()')
        def card(buf):
            return editor.lua('local buf=...;local t=require("config.editor_tabs");if not t.buf then return "" end;'
                              'local first,last;for _,h in ipairs(t.hits or {}) do if h.id==buf then '
                              'first=math.min(first or h.first,h.first);last=math.max(last or h.last,h.last) end end;'
                              'if not first then return "" end;local line=vim.api.nvim_buf_get_lines(t.buf,0,1,false)[1];'
                              'return vim.fn.strcharpart(line,first-1,last-first+1)', buf)
        def changed(label, expected):
            editor.lua('vim.api.nvim_buf_set_lines(0,0,1,false,{...})', expected)
            editor.wait(lambda: '●' in card(filebuf), label + ' marker appears')
        for kind in ('ordinary', 'diff'):
            if kind == 'diff':
                editor.lua('require("config.diff").open(...)', str(path))
                proxy = editor.lua('return require("config.diff").active.buf')
            for method in ('ctrl-s', 'write'):
                expected = kind + '-' + method
                changed(expected, expected)
                if kind == 'diff':
                    editor.wait(lambda: '●' in card(proxy), 'Diff marker appears')
                if method == 'ctrl-s':
                    editor.call('nvim_input', '<C-s>')
                else:
                    result = editor.lua('vim.cmd("write");local t=require("config.editor_tabs");return vim.api.nvim_buf_get_lines(t.buf,0,1,false)[1]')
                    assert '●' not in result, ('Marker immediately after :write', result)
                editor.wait(lambda: path.read_text().strip() == expected, 'Saved to disk')
                editor.wait(lambda: '●' not in card(filebuf), 'Saved normal card clears marker')
                if kind == 'diff':
                    editor.wait(lambda: '●' not in card(proxy), 'Saved diff card clears marker')
        print('PASS: Ctrl+S and :write clear saved markers for ordinary and diff cards.')
    finally:
        editor.close()
