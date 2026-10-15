local M = { cache = {}, sequence = 0, fetching = {}, fetched_at = {} }

local function redraw()
  require("config.colors").set_repository(M.repository_name())
  if package.loaded.lualine then require("lualine").refresh({ force = true }) end
  vim.cmd("redrawtabline")
end

function M.fetch(root, force)
  if M.busy or M.fetching[root] or vim.g.ide_git_autofetch == false then return end
  local now = vim.uv.hrtime() / 1e9
  if not force and now - (M.fetched_at[root] or -math.huge) < 60 then return end
  M.fetched_at[root], M.fetching[root] = now, true
  vim.system({ "git", "-C", root, "fetch", "--quiet" }, {
    text = true, env = { GIT_TERMINAL_PROMPT = "0" }, timeout = 30000,
  }, function()
    vim.schedule(function()
      M.fetching[root] = nil
      if root == require("config.ide").root() then M.refresh() end
    end)
  end)
end

function M.refresh()
  local root = require("config.ide").root()
  M.sequence = M.sequence + 1
  local sequence = M.sequence
  vim.system({ "git", "-C", root, "rev-parse", "--show-toplevel" }, { text = true }, function(repo)
    if repo.code ~= 0 then
      vim.schedule(function() if sequence == M.sequence then M.cache[root] = { repo = false }; redraw() end end)
      return
    end
    vim.system({ "git", "-C", root, "remote", "get-url", "origin" }, { text = true }, function(remote)
      local source = remote.code == 0 and vim.trim(remote.stdout or "") or vim.trim(repo.stdout or "")
      local name = (source:gsub("[/\\]+$", "")):match("([^/\\:]+)$") or ""
      name = name:gsub("%.git$", ""):gsub("%c", " ")
      vim.system({ "git", "-C", root, "rev-list", "--left-right", "--count", "HEAD...@{upstream}" },
        { text = true }, function(result)
          vim.schedule(function()
            if sequence ~= M.sequence then return end
            local ahead, behind = (result.stdout or ""):match("(%d+)%s+(%d+)")
            M.cache[root] = { repo = true, name = name, upstream = result.code == 0,
              ahead = tonumber(ahead), behind = tonumber(behind) }
            redraw()
            if result.code == 0 then M.fetch(root) end
          end)
        end)
    end)
  end)
end

function M.repository_name()
  local state = M.cache[require("config.ide").root()]
  return state and state.name or ""
end

function M.visible()
  local state = M.cache[require("config.ide").root()]
  return state and state.repo or false
end

function M.label()
  local state = M.cache[require("config.ide").root()]
  if not state or not state.repo then return "" end
  if M.busy then return "[↑… ↓…]" end
  return string.format("[↑%s ↓%s]", state.ahead or "–", state.behind or "–")
end

local function publication_remote(root, branch, callback)
  local function git(args)
    local command = { "git", "-C", root }; vim.list_extend(command, args)
    return vim.system(command, { text = true }):wait()
  end
  local result = git({ "remote" })
  if result.code ~= 0 then
    vim.notify(result.stderr or "Unable to list Git remotes", vim.log.levels.ERROR)
    return
  end
  local remotes = vim.split(vim.trim(result.stdout or ""), "\n", { trimempty = true })
  if #remotes == 0 then
    vim.notify("Add a Git remote before publishing this branch", vim.log.levels.INFO)
    return
  end
  for _, key in ipairs({ "branch." .. branch .. ".pushRemote", "remote.pushDefault", "branch." .. branch .. ".remote" }) do
    local configured = git({ "config", "--get", key })
    local remote = vim.trim(configured.stdout or "")
    if configured.code == 0 and vim.tbl_contains(remotes, remote) then callback(remote); return end
  end
  if vim.tbl_contains(remotes, "origin") then callback("origin")
  elseif #remotes == 1 then callback(remotes[1])
  else vim.ui.select(remotes, { prompt = "Publish branch to remote:" }, function(remote)
    if remote then callback(remote) end
  end) end
end

function M.sync()
  if M.busy then return end
  local root = require("config.ide").root()
  local upstream = vim.system({ "git", "-C", root, "rev-parse", "--abbrev-ref", "@{upstream}" }, { text = true }):wait()
  local publish = upstream.code ~= 0
  local commands
  local function finish(error)
    M.busy = false
    if error then vim.notify(error, vim.log.levels.ERROR)
    else vim.notify(publish and "Branch published with upstream" or "Repository synchronized", vim.log.levels.INFO) end
    vim.cmd("checktime")
    require("config.git").refresh()
  end
  local function run(index)
    if not commands[index] then finish(); return end
    local command = { "git", "-C", root }; vim.list_extend(command, commands[index])
    vim.system(command, { text = true, env = { GIT_TERMINAL_PROMPT = "0", GIT_EDITOR = "true" }, timeout = 120000 }, function(result)
      vim.schedule(function()
        if result.code ~= 0 then finish("Git " .. commands[index][1] .. " failed:\n" .. (result.stderr or result.stdout or ""))
        else run(index + 1) end
      end)
    end)
  end
  local function start()
    -- An automatic fetch may already own the refs lock. Let it finish before
    -- starting the explicit pull/push sequence for this captured repository.
    if M.fetching[root] then vim.defer_fn(start, 100) else run(1) end
  end
  local function execute(steps)
    if M.busy then return end
    commands = steps
    M.busy = true; redraw()
    start()
  end
  if publish then
    local head = vim.system({ "git", "-C", root, "symbolic-ref", "--quiet", "HEAD" }, { text = true }):wait()
    if head.code ~= 0 then
      vim.notify("Switch to a branch before publishing (detached HEAD)", vim.log.levels.INFO)
      return
    end
    local branch = vim.trim(head.stdout):gsub("^refs/heads/", "")
    publication_remote(root, branch, function(remote)
      local ref = "refs/heads/" .. branch
      execute({ { "push", "--set-upstream", "--", remote, ref .. ":" .. ref } })
    end)
  else execute({ { "fetch", "--quiet" }, { "pull", "--no-edit" }, { "push" } }) end
end

function M.setup()
  local group = vim.api.nvim_create_augroup("DesktopGitSync", { clear = true })
  local pending = false
  local function queue()
    if pending then return end
    pending = true
    vim.defer_fn(function() pending = false; M.refresh() end, 100)
  end
  vim.api.nvim_create_autocmd({ "FocusGained", "DirChanged", "BufWritePost", "ShellCmdPost", "TermLeave" }, {
    group = group, callback = queue })
  local timer = vim.uv.new_timer()
  timer:start(0, 15000, vim.schedule_wrap(queue))
  vim.api.nvim_create_autocmd("VimLeavePre", { group = group, once = true, callback = function() timer:stop(); timer:close() end })
end
return M
