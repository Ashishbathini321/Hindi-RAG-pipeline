# Hindi PDF RAG - Internship Screening Assignment

A beginner-friendly, local Retrieval-Augmented Generation (RAG) project for answering questions about `Agni_Ki_Udaan_Adhyayan_Sahayika_Hindi.pdf`, a Hindi study guide on A.P.J. Abdul Kalam.

The project extracts the PDF, normalizes Hindi text, stores multilingual embeddings in ChromaDB, retrieves relevant chunks for Hindi or English questions, generates a grounded answer, and adds citations automatically.

## 1. What you need

- Windows 10 or 11
- Python 3.11 (`py -3.11 --version` should work)
- Internet access once for Python packages and the embedding model
- The supplied `Agni_Ki_Udaan_Adhyayan_Sahayika_Hindi.pdf` file
- Optional but recommended: [Ollama](https://ollama.com/) for polished local-LLM answers

## 2. Project folders

```text
Hindi_RAG_Assignment/
├── app/                    # PDF extraction, chunking, retrieval, and answers
├── data/                   # Put the supplied PDF here; PDFs are ignored by Git
├── outputs/                # Generated six-query answer report
├── tests/                  # Automated checks
├── main.py                 # Main command-line program
├── test_queries.json       # The six required assignment queries
├── requirements.txt        # Python packages
├── setup_windows.cmd       # Command Prompt setup helper
├── ingest_pdf.cmd          # Command Prompt ingestion helper
└── run_required_tests.cmd  # Command Prompt test helper
```

## 3. Open the project in PowerShell

Open **PowerShell** and run:

```powershell
cd "C:\Users\ashis\Documents\Codex\2026-10-17\referenced-chatgpt-conversation-this-is-an\outputs\Hindi_RAG_Assignment"
```

Your prompt should begin with `PS`. If it does not, you are in Command Prompt; use [Section 12](#12-command-prompt-alternative).

## 4. Create the virtual environment and install packages

Run each command in order. These commands use the project environment directly, so PowerShell activation is not required.

```powershell
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
& .\.venv\Scripts\python.exe -m unittest discover -s .\tests -v
```

The final command should say that all tests passed.

### Optional: activate the environment

If you prefer activation and PowerShell blocks it, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

This policy change applies only to the current PowerShell window. Activation is optional; every command below works without it.

## 5. Add the supplied PDF

Copy the source PDF into the `data` folder. Replace the example source path with the real file location.

```powershell
Copy-Item "C:\path\to\Agni_Ki_Udaan_Adhyayan_Sahayika_Hindi.pdf" .\data\
Get-ChildItem .\data
```

The listing must include:

```text
Agni_Ki_Udaan_Adhyayan_Sahayika_Hindi.pdf
```

The source PDF is ignored by Git. Do not publish it unless the assignment provider explicitly allows that.

## 6. Build the local RAG index

Run this command after adding the PDF:

```powershell
& .\.venv\Scripts\python.exe main.py ingest --pdf .\data\Agni_Ki_Udaan_Adhyayan_Sahayika_Hindi.pdf --preview
```

What happens:

1. PDF text is extracted page by page.
2. Hindi Unicode is normalized and common PDF control artifacts are removed.
3. Text is split at Hindi danda (`।`) and stored in page-local chunks.
4. Each chunk is embedded with `intfloat/multilingual-e5-base`.
5. Chunks, vectors, and metadata are stored locally in `chroma_db/`.

The first run downloads the embedding model. Later runs reuse the local model cache. Successful output ends with something similar to:

```text
Indexed 37 chunks from 22 pages in ...\chroma_db.
```

### Re-index after changing the source or chunking

The ingestion command safely replaces the existing collection. Run it again whenever you change the PDF, extraction/chunking code, or chunk settings:

```powershell
& .\.venv\Scripts\python.exe main.py ingest --pdf .\data\Agni_Ki_Udaan_Adhyayan_Sahayika_Hindi.pdf --chunk-words 180 --overlap-words 30 --preview
```

## 7. Ask one question

### Offline extractive answer

This does not require a local LLM. It chooses the most relevant sentence from retrieved chunks and is useful for checking retrieval.

```powershell
& .\.venv\Scripts\python.exe main.py ask --query "कलाम को भारत रत्न किस वर्ष प्राप्त हुआ?" --generator extractive
```

### Local-LLM answer with Ollama

Install Ollama from [ollama.com](https://ollama.com/), then download the recommended model once:

```powershell
ollama pull qwen2.5:3b
ollama list
```

Ask an English question with a grounded local answer:

```powershell
& .\.venv\Scripts\python.exe main.py ask --query "Which institution did Kalam attend to study aeronautical engineering?" --generator ollama --ollama-model qwen2.5:3b
```

Each response includes an automatic citation such as:

```text
page: 6 · section: "Page 6" · chunk_id: chunk-0010 · score: 0.799
```

The citation fields are stored in ChromaDB metadata; they are not manually typed into the answer.

## 8. Generate the six required assignment answers

The six required questions are in `test_queries.json`. Generate the submission report with Ollama:

```powershell
& .\.venv\Scripts\python.exe main.py run-tests --generator ollama --ollama-model qwen2.5:3b
```

The report is saved here:

```text
outputs\test_answers.md
```

Open it with:

```powershell
Get-Content -Encoding UTF8 .\outputs\test_answers.md
```

### Offline fallback

If Ollama is unavailable, you can still test retrieval and citations:

```powershell
& .\.venv\Scripts\python.exe main.py run-tests --generator extractive
```

Use the extractive mode only as a retrieval check. For the final assignment log, prefer the Ollama version and review every answer against its primary citation.

## 9. Review before submission

Open `outputs\test_answers.md` and check every answer against the **Primary source** citation. In particular, confirm these facts:

| Query | Fact to verify in the cited source |
| --- | --- |
| SLV-III | Rohini satellite; 1980 |
| Bharat Ratna | 1997 |
| Pokhran-II | Kalam had a central organizational role with Department of Atomic Energy scientists while serving as Defence Minister's scientific adviser and DRDO chief |
| Aeronautical engineering | Madras Institute of Technology (MIT), Chennai |
| Autobiography | Co-written with Arun Tiwari; published in 1999 |
| Death in 2015 | Collapsed while lecturing at Indian Institute of Management Shillong on 27 July 2015 |

Do **not** edit citations by hand. If an answer is wrong, improve retrieval or the generation prompt, re-run the program, and preserve the newly generated metadata.

## 10. How the project works

### Hindi text handling

- Reads and writes text as UTF-8.
- Normalizes text with Unicode NFC.
- Removes BOM, soft hyphen, zero-width-space, and unmapped PDF control markers.
- Treats Hindi danda (`।`) as a sentence boundary.
- Preserves ZWJ and ZWNJ because they can be meaningful in Indic text.
- Prefers ordinary PDF extraction because layout extraction can insert spaces between Devanagari characters in this source PDF.

The supplied PDF has some incomplete embedded-font mappings. A few source characters may therefore be imperfect after extraction, which is why citation review is essential.

### Chunking strategy

- Maximum chunk size: **180 words**.
- Overlap: **30 words**, using complete trailing sentences where possible.
- Chunks never span pages, so each citation has one clear page number.
- Metadata stored for every chunk: `page`, `section`, `chunk_id`, and `embedding_model`.

### Embeddings and vector database

- Vector database: **ChromaDB**, stored locally in `chroma_db/`.
- Embedding model: **`intfloat/multilingual-e5-base`**.
- E5 document chunks use the `passage:` prefix; questions use the `query:` prefix.
- Vectors are normalized and Chroma uses cosine distance.
- The multilingual model enables English questions to retrieve Hindi evidence.

### Answer generation

- `extractive`: selects the closest source sentence from retrieved chunks and does not invent facts.
- `ollama`: sends the primary evidence sentence to the local model and asks it to answer only from that evidence. The program attaches metadata citations after generation.

## 11. Troubleshooting

### `ModuleNotFoundError: No module named 'pypdf'`

You are using global Python rather than the project environment. Run:

```powershell
& .\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
& .\.venv\Scripts\python.exe main.py --help
```

### `PDF not found`

Check the source file:

```powershell
Get-ChildItem .\data
```

Then ensure the ingestion command uses the exact filename.

### `Could not reach Ollama at http://localhost:11434`

Open Ollama and check that the model exists:

```powershell
ollama list
ollama pull qwen2.5:3b
```

Then run the answer command again.

### `Failed to send telemetry event ...`

This ChromaDB/PostHog warning does not affect indexing, retrieval, citations, or answers. To refresh the pinned package versions, run:

```powershell
& .\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

### Hindi displays as `à¤...`

Use:

```powershell
Get-Content -Encoding UTF8 .\outputs\test_answers.md
```

### PowerShell blocks `Activate.ps1`

Activation is not required. Use the direct `.venv` commands in this README, or run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### You are in Command Prompt, not PowerShell

Do not use PowerShell's `&` or `Get-ChildItem` commands there. Use the `.cmd` helpers in [Section 12](#12-command-prompt-alternative).

## 12. Command Prompt alternative

If your prompt looks like this:

```text
C:\Users\...\Hindi_RAG_Assignment>
```

run:

```bat
setup_windows.cmd
```

After copying the PDF into `data`, run:

```bat
ingest_pdf.cmd
run_required_tests.cmd
```

`run_required_tests.cmd` uses the offline extractive mode. To use Ollama from Command Prompt:

```bat
.venv\Scripts\python.exe main.py run-tests --generator ollama --ollama-model qwen2.5:3b
```

```bat
& .\.venv\Scripts\python.exe main.py run-tests --generator ollama --ollama-model qwen2.5:3b
Get-Content -Encoding UTF8 .\outputs\test_answers.md
```
