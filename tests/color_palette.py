"""Selected JSON palettes apply bounded semantic changes and independent UI colors."""
import json
from pathlib import Path
import tempfile

from ui import Editor

config = Path(__file__).resolve().parents[1]
settings_module = config / 'lua/config/settings.lua'
original = (config / 'palette.json').read_bytes()
baseline = json.loads(original)
matugen = json.loads((config / 'matugen.json').read_text())
interface = {'ui_background', 'ui_bar_background', 'ui_separator', 'vscSelection',
             'vscSearchCurrent', 'vscSearch', 'vscUiBlue', 'vscPopupHighlightLightBlue',
             'status_blue', 'status_accent_fg', 'scrollbar_thumb', 'minimap_viewport_bg'}
interface.update(f'terminal_{index}' for index in range(16))
nearby = {
    'cursor_line_number_fg', 'diagnostic_error', 'diagnostic_hint',
    'diagnostic_info', 'diff_added_fg', 'diff_deleted_bg',
    'panel_fg', 'sidebar_fg', 'sidebar_inactive_fg',
    'status_fg', 'status_green', 'status_inactive',
    'status_red', 'syntax_type', 'syntax_yaml_string',
    'vscBlue', 'vscBlueGreen', 'vscContext',
    'vscContextCurrent', 'vscCursorLight', 'vscDarkYellow',
    'vscDiffRedDark', 'vscDiffRedLight', 'vscDiffRedLightLight',
    'vscDimHighlight', 'vscFoldBackground', 'vscFront',
    'vscGitDeleted', 'vscGitRenamed', 'vscGitStageDeleted',
    'vscGitUntracked', 'vscLightRed', 'vscLineNumber',
    'vscOrange', 'vscPopupFront', 'vscRed',
    'vscSuggestion', 'vscUiOrange', 'whitespace_fg',
}
assert matugen['git_line_fg'] == baseline['ui_background']
assert {k: v for k, v in matugen.items() if k not in interface | nearby} == {
    **{k: v for k, v in baseline.items() if k not in interface | nearby},
    'git_line_fg': baseline['ui_background']}
assert matugen['ui_background'] != 'NONE'


def bootstrap(filename):
    return ('lua package.preload["config.settings"]=function() '
            f'local m=dofile({json.dumps(str(settings_module))});'
            f'm.color_palette={json.dumps(str(filename))};return m end')


def protected_colors(editor):
    return editor.lua('local out={syntax={},git={}};'
                      'for name,hl in pairs(vim.api.nvim_get_hl(0,{})) do '
                      'if (name:sub(1,1)=="@" and not name:match("delimiter%.vimdoc$")) or vim.tbl_contains({'
                      '"Comment","String","Character","Number","Boolean","Float","Identifier",'
                      '"Function","Statement","Conditional","Repeat","Operator","Keyword",'
                      '"Type","StorageClass","Typedef","Constant"},name) then '
                      'out.syntax[name]=vim.api.nvim_get_hl(0,{name=name,link=false}).fg end;'
                      'if name:match("^Diff") or name:match("^GitSigns") or name:match("^NeoTreeGit") or '
                      'name:match("^DesktopMap[ACD]") then '
                      'local resolved=vim.api.nvim_get_hl(0,{name=name,link=false});'
                      'out.git[name]=name=="GitSignsDiffStaged" and {fg=resolved.fg} or resolved end end;return out')


def check_protected(editor, expected):
    actual = protected_colors(editor)
    differences = [(section, name, color, actual[section].get(name))
                   for section, values in expected.items() for name, color in values.items()
                   if actual[section].get(name) != color]
    assert not differences, differences


with tempfile.TemporaryDirectory(prefix='nvim-color-palette-') as directory:
    root = Path(directory)
    file = root / 'example.lua'
    file.write_text('local example = "unchanged syntax"\n')
    # Compare the generated interface against the explicitly permitted semantic
    # replacements, keeping every other original palette token intact.
    expected = dict(baseline)
    expected.update({key: matugen[key] for key in nearby})
    reference = root / 'semantic-reference.json'
    reference.write_text(json.dumps(expected))
    editor = Editor(root, root / 'original-state', args=('--cmd', bootstrap(reference)))
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(file))
        protected = protected_colors(editor)
        assert editor.lua('return require("config.colors").palette_path') == str(reference)
        assert editor.lua('return vim.api.nvim_get_hl(0,{name="Normal",link=false}).bg') == int(baseline['ui_background'][1:], 16)
    finally:
        editor.close()

    editor = Editor(root, root / 'matugen-state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(file))
        assert editor.lua('return require("config.settings").color_palette') == 'matugen.json'
        assert editor.lua('return require("config.colors").palette_path') == str(config / 'matugen.json')
        assert not editor.lua('return require("config.colors").theme_options().transparent')
        background = int(matugen['ui_background'][1:], 16)
        for group in ('Normal', 'NormalNC', 'NeoTreeNormal', 'NormalFloat', 'DesktopPanelNormal'):
            assert editor.lua('return vim.api.nvim_get_hl(0,{name=...,link=false}).bg', group) == background, group
        for index in range(16):
            assert editor.lua('return vim.g["terminal_color_"..tostring(...)]', index) == matugen[f'terminal_{index}']
        assert editor.lua('return vim.api.nvim_get_hl(0,{name="DesktopScrollbarThumb",link=false}).fg') == int(matugen['scrollbar_thumb'][1:], 16)
        check_protected(editor, protected)
        editor.lua('require("config.editor_tabs").draw()')
        assert editor.lua('local t=require("config.editor_tabs");return vim.api.nvim_buf_get_lines(t.buf,0,1,false)[1]:find("▌",1,true)~=nil'), 'Opaque palettes retain the tab separator'
        assert editor.lua('return require("config.colors").statusline().insert.a.fg') != 'NONE'
        editor.lua('vim.cmd("colorscheme vscode")')
        editor.wait(lambda: editor.lua('return vim.api.nvim_get_hl(0,{name="Normal",link=false}).bg') == background, 'Background survives colorscheme reload')
        check_protected(editor, protected)
        preferences = root / 'settings.json'
        for data, icons, filename in [
            ({'color-palette': 'my palette.json'}, True, 'my palette.json'),
            ({'icons': False, 'color-palette': 'custom.json'}, False, 'custom.json'),
            ({'icons': False, 'color-palette': 42}, False, 'palette.json'),
            ({'icons': False, 'color-palette': '  '}, False, 'palette.json'),
            ({'icons': 'false', 'color-palette': 'custom.json'}, True, 'custom.json'),
        ]:
            preferences.write_text(json.dumps(data))
            assert editor.lua('return require("config.settings").read(...)', str(preferences)) == {
                'icons': icons, 'color-palette': filename}
    finally:
        editor.close()

    custom = root / 'my alternate palette.json'
    custom_colors = dict(matugen, ui_background='#102030', scrollbar_thumb='#abcdef')
    custom.write_text(json.dumps(custom_colors))
    editor = Editor(root, root / 'custom-state', args=('--cmd', bootstrap(custom)))
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(file))
        assert editor.lua('return require("config.colors").palette_path') == str(custom)
        assert editor.lua('return vim.api.nvim_get_hl(0,{name="Normal",link=false}).bg') == 0x102030
        assert editor.lua('return vim.api.nvim_get_hl(0,{name="DesktopScrollbarThumb",link=false}).fg') == 0xabcdef
        check_protected(editor, protected)
        for content in ('{', '{"ui_background":"NONE"}', '{"ui_background":12}'):
            custom.write_text(content)
            editor.lua('package.loaded["config.colors"]=nil')
            assert editor.lua('return require("config.colors").palette_path') == str(config / 'palette.json')
        custom.unlink()
        editor.lua('package.loaded["config.colors"]=nil')
        assert editor.lua('return require("config.colors").palette_path') == str(config / 'palette.json')
    finally:
        editor.close()

assert (config / 'palette.json').read_bytes() == original
print('PASS: configured palettes, opaque background, ANSI/UI colors, approved semantic replacements, colorscheme reload, and safe fallbacks.')
