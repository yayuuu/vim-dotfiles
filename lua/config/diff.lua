-- A diff is one buffer tab with two editor windows. The editable buffer mirrors
-- the real file, so switching back to its ordinary tab keeps unsaved changes.
local M = { entries = {}, paths = {} }
local function valid(buf) return buf and vim.api.nvim_buf_is_valid(buf) end
local function winvalid(win) return win and vim.api.nvim_win_is_valid(win) end

local function copy(from, to)
  if not valid(from) or not valid(to) then return end
  local lines = vim.api.nvim_buf_get_lines(from, 0, -1, false)
  if not vim.deep_equal(lines, vim.api.nvim_buf_get_lines(to, 0, -1, false)) then
    vim.api.nvim_buf_set_lines(to, 0, -1, false, lines)
  end
  vim.bo[to].endofline = vim.bo[from].endofline
  vim.bo[to].modified = vim.bo[from].modified
end

function M.sync(entry, from)
  if not entry or entry.busy then return end
  entry.busy = true
  copy(from or entry.buf, from == entry.filebuf and entry.buf or entry.filebuf)
  entry.busy = false
end

function M.hide_tabs()
  M.leave()
  for buf in pairs(M.entries) do
    if valid(buf) then vim.bo[buf].buflisted = false end
  end
end

local function attach(entry, buf)
  vim.api.nvim_buf_attach(buf, false, { on_lines = function()
    if entry.removed then return true end
    if entry.busy then return end
    entry.pending = buf
    vim.schedule(function()
      if entry.pending ~= buf then return end
      entry.pending = nil
      M.sync(entry, buf)
    end)
  end })
end

function M.flush()
  for _, entry in pairs(M.entries) do
    if entry.pending then
      local from = entry.pending
      entry.pending = nil
      M.sync(entry, from)
    end
  end
end

function M.leave()
  M.flush()
  local active = M.active
  if not active then return end
  require("config.editor_tabs").close()
  M.busy = true
  M.active = nil
  if package.loaded["config.hscroll"] then
    require("config.hscroll").close(active.left)
    require("config.hscroll").close(active.right)
  end
  if winvalid(active.header) then vim.api.nvim_win_close(active.header, true) end
  if winvalid(active.right) then
    vim.api.nvim_win_call(active.right, function() vim.cmd("diffoff") end)
    for option, value in pairs(active.options) do vim.wo[active.right][option] = value end
    vim.wo[active.right].winbar = require("config.ide").winbar()
  end
  if winvalid(active.left) then
    -- Closing a window alone leaves its hidden buffer in the tab's native
    -- diff set. Explicitly unregister HEAD before opening another comparison.
    vim.api.nvim_win_call(active.left, function() vim.cmd("diffoff") end)
    vim.api.nvim_win_close(active.left, true)
  end
  if winvalid(active.right) then
    vim.api.nvim_set_current_win(active.right)
    require("config.ide").last_editor = active.right
  end
  M.busy = false
  require("config.layout").reflow()
end

function M.show(buf)
  local entry = M.entries[buf]
  if not entry or not valid(buf) or M.busy then return end
  if M.active and M.active.buf == buf and winvalid(M.active.left) and winvalid(M.active.right) then
    vim.api.nvim_set_current_win(M.active.right)
    require("config.tabs").activate(buf)
    require("config.hscroll").refresh()
    return
  end
  M.leave()
  M.flush()
  M.sync(entry, entry.filebuf)
  vim.bo[buf].buflisted = true
  local ide = require("config.ide")
  local right = ide.editor_window()
  M.busy = true
  vim.cmd("stopinsert")
  vim.api.nvim_set_current_win(right)
  local options = { wrap = vim.wo[right].wrap, foldenable = vim.wo[right].foldenable }
  vim.api.nvim_win_set_buf(right, buf)
  vim.cmd("aboveleft 1split")
  local header = vim.api.nvim_get_current_win()
  local toolbar = vim.api.nvim_create_buf(false, true)
  vim.bo[toolbar].bufhidden = "wipe"
  vim.bo[toolbar].filetype = "ide_diff_toolbar"
  vim.api.nvim_win_set_buf(header, toolbar)
  vim.wo[header].number = false; vim.wo[header].relativenumber = false
  vim.wo[header].signcolumn = "no"; vim.wo[header].statuscolumn = ""
  vim.wo[header].winfixheight = true; vim.wo[header].winbar = " "
  vim.api.nvim_set_current_win(right)
  vim.cmd("leftabove vsplit")
  local left = vim.api.nvim_get_current_win()
  vim.api.nvim_win_set_buf(left, entry.before)
  M.active = { left = left, right = right, header = header, toolbar = toolbar, buf = buf, options = options }
  for _, win in ipairs({ left, right }) do
    vim.api.nvim_win_call(win, function()
      vim.cmd("diffthis")
      vim.wo.wrap = false
      vim.wo.foldenable = false
    end)
  end
  vim.wo[left].winbar = ""
  -- In native diff mode DiffAdd means a line unique to either side. A line
  -- unique to HEAD is a deletion, so use red in the left window.
  vim.wo[left].winhighlight = "DiffAdd:DesktopDiffRemoved,DiffDelete:DesktopDiffAddedGap"
  vim.wo[right].winbar = ""
  vim.opt.scrollopt:append("hor")
  vim.api.nvim_set_current_win(right)
  ide.last_editor = right
  M.busy = false
  ide.discard_empty_buffers()
  require("config.tabs").activate(buf)
  require("config.layout").reflow()
  vim.cmd("diffupdate")
  vim.cmd("redrawstatus")
  require("config.editor_tabs").refresh()
  require("config.hscroll").refresh()
end

function M.hunks(buf)
  local entry = M.entries[buf or (M.active and M.active.buf)]
  if not entry or not valid(entry.before) or not valid(entry.buf) then return {} end
  local oldtick, newtick = vim.api.nvim_buf_get_changedtick(entry.before), vim.api.nvim_buf_get_changedtick(entry.buf)
  if entry.hunk_cache and entry.oldtick == oldtick and entry.newtick == newtick then return entry.hunk_cache end
  local old = table.concat(vim.api.nvim_buf_get_lines(entry.before, 0, -1, false), "\n") .. "\n"
  local new = table.concat(vim.api.nvim_buf_get_lines(entry.buf, 0, -1, false), "\n") .. "\n"
  local diff = vim.text and vim.text.diff or vim.diff
  entry.hunk_cache = diff(old, new, { result_type = "indices", algorithm = "histogram", linematch = 60 })
  entry.oldtick, entry.newtick = oldtick, newtick
  return entry.hunk_cache
end

function M.jump(direction)
  if not M.active or not winvalid(M.active.right) then return end
  local win, hunks = M.active.right, M.hunks()
  if #hunks == 0 then return end
  local line = vim.api.nvim_win_get_cursor(win)[1]
  local target
  if direction > 0 then
    for _, h in ipairs(hunks) do if math.max(1, h[3]) > line then target = h[3]; break end end
    target = target or hunks[1][3]
  else
    for i = #hunks, 1, -1 do if math.max(1, hunks[i][3]) < line then target = hunks[i][3]; break end end
    target = target or hunks[#hunks][3]
  end
  vim.cmd("stopinsert")
  vim.api.nvim_set_current_win(win)
  vim.api.nvim_win_set_cursor(win, { math.max(1, math.min(target, vim.api.nvim_buf_line_count(M.active.buf))), 0 })
  vim.cmd("normal! zz")
  vim.cmd("syncbind")
end

function M.open(path)
  path = vim.fs.normalize(vim.fn.fnamemodify(path, ":p"))
  local root = vim.system({ "git", "-C", vim.fn.fnamemodify(path, ":h"), "rev-parse", "--show-toplevel" }, { text = true }):wait()
  if root.code ~= 0 then vim.notify("This file is not in a Git repository", vim.log.levels.WARN); return end
  local relative = path:sub(#vim.trim(root.stdout) + 2)
  local baseline = vim.system({ "git", "-C", vim.trim(root.stdout), "show", "HEAD:" .. relative }, { text = true }):wait()
  -- Missing HEAD entry is normal for added/untracked files. Other errors are
  -- reported instead of silently presenting a fabricated empty baseline.
  if baseline.code ~= 0 then
    local exists = vim.system({ "git", "-C", vim.trim(root.stdout), "cat-file", "-e", "HEAD" }):wait()
    if exists.code == 0 then
      -- Inspect the tree instead of matching localized Git error messages.
      local entry = vim.system({ "git", "--literal-pathspecs", "-C", vim.trim(root.stdout),
        "ls-tree", "-z", "HEAD", "--", relative }, { text = true }):wait()
      if entry.code ~= 0 or entry.stdout ~= "" then
        vim.notify(baseline.stderr or "Cannot read Git baseline", vim.log.levels.ERROR); return
      end
    end
  end
  local text = baseline.code == 0 and baseline.stdout or ""
  local lines = vim.split(text, "\n", { plain = true })
  if #lines > 1 and lines[#lines] == "" then table.remove(lines) end
  local filebuf = vim.fn.bufadd(path)
  vim.fn.bufload(filebuf)
  if not vim.bo[filebuf].modified then
    if vim.uv.fs_stat(path) then
      vim.cmd("checktime " .. filebuf)
    else
      vim.api.nvim_buf_set_lines(filebuf, 0, -1, false, { "" })
      vim.bo[filebuf].modified = false
    end
  end
  if valid(M.paths[path]) then
    local entry = M.entries[M.paths[path]]
    vim.bo[entry.before].modifiable = true
    vim.api.nvim_buf_set_lines(entry.before, 0, -1, false, lines)
    vim.bo[entry.before].modified = false
    vim.bo[entry.before].modifiable = false
    M.show(entry.buf)
    vim.cmd("diffupdate")
    return
  end
  vim.bo[filebuf].buflisted = true
  local before = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_buf_set_name(before, "git-before://" .. path)
  vim.b[before].ide_diff_before = true
  vim.api.nvim_buf_set_lines(before, 0, -1, false, lines)
  vim.bo[before].filetype = vim.bo[filebuf].filetype
  vim.bo[before].bufhidden = "hide"
  vim.bo[before].modified = false
  vim.bo[before].modifiable = false
  vim.bo[before].readonly = true
  local buf = vim.api.nvim_create_buf(true, false)
  vim.api.nvim_buf_set_name(buf, "ide-diff://" .. path)
  vim.bo[buf].buftype = "acwrite"
  vim.bo[buf].swapfile = false
  vim.bo[buf].bufhidden = "hide"
  vim.b[buf].ide_diff_file = path
  local entry = { buf = buf, before = before, filebuf = filebuf, path = path }
  M.entries[buf], M.paths[path] = entry, buf
  copy(filebuf, buf)
  vim.bo[buf].filetype = vim.bo[filebuf].filetype
  attach(entry, buf)
  attach(entry, filebuf)
  vim.api.nvim_create_autocmd("BufWriteCmd", { buffer = buf, callback = function()
    M.flush()
    M.sync(entry)
    vim.api.nvim_buf_call(filebuf, function() vim.cmd("write") end)
    vim.bo[buf].modified = false
    require("config.editor_tabs").draw()
  end })
  vim.api.nvim_create_autocmd("BufWritePost", { buffer = filebuf, callback = function()
    M.sync(entry, filebuf)
    require("config.editor_tabs").draw()
  end })
  vim.api.nvim_create_autocmd("BufWipeout", { buffer = buf, once = true, callback = function()
    M.flush()
    if M.active and M.active.buf == buf then M.leave() end
    M.entries[buf], M.paths[path] = nil, nil
    entry.removed = true
    vim.schedule(function() if valid(before) then vim.api.nvim_buf_delete(before, { force = true }) end end)
  end })
  M.show(buf)
end

local function colors()
  vim.api.nvim_set_hl(0, "DiffAdd", { bg = "#204d2a" })
  vim.api.nvim_set_hl(0, "DiffDelete", { bg = "#5a2020", fg = "#ff8989" })
  vim.api.nvim_set_hl(0, "DiffChange", { bg = "#59401f" })
  vim.api.nvim_set_hl(0, "DiffText", { bg = "#915b20", bold = true })
  vim.api.nvim_set_hl(0, "DesktopDiffRemoved", { bg = "#5a2020" })
  vim.api.nvim_set_hl(0, "DesktopDiffAddedGap", { bg = "#204d2a", fg = "#84c88b" })
  vim.api.nvim_set_hl(0, "DesktopMapAdd", { bg = "#204d2a", fg = "#84c88b" })
  vim.api.nvim_set_hl(0, "DesktopMapDelete", { bg = "#5a2020", fg = "#ff8989" })
  vim.api.nvim_set_hl(0, "DesktopMapChange", { bg = "#59401f", fg = "#eab16b" })
end

function M.setup()
  colors()
  local group = vim.api.nvim_create_augroup("DesktopIDEDiff", { clear = true })
  local releases = {}
  for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
    releases[vim.keycode("<" .. prefix .. "LeftRelease>")] = true
  end
  vim.on_key(function(key, typed)
    if not releases[typed] and not releases[key] then return end
    local active, mouse = M.active, vim.fn.getmousepos()
    if M.busy or not active or not winvalid(active.right) or mouse.winid ~= active.right
      or mouse.line < 1 or mouse.winrow < 1 then return end
    local info = vim.fn.getwininfo(active.right)[1]
    if not info or mouse.wincol <= info.textoff then return end
    vim.schedule(function()
      if not M.busy and M.active == active and winvalid(active.right)
        and vim.api.nvim_get_current_win() == active.right
        and vim.api.nvim_win_get_buf(active.right) == active.buf
        and vim.bo[active.buf].modifiable and vim.fn.mode() == "n" then
        vim.cmd("startinsert")
      end
    end)
  end, vim.api.nvim_create_namespace("DesktopDiffInputMouse"))
  vim.api.nvim_create_autocmd("ColorScheme", { group = group, callback = colors })
  vim.api.nvim_create_autocmd("BufEnter", { group = group, callback = function(event)
    if M.busy or require("config.ide").is_tool_tab() then return end
    local win, buf = vim.api.nvim_get_current_win(), event.buf
    if vim.api.nvim_win_get_config(win).relative ~= "" then return end
    if not M.entries[buf] and (not M.active or (win ~= M.active.right and win ~= M.active.left)
      or vim.bo[buf].buftype ~= "") then return end
    vim.schedule(function()
      if M.busy or not winvalid(win) or vim.api.nvim_win_get_buf(win) ~= buf
        or require("config.ide").is_tool_tab(vim.api.nvim_win_get_tabpage(win)) then return end
      if M.entries[buf] then M.show(buf)
      elseif M.active and not vim.b[buf].ide_diff_before then
        local right = M.active.right
        if win == M.active.left and winvalid(right) then
          M.busy = true
          vim.api.nvim_win_set_buf(right, buf)
          M.busy = false
        end
        M.leave()
      end
    end)
  end })
end
return M
