local use_icons = require("config.settings").icons
local diagnostics_icons = use_icons
  and { Error = " ", Warn = " ", Hint = "󰌵 ", Info = " " }
  or { Error = "E ", Warn = "W ", Hint = "H ", Info = "I " }
return {
  { "stevearc/aerial.nvim", lazy = false, opts = {
    backends = { "treesitter", "lsp", "markdown" },
    attach_mode = "global", close_automatic_events = {},
    ignore = { filetypes = { "neo-tree", "NvMenu", "VoltWindow", "noice", "snacks_input", "snacks_terminal", "neominimap",
      "ide_git_history", "ide_terminal_list" } },
    layout = { width = 30, min_width = 20, max_width = 40, placement = "window", default_direction = "left",
      resize_to_content = false, preserve_equality = false },
    filter_kind = { "Class", "Constructor", "Function", "Method", "Interface", "Enum", "Struct" },
    icons = { Class = "C", Constructor = "c", Function = "f", Method = "m", Interface = "I", Enum = "E", Struct = "S" },
    show_guides = true,
    keymaps = { ["<LeftRelease>"] = function() require("config.ide").symbols_click() end,
      ["<2-LeftMouse>"] = function() require("config.ide").symbols_click() end },
    win_opts = { winbar = " Functions / Symbols ", number = false, relativenumber = false,
      foldcolumn = "1", statuscolumn = "%#Normal# " },
  }, config = function(_, opts)
    require("aerial").setup(opts)
    -- Keep empty Symbols panels compact; backend details remain in :AerialInfo.
    local util = require("aerial.util")
    local render_centered_text = util.render_centered_text
    util.render_centered_text = function(buf, text)
      if type(text) == "table" and text[1] == "No symbols" then text = { "No symbols" } end
      return render_centered_text(buf, text)
    end
    local window = require("aerial.window")
    vim.api.nvim_create_autocmd("CursorMovedI", {
      group = vim.api.nvim_create_augroup("DesktopSymbolsPosition", { clear = true }),
      callback = function(event)
        local ide = require("config.ide")
        if require("config.sidebar").symbols_enabled() and ide.is_document(event.buf)
          and not ide.is_tool_tab() and vim.api.nvim_win_get_config(0).relative == "" then
          -- Aerial listens to CursorMoved only; keep the same cursor/highlight
          -- update when editing without reopening or reparsing the outline.
          window.update_position(0, 0)
        end
      end,
    })
    local open = window.open_aerial_in_win
    local pending = false
    window.open_aerial_in_win = function(...)
      if not require("config.sidebar").symbols_enabled() then return end
      local mode = vim.fn.mode()
      if mode == "v" or mode == "V" or mode == "\22" or mode == "s" or mode == "S" or mode == "\19" then
        -- Replacing a sidebar buffer through nvim_win_set_buf cancels the
        -- editor's selection. Refresh the outline when selection ends.
        if not pending then
          pending = true
          vim.api.nvim_create_autocmd("ModeChanged", { once = true, callback = function()
            pending = false
            vim.schedule(function() require("aerial.autocommands").on_enter_buffer() end)
          end })
        end
        return
      end
      local target = select(3, ...)
      if target and vim.api.nvim_win_is_valid(target) and vim.api.nvim_win_get_config(target).relative == "" then
        -- open_in_win still applies Aerial's cached/default width on first
        -- render. This internal flag keeps our custom split's existing width,
        -- including when an asynchronous symbol refresh finishes later.
        vim.w[target].aerial_set_width = true
      end
      return open(...)
    end
  end },
  -- LazyVim's completion configuration uses the v1 API; v2 changes it and adds blink.lib.
  { "saghen/blink.cmp", version = "1.*", opts = { keymap = {
    ["<C-y>"] = false, ["<C-n>"] = false, ["<C-f>"] = false,
    ["<S-Tab>"] = false,
    ["<Tab>"] = { "select_and_accept", "snippet_forward", "fallback" },
  } } },
  { "Mofiqul/vscode.nvim", priority = 1000, opts = function() return require("config.colors").theme_options() end },
  { "LazyVim/LazyVim", opts = {
    colorscheme = "vscode",
    icons = {
      diagnostics = diagnostics_icons,
      git = { added = "+", modified = "~", removed = "-" },
      dap = { Stopped = { ">", "DiagnosticWarn", "DapStoppedLine" }, Breakpoint = "●", BreakpointCondition = "?", BreakpointRejected = "x", LogPoint = "L" },
    },
  } },
  { "nvim-mini/mini.icons", opts = { style = use_icons and "glyph" or "ascii" } },
  { "nvim-neo-tree/neo-tree.nvim", opts = {
    sources = { "config.project_source", "filesystem", "config.search_source", "config.debug_source", "config.git_source", "config.tab_source" },
    close_if_last_window = false,
    open_files_do_not_replace_types = { "aerial", "NvMenu", "neominimap", "snacks_terminal", "terminal", "nofile", "prompt", "quickfix", "Trouble", "trouble", "qf", "Outline" },
    event_handlers = { { event = "after_render", handler = function(state)
      require("config.git").after_render(state)
      if state.name == "search" then require("config.project_search").sync(state) end
    end },
      { event = "neo_tree_window_after_open", handler = function(args) require("config.git").enter(args) end },
      { event = "neo_tree_window_before_open", handler = function(args) require("config.sidebar").prepare(args) end },
      { event = "neo_tree_window_after_open", handler = function() require("config.sidebar").schedule() end },
      { event = "file_open_requested", handler = function(args)
      if args.open_cmd ~= "edit" then return end
      require("config.ide").open_file(args.path, args.bufnr)
      return { handled = true }
    end } },
    source_selector = { winbar = true, statusline = false, tabs_layout = "start", padding = { left = 1, right = 0 },
      separator = { left = "", right = " ", override = "right" }, sources = {
      { source = "projects", display_name = "Projects" },
      { source = "filesystem", display_name = "Files" },
      { source = "search", display_name = "Search" },
      { source = "debug", display_name = "Debug" },
      { source = "git_status", display_name = "Git" },
      { source = "buffers", display_name = "Tabs" },
    } },
    filesystem = { filtered_items = { visible = true }, components = {
      diagnostics = function(config, node, state)
        local result = require("neo-tree.sources.common.components").diagnostics(config, node, state)
        if result.text then result.text = result.text .. " " end
        return result
      end,
    }, commands = {
      add = function(state) require("config.files").create(state, false) end,
      add_directory = function(state) require("config.files").create(state, true) end,
      rename = function(state) require("config.ide").rename_file(state) end,
      open = function(state) require("config.files").open(state) end,
      copy_to_clipboard = function(state) require("config.files").copy(state) end,
      paste_from_clipboard = function(state) require("config.files").paste(state) end,
      delete = function(state) require("config.files").delete(state) end,
    }, window = { mappings = {
      ["<C-c>"] = "copy_to_clipboard",
      ["<C-v>"] = "paste_from_clipboard",
      ["<Del>"] = "delete",
    } } },
    git_status = { bind_to_cwd = false, cwd_target = { sidebar = "global", current = "global" }, components = {
      name = function(...) return require("config.git").name(...) end,
      git_directory = function(...) return require("config.git").directory(...) end,
    }, renderers = { directory = { { "git_directory" } } }, commands = {
      open = function(state) require("config.git").open(state) end,
    }, window = { mappings = {
      ["R"] = function() require("config.git").refresh() end,
      ["<F5>"] = function() require("config.git").refresh() end,
      ["<LeftRelease>"] = function(state) require("config.git").click(state) end,
      ["<2-LeftRelease>"] = function(state) require("config.git").click(state) end,
      ["<3-LeftRelease>"] = function(state) require("config.git").click(state) end,
      ["<4-LeftRelease>"] = function(state) require("config.git").click(state) end,
    } } },
    window = { width = 38, mappings = {
      ["<F2>"] = function() require("config.ide").rename_file() end,
      ["<C-s>"] = function() require("config.ide").save() end,
      ["<C-f>"] = function() require("config.ide").find() end,
      ["<LeftRelease>"] = function() require("config.ide").tree_click() end,
      ["<2-LeftRelease>"] = function() require("config.ide").tree_click() end,
      ["<3-LeftRelease>"] = function() require("config.ide").tree_click() end,
      ["<4-LeftRelease>"] = function() require("config.ide").tree_click() end,
      -- Consume repeated presses so Vim doesn't start word/line selection.
      ["<2-LeftMouse>"] = function() end,
      ["<3-LeftMouse>"] = function() end,
      ["<4-LeftMouse>"] = function() end,
    } },
    default_component_configs = {
      icon = { folder_closed = use_icons and "" or "+", folder_open = use_icons and "" or "-",
        folder_empty = use_icons and "" or "+", folder_empty_open = use_icons and "" or "-", default = "·" },
      indent = { expander_collapsed = use_icons and "▸" or ">", expander_expanded = use_icons and "▾" or "v" },
      diagnostics = { symbols = { error = vim.trim(diagnostics_icons.Error), warn = vim.trim(diagnostics_icons.Warn),
        hint = vim.trim(diagnostics_icons.Hint), info = vim.trim(diagnostics_icons.Info) } },
      -- Files uses Git name colors; the dedicated Git source renders its own markers.
      git_status = { symbols = { added = "", modified = "", deleted = "", renamed = "", untracked = "",
        ignored = "", unstaged = "", staged = "", conflict = use_icons and "" or "!" } },
    },
  } },
  { "akinsho/bufferline.nvim", opts = { options = {
    always_show_bufferline = true, show_buffer_icons = false,
    diagnostics_indicator = function(_, _, diagnostics)
      return vim.trim((diagnostics.error and diagnostics_icons.Error .. diagnostics.error .. " " or "")
        .. (diagnostics.warning and diagnostics_icons.Warn .. diagnostics.warning or ""))
    end,
    persist_buffer_sort = false,
    sort_by = function(a,b) return require("config.tabs").compare(a,b) end,
    separator_style = "thin", buffer_close_icon = "×", close_icon = "×",
    indicator = { style = "icon", icon = "" },
    modified_icon = "●", left_trunc_marker = "<", right_trunc_marker = ">",
    close_command = function(buf) require("config.ide").close_buffer(buf) end,
    left_mouse_command = function(buf)
      require("config.ide").open_file(nil, buf)
      if vim.bo.modifiable and vim.bo.buftype == "" then vim.cmd("startinsert") end
    end,
    right_mouse_command = function(buf) require("config.ide").tab_menu(buf) end,
    middle_mouse_command = function(buf) require("config.ide").close_buffer(buf) end,
    offsets = {},
    custom_filter = function(buf) return not vim.b[buf].ide_diff_before end,
    name_formatter = function(buf)
      if vim.b[buf.bufnr].ide_diff_file then return vim.fn.fnamemodify(vim.b[buf.bufnr].ide_diff_file, ":t") .. " (diff)" end
    end,
  } }, config = function(_, opts)
    require("bufferline").setup(opts)
    vim.o.tabline = require("config.ide").menu_bar()
    vim.api.nvim_create_autocmd({ "BufAdd", "BufDelete" }, { callback = function()
      vim.schedule(function() if _G.nvim_bufferline then pcall(_G.nvim_bufferline) end; vim.cmd("redrawstatus") end)
    end })
  end },
  { "nvim-lualine/lualine.nvim", opts = function(_, opts)
    -- The menu component already contains the source's complete statusline,
    -- including alignment. Do not append a second middle divider to it.
    opts.options.always_divide_middle = false
    opts.extensions = opts.extensions or {}
    opts.extensions[#opts.extensions + 1] = {
      filetypes = { "NvMenu" },
      sections = { lualine_a = { { function() return vim.b.ide_menu_statusline or "" end,
        padding = 0, separator = "" } } },
    }
    opts.options.theme = require("config.colors").statusline()
    opts.options.component_separators = { left = "|", right = "|" }
    opts.options.section_separators = { left = "", right = "" }
    opts.sections.lualine_a = { "mode" }
    opts.sections.lualine_b = { { function()
      return (require("config.git_sync").branch():gsub("%%", "%%%%"))
    end, icon = "git", on_click = function(_, button)
      if button == "l" and require("config.panel_mouse").statusline_click() then
        vim.schedule(function() require("config.git").branches() end)
      end
    end }, { function() return require("config.git_sync").label() end,
      cond = function() return require("config.git_sync").visible() end,
      color = require("config.colors").git_sync(), padding = { left = 1, right = 1 },
      on_click = function(_, button)
        if button == "l" and require("config.panel_mouse").statusline_click() then
          vim.schedule(function() require("config.git_sync").sync() end)
        end
      end,
    } }
    opts.sections.lualine_c = { { "filename", path = 1 }, "diff", { "diagnostics", on_click = function(_, button)
      if button == "l" and require("config.panel_mouse").statusline_click() then vim.schedule(function()
        local problems = require("config.problems")
        if not problems.view then problems.open() end
      end) end
    end } }
    opts.sections.lualine_x = { "encoding", "fileformat", "filetype" }
    opts.sections.lualine_y = { "progress" }
    opts.sections.lualine_z = { "location" }
    -- Tool extensions replace the regular sections. Retain their own details
    -- while showing the same project Git buttons in every focused panel.
    -- Menus already carry the complete statusline captured from their source.
    for index, extension in ipairs(opts.extensions) do
      if type(extension) == "string" then extension = require("lualine.extensions." .. extension) end
      if not vim.tbl_contains(extension.filetypes or {}, "NvMenu") then
        extension = vim.deepcopy(extension)
        extension.sections = extension.sections or {}
        local git = vim.deepcopy(opts.sections.lualine_b)
        vim.list_extend(git, extension.sections.lualine_b or {})
        extension.sections.lualine_b = git
        opts.extensions[index] = extension
      end
    end
  end },
  { "folke/snacks.nvim", opts = {
    dashboard = { enabled = false }, scroll = { enabled = false },
    terminal = { win = { position = "bottom", relative = "win", height = 0.25, stack = false, resize = false }, shell = "/bin/bash" },
    input = { win = { keys = {
      i_esc = { "<esc>", { "cmp_close", "cancel" }, mode = "i", expr = true },
    }, on_win = function(win)
      require("config.popup_ui").register(win.win, function() win:execute("cancel") end)
    end } },
    picker = {
      win = { input = { keys = { ["<Esc>"] = { "cancel", mode = { "n", "i" } } } } },
      on_show = function(picker)
        require("config.popup_ui").register(picker.layout.root.win, function() picker:close() end)
      end,
      icons = { files = { enabled = false }, tree = { vertical = "│ ", middle = "├─", last = "└─" } },
    },
  } },
  { "sindrets/diffview.nvim", cmd = { "DiffviewOpen", "DiffviewFileHistory" }, opts = { use_icons = false } },
  { "lewis6991/gitsigns.nvim", opts = function(_, opts)
    -- Gitsigns hides its built-in annotation in Insert mode; our editor uses
    -- Insert by default, so keep one shared annotation for both modes.
    opts.current_line_blame = false
    require("config.git_line_blame").setup()
  end },
  { "nvzone/menu", lazy = true, dependencies = { "nvzone/volt" } },
  { "rcarriga/nvim-dap-ui", opts = function(_, opts)
    opts.expand_lines = false
    opts.floating = { border = "rounded", max_width = 80, max_height = 20 }
    opts.select_window = function() return require("config.ide").editor_window() end
    opts.icons = { expanded = "v", collapsed = ">", current_frame = ">" }
    opts.controls = { enabled = true, icons = { pause = "||", play = ">", step_into = "v", step_over = ">|", step_out = "^", step_back = "<", run_last = "R", terminate = "X", disconnect = "D" } }
    opts.layouts = {}
  end, config = function(_, opts)
    require("dapui").setup(opts)
    require("config.debugger").setup(require("dap"))
  end, keys = {
    { "<leader>du", function() require("config.debugger").show() end, desc = "Debug sidebar" },
  } },
  { "mfussenegger/nvim-dap", keys = {
    { "<leader>dr", function() require("config.terminals").show_debug_console() end, desc = "Debug console" },
  } },
  -- Inspect values on demand; per-variable updates parse large files repeatedly.
  { "theHamsta/nvim-dap-virtual-text", enabled = false },
  { "mason-org/mason.nvim", opts = function(_, opts)
    opts.ensure_installed = opts.ensure_installed or {}
    vim.list_extend(opts.ensure_installed, {
      "lua-language-server", "stylua", "pyright", "ruff", "bash-language-server", "shfmt", "vtsls", "prettier", "debugpy", "codelldb", "js-debug-adapter",
    })
    -- Language extras also request these tools. Mason rejects a second
    -- installation while the first one is still in progress.
    local unique, seen = {}, {}
    for _, tool in ipairs(opts.ensure_installed or {}) do
      if not seen[tool] then unique[#unique + 1], seen[tool] = tool, true end
    end
    opts.ensure_installed = unique
  end },
  { "neovim/nvim-lspconfig", opts = { servers = { bashls = {}, clangd = { mason = false } } } },
}
