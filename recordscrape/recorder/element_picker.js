// Lets the user click elements on this document to mark them for extraction, until they press Done.
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

// Must be installed before any other window listener in this script: its capture-phase listeners
// then run first, and stopImmediatePropagation keeps picking clicks away from action capture too.
function installElementPicker(sendToRecorder, activatePickerEvent) {
  let pickerPanel = null;
  let pickedCountLabel = null;
  let hoverBox = null;
  let pickedCount = 0;
  const originalStyleByMarkedElement = new Map();

  // Built with DOM calls, not innerHTML, because pages that enforce Trusted Types reject innerHTML.
  const openPicker = () => {
    pickerPanel = document.createElement('div');
    pickerPanel.style.cssText = `position: fixed; top: 16px; right: 16px; z-index: 2147483647;
      padding: 12px 16px; background: #fff; color: #111; border: 2px solid ${PICKER_COLOR};
      border-radius: 8px; font: 14px/1.4 system-ui, sans-serif;`;
    const instructions = document.createElement('div');
    instructions.textContent = 'Click elements to extract';
    pickedCountLabel = document.createElement('div');
    pickedCountLabel.textContent = `Picked: ${pickedCount}`;
    const doneButton = document.createElement('button');
    doneButton.id = PICKER_DONE_BUTTON_ID;
    doneButton.type = 'button';
    doneButton.textContent = 'Done';
    pickerPanel.append(instructions, pickedCountLabel, doneButton);
    hoverBox = document.createElement('div');
    hoverBox.style.cssText = `position: fixed; z-index: 2147483646; pointer-events: none;
      outline: 2px solid ${PICKER_COLOR}; display: none;`;
    document.body.append(pickerPanel, hoverBox);
  };

  const closePicker = () => {
    pickerPanel.remove();
    hoverBox.remove();
    pickerPanel = null;
    pickedCountLabel = null;
    hoverBox = null;
    for (const [markedElement, originalStyle] of originalStyleByMarkedElement) {
      if (originalStyle === null) {
        markedElement.removeAttribute('style');
      } else {
        markedElement.setAttribute('style', originalStyle);
      }
    }
    originalStyleByMarkedElement.clear();
  };

  const pickElement = (element) => {
    const [selector, ...fallbackSelectors] = buildSelectors(element);
    let attribute = 'textContent';
    if (element.tagName === 'IMG') attribute = 'src';
    else if (element.tagName === 'A') attribute = 'href';
    else if (element.hasAttribute('value')) attribute = 'value';
    const previewText = element.textContent.trim().substring(0, 30) || element.tagName;
    sendToRecorder({
      kind: 'pick',
      pickedElement: {
        selector,
        fallbackSelectors,
        tagName: element.tagName,
        attribute,
        preview: `${previewText}...`,
      },
    });
    if (!originalStyleByMarkedElement.has(element)) {
      const originalStyle = element.getAttribute('style');
      originalStyleByMarkedElement.set(element, originalStyle);
      // Marked through the attribute, not element.style: Chromium writes element.style changes to
      // the attribute lazily, and removeAttribute('style') before that write leaves style="".
      element.setAttribute('style', `${originalStyle ?? ''}; outline: 2px solid ${PICKER_COLOR}`);
    }
    pickedCount += 1;
    pickedCountLabel.textContent = `Picked: ${pickedCount}`;
  };

  const handleEventWhilePicking = (event) => {
    if (pickerPanel === null) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (event.type !== 'click') return;
    if (event.target.closest(`#${PICKER_DONE_BUTTON_ID}`)) {
      closePicker();
    } else if (!pickerPanel.contains(event.target)) {
      pickElement(event.target);
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
    if (pickerPanel === null) openPicker();
  });
}
