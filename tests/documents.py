from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
import ui

with tempfile.TemporaryDirectory(prefix='nvim-documents-') as directory:
    root = Path(directory)
    project = root / 'project'
    project.mkdir()
    code = project / 'code.txt'
    code.write_text('Keep this unsaved change\n')
    second = project / 'second.txt'
    second.write_text('Second document\n')
    editor = ui.Editor(project, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(code))
        main = editor.lua('return require("config.ide").editor_window()')
        original = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.lua('vim.api.nvim_buf_set_lines(0,0,1,false,{"Unsaved user edit"})')
        def document_windows():
            return editor.lua('local r={};for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do '
                              'if vim.api.nvim_win_get_config(w).relative=="" and require("config.ide").is_document(vim.api.nvim_win_get_buf(w)) then r[#r+1]=w end end;return r')
        def one_document():
            return document_windows() == [main]
        def active_tabs():
            return editor.lua('local r={};for _,h in ipairs(require("config.editor_tabs").hits or {}) do r[tostring(h.id)]=true end;return r')
        editor.lua('require("config.ide").help();vim.cmd("stopinsert")')
        editor.wait(one_document, 'Shortcut guide stays in main editor')
        assert editor.lua('return vim.api.nvim_buf_get_name(0)').endswith('/KEYBINDS.md')
        editor.lua('vim.cmd("help windows")')
        editor.wait(lambda: one_document() and editor.lua('return vim.bo[vim.api.nvim_win_get_buf(...)].buftype=="help"', main), 'Native help moves from split to main editor')
        helpbuf = editor.lua('return vim.api.nvim_win_get_buf(...)', main)
        editor.wait(lambda: str(helpbuf) in active_tabs(), 'Help appears in document strip')
        assert str(original) in active_tabs(), active_tabs()
        editor.lua('require("config.ide").open_file(nil,...)', original)
        assert editor.lua('return vim.api.nvim_buf_get_lines(0,0,1,false)[1]') == 'Unsaved user edit'
        editor.lua('require("config.ide").open_file(nil,...)', helpbuf)
        editor.call('nvim_input', 'q')
        editor.wait(lambda: one_document() and not editor.lua('return vim.api.nvim_buf_is_valid(...) and vim.bo[...].buflisted', helpbuf), 'q closes help tab while preserving main editor')
        for command in ['split', 'vsplit']:
            editor.lua('vim.cmd("stopinsert");vim.cmd(... .. " " .. vim.fn.fnameescape(select(2,...)))', command, str(second))
            editor.wait(lambda: one_document() and editor.lua('return vim.api.nvim_buf_get_name(vim.api.nvim_win_get_buf(...))', main) == str(second), f'{command} file routes to main editor')
        editor.lua('vim.cmd("checkhealth vim.lsp")')
        editor.wait(lambda: one_document() and editor.lua('return vim.bo[vim.api.nvim_win_get_buf(...)].filetype=="checkhealth"', main), 'Health report moves to main editor')
        health = editor.lua('return vim.api.nvim_win_get_buf(...)', main)
        editor.wait(lambda: str(health) in active_tabs(), 'Health report appears in document strip')
        editor.lua('vim.cmd("stopinsert");vim.cmd("Lazy")')
        editor.wait(lambda: editor.lua('return require("lazy.view").visible() or false'), 'Lazy remains a floating dialog')
        assert one_document()
        editor.lua('require("lazy.view").view:close()')
        print('PASS: shortcut guide, native help, help tab switching/q, horizontal/vertical file splits and health reports use one editor; unsaved content preserved; Lazy stays floating', flush=True)
    finally:
        editor.close()
