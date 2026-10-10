-- Put a mouse close button on the border without taking space from the popup.
local M = { buttons = {}, owners = {} }
local api = vim.api
local namespace = api.nvim_create_namespace("DesktopPopupClose")
local function valid(win) return win and api.nvim_win_is_valid(win) end

function M.close(win)
  if not valid(win) then return end
  if vim.b[api.nvim_win_get_buf(win)].ide_git_input then return end
  if M.owners[win] then M.owners[win](); return end
  local lazy = package.loaded["lazy.view"]
  if lazy and lazy.visible() and lazy.view.win == win then lazy.view:close(); return end
  if vim.bo[api.nvim_win_get_buf(win)].filetype == "noice" then
    if vim.fn.getcmdtype() ~= "" then api.nvim_input("<C-c>") else require("noice").cmd("dismiss") end
    return
  end
  api.nvim_win_close(win, false)
end

function M.register(win, close)
  if not valid(win) then return end
  M.owners[win] = close
  M.schedule()
end

function M.refresh()
  M.scanning = true
  for parent, button in pairs(M.buttons) do
    if not valid(parent) or vim.b[api.nvim_win_get_buf(parent)].ide_git_input then
      if valid(button.win) then api.nvim_win_close(button.win, true) end
      M.buttons[parent], M.owners[parent] = nil, nil
    end
  end
  for win in pairs(M.owners) do if not valid(win) then M.owners[win] = nil end end
  for _, win in ipairs(api.nvim_tabpage_list_wins(0)) do
    local config = api.nvim_win_get_config(win)
    local buf = api.nvim_win_get_buf(win)
    local ft = vim.bo[buf].filetype
    local layout_window = vim.w[win].snacks_layout or ft == "snacks_layout_box"
    local popup = M.owners[win] or (config.relative == "editor" and (config.focusable or ft == "noice")
      and ft ~= "NvMenu" and ft ~= "VoltWindow" and not layout_window)
    if popup and not vim.b[buf].ide_git_input and config.relative ~= "" and not config.external and not config.hide then
      local borderless = not config.border or config.border == "none"
      -- Snacks already positions its panes and borders inside the layout root.
      -- Adding a root border afterwards shifts every pane and duplicates edges.
      -- Noice/Nui can render padding and borders in a separate window. Its
      -- borderless content is already framed; another border moves the text.
      if borderless and not layout_window and ft ~= "noice" then
        api.nvim_win_set_config(win, { border = "rounded" })
      end
      local row = borderless and (layout_window or ft == "noice") and 0 or -1
      local col = math.max(0, config.width - (row == 0 and 4 or 3))
      local button = M.buttons[win]
      if not button or not valid(button.win) then
        local close_buf = api.nvim_create_buf(false, true)
        vim.bo[close_buf].bufhidden = "wipe"
        api.nvim_buf_set_lines(close_buf, 0, -1, false, { " × " })
        vim.bo[close_buf].modifiable = false
        local close_win = api.nvim_open_win(close_buf, false, { relative = "win", win = win,
          row = row, col = col, width = 3, height = 1,
          focusable = false, mouse = true, style = "minimal", border = "none",
          zindex = math.min(32000, (config.zindex or 50) + 5), noautocmd = true })
        vim.wo[close_win].winbar = ""
        vim.wo[close_win].winhighlight = "Normal:FloatBorder,EndOfBuffer:FloatBorder"
        api.nvim_buf_set_extmark(close_buf, namespace, 0, 1, { end_col = 3, hl_group = "DiagnosticError" })
        button = { win = close_win, width = config.width, row = row, col = col }
        M.buttons[win] = button
      elseif button.width ~= config.width or button.row ~= row or button.col ~= col then
        api.nvim_win_set_config(button.win, { relative = "win", win = win,
          row = row, col = col })
        button.width, button.row, button.col = config.width, row, col
      end
    end
  end
  M.scanning = false
end

function M.schedule()
  if M.pending or M.scanning then return end
  M.pending = true
  vim.schedule(function() M.pending = false; M.refresh() end)
end

function M.setup()
  local group = api.nvim_create_augroup("DesktopPopupUI", { clear = true })
  api.nvim_create_autocmd({ "WinNew", "WinEnter", "BufWinEnter", "FileType", "WinClosed", "WinResized", "VimResized" },
    { group = group, callback = M.schedule })
  api.nvim_create_autocmd("FileType", { group = group, pattern = "lazy", callback = function(event)
    vim.keymap.set("n", "<Esc>", function() M.close(api.nvim_get_current_win()) end,
      { buffer = event.buf, silent = true, desc = "Close popup" })
  end })
  local mouse_keys = {}
  for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
    mouse_keys[vim.keycode("<" .. prefix .. "LeftMouse>")] = false
    mouse_keys[vim.keycode("<" .. prefix .. "LeftRelease>")] = true
  end
  vim.on_key(function(key, typed)
    if require("config.mouse_capture").blocked(key, typed) then return end
    if mouse_keys[typed] ~= nil then key = typed end
    if mouse_keys[key] == nil then return end
    local mouse = vim.fn.getmousepos()
    for parent, button in pairs(M.buttons) do
      local hit = mouse.winid == button.win
      -- Command-line mode reports the underlying editor for floating clicks.
      if not hit and valid(button.win) and vim.fn.getcmdtype() ~= "" then
        local position = api.nvim_win_get_position(button.win)
        hit = mouse.screenrow == position[1] + 1 and mouse.screencol >= position[2] + 1
          and mouse.screencol <= position[2] + 3
      end
      if hit then
        if mouse_keys[key] then vim.schedule(function() M.close(parent) end) end
        return ""
      end
    end
  end, namespace)
end

return M
