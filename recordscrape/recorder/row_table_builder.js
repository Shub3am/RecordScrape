// Works out a repeating row, and names for the columns inside it, from the elements the user clicks.
// Must not change the page or talk to the recorder; the picker does both.

// The rows are the two children of the examples' lowest common ancestor that hold one example each.
// Returns the row selector and its fallbacks, each matching both rows, or null when the examples
// are not inside two sibling rows that share a tag. An example that is its whole row is refused:
// the column reads through the row's querySelector, which never matches the row itself.
function buildRowSelectors(firstExample, secondExample) {
  if (firstExample.contains(secondExample) || secondExample.contains(firstExample)) return null;
  let rowContainer = firstExample.parentElement;
  while (!rowContainer.contains(secondExample)) {
    rowContainer = rowContainer.parentElement;
  }
  const [firstRow, secondRow] = [firstExample, secondExample].map((example) =>
    Array.from(rowContainer.children).find((child) => child.contains(example)),
  );
  if (firstRow === firstExample || secondRow === secondExample) return null;
  const sharedClassPart = Array.from(firstRow.classList)
    .filter((className) => secondRow.classList.contains(className))
    .map((className) => `.${CSS.escape(className)}`)
    .join('');
  const rowPart = firstRow.tagName.toLowerCase() + sharedClassPart;
  const rowSelectors = buildSelectors(rowContainer)
    .map((containerSelector) => `${containerSelector} > ${rowPart}`)
    .filter((rowSelector) => {
      const matchedRows = Array.from(document.querySelectorAll(rowSelector));
      return matchedRows.includes(firstRow) && matchedRows.includes(secondRow);
    });
  if (rowSelectors.length === 0) return null;
  const [rowSelector, ...rowFallbackSelectors] = rowSelectors;
  return { rowSelector, rowFallbackSelectors };
}

// Names a column after the element's first class, else by its position, then adds a numeric
// suffix until the name is not already taken, because each name is a key in every extracted row.
function buildColumnName(element, takenColumnNames) {
  const baseName = element.classList[0] ?? `column_${takenColumnNames.length + 1}`;
  let columnName = baseName;
  for (let suffix = 2; takenColumnNames.includes(columnName); suffix += 1) {
    columnName = `${baseName}_${suffix}`;
  }
  return columnName;
}
