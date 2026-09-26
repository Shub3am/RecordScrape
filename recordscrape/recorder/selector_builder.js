// Builds CSS selectors that match exactly one element, most stable first, so a replay can fall back
// to the next selector when the page changes. Must not touch the page or talk to the recorder.

const TEST_ID_ATTRIBUTES = ['data-testid', 'data-test-id', 'data-test', 'data-qa', 'data-cy'];
const MAX_SELECTORS_PER_ELEMENT = 3;

// With a root, the selectors are relative to it, for the root's own querySelector. Ids are skipped
// then, because an id can only match inside one of the roots the selector is meant for.
function buildSelectors(element, root = null) {
  const tagName = element.tagName.toLowerCase();
  const candidateSelectors = [];
  for (const attributeName of TEST_ID_ATTRIBUTES) {
    if (element.hasAttribute(attributeName)) {
      candidateSelectors.push(`[${attributeName}="${CSS.escape(element.getAttribute(attributeName))}"]`);
    }
  }
  if (element.getAttribute('name')) {
    candidateSelectors.push(`${tagName}[name="${CSS.escape(element.getAttribute('name'))}"]`);
  }
  if (element.id && root === null) {
    candidateSelectors.push(`#${CSS.escape(element.id)}`);
  }
  if (element.classList.length > 0) {
    const classPart = Array.from(element.classList, (className) => `.${CSS.escape(className)}`).join('');
    candidateSelectors.push(tagName + classPart);
  }
  const uniqueSelectors = candidateSelectors.filter((selector) => matchesOnly(selector, element, root));
  uniqueSelectors.push(buildPositionPath(element, root));
  return [...new Set(uniqueSelectors)].slice(0, MAX_SELECTORS_PER_ELEMENT);
}

function matchesOnly(selector, element, root = null) {
  const matchedElements = (root ?? element.ownerDocument).querySelectorAll(selector);
  return matchedElements.length === 1 && matchedElements[0] === element;
}

// Walks up to the nearest ancestor with a unique id, or to <html>, naming each step by its position
// among siblings of the same tag. Always unique, but breaks when the page's structure shifts. The
// element's own id is skipped so the path stays a fallback that does not depend on that id. With a
// root, the walk stops there and the path starts at `:scope`.
function buildPositionPath(element, root = null) {
  const pathSegments = [];
  let currentElement = element;
  while (currentElement !== root && currentElement.parentElement) {
    const sameTagSiblings = Array.from(currentElement.parentElement.children).filter(
      (sibling) => sibling.tagName === currentElement.tagName,
    );
    const position = sameTagSiblings.indexOf(currentElement) + 1;
    pathSegments.unshift(`${currentElement.tagName.toLowerCase()}:nth-of-type(${position})`);
    currentElement = currentElement.parentElement;
    const idSelector = root === null && currentElement.id ? `#${CSS.escape(currentElement.id)}` : '';
    if (idSelector && matchesOnly(idSelector, currentElement)) {
      return [idSelector, ...pathSegments].join(' > ');
    }
  }
  const pathStart = root === null ? currentElement.tagName.toLowerCase() : ':scope';
  return [pathStart, ...pathSegments].join(' > ');
}
