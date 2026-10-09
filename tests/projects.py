"""Regression checks for persistent project navigation and file tabs."""
import json
from pathlib import Path
import tempfile
from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-projects-test-') as temporary:
    base = Path(temporary)
    a, b, state = base / 'project A', base / 'project B', base / 'state'
    a.mkdir(); b.mkdir(); state.mkdir()
    (a / 'one.lua').write_text('local first = 1\nlocal second = 2\nreturn first + second\n')
    (a / 'two.lua').write_text('return true\n')
    (b / 'other.txt').write_text('Other project\n')
    alias = base / 'alias'; alias.symlink_to(a, target_is_directory=True)
    history = state / 'nvim' / 'desktop-ide-projects.json'
    editor = Editor(a, state)
    try:
        assert [p['path'] for p in json.loads(history.read_text())['projects']] == [str(a)]
        editor.lua('require("config.ide").open_file(...)', str(a / 'one.lua'))
        editor.lua('require("config.ide").open_file(...)', str(a / 'two.lua'))
        editor.lua('require("config.ide").open_file(...); vim.api.nvim_win_set_cursor(0,{2,4})', str(a / 'one.lua'))
        # Use the actual Open folder prompt callback, including path completion flow.
        editor.lua('local path=...; local input=vim.ui.input; vim.ui.input=function(_,cb) cb(path) end; '
                   'require("config.ide").open_folder(); vim.ui.input=input', str(b))
        editor.wait(lambda: editor.lua('return vim.fn.getcwd()') == str(b), 'Open folder')
        assert editor.files() == []
        editor.lua('require("config.ide").open_file(...)', str(b / 'other.txt'))
        editor.lua('vim.cmd("stopinsert"); vim.cmd("redraw!")')
        # Real click on Projects in the sidebar's source-selector winbar.
        editor.lua('return true')
        match = next((row, ''.join(line).index('Projects') + 2)
                     for row, line in enumerate(editor.grid) if 'Projects' in ''.join(line))
        editor.click(*match)
        editor.wait(lambda: editor.lua('local s=require("neo-tree.sources.manager").get_state("projects"); '
                                      'return s.winid and vim.api.nvim_win_is_valid(s.winid)'), 'Projects tab click')
        position = editor.lua('local s=require("neo-tree.sources.manager").get_state("projects"); '
                              'local p=vim.api.nvim_win_get_position(s.winid); return {p[1]+2,p[2]+3}')
        # MRU order is B, A; click the second row (A).
        editor.click(*position)
        editor.wait(lambda: editor.lua('return vim.fn.getcwd()') == str(a), 'Project click')
        assert set(editor.files()) == {str(a / 'one.lua'), str(a / 'two.lua')}, editor.lua('local r={};for _,b in ipairs(vim.api.nvim_list_bufs()) do if vim.bo[b].buftype=="" then table.insert(r,{name=vim.api.nvim_buf_get_name(b),listed=vim.bo[b].buflisted,modified=vim.bo[b].modified,owner=vim.b[b].ide_project_owner}) end end;return r')
        assert editor.lua('return vim.api.nvim_buf_get_name(0)') == str(a / 'one.lua')
        assert editor.lua('return vim.api.nvim_win_get_cursor(0)') == [2, 4], (editor.lua('return vim.api.nvim_win_get_cursor(0)'),json.loads(history.read_text()))
        assert editor.lua('return require("neo-tree.sources.manager").get_state_for_window('
                          'require("neo-tree.sources.manager").get_state("filesystem").winid).name') == 'filesystem'
        editor.lua('require("config.ide").open_project(...)', str(alias))
        projects = json.loads(history.read_text())['projects']
        assert [p['path'] for p in projects] == [str(a), str(b)], projects
        # Closed file tabs must stay closed after restoring this project.
        editor.lua('local b=vim.fn.bufnr(...); vim.api.nvim_buf_delete(b,{force=true})', str(a / 'two.lua'))
        # Keep unsaved edits when switching to another project.
        editor.lua('vim.api.nvim_buf_set_lines(0,0,1,false,{"local first = 99"})')
        editor.lua('require("config.ide").open_project(...)', str(b))
        assert editor.lua('local b=vim.fn.bufnr(...); return vim.bo[b].modified', str(a / 'one.lua'))
        assert str(b / 'other.txt') in editor.files()
        editor.lua('require("config.ide").open_project(...)', str(a))
        assert editor.lua('return vim.api.nvim_buf_get_lines(0,0,1,false)[1]') == 'local first = 99'
        editor.lua('vim.bo.modified=false')  # The fixture deliberately discards its test-only edit.
        assert str(a / 'two.lua') not in editor.files()
    finally:
        editor.close()
    editor = Editor(a, state)
    try:
        assert editor.files() == [str(a / 'one.lua')], editor.files()
        assert editor.lua('return vim.api.nvim_buf_get_name(0)') == str(a / 'one.lua')
        assert editor.lua('return vim.api.nvim_win_get_cursor(0)') == [2, 4], (editor.lua('return vim.api.nvim_win_get_cursor(0)'),json.loads(history.read_text()))
        editor.lua('require("config.ide").open_project(...)', str(b))
        assert editor.files() == [str(b / 'other.txt')], editor.files()
    finally:
        editor.close()
    editor = Editor(Path.home(), state)
    try:
        assert str(Path.home()) not in [p['path'] for p in json.loads(history.read_text())['projects']]
        editor.lua('require("config.ide").open_project(...)', str(Path.home()))
        assert str(Path.home()) not in [p['path'] for p in json.loads(history.read_text())['projects']]
    finally:
        editor.close()
    editor = Editor(Path.home(), state, [str(b)])
    try:
        assert editor.lua('return vim.fn.getcwd()') == str(b)
        assert editor.files() == [str(b / 'other.txt')]
        assert json.loads(history.read_text())['projects'][0]['path'] == str(b)
    finally:
        editor.close()
    print('PASS: real Projects tab and single project click, Files selection, startup/Open folder MRU, '
          'deduplication and Home exclusion, separate file tabs and active cursor, closed-tab removal, '
          'unsaved edits across switches, restart restoration and directory arguments')
