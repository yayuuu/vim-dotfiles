-- Fetch metadata before patches: generated/minified files must not freeze the UI.
local M = { max_changes = 800, max_blob = 128 * 1024, auto_budget = 256 * 1024,
  auto_lines = 4000, auto_files = 40,
  max_patch = 128 * 1024, max_line = 1600 }
local api = vim.api

local function active(state)
  return not state.closed and not state.picker.closed and api.nvim_buf_is_valid(state.ctx.buf)
    and state.picker.ide_commit_preview == state
end

local function run(state, args, callback, stdin, limit)
  local cmd = { "git", "--no-pager", "--literal-pathspecs", "-C", state.item.root }
  vim.list_extend(cmd, args)
  local chunks, size, truncated = {}, 0, false
  local opts = { text = true, stdin = stdin }
  if limit then
    opts.stdout = function(_, data)
      if not data then return end
      local remaining = math.max(0, limit - size)
      chunks[#chunks + 1] = data:sub(1, remaining)
      size, truncated = size + #data, truncated or #data > remaining
    end
  end
  local job
  job = vim.system(cmd, opts, function(result)
    vim.schedule(function()
      state.jobs[job] = nil
      if not active(state) then return end
      if limit then result.stdout = table.concat(chunks) end
      callback(result, truncated)
    end)
  end)
  state.jobs[job] = true
end

function M.cancel(picker)
  local state = picker.ide_commit_preview
  if not state then return end
  state.closed = true
  for job in pairs(state.jobs) do job:kill(15) end
end

local function render(state)
  if not active(state) then return end
  local lines = vim.split(state.header or "Loading commit…", "\n", { plain = true, trimempty = true })
  state.rows = {}
  for _, file in ipairs(state.files) do
    lines[#lines + 1] = ""
    local icon = require("config.settings").icons and (file.expanded and "▾" or "▸") or (file.expanded and "v" or ">")
    local status = file.loading and " — Loading…" or file.reason and not file.expanded and " — " .. file.reason .. "; Enter/click to load" or ""
    lines[#lines + 1] = icon .. " " .. vim.fn.strtrans(file.path) .. "  (+" .. file.added .. " -" .. file.deleted .. ")" .. status
    state.rows[#lines] = file
    if file.expanded then
      if file.patch then vim.list_extend(lines, file.patch)
      elseif file.error then lines[#lines + 1] = "  Cannot load diff: " .. file.error end
    end
  end
  local preview = state.ctx.preview
  preview:set_lines(lines)
  preview:highlight({ ft = "git" })
end

local function refresh(state)
  if state.pending then return end
  state.pending = true
  vim.schedule(function() state.pending = false; render(state) end)
end

local function load_patch(state, file, done)
  file.loading = true
  run(state, { "show", "--format=", "--no-ext-diff", "--no-textconv", "--no-color", "--no-renames",
    "--diff-merges=first-parent", state.item.commit, "--", file.path }, function(result, truncated)
    file.loading = false
    if result.code ~= 0 then file.error = vim.trim(result.stderr or "Git failed")
    else
      file.patch = {}
      for line in (result.stdout .. "\n"):gmatch("(.-)\n") do
        line = line:gsub("%z", "^@")
        if #line > M.max_line then line = vim.fn.strcharpart(line, 0, M.max_line) .. " … [line shortened]" end
        file.patch[#file.patch + 1] = line
      end
      if truncated then file.patch[#file.patch + 1] = "[Large diff: preview limited to 128 KiB]" end
    end
    refresh(state)
    if done then done() end
  end, nil, M.max_patch)
end

function M.toggle(state, row)
  local file = state.rows[row]
  if not file or not active(state) then return end
  file.expanded = not file.expanded
  if file.expanded and not file.patch and not file.loading then load_patch(state, file) end
  refresh(state)
end

local function prepare(state, data)
  local tokens = vim.split(data, "\0", { plain = true, trimempty = true })
  local raw, objects, seen, index = {}, {}, {}, 1
  while index <= #tokens do
    local token = tokens[index]:gsub("^\n", "")
    local old, new = token:match("^:%d+ %d+ (%x+) (%x+) %u")
    if old then
      raw[tokens[index + 1]] = { old, new }
      for _, hash in ipairs({ old, new }) do
        if not hash:match("^0+$") and not seen[hash] then objects[#objects + 1], seen[hash] = hash, true end
      end
      index = index + 2
    else
      local added, deleted, path = token:match("^([%d-]+)\t([%d-]+)\t(.*)$")
      if path then state.files[#state.files + 1] = { path = path, added = added, deleted = deleted, objects = raw[path] or {} } end
      index = index + 1
    end
  end
  local function classify(sizes)
    local budget, line_budget, queue = M.auto_budget, M.auto_lines, {}
    for _, file in ipairs(state.files) do
      local size = 0
      for _, hash in ipairs(file.objects) do size = size + (sizes[hash] or 0) end
      if file.added == "-" then file.reason = "Binary file"
      elseif tonumber(file.added) + tonumber(file.deleted) > M.max_changes then file.reason = "Large diff"
      elseif size > M.max_blob then file.reason = "Large file"
      elseif size > budget or tonumber(file.added) + tonumber(file.deleted) > line_budget or #queue >= M.auto_files then
        file.reason = "Commit preview limit"
      else
        file.expanded = true
        budget, line_budget = budget - size, line_budget - tonumber(file.added) - tonumber(file.deleted)
        queue[#queue + 1] = file
      end
    end
    refresh(state)
    local next_index = 0
    local function next_file()
      next_index = next_index + 1
      local file = queue[next_index]
      if file and active(state) then load_patch(state, file, next_file) end
    end
    for _ = 1, math.min(4, #queue) do next_file() end
  end
  if #objects == 0 then classify({}); return end
  run(state, { "cat-file", "--batch-check=%(objectname) %(objectsize)" }, function(result)
    if result.code ~= 0 then state.header = "Cannot read file sizes: " .. vim.trim(result.stderr); refresh(state); return end
    local sizes = {}
    for hash, size in result.stdout:gmatch("(%x+) (%d+)") do sizes[hash] = tonumber(size) end
    classify(sizes)
  end, table.concat(objects, "\n") .. "\n")
end

function M.preview(ctx)
  local picker = ctx.picker
  local previous = picker.ide_commit_preview
  if previous and previous.ctx.buf == ctx.buf and previous.item.commit == ctx.item.commit then
    previous.ctx = ctx; render(previous); return
  end
  M.cancel(picker)
  local state = { ctx = ctx, picker = picker, item = ctx.item, files = {}, rows = {}, jobs = {} }
  picker.ide_commit_preview = state
  ctx.preview:reset()
  render(state)
  local opts = { buffer = ctx.buf, silent = true, nowait = true }
  for _, key in ipairs({ "<CR>", "<Space>" }) do
    vim.keymap.set("n", key, function() M.toggle(state, api.nvim_win_get_cursor(ctx.win)[1]) end, opts)
  end
  vim.keymap.set("n", "<LeftRelease>", function()
    local mouse = vim.fn.getmousepos()
    if require("config.mouse_capture").active() then return end
    local row = require("config.panel_mouse").row(mouse, ctx.win)
    if row then M.toggle(state, row) end
  end, opts)
  run(state, { "show", "--no-patch", "--format=fuller", state.item.commit }, function(result)
    state.header = result.code == 0 and result.stdout or "Cannot load commit: " .. vim.trim(result.stderr)
    refresh(state)
  end)
  run(state, { "show", "--format=", "--raw", "--numstat", "--no-abbrev", "--no-renames", "--no-ext-diff", "--no-textconv",
    "--diff-merges=first-parent", "-z", state.item.commit }, function(result)
    if result.code == 0 then prepare(state, result.stdout)
    else state.header = "Cannot load changes: " .. vim.trim(result.stderr); refresh(state) end
  end)
end

function M.open(item)
  return Snacks.picker({ title = "Commit " .. item.commit:sub(1, 8), cwd = item.root,
    items = { item }, format = "git_log", preview = M.preview, main = { current = true },
    on_show = function(picker)
      require("config.popup_ui").register(picker.layout.root.win, function() picker:close() end)
      for _, pane in ipairs({ picker.input, picker.list, picker.preview }) do
        for _, key in ipairs({ "q", "<Esc>" }) do
          vim.keymap.set({ "n", "i" }, key, function() picker:close() end,
            { buffer = pane.win.buf, silent = true, nowait = true, desc = "Close commit preview" })
        end
      end
    end,
    on_change = function(picker)
      if picker.preview.win:valid() then require("config.vscroll").attach(picker.preview.win.win) end
    end,
    on_close = function(picker)
      M.cancel(picker)
      if picker.preview then require("config.vscroll").detach(picker.preview.win.win) end
    end,
    confirm = function(picker) picker:close() end })
end

return M
