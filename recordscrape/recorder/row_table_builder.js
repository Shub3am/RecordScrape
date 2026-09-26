// Works out a repeating row, and names for the columns inside it, from the elements the user clicks.
// Must not change the page or talk to the recorder; the picker does both.

// The rows are the two children of the examples' lowest common ancestor that hold one example each,
// or are the examples themselves. Returns the row selector and its fallbacks, each matching both
// rows, with the row that holds the first example, or null when the examples are not inside two
// sibling rows that share a tag.
function buildRowSelectors(firstExample, secondExample) {
  if (firstExample.contains(secondExample) || secondExample.contains(firstExample)) return null;
  let rowContainer = firstExample.parentElement;
  while (!rowContainer.contains(secondExample)) {
    rowContainer = rowContainer.parentElement;
  }
  const [firstRow, secondRow] = [firstExample, secondExample].map((example) =>
    Array.from(rowContainer.children).find((child) => child.contains(example)),
  );
  const sharedClassNames = Array.from(firstRow.classList).filter((className) =>
    secondRow.classList.contains(className),
  );
  const rowPart = firstRow.tagName.toLowerCase() + buildClassPart(sharedClassNames);
  const rowSelectors = buildSelectors(rowContainer)
    .map((containerSelector) => `${containerSelector} > ${rowPart}`)
    .filter((rowSelector) => firstRow.matches(rowSelector) && secondRow.matches(rowSelector));
  if (rowSelectors.length === 0) return null;
  const [rowSelector, ...rowFallbackSelectors] = rowSelectors;
  return { rowSelector, rowFallbackSelectors, firstRow };
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
