-- Vertical panel scrollbars; editor windows use their minimaps instead.
local M = { sources = {}, buffers = {} }
local api = vim.api
local capture = require("config.mouse_capture")
local namespace = api.nvim_create_namespace("DesktopVerticalScroll")
local function valid(win) return win and api.nvim_win_is_valid(win) end

local function eligible(win)
  if not valid(win) or api.nvim_win_get_tabpage(win) ~= api.nvim_get_current_tabpage() then return false end
  local config, buf = api.nvim_win_get_config(win), api.nvim_win_get_buf(win)
  local ft = vim.bo[buf].filetype
  if config.external or config.hide or vim.wo[win].diff
    or ft == "snacks_layout_box" or ft == "snacks_win_backdrop" or ft == "neominimap"
    or vim.b[buf].ide_hscroll or vim.b[buf].ide_vscroll or vim.b[buf].ide_editor_tabs or vim.b[buf].ide_panel_header
    or vim.b[buf].ide_diff_before or vim.b[buf].ide_diff_file then return false end
  -- Border buttons and other noninteractive overlays are not content panels.
  if config.relative ~= "" and not config.focusable and not vim.w[win].snacks_picker_preview then return false end
  return config.relative ~= "" or not require("config.ide").is_document(buf)
end

function M.width(win)
  local state = M.sources[win]
  return state and state.bar and state.bar.inside and 1 or 0
end

local function close_bar(state)
  if state.bar and valid(state.bar.win) then api.nvim_win_close(state.bar.win, true) end
  state.bar = nil
end

function M.detach(win)
  if not win then return end
  local state = M.sources[win]
  if state then close_bar(state) end
  M.sources[win] = nil
  if M.drag and M.drag.source == win then capture.release(M.drag); M.drag = nil end
end

local function bounds(win)
  local pinned = require("config.git_header").height(win)
  local height = math.max(1, require("config.hscroll").content_height(win) - pinned)
  local state = M.sources[win]
  if state and state.list then
    local total = state.list:count()
    local maximum = math.max(0, total - height)
    local offset = state.list.top - 1
    if state.list.reverse then offset = maximum - offset end
    return math.max(0, math.min(maximum, offset)), maximum, height, total
  end
  local total = math.max(0, api.nvim_win_text_height(win, {}).all - pinned)
  local view = api.nvim_win_call(win, vim.fn.winsaveview)
  local offset = api.nvim_win_text_height(win, { end_row = view.topline - 1, end_vcol = view.skipcol }).all - view.topfill
  local maximum = math.max(0, total - height)
  return math.max(0, math.min(maximum, offset)), maximum, height, total
end

function M.set(win, offset)
  if not valid(win) then return end
  local current, maximum = bounds(win)
  offset = math.floor(math.max(0, math.min(maximum, offset)))
  local delta = offset - current
  if delta ~= 0 then
    local state = M.sources[win]
    if state and state.list then
      -- Picker lists render only the visible items into their buffer.
      -- Scroll their item model instead of scrolling that temporary buffer.
      state.list:scroll(delta)
      M.refresh()
      return
    end
    if vim.bo[api.nvim_win_get_buf(win)].buftype == "terminal"
      or (not vim.wo[win].wrap and api.nvim_win_text_height(win, {}).all == api.nvim_buf_line_count(api.nvim_win_get_buf(win))) then
      -- Flat panel/terminal buffers have one row per screen line. Move their
      -- view directly: :normal can insert text into a readonly tree while the
      -- focused editor is in Select mode.
      api.nvim_win_call(win, function()
        local view = vim.fn.winsaveview()
        view.topline, view.topfill, view.skipcol = offset + 1, 0, 0
        local height = require("config.hscroll").content_height(win)
        local margin = math.min(vim.wo[win].scrolloff, math.floor((height - 1) / 2))
        view.lnum = math.max(view.topline + margin, math.min(view.topline + height - 1 - margin, view.lnum))
        vim.fn.winrestview(view)
      end)
      M.refresh()
      return
    end
    -- Native screen-line scrolling handles wrapped text and virtual lines.
    -- win_call restores focus to the picker input after moving the preview.
    api.nvim_win_call(win, function()
      vim.cmd.normal({ args = { tostring(math.abs(delta)) .. vim.keycode(delta > 0 and "<C-e>" or "<C-y>") }, bang = true })
    end)
  end
  M.refresh()
end

local function draw(win, state)
  local buf = api.nvim_win_get_buf(win)
  if not M.buffers[buf] then
    M.buffers[buf] = true
    api.nvim_buf_attach(buf, false, {
      on_lines = function() M.refresh(); require("config.hscroll").refresh() end,
      on_detach = function() M.buffers[buf] = nil end,
    })
  end
  local offset, maximum, height, total = bounds(win)
  if maximum == 0 then close_bar(state); return end
  local config = api.nvim_win_get_config(win)
  local border = config.border
  local bordered = config.relative ~= "" and border and border ~= "none"
  if type(border) == "table" then
    local right = border[4]
    bordered = right and right ~= "" and (type(right) ~= "table" or right[1] ~= "")
  end
  local inside = not bordered
  local bar_config = { relative = "win", win = win, row = require("config.git_header").height(win), col = api.nvim_win_get_width(win) - (inside and 1 or 0),
    width = 1, height = height, focusable = false, mouse = true, style = "minimal", border = "none",
    -- Native panel overlays sit below ordinary dialogs (default zindex 50).
    -- A floating panel's own bar must follow that panel's layer instead.
    zindex = config.relative == "" and 21 or math.min(32000, (config.zindex or 50) + 5), noautocmd = true }
  local bar = state.bar
  if not bar or not valid(bar.win) then
    local barbuf = api.nvim_create_buf(false, true)
    vim.bo[barbuf].bufhidden = "wipe"; vim.bo[barbuf].filetype = "ide_vscroll"
    vim.b[barbuf].ide_vscroll = true
    bar = { buf = barbuf, win = api.nvim_open_win(barbuf, false, bar_config) }
    state.bar = bar
    vim.wo[bar.win].winbar = ""
    vim.wo[bar.win].winhighlight = "Normal:DesktopScrollbarTrack,EndOfBuffer:DesktopScrollbarTrack"
  else api.nvim_win_set_config(bar.win, bar_config) end
  bar.inside = inside
  bar.thumb = math.max(1, math.floor(height * height / total))
  bar.span, bar.maximum = height - bar.thumb, maximum
  bar.start = math.floor(offset / maximum * bar.span)
  local lines = {}
  for row = 0, height - 1 do lines[#lines + 1] = "█" end
  vim.bo[bar.buf].modifiable = true
  api.nvim_buf_set_lines(bar.buf, 0, -1, false, lines)
  api.nvim_buf_clear_namespace(bar.buf, namespace, 0, -1)
  for row = bar.start, bar.start + bar.thumb - 1 do
    api.nvim_buf_set_extmark(bar.buf, namespace, row, 0, { end_col = #"█", hl_group = "DesktopScrollbarThumb" })
  end
  vim.bo[bar.buf].modified = false; vim.bo[bar.buf].modifiable = false
end

function M.refresh()
  if M.pending or M.running then return end
  M.pending = true
  vim.schedule(function()
    M.pending, M.running = false, true
    local ok, err = pcall(function()
      local lists = {}
      local picker = package.loaded["snacks.picker"]
      if picker then
        for _, p in ipairs(picker.get()) do
          if p.shown and not p.closed and p.list and p.list.win:valid() then lists[p.list.win.win] = p.list end
        end
      end
      local resized = false
      for _, win in ipairs(api.nvim_tabpage_list_wins(0)) do
        if eligible(win) then
          local buf = api.nvim_win_get_buf(win)
          if not M.buffers[buf] then
            M.buffers[buf] = true
            api.nvim_buf_attach(buf, false, {
              on_lines = function() M.refresh(); require("config.hscroll").refresh() end,
              on_detach = function() M.buffers[buf] = nil end,
            })
          end
          M.sources[win] = M.sources[win] or {}
          M.sources[win].list = lists[win]
        end
      end
      for win, state in pairs(M.sources) do
        local old_width = M.width(win)
        if eligible(win) then
          draw(win, state)
          if not state.bar and not state.manual then M.sources[win] = nil end
        else M.detach(win) end
        local changed = old_width ~= M.width(win)
        resized = resized or changed
        if changed and valid(win) and vim.bo[api.nvim_win_get_buf(win)].filetype == "neo-tree" then
          local manager = package.loaded["neo-tree.sources.manager"]
          local tree = manager and manager.get_state_for_window(win)
          if tree and tree.name == "git_status" and tree.tree then
            require("config.git").header(tree)
          end
        end
      end
      if resized then require("config.hscroll").refresh() end
    end)
    M.running = false
    if not ok then vim.notify("Vertical scrollbar: " .. tostring(err), vim.log.levels.ERROR) end
  end)
end

function M.attach(win)
  if not valid(win) then return end
  if not M.ready then M.setup() end
  M.sources[win] = M.sources[win] or {}
  M.sources[win].manual = true
  M.refresh()
end

function M.setup()
  if M.ready then return end
  M.ready = true
  local group = api.nvim_create_augroup("DesktopVerticalScroll", { clear = true })
  api.nvim_create_autocmd({ "WinNew", "WinScrolled", "WinResized", "VimResized", "WinClosed", "TabEnter", "FileType", "BufWinEnter", "TextChanged", "TextChangedI" },
    { group = group, callback = M.refresh })
  local events = {}
  for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
    for _, kind in ipairs({ "Mouse", "Drag", "Release" }) do events[vim.keycode("<" .. prefix .. "Left" .. kind .. ">")] = kind end
  end
  local wheels = { [vim.keycode("<ScrollWheelUp>")] = -3, [vim.keycode("<ScrollWheelDown>")] = 3 }
  vim.on_key(function(key, typed)
    local kind, wheel = events[typed] or events[key], wheels[typed] or wheels[key]
    if not kind and not wheel then return end
    local mouse = vim.fn.getmousepos()
    if wheel and valid(mouse.winid) and vim.bo[api.nvim_win_get_buf(mouse.winid)].buftype == "terminal" then
      local source = mouse.winid
      if vim.fn.mode() == "t" then
        local enabled = require("config.terminals").mouse_enabled(api.nvim_win_get_buf(source))
        -- Let Neovim encode events for an application that requested the mouse.
        -- For unmanaged terminals retain Neovim's own input routing as well.
        if enabled ~= false then return end
      end
      local state = M.sources[source]
      if not state or not state.bar or not valid(state.bar.win) then return "" end
      if vim.fn.mode() == "t" then api.nvim_feedkeys(vim.keycode("<C-\\><C-n>"), "ni", false) end
      vim.schedule(function() local offset = bounds(source); M.set(source, offset + wheel) end)
      return ""
    end
    if kind == "Mouse" then
      -- The host may miss a release outside its window. The next press must
      -- release the old capture before starting another independent gesture.
      capture.cancel(M.drag)
      M.drag = nil
    end
    for source, state in pairs(M.sources) do
      local bar = state.bar
      local hit, position = bar and mouse.winid == bar.win, bar and valid(bar.win) and api.nvim_win_get_position(bar.win)
      -- Floating border clicks can report the underlying document. Resolve the
      -- visible bar by screen coordinates too, without intercepting a higher
      -- popup such as a notification displayed over it.
      if not hit and position then
        local hovered = valid(mouse.winid) and api.nvim_win_get_config(mouse.winid)
        local zindex = api.nvim_win_get_config(bar.win).zindex
        hit = (not hovered or (hovered.zindex or 0) <= zindex)
          and mouse.screencol == position[2] + 1
          and mouse.screenrow > position[1] and mouse.screenrow <= position[1] + api.nvim_win_get_height(bar.win)
      end
      if hit then
        if vim.fn.mode() == "t" and vim.bo[api.nvim_win_get_buf(source)].buftype == "terminal" then
          -- Scrollback must leave live input, which otherwise follows the
          -- shell cursor on redraw. Never remap Ctrl+N to our New file action.
          api.nvim_feedkeys(vim.keycode("<C-\\><C-n>"), "ni", false)
        end
        if wheel then
          vim.schedule(function() local offset = bounds(source); M.set(source, offset + wheel) end)
          return ""
        end
        if kind == "Mouse" then
          local row = mouse.screenrow - position[1] - 1
          M.drag = { source = source, bar = bar,
            grab = row >= bar.start and row < bar.start + bar.thumb and row - bar.start or math.floor(bar.thumb / 2) }
          capture.claim(M.drag)
        end
        break
      end
    end
    local drag = M.drag
    if not drag or not kind then return end
    if valid(drag.bar.win) then
      local row = mouse.screenrow - api.nvim_win_get_position(drag.bar.win)[1] - 1
      local offset = (row - drag.grab) / math.max(1, drag.bar.span) * drag.bar.maximum
      vim.schedule(function() M.set(drag.source, offset) end)
    end
    if kind == "Release" then capture.release(drag); M.drag = nil end
    return ""
  end, namespace)
  M.refresh()
end

return M
