import json
import shutil
import subprocess

import pytest

from doclens.config import ROOT
from doclens.retrieval import SearchIndex


def test_browser_search_matches_python() -> None:
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for the browser search parity check')
    questions = ['HTTPException 404', 'required query parameter', 'background tasks',
                 'zxqvkjxyz', 'response model', 'file upload', 'CORS middleware']
    script = '''import {readFileSync} from 'node:fs';
import {SearchIndex} from './web/search.mjs';
const index = new SearchIndex(JSON.parse(readFileSync('web/chunks.json', 'utf8')));
console.log(JSON.stringify(JSON.parse(process.argv[1]).map(q => index.search(q))));'''
    result = subprocess.run([node, '--input-type=module', '-e', script, json.dumps(questions)],
                            cwd=ROOT, capture_output=True, text=True, check=True)
    browser_hits = json.loads(result.stdout)
    index = SearchIndex.load(ROOT / 'data/chunks.json')
    assert browser_hits == [[hit.to_dict() for hit in index.search(q)] for q in questions]
    assert json.loads((ROOT / 'web/chunks.json').read_text()) == json.loads(
        (ROOT / 'data/chunks.json').read_text())
