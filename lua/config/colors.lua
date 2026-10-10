-- Apply the colors listed in palette.json through theme and plugin APIs.
local M = {}
local api = vim.api
M.palette = vim.json.decode(table.concat(vim.fn.readfile(vim.fn.stdpath('config') .. '/palette.json'), '\n'))

function M.highlights()
  local p = M.palette
  local groups = {
    Normal = { fg = p.vscFront, bg = p.ui_background },
    NormalNC = { link = 'Normal' },
    EndOfBuffer = { fg = p.ui_background, bg = p.ui_background },
    WinBar = { fg = p.vscFront, bg = p.ui_background, bold = true },
    WinBarNC = { fg = p.vscFront, bg = p.ui_background },
    TabLine = { fg = p.vscFront, bg = p.ui_bar_background },
    TabLineFill = { link = 'TabLine' },
    TabLineSel = { fg = p.vscFront, bg = p.ui_background, bold = true },
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
  return { style = 'dark', transparent = false,
    color_overrides = overrides, group_overrides = M.highlights() }
end

function M.statusline()
  local p = M.palette
  return {
    normal = { a = { fg = p.status_fg, bg = p.status_blue, gui = 'bold' },
      b = { fg = p.status_blue, bg = p.ui_bar_background }, c = { fg = p.status_fg, bg = p.ui_bar_background } },
    visual = { a = { fg = p.ui_background, bg = p.status_yellow },
      b = { fg = p.status_yellow, bg = p.ui_bar_background } },
    inactive = { a = { fg = p.status_fg, bg = p.ui_bar_background },
      b = { fg = p.status_inactive, bg = p.ui_bar_background }, c = { fg = p.status_inactive, bg = p.ui_bar_background } },
    replace = { a = { fg = p.ui_background, bg = p.status_red },
      b = { fg = p.status_red, bg = p.ui_bar_background }, c = { fg = p.status_fg, bg = p.ui_bar_background } },
    insert = { a = { fg = p.ui_background, bg = p.status_green },
      b = { fg = p.status_green, bg = p.ui_bar_background }, c = { fg = p.status_fg, bg = p.ui_bar_background } },
    terminal = { a = { fg = p.ui_background, bg = p.status_green },
      b = { fg = p.status_fg, bg = p.ui_bar_background }, c = { fg = p.status_fg, bg = p.ui_bar_background } },
    command = { a = { fg = p.ui_background, bg = p.status_pink },
      b = { fg = p.status_pink, bg = p.ui_bar_background }, c = { fg = p.status_fg, bg = p.ui_bar_background } },
  }
end

function M.git_sync()
  return { fg = M.palette.status_fg, bg = M.palette.ui_bar_background }
end

function M.tab_separator(win)
  local background = api.nvim_get_hl(0, { name = 'BufferLineBackground', link = false }).bg
  -- Resolve Normal in the editor even when a tool has focus.
  local editor_background = api.nvim_win_call(win, function()
    return api.nvim_get_hl(0, { name = 'Normal', link = false }).bg or M.palette.ui_background
  end)
  api.nvim_set_hl(0, 'DesktopTabSeparator', { fg = editor_background, bg = background })
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
