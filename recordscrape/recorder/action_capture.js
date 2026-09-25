// Turns the user's clicks, typing and page scrolling on this document into recorder actions.
// Must not decide how actions reach Python; sendToRecorder owns delivery.

const SCROLL_SETTLE_MS = 200;

function startActionCapture(sendToRecorder) {
  const sendAction = (action) => sendToRecorder({ kind: 'action', action });
  const describeTarget = (element) => {
    const [selector, ...fallbackSelectors] = buildSelectors(element);
    return { selector, fallbackSelectors };
  };

  // Capture phase on window runs before any page listener can stop the event.
  window.addEventListener(
    'click',
    (event) => {
      sendAction({ type: 'click', ...describeTarget(event.target) });
    },
    true,
  );
  window.addEventListener(
    'input',
    (event) => {
      const { target } = event;
      // Clicking a label also clicks its checkbox, so replaying the clicks alone can toggle it back.
      // The final checked state lets replay settle it. Other fields get no key at all, because
      // Playwright turns an undefined property into None rather than dropping it.
      const checkedState =
        target.type === 'checkbox' || target.type === 'radio' ? { checked: target.checked } : {};
      sendAction({ type: 'input', ...describeTarget(target), value: target.value, ...checkedState });
    },
    true,
  );
  let scrollSettleTimer;
  window.addEventListener('scroll', () => {
    clearTimeout(scrollSettleTimer);
    scrollSettleTimer = setTimeout(() => {
      sendAction({ type: 'scroll', x: window.scrollX, y: window.scrollY });
    }, SCROLL_SETTLE_MS);
  });
}
