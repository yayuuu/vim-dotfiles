-- Observe mouse-reporting requests through jobstart's public stdout callback.
-- Neovim still encodes/forwards the actual mouse events to the child process.
local M = {}
local tracking = { [1000] = true, [1002] = true, [1003] = true }

function M.feed(state, data)
  local text = (state.pending or "") .. table.concat(data, "\n")
  state.pending = nil
  local at = 1
  while at <= #text do
    if state.string then
      -- OSC/DCS/APC/PM/SOS contents are data, even if they contain CSI text.
      local stop = text:find("\27\\", at, true)
      local bell = text:find("\7", at, true)
      if bell and (not stop or bell < stop) then
        at, state.string = bell + 1, nil
      elseif stop then
        at, state.string = stop + 2, nil
      else
        state.pending = text:sub(-1) == "\27" and "\27" or nil
        return
      end
    else
      local start = text:find("\27", at, true)
      if not start then return end
      local kind = text:sub(start + 1, start + 1)
      if kind == "" then state.pending = "\27"; return end
      at = start + 2
      if kind == "[" then
        local finish = text:find("[@-~]", at)
        if not finish then
          if #text - start < 64 then state.pending = text:sub(start) end
          return
        end
        local params, command = text:sub(at, finish - 1), text:sub(finish, finish)
        if (command == "h" or command == "l") and params:match("^%?[%d;]+$") then
          for mode in params:gmatch("%d+") do
            if tracking[tonumber(mode)] then state.enabled = command == "h" end
          end
        elseif params == "!" and command == "p" then state.enabled = false end
        at = finish + 1
      elseif kind == "]" or kind == "P" or kind == "_" or kind == "^" or kind == "X" then
        state.string = true
      elseif kind == "c" then state.enabled = false end
    end
  end
end

return M
