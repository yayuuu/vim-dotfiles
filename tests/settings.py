"""Icon preferences affect real file-tree and tab rendering in both modes."""
import json
from pathlib import Path
import subprocess
import tempfile

from ui import Editor

module = Path(__file__).resolve().parents[1] / 'lua' / 'config' / 'settings.lua'
with tempfile.TemporaryDirectory(prefix='nvim-settings-') as directory:
    root = Path(directory)
    for enabled in (True, False):
        project = root / str(enabled)
        project.mkdir()
        folder = project / 'folder'
        folder.mkdir()
        file = folder / 'example.lua'
        file.write_text('local example = 1\n')
        subprocess.run(['git', 'init', '-b', 'main', str(project)], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(['git', '-C', str(project), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(project), '-c', 'user.name=UI Test', '-c', 'user.email=ui@example.invalid',
                        'commit', '-m', 'Baseline'], check=True, stdout=subprocess.DEVNULL)
        file.write_text('local example = 2\n')
        settings = root / f'{enabled}.json'
        settings.write_text(json.dumps({'icons': enabled}))
        # Load the actual reader against an isolated preference file before plugins start.
        bootstrap = ('lua package.preload["config.settings"]=function() '
                     f'local m=dofile({json.dumps(str(module))});m.icons=m.read({json.dumps(str(settings))}).icons;return m end')
        editor = Editor(project, root / f'state-{enabled}', args=('--cmd', bootstrap))
        try:
            assert editor.lua('return require("config.settings").icons') == enabled
            assert editor.lua('return require("mini.icons").config.style') == ('glyph' if enabled else 'ascii')
            def row(path):
                return editor.lua('local s=require("config.sidebar").state();if not s or not s.tree then return "" end;'
                                  'local n,l=s.tree:get_node(...);if not l then return "" end;'
                                  'return vim.api.nvim_buf_get_lines(s.bufnr,l-1,l,false)[1] or ""', str(path))
            editor.wait(lambda: ('' if enabled else '+') in row(folder), 'Closed folder renders')
            editor.lua('vim.cmd("stopinsert");local s=require("config.sidebar").state();vim.api.nvim_set_current_win(s.winid);'
                       'local n,l=s.tree:get_node(...);vim.api.nvim_win_set_cursor(s.winid,{l,0});s.commands.toggle_node(s)', str(folder))
            editor.wait(lambda: ('' if enabled else '-') in row(folder), 'Open folder renders')
            editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert");'
                       'local ns=vim.api.nvim_create_namespace("SettingsDiagnostics");'
                       'vim.diagnostic.set(ns,0,{{lnum=0,col=0,severity=1,message="Error"},'
                       '{lnum=0,col=1,severity=2,message="Warning"}})', str(file))
            editor.call('nvim_input', '<Esc>')
            error, warn = ('', '') if enabled else ('E', 'W')
            def tabs():
                return editor.lua('local t=require("config.editor_tabs");return t.buf and '
                                  'vim.api.nvim_buf_get_lines(t.buf,0,1,false)[1] or ""')
            editor.wait(lambda: error + ' 1' in tabs() and warn + ' 1' in tabs(), 'Tab icons and counts render')
            editor.wait(lambda: error in row(file), 'File-tree diagnostic renders')
            editor.wait(lambda: editor.lua('return require("neo-tree.git").find_existing_status_code(...)', str(file)) == '.M',
                        'Files still tracks Git changes for name colors')
            assert not any(marker in row(file) for marker in ('', '󰄱', '󰱒', '~')), row(file)
            marker = editor.lua('return require("config.git_source").components.git_file({},'
                                '{name="example.lua",extra={status="M"}}).text')
            assert marker == ('' if enabled else 'M') + ' example.lua'
            if enabled:
                assert editor.lua('return require("config.settings").read(...).icons', str(root / 'missing.json'))
                malformed = root / 'invalid.json'
                for contents in ('{', '{"icons":"false"}'):
                    malformed.write_text(contents)
                    assert editor.lua('return require("config.settings").read(...).icons', str(malformed))
        finally:
            editor.close()
    print('PASS: settings.json selects glyphs/letters in file types, folders, Files diagnostics, tabs and Git; missing/invalid preferences fall back safely.')
