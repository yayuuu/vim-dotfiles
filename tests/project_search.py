"""Project search uses one sidebar, grouped rg results and pinned clickable inputs."""
from pathlib import Path
import subprocess
import tempfile
from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-project-search-') as directory:
    root = Path(directory)
    repo = root / 'project'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    (repo / 'folder').mkdir()
    source = repo / 'folder' / 'example file.txt'
    source.write_text('first line\nhello Needle here\nthird line\nsecond needle found\n')
    (repo / 'other.txt').write_text('needle again\n')
    (repo / '.hidden.txt').write_text('needle hidden\n')
    (repo / 'needle filename.txt').write_text('filename only\n')
    (repo / '.gitignore').write_text('ignored.txt\n')
    (repo / 'ignored.txt').write_text('needle ignored\n')
    editor = Editor(repo, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.api.nvim_buf_set_lines(0,4,4,false,{"Unsaved notes"})', str(source))
        document = editor.lua('return vim.api.nvim_get_current_buf()')
        terminal = editor.lua('return require("config.terminals").items[1].buf')

        def current():
            return editor.lua('local s=require("config.sidebar").state();return s and s.name')

        def tab(label, name):
            editor.lua('vim.cmd("redraw!")')
            row, col, width = editor.lua('local s,w=require("config.sidebar").state();local p=vim.api.nvim_win_get_position(w);return {p[1],p[2],vim.api.nvim_win_get_width(w)}')
            bar = ''.join(editor.grid[row][col:col + width])
            editor.click(row, col + bar.index(label) + len(label) // 2)
            editor.wait(lambda: current() == name, label + ' tab opens')
            editor.wait(lambda: not editor.lua('return require("config.sidebar").changing or require("config.layout").scaling'), 'Sidebar settles')

        def session():
            return editor.lua('local s=require("config.project_search").sessions[require("config.ide").root()];return {query=s.query,mode=s.mode,count=s.count,busy=s.busy or false,status=s.status,files=s.files}')

        def settled(query, count):
            editor.wait(lambda: session()['query'] == query and session()['count'] == count and not session()['busy'], 'Search completes: ' + query)
            editor.lua('vim.wait(100);vim.cmd("redraw!")')

        def input_text(query):
            editor.lua('local m=require("config.project_search");m.focus();vim.api.nvim_buf_set_lines(0,0,-1,false,{...})', query)

        def choose_mode(target):
            row, col = editor.lua('return vim.api.nvim_win_get_position(require("config.project_search").header.win)')
            label = editor.lua('return vim.api.nvim_buf_get_lines(require("config.project_search").header.buf,0,1,false)[1]')
            editor.click(row, col + (label.index('⇄') if target == 'arrow' else 9))

        def check_header(mode):
            label, field, panel, marks = editor.lua('local h=require("config.project_search").header;return {'
                'vim.api.nvim_buf_get_lines(h.buf,0,1,false)[1],vim.api.nvim_win_get_config(h.input),'
                'vim.api.nvim_win_get_position(h.source),vim.api.nvim_buf_get_extmarks(h.buf,-1,0,-1,{details=true})}')
            assert label == ' Find in ' + mode + ' ⇄', label
            assert field['row'] == 1 and field['col'] == 1, 'Input border directly below the label, with one character of left padding'
            editor.wait(lambda: editor.lua('local h=require("config.project_search").header;'
                'local field=vim.api.nvim_win_get_position(h.input);local source=vim.api.nvim_win_get_position(h.source);'
                'return field[1]==source[1]+2 and field[2]==source[2]+1'), 'Input border stays aligned with the label after layout settles')
            assert any(mark[2] == 9 and mark[3].get('end_col') == 9 + len(mode) and mark[3].get('hl_group') == 'DesktopSearchMode' for mark in marks), marks
            assert editor.lua('return vim.api.nvim_get_hl(0,{name="DesktopSearchLabel",link=false}).fg') == editor.lua('return tonumber(require("config.colors").palette.vscFront:sub(2),16)')
            assert editor.lua('return vim.api.nvim_get_hl(0,{name="DesktopSearchMode",link=false}).fg') == editor.lua('return tonumber(require("config.colors").palette.vscGreen:sub(2),16)')

        def lines():
            return editor.lua('local s=require("config.sidebar").state();return vim.api.nvim_buf_get_lines(s.bufnr,0,-1,false)')

        def click_result(text):
            before = editor.lua('local out={};for _,b in ipairs(vim.api.nvim_list_bufs()) do '
                                'if vim.bo[b].buflisted and vim.bo[b].buftype=="" then out[#out+1]={buf=b,'
                                'lines=vim.api.nvim_buf_get_lines(b,0,-1,false),tick=vim.api.nvim_buf_get_changedtick(b),'
                                'modified=vim.bo[b].modified} end end;return out')
            data = editor.lua('local s,w=require("config.sidebar").state();local p=vim.api.nvim_win_get_position(w);return {p[1],p[2],vim.api.nvim_win_call(w,function()return vim.fn.line("w0")end)}')
            index = next(i for i, line in enumerate(lines()) if text in line)
            editor.click(data[0] + 1 + index - (data[2] - 1), data[1] + 8)
            editor.lua('vim.wait(100)')
            for saved in before:
                assert editor.lua('return vim.api.nvim_buf_get_lines(...,0,-1,false)', saved['buf']) == saved['lines'], 'Clicking a search result must not insert text'
                assert editor.lua('return vim.api.nvim_buf_get_changedtick(...)', saved['buf']) == saved['tick'], 'Navigation must not edit the document'
                assert editor.lua('return vim.bo[...].modified', saved['buf']) == saved['modified'], 'Navigation must preserve modified flags'

        editor.lua('local s,w=require("config.sidebar").state();vim.api.nvim_win_set_width(w,54);require("config.layout").save()')
        tab('Search', 'search')
        editor.wait(lambda: editor.lua('local h=require("config.project_search").header;return h and vim.api.nvim_win_is_valid(h.input)'), 'Pinned search field')
        check_header('content')
        # Start typing by clicking the empty input, without Vim mode commands.
        editor.lua('vim.cmd("stopinsert")')
        field_position = editor.lua('return vim.api.nvim_win_get_position(require("config.project_search").header.input)')
        editor.click(field_position[0] + 1, field_position[1] + 2)
        editor.wait(lambda: editor.lua('return vim.fn.mode()').startswith('i'), 'Empty input click enters Insert mode')
        editor.call('nvim_input', 'needle')
        settled('needle', 4)
        output = lines()
        assert any('example file.txt (2)' in line for line in output), output
        assert any('2: hello Needle here' in line for line in output), output
        assert any('4: second needle found' in line for line in output), output
        assert not any('ignored.txt' in line for line in output), output
        assert len(session()['files']) == 3, session()
        click_result('4: second needle')
        editor.wait(lambda: editor.lua('return vim.api.nvim_get_current_buf()') == document, 'Matching line opens existing document')
        assert editor.lua('return vim.api.nvim_win_get_cursor(0)') == [4, 7]
        editor.wait(lambda: editor.lua('return vim.fn.mode()').startswith('i'), 'Result opens in Insert mode')
        assert editor.lua('return vim.bo[...].modified', document)
        click_result('example file.txt (2)')
        assert editor.lua('return vim.api.nvim_win_get_cursor(0)') == [2, 6], 'Filename opens its first occurrence'
        for _ in range(4):
            click_result('4: second needle')
            editor.call('nvim_input', '<Esc>')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Escape stays in Normal mode')
            click_result('example file.txt (2)')
            editor.wait(lambda: editor.lua('return vim.fn.mode()').startswith('i'), 'Repeated result navigation enters Insert mode')
        # Focus handlers can request Insert after navigation queues its own
        # transition, before Neovim consumes queued input. Neither may edit text.
        editor.call('nvim_input', '<Esc>')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Prepare overlapping Insert requests')
        editor.lua('local m=require("config.project_search");local s=m.sessions[require("config.ide").root()];'
                   'local file;for _,f in ipairs(s.files)do if f.path==... then file=f;break end end;'
                   'm.open({type="search_match",path=file.path,extra=file.first});vim.wait(30);vim.cmd("startinsert")', str(source))
        editor.lua('vim.wait(100)')
        assert editor.lua('return vim.api.nvim_buf_get_lines(...,0,-1,false)', document) == ['first line', 'hello Needle here', 'third line', 'second needle found', 'Unsaved notes'], 'Overlapping Insert requests must not insert an i'
        # Blank space cannot activate the last result.
        before = editor.lua('return vim.api.nvim_win_get_buf(require("config.ide").main_editor)')
        row, col, height = editor.lua('local s,w=require("config.sidebar").state();local p=vim.api.nvim_win_get_position(w);return {p[1],p[2],vim.api.nvim_win_get_height(w)}')
        editor.click(row + height - 2, col + 8)
        assert editor.lua('return vim.api.nvim_win_get_buf(require("config.ide").main_editor)') == before
        # Mode switch reuses the query and returns matching file paths.
        choose_mode('arrow')
        settled('needle', 1)
        assert session()['mode'] == 'files'
        check_header('file names')
        assert any('needle filename.txt' in line for line in lines()), lines()
        assert not any('2: hello' in line for line in lines())
        click_result('needle filename.txt')
        assert editor.lua('return vim.api.nvim_buf_get_name(0)') == str(repo / 'needle filename.txt')
        tab('Files', 'filesystem')
        assert not editor.lua('return require("config.project_search").header'), 'Search fields hide with source'
        tab('Debug', 'debug')
        assert not editor.lua('return require("config.project_search").header')
        tab('Search', 'search')
        settled('needle', 1)
        choose_mode('mode')
        settled('needle', 4)
        check_header('content')
        input_text('missing result')
        settled('missing result', 0)
        assert any('No matches' in line for line in lines())
        # Smart case, literal punctuation and a leading dash are rg arguments safely.
        input_text('Needle')
        settled('Needle', 1)
        input_text('-not-a-flag[')
        settled('-not-a-flag[', 0)
        input_text('needle')
        settled('needle', 4)
        header = editor.lua('return require("config.project_search").header.input')
        editor.lua('require("config.ide").search_project()')
        editor.wait(lambda: editor.lua('return vim.api.nvim_get_current_win()') == header, 'Project search action focuses existing input')
        editor.call('nvim_ui_try_resize', 190, 56)
        editor.lua('vim.wait(300);vim.cmd("redraw!")')
        check_header('content')
        assert editor.lua('local h=require("config.project_search").header;local c=vim.api.nvim_win_get_config(h.input);return c.win==h.source and c.width<=vim.api.nvim_win_get_width(h.source)-2')
        # Streaming is bounded, and both scrollbars leave the input pinned.
        (repo / 'large.txt').write_text(('bulkword ' + 'long excerpt ' * 40 + '\n') * 1200)
        input_text('bulkword')
        settled('bulkword', 1000)
        assert '1000+' in session()['status'], session()
        tree = editor.lua('return require("config.sidebar").state().winid')
        editor.wait(lambda: editor.lua('local s=require("config.vscroll").sources[...];return s and s.bar~=nil', tree), 'Search vertical scrollbar')
        editor.wait(lambda: editor.lua('return require("config.hscroll").bars[...]~=nil', tree), 'Search horizontal scrollbar')
        header_position = editor.lua('return vim.api.nvim_win_get_position(require("config.project_search").header.input)')
        bar = editor.lua('return require("config.vscroll").sources[...].bar', tree)
        bar_position = editor.call('nvim_win_get_position', bar['win'])
        assert editor.call('nvim_win_get_config', bar['win'])['row'] == 4
        editor.click(bar_position[0] + editor.call('nvim_win_get_height', bar['win']) - 1, bar_position[1])
        editor.wait(lambda: editor.lua('return vim.api.nvim_win_call(...,function()return vim.fn.line("w0")>1 end)', tree), 'Search scrolls to later matches')
        assert editor.lua('return vim.api.nvim_win_get_position(require("config.project_search").header.input)') == header_position
        # The last query wins, and a different project has separate search state.
        input_text('bulkword')
        input_text('missing-newest-query')
        settled('missing-newest-query', 0)
        other = root / 'second project'
        other.mkdir()
        (other / 'second.txt').write_text('newproject needle\n')
        editor.lua('require("config.ide").open_project(...);require("config.ide").search_project()', str(other))
        editor.wait(lambda: current() == 'search' and editor.lua('local h=require("config.project_search").header;return h and h.root==require("config.ide").root()'), 'New project search')
        assert session()['query'] == '', session()
        input_text('newproject')
        settled('newproject', 1)
        assert session()['files'][0]['path'] == str(other / 'second.txt')
        editor.lua('require("config.ide").open_project(...);require("config.ide").search_project()', str(repo))
        editor.wait(lambda: current() == 'search' and editor.lua('local h=require("config.project_search").header;return h and h.root==require("config.ide").root()'), 'Original project restored')
        settled('missing-newest-query', 0)
        assert editor.lua('return require("config.terminals").items[1].buf') == terminal
        assert editor.lua('return vim.api.nvim_buf_get_lines(...,0,-1,false)', document)[-1] == 'Unsaved notes'
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: Search tab, grouped line navigation, filename mode, smart case, ignored/hidden files, blank guard, source transitions, singleton input, resizing, capped streaming, pinned controls with both scrollbars, latest query and project isolation; unsaved document and terminal preserved', flush=True)
    except Exception:
        print(editor.lua('return vim.fn.execute("messages")'), flush=True)
        print('\n'.join(''.join(line) for line in editor.grid), flush=True)
        raise
    finally:
        editor.close()
