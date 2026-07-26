// Delivers messages from this document to the Python recorder through its exposed binding, in order.
// Must not decide what gets recorded; callers build the messages.

// The binding can be missing when this runs: Patchright only exposes it after the backend's
// bindings-ready announcement (see recordscrape/browsers/CLAUDE.md), so messages wait until then.
function createRecorderChannel(recordBinding, bindingsReadyEvent) {
  const pendingMessages = [];
  const flushPendingMessages = () => {
    while (pendingMessages.length > 0) {
      window[recordBinding](pendingMessages.shift());
    }
  };
  window.addEventListener(bindingsReadyEvent, flushPendingMessages);
  return (recorderMessage) => {
    if (typeof window[recordBinding] !== 'function') {
      pendingMessages.push(recorderMessage);
      return;
    }
    flushPendingMessages();
    window[recordBinding](recorderMessage);
  };
}
