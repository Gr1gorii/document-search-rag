[English](README.md) | [Italiano](README.it.md)

# document-search-rag

[Demo di ricerca online](https://gr1gorii.github.io/document-search-rag/)

La demo gratuita cerca estratti della documentazione nel browser. La generazione con Qwen3 funziona in locale con Ollama; segui le istruzioni qui sotto.


Il nome pubblico è `document-search-rag`. La cartella e il pacchetto Python si chiamano `doclens`, come nei comandi qui sotto.

Un assistente locale per la documentazione di FastAPI: fai una domanda, recupera i passaggi pertinenti, ottieni una risposta dal modello e consulta le fonti. Se le informazioni trovate sembrano insufficienti, l'assistente può astenersi dal rispondere. La modalità di sola ricerca permette di leggere il testo recuperato senza generazione e confrontarlo con la risposta RAG.

document-search-rag usa Ollama e `qwen3:1.7b`. Non richiede chiavi API OpenAI né servizi a pagamento. La ricerca funziona anche quando Ollama non è disponibile.

## Esempio di utilizzo

Domanda: `How do I raise HTTPException with a 404 status?`

Una risposta effettiva dell'applicazione:

> Raise HTTPException with status_code=404. [S1]

La citazione `[S1]` rimanda alla sezione [Raise an HTTPException in your code](https://fastapi.tiangolo.com/tutorial/handling-errors/#raise-an-httpexception-in-your-code). Apri il passaggio nell'interfaccia per confrontare la risposta con la documentazione.

![Risposta di document-search-rag con una citazione e il passaggio della fonte aperto](reports/ui-answer.png)

La modalità di ricerca restituisce passaggi senza generare una risposta. Questo esempio cerca come dichiarare un parametro di query obbligatorio.

![Risultati di ricerca per un parametro di query obbligatorio nella documentazione FastAPI](reports/ui-search.png)

<details>
<summary>Vista mobile: risposta e fonti</summary>

<img src="reports/ui-mobile.png" alt="Risposta di document-search-rag con una fonte su uno schermo largo 390 pixel" width="390">

</details>

Gli screenshot mostrano l'applicazione locale in esecuzione con un'interfaccia essenziale: un campo per la domanda, i comandi, il risultato e l'elenco delle fonti. Contengono solo la pagina dell'applicazione, senza barra del browser, altre finestre o cursore. Lo stato iniziale è visibile in [ui-desktop.png](reports/ui-desktop.png).

## Risultati misurati

Corpus: 12 pagine ufficiali di FastAPI, suddivise in 135 passaggi. La tabella riporta le esecuzioni salvate con `qwen3:1.7b` su Apple M3 con 16 GB di RAM. Il set principale è stato usato durante lo sviluppo. Il nuovo set di 12 domande è stato valutato dopo aver fissato le soglie, senza ulteriori modifiche ai parametri.

| Verifica | Set principale: 60 domande | Nuovo set: 12 domande |
|---|---:|---:|
| Pagina attesa nei primi quattro risultati di ricerca | 45/45 con risposta nel corpus | 6/6 con risposta nel corpus |
| Astensione su domande fuori dal corpus | 15/15 | 6/6 |
| Astensione superflua su domande con risposta nel corpus | 3/45 | 2/6 |
| Presenza delle parole chiave attese nella risposta | 41/45 (91.11%) | 3/6 (50%) |
| Citazioni alla pagina attesa, tra quelle mostrate | 42/42 (100%) | 3/4 (75%) |
| Tempo delle risposte fornite, p50 / p95 | 2.43 / 3.36 s | 2.21 / 2.68 s |
| Errori tecnici | 0/60 | 0/12 |

**Superare una verifica non dimostra la correttezza dei fatti.** La corrispondenza delle parole chiave è solo un indicatore approssimativo. Un controllo a campione delle fonti ha rilevato un requisito `item:` inventato nella q10 e una tempistica errata dei background task nella q28, nonostante gli ID delle citazioni fossero tecnicamente validi. Nel nuovo set, il controllo di copertura ha rifiutato due domande riformulate con risposta nel corpus e una risposta ha citato un passaggio non pertinente. Tutte le domande hanno l'etichetta provvisoria `draft_unreviewed`; l'intero set non ha ricevuto una revisione umana indipendente.

Metodo e casi di errore: [rapporto sulla qualità](reports/QUALITY.md). Risultati originali: [esecuzione principale](reports/evaluation.json), [nuovo set](reports/fresh-probe.json), [controlli a campione delle fonti](reports/source-spot-checks.json). Verifiche dell'interfaccia: [ui-checks.json](reports/ui-checks.json).

## Avvio locale

Ambiente verificato: macOS, Apple M3, 16 GB di RAM, Python 3.10. Il modello installato `qwen3:1.7b` occupa circa 1.4 GB su disco. L'applicazione non scarica modelli automaticamente.

```bash
cd /path/to/doclens
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install -e . --no-deps
ollama list
.venv/bin/python -m uvicorn doclens.app:app --host 127.0.0.1 --port 8013
```

Apri <http://127.0.0.1:8013>. La documentazione delle API è su <http://127.0.0.1:8013/docs>. Ollama deve essere in esecuzione su `127.0.0.1:11434` e `qwen3:1.7b` deve comparire in `ollama list`. Se il modello non è disponibile, l'interfaccia lo segnala e offre la ricerca dei passaggi. Per fermare il server, premi Ctrl+C.

Le domande e il corpus sono in inglese. Esempi:

- `How do I raise HTTPException with a 404 status?`
- `How do I declare a required query parameter?`
- `When do background tasks run?`
- `How do I configure Kubernetes autoscaling for a FastAPI deployment?` - è prevista un'astensione: l'argomento non è nel corpus.

È una demo locale per un solo utente. Non dispone di autenticazione, coda delle richieste o limiti di carico per un servizio pubblico. L'applicazione non salva la cronologia delle domande; lo script di valutazione registra in un rapporto le domande e le risposte del proprio set fisso.

## Struttura del progetto

```text
doclens/
  app.py             API HTTP e file statici
  config.py          percorsi, modello e indirizzo locale di Ollama
  retrieval.py       tokenizzazione, BM25 e ordinamento dei risultati
  rag.py             richieste al modello, astensione e verifica degli ID delle citazioni
  static/            HTML, CSS e JavaScript senza build del frontend
scripts/
  build_corpus.py    download ed elaborazione riproducibile dell'HTML
  evaluate.py        ricerca e RAG sullo stesso set di domande
  ui_smoke.py        verifiche dell'interfaccia in un profilo Chrome headless separato
data/
  raw/               copie delle pagine ufficiali
  manifest.json      URL, tempi di download e SHA-256 di ogni file
  chunks.json        passaggi con titoli e link alle sezioni
eval/questions.json  45 domande con risposta e 15 senza risposta nel corpus
tests/               test di ricerca, astensione, API, corpus ed errori
reports/             risposte effettive, metriche, screenshot e limiti
```

Non ci sono LangChain, database vettoriali o un framework separato per il frontend. Il corpus è piccolo e il normale codice Python rende facile seguire ogni passaggio.

1. `build_corpus.py` estrae l'articolo, rimuove la navigazione, conserva il codice e divide il testo per titolo di sezione. Le sezioni grandi diventano frammenti di circa 2.400 caratteri con una piccola sovrapposizione. Ogni link porta alla sezione corrispondente della pagina originale.
2. BM25 ordina i frammenti usando le parole della domanda. L'indice include i titoli delle pagine e delle sezioni. La ricerca lessicale gestisce sinonimi e altre lingue meno bene di un modello di embedding; una domanda in un'altra lingua può non trovare il materiale inglese.
3. I quattro frammenti migliori vengono passati al modello. Le corrispondenze molto deboli vengono rifiutate prima della generazione. Almeno il 60% delle parole significative della domanda deve inoltre essere presente nei frammenti recuperati. `min_score=2.0` e `min_coverage=0.6` sono euristiche, non probabilità di affidabilità né prove che esista una risposta. Il controllo di copertura è stato aggiunto dopo gli errori sul set di sviluppo. È conservativo e può rifiutare parafrasi o sinonimi.
4. Il modello restituisce un JSON con risposta, decisione sulla possibilità di rispondere e riferimenti da `[S1]` a `[S4]`. Uno schema JSON semplice è compatibile con il backend installato; Python verifica i limiti di lunghezza.
5. Pydantic verifica la struttura. I riferimenti sconosciuti o non dichiarati vengono rifiutati. Gli ID aggiuntivi dichiarati tra i frammenti recuperati non vengono mostrati se la risposta non li menziona. Gli URL provengono dal corpus, non dal testo del modello. Un'astensione ha stato `abstained`; un errore di Ollama restituisce HTTP 503 ed è registrato come errore tecnico.

La verifica degli ID impedisce indirizzi di fonti inventati, ma non dimostra che una fonte sostenga ogni affermazione. Il modello piccolo può sbagliare o astenersi anche quando la risposta è presente. Per questo l'interfaccia espone i passaggi originali e la valutazione misura separatamente citazioni, astensioni e contenuto delle risposte.

## Corpus

Dodici pagine del [tutorial ufficiale di FastAPI](https://fastapi.tiangolo.com/tutorial/): path parameters, query parameters, request body, response model, response status code, handling errors, dependencies, background tasks, middleware, CORS, testing e request files. La copia salvata produce 135 frammenti.

L'avvio normale non contatta il sito. La ricostruzione dall'HTML salvato verifica gli hash SHA-256 e dovrebbe produrre lo stesso JSON:

```bash
.venv/bin/python scripts/build_corpus.py
```

Un aggiornamento esplicito richiede accesso alla rete e modifica i dati e i risultati della valutazione:

```bash
.venv/bin/python scripts/build_corpus.py --refresh
```

I materiali originali appartengono agli autori di FastAPI. Le informazioni sulla licenza sono nel [repository di FastAPI](https://github.com/fastapi/fastapi/blob/master/LICENSE). Gli URL delle fonti e i tempi delle copie salvate sono in `data/manifest.json`.

## Verifiche e valutazione

```bash
.venv/bin/ruff check doclens scripts eval tests
.venv/bin/ruff format --check doclens scripts eval tests
.venv/bin/mypy doclens scripts eval tests
.venv/bin/python -m pytest -m 'not live' -q
.venv/bin/python -m pytest -m live -q
.venv/bin/python scripts/evaluate.py --output reports/search-baseline
.venv/bin/python scripts/evaluate.py --live --output reports/evaluation
.venv/bin/python scripts/evaluate.py --live --dataset eval/fresh-probe.json --output reports/fresh-probe
```

Senza `--live`, la valutazione non chiama il modello. Con `--live`, ogni domanda passa attraverso l'istanza locale reale di Ollama e il risultato viene subito scritto in JSONL. Gli errori vengono registrati separatamente dalle astensioni. Un'esecuzione può richiedere diversi minuti. Riutilizzare lo stesso `--output` sostituisce il rapporto; scegli un nome nuovo per confrontare le esecuzioni.

Definizioni delle metriche, risultati effettivi e casi di errore sono in [reports/QUALITY.md](reports/QUALITY.md). Le distinzioni principali:

- `gold_page_hit_at_4` verifica se la pagina attesa compare tra i quattro frammenti recuperati. Non dimostra la correttezza della risposta.
- `answer_keyword_pass_on_answerable` verifica la presenza delle parole attese nella risposta. È un indicatore approssimativo del contenuto, non una misura di accuratezza semantica.
- `citation_page_precision` confronta le pagine citate con le etichette. Non verifica il supporto alle singole affermazioni.
- `abstention_recall` misura l'astensione sulle domande fuori dal corpus; `false_abstention_on_answerable` misura i rifiuti superflui.
- p50 è la mediana; p95 usa il rango più vicino, `ceil(0.95 * n)`. Entrambi descrivono una singola esecuzione sequenziale sulla macchina indicata.

Tutte le 60 domande hanno `review_status: draft_unreviewed`. Non è stata completata una revisione umana indipendente di tutte le etichette e risposte. Questo set, costruito per il corpus, serve a verificare lo sviluppo e non è un benchmark indipendente. Le verifiche delle parole chiave superate non vanno presentate come "accuratezza RAG del 100%".

Il file separato `eval/fresh-probe.json` contiene 12 nuove domande: sei parafrasi con risposta nel corpus e sei domande fuori dal corpus. È stato creato dopo aver fissato le soglie, separatamente da dev60, e non è stato usato per ulteriori modifiche ai parametri. È un piccolo esperimento aggiuntivo senza revisore indipendente; i risultati sono in `reports/fresh-probe.*`.

Per verificare l'interfaccia, avvia il server e poi esegui:

```bash
.venv/bin/python scripts/ui_smoke.py
```

Lo script usa Chrome installato con un nuovo profilo temporaneo per verificare ricerca, risposta generata reale, astensione, lettura delle fonti, larghezza mobile e un HTTP 503 simulato. Usa `--chrome` per indicare un altro percorso dell'eseguibile del browser. Le schede personali non vengono usate.

## Configurazione

Variabili facoltative: `DOCLENS_MODEL`, `DOCLENS_OLLAMA_URL`, `DOCLENS_CORPUS`. I valori predefiniti non richiedono configurazione. L'indirizzo di Ollama è limitato a HTTP su loopback, così le domande non vengono inviate a un server remoto. `DOCLENS_MODEL` seleziona un modello già installato; il codice non lo scarica.

## Prossimi passi

Prima verifica in modo indipendente le etichette e se le fonti sostengono le affermazioni delle risposte. Poi aggiungi un set separato di parafrasi e domande con risposte solo parzialmente disponibili. Infine confronta BM25 con una ricerca basata su embedding o con un altro modello locale, per distinguere gli errori di ricerca da quelli di generazione.
