// Lets the user click elements on this document to mark them for extraction, until they press Done:
// single elements, or in row mode a repeating row and the columns inside it.
// Must not let a picking click reach the page, and must leave the page's own styles as it found them.

const PICKER_DONE_BUTTON_ID = 'recordscrape-picker-done';
const PICKER_COLOR = '#4f46e5';
const EVENTS_BLOCKED_WHILE_PICKING = [
  'click',
  'dblclick',
  'mousedown',
  'mouseup',
  'pointerdown',
  'pointerup',
  'contextmenu',
  'touchstart',
  'touchend',
  'keydown',
  'keypress',
  'submit',
];
const INSTRUCTIONS_BY_MODE = {
  elements: 'Click elements to extract',
  rows: 'Click the same field in two different rows',
};

function extractedAttribute(element) {
  if (element.tagName === 'IMG') return 'src';
  if (element.tagName === 'A') return 'href';
  if (element.hasAttribute('value')) return 'value';
  return 'textContent';
}

// Must be installed before any other window listener in this script: its capture-phase listeners
// then run first, and stopImmediatePropagation keeps picking clicks away from action capture too.
function installElementPicker(sendToRecorder, activatePickerEvent, activateRowPickerEvent) {
  let pickerMode = null;
  let pickerPanel = null;
  let statusLabel = null;
  let hoverBox = null;
  let pickedCount = 0;
  let firstRowExample = null;
  let rowTable = null;
  let matchedRowCount = 0;
  const originalStyleByMarkedElement = new Map();

  // Built with DOM calls, not innerHTML, because pages that enforce Trusted Types reject innerHTML.
  const openPicker = (mode) => {
    pickerMode = mode;
    pickerPanel = document.createElement('div');
    pickerPanel.style.cssText = `position: fixed; top: 16px; right: 16px; z-index: 2147483647;
      padding: 12px 16px; background: #fff; color: #111; border: 2px solid ${PICKER_COLOR};
      border-radius: 8px; font: 14px/1.4 system-ui, sans-serif;`;
    const instructions = document.createElement('div');
    instructions.textContent = INSTRUCTIONS_BY_MODE[mode];
    statusLabel = document.createElement('div');
    statusLabel.textContent = mode === 'elements' ? `Picked: ${pickedCount}` : 'Rows: none yet';
    const doneButton = document.createElement('button');
    doneButton.id = PICKER_DONE_BUTTON_ID;
    doneButton.type = 'button';
    doneButton.textContent = 'Done';
    pickerPanel.append(instructions, statusLabel, doneButton);
    hoverBox = document.createElement('div');
    hoverBox.style.cssText = `position: fixed; z-index: 2147483646; pointer-events: none;
      outline: 2px solid ${PICKER_COLOR}; display: none;`;
    document.body.append(pickerPanel, hoverBox);
  };

  const closePicker = () => {
    pickerPanel.remove();
    hoverBox.remove();
    pickerMode = null;
    pickerPanel = null;
    statusLabel = null;
    hoverBox = null;
    firstRowExample = null;
    rowTable = null;
    for (const [markedElement, originalStyle] of originalStyleByMarkedElement) {
      if (originalStyle === null) {
        markedElement.removeAttribute('style');
      } else {
        markedElement.setAttribute('style', originalStyle);
      }
    }
    originalStyleByMarkedElement.clear();
  };

  const markElement = (element, outlineStyle) => {
    if (originalStyleByMarkedElement.has(element)) return;
    const originalStyle = element.getAttribute('style');
    originalStyleByMarkedElement.set(element, originalStyle);
    // Marked through the attribute, not element.style: Chromium writes element.style changes to
    // the attribute lazily, and removeAttribute('style') before that write leaves style="".
    element.setAttribute('style', `${originalStyle ?? ''}; outline: 2px ${outlineStyle} ${PICKER_COLOR}`);
  };

  const pickElement = (element) => {
    const [selector, ...fallbackSelectors] = buildSelectors(element);
    const previewText = element.textContent.trim().substring(0, 30) || element.tagName;
    sendToRecorder({
      kind: 'pick',
      pickedElement: {
        selector,
        fallbackSelectors,
        tagName: element.tagName,
        attribute: extractedAttribute(element),
        preview: `${previewText}...`,
      },
    });
    markElement(element, 'solid');
    pickedCount += 1;
    statusLabel.textContent = `Picked: ${pickedCount}`;
  };

  const addColumn = (element, row) => {
    const [selector, ...fallbackSelectors] = buildSelectors(element, row);
    const takenColumnNames = rowTable.columns.map((column) => column.name);
    rowTable.columns.push({
      name: buildColumnName(element, takenColumnNames),
      selector,
      fallbackSelectors,
      attribute: extractedAttribute(element),
    });
    sendToRecorder({ kind: 'table', table: rowTable });
    markElement(element, 'solid');
    statusLabel.textContent = `Rows: ${matchedRowCount}, columns: ${rowTable.columns.length}`;
  };

  const pickForRowTable = (element) => {
    if (rowTable !== null) {
      const row = element.closest(rowTable.rowSelector);
      if (row === null) {
        statusLabel.textContent = 'Click inside a highlighted row';
        return;
      }
      addColumn(element, row);
      return;
    }
    if (firstRowExample === null) {
      firstRowExample = element;
      markElement(element, 'solid');
      statusLabel.textContent = 'Now click the same field in another row';
      return;
    }
    const rowSelection = buildRowSelectors(firstRowExample, element);
    if (rowSelection === null) {
      statusLabel.textContent = 'Not a field inside another row. Click the same field in another row';
      return;
    }
    const { rowSelector, rowFallbackSelectors, firstRow } = rowSelection;
    rowTable = { rowSelector, rowFallbackSelectors, columns: [] };
    const matchedRows = document.querySelectorAll(rowSelector);
    for (const matchedRow of matchedRows) {
      markElement(matchedRow, 'dashed');
    }
    matchedRowCount = matchedRows.length;
    markElement(element, 'solid');
    addColumn(firstRowExample, firstRow);
  };

  const handleEventWhilePicking = (event) => {
    if (pickerPanel === null) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (event.type !== 'click') return;
    if (event.target.closest(`#${PICKER_DONE_BUTTON_ID}`)) {
      closePicker();
    } else if (pickerPanel.contains(event.target)) {
      return;
    } else if (pickerMode === 'elements') {
      pickElement(event.target);
    } else {
      pickForRowTable(event.target);
    }
  };

  for (const eventType of EVENTS_BLOCKED_WHILE_PICKING) {
    window.addEventListener(eventType, handleEventWhilePicking, true);
  }
  window.addEventListener(
    'mousemove',
    (event) => {
      if (pickerPanel === null || pickerPanel.contains(event.target)) return;
      const targetBounds = event.target.getBoundingClientRect();
      Object.assign(hoverBox.style, {
        display: 'block',
        top: `${targetBounds.top}px`,
        left: `${targetBounds.left}px`,
        width: `${targetBounds.width}px`,
        height: `${targetBounds.height}px`,
      });
    },
    true,
  );
  window.addEventListener(activatePickerEvent, () => {
    if (pickerPanel === null) openPicker('elements');
  });
  window.addEventListener(activateRowPickerEvent, () => {
    if (pickerPanel === null) openPicker('rows');
  });
}
