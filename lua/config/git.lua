local M = { messages = {}, inputs = {} }
local refresh_label = "[⟳]"
local registered = {}
local window_sources = {}
local selection_ns = vim.api.nvim_create_namespace("DesktopIDEGitSelection")

function M.expand(state)
  if not state or not state.tree or not state.winid or not vim.api.nvim_win_is_valid(state.winid)
    or vim.api.nvim_win_get_buf(state.winid) ~= state.bufnr then return end
  local changed = false
  for _, id in ipairs({ state.path, state.path .. "::staged", state.path .. "::changes" }) do
    local node = state.tree:get_node(id)
    if node and node:expand() then changed = true end
  end
  if changed then require("neo-tree.ui.renderer").redraw(state) end
end

function M.enter(args)
  local previous = window_sources[args.winid]
  window_sources[args.winid] = args.source
  -- Neo-tree fires this event for refreshes too, not only source switches.
  if args.source ~= "git_status" or previous == "git_status" then return end
  vim.schedule(function()
    local state = require("neo-tree.sources.manager").get_state_for_window(args.winid)
    if state and state.name == "git_status" then M.expand(state) end
  end)
end

function M.highlight(state)
  if not state.tree or not state.bufnr or not vim.api.nvim_buf_is_valid(state.bufnr) then return end
  vim.api.nvim_buf_clear_namespace(state.bufnr, selection_ns, 0, -1)
  for id in pairs(state.ide_selected or {}) do
    local node, line = state.tree:get_node(id)
    if not node or node.type ~= "file" then state.ide_selected[id] = nil
    elseif line then
      local text = vim.api.nvim_buf_get_lines(state.bufnr, line - 1, line, false)[1] or ""
      local start = (text:find("%S") or 1) - 1
      -- A range ending at the next row lets hl_eol paint the empty space
      -- to the window edge, while keeping the tree's left margin untouched.
      vim.api.nvim_buf_set_extmark(state.bufnr, selection_ns, line - 1, start,
        { end_row = line, end_col = 0, hl_group = "Visual", hl_eol = true, priority = 200 })
    end
  end
  if state.ide_anchor and not state.tree:get_node(state.ide_anchor) then state.ide_anchor = nil end
end

function M.select(state, node, extend, keep, toggle)
  if not node or node.type ~= "file" then
    state.ide_selected, state.ide_anchor = {}, nil
    M.highlight(state); return
  end
  local id = node:get_id()
  if keep and state.ide_selected and state.ide_selected[id] then return end
  if toggle then
    state.ide_selected = state.ide_selected or {}
    state.ide_selected[id] = not state.ide_selected[id] or nil
    state.ide_anchor = id
    M.highlight(state); return
  end
  local anchor
  if state.ide_anchor then local _, line = state.tree:get_node(state.ide_anchor); anchor = line end
  local _, finish = state.tree:get_node(id)
  state.ide_selected = {}
  if extend and anchor and finish then
    for line = math.min(anchor, finish), math.max(anchor, finish) do
      local file = state.tree:get_node(line)
      if file and file.type == "file" then state.ide_selected[file:get_id()] = true end
    end
  else state.ide_selected[id], state.ide_anchor = true, id end
  M.highlight(state)
end

function M.targets(state, node, action)
  if not node or (node.type ~= "file" and node.type ~= "git_section") then return {} end
  local section = action == "unstage" and "staged" or "changes"
  local result = {}
  local function add(file)
    if file and file.type == "file" and file.extra.section == section then result[#result + 1] = file end
  end
  if node.type == "git_section" then
    for _, child in ipairs(state.tree:get_nodes(node:get_id())) do add(child) end
  elseif state.ide_selected and state.ide_selected[node:get_id()] then
    for id in pairs(state.ide_selected) do add(state.tree:get_node(id)) end
  else add(node) end
  table.sort(result, function(a,b) return a.extra.relative < b.extra.relative end)
  return result
end

function M.open_diff(state, node)
  local staged = node.extra.section == "changes" and state.tree:get_node(node.path .. "::staged")
  require("config.diff").open(node.path, { baseline = staged and "index" or "HEAD" })
end

function M.menu(state, node)
  M.select(state, node, false, true)
  local items = {}
  if node and node.type == "file" then
    items[#items + 1] = { name = "Open diff", cmd = function() M.open_diff(state, node) end }
    local staged = node.extra.section == "staged"
    local actions = staged and { { "unstage", "Unstage Changes" } }
      or { { "stage", "Stage Changes" }, { "discard", "Discard Changes…" } }
    for _, action in ipairs(actions) do
      local kind, label = unpack(action)
      local targets = M.targets(state, node, kind)
      items[#items + 1] = { name = label,
        cmd = function() M.action(state, kind, node, targets) end }
    end
    items[#items + 1] = { name = "separator" }
  end
  items[#items + 1] = { name = "Refresh Git status", rtxt = "F5", cmd = M.refresh }
  items[#items + 1] = { name = "Switch branch…", cmd = M.branches }
  return items
end

function M.setup()
  local events = {}
  for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
    events[vim.keycode("<" .. prefix .. "LeftMouse>")] = "Reset"
    for _, modifier in ipairs({ "", "S-", "C-" }) do
      events[vim.keycode("<" .. modifier .. prefix .. "LeftRelease>")] = "Release"
      events[vim.keycode("<" .. modifier .. prefix .. "LeftDrag>")] = "Drag"
    end
    events[vim.keycode("<S-" .. prefix .. "LeftMouse>")] = "Range"
    events[vim.keycode("<C-" .. prefix .. "LeftMouse>")] = "Toggle"
  end
  vim.on_key(function(key, typed)
    local kind = events[typed] or events[key]
    if not kind then return end
    if kind == "Reset" then M.selection_mouse_pending = nil; return end
    if kind == "Range" or kind == "Toggle" then
      M.selection_mouse_pending = nil
      local mouse = vim.fn.getmousepos()
      if mouse.winid == 0 or mouse.line < 1 or not vim.api.nvim_win_is_valid(mouse.winid)
        or vim.bo[vim.api.nvim_win_get_buf(mouse.winid)].filetype ~= "neo-tree" then return end
      local state = require("neo-tree.sources.manager").get_state_for_window(mouse.winid)
      if not state or state.name ~= "git_status" then return end
      local node = state.tree and state.tree:get_node(mouse.line)
      if not node or node.type ~= "file" then return end
      M.selection_mouse_pending = true
      vim.schedule(function()
        if not vim.api.nvim_win_is_valid(state.winid)
          or vim.api.nvim_win_get_buf(state.winid) ~= state.bufnr then return end
        vim.cmd("stopinsert")
        -- normal! executes only Escape; feedkeys would also consume queued
        -- mouse events and could turn the release into a second plain click.
        vim.cmd.normal({ args = { vim.keycode("<Esc>") }, bang = true })
        vim.api.nvim_set_current_win(state.winid)
        vim.api.nvim_win_set_cursor(state.winid, { mouse.line, 0 })
        M.select(state, node, kind == "Range", false, kind == "Toggle")
      end)
    end
    if M.selection_mouse_pending then
      if kind == "Release" then
        -- Some terminal releases omit modifiers. Ignore the release either way.
        -- Release mappings can run before on_key, so clear the guard later.
        vim.schedule(function() M.selection_mouse_pending = nil end)
      end
      return ""
    end
  end, vim.api.nvim_create_namespace("DesktopIDEGitMouse"))
end

function M.set_root(path)
  require("neo-tree").ensure_config()
  local state = require("neo-tree.sources.manager").get_state("git_status")
  if state.path ~= path then state.ide_selected, state.ide_anchor = {}, nil end
  state.path, state.dirty = path, true
end

function M.refresh()
  require("config.git_sync").refresh()
  require("config.sidebar").refresh_history()
  local manager = require("neo-tree.sources.manager")
  local state = manager.get_state("git_status")
  state.path = require("config.ide").root()
  if state.winid and vim.api.nvim_win_is_valid(state.winid)
    and vim.api.nvim_win_get_buf(state.winid) == state.bufnr then manager.navigate(state, state.path)
  else state.dirty = true end
  if package.loaded["lualine.components.branch.git_branch"] then
    require("lualine.components.branch.git_branch").find_git_dir()
  end
  if package.loaded.lualine then require("lualine").refresh({ force = true }) end
end

function M.branches()
  vim.cmd("stopinsert")
  local cwd = require("config.ide").root()
  local repo = vim.system({ "git", "-C", cwd, "rev-parse", "--show-toplevel" }, { text = true }):wait()
  if repo.code ~= 0 then
    vim.notify("This project is not a Git repository", vim.log.levels.INFO)
    return
  end
  cwd = vim.trim(repo.stdout)
  Snacks.picker.git_branches({
    cwd = cwd,
    confirm = function(picker, item)
      if not item or not item.branch then return end
      picker:close()
      Snacks.picker.util.cmd({ "git", "switch", "--", item.branch }, function()
        vim.cmd("checktime")
        M.refresh()
      end, { cwd = cwd })
    end,
  })
end

function M.name(config, node, state, width)
  local original = require("neo-tree.sources.git_status.components").name(config, node, state)
  if node.type ~= "directory" or node:get_depth() ~= 1 then return original end
  width = math.max(1, width or vim.api.nvim_win_get_width(state.winid))
  local available = math.max(0, width - vim.fn.strdisplaywidth(refresh_label) - 1)
  local title = original.text
  if vim.fn.strdisplaywidth(title) > available then
    while vim.fn.strdisplaywidth(title) > math.max(0, available - 1) do
      title = vim.fn.strcharpart(title, 0, vim.fn.strchars(title) - 1)
    end
    title = available > 0 and title .. "…" or ""
  end
  return { text = title, highlight = original.highlight }
end

function M.directory(_, node, state, remaining_width)
  if node:get_depth() == 1 then
    local width = state.winid and vim.api.nvim_win_is_valid(state.winid)
      and vim.api.nvim_win_get_width(state.winid) or state.win_width or 30
    width = math.min(width, remaining_width or width)
    local title = require("neo-tree.sources.git_status.components").name({}, node, state).text
    local space = math.max(0, width - vim.fn.strdisplaywidth(refresh_label) - 1)
    if vim.fn.strdisplaywidth(title) > space then
      while vim.fn.strdisplaywidth(title) > math.max(0, space - 1) do
        title = vim.fn.strcharpart(title, 0, vim.fn.strchars(title) - 1)
      end
      title = space > 0 and title .. "…" or ""
    end
    return {
      { text = title .. string.rep(" ", math.max(0, width - vim.fn.strdisplaywidth(title) - 3)),
        highlight = "NeoTreeRootName", no_next_padding = true },
      { text = refresh_label, highlight = "NeoTreeTabActive", no_padding = true },
    }
  end
  local parts = {}
  -- Source renderers have component defaults resolved by Neo-tree setup.
  -- The global template does not (notably container.width is still nil).
  local width = remaining_width or state.win_width or 30
  for _, component in ipairs(require("neo-tree").config.filesystem.renderers.directory) do
    -- Neo-tree already inserts its indentation before this component.
    if component[1] ~= "indent" then
      local chunks = require("neo-tree.ui.renderer").render_component(component, node, state, math.max(0, width))
      vim.list_extend(parts, chunks or {})
      for _, chunk in ipairs(chunks or {}) do
        width = width - vim.fn.strdisplaywidth(chunk.text or "") - 1
      end
    end
  end
  return parts
end

function M.click(state, mouse)
  if M.selection_mouse_pending or require("config.ide").menu_mouse_pending then return end
  mouse = mouse or vim.fn.getmousepos()
  local node = state.tree and state.tree:get_node()
  if state.tree and mouse.winid == state.winid and mouse.line > 0 then
    -- Repeated mouse presses are mapped to no-ops to prevent Vim text selection.
    -- Use the actual clicked row rather than the cursor left by a previous click.
    node = state.tree:get_node(mouse.line)
    if node then vim.api.nvim_win_set_cursor(state.winid, { mouse.line, 0 }) end
  end
  if node and node.type == "directory" and node:get_depth() == 1
    and mouse.winid == state.winid and mouse.line > 0 then
    local _, root_line = state.tree:get_node(state.path)
    local width = vim.api.nvim_win_get_width(state.winid)
    if mouse.line == root_line and mouse.wincol > width - vim.fn.strdisplaywidth(refresh_label) then
      M.refresh()
      return
    end
  end
  M.select(state, node)
  M.open(state)
end

function M.open(state)
  local node = state.tree and state.tree:get_node()
  if node and node.type == "file" then M.open_diff(state, node)
  elseif node and node.type == "git_commit" then M.input(state, true)
  elseif node and node.type == "git_commit_action" then M.commit(state)
  elseif node and node.type == "git_section" then
    if node:is_expanded() then node:collapse() else node:expand() end
    require("neo-tree.ui.renderer").redraw(state)
  else require("neo-tree.sources.git_status.commands").open(state) end
end

function M.run(root, args, callback)
  local cmd = { "git", "-C", root }
  vim.list_extend(cmd, args)
  vim.system(cmd, { text = true }, function(result)
    vim.schedule(function()
      if result.code ~= 0 then vim.notify(result.stderr or result.stdout, vim.log.levels.ERROR); return end
      if callback then callback(result) end
      M.refresh()
    end)
  end)
end

function M.action(state, action, node, targets)
  -- get_node() also returns a line number when passed as the final argument.
  if type(targets) ~= "table" then targets = nil end
  node = node or (state.tree and state.tree:get_node())
  if not node or (node.type ~= "file" and node.type ~= "git_section") then return end
  local root, paths, seen = state.path, {}, {}
  for _, file in ipairs(targets or M.targets(state, node, action)) do
    for _, path in ipairs({ file.extra.relative, file.extra.original }) do
      if not seen[path] then paths[#paths + 1], seen[path] = path, true end
    end
  end
  if #paths == 0 then return end
  local function execute(args)
    args[#args + 1] = "--"; vim.list_extend(args, paths); M.run(root, args)
  end
  if action == "stage" then
    local function save_next(i)
      if i > #paths then execute({ "add" }); return end
      local buf = vim.fn.bufnr(root .. "/" .. paths[i])
      if buf >= 0 and vim.bo[buf].modified then
        require("config.ide").save_buffer(buf, false, function(ok) if ok then save_next(i + 1) end end)
      else save_next(i + 1) end
    end
    save_next(1)
  elseif action == "unstage" then
    local head = vim.system({ "git", "-C", root, "rev-parse", "--verify", "HEAD" }):wait()
    execute(head.code == 0 and { "restore", "--staged" } or { "rm", "--cached", "--ignore-unmatch" })
  elseif action == "discard" then
    local label = #paths > 1 and (#paths .. " selected files") or node.name
    vim.ui.select({ "Discard changes", "Cancel" }, { prompt = "Discard working changes to " .. label .. "?" }, function(choice)
      if choice ~= "Discard changes" then return end
      local backup = vim.fn.stdpath("state") .. "/git-discard/" .. os.date("%Y%m%d-%H%M%S") .. "-" .. vim.uv.hrtime()
      for _, relative in ipairs(paths) do
        local path = root .. "/" .. relative
        if vim.uv.fs_stat(path) then
          vim.fn.mkdir(vim.fn.fnamemodify(backup .. "/" .. relative, ":h"), "p")
          assert(vim.uv.fs_copyfile(path, backup .. "/" .. relative))
          local buf = vim.fn.bufnr(path)
          if buf >= 0 and vim.bo[buf].modified then
            vim.fn.writefile(vim.api.nvim_buf_get_lines(buf, 0, -1, false), backup .. "/" .. relative .. ".unsaved")
          end
        end
      end
      local tracked, untracked = {}, {}
      for _, relative in ipairs(paths) do
        local exists = vim.system({ "git", "-C", root, "ls-files", "--error-unmatch", "--", relative }):wait()
        if exists.code == 0 then tracked[#tracked + 1] = relative else untracked[#untracked + 1] = relative end
      end
      for _, relative in ipairs(untracked) do vim.uv.fs_unlink(root .. "/" .. relative) end
      local function reload()
        for _, relative in ipairs(paths) do
          local buf = vim.fn.bufnr(root .. "/" .. relative)
          if buf >= 0 and vim.api.nvim_buf_is_loaded(buf) then
            vim.api.nvim_buf_call(buf, function() vim.cmd("silent edit!") end)
          end
        end
        M.refresh()
      end
      if #tracked > 0 then
        local args = { "restore", "--worktree", "--" }; vim.list_extend(args, tracked)
        M.run(root, args, reload)
      else reload() end
    end)
  end
end

function M.commit(state)
  local root = state.path
  local field = M.inputs[root]
  local message = field and vim.api.nvim_buf_is_valid(field.buf)
    and table.concat(vim.api.nvim_buf_get_lines(field.buf, 0, -1, false), "\n") or M.messages[root] or ""
  if vim.trim(message) == "" then vim.notify("Enter a commit message first", vim.log.levels.INFO); M.input(state, true); return end
  local index = vim.system({ "git", "-C", root, "diff", "--cached", "--quiet" }):wait()
  if index.code == 0 then vim.notify("No staged changes to commit", vim.log.levels.INFO); return end
  vim.system({ "git", "-C", root, "commit", "--file", "-" }, { text = true, stdin = message }, function(result)
    vim.schedule(function()
      if result.code ~= 0 then vim.notify(result.stderr or result.stdout, vim.log.levels.ERROR); return end
      M.messages[root] = ""
      if field and vim.api.nvim_buf_is_valid(field.buf) then vim.api.nvim_buf_set_lines(field.buf, 0, -1, false, { "" }) end
      vim.notify(vim.trim(result.stdout), vim.log.levels.INFO)
      M.refresh()
    end)
  end)
end

function M.input(state, focus)
  if not state.winid or not vim.api.nvim_win_is_valid(state.winid) or vim.api.nvim_win_get_buf(state.winid) ~= state.bufnr then return end
  local root = state.path
  for path, other in pairs(M.inputs) do
    if path ~= root and other.win and vim.api.nvim_win_is_valid(other.win) then vim.api.nvim_win_close(other.win, true); other.win = nil end
  end
  local field = M.inputs[root]
  if not field or not vim.api.nvim_buf_is_valid(field.buf) then
    local buf = vim.api.nvim_create_buf(false, true)
    field = { buf = buf }; M.inputs[root] = field
    vim.bo[buf].bufhidden = "hide"; vim.bo[buf].filetype = "ide_git_message"
    vim.api.nvim_buf_set_lines(buf, 0, -1, false, { M.messages[root] or "" })
    vim.b[buf].ide_git_input = true
    vim.keymap.set("n", "<LeftRelease>", function() vim.cmd("startinsert") end, { buffer = buf })
    vim.keymap.set({ "n", "i" }, "<CR>", function() vim.cmd("stopinsert"); M.commit(state) end, { buffer = buf })
    vim.keymap.set({ "n", "i" }, "<C-CR>", function() vim.cmd("stopinsert"); M.commit(state) end, { buffer = buf })
    vim.keymap.set("n", "<Esc>", function() vim.api.nvim_set_current_win(state.winid) end, { buffer = buf })
    local namespace = vim.api.nvim_create_namespace("DesktopIDEGitInput")
    vim.api.nvim_buf_attach(buf, false, { on_lines = function()
      vim.schedule(function()
        if not vim.api.nvim_buf_is_valid(buf) then return end
        local lines = vim.api.nvim_buf_get_lines(buf, 0, -1, false)
        M.messages[root] = table.concat(lines, " ")
        vim.api.nvim_buf_clear_namespace(buf, namespace, 0, -1)
        if lines[1] == "" then vim.api.nvim_buf_set_extmark(buf, namespace, 0, 0,
          { virt_text = { { "Commit message (Enter to commit)…", "Comment" } }, virt_text_pos = "overlay" }) end
      end)
    end })
    if (M.messages[root] or "") == "" then vim.api.nvim_buf_set_extmark(buf, namespace, 0, 0,
      { virt_text = { { "Commit message (Enter to commit)…", "Comment" } }, virt_text_pos = "overlay" }) end
  end
  local position = vim.api.nvim_win_get_position(state.winid)
  field.treewin, field.treebuf = state.winid, state.bufnr
  local config = { relative = "editor", row = position[1] + 2, col = position[2] + 1,
    width = math.max(1, vim.api.nvim_win_get_width(state.winid) - 2), height = 1, border = "none", style = "minimal", zindex = 25 }
  if field.win and vim.api.nvim_win_is_valid(field.win) then vim.api.nvim_win_set_config(field.win, config)
  else field.win = vim.api.nvim_open_win(field.buf, false, config) end
  vim.wo[field.win].winbar = ""; vim.wo[field.win].winhighlight = "Normal:Visual"
  if focus then vim.api.nvim_set_current_win(field.win); vim.cmd("startinsert!") end
end

function M.align(state)
  if M.aligning or not state.winid or not vim.api.nvim_win_is_valid(state.winid)
    or vim.api.nvim_win_get_buf(state.winid) ~= state.bufnr then return end
  M.aligning = true
  vim.api.nvim_win_call(state.winid, function()
    local cursor = vim.api.nvim_win_get_cursor(0)
    local view = vim.fn.winsaveview()
    if view.leftcol == 0 and cursor[2] ~= 0 then
      vim.api.nvim_win_set_cursor(0, { cursor[1], 0 }); view.col = 0
    end
    vim.wo.sidescrolloff = 0
    view.skipcol = 0
    vim.fn.winrestview(view)
  end)
  M.aligning = false
end

function M.header(state)
  if not state.winid or not vim.api.nvim_win_is_valid(state.winid) or not state.tree
    or vim.api.nvim_win_get_buf(state.winid) ~= state.bufnr then return end
  require("neo-tree.ui.renderer").redraw(state)
  -- redraw() replaces the buffer without firing Neo-tree's after_render event.
  M.highlight(state)
end

function M.after_render(state)
  if state.name == "git_status" and state.winid and vim.api.nvim_win_is_valid(state.winid) then
    vim.keymap.set({ "n", "i", "x", "s" }, "<F5>", M.refresh,
      { buffer = state.bufnr, desc = "Refresh Git status" })
    M.align(state)
    M.input(state)
    M.highlight(state)
    if not registered[state.bufnr] then
      registered[state.bufnr] = true
      local group = vim.api.nvim_create_augroup("DesktopIDEGitView" .. state.bufnr, { clear = true })
      vim.api.nvim_create_autocmd({ "CursorMoved", "CursorMovedI", "BufWinEnter", "WinScrolled" }, {
        group = group, buffer = state.bufnr, callback = function() M.align(state) end,
      })
      vim.api.nvim_create_autocmd("WinResized", {
        group = group, callback = function() M.align(state); M.header(state) end,
      })
    end
  end
end

return M
