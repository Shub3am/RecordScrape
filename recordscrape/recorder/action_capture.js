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
      sendAction({ type: 'input', ...describeTarget(event.target), value: event.target.value });
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
