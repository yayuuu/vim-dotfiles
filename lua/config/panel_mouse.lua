-- Distinguish rendered rows from clicks that Neovim clamps to the last item.
local M = {}
local api = vim.api

function M.row(mouse, win)
  win = win or mouse.winid
  if not win or win == 0 or not api.nvim_win_is_valid(win) or mouse.winid ~= win or mouse.line < 1 then return end
  local position = vim.fn.screenpos(win, mouse.line, math.max(1, mouse.column))
  if position.row == mouse.screenrow then return mouse.line end
end

function M.statusline_click()
  return not require("config.mouse_capture").active()
    and (vim.o.laststatus ~= 3 or vim.fn.getmousepos().screenrow == vim.o.lines - vim.o.cmdheight)
end

local function horizontal_divider(mouse)
  local win = mouse.winid
  if vim.o.laststatus ~= 3 or win == 0 or not api.nvim_win_is_valid(win)
    or api.nvim_win_get_config(win).relative ~= "" then return end
  local position = api.nvim_win_get_position(win)
  if mouse.screenrow ~= position[1] + api.nvim_win_get_height(win) + 1
    or mouse.screencol <= position[2] or mouse.screencol > position[2] + api.nvim_win_get_width(win) then return end
  -- The real global status bar has no native window directly below it.
  for _, below in ipairs(api.nvim_tabpage_list_wins(0)) do
    if api.nvim_win_get_config(below).relative == "" then
      local p = api.nvim_win_get_position(below)
      if p[1] == mouse.screenrow and mouse.screencol > p[2]
        and mouse.screencol <= p[2] + api.nvim_win_get_width(below) then return win end
    end
  end
end

local function resize_divider(drag, row)
  drag.latest = row
  if drag.pending then return end
  drag.pending = true
  vim.schedule(function()
    drag.pending = false
    if drag.cancelled or not api.nvim_win_is_valid(drag.win)
      or api.nvim_win_get_tabpage(drag.win) ~= api.nvim_get_current_tabpage() then return end
    local offset = drag.height + drag.latest - drag.row - api.nvim_win_get_height(drag.win)
    if offset ~= 0 then vim.fn.win_move_statusline(drag.win, offset) end
  end)
end

function M.setup()
  local capture = require("config.mouse_capture")
  local events = {}
  for _, modifier in ipairs({ "", "S-", "C-", "A-" }) do
    for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
      for _, kind in ipairs({ "Mouse", "Drag", "Release" }) do
        events[vim.keycode("<" .. modifier .. prefix .. "Left" .. kind .. ">")] = kind
      end
    end
  end
  local blank, resize
  vim.on_key(function(key, typed)
    local kind = events[typed] or events[key]
    if not kind then return end
    if kind == "Mouse" and resize then
      resize.cancelled = true
      capture.cancel(resize)
      resize = nil
    elseif resize then
      resize_divider(resize, vim.fn.getmousepos().screenrow)
      if kind == "Release" then capture.release(resize); resize = nil end
      return ""
    end
    if blank and kind ~= "Mouse" then
      if kind == "Release" then capture.release(blank); blank = nil end
      return ""
    end
    if kind ~= "Mouse" then return end
    if blank then capture.cancel(blank); blank = nil end
    if capture.active() then return end
    local mouse = vim.fn.getmousepos()
    local menus = package.loaded["menu.state"]
    if menus and #menus.bufids > 0 then
      local inside = false
      for _, buf in ipairs(menus.bufids) do
        for _, w in ipairs(vim.fn.win_findbuf(buf)) do
          local p = api.nvim_win_get_position(w)
          if mouse.screenrow >= p[1] and mouse.screenrow <= p[1] + api.nvim_win_get_height(w) + 1
            and mouse.screencol >= p[2] and mouse.screencol <= p[2] + api.nvim_win_get_width(w) + 1 then inside = true end
        end
      end
      -- The menu bar's own buttons still switch between dropdowns.
      local bar_button = mouse.screenrow == 1 and mouse.screencol <= require("config.ide").menu_width()
      if not inside and not bar_button then
        blank = {}; capture.claim(blank)
        vim.schedule(function() require("config.ide").close_menu() end)
        return ""
      end
    end
    local popups = package.loaded["config.popup_ui"]
    if popups and popups.button_at_mouse(mouse) then return end
    local divider = horizontal_divider(mouse)
    if divider then
      -- Native global-statusline click regions also cover horizontal split
      -- separators. Own the gesture and move the actual native boundary.
      resize = { win = divider, row = mouse.screenrow, height = api.nvim_win_get_height(divider) }
      capture.claim(resize)
      return ""
    end
    local win = mouse.winid
    if win == 0 or not api.nvim_win_is_valid(win) then return end
    local buf, config = api.nvim_win_get_buf(win), api.nvim_win_get_config(win)
    -- Neovim reports a native vertical separator as belonging to the window
    -- on its left, with line=0 and wincol=width+1. It is not blank list space.
    local position = api.nvim_win_get_position(win)
    if config.relative == "" and (mouse.screencol <= position[2]
      or mouse.screencol > position[2] + api.nvim_win_get_width(win)) then return end
    -- Editors and terminal/console bodies accept cursor/input clicks anywhere.
    if vim.bo[buf].buftype == "terminal" or vim.bo[buf].buftype == "prompt" or vim.b[buf].ide_git_input or vim.b[buf].ide_panel_header
      or vim.bo[buf].filetype == "dap-repl" or vim.b[buf].ide_hscroll or vim.b[buf].ide_vscroll
      or vim.b[buf].ide_editor_tabs or vim.b[buf].ide_diff_before or vim.b[buf].ide_diff_file
      or (config.relative == "" and require("config.ide").is_document(buf)) then return end
    local top = position[1] + 1 + (vim.wo[win].winbar ~= "" and 1 or 0)
    -- Preserve titles, tab selectors, borders, and resize separators.
    if mouse.screenrow < top or mouse.screenrow >= top + vim.fn.getwininfo(win)[1].height then return end
    local row = M.row(mouse, win)
    if vim.b[buf].ide_replace and require("config.search").input_at_mouse(mouse) then return end
    local menu = vim.bo[buf].filetype == "NvMenu" and menus and menus.bufs[buf]
    if row and menu and menu.items and menu.items[row] then return end
    local text = row and api.nvim_buf_get_lines(buf, row - 1, row, false)[1]
    if row and text and vim.trim(text) ~= "" then return end
    blank = {}
    capture.claim(blank)
    return ""
  end, api.nvim_create_namespace("DesktopPanelBlankClick"))
end

return M
