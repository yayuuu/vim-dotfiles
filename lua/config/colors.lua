-- Apply the colors listed in palette.json through theme and plugin APIs.
local M = {}
local api = vim.api
M.palette = vim.json.decode(table.concat(vim.fn.readfile(vim.fn.stdpath('config') .. '/palette.json'), '\n'))

function M.highlights()
  local p = M.palette
  return {
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
    DesktopMinimapViewport = { link = 'CursorLine' },
    NeoTreeTabActive = { fg = p.vscFront, bg = p.vscBack, bold = true },
    NeoTreeTabInactive = { fg = p.sidebar_inactive_fg, bg = p.sidebar_inactive_bg },
    NeoTreeTabSeparatorActive = { fg = p.sidebar_separator_active_fg },
    NeoTreeTabSeparatorInactive = { fg = p.sidebar_separator_inactive_fg, bg = p.sidebar_inactive_bg },
  }
end

function M.theme_options()
  return { style = 'dark', transparent = false,
    color_overrides = M.palette, group_overrides = M.highlights() }
end

function M.statusline()
  local p = M.palette
  return {
    normal = { a = { fg = p.status_fg, bg = p.status_blue, gui = 'bold' },
      b = { fg = p.status_blue, bg = p.status_bg_secondary }, c = { fg = p.status_fg, bg = p.status_bg } },
    visual = { a = { fg = p.status_bg, bg = p.status_yellow },
      b = { fg = p.status_yellow, bg = p.status_bg } },
    inactive = { a = { fg = p.status_fg, bg = p.status_bg },
      b = { fg = p.status_inactive, bg = p.status_bg }, c = { fg = p.status_inactive, bg = p.status_bg } },
    replace = { a = { fg = p.status_bg, bg = p.status_red },
      b = { fg = p.status_red, bg = p.status_bg }, c = { fg = p.status_fg, bg = p.status_bg } },
    insert = { a = { fg = p.status_bg, bg = p.status_green },
      b = { fg = p.status_green, bg = p.status_bg }, c = { fg = p.status_fg, bg = p.status_bg } },
    terminal = { a = { fg = p.status_bg, bg = p.status_green },
      b = { fg = p.status_fg, bg = p.status_bg }, c = { fg = p.status_fg, bg = p.status_bg } },
    command = { a = { fg = p.status_bg, bg = p.status_pink },
      b = { fg = p.status_pink, bg = p.status_bg }, c = { fg = p.status_fg, bg = p.status_bg } },
  }
end

function M.git_sync()
  return { fg = M.palette.status_fg, bg = M.palette.status_git_sync_bg }
end

function M.tab_separator(win)
  local background = api.nvim_get_hl(0, { name = 'BufferLineBackground', link = false }).bg
  -- Resolve Normal in the editor even when a tool has focus.
  local editor_background = api.nvim_win_call(win, function()
    return api.nvim_get_hl(0, { name = 'Normal', link = false }).bg or M.palette.vscBack
  end)
  api.nvim_set_hl(0, 'DesktopTabSeparator', { fg = editor_background, bg = background })
end

function M.apply()
  for name, definition in pairs(M.highlights()) do api.nvim_set_hl(0, name, definition) end
end

function M.setup()
  M.apply()
  api.nvim_create_autocmd('ColorScheme', {
    group = api.nvim_create_augroup('DesktopColors', { clear = true }),
    callback = function() vim.schedule(M.apply) end,
  })
end

return M
