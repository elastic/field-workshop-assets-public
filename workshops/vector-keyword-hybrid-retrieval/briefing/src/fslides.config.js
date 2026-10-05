module.exports = {
  name: 'Vector search: the briefing',

  // Slide filenames in order, relative to the slides/ directory
  slides: [
    '01-title.html',
    '02-vector-database.html',
    '03-words-vs-meaning.html',
    '04-lexical-bm25.html',
    '05-text-to-vector.html',
    '06-semantic-text-eis.html',
    '07-indexing-algorithms.html',
    '08-choosing-index.html',
    '09-bbq.html',
    '10-scores-dont-mix.html',
    '11-relevance-pyramid.html',
    '12-recall-precision.html',
    '13-rag-agents.html',
    '14-keeping-score.html',
    '15-ready.html',
  ],

  // Human-readable labels for the overview panel (must match slides array length)
  labels: [
    'Title',
    'Elasticsearch is a Vector Database',
    'Words vs meaning (interactive)',
    'Lexical search: BM25 in one slide (interactive)',
    'From text to vector embedding (interactive)',
    'semantic_text + inference endpoints',
    'Three vector indexing algorithms (interactive)',
    'Choosing your vector index',
    'BBQ: 32x smaller vectors (interactive)',
    'Scores don\'t mix: fuse by rank (interactive)',
    'The relevance pyramid (interactive)',
    'Recall, then precision: reranking',
    'RAG and agents',
    'Keeping score: MRR (interactive)',
    'Ready for Lab 1',
  ],
};
