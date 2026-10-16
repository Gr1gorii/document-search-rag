import { SearchIndex } from './search.mjs';
let index;
const form = document.querySelector('#ask-form');
const question = document.querySelector('#question');
const submit = document.querySelector('#submit');
const result = document.querySelector('#result');

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function sourceCard(source, label) {
  const card = element('div', null, 'source');
  const link = element('a', `${label ? `[${label}] ` : ''}${source.title} · ${source.section}`);
  link.href = source.url;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  card.append(link, element('small', `FastAPI documentation · ${source.id}`));
  const details = element('details');
  details.append(element('summary', 'Inspect excerpt'), element('pre', source.text));
  card.append(details);
  return card;
}

function render(data) {
  result.replaceChildren();
  const head = element('div', null, 'result-head');
  const labels = { answered: 'Answer with sources', abstained: 'Not enough evidence', search: 'Search results' };
  head.append(element('span', labels[data.status], `badge ${data.status}`),
    element('span', `${(data.latency_ms / 1000).toFixed(2)} s`, 'time'));
  result.append(head);
  if (data.answer) result.append(element('div', data.answer, 'answer'));
  for (const citation of data.citations) result.append(sourceCard(citation, citation.label));
  if (data.status === 'search') {
    result.append(element('p', 'These excerpts are ranked search results. They are not a generated answer.'));
    if (!data.retrieved.length) result.append(element('p', 'No matching excerpts. Try a more specific English question.'));
    for (const hit of data.retrieved) result.append(sourceCard(hit));
  } else if (data.retrieved.length) {
    const details = element('details', null, 'retrieval');
    details.append(element('summary', 'Inspect all retrieved excerpts'));
    for (const hit of data.retrieved) details.append(sourceCard(hit));
    result.append(details);
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!form.reportValidity() || submit.disabled) return;
  submit.disabled = true;
  const searchOnly = document.querySelector('#mode').value === 'search';
  result.replaceChildren(element('p', searchOnly ? 'Searching the documentation…' : 'Reading the documentation… Local generation may take a few seconds.'));
  result.setAttribute('aria-busy', 'true');
  try {
    if (!index) throw new Error('Search is still loading. Please try again.');
    const start = performance.now();
    const data = {status: 'search', answer: '', citations: [], retrieved: index.search(question.value.trim()), latency_ms: performance.now() - start};
    render(data);
  } catch (error) {
    result.replaceChildren(element('span', 'Request failed', 'badge error'),
      element('p', error.name === 'TimeoutError' ? 'The local model took too long. Please try again.' : error.message),
      element('p', 'Reload this page if the search index could not be loaded.'));
  } finally {
    submit.disabled = false;
    result.setAttribute('aria-busy', 'false');
  }
});

document.querySelectorAll('[data-question]').forEach((button) => {
  button.addEventListener('click', () => { question.value = button.dataset.question; question.focus(); });
});

async function loadInfo() {
  submit.disabled = true;
  try {
    const response = await fetch('./chunks.json');
    if (!response.ok) throw new Error('Corpus unavailable');
    const chunks = await response.json();
    index = new SearchIndex(chunks);
    document.querySelector('#pages').textContent = new Set(chunks.map(c => c.page)).size;
    document.querySelector('#chunks').textContent = chunks.length;
    document.querySelector('#health').textContent = 'Excerpt search ready';
    submit.disabled = false;
  } catch {
    document.querySelector('#health').textContent = 'Could not load search. Please reload.';
  }
}
loadInfo();
