-- Make every table a simple pipe table so it survives as plain markdown.
-- Google Docs exports put each cell's lines in separate paragraphs and mark every row as a header.
-- Cell paragraphs are joined with "; " and only the first row stays a header row.

local function flatten(cell)
  local inlines = pandoc.List()
  for _, block in ipairs(cell.contents) do
    if block.t == 'Para' or block.t == 'Plain' then
      if #inlines > 0 then inlines:insert(pandoc.Str('; ')) end
      inlines:extend(block.content)
    end
  end
  cell.contents = { pandoc.Plain(inlines) }
  cell.col_span = 1
  cell.row_span = 1
end

function Table(tbl)
  local head_rows = tbl.head.rows
  local body_rows = pandoc.List()
  for i, row in ipairs(head_rows) do
    if i > 1 then body_rows:insert(row) end
  end
  if #head_rows > 1 then
    tbl.head.rows = { head_rows[1] }
  end
  for _, body in ipairs(tbl.bodies) do
    for _, row in ipairs(body.body) do body_rows:insert(row) end
  end
  for _, row in ipairs(tbl.head.rows) do
    for _, cell in ipairs(row.cells) do flatten(cell) end
  end
  for _, row in ipairs(body_rows) do
    for _, cell in ipairs(row.cells) do flatten(cell) end
  end
  if #tbl.bodies == 0 then
    tbl.bodies = { { attr = pandoc.Attr(), row_head_columns = 0, head = {}, body = body_rows } }
  else
    tbl.bodies[1].body = body_rows
    for i = #tbl.bodies, 2, -1 do tbl.bodies[i] = nil end
  end
  return tbl
end
