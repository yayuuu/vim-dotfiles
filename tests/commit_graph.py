"""Match LazyGit graph geometry, ANSI author matching, real ancestry and UI colors."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from ui import Editor


def lazygit_color(name):
    digest = hashlib.md5(name.encode()).digest()
    h, s, l = (sum(digest[:4]) % 100 / 100 * 360 / 360,
               .6 + .4 * (sum(digest[4:8]) % 100 / 100),
               .4 + .2 * (sum(digest[8:12]) % 100 / 100))
    high = l * (1 + s) if l < .5 else l + s - l * s
    low = 2 * l - high

    def channel(t):
        if t < 0:
            t += 1
        elif t > 1:
            t -= 1
        value = (low + (high - low) * 6 * t if 6 * t < 1 else high if 2 * t < 1 else
                 low + (high - low) * (2 / 3 - t) * 6 if 3 * t < 2 else low)
        return int(value * 255)

    return channel(h + 1 / 3) * 65536 + channel(h) * 256 + channel(h - 1 / 3)


with tempfile.TemporaryDirectory(prefix='nvim-commit-graph-') as directory:
    root = Path(directory)
    repo = root / 'repo'
    repo.mkdir()

    def git(*args, **kwargs):
        return subprocess.check_output(['git', '-C', str(repo), *args], **kwargs).decode().strip()

    git('init', '-b', 'main')
    git('config', 'user.name', 'Graph Test')
    git('config', 'user.email', 'graph@example.invalid')
    tree = git('write-tree')

    def commit(subject, parents=(), author='yayuuu'):
        options = [arg for parent in parents for arg in ('-p', parent)]
        return git('commit-tree', tree, *options, input=(subject + '\n').encode(),
                   env={**os.environ, 'GIT_AUTHOR_NAME': author, 'GIT_COMMITTER_NAME': author})

    base = commit('Base')
    email = commit('EP-8281 email fix', [base], 'Daniel Skorupa')
    first_merge = commit('Merge #2178', [base, email])
    pickup = commit('EP-4790 pickup fix', [base], 'Daniel Skorupa')
    head = commit('Merge #2179 / subject contains ╯ and *', [first_merge, pickup])
    git('update-ref', 'refs/heads/main', head)
    git('update-ref', 'refs/heads/feature-email', email)
    git('update-ref', 'refs/heads/feature-pickup', pickup)
    fixtures = json.loads((Path(__file__).parent / 'fixtures/lazygit_graph.json').read_text())
    editor = Editor(repo, root / 'state')
    try:
        for fixture in fixtures['fixtures']:
            actual = editor.lua('local commits=...;local g=require("config.git_graph");local sets=g.build(commits);'
                                'local rows={};for i,p in ipairs(sets) do local s={};for _,c in ipairs(g.render(p)) do '
                                's[#s+1]=c[1] end;rows[i]=table.concat(s):gsub("%s+$","") end;return rows', fixture['commits'])
            assert actual == fixture['expected'], (fixture['name'], actual, fixture['expected'])
        for fixture in fixtures['cells']:
            actual = editor.lua('local f=...;local g=require("config.git_graph");'
                                'return g.render(f.pipes,"selected",f.previous)', fixture)
            assert ''.join(c[0] for c in actual).rstrip() == fixture['expected'], fixture['name']
            for cell, char, style in zip(actual, fixture['expected'], fixture['styles']):
                if char == ' ':
                    continue
                expected_group = ('DesktopCommitGraphSelected' if style == 'highlightStyle' else
                                  editor.lua('return require("config.colors").git_author(...)', style))
                assert cell[1] == expected_group, (fixture['name'], char, cell, style)
        names = ['', 'yayuuu', 'Daniel Skorupa', 'Jesse Duffield', 'Zażółć gęślą', '長い名前', 'x' * 100]
        ansi = editor.lua('local p=require("config.colors").palette;local out={};for i=0,15 do '
                          'out[#out+1]=tonumber(p["terminal_"..i]:sub(2),16) end;return out')

        def author_color(name):
            return editor.lua('local c=require("config.colors");return vim.api.nvim_get_hl(0,{name=c.git_author(...)}).fg', name)

        original_colors = {name: author_color(name) for name in names}
        assert set(original_colors.values()) <= set(ansi), 'Authors use only the sixteen terminal colors'
        assert {name: author_color(name) for name in reversed(names)} == original_colors, 'Assignments do not depend on visit order'
        for name in ['Extra author ' + str(i) for i in range(100)]:
            assert author_color(name) in ansi

        # With exact LazyGit reference RGBs among the sixteen, the perceptual
        # match must select those entries instead of a different readable color.
        exact = {name: lazygit_color(name) for name in ['yayuuu', 'Daniel Skorupa']}
        editor.lua('_G.graph_saved_palette=vim.deepcopy(require("config.colors").palette);'
                   'local c=require("config.colors");c.palette.ui_background="#000000";'
                   'for i=0,15 do c.palette["terminal_"..i]="#000000" end;'
                   'local refs=...;c.palette.terminal_2=string.format("#%06x",refs.yayuuu);'
                   'c.palette.terminal_5=string.format("#%06x",refs["Daniel Skorupa"]);'
                   'c.palette.terminal_15="#ffffff";c.apply()', exact)
        assert {name: author_color(name) for name in exact} == exact, 'Choose the nearest available terminal color'

        # Cached author groups follow palette changes and reject an invisible
        # match. This also covers transparent backgrounds using terminal_0.
        for background in ['#000000', 'NONE']:
            editor.lua('local c=require("config.colors");c.palette.ui_background=...;'
                       'for i=0,15 do c.palette["terminal_"..i]="#000000" end;'
                       'c.palette.terminal_15="#ffffff";c.apply()', background)
            assert all(author_color(name) == 0xffffff for name in names), 'Use the readable ANSI entry'
        editor.lua('local c=require("config.colors");for i=0,15 do c.palette["terminal_"..i]="#000000" end;'
                   'c.palette.terminal_12="#101010";c.apply()')
        assert all(author_color(name) == 0x101010 for name in names), 'Low-contrast palette uses its best available ANSI color'
        editor.lua('local c=require("config.colors");c.palette=_G.graph_saved_palette;_G.graph_saved_palette=nil;c.apply()')
        assert {name: author_color(name) for name in names} == original_colors, 'Restoring the palette restores author assignments'

        editor.lua('vim.g.ide_git_autofetch=false;require("config.ide").git_explorer()')
        editor.wait(lambda: editor.lua('local s=require("config.sidebar");return s.commits and #s.commits==5'), 'Five commits, without spacer rows')
        rows = editor.lua('local s=require("config.sidebar");return vim.api.nvim_buf_get_lines(s.history_buf,0,-1,false)')
        commits = editor.lua('return require("config.sidebar").commits')
        assert [c['commit'] for c in commits] == [head, pickup, first_merge, email, base]
        assert commits[0]['parents'] == [first_merge, pickup]
        assert commits[1]['parents'] == commits[3]['parents'] == [base]
        assert commits[2]['parents'] == [base, email]
        print('\n'.join(rows))
        assert rows[0].startswith(' ⏣─╮ '), rows
        assert rows[1].startswith(' │ ◯ '), rows
        assert rows[2].startswith(' ⏣─│─╮ '), rows
        assert rows[3].startswith(' │ │ ◯ '), rows
        assert rows[4].startswith(' ◯─┴─╯ '), rows
        assert 'subject contains ╯ and *' in rows[0]
        assert '(feature-pickup)' in rows[1] and '(feature-email)' in rows[3]

        def color(row, column):
            editor.lua('vim.cmd("redraw!")')
            position = editor.lua('local s=require("config.sidebar");return vim.fn.screenpos(s.history_win,...,1)', row)
            return editor.highlights[editor.attributes[position['row'] - 1][position['col'] - 1 + column]].get('foreground')

        assert color(2, 3) == author_color('Daniel Skorupa'), 'Rendered feature node uses its terminal color'
        assert color(3, 3) == author_color('Daniel Skorupa'), 'Crossing retains the vertical edge color'
        editor.lua('local s=require("config.sidebar");vim.api.nvim_set_current_win(s.history_win);'
                   'vim.api.nvim_win_set_cursor(s.history_win,{1,0});s.paint_history()')
        selected = editor.lua('return vim.api.nvim_get_hl(0,{name="DesktopCommitGraphSelected"}).fg')
        assert color(2, 1) == selected, 'Selected merge highlights its parent path'
        editor.lua('local c=require("config.colors");c.apply();local s=require("config.sidebar");'
                   'vim.api.nvim_set_current_win(require("config.ide").editor_window());s.paint_history()')
        assert color(2, 3) == author_color('Daniel Skorupa'), 'Palette reload preserves palette-matched author colors'

        editor.lua('local s=require("config.sidebar");s.open_commit(4)')
        editor.wait(lambda: editor.lua('local p=Snacks.picker.get()[1];return p and p.shown'), 'Mapped commit opens preview')
        assert editor.lua('return Snacks.picker.get()[1]:current().commit') == email
        editor.lua('Snacks.picker.get()[1]:close()')
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print(f'PASS: {len(fixtures["fixtures"])} LazyGit routing fixtures, {len(fixtures["cells"])} colored/selected cell fixtures, '
              'ANSI-only author matching, nearest reference colors, contrast/fallback, palette changes, real history, UI colors, selection and preview mapping.')
    finally:
        editor.close()
