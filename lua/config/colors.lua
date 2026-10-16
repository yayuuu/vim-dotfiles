-- Apply the palette selected in settings.json through theme and plugin APIs.
local M = {}
local api = vim.api
local config = vim.fn.stdpath('config')
local default_path = vim.fs.joinpath(config, 'palette.json')

local function read_palette(path)
  local palette = vim.json.decode(table.concat(vim.fn.readfile(path), '\n'))
  assert(type(palette) == 'table' and type(palette.ui_background) == 'string', 'expected a complete color palette')
  for _, value in pairs(palette) do
    assert(type(value) == 'string' and (value == 'NONE' or value:match('^#%x%x%x%x%x%x$')), 'invalid palette color')
  end
  return palette
end

local filename = vim.fs.normalize(require('config.settings').color_palette)
local absolute = filename:sub(1, 1) == '/' or filename:match('^%a:[/\\]')
M.palette_path = absolute and filename or vim.fs.joinpath(config, filename)
local ok, palette = pcall(function()
  local selected = read_palette(M.palette_path)
  if M.palette_path ~= default_path then
    local baseline_ok, baseline = pcall(read_palette, default_path)
    if baseline_ok then
      for key in pairs(baseline) do assert(selected[key] ~= nil, 'missing palette color: ' .. key) end
    end
  end
  return selected
end)
if not ok then
  local message = 'Cannot load color palette ' .. filename .. ': ' .. tostring(palette) .. '. Using palette.json.'
  vim.schedule(function() vim.notify(message, vim.log.levels.WARN) end)
  M.palette_path, palette = default_path, read_palette(default_path)
end
M.palette = palette
local repository_name = ''

function M.repository_color(name)
  if name == '' then return M.palette.status_green end
  -- Independent parts of a stable hash choose hue, saturation and lightness.
  -- Use deeper mint/turquoise and brighter pink/blue to separate the pastels.
  -- Warm reds stay light enough to read as pink or peach, never saturated red.
  local hash = vim.fn.sha256(name)
  local hue = (tonumber(hash:sub(1, 8), 16) % 36000) / 6000
  local saturation = 0.50 + 0.22 * tonumber(hash:sub(9, 12), 16) / 65535
  local ranges = { { 0.76, 0.80 }, { 0.64, 0.72 }, { 0.60, 0.70 },
    { 0.57, 0.68 }, { 0.70, 0.77 }, { 0.70, 0.78 } }
  local sector, blend = math.floor(hue) + 1, hue % 1
  local current, following = ranges[sector], ranges[sector % 6 + 1]
  local minimum = current[1] + (following[1] - current[1]) * blend
  local maximum = current[2] + (following[2] - current[2]) * blend
  local lightness = minimum + (maximum - minimum) * tonumber(hash:sub(13, 16), 16) / 65535
  local chroma = (1 - math.abs(2 * lightness - 1)) * saturation
  local secondary = chroma * (1 - math.abs(hue % 2 - 1))
  local offset = lightness - chroma / 2
  local rgb = ({ { chroma, secondary, 0 }, { secondary, chroma, 0 },
    { 0, chroma, secondary }, { 0, secondary, chroma },
    { secondary, 0, chroma }, { chroma, 0, secondary } })[sector]
  return string.format('#%02x%02x%02x',
    math.floor((rgb[1] + offset) * 255 + 0.5),
    math.floor((rgb[2] + offset) * 255 + 0.5),
    math.floor((rgb[3] + offset) * 255 + 0.5))
end

local function repository_highlight()
  return { fg = M.repository_color(repository_name), bg = M.palette.ui_background, bold = true }
end

function M.set_repository(name)
  if repository_name == name then return end
  repository_name = name
  api.nvim_set_hl(0, 'DesktopRepositoryName', repository_highlight())
end

function M.highlights()
  local p = M.palette
  local git_line_fg = p.git_line_fg or (p.ui_background == 'NONE' and p.terminal_0 or p.ui_background)
  local groups = {
    Normal = { fg = p.vscFront, bg = p.ui_background },
    NormalNC = { link = 'Normal' },
    EndOfBuffer = { fg = p.ui_background, bg = p.ui_background },
    WinBar = { fg = p.vscFront, bg = p.ui_background, bold = true },
    WinBarNC = { fg = p.vscFront, bg = p.ui_background },
    DesktopRepositoryName = repository_highlight(),
    TabLine = { fg = p.vscFront, bg = p.ui_bar_background },
    TabLineFill = { link = 'TabLine' },
    TabLineSel = { fg = p.vscFront, bg = p.ui_background, bold = true },
    DesktopTabStrip = { fg = p.sidebar_inactive_fg, bg = p.ui_background },
    StatusLine = { fg = p.status_fg, bg = p.ui_bar_background },
    StatusLineNC = { fg = p.status_inactive, bg = p.ui_bar_background },
    WinSeparator = { fg = p.ui_separator, bg = p.ui_background },
    VertSplit = { link = 'WinSeparator' },
    FloatBorder = { fg = p.ui_separator, bg = p.ui_background },
    NeoTreeWinSeparator = { link = 'WinSeparator' },
    NeoTreeFloatBorder = { link = 'FloatBorder' },
    NeoTreeTitleBar = { link = 'WinBar' },
    TroubleNormal = { link = 'Normal' },
    TroubleNormalNC = { link = 'Normal' },
    DapUINormal = { link = 'Normal' },
    DapUIEndOfBuffer = { link = 'EndOfBuffer' },
    AerialNormal = { link = 'Normal' },
    AerialNormalNC = { link = 'Normal' },
    AerialLine = { bg = p.ui_bar_background, bold = true },
    AerialLineNC = { link = 'AerialLine' },
    DiffAdd = { bg = p.diff_added_bg },
    DiffDelete = { bg = p.diff_deleted_bg, fg = p.diff_deleted_fg },
    DiffChange = { bg = p.diff_changed_bg },
    DiffText = { bg = p.diff_text_bg, bold = true },
    -- The theme otherwise borrows the transparent editor background as text.
    GitSignsAddLn = { fg = git_line_fg, bg = p.vscGreen },
    GitSignsChangeLn = { fg = git_line_fg, bg = p.vscYellow },
    GitSignsDeleteLn = { fg = git_line_fg, bg = p.vscRed },
    DesktopDiffRemoved = { bg = p.diff_deleted_bg },
    DesktopDiffAddedGap = { bg = p.diff_added_bg, fg = p.diff_added_fg },
    DesktopMapAdd = { bg = p.diff_added_bg, fg = p.diff_added_fg },
    DesktopMapDelete = { bg = p.diff_deleted_bg, fg = p.diff_deleted_fg },
    DesktopMapChange = { bg = p.diff_changed_bg, fg = p.diff_changed_fg },
    NeominimapBackground = { link = 'Normal' },
    NeominimapCursorLine = { link = 'Visual' },
    DesktopMinimapViewport = { bg = p.minimap_viewport_bg },
    DesktopScrollbarTrack = { fg = p.ui_bar_background, bg = p.ui_background },
    DesktopScrollbarThumb = { fg = p.scrollbar_thumb, bg = p.ui_background },
    NeoTreeTabActive = { fg = p.vscFront, bg = p.ui_background, bold = true },
    NeoTreeTabInactive = { fg = p.sidebar_inactive_fg, bg = p.ui_bar_background },
    NeoTreeTabSeparatorActive = { fg = p.ui_background },
    NeoTreeTabSeparatorInactive = { fg = p.ui_background, bg = p.ui_bar_background },
    NeoTreeNormal = { fg = p.sidebar_fg, bg = p.ui_background },
    NeoTreeNormalNC = { link = 'NeoTreeNormal' },
    DesktopSearchLabel = { fg = p.vscFront, bg = p.ui_background, bold = true, italic = true },
    DesktopSearchMode = { fg = p.vscGreen, bg = p.ui_background, bold = true, italic = true },
    NeoTreeEndOfBuffer = { fg = p.ui_background, bg = p.ui_background },
    NeoTreeCursorLine = { bg = p.ui_bar_background },
    DesktopPanelNormal = { fg = p.panel_fg, bg = p.ui_background },
    DesktopPanelEndOfBuffer = { fg = p.ui_background, bg = p.ui_background },
    NormalFloat = { fg = p.vscPopupFront, bg = p.ui_background },
    SnacksPicker = { link = 'NormalFloat' },
    SnacksPickerBorder = { fg = p.ui_separator, bg = p.ui_background },
    CursorLineNr = { fg = p.cursor_line_number_fg, bg = p.ui_background },
    Whitespace = { fg = p.whitespace_fg },
    Type = { fg = p.syntax_type },
    StorageClass = { fg = p.vscPink },
    Typedef = { fg = p.syntax_type },
    ['@type.builtin'] = { fg = p.syntax_type },
    ['@type.qualifier'] = { fg = p.vscPink },
    ['@lsp.type.property'] = { fg = p.syntax_property },
    ['@lsp.type.variable'] = { fg = p.vscLightBlue },
    ['@lsp.type.parameter'] = { fg = p.vscLightBlue },
    ['@string.yaml'] = { fg = p.syntax_yaml_string },
    ['@property.yaml'] = { fg = p.vscFront },
    ['@string.special.key.yaml'] = { fg = p.vscFront },
    ['@property.toml'] = { fg = p.vscFront },
    ['@string.special.key.json'] = { fg = p.vscFront },
    ['@markup.heading'] = { fg = p.vscPink, bold = true },
    WarningMsg = { fg = p.diagnostic_warn, bg = p.ui_background },
  }
  for _, severity in ipairs({ 'Error', 'Warn', 'Info', 'Hint' }) do
    local color = p['diagnostic_' .. severity:lower()]
    for _, prefix in ipairs({ 'Diagnostic', 'DiagnosticSign', 'DiagnosticFloating', 'DiagnosticVirtualText' }) do
      groups[prefix .. severity] = { fg = color }
    end
    groups['DiagnosticUnderline' .. severity] = { undercurl = true, sp = color }
  end
  for level = 1, 6 do
    groups['@markup.heading.' .. level .. '.markdown'] = { fg = p.vscPink, bold = true }
  end
  -- Bufferline derives defaults from Normal; explicitly retain the imported tab colors.
  groups.BufferLineBackground = { fg = p.sidebar_inactive_fg, bg = p.ui_bar_background }
  groups.BufferLineFill = { bg = p.ui_bar_background }
  for _, suffix in ipairs({ '', 'Visible', 'Selected' }) do
    local background = suffix == 'Selected' and p.ui_background or p.ui_bar_background
    for _, name in ipairs({ 'Buffer', 'Numbers', 'CloseButton', 'Modified', 'Diagnostic',
      'Error', 'ErrorDiagnostic', 'Warning', 'WarningDiagnostic', 'Info', 'InfoDiagnostic', 'Hint', 'HintDiagnostic' }) do
      local foreground = suffix == 'Selected' and p.vscFront or p.sidebar_inactive_fg
      if name:find('Error') then foreground = p.diagnostic_error
      elseif name:find('Warning') then foreground = p.diagnostic_warn
      elseif name:find('Info') then foreground = p.diagnostic_info
      elseif name:find('Hint') then foreground = p.diagnostic_hint end
      groups['BufferLine' .. name .. suffix] = { fg = foreground, bg = background }
    end
  end
  return groups
end

function M.theme_options()
  local p = M.palette
  local overrides = vim.deepcopy(p)
  -- One palette value feeds every theme token for the same structural surface.
  for _, name in ipairs({ 'vscBack', 'vscTabCurrent', 'vscLeftDark', 'vscPopupBack',
    'vscCursorDarkDark', 'vscCursorDark' }) do overrides[name] = p.ui_background end
  for _, name in ipairs({ 'vscTabOther', 'vscTabOutside', 'vscLeftMid', 'vscLeftLight' }) do
    overrides[name] = p.ui_bar_background
  end
  overrides.vscSplitDark, overrides.vscSplitLight = p.ui_separator, p.ui_separator
  overrides.vscSplitThumb = p.scrollbar_thumb
  overrides.vscPopupHighlightBlue = p.vscSelection
  overrides.vscPopupHighlightGray = p.ui_bar_background
  return { style = 'dark', transparent = p.ui_background == 'NONE',
    color_overrides = overrides, group_overrides = M.highlights() }
end

function M.statusline()
  local p = M.palette
  -- A transparent panel background cannot also serve as a badge's text color.
  local badge_fg = p.ui_background == 'NONE' and p.terminal_0 or p.ui_background
  return {
    normal = { a = { fg = p.status_accent_fg or p.status_fg, bg = p.status_blue, gui = 'bold' },
      b = { fg = p.status_blue, bg = p.ui_bar_background }, c = { fg = p.status_fg, bg = p.ui_bar_background } },
    visual = { a = { fg = badge_fg, bg = p.status_yellow },
      b = { fg = p.status_yellow, bg = p.ui_bar_background } },
    inactive = { a = { fg = p.status_fg, bg = p.ui_bar_background },
      b = { fg = p.status_inactive, bg = p.ui_bar_background }, c = { fg = p.status_inactive, bg = p.ui_bar_background } },
    replace = { a = { fg = badge_fg, bg = p.status_red },
      b = { fg = p.status_red, bg = p.ui_bar_background }, c = { fg = p.status_fg, bg = p.ui_bar_background } },
    insert = { a = { fg = badge_fg, bg = p.status_green },
      b = { fg = p.status_green, bg = p.ui_bar_background }, c = { fg = p.status_fg, bg = p.ui_bar_background } },
    terminal = { a = { fg = badge_fg, bg = p.status_green },
      b = { fg = p.status_fg, bg = p.ui_bar_background }, c = { fg = p.status_fg, bg = p.ui_bar_background } },
    command = { a = { fg = badge_fg, bg = p.status_pink },
      b = { fg = p.status_pink, bg = p.ui_bar_background }, c = { fg = p.status_fg, bg = p.ui_bar_background } },
  }
end

function M.git_sync()
  return { fg = M.palette.status_fg, bg = M.palette.ui_bar_background }
end

function M.tab_separator(win)
  -- Resolve Normal in the editor even when a tool has focus.
  local editor_background = api.nvim_win_call(win, function()
    return api.nvim_get_hl(0, { name = 'Normal', link = false }).bg or M.palette.ui_background
  end)
  api.nvim_set_hl(0, 'DesktopTabSeparator', { fg = editor_background, bg = editor_background })
  -- A half-block cannot paint a transparent foreground; keep the one-cell gap.
  return editor_background == 'NONE' and ' ' or '▌'
end

function M.apply()
  for name, definition in pairs(M.highlights()) do api.nvim_set_hl(0, name, definition) end
  -- ANSI colors are independent of syntax colors (e.g. green strings and gray comments).
  for index = 0, 15 do vim.g['terminal_color_' .. index] = M.palette['terminal_' .. index] end
end

function M.panel(win)
  local types = { aerial = true, dapui_scopes = true, dapui_breakpoints = true,
    dapui_stacks = true, dapui_watches = true, ide_terminal_list = true, trouble = true }
  if not types[vim.bo[api.nvim_win_get_buf(win)].filetype] then return end
  local highlights = {}
  for entry in vim.wo[win].winhighlight:gmatch('[^,]+') do
    if not entry:match('^Normal:') and not entry:match('^NormalNC:') and not entry:match('^EndOfBuffer:') then
      highlights[#highlights + 1] = entry
    end
  end
  vim.list_extend(highlights, { 'Normal:DesktopPanelNormal', 'NormalNC:DesktopPanelNormal',
    'EndOfBuffer:DesktopPanelEndOfBuffer' })
  vim.wo[win].winhighlight = table.concat(highlights, ',')
end

function M.setup()
  M.apply()
  for _, win in ipairs(api.nvim_list_wins()) do M.panel(win) end
  local group = api.nvim_create_augroup('DesktopColors', { clear = true })
  api.nvim_create_autocmd('ColorScheme', {
    group = group,
    callback = function() vim.schedule(M.apply) end,
  })
  api.nvim_create_autocmd({ 'FileType', 'BufWinEnter' }, {
    group = group, callback = function() M.panel(api.nvim_get_current_win()) end,
  })
end

return M
