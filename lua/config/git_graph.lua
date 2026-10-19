-- Lua adaptation of LazyGit v0.50.0's graph.go and cell.go.
-- https://github.com/jesseduffield/lazygit/tree/v0.50.0/pkg/gui/presentation/graph
-- Copyright (c) 2018 Jesse Duffield; MIT license: LICENSES/lazygit.txt.
-- Positions are zero-based lanes; each lane renders two screen columns.
local M = {}
local TERMINATES, STARTS, CONTINUES = 0, 1, 2

local function next_pipes(previous, commit)
  local current, maximum = {}, 0
  for _, pipe in ipairs(previous) do
    maximum = math.max(maximum, pipe.to)
    if pipe.kind ~= TERMINATES then current[#current + 1] = pipe end
  end
  local position = maximum + 1
  for _, pipe in ipairs(current) do
    if pipe.target == commit.commit then position = pipe.to; break end
  end
  local taken, traversed, continuing = {}, {}, {}
  local result = {}
  local function add(from, to, source, target, kind, author)
    result[#result + 1] = { from = from, to = to, source = source, target = target, kind = kind, author = author }
  end
  local function traverse(from, to)
    for lane = math.min(from, to), math.max(from, to) do traversed[lane] = true end
    taken[to] = true
  end
  add(position, position, commit.commit, commit.parents[1] or "EMPTY_TREE", STARTS, commit.author)
  for _, pipe in ipairs(current) do
    if pipe.target ~= commit.commit then continuing[pipe.to] = true end
  end
  for _, pipe in ipairs(current) do
    if pipe.target == commit.commit then
      add(pipe.to, position, pipe.source, pipe.target, TERMINATES, pipe.author)
      traverse(pipe.to, position)
    elseif pipe.to < position then
      local available = 0
      while traversed[available] do available = available + 1 end
      add(pipe.to, available, pipe.source, pipe.target, CONTINUES, pipe.author)
      traverse(pipe.to, available)
    end
  end
  for index = 2, #commit.parents do
    local available = 0
    while taken[available] or continuing[available] do available = available + 1 end
    add(position, available, commit.commit, commit.parents[index], STARTS, commit.author)
    taken[available] = true
  end
  for _, pipe in ipairs(current) do
    if pipe.target ~= commit.commit and pipe.to > position then
      local last = pipe.to
      for lane = pipe.to, position + 1, -1 do
        if taken[lane] or traversed[lane] then break end
        last = lane
      end
      add(pipe.to, last, pipe.source, pipe.target, CONTINUES, pipe.author)
      traverse(pipe.to, last)
    end
  end
  table.sort(result, function(a, b) return a.to == b.to and a.kind < b.kind or a.to < b.to end)
  return result
end

function M.build(commits)
  if #commits == 0 then return {} end
  local previous = { { from = 0, to = 0, source = "START", target = commits[1].commit, kind = STARTS } }
  local sets = {}
  for index, commit in ipairs(commits) do
    previous = next_pipes(previous, commit)
    sets[index] = previous
  end
  return sets
end

-- North/south/west/east masks, including LazyGit's intentional vertical
-- overpasses: a crossing is │─ rather than a false four-way junction.
local symbols = {
  [0] = { " ", " " }, { "╵", " " }, { "╷", " " }, { "│", " " },
  { "─", " " }, { "╯", " " }, { "╮", " " }, { "│", " " },
  { "╶", "─" }, { "╰", "─" }, { "╭", "─" }, { "│", "─" },
  { "─", "─" }, { "┴", "─" }, { "┬", "─" }, { "│", "─" },
}

function M.render(pipes, selected, previous_hash)
  local maximum, position, starts = 0, 0, 0
  for _, pipe in ipairs(pipes) do
    if pipe.kind == STARTS then starts = starts + 1; position = pipe.from
    elseif pipe.kind == TERMINATES then position = pipe.to end
    maximum = math.max(maximum, pipe.from, pipe.to)
  end
  local cells = {}
  for lane = 0, maximum do cells[lane] = { mask = 0 } end
  local function set(lane, direction, style, override)
    local cell = cells[lane]
    cell.mask = bit.bor(cell.mask, direction)
    if direction == 8 then
      if not cell.right_style or override then cell.right_style = style end
    elseif direction ~= 4 or bit.band(cell.mask, 3) == 0 then cell.style = style end
  end
  local function paint(pipe, style, override)
    local left, right = math.min(pipe.from, pipe.to), math.max(pipe.from, pipe.to)
    if left ~= right then
      for lane = left + 1, right - 1 do set(lane, 4, style); set(lane, 8, style, override) end
      set(left, 8, style, override); set(right, 4, style)
    end
    if pipe.kind == STARTS or pipe.kind == CONTINUES then set(pipe.to, 2, style) end
    if pipe.kind == TERMINATES or pipe.kind == CONTINUES then set(pipe.from, 1, style) end
  end
  local highlight = selected ~= nil
  if previous_hash == selected then
    highlight = false
    for _, pipe in ipairs(pipes) do
      if pipe.source == selected and (pipe.kind ~= TERMINATES or pipe.from ~= pipe.to) then highlight = true end
    end
  end
  local function is_selected(pipe) return highlight and pipe.source == selected end
  local colors = require("config.colors")
  for _, pipe in ipairs(pipes) do
    if not is_selected(pipe) and pipe.kind == STARTS then paint(pipe, colors.git_author(pipe.author), true) end
  end
  for _, pipe in ipairs(pipes) do
    if not is_selected(pipe) and pipe.kind ~= STARTS
      and not (pipe.kind == TERMINATES and pipe.from == position and pipe.to == position) then
      paint(pipe, colors.git_author(pipe.author), false)
    end
  end
  for _, pipe in ipairs(pipes) do
    if is_selected(pipe) then
      for lane = math.min(pipe.from, pipe.to), math.max(pipe.from, pipe.to) do cells[lane].mask = 0 end
    end
  end
  for _, pipe in ipairs(pipes) do
    if is_selected(pipe) then
      paint(pipe, "DesktopCommitGraphSelected", true)
      if pipe.to == position then cells[pipe.to].style = "DesktopCommitGraphSelected" end
    end
  end
  local chunks = {}
  for lane = 0, maximum do
    local cell = cells[lane]
    local chars = symbols[cell.mask]
    chunks[#chunks + 1] = { lane == position and (starts > 1 and "⏣" or "◯") or chars[1], cell.style }
    chunks[#chunks + 1] = { chars[2], chars[2] ~= " " and (cell.right_style or cell.style) or nil }
  end
  return chunks
end

return M
