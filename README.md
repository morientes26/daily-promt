# Daily ChatGPT Prompt → Email

Každý deň automaticky zavolá OpenAI API a výsledok pošle emailom.
Beží na **GitHub Actions** — zadarmo, bez servera, bez otvoreného počítača.

---

## Nastavenie (5 minút)

### 1. Vytvor GitHub repo
```bash
git init daily-prompt
cd daily-prompt
# skopíruj súbory z tohto projektu
git add .
git commit -m "init"
gh repo create daily-prompt --private --push
```

### 2. Nastav GitHub Secrets
`Settings → Secrets and variables → Actions → New repository secret`

| Secret | Hodnota |
|--------|---------|
| `OPENAI_API_KEY` | Tvoj OpenAI kľúč z platform.openai.com |
| `EMAIL_SENDER` | Gmail adresa odosielateľa (napr. `bot@gmail.com`) |
| `EMAIL_PASSWORD` | **Gmail App Password** — nie bežné heslo! Viď nižšie. |
| `EMAIL_RECIPIENT` | Adresa, kam chceš dostávať emaily |

### 3. Nastav Variables (voliteľné)
`Settings → Secrets and variables → Actions → Variables`

| Variable | Popis | Default |
|----------|-------|---------|
| `OPENAI_MODEL` | Model (napr. `gpt-4o`, `gpt-4o-mini`) | `gpt-4o` |
| `SYSTEM_PROMPT` | Systémový prompt | všeobecný asistent |
| `USER_PROMPT` | Denný prompt | SW engineering insight |

---

## Gmail App Password

Gmail vyžaduje App Password (nie bežné heslo):

1. Zapni 2FA na Google účte
2. Choď na: **myaccount.google.com → Security → App passwords**
3. Vyber `Mail` + `Other (custom name)` → `GitHub Bot`
4. Skopíruj vygenerované 16-znakové heslo → vlož do `EMAIL_PASSWORD`

---

## Zmena promptu

Prompt zmeníš priamo v GitHub UI bez dotyku kódu:
`Settings → Secrets and variables → Actions → Variables → USER_PROMPT`

---

## Ručné spustenie

`Actions → Daily ChatGPT Prompt → Run workflow`

---

## Cena

- **GitHub Actions**: zadarmo (2 000 min/mesiac na private repo, pre tento use-case ~5 min/mesiac)
- **OpenAI**: `gpt-4o-mini` ≈ $0.001/deň | `gpt-4o` ≈ $0.01–0.05/deň
