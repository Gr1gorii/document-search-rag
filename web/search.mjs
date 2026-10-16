const STOP_WORDS = new Set('a an and are as at be by can do does for from how i in is it of on or that the this to was what when where which why with you your using use fastapi please explain tell me about would should my'.split(' '));
const tokenize = text => (text.toLowerCase().match(/[\p{L}\p{N}_]+/gu) || []).filter(word => !STOP_WORDS.has(word));
export class SearchIndex {
  constructor(chunks) {
    if (!chunks.length) throw new Error('Corpus is empty');
    this.chunks = chunks;
    this.terms = chunks.map(c => {
      const counts = new Map();
      for (const word of tokenize(`${c.title} ${c.section} ${c.text}`)) counts.set(word, (counts.get(word) || 0) + 1);
      return counts;
    });
    this.lengths = this.terms.map(counts => [...counts.values()].reduce((a, b) => a + b, 0));
    this.averageLength = this.lengths.reduce((a, b) => a + b, 0) / chunks.length;
    const documentCounts = new Map();
    for (const counts of this.terms) for (const word of counts.keys()) documentCounts.set(word, (documentCounts.get(word) || 0) + 1);
    this.idf = new Map([...documentCounts].map(([word, count]) => [word, Math.log(1 + (chunks.length - count + 0.5) / (count + 0.5))]));
  }
  search(question, topK = 4) {
    const query = [...new Set(tokenize(question))].sort();
    return this.chunks.map((chunk, i) => {
      let score = 0;
      for (const word of query) {
        const frequency = this.terms[i].get(word) || 0;
        if (frequency) score += this.idf.get(word) * frequency * 2.5 / (frequency + 1.5 * (0.25 + 0.75 * this.lengths[i] / this.averageLength));
      }
      return {...chunk, score};
    }).filter(hit => hit.score > 0).sort((a, b) => b.score - a.score || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0)).slice(0, topK).map(hit => ({...hit, score: Number(hit.score.toFixed(3))}));
  }
}
