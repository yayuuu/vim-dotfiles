-- A scrollable document strip in the reserved winbar row, above both diff columns.
local M = { first = 1 }
local api = vim.api
local namespace = api.nvim_create_namespace("DesktopIDESharedTabs")
local function valid(win) return win and api.nvim_win_is_valid(win) end

function M.close()
  if valid(M.win) then api.nvim_win_close(M.win, true) end
  M.win, M.hits = nil, {}
end

function M.draw()
  if #api.nvim_list_uis() == 0 then return end
  if require("config.ide").is_tool_tab() then return end
  local diff = require("config.diff").active
  if not _G.nvim_bufferline then return end
  local target, position, width
  if diff and valid(diff.left) and valid(diff.right) and valid(diff.header) then
    target, position, width = diff.right, api.nvim_win_get_position(diff.header), api.nvim_win_get_width(diff.header)
  else
    local ide = require("config.ide")
    local function editor(win)
      return valid(win) and api.nvim_win_get_config(win).relative == "" and ide.is_document(api.nvim_win_get_buf(win))
        and api.nvim_win_get_tabpage(win) == api.nvim_get_current_tabpage()
        and vim.wo[win].winbar ~= ""
    end
    if editor(ide.main_editor) then target = ide.main_editor
    elseif editor(api.nvim_get_current_win()) then target = api.nvim_get_current_win()
    elseif editor(ide.last_editor) then target = ide.last_editor
    else for _, win in ipairs(api.nvim_tabpage_list_wins(0)) do if editor(win) then target = win; break end end end
    if not target then M.close(); return end
    position, width = api.nvim_win_get_position(target), api.nvim_win_get_width(target)
  end
  if diff then
  local hunks = require("config.diff").hunks()
  local buttons = "[↑ Previous] [Next ↓] "
  local entry = require("config.diff").entries[diff.buf]
  local baseline = entry.baseline == "index" and "Staged" or "HEAD"
  local label = " " .. baseline .. " → Working tree  ·  " .. #hunks .. " changes"
  while vim.fn.strdisplaywidth(label) > math.max(0, width - #buttons) do label = vim.fn.strcharpart(label, 0, vim.fn.strchars(label) - 1) end
  local button_width = vim.fn.strdisplaywidth(buttons)
  local toolbar_text = label .. string.rep(" ", math.max(0, width - vim.fn.strdisplaywidth(label) - button_width)) .. buttons
  vim.bo[diff.toolbar].modifiable = true
  api.nvim_buf_set_lines(diff.toolbar, 0, -1, false, { toolbar_text })
  vim.bo[diff.toolbar].modified = false; vim.bo[diff.toolbar].modifiable = false
  M.previous = width - button_width + 1; M.next = M.previous + vim.fn.strdisplaywidth("[↑ Previous] ")
  end
  local components = api.nvim_win_call(target, function()
    _G.nvim_bufferline() -- Update the plugin's navigation list as well.
    local items = require("bufferline.buffers").get_components(require("bufferline.state"))
    table.sort(items, require("config.tabs").compare)
    local parts = {}
    for _, item in ipairs(items) do
      -- Render the card body once; this strip owns the boundaries between cards.
      parts[#parts + 1] = { id = item.id, body = item.component(nil),
        background = require("bufferline.highlights").for_element(item).buffer }
    end
    return parts
  end)
  local groups = {}
  for _, component in ipairs(components or {}) do
    local id = component.id
    if id then
      local group = { id = id, parts = {}, width = 0 }
      for _, part in ipairs(component.body) do
        if part.text then
          local text = part.text:gsub("%%%%", "%%")
          group.parts[#group.parts + 1] = { text = text, highlight = part.highlight or component.background,
            close = part.attr and (part.attr.prefix or ""):find("handle_close", 1, true) ~= nil }
          group.width = group.width + vim.fn.strdisplaywidth(text)
        end
      end
      groups[#groups + 1] = group
    end
  end
  M.count = #groups
  local colors = require("config.colors")
  local separator = colors.tab_separator(target)
  local transparent = colors.palette.ui_background == "NONE"
  local first = math.min(math.max(1, M.first), math.max(1, #groups))
  M.first = first
  local text, spans, hits, column, byte = "", {}, {}, 0, 0
  for i = first, #groups do
    local group = groups[i]
    if column >= width then break end
    if i > first then
      if column + 1 >= width then break end
      spans[#spans + 1] = { first = byte, last = byte + #separator, hl = "DesktopTabSeparator" }
      text, column, byte = text .. separator, column + 1, byte + #separator
    end
    for _, part in ipairs(group.parts) do
      local part_text = part.text
      while part_text ~= "" and column + vim.fn.strdisplaywidth(part_text) > width do
        part_text = vim.fn.strcharpart(part_text, 0, vim.fn.strchars(part_text) - 1)
      end
      local size = vim.fn.strdisplaywidth(part_text)
      if size > 0 then
        hits[#hits + 1] = { first = column + 1, last = column + size, id = group.id, close = part.close }
        if part.highlight then spans[#spans + 1] = { first = byte, last = byte + #part_text, hl = part.highlight } end
        text, column, byte = text .. part_text, column + size, byte + #part_text
      end
    end
  end
  if text ~= "" and column < width then
    spans[#spans + 1] = { first = byte, last = byte + #separator, hl = "DesktopTabSeparator" }
    text = text .. separator
    column, byte = column + 1, byte + #separator
  end
  if transparent and column < width then
    -- Paint unused cells explicitly: the underlying strip must stay transparent
    -- so a selected card with bg=NONE can inherit the terminal background.
    local padding = string.rep(" ", width - column)
    spans[#spans + 1] = { first = byte, last = byte + #padding, hl = "BufferLineFill" }
    text = text .. padding
  end
  M.hits = hits
  if not M.buf or not api.nvim_buf_is_valid(M.buf) then
    M.buf = api.nvim_create_buf(false, true)
    vim.bo[M.buf].bufhidden = "hide"
    vim.b[M.buf].ide_editor_tabs = true
  end
  vim.bo[M.buf].modifiable = true
  api.nvim_buf_set_lines(M.buf, 0, -1, false, { text })
  api.nvim_buf_clear_namespace(M.buf, namespace, 0, -1)
  for _, span in ipairs(spans) do
    api.nvim_buf_set_extmark(M.buf, namespace, 0, span.first, { end_col = span.last, hl_group = span.hl })
  end
  vim.bo[M.buf].modified = false
  vim.bo[M.buf].modifiable = false
  local config = { relative = "editor", row = position[1], col = position[2], width = width, height = 1,
    focusable = false, mouse = true, style = "minimal", border = "none", zindex = 30 }
  if valid(M.win) then api.nvim_win_set_config(M.win, config)
  else M.win = api.nvim_open_win(M.buf, false, config) end
  vim.wo[M.win].winbar = ""
  vim.wo[M.win].winhighlight = transparent
    and "Normal:DesktopTabStrip,NormalNC:DesktopTabStrip,EndOfBuffer:DesktopTabStrip"
    or "Normal:BufferLineBackground,EndOfBuffer:BufferLineBackground"
end

function M.refresh()
  if M.pending then return end
  M.pending = true
  vim.schedule(function() M.pending = false; M.draw() end)
end

function M.setup()
  local group = api.nvim_create_augroup("DesktopIDESharedTabs", { clear = true })
  api.nvim_create_autocmd("BufWritePost", { group = group, callback = function() M.draw() end })
  api.nvim_create_autocmd({ "ColorScheme", "TabEnter", "BufEnter", "BufAdd", "BufDelete", "BufModifiedSet", "TextChanged", "TextChangedI", "DiagnosticChanged", "WinResized", "VimResized" }, {
    group = group, callback = function(event)
      if event.buf ~= M.buf and not vim.b[event.buf].ide_hscroll then M.refresh() end
    end,
  })
  local events = {}
  for _, button in ipairs({ "Left", "Right", "Middle" }) do
    for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
      for _, kind in ipairs({ "Mouse", "Drag", "Release" }) do
        events[vim.keycode("<" .. prefix .. button .. kind .. ">")] = { button = button, kind = kind }
      end
    end
  end
  local wheels = {}
  for _, name in ipairs({ "Down", "Right", "Up", "Left" }) do wheels[vim.keycode("<ScrollWheel" .. name .. ">")] =
    (name == "Down" or name == "Right") and 1 or -1 end
  vim.on_key(function(key, typed)
    if require("config.mouse_capture").blocked(key, typed) then return end
    -- A Files/terminal buffer mapping can replace key before this listener sees
    -- it. The original typed mouse event still belongs to the document strip.
    local wheel = wheels[typed] or wheels[key]
    if wheel and vim.fn.getmousepos().winid == M.win then
      M.first = math.max(1, math.min(M.count or 1, M.first + wheel))
      M.refresh(); return ""
    end
    local event = events[typed] or events[key]
    if not event then return end
    local mouse = vim.fn.getmousepos()
    -- On the global tabline Neovim may report the diff header underneath it.
    -- Leave these events to the menu's native tabline click handlers.
    if mouse.screenrow == 1 then return end
    local diff = require("config.diff").active
    if diff and mouse.winid == diff.header then
      if event.button == "Left" and event.kind == "Release" and mouse.winrow > 1 and mouse.wincol >= M.previous then
        vim.schedule(function() require("config.diff").jump(mouse.wincol >= M.next and 1 or -1) end)
      end
      return ""
    end
    if mouse.winid ~= M.win then return end
    -- Act on middle press: legacy terminal mouse protocols can report a
    -- generic release without retaining which button was released.
    if (event.button == "Middle" and event.kind == "Mouse") or (event.button ~= "Middle" and event.kind == "Release") then
      for _, hit in ipairs(M.hits or {}) do
        if mouse.wincol >= hit.first and mouse.wincol <= hit.last then
          vim.schedule(function()
            local ide = require("config.ide")
            if event.button == "Middle" or (event.button == "Left" and hit.close) then ide.close_buffer(hit.id)
            elseif event.button == "Right" then ide.tab_menu(hit.id)
            else
              ide.open_file(nil, hit.id)
              if vim.bo.modifiable and not vim.bo.readonly
                and (vim.bo.buftype == "" or vim.b.ide_diff_file) then vim.cmd("startinsert") end
            end
            M.refresh()
          end)
          break
        end
      end
    end
    return ""
  end, namespace)
end
return M
