-- Ex commands are automatically discoverable in Snacks' command palette.
local M = {}

local function root()
  local cwd = require("config.ide").root()
  local repo = vim.system({ "git", "-C", cwd, "rev-parse", "--show-toplevel" }, { text = true }):wait()
  if repo.code == 0 then return vim.trim(repo.stdout) end
  vim.notify("This project is not a Git repository", vim.log.levels.INFO)
end

local function run(cwd, args)
  if M.busy then vim.notify("A Git operation is already running", vim.log.levels.INFO); return end
  M.busy = true
  local command = { "git", "-C", cwd }; vim.list_extend(command, args)
  vim.system(command, { text = true, timeout = 120000,
    env = { GIT_EDITOR = "true", GIT_TERMINAL_PROMPT = "0" } }, function(result)
    vim.schedule(function()
      M.busy = false
      local message = vim.trim((result.stdout or "") .. "\n" .. (result.stderr or ""))
      if message == "" then message = "Git " .. args[1] .. (result.code == 0 and " completed" or " failed") end
      vim.notify(message, result.code == 0 and vim.log.levels.INFO or vim.log.levels.ERROR)
      -- A failed merge can still create conflicts; refresh those as well.
      if cwd == require("config.ide").root() then
        vim.cmd("checktime")
        require("config.git").refresh()
      end
    end)
  end)
end

function M.merge(branch)
  vim.cmd("stopinsert")
  local cwd = root()
  if not cwd then return end
  if branch and branch ~= "" then run(cwd, { "merge", "--no-edit", "--", branch }); return end
  Snacks.picker.git_branches({ cwd = cwd, all = true, title = "Merge branch",
    confirm = function(picker, item)
      if not item or not item.branch then return end
      picker:close()
      run(cwd, { "merge", "--no-edit", "--", item.branch })
    end,
  })
end

local function operation(args)
  return function()
    local cwd = root()
    if cwd then run(cwd, args) end
  end
end

local function editor_action(action)
  return function()
    vim.api.nvim_set_current_win(require("config.ide").editor_window())
    action()
  end
end

function M.setup()
  local commands = {
    GitStatus = { "Git: show changed files", function() require("config.ide").git_explorer() end },
    GitRefresh = { "Git: refresh status and commit graph", function() require("config.git").refresh() end },
    GitSwitchBranch = { "Git: switch branch", function() require("config.git").branches() end },
    GitMerge = { "Git: merge branch into the current branch", function(opts) M.merge(opts.args) end, nargs = "?" },
    GitMergeAbort = { "Git: abort the current merge", operation({ "merge", "--abort" }) },
    GitFetch = { "Git: fetch remote changes", operation({ "fetch" }) },
    GitPull = { "Git: pull remote changes", operation({ "pull", "--no-edit" }) },
    GitPush = { "Git: push the current branch", operation({ "push" }) },
    GitSync = { "Git: synchronize through fetch, pull, and push", function() require("config.git_sync").sync() end },
    GitCommit = { "Git: enter a commit message", function()
      require("config.ide").git_explorer()
      local state = require("neo-tree.sources.manager").get_state("git_status")
      require("config.git").input(state, true)
    end },
    GitDiff = { "Git: open repository diff", function() vim.cmd("DiffviewOpen") end },
    GitProjectHistory = { "Git: open project history", function() vim.cmd("DiffviewFileHistory") end },
    GitFileHistory = { "Git: open file history", editor_action(function()
      local buf = vim.api.nvim_get_current_buf()
      local path = vim.b[buf].ide_diff_file or vim.api.nvim_buf_get_name(buf)
      if path == "" then vim.notify("Open a file first", vim.log.levels.INFO); return end
      vim.cmd("DiffviewFileHistory " .. vim.fn.fnameescape(path))
    end) },
    GitBlame = { "Git: blame the current line", editor_action(function() require("gitsigns").blame_line({ full = true }) end) },
    GitStageHunk = { "Git: stage the current hunk", editor_action(function() require("gitsigns").stage_hunk() end) },
  }
  for name, command in pairs(commands) do
    vim.api.nvim_create_user_command(name, command[2], { desc = command[1], nargs = command.nargs or 0 })
  end
end

return M
