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
  result.replaceChildren(element('p', 'Reading the documentation… Local generation may take a few seconds.'));
  result.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch('/api/ask', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: question.value.trim(), mode: document.querySelector('#mode').value }),
      signal: AbortSignal.timeout(100000),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Please check your question and try again.');
    render(data);
  } catch (error) {
    result.replaceChildren(element('span', 'Request failed', 'badge error'),
      element('p', error.name === 'TimeoutError' ? 'The local model took too long. Please try again.' : error.message),
      element('p', 'Search excerpts only works without Ollama.'));
  } finally {
    submit.disabled = false;
    result.setAttribute('aria-busy', 'false');
  }
});

document.querySelectorAll('[data-question]').forEach((button) => {
  button.addEventListener('click', () => { question.value = button.dataset.question; question.focus(); });
});

async function loadInfo() {
  try {
    const info = await (await fetch('/api/info')).json();
    document.querySelector('#pages').textContent = info.pages;
    document.querySelector('#chunks').textContent = info.chunks;
    document.querySelector('#model').textContent = info.model;
    const health = await (await fetch('/api/health')).json();
    document.querySelector('#health').textContent = health.ollama ? 'Local model ready' : 'Ollama unavailable · search is ready';
  } catch {
    document.querySelector('#health').textContent = 'Could not check the connection';
  }
}
loadInfo();
