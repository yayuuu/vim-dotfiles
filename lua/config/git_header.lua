-- The Git title and commit input stay above the scrolling status rows.
local M = { windows = {}, rows = 4 }
local api = vim.api
local function valid(win) return win and api.nvim_win_is_valid(win) end

function M.height(win)
  return valid(win) and (vim.b[api.nvim_win_get_buf(win)].ide_fixed_header or 0) or 0
end

function M.cleanup()
  for source, header in pairs(M.windows) do
    if not valid(source) or api.nvim_win_get_buf(source) ~= header.source_buf then
      if valid(header.win) then api.nvim_win_close(header.win, true) end
      M.windows[source] = nil
    end
  end
end

function M.sync(state)
  M.cleanup()
  local source = state.winid
  if not valid(source) or not state.tree or api.nvim_win_get_buf(source) ~= state.bufnr then return end
  local width = api.nvim_win_get_width(source)
  local config = { relative = "win", win = source, row = 0, col = 0,
    width = width, height = M.rows, style = "minimal", border = "none",
    focusable = false, mouse = true, zindex = 22, noautocmd = true }
  local header = M.windows[source]
  if not header or not valid(header.win) then
    local buf = api.nvim_create_buf(false, true)
    vim.bo[buf].bufhidden = "wipe"; vim.bo[buf].filetype = "ide_git_header"
    vim.b[buf].ide_panel_header = true
    header = { buf = buf, win = api.nvim_open_win(buf, false, config), source_buf = state.bufnr }
    M.windows[source] = header
    vim.wo[header.win].winbar = ""
    vim.wo[header.win].winhighlight = "Normal:NeoTreeNormal,EndOfBuffer:NeoTreeNormal"
  else api.nvim_win_set_config(header.win, config) end
  header.state = state
  vim.b[state.bufnr].ide_fixed_header = M.rows
  local node = state.tree:get_node(state.path)
  local text = " "
  if node then
    for _, chunk in ipairs(require("config.git").directory({}, node, state, width - 1)) do
      text = text .. (chunk.text or "")
    end
  end
  vim.bo[header.buf].modifiable = true
  local input = require("config.git").inputs[state.path]
  if not input or not valid(input.win) then require("config.git").input(state) end
  api.nvim_buf_set_lines(header.buf, 0, -1, false, { text, "", "", "" })
  local ns = api.nvim_create_namespace("DesktopGitHeader")
  api.nvim_buf_clear_namespace(header.buf, ns, 0, -1)
  api.nvim_buf_set_extmark(header.buf, ns, 0, 0, { end_col = #text, hl_group = "NeoTreeRootName" })
  vim.bo[header.buf].modified = false; vim.bo[header.buf].modifiable = false
end

function M.setup()
  local group = api.nvim_create_augroup("DesktopGitHeader", { clear = true })
  api.nvim_create_autocmd({ "WinClosed", "BufWinEnter" }, { group = group,
    callback = function() vim.schedule(function()
      M.cleanup()
      for _, header in pairs(M.windows) do M.sync(header.state) end
    end) end })
  local events = {}
  for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
    events[vim.keycode("<" .. prefix .. "LeftMouse>")] = "press"
    events[vim.keycode("<" .. prefix .. "LeftRelease>")] = "release"
  end
  events[vim.keycode("<ScrollWheelUp>")] = "wheel"
  events[vim.keycode("<ScrollWheelDown>")] = "wheel"
  vim.on_key(function(key, typed)
    if require("config.mouse_capture").blocked(key, typed) then return end
    local kind = events[typed] or events[key]
    if not kind then return end
    local mouse = vim.fn.getmousepos()
    for source, header in pairs(M.windows) do
      if mouse.winid == header.win then
        if kind == "release" and mouse.winrow == 1
          and mouse.wincol > api.nvim_win_get_width(source) - 3 then
          vim.schedule(function()
            if not valid(source) then return end
            vim.cmd("stopinsert")
            api.nvim_set_current_win(source)
            require("config.git").refresh()
          end)
        end
        return ""
      end
    end
  end, api.nvim_create_namespace("DesktopGitHeaderMouse"))
end

return M
